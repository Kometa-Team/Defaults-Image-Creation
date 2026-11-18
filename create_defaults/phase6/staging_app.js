let state=null;
const node=id=>document.getElementById(id);
async function request(path,payload) {
  const response=await fetch(path,payload===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':state?.csrf || ''},body:JSON.stringify(payload)});
  const value=await response.json();if(!response.ok)throw new Error(value.error || 'Request failed');return value;
}
function message(value){node('message').textContent=value;}
function text(tag,value,className){const e=document.createElement(tag);e.textContent=value;if(className)e.className=className;return e;}
function adaptLogo(){const upload=node('logo-source').value==='upload';node('upload-label').hidden=!upload;node('mapped-label').hidden=upload;node('upload').required=upload && node('intent').value!=='remove';}
function adaptStyle(){
  const style=state.styles.find(row=>row.id===node('style').value);if(!style)return;
  node('caption-label').hidden=!style.caption;node('caption').required=style.caption;node('caption').disabled=!style.caption || node('intent').value==='remove';
  node('style-help').textContent=style.id==='playlist-contained-v1'?'Playlist: visible-alpha contain, 1600 x 900 logo box, 100px minimum caption gap.':style.caption?'Recorded legacy Playlist layout: proportional logo width and existing caption.':'Existing Franchise logo-only preset; no caption input.';
}
function fillRender(record){
  const preset=state.entries.find(r=>r.identity==='fixture.playlist.disposable');
  const settings=record?.render_request || preset.render_request;
  const p=settings.parameters;
  node('style').value=settings.composition_style;
  if(p.logo && ![...node('logo').options].some(o=>o.value===p.logo))node('logo').add(new Option('Recorded uploaded logo '+p.logo,p.logo));
  node('logo').value=p.logo || '';node('colour').value=p.base_color || '#123456';node('caption').value=p.text || '';
  node('logo-source').value=p.logo?'mapped':'upload';node('upload').value='';adaptLogo();adaptStyle();
  if(record && !record.render_request){node('logo').value='';node('logo-source').value='upload';adaptLogo();}
}
function fields(){
  const intent=node('intent').value,add=intent==='add',remove=intent==='remove';
  node('add-fields').hidden=!add;node('target-fields').hidden=add;node('render-fields').hidden=remove;node('render-fields').disabled=remove;
  node('remove-fields').hidden=!remove;node('reason').required=remove;node('reason').disabled=!remove;
  node('title').required=add;node('title').disabled=!add;node('generate-button').hidden=remove;node('remove').hidden=!remove;
  if(add){const row=state.entries.find(r=>r.identity===node('preset').value);node('title').value=row?.display_name || '';fillRender(row);}
  else {
    const row=state.catalog[node('item').value];
    node('current-poster').hidden=!row;
    if(row){node('current-poster').src='/catalog-preview/'+row.identity;node('target-info').textContent=`${row.identity} / ${row.destination} / SHA-256 ${row.sha256}`+(row.render_request?'':' / No recorded render settings; choose inputs for replacement. Removal does not need them.');if(!remove)fillRender(row);}
    else node('target-info').textContent='Choose an active catalog poster.';
  }
  adaptLogo();adaptStyle();
}
async function action(route,payload){const result=await request('/api/'+route,payload);await refresh();message(route==='stage'?'Staging file and catalog state verified; receipt recorded.':'Request updated.');return result;}
function poster(src,caption){const figure=document.createElement('figure'),image=document.createElement('img');image.width=2000;image.height=3000;image.loading='lazy';image.src=src;image.alt=caption;figure.append(text('figcaption',caption),image);return figure;}
async function refresh(){
  state=await request('/api/state');node('signed-in').textContent='Signed in as fixture '+state.role;
  node('submit-section').hidden=state.role!=='contributor';node('reference-section').hidden=state.role!=='maintainer';node('review-section').hidden=false;
  const selected=node('item').value,preset=node('preset').value;
  node('preset').replaceChildren(new Option('Custom new poster (no mapping needed)',''),...state.entries.filter(r=>state.catalog[r.identity]?.status!=='active').map(r=>new Option(r.display_name,r.identity)));
  node('item').replaceChildren(...Object.values(state.catalog).filter(r=>r.status==='active').map(r=>new Option(r.display_name || r.identity,r.identity)));
  if([...node('item').options].some(o=>o.value===selected))node('item').value=selected;
  if([...node('preset').options].some(o=>o.value===preset))node('preset').value=preset;
  node('style').replaceChildren(...state.styles.map(row=>new Option(row.label,row.id)));
  node('logo').replaceChildren(new Option('Choose a logo',''),...state.logos.map(logo=>new Option(logo,logo)));fields();
  const main=state.submissions.filter(r=>!r.identity.startsWith('fixture.') && r.status==='staged');
  node('summary').textContent=`Main set: ${main.filter(r=>r.action==='CREATE').length} adds, ${main.filter(r=>r.action==='REPLACE').length} in-place replacements verified. All writes stay in staging.`;
  node('catalog').textContent=JSON.stringify(state.catalog,null,2);node('cards').replaceChildren();
  for(const item of state.submissions){
    const card=text('article','','card');Object.assign(card.dataset,{id:item.id,identity:item.identity,status:item.status});
    card.append(text('h3',item.display_name),text('p',`${item.action} / ${item.status}`,'status'));
    if(item.action==='REPLACE'){
      const pair=text('div','','comparison');pair.append(poster('/current/'+item.id,'Current poster (request preimage)'),poster('/preview/'+item.id,'Proposed replacement'));card.append(pair);
    }else card.append(poster('/preview/'+item.id,item.action==='REMOVE'?'Current poster to remove':'Generated preview'));
    card.append(text('p',item.destination),text('p',(item.action==='REMOVE'?'Current file SHA-256 ':'Generated JPEG SHA-256 ')+item.sha256,'hash'));
    if(item.reason){card.append(text('p','Removal reason: '+item.reason),text('p','Active references: '+(item.before.references.join(', ') || 'none')));}
    if(item.reference_sha256)card.append(text('p','Approved reference '+item.reference_sha256+' / '+(item.reference_match?'MATCH':'DIFFERENT BYTES - approval blocked'),'hash'));
    if(item.prior_visual_reference_sha256)card.append(text('p','Changed replacement inputs: prior visual approval is not carried over. Review these exact new bytes. Previous reference '+item.prior_visual_reference_sha256,'hash'));
    if(item.render)card.append(text('p',`${item.render.style}; ${item.render.parameters.base_color}; Pillow ${item.render.pillow}`));
    const detail=document.createElement('details');detail.append(text('summary','Catalog change (before / after)'),text('pre',JSON.stringify(item.catalog_change,null,2)));card.append(detail);
    const checks=text('ul','','checks');for(const check of item.checks){const li=text('li',(check.passed?'PASS: ':'FAIL: ')+check.name);li.dataset.passed=String(check.passed);checks.append(li);}card.append(checks);
    const actions=text('div','','actions');let route,label;
    if(state.role==='contributor' && item.status==='draft'){route='submit';label='Submit generated preview';}
    if(state.role==='maintainer' && item.status==='preview'){route='approve';label=item.action==='REMOVE'?'Approve exact removal':'Approve exact render and change';}
    if(state.role==='maintainer' && item.status==='approved'){route='stage';label='Write to staging and verify';}
    if(route){const button=text('button',label);button.dataset.action=route;button.disabled=route!=='submit' && !item.can_approve;
      button.onclick=async()=>{button.disabled=true;try{await action(route,{id:item.id,sha256:item.sha256,review_digest:item.review_digest});}catch(error){message(error.message);await refresh();}};actions.append(button);}
    if(item.receipt){const p=text('p','Verified file + catalog: '+item.receipt.destination+(item.receipt.file_absent?' (removed)':''));p.dataset.receipt='matched';card.append(p);}card.append(actions);node('cards').append(card);
  }
}
node('login').onsubmit=async e=>{e.preventDefault();try{await request('/api/login',{role:node('role').value,code:node('code').value});node('code').value='';await refresh();message('Fixture role signed in.');}catch(error){message(error.message);}};
for(const id of ['intent','item','preset'])node(id).onchange=fields;
node('style').onchange=()=>{const style=state.styles.find(r=>r.id===node('style').value);node('caption').value=style.default_caption;adaptStyle();};node('logo-source').onchange=adaptLogo;
node('generate').onsubmit=async e=>{
  e.preventDefault();const button=e.submitter;button.disabled=true;
  try{
    if(node('intent').value==='remove'){await action('remove',{identity:node('item').value,reason:node('reason').value});message('Removal submitted for exact catalog entry and current file.');}
    else {
      message('Generating with the production Python renderer...');let upload=null;
      if(node('logo-source').value==='upload'){
        const file=node('upload').files[0];if(!file || file.size>2*1024*1024)throw new Error('Choose a PNG logo up to 2 MiB.');
        upload=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result.split(',')[1]);reader.onerror=reject;reader.readAsDataURL(file);});
      }
      await action('generate',{intent:node('intent').value,title:node('title').value,identity:node('intent').value==='replace'?node('item').value:null,style:node('style').value,logo:node('logo').value,upload,colour:node('colour').value,caption:node('caption').disabled?'':node('caption').value});message('Generated preview ready. Review it, then submit.');
    }
  }catch(error){message(error.message);}finally{button.disabled=false;}
};
for(const active of [true,false])node(active?'attach':'release').onclick=()=>action('reference',{active}).catch(error=>message(error.message));
refresh().catch(()=>{});
