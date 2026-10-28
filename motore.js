#!/usr/bin/env node
/*
 MULTICHANNEL - video KAO tutto su GitHub (render_engine = github_completo, github_workflow = video_kao.yml)

 Fa quello che facevano il PRODUCTION e il Publisher di n8n, con GLI STESSI prompt e la stessa logica:
 il codice dei nodi n8n e' copiato tale e quale in kao/produzione.json ed eseguito qui, nodo per nodo,
 nello stesso ordine del workflow (solo il ramo usato da KAO: clip 100% Pexels, montaggio render_kao.py,
 copertina copertine_cinema_kao.py).

   1) testo del competitor (RapidAPI)            6) voce ElevenLabs scena per scena
   2) leve psicologiche (Bias Analyzer)           7) scene tipografiche di riserva (Pexels a vuoto)
   3) copione a blocchi con Claude                8) montaggio: render_kao.py (come prima)
   4) tag del video originale + testo copertina   9) copertina: copertine_cinema_kao.py (come prima, in parallelo)
   5) SEO (descrizione, tag, commento)           10) caricamento YouTube, copertina, primo commento, playlist
 Alla fine avvisa n8n (webhook github-fatto) e il workflow "GitHub Video" aggiorna il foglio e salva su Drive.

 Ingresso: variabile PAYLOAD (riga del canale in Channel Configs + link + riga del file di produzione), preparata da n8n.
 Chiavi: ANTHROPIC_API_KEY, ELEVENLABS_API_KEY, PEXELS_API_KEY, RAPIDAPI_KEY, FAL_KEY, YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN
         (facoltativa OPENAI_API_KEY: i 3 passaggi che in n8n usavano GPT-4.1 lo usano anche qui; senza, li fa Claude).
*/
'use strict';
const fs = require('fs'), path = require('path'), http = require('http'), { spawn } = require('child_process');
const { DateTime, Settings } = require('luxon');
Settings.defaultZone = 'Europe/Rome';

const E = (k, d = '') => process.env[k] || d;
const ROOT = path.resolve(__dirname, '..');
const LAVORO = path.join(ROOT, 'lavoro_kao_completo');
fs.mkdirSync(LAVORO, { recursive: true });
const WF = JSON.parse(fs.readFileSync(path.join(__dirname, 'produzione.json'), 'utf8')).nodi;
const P = JSON.parse(E('PAYLOAD', '{}') || '{}');
const PROVA = String(P.prova || E('PROVA', 'NO')).trim().toUpperCase() === 'SI';
const T0 = Date.now();
const RUN_ID = E('GITHUB_RUN_ID', String(Date.now()));
const log = (...a) => console.log('[kao]', ...a);
const sleep = (ms) => new Promise(r => setTimeout(r, ms));
const MODELLO_CLAUDE_GPT = E('MODELLO_AL_POSTO_DI_GPT', 'claude-sonnet-4-6');   // usato solo se manca OPENAI_API_KEY

// ======================================================================= stato "n8n"
const OUT = {};            // nome nodo -> items dell'ultima esecuzione (come $('Nodo') in n8n)
const ESEGUITI = new Set();
const SD = {};             // $getWorkflowStaticData('global')
const metti = (nome, items) => { OUT[nome] = items; ESEGUITI.add(nome); return items; };
const J = (o) => ({ json: o });

