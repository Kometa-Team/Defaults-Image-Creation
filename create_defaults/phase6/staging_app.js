let state = null;
const node = id => document.getElementById(id);
async function request(path, payload) {
  const options = payload === undefined ? {} : {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': state?.csrf || ''}, body: JSON.stringify(payload)};
  const response = await fetch(path, options);
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'Request failed');
  return result;
}
function message(text) { node('message').textContent = text; }
function text(tag, value, className) { const element = document.createElement(tag); element.textContent = value; if (className) element.className = className; return element; }
async function refresh() {
  state = await request('/api/state');
  node('signed-in').textContent = `Signed in as fixture ${state.role}`;
  node('submit-section').hidden = state.role !== 'contributor';
  node('review-section').hidden = false;
  const selection = node('item').value;
  node('item').replaceChildren(...state.entries.map(entry => { const option = new Option(`${entry.action} — ${entry.display_name}`, entry.identity); return option; }));
  if (selection) node('item').value = selection;
  node('summary').textContent = `${state.submissions.filter(item => item.status === 'staged').length} / 10 verified at the staging destination`;
  node('cards').replaceChildren();
  for (const item of state.submissions) {
    const card = text('article', '', 'card'); card.dataset.id = item.id; card.dataset.identity = item.identity; card.dataset.status = item.status;
    card.append(text('h3', item.display_name), text('p', `${item.action} · ${item.status}`, 'status'));
    const image = document.createElement('img'); image.width = 2000; image.height = 3000; image.loading = 'lazy'; image.src = '/preview/' + item.id; image.alt = item.display_name; card.append(image);
    card.append(text('p', item.destination), text('p', 'SHA-256 ' + item.sha256, 'hash'));
    const actions = text('div', '', 'actions');
    if (state.role === 'maintainer' && ['preview', 'approved'].includes(item.status)) {
      const action = item.status === 'preview' ? 'approve' : 'stage';
      const button = text('button', action === 'approve' ? 'Approve this exact render' : 'Write to staging and verify'); button.dataset.action = action;
      button.onclick = async () => { button.disabled = true; try { await request('/api/' + action, {id: item.id, sha256: item.sha256}); await refresh(); message(action === 'approve' ? 'Exact render approved for staging.' : 'Staging destination SHA-256 matches the approved render.'); } catch (error) { message(error.message); button.disabled = false; } };
      actions.append(button);
    }
    if (item.receipt) { const link = text('p', 'Verified destination: ' + item.receipt.destination); link.dataset.receipt = 'matched'; card.append(link); }
    card.append(actions); node('cards').append(card);
  }
}
node('login').onsubmit = async event => { event.preventDefault(); try { await request('/api/login', {role: node('role').value, code: node('code').value}); node('code').value = ''; await refresh(); message('Fixture role signed in.'); } catch (error) { message(error.message); } };
node('submit').onsubmit = async event => {
  event.preventDefault(); const button = event.submitter; button.disabled = true;
  try {
    const file = node('poster').files[0]; if (!file || file.size > 2 * 1024 * 1024) throw new Error('Choose a pilot JPEG under 2 MiB.');
    const jpeg = await new Promise((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(reader.result.split(',')[1]); reader.onerror = reject; reader.readAsDataURL(file); });
    await request('/api/submit', {identity: node('item').value, jpeg}); await refresh(); message('Poster submitted. A maintainer can review this exact preview.');
  } catch (error) { message(error.message); } finally { button.disabled = false; }
};
refresh().catch(() => {});
