// Contributor generation and maintainer lifecycle actions in real Chrome.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright-core');
const [stateDir,fixtureDir,out]=process.argv.slice(2).map(value=>path.resolve(value));
const server=JSON.parse(fs.readFileSync(path.join(stateDir,'server.json')));
const access=JSON.parse(fs.readFileSync(path.join(stateDir,'fixture-access.json'))).access_codes;
const fixtures=JSON.parse(fs.readFileSync(path.join(fixtureDir,'ten-item-fixtures.json')));
const digest=file=>crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
const read=name=>JSON.parse(fs.readFileSync(path.join(stateDir,name)));
const check=(value,message)=>{if(!value)throw new Error(message);};
const disposable='fixture.playlist.disposable',second='fixture.franchise.disposable';

(async()=>{
  fs.mkdirSync(out);const started=Date.now(),errors=[],requests=[],rejections=[],results=[],lifecycle=[];
  const browser=await chromium.launch({channel:'chrome',headless:true});
  async function rolePage(role) {
    const context=await browser.newContext({viewport:{width:1280,height:900}});
    await context.route('**/*',route=>route.request().url().startsWith(server.url+'/')?route.continue():route.abort());
    const page=await context.newPage();
    page.on('pageerror',error=>errors.push(String(error)));
    page.on('request',request=>requests.push(request.url()));
    await page.goto(server.url);await page.locator('#role').selectOption(role);await page.locator('#code').fill(access[role]);
    await page.getByRole('button',{name:'Sign in',exact:true}).click();
    await page.waitForFunction(role=>state?.role===role,role);
    return page;
  }
  const selector=item=>`.card[data-id="${item.id}"]`;
  async function click(page,locator,route) {
    const pending=page.waitForResponse(response=>response.url().endsWith('/api/'+route) && response.request().method()==='POST');
    await locator.click();const response=await pending;const body=await response.json();
    check(response.ok(),route+' failed: '+JSON.stringify(body));return body;
  }
  async function ready(page,item,status) {
    await page.locator(selector(item)+`[data-status="${status}"]`).waitFor();
  }
  async function imageReady(page,item) {
    for(const image of await page.locator(selector(item)+' img').all()) {
      await image.scrollIntoViewIfNeeded();
      await image.evaluate(i=>new Promise((resolve,reject)=>{if(i.complete && i.naturalWidth===2000)return resolve();const timer=setTimeout(()=>reject(new Error('Preview load timeout')),10000);i.onload=()=>{clearTimeout(timer);i.naturalWidth===2000?resolve():reject(new Error('Preview dimensions'));};}));
      const box=await image.boundingBox();check(Math.abs(box.width/box.height-2/3)<0.01,'Preview aspect ratio');
    }
  }
  async function generate(page,identity,colour) {
    await page.reload();await page.waitForFunction(()=>state?.role==='contributor');
    const row=await page.evaluate(identity=>state.entries.find(r=>r.identity===identity),identity);
    const existing=await page.evaluate(identity=>state.catalog[identity]?.status==='active',identity);
    await page.locator('#intent').selectOption(existing?'replace':'add');
    await page.locator(existing?'#item':'#preset').selectOption(identity);
    if(!existing)await page.locator('#title').fill(row.display_name);
    const params=row.render_request.parameters;
    await page.locator('#style').selectOption(row.render_request.composition_style);
    await page.locator('#logo').selectOption(params.logo);
    await page.locator('#colour').fill(colour || params.base_color);
    const caption=page.locator('#caption');
    if(row.render_request.composition_style==='franchise-legacy') {
      check(await caption.isDisabled() && !(await page.locator('#caption-label').isVisible()),'Franchise form must remove caption input');
    } else {check(await caption.isEnabled(),'Playlist caption required');await caption.fill(params.text);}
    const item=await click(page,page.getByRole('button',{name:'Generate preview',exact:true}),'generate');
    await ready(page,item,'draft');await imageReady(page,item);
    const submitted=await click(page,page.locator(selector(item)+' [data-action="submit"]'),'submit');
    await ready(page,item,'preview');return submitted;
  }
  async function remove(page,identity=disposable) {
    await page.reload();await page.waitForFunction(()=>state?.role==='contributor');
    await page.locator('#intent').selectOption('remove');await page.locator('#item').selectOption(identity);
    await page.locator('#reason').fill('Disposable staging lifecycle check');
    check(!(await page.locator('#render-fields').isVisible()),'Removal must not ask for render inputs');
    return click(page,page.locator('#remove'),'remove');
  }
  async function custom(page,{identity=null,title='Unmapped Browser Logo',file=null}={}) {
    await page.reload();await page.waitForFunction(()=>state?.role==='contributor');
    await page.locator('#intent').selectOption(identity?'replace':'add');
    if(identity) {
      await page.locator('#item').selectOption(identity);
      check(await page.locator('#current-poster').isVisible(),'Current catalog poster must be shown');
      if(!file)check((await page.locator('#logo').inputValue()).startsWith('uploaded:'),'Recorded unmapped logo must be prefilled for reuse');
    } else {await page.locator('#preset').selectOption('');await page.locator('#title').fill(title);}
    await page.locator('#style').selectOption('playlist-contained-v1');
    await page.locator('#colour').fill('#123456');await page.locator('#caption').fill('TIMELINE ORDER');
    await page.locator('#logo-source').selectOption(file?'upload':'mapped');
    if(file)await page.locator('#upload').setInputFiles(file);
    const item=await click(page,page.getByRole('button',{name:'Generate preview',exact:true}),'generate');
    await ready(page,item,'draft');await imageReady(page,item);
    check(item.approved_sha256===null && item.reference_sha256===null,'New bytes must have no inherited approval');
    const submitted=await click(page,page.locator(selector(item)+' [data-action="submit"]'),'submit');
    await ready(page,item,'preview');return submitted;
  }
  async function reject(page,item,expected=409,csrf=true) {
    const result=await page.evaluate(async ({item,csrf})=>{
      const response=await fetch('/api/approve',{method:'POST',headers:{'Content-Type':'application/json',...(csrf?{'X-CSRF-Token':state.csrf}:{})},body:JSON.stringify({id:item.id,sha256:item.sha256,review_digest:item.review_digest})});
      return {status:response.status,...await response.json()};
    },{item,csrf});
    check(result.status===expected,'Expected server-side approval rejection: '+JSON.stringify(result));
    rejections.push({id:item.id,action:item.action,...result});
  }
  async function stage(page,item) {
    await page.reload();await ready(page,item,'preview');await imageReady(page,item);
    if(item.action==='REPLACE')check(await page.locator(selector(item)+' .comparison img').count()===2,'Maintainer requires current/proposed side by side');
    check(await page.locator(selector(item)+' .checks [data-passed="false"]').count()===0,'Required checks not all passing');
    const approved=await click(page,page.locator(selector(item)+' [data-action="approve"]'),'approve');
    await ready(page,item,'approved');
    const staged=await click(page,page.locator(selector(item)+' [data-action="stage"]'),'stage');
    await ready(page,item,'staged');
    const receipt=staged.receipt,catalog=read('catalog.json'),destination=path.join(stateDir,'destination',staged.destination);
    check(JSON.stringify(catalog[item.identity])===JSON.stringify(receipt.catalog_entry),'Physical catalog must match receipt');
    check(receipt.identity===item.identity && receipt.relative_path===item.destination,'Identity/path must not change');
    if(item.action==='REMOVE')check(!fs.existsSync(destination) && catalog[item.identity].status==='retired','Removal file/catalog postcondition');
    else check(digest(destination)===item.sha256 && catalog[item.identity].sha256===item.sha256 && catalog[item.identity].status==='active','File/catalog hash postcondition');
    check(receipt.review_digest===approved.review_digest,'Receipt must bind approved render AND catalog change');
    return {identity:item.identity,action:item.action,destination,sha256:item.sha256,receipt,verified:true};
  }
  try {
    const contributor=await rolePage('contributor'),maintainer=await rolePage('maintainer');
    const initialCatalog=read('catalog.json');
    const mapped=await contributor.evaluate(()=>state.logos);
    const sourceRoot=path.resolve(fixtureDir,'../..');
    const sourceHashes=Object.fromEntries(mapped.map(name=>[name,digest(path.join(sourceRoot,name))]));
    // A changed background is an intentional negative control, not an approval carryover.
    const wrong=await generate(contributor,fixtures.entries[0].identity,'#123456');
    check(wrong.reference_match===false && wrong.can_approve===false,'Different render bytes must fail reference check');
    await maintainer.reload();await ready(maintainer,wrong,'preview');
    check(await maintainer.locator(selector(wrong)+' [data-action="approve"]').isDisabled(),'Failed checks must disable approval');
    await reject(maintainer,wrong);
    const mismatch={case:'changed background',expected_sha256:wrong.reference_sha256,actual_sha256:wrong.sha256,
      reason:'Contributor changed base_color from approved fixture to #123456; generated image is new bytes and receives no carried approval.',checks:wrong.checks};
    const first=fixtures.entries.find(r=>r.action==='CREATE'),replacement=fixtures.entries.find(r=>r.action==='REPLACE');
    const ordered=[first,replacement,...fixtures.entries.filter(r=>r!==first && r!==replacement)];
    for(const [index,row] of ordered.entries()) {
      const item=await generate(contributor,row.identity);
      check(item.reference_match && item.sha256===row.approved_sha256,'Investigate generated/reference hash difference: '+row.display_name);
      if(index===0){await reject(contributor,item,403);await maintainer.reload();await reject(maintainer,item,403,false);}
      results.push(await stage(maintainer,item));
      if(row.action==='REPLACE')check(initialCatalog[row.identity].destination===row.destination && read('catalog.json')[row.identity].identity===row.identity,'Replacement identity/path changed');
      console.log(`${index+1}/10 generated ${row.action}: ${row.display_name} MATCH`);
      if(index===1)fs.writeFileSync(path.join(out,'first-two-result.json'),JSON.stringify({candidate_commit:server.candidate_commit,results},null,2)+'\n');
    }
    const replacementIDs=new Set(fixtures.entries.filter(r=>r.action==='REPLACE').map(r=>r.identity));
    for(const [id,before] of Object.entries(initialCatalog))if(!replacementIDs.has(id))check(JSON.stringify(before)===JSON.stringify(read('catalog.json')[id]),'Untouched catalog entry changed');
    const replacedPaths=new Set(fixtures.entries.filter(r=>r.action==='REPLACE').map(r=>r.destination));
    let preserved=0;
    for(const name of fs.readdirSync(path.join(fixtureDir,'staging-baseline','playlist')))if(!replacedPaths.has('playlist/'+name)) {
      check(digest(path.join(fixtureDir,'staging-baseline','playlist',name))===digest(path.join(stateDir,'destination','playlist',name)),'Untouched historical bytes changed');preserved++;
    }
    check(preserved===7 && fs.readdirSync(path.join(stateDir,'destination','playlist')).length===17,'Main set inventory');
    await maintainer.locator('.card img').evaluateAll(images=>images.forEach(i=>{i.loading='eager';}));
    await maintainer.waitForFunction(()=>[...document.querySelectorAll('.card img')].every(i=>i.complete && i.naturalWidth===2000));
    await maintainer.screenshot({path:path.join(out,'ten-generated-staging.png'),fullPage:true});
    // Full disposable lifecycle, with an active-reference removal denial.
    const added=await generate(contributor,disposable);lifecycle.push(await stage(maintainer,added));
    const changed=await generate(contributor,disposable,'#556677');check(changed.sha256!==added.sha256,'Different replacement render required');lifecycle.push(await stage(maintainer,changed));
    await click(maintainer,maintainer.locator('#attach'),'reference');
    const blocked=await remove(contributor);
    await maintainer.reload();await ready(maintainer,blocked,'preview');await imageReady(maintainer,blocked);
    check(blocked.checks.some(c=>c.name==='no active references for removal' && !c.passed),'Active dependency must block removal');
    check(await maintainer.locator(selector(blocked)+' [data-action="approve"]').isDisabled(),'Blocked removal approval button');
    await reject(maintainer,blocked);
    await maintainer.locator(selector(blocked)+' details').evaluate(e=>{e.open=true;});
    await maintainer.locator(selector(blocked)).screenshot({path:path.join(out,'blocked-removal.png')});
    await click(maintainer,maintainer.locator('#release'),'reference');
    await reject(maintainer,blocked); // Original request is stale after reference revision.
    const removal=await remove(contributor);lifecycle.push(await stage(maintainer,removal));
    const restored=await generate(contributor,disposable);check(restored.action==='RESTORE','Add-back must restore tombstoned fixture identity');lifecycle.push(await stage(maintainer,restored));
    check(restored.identity===added.identity && restored.destination===added.destination,'Restoration identity/path');
    const other=await generate(contributor,second);const secondResult=await stage(maintainer,other);
    await imageReady(maintainer,other);await maintainer.locator(selector(other)).screenshot({path:path.join(out,'second-style.png')});
    // A genuine local PNG with no mapping, then both replacement logo choices.
    const files=[];
    for(const shape of ['rectangle','ellipse']) {
      const encoded=await contributor.evaluate(shape=>{const c=document.createElement('canvas');c.width=640;c.height=320;const g=c.getContext('2d');g.fillStyle='#4477AA';if(shape==='rectangle')g.fillRect(35,30,570,260);else {g.beginPath();g.ellipse(320,160,270,120,0,0,Math.PI*2);g.fill();}return c.toDataURL('image/png').split(',')[1];},shape);
      const file=path.join(out,'unmapped-'+shape+'.png');fs.writeFileSync(file,Buffer.from(encoded,'base64'));files.push(file);
      check(!Object.values(sourceHashes).includes(digest(file)),'Uploaded test logo must be unmapped');
    }
    const customAdd=await custom(contributor,{file:files[0]});const customAdded=await stage(maintainer,customAdd);
    const reused=await custom(contributor,{identity:customAdd.identity});const customReused=await stage(maintainer,reused);
    check(reused.sha256===customAdd.sha256,'Reusing recorded logo/settings must reproduce bytes');
    const staleRemoval=await remove(contributor,customAdd.identity);
    await maintainer.reload();await ready(maintainer,staleRemoval,'preview');
    await click(maintainer,maintainer.locator(selector(staleRemoval)+' [data-action="approve"]'),'approve');
    await ready(maintainer,staleRemoval,'approved');
    const uploaded=await custom(contributor,{identity:customAdd.identity,file:files[1]});const customUploaded=await stage(maintainer,uploaded);
    check(uploaded.sha256!==reused.sha256 && uploaded.identity===customAdd.identity && uploaded.destination===customAdd.destination,'Uploaded replacement must change bytes and retain identity/path');
    await imageReady(maintainer,uploaded);await maintainer.locator(selector(uploaded)).screenshot({path:path.join(out,'replacement-side-by-side.png')});
    const staleResult=await maintainer.evaluate(async item=>{const r=await fetch('/api/stage',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':state.csrf},body:JSON.stringify({id:item.id,sha256:item.sha256,review_digest:item.review_digest})});return {status:r.status,...await r.json()};},staleRemoval);
    check(staleResult.status===409 && staleResult.error==='required_check_failed','Newer replacement must invalidate approved removal');
    rejections.push({case:'newer replacement invalidates approved removal',...staleResult});
    check(digest(customUploaded.destination)===uploaded.sha256,'Stale removal must leave newer replacement intact');
    for(const [name,hash] of Object.entries(sourceHashes))check(digest(path.join(sourceRoot,name))===hash,'Shared source logo must be preserved');
    for(const file of files)check(fs.existsSync(path.join(stateDir,'uploaded-logos',digest(file)+'.png')),'Uploaded source logo must be retained');
    check(errors.length===0 && requests.every(url=>url.startsWith(server.url+'/')),'Browser errors or external requests');
    const result={kind:'phase6-generated-browser-lifecycle-proof',candidate_commit:server.candidate_commit,
      browser:browser.version(),playwright:require(path.join(process.env.PLAYWRIGHT_MODULE || 'playwright-core','package.json')).version,
      creates:8,replacements:2,generated_reference_matches:10,destination_hash_matches:10,
      unchanged_historical_files:preserved,main_set:results,negative_reference_case:mismatch,disposable:lifecycle,
      action_specific_proof:{unmapped_add:customAdded,recorded_logo_replace:customReused,uploaded_logo_replace:customUploaded,
        prior_approved_removal_rejected:staleResult,unmapped_logo_fixtures:files.map(file=>({file,sha256:digest(file)})),shared_mapped_logos_preserved:mapped.length,uploaded_logos_preserved:files.length},
      second_style:secondResult,rejections,catalog_sha256:digest(path.join(stateDir,'catalog.json')),
      receipts_sha256:digest(path.join(stateDir,'staging-receipts.json')),fixture_manifest_sha256:digest(path.join(fixtureDir,'ten-item-fixtures.json')),
      browser_errors:errors,external_requests:0,elapsed_seconds:(Date.now()-started)/1000,
      restoration:'owned staging catalog only; native registry tombstone reuse remains blocked',
      native_lifecycle_replacement_acceptance:false,live_registry_reservations:'PENDING',live_catalog_mappings:'PENDING',publication_authorized:false};
    fs.writeFileSync(path.join(out,'browser-result.json'),JSON.stringify(result,null,2)+'\n');
    console.log(JSON.stringify({creates:8,replacements:2,matches:10,disposable_actions:lifecycle.map(r=>r.action),second_style:other.render.style,elapsed_seconds:result.elapsed_seconds}));
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