function rif(nome, ctx) {
  const arr = () => OUT[nome] || [];
  return {
    first: () => { const a = arr(); if (!a.length) throw new Error(`Il nodo '${nome}' non ha dati`); return a[0]; },
    last: () => { const a = arr(); return a[a.length - 1]; },
    all: () => arr(),
    get item() { const a = arr(); const i = ctx && ctx.pair != null ? ctx.pair : (ctx ? ctx.itemIndex : 0); return a[i] || a[0] || { json: {} }; },
    get isExecuted() { return ESEGUITI.has(nome); },
    get json() { return (arr()[0] || { json: {} }).json; },
  };
}
function contesto(ctx) {
  const $ = (n) => rif(n, ctx);
  const items = ctx.items || [];
  const $input = { all: () => items, first: () => items[0], last: () => items[items.length - 1], item: ctx.item || items[ctx.itemIndex || 0] };
  const $node = new Proxy({}, { get: (_, n) => ({ json: (OUT[n] && OUT[n][0] ? OUT[n][0].json : {}) }) });
  return {
    $, $input, $json: (ctx.item || items[ctx.itemIndex || 0] || { json: {} }).json, $itemIndex: ctx.itemIndex || 0,
    $execution: { id: RUN_ID, resumeUrl: '', mode: 'production' }, $getWorkflowStaticData: () => SD,
    $now: DateTime.now(), $today: DateTime.now().startOf('day'), DateTime, $node, $items: (n) => (OUT[n] || []),
    console, $vars: {}, $workflow: { id: 'github', name: 'video_kao' },
  };
}
// ---------------- espressioni n8n "={{ ... }}"
function valuta(v, ctx) {
  if (typeof v !== 'string' || !v.startsWith('=')) return v;
  const s = v.slice(1);
  const pezzi = []; let i = 0;
  while (i < s.length) {
    const a = s.indexOf('{{', i);
    if (a < 0) { pezzi.push({ t: s.slice(i) }); break; }
    if (a > i) pezzi.push({ t: s.slice(i, a) });
    const b = s.indexOf('}}', a + 2);
    if (b < 0) { pezzi.push({ t: s.slice(a) }); break; }
    pezzi.push({ e: s.slice(a + 2, b) }); i = b + 2;
  }
  const c = contesto(ctx), nomi = Object.keys(c), valori = nomi.map(k => c[k]);
  const calcola = (e) => { try { return new Function(...nomi, 'return (' + e + '\n);')(...valori); }
    catch (err) { throw new Error('Espressione n8n non valutata (' + err.message + '): ' + e.slice(0, 200)); } };
  if (pezzi.length === 1 && pezzi[0].e !== undefined) return calcola(pezzi[0].e);
  return pezzi.map(p => { if (p.t !== undefined) return p.t; const r = calcola(p.e);
    return r === null || r === undefined ? '' : (typeof r === 'object' ? JSON.stringify(r) : String(r)); }).join('');
}
// ---------------- nodo Code (stesso codice di n8n)
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
function normalizza(r) {
  if (r === undefined || r === null) return [];
  const uno = (x) => (x && typeof x === 'object' && x.json && typeof x.json === 'object') ? x : J(x);
  return Array.isArray(r) ? r.map(uno) : [uno(r)];
}
async function codice(nome, items, opz = {}) {
  const nodo = WF[nome]; if (!nodo) throw new Error('nodo mancante in produzione.json: ' + nome);
  const src = nodo.params.jsCode, perItem = nodo.params.mode === 'runOnceForEachItem';
  const helpers = { getBinaryDataBuffer: async (i, k) => Buffer.from((items[i].binary[k] || {}).data || '', 'base64') };
  let out = [];
  const esegui = async (ctx) => {
    const c = contesto(ctx), nomi = Object.keys(c);
    const f = new AsyncFunction(...nomi, src);
    return normalizza(await f.apply({ helpers }, nomi.map(k => c[k])));
  };
  if (perItem) {
    for (let i = 0; i < items.length; i++) out = out.concat(await esegui({ items, item: items[i], itemIndex: i, pair: opz.pair ? opz.pair(i) : i }));
  } else out = await esegui({ items, itemIndex: 0 });
  return metti(nome, out);
}
// ---------------- nodo Set (Edit Fields)
function setNodo(nome, items, opz = {}) {
  const p = WF[nome].params, ass = (p.assignments && p.assignments.assignments) || [];
  const out = items.map((it, i) => {
    const ctx = { items, item: it, itemIndex: i, pair: opz.pair ? opz.pair(i) : i };
    const o = p.includeOtherFields ? { ...it.json } : {};
    for (const a of ass) {
      let v = valuta(a.value, ctx);
      if (a.type === 'string') v = v === null || v === undefined ? '' : (typeof v === 'object' ? JSON.stringify(v) : String(v));
      else if (a.type === 'number') v = Number(v);
      else if (a.type === 'boolean') v = v === true || v === 'true';
      o[String(a.name).replace(/^=/, '')] = v;
    }
    return J(o);
  });
  return metti(nome, out);
}

