let state = null;
const node = id => document.getElementById(id);
async function request(path, payload) {
  const response = await fetch(path, payload === undefined ? {} : {method:'POST', headers:{'Content-Type':'application/json','X-CSRF-Token':state?.csrf || ''},body:JSON.stringify(payload)});
  const value = await response.json();
  if (!response.ok) throw new Error(value.error || 'Request failed');
  return value;
}
function message(value) {node('message').textContent=value;}
function text(tag, value, className) {const e=document.createElement(tag);e.textContent=value;if(className)e.className=className;return e;}
function fields() {
  const entry=state.entries.find(row => row.identity===node('item').value);
  if (!entry) return;
  const params=entry.render_request.parameters;
  node('style').value=entry.render_request.composition_style;
  node('logo').value=params.logo;
  node('colour').value=params.base_color;
  node('caption').value=params.text;
  adaptStyle();
}
function adaptStyle() {
  const style=state.styles.find(row=>row.id===node('style').value);
  node('caption-label').hidden=!style.caption;
  node('caption').required=style.caption;
  node('caption').disabled=!style.caption;
  node('style-help').textContent=style.caption ? 'Playlist: visible-alpha contain, 1600 x 900 logo box, 100px minimum caption gap.' : 'Existing Franchise logo-only preset: proportional target width; no caption input or new fit policy.';
}
async function action(route,payload) {
  await request('/api/'+route,payload);
  await refresh();
  message(route==='stage' ? 'Staging file and catalog state verified; receipt recorded.' : 'Staging request updated.');
}
async function refresh() {
  state=await request('/api/state');
  node('signed-in').textContent='Signed in as fixture '+state.role;
  node('submit-section').hidden=state.role!=='contributor';
  node('reference-section').hidden=state.role!=='maintainer';
  node('review-section').hidden=false;
  const selection=node('item').value;
  node('item').replaceChildren(...state.entries.map(row=>new Option(row.display_name,row.identity)));
  node('style').replaceChildren(...state.styles.map(row=>new Option(row.label,row.id)));
  node('logo').replaceChildren(...state.logos.map(logo=>new Option(logo,logo)));
  if(selection)node('item').value=selection;
  fields();
  const main=state.submissions.filter(row=>!row.identity.startsWith('fixture.') && row.status==='staged');
  node('summary').textContent=`Main set: ${main.filter(r=>r.action==='CREATE').length} adds, ${main.filter(r=>r.action==='REPLACE').length} in-place replacements verified. Live publication pending.`;
  node('catalog').textContent=JSON.stringify(state.catalog,null,2);
  node('cards').replaceChildren();
  for (const item of state.submissions) {
    const card=text('article','','card');Object.assign(card.dataset,{id:item.id,identity:item.identity,status:item.status});
    card.append(text('h3',item.display_name),text('p',`${item.action} / ${item.status}`,'status'));
    const image=document.createElement('img');image.width=2000;image.height=3000;image.loading='lazy';image.src='/preview/'+item.id;image.alt=item.action==='REMOVE'?'Current poster to remove':item.display_name;card.append(image);
    card.append(text('p',item.destination),text('p','Exact submitted SHA-256 '+item.sha256,'hash'));
    if(item.reference_sha256)card.append(text('p','Approved reference '+item.reference_sha256+' / '+(item.reference_match?'MATCH':'DIFFERENT BYTES - approval blocked'),'hash'));
    if(item.render)card.append(text('p',`${item.render.style}; ${item.render.parameters.base_color}; Pillow ${item.render.pillow}`));
    const details=document.createElement('details');details.append(text('summary','Catalog change (before / after)'),text('pre',JSON.stringify(item.catalog_change,null,2)));card.append(details);
    const checks=text('ul','','checks');
    for(const check of item.checks) {const li=text('li',(check.passed?'PASS: ':'FAIL: ')+check.name);li.dataset.passed=String(check.passed);checks.append(li);}
    card.append(checks);
    const actions=text('div','','actions');
    let route,label;
    if(state.role==='contributor' && item.status==='draft'){route='submit';label='Submit generated preview';}
    if(state.role==='maintainer' && item.status==='preview'){route='approve';label='Approve exact render and change';}
    if(state.role==='maintainer' && item.status==='approved'){route='stage';label='Write to staging and verify';}
    if(route) {
      const button=text('button',label);button.dataset.action=route;
      button.disabled=route!=='submit' && !item.can_approve;
      button.onclick=async()=>{button.disabled=true;try{await action(route,{id:item.id,sha256:item.sha256,review_digest:item.review_digest});}catch(error){message(error.message);await refresh();}};
      actions.append(button);
    }
    if(item.receipt){const p=text('p','Verified file + catalog: '+item.receipt.destination+(item.receipt.file_absent?' (removed)':''));p.dataset.receipt='matched';card.append(p);}
    card.append(actions);node('cards').append(card);
  }
}
node('login').onsubmit=async event=>{event.preventDefault();try{await request('/api/login',{role:node('role').value,code:node('code').value});node('code').value='';await refresh();message('Fixture role signed in.');}catch(error){message(error.message);}};
node('item').onchange=fields;
node('style').onchange=adaptStyle;
node('generate').onsubmit=async event=>{
  event.preventDefault();const button=event.submitter;button.disabled=true;message('Generating with the production Python renderer...');
  try{await action('generate',{identity:node('item').value,style:node('style').value,logo:node('logo').value,colour:node('colour').value,caption:node('caption').disabled?'':node('caption').value});message('Generated preview ready. Review it, then submit.');}catch(error){message(error.message);}finally{button.disabled=false;}
};
node('remove').onclick=()=>action('remove',{identity:'fixture.playlist.disposable'}).catch(error=>message(error.message));
for(const active of [true,false])node(active?'attach':'release').onclick=()=>action('reference',{active}).catch(error=>message(error.message));
refresh().catch(()=>{});
