// Actual Chrome interactions: isolated contributor and maintainer contexts.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright-core');
const [stateDir, fixtureDir, outputDir] = process.argv.slice(2).map(value => path.resolve(value));
const server = JSON.parse(fs.readFileSync(path.join(stateDir, 'server.json')));
const access = JSON.parse(fs.readFileSync(path.join(stateDir, 'fixture-access.json'))).access_codes;
const fixture = JSON.parse(fs.readFileSync(path.join(fixtureDir, 'ten-item-fixtures.json')));
const checksum = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
const check = (condition, message) => { if (!condition) throw new Error(message); };

(async () => {
  fs.mkdirSync(outputDir); const started = Date.now();
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  const errors = [], requests = [];
  async function rolePage(role) {
    const context = await browser.newContext({viewport: {width: 1280, height: 900}});
    await context.route('**/*', route => route.request().url().startsWith(server.url + '/') ? route.continue() : route.abort());
    const page = await context.newPage();
    page.on('pageerror', error => errors.push(String(error)));
    page.on('request', request => requests.push(request.url()));
    await page.goto(server.url);
    await page.locator('#role').selectOption(role);
    await page.locator('#code').fill(access[role]);
    await page.getByRole('button', {name:'Sign in', exact:true}).click();
    await page.waitForFunction(role => document.querySelector('#signed-in').textContent.includes('fixture ' + role), role);
    return page;
  }
  try {
    const contributor = await rolePage('contributor');
    const maintainer = await rolePage('maintainer');
    const firstCreate = fixture.entries.find(row => row.action === 'CREATE');
    const firstReplacement = fixture.entries.find(row => row.action === 'REPLACE');
    const ordered = [firstCreate, firstReplacement, ...fixture.entries.filter(row => row !== firstCreate && row !== firstReplacement)];
    const results = [], rejections = [];
    for (const [index, entry] of ordered.entries()) {
      await contributor.locator('#item').selectOption(entry.identity);
      await contributor.locator('#poster').setInputFiles(path.join(fixtureDir, entry.approved_file));
      await contributor.getByRole('button', {name:'Submit and preview', exact:true}).click();
      const selector = `.card[data-identity="${entry.identity}"]`;
      await contributor.locator(selector).waitFor();
      await contributor.locator(selector + ' img').evaluate(image => image.decode());
      const id = await contributor.locator(selector).getAttribute('data-id');
      if (index === 0) {
        const forbidden = await contributor.evaluate(async ({id, hash}) => {
          const response = await fetch('/api/approve', {method:'POST', headers:{'Content-Type':'application/json','X-CSRF-Token':state.csrf}, body:JSON.stringify({id,sha256:hash})});
          return {status:response.status,...await response.json()};
        }, {id, hash:entry.approved_sha256});
        check(forbidden.status === 403 && forbidden.error === 'maintainer_required', 'Contributor role escalation was not rejected');
        rejections.push({case:'contributor cannot approve', ...forbidden});
      }
      await maintainer.reload();
      await maintainer.locator(selector + '[data-status="preview"]').waitFor();
      if (index === 0) {
        for (const test of [{route:'stage', hash:entry.approved_sha256, csrf:true, status:409}, {route:'approve',hash:'0'.repeat(64),csrf:true,status:409}, {route:'approve',hash:entry.approved_sha256,csrf:false,status:403}]) {
          const rejected = await maintainer.evaluate(async ({id, test}) => {
            const response = await fetch('/api/' + test.route, {method:'POST', headers:{'Content-Type':'application/json', ...(test.csrf ? {'X-CSRF-Token':state.csrf} : {})}, body:JSON.stringify({id,sha256:test.hash})});
            return {status:response.status,...await response.json()};
          }, {id,test});
          check(rejected.status === test.status, 'Approval/CSRF rejection failed');
          rejections.push({case:test.csrf ? 'unapproved or wrong-hash action' : 'missing CSRF',...rejected});
        }
      }
      await maintainer.locator(selector + ' img').scrollIntoViewIfNeeded();
      await maintainer.locator(selector + ' img').evaluate(image => image.decode());
      const approving = maintainer.waitForResponse(response => response.url().endsWith('/api/approve') && response.request().method() === 'POST');
      await maintainer.locator(selector + ' [data-action="approve"]').click();
      const approved = await approving;
      check(approved.ok(), 'Approval failed: ' + await approved.text());
      await maintainer.locator(selector + '[data-status="approved"]').waitFor();
      const staging = maintainer.waitForResponse(response => response.url().endsWith('/api/stage') && response.request().method() === 'POST');
      await maintainer.locator(selector + ' [data-action="stage"]').click();
      const staged = await staging;
      check(staged.ok(), 'Staging failed: ' + await staged.text());
      await maintainer.locator(selector + '[data-status="staged"]').waitFor();
      await maintainer.locator(selector + ' [data-receipt="matched"]').waitFor();
      const destination = path.join(stateDir, 'destination', entry.destination);
      const actual = checksum(destination);
      check(actual === entry.approved_sha256, 'Destination differs from approved JPEG');
      results.push({identity:entry.identity,action:entry.action,destination,approved_sha256:entry.approved_sha256,actual_sha256:actual,match:true});
      console.log(`${index+1}/10 ${entry.action}: ${entry.display_name} MATCH`);
      if (index === 1) {
        await maintainer.screenshot({path:path.join(outputDir,'one-create-one-replacement.png'),fullPage:true});
        fs.writeFileSync(path.join(outputDir,'first-two-result.json'),JSON.stringify({candidate_commit:server.candidate_commit,creates:1,replacements:1,results},null,2)+'\n');
      }
    }
    const replaced = new Set(fixture.entries.filter(row => row.action === 'REPLACE').map(row => row.destination));
    const baseline = path.join(fixtureDir,'staging-baseline','playlist');
    let preserved = 0;
    for (const file of fs.readdirSync(baseline)) {
      const relative = 'playlist/' + file;
      if (!replaced.has(relative)) { check(checksum(path.join(baseline,file)) === checksum(path.join(stateDir,'destination',relative)), 'Untouched historical poster changed'); preserved++; }
    }
    check(preserved===7 && fs.readdirSync(path.join(stateDir,'destination','playlist')).length===17, 'Incorrect destination inventory');
    check(errors.length === 0, 'Browser JavaScript error');
    check(requests.every(url => url.startsWith(server.url + '/')), 'Browser requested an external origin');
    await maintainer.screenshot({path:path.join(outputDir,'ten-item-staging.png'),fullPage:true});
    const receipts = path.join(stateDir,'staging-receipts.json');
    const result = {kind:'phase6-real-chrome-staging-result',candidate_commit:server.candidate_commit,browser:browser.version(),playwright:require(path.join(process.env.PLAYWRIGHT_MODULE || 'playwright-core','package.json')).version,creates:8,replacements:2,destination_hash_matches:10,untouched_historical_posters_preserved:7,total_destination_posters:17,results,rejections,receipt_sha256:checksum(receipts),fixture_manifest_sha256:checksum(path.join(fixtureDir,'ten-item-fixtures.json')),browser_javascript_errors:errors,external_browser_requests:0,elapsed_seconds:(Date.now()-started)/1000,simulation:true,role_scope:'local fixture access codes',native_lifecycle_replacement_acceptance:false,live_registry_reservations:'PENDING',catalog_mappings:'PENDING',publication_authorized:false,activation_authorized:false};
    fs.writeFileSync(path.join(outputDir,'browser-result.json'),JSON.stringify(result,null,2)+'\n');
    console.log(JSON.stringify({creates:8,replacements:2,matches:10,preserved:7,elapsed_seconds:result.elapsed_seconds}));
  } finally { await browser.close(); }
})().catch(error => {console.error(error);process.exitCode=1;});