// ======================================================================= rete
async function richiesta(url, { metodo = 'GET', corpo, headers = {}, tipo = 'json', timeout = 300000, tentativi = 4 } = {}) {
  let ultimo;
  for (let k = 0; k < tentativi; k++) {
    try {
      const h = { ...headers }; let b = corpo;
      if (corpo && typeof corpo === 'object' && !Buffer.isBuffer(corpo)) { b = JSON.stringify(corpo); h['Content-Type'] = h['Content-Type'] || 'application/json'; }
      const r = await fetch(url, { method: metodo, headers: h, body: b, signal: AbortSignal.timeout(timeout) });
      if (r.status === 429 || r.status >= 500) { ultimo = new Error('HTTP ' + r.status + ' ' + (await r.text()).slice(0, 200)); await sleep((r.status === 429 ? 60000 : 8000) * (k + 1)); continue; }
      if (!r.ok) throw Object.assign(new Error('HTTP ' + r.status + ' ' + url.split('?')[0] + ': ' + (await r.text()).slice(0, 300)), { stop: true });
      if (tipo === 'buffer') return Buffer.from(await r.arrayBuffer());
      if (tipo === 'risposta') return r;
      const t = await r.text(); return t ? JSON.parse(t) : {};
    } catch (e) { ultimo = e; if (e.stop) throw e; await sleep(5000 * (k + 1)); }
  }
  throw ultimo;
}
async function claude(body) {
  return richiesta('https://api.anthropic.com/v1/messages', { metodo: 'POST', corpo: body, timeout: 600000,
    headers: { 'x-api-key': E('ANTHROPIC_API_KEY'), 'anthropic-version': '2023-06-01' } });
}
const testoClaude = (r) => (r.content || []).filter(x => x.type === 'text').map(x => x.text).join('\n').trim();
// chiamata in formato OpenAI (come in n8n). Senza OPENAI_API_KEY la fa Claude e rimette la risposta nello stesso formato.
async function openaiChat(payload) {
  if (E('OPENAI_API_KEY')) return richiesta('https://api.openai.com/v1/chat/completions', { metodo: 'POST', corpo: payload,
    headers: { Authorization: 'Bearer ' + E('OPENAI_API_KEY') } });
  const sys = payload.messages.filter(m => m.role === 'system').map(m => m.content).join('\n\n');
  const msgs = payload.messages.filter(m => m.role !== 'system').map(m => ({ role: m.role,
    content: typeof m.content === 'string' ? m.content : m.content.map(c => c.type === 'image_url'
      ? { type: 'image', source: { type: 'url', url: c.image_url.url } } : { type: 'text', text: c.text }) }));
  const r = await claude({ model: MODELLO_CLAUDE_GPT, max_tokens: Math.max(1500, payload.max_tokens || 4000), system: sys || undefined, messages: msgs });
  return { choices: [{ message: { role: 'assistant', content: testoClaude(r) } }] };
}
// nodo "AI Agent" di n8n con modello GPT-4.1 (Bias Analyzer, SEO Generator)
async function agente(nome, schemaEsempio) {
  const p = WF[nome].params, ctx = { items: [J({})], itemIndex: 0 };
  const sistema = valuta(p.options.systemMessage || '', ctx);
  let utente = valuta(p.text, ctx);
  if (schemaEsempio) utente += '\n\nYou must format your output as a JSON value that adheres to this example (same keys, same types). ' +
    'Return ONLY the JSON, no markdown:\n' + schemaEsempio;
  for (let k = 0; k < 3; k++) {
    const r = await openaiChat({ model: 'gpt-4.1', messages: [{ role: 'system', content: sistema }, { role: 'user', content: utente }], max_tokens: 6000 });
    const testo = String(r.choices[0].message.content || '').trim();
    if (!schemaEsempio) return metti(nome, [J({ output: testo })]);
    const pulito = testo.replace(/^```json\s*/i, '').replace(/^```\s*/, '').replace(/```\s*$/, '');
    const m = pulito.match(/\{[\s\S]*\}/);
    try { return metti(nome, [J({ output: JSON.parse(m ? m[0] : pulito) })]); }
    catch (e) { log(nome + ': JSON non valido, riprovo'); utente += '\n\nIMPORTANT: the previous answer was not valid JSON. Return ONLY valid JSON.'; }
  }
  throw new Error(nome + ': nessun JSON valido dopo 3 tentativi');
}

// ======================================================================= mini server locale (audio per il montaggio + risposte dei programmi Python)
const RISPOSTE = {};
const SERVER_DIR = path.join(LAVORO, 'file'); fs.mkdirSync(SERVER_DIR, { recursive: true });
let PORTA = 0;
const server = http.createServer((req, res) => {
  if (req.method === 'POST' && req.url.startsWith('/risposta/')) {
    let b = ''; req.on('data', d => b += d); req.on('end', () => {
      try { RISPOSTE[req.url.slice(10)] = JSON.parse(b || '{}'); } catch (e) { RISPOSTE[req.url.slice(10)] = { errore: b }; }
      res.writeHead(200, { 'Content-Type': 'application/json' }); res.end('{"ok":true}'); });
    return;
  }
  const f = path.join(SERVER_DIR, path.basename(decodeURIComponent(req.url.replace(/^\/file\//, '').split('?')[0])));
  if (req.url.startsWith('/file/') && fs.existsSync(f)) { res.writeHead(200, { 'Content-Type': 'audio/mpeg' }); fs.createReadStream(f).pipe(res); return; }
  res.writeHead(404); res.end();
});
const avviaServer = () => new Promise(r => server.listen(0, '127.0.0.1', () => { PORTA = server.address().port; r(); }));
const urlLocale = (n) => `http://127.0.0.1:${PORTA}/file/${n}`;
const PREFISSO_AUDIO = 'GHKAO_';   // id finto "Drive" degli audio: dopo diventa un link del server locale

function python(script, env, nomeRisposta) {
  return new Promise((ok) => {
    const p = spawn('python3', [script], { cwd: ROOT, env: { ...process.env, ...env }, stdio: 'inherit' });
    p.on('close', (code) => ok({ code, risposta: nomeRisposta ? RISPOSTE[nomeRisposta] : null }));
  });
}

// ======================================================================= YouTube
let _token = null;
async function tokenYT() {
  if (_token && _token.scade > Date.now()) return _token.v;
  const r = await richiesta('https://oauth2.googleapis.com/token', { metodo: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    corpo: new URLSearchParams({ client_id: E('YT_CLIENT_ID'), client_secret: E('YT_CLIENT_SECRET'), refresh_token: E('YT_REFRESH_TOKEN'), grant_type: 'refresh_token' }).toString() });
  _token = { v: r.access_token, scade: Date.now() + 50 * 60000 }; return r.access_token;
}
const yt = async (url, opz = {}) => richiesta(url, { ...opz, headers: { ...(opz.headers || {}), Authorization: 'Bearer ' + await tokenYT() } });

// ======================================================================= risposta a n8n
async function avvisa(esito) {
  esito.minuti_lavoro = Math.round((Date.now() - T0) / 6000) / 10;
  log('esito:', JSON.stringify(esito).slice(0, 600));
  if (!P.callback_url) return;
  for (let k = 0; k < 3; k++) {
    try { await richiesta(P.callback_url, { metodo: 'POST', corpo: { id: P.id, foglio: P.foglio || '', gid: P.gid || '', ...esito }, tentativi: 1 }); return; }
    catch (e) { log('avviso a n8n non riuscito:', String(e.message).slice(0, 150)); await sleep(10000); }
  }
}

// ======================================================================= PIPELINE
async function main() {
  await avviaServer();
  // ---- Load Channel Config + riga del file di produzione (come li leggeva n8n)
  const cfg = { ...P };
  metti('Load Channel Config', [J(cfg)]);
  const riga = { ...(P.riga || {}), titolo_originale: P.titolo_originale || (P.riga || {}).titolo_originale || '', 'Link video': P.link || P.id || '', status: 'Pronto' };
  for (const n of ['Read Production Row', 'Prima Riga Pronto', 'Filter']) metti(n, [J(riga)]);
  log('canale', cfg.channel_id, '| video', riga['Link video'], '|', riga.titolo_originale, PROVA ? '| PROVA' : '');

  // ---- 1) testo del competitor (IF Modalita -> HTTP Request3 / Nessuna Trascrizione)
  let trascr;
  if (String(riga['Link video'] || '').trim()) {
    const p = WF['HTTP Request3'].params, ctx = { items: [J(riga)], itemIndex: 0 };
    const url = valuta(p.url, ctx), q = JSON.parse(valuta(p.jsonQuery, ctx));
    trascr = await richiesta(url + '?' + new URLSearchParams(q).toString(), { headers: { 'X-RapidAPI-Key': E('RAPIDAPI_KEY'), 'X-RapidAPI-Host': 'youtube-transcript3.p.rapidapi.com' } });
    metti('HTTP Request3', [J(trascr)]);
    const n = Array.isArray(trascr.transcript) ? trascr.transcript.length : 0;
    log('trascrizione:', n, 'righe');
    if (!n) throw new Error('STOP: trascrizione del competitor vuota (' + JSON.stringify(trascr).slice(0, 200) + ')');
  } else trascr = (await codice('Nessuna Trascrizione', [J({})]))[0].json;
  // ---- copioni di riferimento (cartella Drive scripts_examples_folder_id, copiata nel repository in esempi_copioni/<id cartella>)
  const cart = path.join(ROOT, 'esempi_copioni', String(cfg.scripts_examples_folder_id || '').trim());
  const blocchi = fs.existsSync(cart) ? fs.readdirSync(cart).filter(f => f.endsWith('.txt')).sort()
    .map(f => '========== ' + f.replace(/^\d+_/, '').replace(/\.txt$/, '') + ' ==========\n\n' + fs.readFileSync(path.join(cart, f), 'utf8').trim()) : [];
  if (!blocchi.length) log('ATTENZIONE: nessun copione di riferimento in', cart);
  const ref = blocchi.slice(0, 3).join('\n\n---\n\n');
  metti('Code in JavaScript3', [J({ referenceBlock: ref, exampleCount: blocchi.length, totalChars: ref.length })]);
  metti('Merge', [J({ ...trascr, referenceBlock: ref, exampleCount: blocchi.length, totalChars: ref.length })]);
  await codice('Costruisci URL Copertina', [J({})]);

  // ---- 2) Bias Analyzer
  await agente('Bias Analyzer');
  log('leve psicologiche pronte');
  // ---- Ricerca Web? (web_research_enabled = SI)
  let ultimo = OUT['Bias Analyzer'];
  if (String(cfg.web_research_enabled || '').trim().toUpperCase() === 'SI') {
    const r = await claude(JSON.parse(valuta(WF['Ricerca Azienda'].params.jsonBody, { items: ultimo, itemIndex: 0 })));
    ultimo = metti('Ricerca Azienda', [J(r)]); log('dossier di ricerca web pronto');
  }
  setNodo('System Scriptwriter', ultimo);

  // ---- 3) copione a blocchi (Prepara Blocchi -> Loop Blocchi -> Costruisci Prompt Blocco -> Chiama Claude -> Accumula Blocco)
  const blocchiItems = await codice('Prepara Blocchi', [J({})]);
  for (const b of blocchiItems) {
    metti('Loop Blocchi', [b]);
    const cp = await codice('Costruisci Prompt Blocco', [b]);
    let corpo = cp[0].json.anthropicBody;
    for (let giro = 0; giro < 8; giro++) {
      const resp = await claude(corpo); metti('Chiama Claude', [J(resp)]);
      const acc = await codice('Accumula Blocco', [J(resp)]);
      if (!acc[0].json.__retry) { log('blocco', acc[0].json.blockDone, '/', acc[0].json.nBlocks, '- scene finora', acc[0].json.sceneFinora); break; }
      corpo = acc[0].json.anthropicBody; await sleep(5000);
    }
  }
  metti('Loop Blocchi', blocchiItems);
  const sw = (await codice('AI Scriptwriter', [J({})]))[0].json.output;
  log('copione:', sw.segments.length, 'scene | titolo:', sw.titolo_italiano);

  // ---- 9) copertina in parallelo (stesso programma e stesse impostazioni di "Copertina KAO n8n")
  let copertinaFatta = null;
  const saltaCop = String(cfg.skip_thumbnail || '').trim() !== '';
  if (!saltaCop && String(cfg.copertina_github || '').trim().toUpperCase() === 'SI') {
    copertinaFatta = python('copertine_cinema_kao.py', {
      PAYLOAD: JSON.stringify({ id: RUN_ID, titolo: sw.titolo_italiano, link_competitor: riga['Link video'], resume_url: `http://127.0.0.1:${PORTA}/risposta/copertina` }),
      APPLICA: 'NO', STILE: 'piatto', SFONDO_TESTO: 'fumetto', PROVA_SFONDI: 'NO', RIFAI: 'NO', COACH: 'NO', MAX_VIDEO: '5' }, 'copertina');
  } else if (!saltaCop) log('ATTENZIONE: copertina_github non e\' SI: su GitHub c\'e\' solo la copertina di copertine_cinema_kao.py');

  // ---- 4) tag del video originale + testo della copertina del competitor
  try {
    const id = valuta(WF['Tag Originale'].params.queryParameters.parameters.find(x => x.name === 'id').value, { items: [J({})], itemIndex: 0 });
    metti('Tag Originale', [J(id === 'nessuno' ? { items: [] } : await yt('https://www.googleapis.com/youtube/v3/videos?part=snippet&id=' + id))]);
  } catch (e) { log('tag originali non letti:', e.message.slice(0, 120)); metti('Tag Originale', [J({ items: [] })]); }
  const est = await codice('Estrai Copertina Competitor', [J({})]);
  if (est[0].json.attivo === true || est[0].json.attivo === 'true') {
    try { metti('Leggi Copertina Competitor', [J(await openaiChat(est[0].json.payload))]); }
    catch (e) { log('copertina competitor non letta:', e.message.slice(0, 120)); metti('Leggi Copertina Competitor', [J({})]); }
    await codice('Parse Copertina Competitor', OUT['Leggi Copertina Competitor']);
  }
  // ---- 5) SEO Generator (GPT-4.1 + formato JSON come il nodo "SEO Parser")
  await agente('SEO Generator', WF['SEO Parser'].params.jsonSchemaExample);
  log('SEO pronto | copertina:', OUT['SEO Generator'][0].json.output.titolo_thumbnail);

  // ---- scene: Edit Fields2 -> Split Out -> Classify scenes -> Limit
  setNodo('Edit Fields2', OUT['SEO Generator']);
  const segs = OUT['Edit Fields2'][0].json.segments || [];
  metti('Split Out', segs.map(s => J(typeof s === 'object' ? { ...s } : { segments: s })));
  await codice('Classify scenes', OUT['Split Out']);
  const lim = parseInt(valuta(WF['Limit'].params.maxItems, { items: [J({})], itemIndex: 0 })) || 999;
  const scene = metti('Limit', OUT['Classify scenes'].slice(0, lim));
  log('scene:', scene.length);

  // ---- 6) voce: Code in JavaScript1 -> HTTP Request (ElevenLabs) -> Upload file -> Accumula Audio -> Leggi Audio
  const c1 = await codice('Code in JavaScript1', scene);
  const pTTS = WF['HTTP Request'].params;
  const audio = new Array(c1.length);
  let prossimo = 0;
  const lavora = async () => {
    while (prossimo < c1.length) {
      const i = prossimo++;
      const ctx = { items: c1, item: c1[i], itemIndex: i };
      const buf = await richiesta(valuta(pTTS.url, ctx), { metodo: 'POST', corpo: JSON.parse(valuta(pTTS.jsonBody, ctx)), tipo: 'buffer', timeout: 120000,
        headers: { 'xi-api-key': E('ELEVENLABS_API_KEY'), Accept: 'audio/mpeg' } });
      const nome = PREFISSO_AUDIO + String(c1[i].json.index || i + 1) + '_audio.mp3';
      fs.writeFileSync(path.join(SERVER_DIR, nome), buf);
      audio[i] = { buf, nome };
    }
  };
  await Promise.all([lavora(), lavora(), lavora()]);
  metti('HTTP Request', audio.map(a => ({ json: {}, binary: { data: { fileName: a.nome, mimeType: 'audio/mpeg', fileSize: (a.buf.length / 1000).toFixed(1) + ' kB' } } })));
  metti('Upload file', audio.map(a => J({ id: a.nome, name: a.nome })));
  metti('Share file', OUT['Upload file']);
  await codice('Accumula Audio', OUT['Share file']);
  await codice('Leggi Audio', [J({})]);
  log('voce:', audio.length, 'audio');

  // ---- 7) Switch Render Mode: stock -> Pexels (solo per sapere se c'e' una clip; le clip vere le sceglie render_kao.py), typo -> texture
  const unisci = [];
  for (let i = 0; i < scene.length; i++) {
    const sc = scene[i], modo = sc.json.render_mode;
    if (modo === 'stock') {
      const q = WF['HTTP Request4'].params.queryParameters.parameters;
      const ctx = { items: scene, item: sc, itemIndex: i };
      const qs = new URLSearchParams(q.map(x => [x.name, String(valuta(x.value, ctx))])).toString();
      let r = {};
      try { r = await richiesta(WF['HTTP Request4'].params.url + '?' + qs, { headers: { Authorization: E('PEXELS_API_KEY') } }); }
      catch (e) { log('Pexels scena', i + 1, e.message.slice(0, 100)); }
      await sleep(1200);
      const pick = await codice('Pick Clip Pexels', [J(r)], { pair: () => i });
      if (pick[0].json.pexels_found) unisci.push(pick[0]);
      else if (String(cfg.scene_bg_textures || '').trim().length > 0) unisci.push((await codice('Pick Texture Fallback', pick, { pair: () => i }))[0]);
    } else if (modo === 'typo') unisci.push((await codice('Pick Texture', [sc], { pair: () => i }))[0]);
    else throw new Error('Scena ' + (i + 1) + ': render_mode "' + modo + '" (immagini AI) non e\' ancora previsto nel programma GitHub di KAO');
  }
  const ordinate = unisci.slice().sort((a, b) => (Number(a.json.scena) || 0) - (Number(b.json.scena) || 0));
  metti('Unisci Stock e Texture', unisci); metti('Sincronizza Media', unisci); metti('Ordina per scena', ordinate);
  log('scene tipografiche di riserva:', ordinate.filter(o => o.json.is_texture).length);

  // ---- Edit Fields -> Edit Fields1 -> Aggregate -> Collect Card URLs -> Raccogli Foto Cornice -> Prepara Render GitHub
  metti('Merge Audio Immagine', ordinate);
  setNodo('Edit Fields', ordinate);
  setNodo('Edit Fields1', OUT['Edit Fields']);
  const campi = WF['Aggregate'].params.fieldsToAggregate.fieldToAggregate.map(f => f.fieldToAggregate);
  const agg = {}; for (const k of campi) agg[k] = OUT['Edit Fields1'].map(it => it.json[k]).filter(v => v !== undefined);
  metti('Aggregate', [J(agg)]);
  metti('Build Card Payloads', [J({ _sentinel: true })]);
  await codice('Collect Card URLs', [J({})]);
  metti('Prepara Foto Cornice', [J({ _sentinel: true })]);
  await codice('Raccogli Foto Cornice', [J({})]);
  const prep = await codice('Prepara Render GitHub', [J({})]);
  const dati = JSON.parse(Buffer.from(prep[0].binary.data.data, 'base64').toString('utf8'));
  for (const s of dati.scene) { const m = String(s.audio || '').match(/id=(GHKAO_[^&]+)/); if (m) s.audio = urlLocale(m[1]); }
  if (String(cfg.effetti_github || '').trim().toUpperCase() === 'SI') log('ATTENZIONE: effetti_github = SI non e\' previsto qui (servirebbe json2video): montaggio senza effetti');

  // ---- 8) montaggio (render_kao.py, invariato)
  log('montaggio:', dati.scene.length, 'scene');
  const rr = await python('render_kao.py', { PAYLOAD: JSON.stringify({ id: RUN_ID, dati, resume_url: `http://127.0.0.1:${PORTA}/risposta/render` }), DRY_RUN: '0',
    LINGUA: String(cfg.language || 'it'), WHISPER_MODEL: E('WHISPER_MODEL', 'small') }, 'render');
  const movie = (rr.risposta || {}).movie || {};
  if (movie.status !== 'done') throw new Error('montaggio non riuscito: ' + (movie.message || 'codice ' + rr.code));
  metti('Attendi Render GitHub', [J({ body: rr.risposta })]);
  await codice('Risultato Render GitHub', OUT['Attendi Render GitHub']);
  const fileVideo = path.join(ROOT, 'lavoro_kao', 'video_finale.mp4');
  log('video:', Math.round(movie.duration / 6) / 10, 'minuti');
  metti('Upload file2', [J({ id: '' })]);
  await codice('Build Prompt Manuale', [J({})]);

  // ---- copertina: aspetto il programma partito in parallelo
  let copertina = null, urlCop = '';
  if (copertinaFatta) {
    const rc = await copertinaFatta;
    metti('Attendi Copertina GitHub', [J({ body: rc.risposta || {} })]);
    const ris = (await codice('Risultato Copertina GitHub', OUT['Attendi Copertina GitHub']))[0].json;
    if (ris.ok) { urlCop = ris.url; copertina = await richiesta(ris.url, { tipo: 'buffer' }); log('copertina pronta'); }
    else log('ATTENZIONE: copertina non creata: il video viene caricato con la copertina automatica di YouTube');
  }

  // ---- campi del foglio (Update row in sheet1, stesse formule)
  const colonne = {};
  const valori = WF['Update row in sheet1'].params.columns.value;
  for (const [k, v] of Object.entries(valori)) {
    if (['status', 'row_number', 'video_download', 'thumbnail_download', 'thumbnail_anteprima'].includes(k)) continue;
    try { colonne[k] = valuta(v, { items: [J({})], itemIndex: 0 }); } catch (e) { log('campo', k, 'non calcolato:', e.message.slice(0, 100)); }
  }

  // ---- 10) caricamento (stessa logica del Publisher)
  const td = String(riga.target_durata || '');
  const nTd = Number(td.replace(',', '.'));
  const privProva = String(cfg.privacy || '').trim().toLowerCase();
  // prova: si carica solo come NON IN ELENCO (colonna prova_github = NON IN ELENCO); con prova_github = SI il video va solo su Drive
  const carica = (!PROVA || privProva === 'unlisted') && String(cfg.carica || '').trim().toUpperCase() !== 'NO' && !/test|prova/i.test(td) && !(nTd > 0 && nTd < 8)
    && String(cfg.youtube_upload_enabled || '').trim() !== '';
  const extra = { titolo: colonne.titolo_italiano || sw.titolo_italiano, descrizione: colonne.descrizione_youtube || '', tag: colonne.tag_seo || '',
    testo_copertina: colonne.titolo_thumbnail || '', video_url: movie.url, copertina_url: urlCop,
    cartella_video: cfg.output_video_folder_id || '', cartella_copertine: cfg.output_thumbnail_folder_id || '', minuti_video: Math.round(movie.duration / 6) / 10,
    colonne: { frase_commento: colonne.frase_commento || '', post_community: colonne.post_community || '', video_anteprima: movie.url, movie_url: movie.url,
      thumbnail_prompt_inglese: colonne.thumbnail_prompt_inglese || '', prompt_copertina_manuale: colonne.prompt_copertina_manuale || '', copy_competitor_it: colonne.copy_competitor_it || '' } };
  if (!carica) {
    const temi = String(cfg.playlist_topics || '').split('|').map(s => s.trim()).filter(Boolean);
    if (temi.length) extra.playlist = 'scegli tra: ' + temi.join(' / ');
    await avvisa({ stato: PROVA ? 'PROVA OK' : 'CREATO', ...extra }); return;
  }
  const vid = await caricaYouTube(fileVideo, cfg, colonne);
  const note = [];
  if (copertina) { try { await yt('https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId=' + vid, { metodo: 'POST', corpo: copertina, headers: { 'Content-Type': 'image/jpeg' } }); }
    catch (e) { note.push('copertina non caricata: ' + e.message.slice(0, 120)); } }
  if (colonne.frase_commento) { try { await yt('https://www.googleapis.com/youtube/v3/commentThreads?part=snippet', { metodo: 'POST',
    corpo: { snippet: { videoId: vid, topLevelComment: { snippet: { textOriginal: colonne.frase_commento } } } } }); } catch (e) { note.push('primo commento non pubblicato'); } }
  if (!PROVA) { try { extra.playlist = await playlist(vid, cfg, extra.titolo, extra.descrizione); } catch (e) { note.push('playlist: ' + e.message.slice(0, 100)); } }
  await avvisa({ stato: PROVA ? 'PROVA OK' : 'PUBBLICATO', video_id: vid, link: 'https://www.youtube.com/watch?v=' + vid,
    pubblica_il: PROVA ? '' : (P.pubblica_il || ''), errore: note.join('; '), ...extra });
}

async function caricaYouTube(file, cfg, col) {
  // tag: stessa formula del Publisher (tag_seo + titolo + youtube_default_tags, max 460 caratteri)
  const tags = [...String(col.tag_seo || '').split(','), col.titolo_italiano, ...String(cfg.youtube_default_tags || '').split(',')]
    .map(t => String(t || '').replace(/[<>,"]/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 100)).filter(Boolean).filter((t, i, a) => a.indexOf(t) === i)
    .reduce((acc, t) => { const eff = t.length + (t.includes(' ') ? 2 : 0); const sep = acc.total ? 1 : 0; if (acc.total + sep + eff <= 460) { acc.list.push(t); acc.total += sep + eff; } return acc; }, { list: [], total: 0 }).list;
  const priv = String(cfg.privacy || '').trim().toLowerCase();
  const status = ['private', 'unlisted'].includes(priv) ? { privacyStatus: priv }
    : (P.pubblica_il && new Date(P.pubblica_il).getTime() > Date.now() + 20 * 60000 ? { privacyStatus: 'private', publishAt: new Date(P.pubblica_il).toISOString() } : { privacyStatus: 'public' });
  status.selfDeclaredMadeForKids = false;
  const lingua = String(cfg.language || 'it');
  const meta = { snippet: { title: String(col.titolo_italiano || '').slice(0, 100), description: String(col.descrizione_youtube || '').slice(0, 4900),
    categoryId: String(cfg.categoria || cfg.youtube_category_id || '27').replace(/\.0+$/, ''), defaultLanguage: lingua, defaultAudioLanguage: lingua, tags }, status };
  const dim = fs.statSync(file).size;
  const ini = await yt('https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status', { metodo: 'POST', corpo: meta, tipo: 'risposta',
    headers: { 'X-Upload-Content-Type': 'video/mp4', 'X-Upload-Content-Length': String(dim) } });
  const dove = ini.headers.get('location');
  const r = await richiesta(dove, { metodo: 'PUT', corpo: fs.readFileSync(file), headers: { 'Content-Type': 'video/mp4' }, timeout: 3600000, tentativi: 3 });
  log('caricato su YouTube:', r.id, '|', JSON.stringify(status));
  return r.id;
}
async function playlist(vid, cfg, titolo, descr) {   // stessa logica del Publisher (Scegli Argomento + Prepara Playlist)
  const temi = String(cfg.playlist_topics || '').split('|').map(s => s.trim()).filter(Boolean);
  if (!temi.length) return '';
  const norm = s => String(s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^a-z0-9 ]/g, ' ').replace(/\s+/g, ' ').trim();
  const r = await claude({ model: 'claude-haiku-4-5-20251001', max_tokens: 60, messages: [{ role: 'user', content: 'Argomenti disponibili (scegline UNO):\n' +
    temi.map(s => '- ' + s).join('\n') + '\n\nTitolo del video: ' + titolo + '\nDescrizione: ' + String(descr || '').slice(0, 600) +
    '\n\nRispondi SOLO con il nome dell\'argomento, copiato identico a come e\' scritto sopra, nient\'altro.' }] });
  const risp = testoClaude(r);
  const tema = temi.find(t => norm(t) === norm(risp)) || temi.find(t => norm(risp).includes(norm(t)));
  if (!tema) { log('playlist: argomento non riconosciuto', risp); return ''; }
  const lista = await yt('https://www.googleapis.com/youtube/v3/playlists?part=snippet&mine=true&maxResults=50');
  let pl = (lista.items || []).find(p => norm(p.snippet && p.snippet.title) === norm(tema));
  if (!pl) {
    const it = String(cfg.language || 'it').toLowerCase().startsWith('it');
    pl = await yt('https://www.googleapis.com/youtube/v3/playlists?part=snippet,status', { metodo: 'POST', corpo: { snippet: { title: tema,
      description: it ? tema + ' - tutti i video di ' + String(cfg.channel_name || '').trim() + ' su questo argomento.' : tema + ' - all ' + String(cfg.channel_name || '').trim() + ' videos on this topic.',
      defaultLanguage: cfg.language || 'it' }, status: { privacyStatus: 'public' } } });
  }
  await yt('https://www.googleapis.com/youtube/v3/playlistItems?part=snippet', { metodo: 'POST', corpo: { snippet: { playlistId: pl.id, resourceId: { kind: 'youtube#video', videoId: vid } } } });
  log('playlist:', tema); return tema;
}

main().then(() => { server.close(); process.exit(0); }).catch(async (e) => {
  console.error(e);
  await avvisa({ stato: 'ERRORE', errore: String(e.message || e).slice(0, 400) });
  server.close(); process.exit(1);
});
