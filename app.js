(() => {
const $ = (s, r = document) => r.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const P = Object.assign({size: 1, contrast: false, speak: true, lang: 'en-IN', role: 'user'}, JSON.parse(localStorage.getItem('cf') || '{}'));
const savePrefs = () => localStorage.setItem('cf', JSON.stringify(P));
const S = {services: [], req: null, draft: {}, ver: -1, seen: 0, timer: null, q: [], sign: null};
const ROLE = {user: 'Visitor', staff: 'Staff'};
const STATUS = {needs_info: 'Information needed', ready_for_review: 'Ready for both to review',
  awaiting_user: 'Waiting for the visitor to confirm', awaiting_staff: 'Waiting for staff to confirm',
  completed: 'Completed', cancelled: 'Cancelled'};
const STEP = {needs_info: 0, ready_for_review: 1, awaiting_user: 2, awaiting_staff: 2, completed: 3, cancelled: -1};
const other = r => r === 'user' ? 'staff' : 'user';

async function api(path, opts = {}) {
  const r = await fetch('/api' + path, {method: opts.method || 'GET', headers: {'Content-Type': 'application/json'},
    body: opts.body ? JSON.stringify(opts.body) : undefined});
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(typeof d.detail === 'string' ? d.detail : 'Something went wrong. Please try again.');
  return d;
}
function toast(t) { const e = $('#toast'); e.textContent = t; e.style.display = 'block'; clearTimeout(toast.t); toast.t = setTimeout(() => e.style.display = 'none', 4500); }
function setHTML(el, html) { if (el && el._h !== html) { el._h = html; el.innerHTML = html; } }
const when = t => new Date(t * 1000).toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'});

/* ---------- preferences ---------- */
function applyPrefs() {
  document.documentElement.style.fontSize = (P.size * 100) + '%';
  document.body.classList.toggle('hc', P.contrast);
  $('#contrast').setAttribute('aria-pressed', P.contrast);
  $('#speak').checked = P.speak; $('#lang').value = P.lang;
  document.querySelectorAll('.role').forEach(b => b.setAttribute('aria-pressed', b.dataset.role === P.role));
  savePrefs();
}
$('#smaller').onclick = () => { P.size = Math.max(.9, +(P.size - .15).toFixed(2)); applyPrefs(); };
$('#larger').onclick = () => { P.size = Math.min(1.6, +(P.size + .15).toFixed(2)); applyPrefs(); };
$('#contrast').onclick = () => { P.contrast = !P.contrast; applyPrefs(); };
$('#speak').onchange = e => { P.speak = e.target.checked; if (!P.speak) speechSynthesis?.cancel(); applyPrefs(); };
$('#lang').onchange = e => { P.lang = e.target.value; applyPrefs(); };
document.querySelectorAll('.role').forEach(b => b.onclick = () => { P.role = b.dataset.role; applyPrefs(); route(); });

/* ---------- speech ---------- */
function mouth(on) { $('#avatar')?.classList.toggle('talking', on); }
function speak(text) {
  if (!P.speak || !('speechSynthesis' in window)) return;
  speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text); u.lang = P.lang; u.rate = .92;
  u.onstart = () => mouth(true); u.onend = u.onerror = () => mouth(false);
  speechSynthesis.speak(u);
}
function say(text) { const b = $('#bubble'); if (b) b.textContent = text; speak(text); }
function listen(target) {
  const R = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!R) return say('Voice typing is not available in this browser. Please type or choose a phrase.');
  const r = new R(); r.lang = P.lang; r.interimResults = false;
  r.onstart = () => $('#mic').setAttribute('aria-pressed', 'true');
  r.onend = () => $('#mic').setAttribute('aria-pressed', 'false');
  r.onresult = e => { target.value = (target.value + ' ' + e.results[0][0].transcript).trim(); };
  r.onerror = () => say('I could not hear you. Please try again or type.');
  r.start();
}

/* ---------- sign support ----------
   Frames are [rightX, rightY, leftX, leftY]. These are simple demonstration poses of common ASL-style
   signs. For production, drop validated ISL/local-language clips at static/signs/<key>.mp4 — they take priority. */
const REST = [150, 178, 50, 178];
const SIGNS = {
  hello: {label: 'Hello', how: 'Flat hand at the forehead, move it outward.', f: [[162, 62, 50, 178], [188, 56, 50, 178], [162, 62, 50, 178], [188, 56, 50, 178]]},
  help: {label: 'I need help', how: 'Closed fist on the open palm of the other hand, lift both together.', f: [[88, 146, 84, 152], [88, 120, 84, 126], [88, 146, 84, 152]]},
  yes: {label: 'Yes', how: 'Closed fist nods up and down.', f: [[140, 112, 50, 178], [140, 128, 50, 178], [140, 112, 50, 178], [140, 128, 50, 178]]},
  no: {label: 'No', how: 'Index and middle finger tap the thumb.', f: [[138, 108, 50, 178], [150, 108, 50, 178], [138, 108, 50, 178], [150, 108, 50, 178]]},
  thanks: {label: 'Thank you', how: 'Flat hand touches the chin, then moves forward.', f: [[112, 86, 50, 178], [158, 108, 50, 178]]},
  pain: {label: 'I am in pain', how: 'Both index fingers point at each other and twist.', f: [[88, 128, 112, 128], [98, 128, 102, 128], [88, 128, 112, 128], [98, 128, 102, 128]]},
  write: {label: 'Please write it down', how: 'Mime writing on the palm of the other hand.', f: [[100, 152, 62, 152], [118, 158, 62, 152], [100, 152, 62, 152], [118, 158, 62, 152]]},
};
let pose = REST.slice(), signRun = 0;
function draw() {
  const a = $('#avatar'); if (!a) return;
  [['#ra', 0], ['#la', 2]].forEach(([id, i]) => { const l = $(id, a); l.setAttribute('x2', pose[i]); l.setAttribute('y2', pose[i + 1]); });
  $('#rh', a).setAttribute('cx', pose[0]); $('#rh', a).setAttribute('cy', pose[1]);
  $('#lh', a).setAttribute('cx', pose[2]); $('#lh', a).setAttribute('cy', pose[3]);
}
const tween = (to, dur = 480) => new Promise(res => {
  const from = pose.slice(), t0 = performance.now();
  (function step(t) {
    const k = Math.min(1, (t - t0) / dur), e = k < .5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2;
    pose = from.map((v, i) => v + (to[i] - v) * e); draw(); k < 1 ? requestAnimationFrame(step) : res();
  })(t0);
});
async function playSign(key) {
  const s = SIGNS[key]; if (!s) return;
  const run = ++signRun;
  setHTML($('#signcap'), `<strong>${esc(s.label)}</strong>: ${esc(s.how)}`);
  const v = $('#signvideo'), svg = $('#avatar');
  if (v) { v.onerror = () => { v.style.display = 'none'; svg.style.display = ''; }; v.oncanplay = () => { svg.style.display = 'none'; v.style.display = 'block'; };
    v.onended = () => { v.style.display = 'none'; svg.style.display = ''; }; v.src = `/static/signs/${key}.mp4`; v.play().catch(() => {}); }
  if (matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  for (const f of s.f) { if (run !== signRun) return; await tween(f); }
  if (run === signRun) await tween(REST);
}

/* ---------- router / home ---------- */
const main = $('#main');
function route() {
  clearInterval(S.timer); S.req = null; S.ver = -1; S.seen = 0; S.q = []; S.sign = null;
  const m = location.hash.match(/^#\/r\/(\d+)/);
  m ? openReq(+m[1]) : home();
}
window.addEventListener('hashchange', route);

async function home() {
  S.services = S.services.length ? S.services : await api('/services');
  const staff = P.role === 'staff';
  main.innerHTML = `<h1>${staff ? 'Staff desk' : 'Welcome. Where are you today?'}</h1>
    <p>${staff ? 'Start a request with a visitor, or open one from the queue.' : 'Choose a counter. A guide will help you explain what you need.'}</p>
    <div class="cards">${S.services.map(s => `<button class="card" data-s="${s.key}"><strong>${esc(s.name)}</strong>Start a new request</button>`).join('')}</div>
    <form class="panel row" id="open"><label for="rid">Already have a request number?</label><input id="rid" inputmode="numeric" size="6" required><button class="btn">Open request</button></form>
    ${staff ? '<h2 style="margin-top:1.5rem">Queue</h2><div class="panel" id="queue"></div>' : ''}`;
  main.querySelectorAll('.card').forEach(b => b.onclick = async () => { const r = await api('/requests', {method: 'POST', body: {service: b.dataset.s}}); location.hash = '#/r/' + r.id; });
  $('#open').onsubmit = e => { e.preventDefault(); location.hash = '#/r/' + $('#rid').value; };
  if (staff) { const load = async () => { const q = await api('/requests'); setHTML($('#queue'), q.length ? `<table><tr><th>No.</th><th>Counter</th><th>Who</th><th>Need</th><th>Status</th><th></th></tr>${q.map(r => `<tr><td>#${r.id}</td><td>${esc(r.service_name)}</td><td>${esc(r.who) || '—'}</td><td>${esc(r.purpose) || '—'}</td><td>${STATUS[r.status]} (v${r.version})</td><td><a class="btn sm" href="#/r/${r.id}">Open</a></td></tr>`).join('')}</table>` : '<p>No requests yet.</p>'); }; load(); S.timer = setInterval(load, 3000); }
}

/* ---------- request view ---------- */
const svcOf = () => S.services.find(s => s.key === S.req.service);
const isReq = f => f.required || Object.entries(f.required_if || {}).some(([k, v]) => v.includes(S.draft[k]));
const saved = () => S.req.current?.fields || {};
const dirtyKeys = () => svcOf().fields.map(f => f.key).filter(k => (S.draft[k] || '') !== (saved()[k] || ''));

async function openReq(id) {
  try {
    S.services = S.services.length ? S.services : await api('/services');
    S.req = await api('/requests/' + id);
  } catch (e) { main.innerHTML = `<div class="panel"><h1>Request not found</h1><p>${esc(e.message)}</p><a class="btn" href="#/">Back to start</a></div>`; return; }
  buildLayout();
  S.seen = S.req.messages.length;
  render(true);
  S.timer = setInterval(poll, 2500);
  say(S.req.current ? `Request ${id}. You can read it, change it, or confirm it.` : `Hello. I am Flo. Tell me what you need, or choose a phrase. I will only fill in what you say clearly.`);
}
async function poll() {
  try { const r = await api('/requests/' + S.req.id); const fresh = r.messages.slice(S.seen).filter(m => m.sender !== P.role);
    S.req = r; fresh.forEach(m => { say(`${ROLE[m.sender]}: ${m.text}`); if (m.sign) playSign(m.sign); });
    S.seen = r.messages.length; render(false); } catch (e) { /* offline: keep last state */ }
}

function buildLayout() {
  const svc = svcOf();
  main.innerHTML = `<div class="grid">
  <div class="stack">
    <section class="panel" aria-label="Guide">
      <div class="signstage"><svg id="avatar" class="avatar" viewBox="0 0 200 230" role="img" aria-label="Flo, the virtual guide">
        <path class="cloth" d="M52 230c0-60 18-96 48-96s48 36 48 96z"/><line class="sleeve" id="ra" x1="130" y1="140" x2="150" y2="178"/><line class="sleeve" id="la" x1="70" y1="140" x2="50" y2="178"/>
        <circle class="skin" cx="100" cy="72" r="34"/><path class="hair" d="M64 72c0-30 16-42 36-42s36 12 36 42c-8-16-20-22-36-22s-28 6-36 22z"/>
        <circle cx="88" cy="74" r="4" fill="#222"/><circle cx="112" cy="74" r="4" fill="#222"/><ellipse class="mouth" cx="100" cy="92" rx="9" ry="6"/>
        <circle class="skin" id="rh" cx="150" cy="178" r="11"/><circle class="skin" id="lh" cx="50" cy="178" r="11"/></svg>
        <video id="signvideo" muted playsinline aria-label="Sign language video"></video></div>
      <div id="bubble" class="bubble" aria-live="polite"></div>
      <div class="row"><button class="btn sm ghost" id="replay">Hear again</button></div>
      <div id="qs" aria-live="polite"></div>
    </section>
    <section class="panel"><h2>Tell us what you need</h2>
      <label for="say" class="cap">Type, or press the microphone.</label>
      <textarea id="say" rows="3"></textarea>
      <div class="row"><button class="btn" id="go">Check my request</button><button class="btn ghost" id="mic" aria-pressed="false">🎤 Speak</button></div>
      <h3 style="margin-top:1rem">Quick phrases</h3><div class="chips">${svc.phrases.map(p => `<button class="chip" data-p="${esc(p)}">${esc(p)}</button>`).join('')}</div>
    </section>
    <section class="panel"><h2>Signs</h2><p class="cap">Choose a sign to preview it, then send it.</p>
      <div class="chips">${Object.entries(SIGNS).map(([k, s]) => `<button class="chip" data-sign="${k}">${s.label}</button>`).join('')}</div>
      <p id="signcap" class="cap" aria-live="polite"></p><div id="signsend"></div></section>
  </div>
  <section class="panel" id="reqpanel" aria-label="Request"></section>
  <div class="stack"><section class="panel"><h2>Conversation</h2><div class="chat" id="chat" aria-live="polite"></div>
    <form class="row" id="chatform"><input id="chattext" aria-label="Message" placeholder="Write a message" style="flex:1;min-width:0"><button class="btn sm">Send</button></form></section>
    <section class="panel" id="history"></section></div></div>`;
  $('#replay').onclick = () => speak($('#bubble').textContent);
  $('#go').onclick = understand; $('#mic').onclick = () => listen($('#say'));
  main.querySelectorAll('[data-p]').forEach(b => b.onclick = () => { $('#say').value = b.dataset.p; understand(); });
  main.querySelectorAll('[data-sign]').forEach(b => b.onclick = () => { S.sign = b.dataset.sign; playSign(S.sign);
    $('#signsend').innerHTML = `<button class="btn sm" id="sendsign">Send “${SIGNS[S.sign].label}” to ${ROLE[other(P.role)].toLowerCase()}</button>`;
    $('#sendsign').onclick = () => sendMsg(SIGNS[S.sign].label, S.sign); });
  $('#chatform').onsubmit = e => { e.preventDefault(); const t = $('#chattext').value.trim(); if (t) { sendMsg(t, ''); $('#chattext').value = ''; } };
  $('#reqpanel').addEventListener('input', onInput);
  $('#reqpanel').addEventListener('click', onClick);
  $('#qs').addEventListener('click', e => { const b = e.target.closest('[data-qk]'); if (!b) return; S.draft[b.dataset.qk] = b.dataset.qv; S.q = S.q.filter(q => q.key !== b.dataset.qk); renderForm(); renderQs(); renderBars(); });
}

function render(force) {
  const c = S.req.current;
  if (force || (c ? c.version_no : 0) !== S.ver) { if (S.ver !== -1 && S.ver !== (c?.version_no ?? 0)) toast('The request was updated. You are now seeing the latest version.'); S.ver = c ? c.version_no : 0; S.draft = {...saved()}; renderForm(); }
  renderBars(); renderChat(); renderHistory();
}

function renderForm() {
  const svc = svcOf();
  $('#reqpanel').innerHTML = `<div class="head"><h1>${esc(svc.name)}</h1><span><span class="badge" id="vbadge"></span> <span class="cap">Request #${S.req.id}</span></span></div>
  <div id="meta"></div><div id="fields">${svc.fields.map(f => {
    const id = 'f_' + f.key, v = S.draft[f.key] || '';
    const inp = f.type === 'select' ? `<select id="${id}" data-k="${f.key}"><option value="">Choose…</option>${f.options.map(o => `<option ${o.v === v ? 'selected' : ''}>${esc(o.v)}</option>`).join('')}</select>`
      : f.type === 'textarea' ? `<textarea id="${id}" data-k="${f.key}" rows="3">${esc(v)}</textarea>` : `<input id="${id}" data-k="${f.key}" value="${esc(v)}">`;
    return `<div class="field" data-f="${f.key}"><label for="${id}">${esc(f.label)} <span class="req"></span></label>${inp}<p class="ask"></p></div>`;
  }).join('')}</div><div class="bar" id="bar"></div>`;
  refreshFields();
}
function refreshFields() {
  const svc = svcOf(), s = saved(), locked = ['completed', 'cancelled'].includes(S.req.status);
  svc.fields.forEach(f => {
    const el = $(`[data-f="${f.key}"]`); if (!el) return;
    const need = isReq(f) && !(S.draft[f.key] || '').trim();
    el.classList.toggle('needs', need); el.classList.toggle('changed', (S.draft[f.key] || '') !== (s[f.key] || '') && !!S.req.current);
    $('.req', el).textContent = isReq(f) ? '(required)' : '(optional)';
    $('.ask', el).textContent = need ? 'Needed: ' + f.ask : '';
    el.querySelector('[data-k]').disabled = locked;
  });
}
function onInput(e) { const k = e.target.dataset.k; if (!k) return; S.draft[k] = e.target.value; refreshFields(); renderBars(); }

function renderBars() {
  const r = S.req, c = r.current, cur = c ? c.version_no : 0, dirty = dirtyKeys(), svc = svcOf();
  const miss = svc.fields.filter(f => isReq(f) && !(S.draft[f.key] || '').trim());
  const badge = $('#vbadge'); if (badge) { badge.textContent = c ? 'Version ' + cur : 'Not saved yet'; badge.className = 'badge' + (c ? ' v' : ''); }
  const step = STEP[r.status];
  setHTML($('#meta'), `<p class="status" role="status">${STATUS[r.status]}</p>` + (step >= 0 ? `<ol class="tracker">${['Details', 'Review', 'Both confirm', 'Done'].map((t, i) => `<li class="${i <= step ? 'on' : ''}" ${i === step ? 'aria-current="step"' : ''}>${t}</li>`).join('')}</ol>` : ''));
  const locked = ['completed', 'cancelled'].includes(r.status);
  const done = new Set(r.confirmed_current), me = P.role;
  let h = '';
  if (r.status === 'completed') h = `<div class="done">Completed. The visitor and staff both confirmed version ${cur}.</div>`;
  else if (r.status === 'cancelled') h = '<div class="done">This request was cancelled.</div>';
  else {
    if (dirty.length) h += `<div><p><strong>You changed ${dirty.length} item${dirty.length > 1 ? 's' : ''}.</strong> ${c ? 'Saving makes a new version. The original stays on record, and any confirmations start again.' : 'This will be saved as the original request.'}</p>
      <label class="cap" for="note">Why? (optional)</label><input id="note" style="width:100%"><div class="row" style="margin-top:.5rem"><button class="btn ${me === 'staff' ? 'staff' : ''}" data-act="save">${c ? 'Save as version ' + (cur + 1) : 'Save request (original)'}</button>${c ? '<button class="btn ghost" data-act="discard">Discard changes</button>' : ''}</div></div>`;
    if (c) h += `<div><p>Version ${cur}: ${['user', 'staff'].map(x => done.has(x) ? `<span class="ok">✓ ${ROLE[x]} confirmed</span>` : `${ROLE[x]}: not yet`).join(' · ')}</p>
      <div class="row"><button class="btn ${me === 'staff' ? 'staff' : ''}" data-act="confirm" ${dirty.length || miss.length || done.has(me) ? 'disabled' : ''}>${done.has(me) ? 'You confirmed this version' : `Confirm version ${cur} as ${ROLE[me].toLowerCase()}`}</button></div>
      <p class="cap">${miss.length ? 'Fill in the required items first.' : dirty.length ? 'Save your changes before confirming.' : 'The request is complete only when both sides confirm the same version.'}</p></div>`;
    if (c) h += '<div><button class="btn sm ghost" data-act="cancel">Cancel request</button></div>';
  }
  setHTML($('#bar'), h); refreshFields();
}

async function onClick(e) {
  const a = e.target.closest('[data-act]')?.dataset.act; if (!a) return; const id = S.req.id;
  try {
    if (a === 'save') { S.req = await api(`/requests/${id}/versions`, {method: 'POST', body: {fields: S.draft, author: P.role, base_version: S.req.current?.version_no ?? 0, note: $('#note')?.value || ''}}); render(true); say(`Saved as version ${S.req.current.version_no}.`); }
    if (a === 'discard') { S.draft = {...saved()}; renderForm(); renderBars(); }
    if (a === 'confirm') { S.req = await api(`/requests/${id}/confirm`, {method: 'POST', body: {role: P.role, version_no: S.req.current.version_no}}); render(false); say(S.req.status === 'completed' ? 'Both of you confirmed. The request is complete.' : 'You confirmed. Now we wait for the other person.'); }
    if (a === 'cancel' && confirm('Cancel this request?')) { S.req = await api(`/requests/${id}/cancel`, {method: 'POST'}); render(false); }
  } catch (err) { say(err.message); toast(err.message); }
}

async function understand() {
  const t = $('#say').value.trim();
  if (!t) return say('Please write or say what you need, or choose a phrase.');
  try {
    const a = await api('/analyze', {method: 'POST', body: {service: S.req.service, text: t, fields: S.draft}});
    Object.assign(S.draft, a.extracted); S.q = a.questions; renderForm(); renderQs(); renderBars();
    const n = Object.keys(a.extracted).length, m = a.questions.length;
    say(`${n ? `I filled in ${n} item${n > 1 ? 's' : ''} from what you said. Please check them.` : 'I did not fill anything in yet.'} ${m ? `I need ${m} answer${m > 1 ? 's' : ''}. ${a.questions[0].text}` : 'Nothing else is missing. Press Save when it looks right.'}`);
  } catch (err) { say(err.message); }
}
function renderQs() {
  setHTML($('#qs'), S.q.map(q => `<div class="q"><strong>${esc(q.text)}</strong>${q.options?.length ? `<div class="chips">${q.options.map(o => `<button class="chip" data-qk="${q.key}" data-qv="${esc(o)}">${esc(o)}</button>`).join('')}</div>` : `<div><a href="#f_${q.key}" class="cap" onclick="document.getElementById('f_${q.key}').focus()">Answer in the form</a></div>`}</div>`).join(''));
}
async function sendMsg(text, sign) { try { S.req = await api(`/requests/${S.req.id}/messages`, {method: 'POST', body: {sender: P.role, text, sign}}); S.seen = S.req.messages.length; renderChat(); } catch (e) { toast(e.message); } }
function renderChat() {
  const el = $('#chat'), atEnd = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
  setHTML(el, S.req.messages.map(m => `<div class="msg ${m.sender}"><small>${ROLE[m.sender]} · ${when(m.created)}${m.sign ? ' · sign' : ''}</small>${esc(m.text)}</div>`).join('') || '<p class="cap">No messages yet. Ask a question, or send a sign.</p>');
  if (atEnd) el.scrollTop = el.scrollHeight;
}
function renderHistory() {
  const r = S.req, svc = svcOf(), lab = k => svc.fields.find(f => f.key === k)?.label || k;
  const orig = r.original, cur = r.current;
  let h = '<h2>Version history</h2>';
  if (!cur) return setHTML($('#history'), h + '<p class="cap">Nothing saved yet.</p>');
  if (r.versions.length > 1) {
    const ch = svc.fields.map(f => f.key).filter(k => (orig.fields[k] || '') !== (cur.fields[k] || ''));
    h += `<p><strong>Original vs. current</strong></p>${ch.length ? ch.map(k => `<p>${esc(lab(k))}: <del>${esc(orig.fields[k] || 'empty')}</del> <ins>${esc(cur.fields[k] || 'empty')}</ins></p>`).join('') : '<p class="cap">Back to the original details.</p>'}`;
  }
  h += [...r.versions].reverse().map(v => {
    const who = r.confirmations.filter(c => c.version_no === v.version_no).map(c => ROLE[c.role] + ' confirmed').join(', ');
    return `<div class="ver ${v === cur ? 'cur' : ''}"><strong>Version ${v.version_no}${v.version_no === 1 ? ' · original' : ''}</strong> <span class="cap">by ${ROLE[v.author]}, ${when(v.created)}</span>${v.note ? `<div class="cap">“${esc(v.note)}”</div>` : ''}
      ${v.version_no > 1 ? v.changes.map(c => `<div>${esc(lab(c.key))}: <del>${esc(c.old || 'empty')}</del> → <ins>${esc(c.new || 'empty')}</ins></div>`).join('') : '<div class="cap">First saved details.</div>'}${who ? `<div class="ok">${esc(who)}</div>` : ''}</div>`;
  }).join('');
  setHTML($('#history'), h);
}

applyPrefs(); route();
})();
