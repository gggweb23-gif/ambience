// ===== MODELLI DI INQUADRATURA del motore "cartoni + grafici" (7 nov 2026, canale Quanto Ti Resta e futuri canali dello stesso stile).
// Claude sceglie per ogni inquadratura un modello (tipo) e i suoi parametri (p); qui si disegna tutto in codice: costo zero.
// Ogni modello: (t, d, p, C) -> svg. t = secondi dall'inizio dell'inquadratura, d = durata, C = contesto (protagonista, colori, numero inquadratura).
// Regola: gli elementi entrano uno dopo l'altro nel primo 70% della durata (mai un'immagine ferma), e ogni inquadratura ha sfondo e composizione propri.

const PALETTE = ['#FFE9C7', '#DDEBFF', '#E7F7EE', '#FFE7D6', '#E9E4FF', '#FFF6E5', '#DDF5F1', '#FFE0EF', '#F6F7FB', '#FFF3CC', '#E6F4FF', '#EDF1FF'];
const SCURI = ['#1E2235', '#2A3366', '#14513A', '#2A1E3F', '#3A3F58'];
const COLS = [R, Y, PU, G, BL, OR, '#FF7FB6', '#4CC9F0'];
const tappa = (t, d, i, n) => pop(t, .25 + i * Math.max(.35, Math.min(1.2, d * .7 / Math.max(1, n))), .45);   // entrata dell'elemento i di n
const S = v => String(v ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const sfondo = (C, scuro = false) => scuro ? BG(SCURI[C.i % SCURI.length]) : BG(PALETTE[(C.i * 5 + 3) % PALETTE.length]);
const titoletto = (txt, t, y = 130, bg = INK, fg = Y) => txt ? label(960, y, pop(t, .15), S(txt), bg, fg, txt.length > 34 ? 48 : 58) : '';
const lato = C => (C.i % 2 ? 1 : -1);   // alterna destra/sinistra tra un'inquadratura e l'altra

// ----- oggetti disegnati per nome (prezzi, conteggi, copertine)
function oggetto(nome, x, y, s, t = 0, c) {
  const n = String(nome || '').toLowerCase();
  const col = c || COLS[(n.length * 3) % COLS.length];
  if (/magliett|t-shirt|felpa|vestit|abbigl/.test(n)) return tee(x, y, s, col);
  if (/caff|tazz|cappucc/.test(n)) return cup(x, y + 20 * s, s);
  if (/pizz/.test(n)) return tr(x, y, s, `<circle r="110" fill="#F2C46D" ${SW}/><circle r="88" fill="#E8543A"/>${[[-30, -20], [35, -30], [10, 35], [-45, 30], [50, 25]].map(([a, b]) => `<circle cx="${a}" cy="${b}" r="16" fill="#FFF3B0" ${SW5}/>`).join('')}`);
  if (/pane|pagnott|bread|cornett|brioche/.test(n)) return bread(x, y, s * 1.2);
  if (/gelat|cono/.test(n)) return cone(x, y, s);
  if (/crem|bottigli|flacon|profum|shampoo|acqua/.test(n)) return bottle(x, y, s);
  if (/scarp|sneaker/.test(n)) return tr(x, y, s, `<path d="M-120 20 q0 -60 40 -60 l40 30 q60 10 120 30 q40 10 40 40 h-240z" fill="${col}" ${SW}/><path d="M-120 60 h240 v14 h-240z" fill="#fff" ${SW5}/>`);
  if (/libr/.test(n)) return tr(x, y, s, `<rect x="-90" y="-120" width="180" height="240" rx="10" fill="${col}" ${SW}/><rect x="-70" y="-90" width="140" height="40" rx="6" fill="#fff" ${SW5}/>`);
  if (/occhial/.test(n)) return tr(x, y, s, `<circle cx="-60" r="50" fill="#CDEBFF" ${SW} stroke-width="10"/><circle cx="60" r="50" fill="#CDEBFF" ${SW} stroke-width="10"/><path d="M-10 -6 q10 -14 20 0" fill="none" ${SW} stroke-width="10"/>`);
  if (/panin|kebab|hamburg|piadin|toast/.test(n)) return tr(x, y, s, `<path d="M-110 -10 q110 -110 220 0z" fill="#E09A4A" ${SW}/><rect x="-115" y="-10" width="230" height="22" rx="8" fill="#6BBF59" ${SW5}/><rect x="-110" y="12" width="220" height="26" rx="8" fill="#8B4A2B" ${SW5}/><path d="M-110 38 h220 q0 40 -110 40 q-110 0 -110 -40z" fill="#E09A4A" ${SW}/>`);
  if (/fior|ros|mazz/.test(n)) return tr(x, y, s, `<path d="M0 120 V-20" stroke="${G}" stroke-width="12"/>${[0, 72, 144, 216, 288].map(a => `<ellipse cx="0" cy="-60" rx="26" ry="40" fill="${R}" ${SW5} transform="rotate(${a} 0 -20)"/>`).join('')}<circle cy="-20" r="22" fill="${Y}" ${SW5}/>`);
  if (/auto|macchin|car/.test(n)) return tr(x, y, s, `<rect x="-160" y="-40" width="320" height="80" rx="30" fill="${col}" ${SW}/><path d="M-100 -40 q30 -70 100 -70 q70 0 100 70z" fill="#CDEBFF" ${SW}/><circle cx="-90" cy="44" r="34" fill="${INK}"/><circle cx="90" cy="44" r="34" fill="${INK}"/>`);
  if (/benzin|carburant|litr|gasol/.test(n)) return tr(x, y, s, `<rect x="-70" y="-120" width="140" height="220" rx="14" fill="${R}" ${SW}/><rect x="-46" y="-90" width="92" height="60" rx="8" fill="#fff" ${SW5}/><path d="M70 -40 q60 0 60 60 v60" fill="none" ${SW} stroke-width="12"/>`);
  if (/letto|camer|notte|hotel|b&b/.test(n)) return tr(x, y, s, `<rect x="-160" y="-20" width="320" height="80" rx="14" fill="${BL}" ${SW}/><rect x="-160" y="-90" width="40" height="150" rx="10" fill="#8B5A2B" ${SW}/><rect x="-110" y="-50" width="90" height="40" rx="16" fill="#fff" ${SW5}/>`);
  if (/giornal|rivist/.test(n)) return tr(x, y, s, `<rect x="-120" y="-150" width="240" height="300" rx="8" fill="#fff" ${SW}/>${T(0, -90, 'NEWS', 50, INK)}<path d="M-90 -50 h180 M-90 -10 h180 M-90 30 h120 M-90 70 h180" stroke="${GR}" stroke-width="12" stroke-linecap="round"/>`);
  if (/popcorn/.test(n)) return tr(x, y, s, `<path d="M-80 -60 h160 l-24 180 h-112z" fill="#fff" ${SW}/><path d="M-50 -60 l-10 180 M0 -60 v180 M50 -60 l10 180" stroke="${R}" stroke-width="18"/>${[-60, -20, 20, 60].map((a, i) => `<circle cx="${a}" cy="${-80 - (i % 2) * 20}" r="30" fill="#FFF3B0" ${SW5}/>`).join('')}`);
  if (/manubr|pes|palestr/.test(n)) return tr(x, y, s, `<rect x="-130" y="-14" width="260" height="28" rx="10" fill="${GR}" ${SW5}/>${[-120, -90, 90, 120].map(a => `<rect x="${a - 14}" y="-60" width="28" height="120" rx="8" fill="${INK}"/>`).join('')}`);
  if (/forbic|tagli|capell/.test(n)) return scissors(x, y, s * 1.4, Math.abs(Math.sin(t * 8)));
  if (/carn|bistecc|salum/.test(n)) return tr(x, y, s, `<path d="M-120 0 q0 -90 110 -90 q130 0 130 90 q0 80 -120 80 q-120 0 -120 -80z" fill="#E8543A" ${SW}/><path d="M-60 -10 q60 -40 120 0" fill="none" stroke="#fff" stroke-width="14"/>`);
  if (/bigliett|ticket/.test(n)) return tr(x, y, s, `<rect x="-140" y="-70" width="280" height="140" rx="16" fill="${Y}" ${SW}/><path d="M60 -70 v140" stroke="${INK}" stroke-width="6" stroke-dasharray="12 10"/>${T(-40, 20, 'TICKET', 44, INK)}`);
  if (/lavatric|bucato|lavander/.test(n)) return tr(x, y, s, `<rect x="-110" y="-130" width="220" height="260" rx="20" fill="#fff" ${SW}/><circle cy="20" r="70" fill="#7CC4FF" ${SW}/><circle cy="20" r="40" fill="#CDEBFF" transform="rotate(${t * 200})"/>`);
  if (/telefon|smartphone|ordine|online|app/.test(n)) return phone(x, y, s * .5, T(0, 0, '🛒'.length ? 'SHOP' : '', 60, INK));
  if (/soldi|euro|banconot|cassa/.test(n)) return note(x - 160 * s, y - 80 * s, 320 * s, 160 * s, '€', '#8FD18B', 80 * s);
  if (/monet/.test(n)) return coin(x, y, s * 1.6, t * 60);
  if (/pacchett|scatol|pacco|sigarett|tabacc/.test(n)) return box(x, y, s, '#C98A4B');
  return box(x, y, s, col);
}

// ----- ambienti (il "luogo" di ogni storia): pareti, pavimento e arredi diversi per ogni tipo di attivita'
function luogo(tipo, t, C, insegna) {
  const n = String(tipo || '').toLowerCase(), k = C.i;
  const muro = PALETTE[(k * 7 + n.length) % PALETTE.length];
  let s = BG(muro) + floor(820, ['#E8B97A', '#C9CED9', '#D9B98A', '#B8C1D9', '#C98A4B'][(k + n.length) % 5]);
  const scritta = insegna ? `<rect x="1360" y="80" width="500" height="100" rx="20" fill="${INK}"/>` + TF(1610, 150, S(insegna).toUpperCase(), 52, 450, Y, {}, 36) : '';
  if (/bar|caff/.test(n)) s += `<rect x="140" y="260" width="300" height="300" rx="26" fill="${GR}" ${SW}/><rect x="180" y="300" width="220" height="80" rx="12" fill="#5A5F73" ${SW5}/>` + [0, 1, 2].map(i => `<path d="M${270 + i * 20} ${250 - ((t * 60 + i * 30) % 90)} q-14 -20 0 -40" fill="none" stroke="#fff" stroke-width="8" stroke-linecap="round" opacity=".8"/>`).join('') + [0, 1, 2, 3, 4].map(i => cup(560 + i * 110, 300, .4)).join('');
  else if (/pizz|ristorant|cucin|sushi|kebab|food/.test(n)) s += `<rect x="1100" y="260" width="560" height="420" rx="200" fill="#8B5A2B" ${SW}/><path d="M1200 640 q180 -240 360 0z" fill="#3A1E10" ${SW}/><path d="M1240 640 q140 -180 280 0z" fill="${OR}" opacity="${.6 + .3 * Math.sin(t * 6)}"/>` + `<rect y="0" width="1920" height="110" fill="${R}"/>` + [...Array(24)].map((_, i) => `<rect x="${i * 80}" y="0" width="40" height="110" fill="#fff" opacity=".5"/>`).join('');
  else if (/parrucch|barbier|estet/.test(n)) s += `<rect x="1150" y="180" width="460" height="380" rx="190" fill="#CDEBFF" ${SW}/><path d="M260 240 v380" stroke="${R}" stroke-width="40"/><path d="M260 240 v380" stroke="#fff" stroke-width="40" stroke-dasharray="30 30" stroke-dashoffset="${t * 60}"/><rect x="1220" y="620" width="320" height="200" rx="30" fill="${INK}"/>`;
  else if (/palestr|gym|fitness/.test(n)) s += [0, 1, 2].map(i => tr(300 + i * 500, 640, 1, `<rect x="-120" y="-60" width="240" height="120" rx="20" fill="#5A5F73" ${SW}/><rect x="-140" y="40" width="280" height="40" rx="14" fill="${INK}"/>`)).join('') + oggetto('manubrio', 1500, 300, 1);
  else if (/autolavag|lavaggio/.test(n)) s += `<rect x="560" y="140" width="800" height="680" fill="#E6E8F0" ${SW}/>` + [0, 1, 2].map(i => `<rect x="${640 + i * 240}" y="180" width="80" height="560" rx="30" fill="${[BL, PU, Y][i]}" opacity=".85" transform="rotate(${Math.sin(t * 6 + i) * 6} ${680 + i * 240} 180)" ${SW5}/>`).join('') + oggetto('auto', 960, 720, 1.2);
  else if (/gelat/.test(n)) s += `<rect x="200" y="420" width="900" height="200" rx="20" fill="#fff" ${SW}/>` + [...Array(6)].map((_, i) => `<rect x="${230 + i * 145}" y="450" width="120" height="70" rx="10" fill="${['#FF9EC4', '#9BE3B3', '#FFE7A8', '#C8A2FF', '#FFB38A', '#8B4A2B'][i]}" ${SW5}/>`).join('') + cone(1500, 320, .9);
  else if (/pan|forn|pasticc/.test(n)) s += `<rect x="1100" y="260" width="600" height="440" rx="40" fill="#8B5A2B" ${SW}/><path d="M1200 640 q200 -260 400 0z" fill="#3A1E10" ${SW}/><path d="M1240 640 q160 -200 320 0z" fill="${OR}" opacity="${.6 + .3 * Math.sin(t * 6)}"/>` + [...Array(6)].map((_, i) => bread(200 + (i % 3) * 150, 600 - Math.floor(i / 3) * 80, .6)).join('');
  else if (/online|e-commerce|ecommerce|magazzin|spediz/.test(n)) s += [...Array(8)].map((_, i) => box(240 + (i % 4) * 170, 700 - Math.floor(i / 4) * 150, .9, ['#C98A4B', '#D9A066'][i % 2])).join('') + laptop(1400, 700, .9, T(0, -200, 'SHOP', 60, INK));
  else if (/hotel|b&b|bnb|albergo/.test(n)) s += [...Array(6)].map((_, i) => `<rect x="${200 + (i % 3) * 300}" y="${180 + Math.floor(i / 3) * 260}" width="220" height="200" rx="10" fill="${i % 4 ? '#FFF3B0' : '#2A3366'}" ${SW}/>`).join('') + oggetto('letto', 1450, 640, 1.2);
  else if (/supermerc|alimentar|market/.test(n)) s += `<rect x="0" y="120" width="1920" height="80" fill="${G}"/>` + [0, 1].map(r => shelf(160, 380 + r * 220, 1600)).join('') + [...Array(24)].map((_, i) => box(200 + (i % 12) * 130, 340 + Math.floor(i / 12) * 220, .3, COLS[i % COLS.length])).join('');
  else if (/cinema/.test(n)) s += `<rect x="260" y="120" width="1400" height="520" rx="20" fill="#fff" ${SW}/><rect x="300" y="160" width="1320" height="440" fill="#2A3366"/>` + stars(t).replace(/cy="(\d+)"/g, (m, v) => `cy="${180 + (+v % 400)}"`) + [...Array(10)].map((_, i) => `<rect x="${200 + i * 160}" y="700" width="120" height="120" rx="20" fill="${R}" ${SW}/>`).join('');
  else if (/edicol|giornal/.test(n)) s += `<rect x="460" y="200" width="1000" height="620" rx="20" fill="${G}" ${SW}/>` + [...Array(8)].map((_, i) => oggetto('giornale', 600 + (i % 4) * 230, 400 + Math.floor(i / 4) * 260, .55)).join('');
  else if (/fior/.test(n)) s += [...Array(7)].map((_, i) => oggetto('fiore', 220 + i * 230, 640 + (i % 2) * 40, .9)).join('');
  else if (/lavander/.test(n)) s += [...Array(4)].map((_, i) => oggetto('lavatrice', 300 + i * 360, 640, 1.1, t)).join('');
  else if (/officin|meccan|garage/.test(n)) s += oggetto('auto', 1100, 700, 1.6) + `<rect x="200" y="300" width="400" height="300" fill="#5A5F73" ${SW}/>` + [0, 1, 2].map(i => `<rect x="${230 + i * 120}" y="340" width="20" height="200" fill="${GR}"/>`).join('');
  else if (/ottic|occhial/.test(n)) s += shelf(1200, 340, 600) + shelf(1200, 560, 600) + [...Array(6)].map((_, i) => oggetto('occhiali', 1280 + (i % 3) * 180, 300 + Math.floor(i / 3) * 220, .5)).join('');
  else if (/macell|salum/.test(n)) s += `<rect x="200" y="460" width="1000" height="160" rx="20" fill="#fff" ${SW}/>` + [...Array(4)].map((_, i) => oggetto('carne', 330 + i * 240, 540, .6)).join('');
  else if (/scuola|guida|autoscuol/.test(n)) s += oggetto('auto', 1300, 700, 1.4) + `<rect x="200" y="200" width="500" height="320" rx="20" fill="#2E5E3E" ${SW}/>` + T(450, 380, 'A B', 90, '#fff');
  else if (/asil|nido|scuol/.test(n)) s += [...Array(6)].map((_, i) => `<rect x="${200 + i * 120}" y="${600 - (i % 3) * 60}" width="100" height="100" rx="14" fill="${COLS[i]}" ${SW}/>` + T(250 + i * 120, 672 - (i % 3) * 60, 'ABCDEF'[i], 60, '#fff')).join('');
  else if (/idraul|tecnic|artigian|furgon/.test(n)) s += tr(1300, 760, 1, `<rect x="-300" y="-260" width="500" height="220" rx="20" fill="#fff" ${SW}/><path d="M200 -200 h100 l60 80 v80 h-160z" fill="${BL}" ${SW}/>` + [-200, 220].map(x => `<circle cx="${x}" cy="-30" r="44" fill="${INK}"/>`).join(''));
  else if (/benzin|distribut/.test(n)) s += [0, 1].map(i => oggetto('benzina', 500 + i * 400, 640, 1.2)).join('') + `<rect x="300" y="140" width="1100" height="90" fill="${R}" ${SW}/>`;
  else if (/uffic|commercial|banc/.test(n)) s += `<rect x="1100" y="240" width="560" height="380" rx="20" fill="#fff" ${SW}/>` + [0, 1, 2, 3].map(i => `<path d="M1150 ${310 + i * 70} h${380 - i * 60}" stroke="${GR}" stroke-width="14" stroke-linecap="round"/>`).join('') + laptop(500, 760, .7);
  else s += shelf(1300, 300, 500) + shelf(1300, 560, 500) + [...Array(8)].map((_, i) => oggetto(C.oggetto || 'scatola', 1360 + (i % 4) * 120, 250 + Math.floor(i / 4) * 260, .5, t, COLS[i % COLS.length])).join('');
  return s + scritta;
}

// ----- personaggi: il protagonista della puntata (definito da Claude) e comparse sempre diverse
function prot(C, x, y, s, t, extra = {}) {
  const P = C.prot || {};
  const pelle = { chiara: SK, media: SK2, scura: SK3 }[P.pelle] || SK;
  const capelli = ['marco', 'giulia', 'short', 'long', 'curly', 'bun', 'bald', 'cap', 'chef'].includes(P.capelli) ? P.capelli : 'short';
  return person(Object.assign({ x, y, s, t, hair: capelli, hairC: P.colore_capelli || '#5B3A29', skin: pelle, shirt: P.maglia || '#3BAFDA',
    apron: P.grembiule || null, glasses: !!P.occhiali, seed: .4 }, extra));
}
const comparsa = (C, j, x, y, s, t, e = {}) => cliente((C.i * 3 + j) % CLIENTI.length, x, y, s, t, e);
const mood = m => ({ felice: 'happy', preoccupato: 'worried', stupito: 'wow', triste: 'sad', calmo: 'calm', parla: 'happy' }[m] || 'happy');

// ===== I MODELLI
const TPL = {};

// storia: il protagonista nel suo luogo di lavoro, con clienti
TPL.luogo = (t, d, p, C) => {
  const L = lato(C), m = mood(p.azione), jump = p.azione === 'festa';
  let s = luogo(p.luogo || C.attivita, t, C, p.insegna);
  const nc = Math.min(5, +p.clienti || 0);
  for (let j = 0; j < nc; j++) s += comparsa(C, j, L > 0 ? lerp(-200, 220 + j * 150, OUT(pr(t, j * .25, 1.6))) : lerp(2100, 1700 - j * 150, OUT(pr(t, j * .25, 1.6))), 980, .55, t, { walk: t < 1.6 + j * .25 });
  s += prot(C, L > 0 ? 1150 : 760, 1000, 1, t, { mood: m, jump, sweat: m === 'worried', aL: jump ? 150 : 20, aR: jump ? -150 : -40 + 20 * Math.sin(t * 3) });
  if (jump) s += confetti(t, 30);
  if (p.testo) s += label(960, 130, pop(t, .5), S(p.testo), INK, '#fff', 54);
  return s;
};

// prezzo di un prodotto, con cambio di prezzo opzionale
TPL.prezzo = (t, d, p, C) => {
  const L = lato(C), cambia = p.nuovo_prezzo && t > d * .45;
  let s = sfondo(C) + `<circle cx="${L > 0 ? 620 : 1300}" cy="520" r="${300 + 10 * Math.sin(t * 2)}" fill="#fff" opacity=".6"/>`;
  s += oggetto(p.oggetto || C.oggetto, L > 0 ? 620 : 1300, 520, 1.9 * pop(t, .1, .6), t);
  const tg = cambia ? S(p.nuovo_prezzo) : S(p.prezzo || '');
  s += tr(L > 0 ? 1180 : 360, 400, 1.25 * pop(t, .5), tag(0, 0, 1, tg, cambia ? Y : '#fff'), Math.sin(t * 3) * 6 + (cambia ? Math.sin(pr(t, d * .45, .5) * Math.PI) * 25 : 0));
  if (p.nota) s += label(960, 900, pop(t, Math.min(d * .5, 1.6)), S(p.nota), INK, Y, 54);
  return s;
};

// il prezzo diviso in fette (barra + ciambella), l'ultima fetta evidenziata
TPL.fette = (t, d, p, C) => {
  const F = (p.fette || []).slice(0, 6), tot = +p.totale || F.reduce((a, b) => a + (+b.valore || 0), 0) || 1;
  let s = sfondo(C) + titoletto(p.titolo || (p.totale ? `Dove vanno ${S(p.totale_testo || eur(+p.totale))}` : ''), t);
  let acc = 0; const Cc = 2 * Math.PI * 200;
  const cols = F.map((f, i) => i === (p.evidenzia ?? F.length - 1) ? G : [R, OR, PU, BL, GR, '#FF7FB6'][i % 6]);
  s += `<g transform="translate(560 560) rotate(-90)"><circle r="200" fill="none" stroke="${INK}" stroke-width="104"/><circle r="200" fill="none" stroke="#E6E8F0" stroke-width="90"/>`;
  F.forEach((f, i) => { const v = (+f.valore || 0) / tot * pr(t, .3 + i * .45, .5); s += `<circle r="200" fill="none" stroke="${cols[i]}" stroke-width="90" stroke-dasharray="${Cc * v} ${Cc}" stroke-dashoffset="${-Cc * acc}"/>`; acc += (+f.valore || 0) / tot });
  s += `</g>` + T(560, 590, S(p.totale_testo || (p.totale ? eur(+p.totale) : '')), 70, INK);
  F.forEach((f, i) => { const q = pop(t, .3 + i * .45); if (q) s += tr(1000, 300 + i * 105, q, `<rect x="0" y="-36" width="60" height="60" rx="14" fill="${cols[i]}" ${SW5}/>` + T(90, 10, S(f.nome), fit(S(f.nome), 50, 790 - 90 - larg(S(f.testo || eur(+f.valore || 0)), 54) - 30), INK, { a: 'start' }) + T(800, 10, S(f.testo || eur(+f.valore || 0)), fit(S(f.testo || eur(+f.valore || 0)), 54, 300), i === (p.evidenzia ?? F.length - 1) ? DG : INK, { a: 'end' })) });
  return s;
};

// formula: a (op) b = risultato, con riquadri che entrano uno alla volta
TPL.formula = (t, d, p, C) => {
  const n = 4, w = Math.max(420, Math.min(620, 50 * Math.max(String(p.a).length, String(p.b).length)));
  let s = sfondo(C) + titoletto(p.titolo, t);
  s += tr(560, 440, tappa(t, d, 0, n), rr(-w / 2, -110, w, 220, 40, R) + TF(0, 34, S(p.a), 90, w - 60, '#fff'));
  s += T(960, 470, S(p.op || '÷'), 140, INK, { op: tappa(t, d, 1, n) });
  s += tr(1360, 440, tappa(t, d, 1, n), rr(-w / 2, -110, w, 220, 40, G) + TF(0, 34, S(p.b), 90, w - 60, '#fff'));
  const r = String(p.risultato || ''), wr = Math.min(1700, Math.max(760, larg('= ' + S(r), 90) + 120)); s += tr(960, 780, tappa(t, d, 2, n), rr(-wr / 2, -110, wr, 220, 50, Y) + TF(0, 34, '= ' + S(r), 90, wr - 80, INK));
  if (p.nota) s += TF(960, 960, S(p.nota), 44, 1700, '#3A3F58', { op: tappa(t, d, 3, n) });
  return s;
};

// conteggio: tanti oggetti che si riempiono + numero grande
TPL.conteggio = (t, d, p, C) => {
  const N = Math.max(1, Math.min(60, +p.icone || +p.n || 20)), k = Math.round(N * E(pr(t, .2, Math.max(1.2, d * .6))));
  const cols = Math.min(12, Math.ceil(Math.sqrt(N * 2.2))), sz = Math.min(1, 9 / cols) * .55;
  let s = sfondo(C);
  for (let i = 0; i < k; i++) s += oggetto(p.oggetto || C.oggetto, 960 - (cols - 1) * 75 * sz / .55 + (i % cols) * 150 * sz / .55, 220 + Math.floor(i / cols) * 140 * sz / .55, sz, t, COLS[i % COLS.length]);
  s += tr(960, 870, pop(t, .4), rr(-520, -80, 1040, 160, 50, INK) + TF(0, 26, S(p.testo || ''), 64, 960, Y, {}, 44));
  return s;
};

// grafico del punto di pareggio
TPL.pareggio = (t, d, p, C) => {
  const F = +p.fissi || 3000, m0 = +p.margine || 10, m1 = +p.nuovo_margine || 0, xb = F / (m1 || m0);
  const xm = +p.xmax || Math.max(10, Math.ceil(xb * 1.6 / 10) * 10), m = m1 ? lerp(m0, m1, E(pr(t, d * .35, 1.2))) : m0;
  const ym = Math.max(F * 1.6, xm * m * 1.05);
  return sfondo(C) + titoletto(p.titolo, t, 110) + pareggio({ F, m, xm, ym, t, unit: S(p.unita || 'pezzi venduti'), red: OUT(pr(t, .2, .8)), green: E(pr(t, .6, Math.max(1.2, d * .45))),
    mark: pop(t, Math.min(d * .6, 2.4)), loss: p.perdita ? pr(t, d * .65, .6) : 0, gain: p.guadagno ? pr(t, d * .7, .6) : 0, icon: oggetto(p.oggetto || C.oggetto, 0, -10, .3) })
    .replace(/(\d+) € /g, '$1 € ');
};

// barre di 12 mesi (stagionalita', cali, picchi)
TPL.mesi = (t, d, p, C) => {
  const M = ['G', 'F', 'M', 'A', 'M', 'G', 'L', 'A', 'S', 'O', 'N', 'D'], V = (p.valori || []).slice(0, 12).map(Number), mx = Math.max(...V, 1);
  const ev = new Set((p.evidenzia || []).map(Number));
  let s = sfondo(C) + `<rect x="160" y="160" width="1600" height="760" rx="30" fill="#fff" ${SW}/>` + titoletto(p.titolo, t, 110);
  V.forEach((v, i) => { const h = 520 * v / mx * E(pr(t, .2 + i * .08, .6)); s += `<rect x="${260 + i * 125}" y="${840 - h}" width="80" height="${h}" rx="10" fill="${ev.has(i + 1) ? R : BL}" ${SW5}/>` + T(300 + i * 125, 890, M[i], 40, '#5A5F73') });
  if (p.nota) s += label(1300, 250, pop(t, d * .55), S(p.nota), R, '#fff', 46);
  return s;
};

// confronto tra due opzioni
TPL.confronto = (t, d, p, C) => {
  const A = p.a || {}, B = p.b || {}, v = String(p.vincitore || '');
  let s = sfondo(C) + titoletto(p.titolo, t, 120);
  [[A, 520, 0], [B, 1400, 1]].forEach(([o, x, j]) => {
    const q = tappa(t, d, j, 3);
    s += tr(x, 560, q, rr(-330, -300, 660, 600, 40, '#fff') + oggetto(o.oggetto || C.oggetto, 0, -110, 1, t, j ? PU : Y) + TF(0, 90, S(o.titolo || ''), 50, 600, INK, {}, 36) + TF(0, 200, S(o.valore || ''), 84, 600, j ? PU : DG));
    if ((v === 'a' && !j) || (v === 'b' && j)) s += tr(x, 200, pop(t, d * .6), `<path d="M-80 30 l-20 -80 l50 40 l50 -60 l50 60 l50 -40 l-20 80z" fill="${Y}" ${SW}/>`);
  });
  s += T(960, 600, 'VS', 110, R, { st: '#fff', sw: 14 });
  return s;
};

// elenco con le spunte (cose da guardare, voci di costo, passi)
TPL.lista = (t, d, p, C) => {
  const V = (p.voci || []).slice(0, 6);
  const W = 820, cx = C.i % 2 ? 700 : 1220, L = cx - W / 2, top = 150, bot = 860, z = 20, nz = Math.round(W / z);
  let carta = `M${L} ${top} h${W} V${bot}`;
  for (let k = 0; k < nz; k++) carta += ` l${-W / nz} ${k % 2 ? -z : z}`;   // bordo strappato in basso
  carta += ` L${L} ${bot} Z`;
  let s = sfondo(C) + `<path d="${carta}" fill="#fff" ${SW}/>` + TF(cx, top + 95, S(p.titolo || ''), 64, W - 80, INK, {}, 44);
  const passo = Math.min(100, (bot - 70 - (top + 200)) / Math.max(1, V.length - 1 || 1)), x0 = L + 70, maxW = W - 140;
  V.forEach((v, i) => { const q = pr(t, .3 + i * Math.min(1, d * .7 / Math.max(1, V.length)), .3), y = top + 200 + i * passo; s += op(q, TF(x0 + 60, y + 16, S(v), V.length > 4 ? 44 : 52, maxW, INK, { a: 'start' }, 40)) + (q >= 1 ? tick(x0, y, .32) : '') });
  s += prot(C, C.i % 2 ? 1520 : 380, 1000, .8, t, { mood: 'calm', aR: -120 });
  return s;
};

// costi fissi: icone che spuntano intorno al protagonista + totale
TPL.costi = (t, d, p, C) => {
  const V = (p.voci || []).slice(0, 6), pos = [[330, 300], [1590, 300], [330, 650], [1590, 650], [600, 170], [1320, 170]];
  const ico = (n, tt) => { const x = String(n).toLowerCase(); return /affitt|casa|local/.test(x) ? house(0, -40, .9) : /luce|energ|gas|bollett/.test(x) ? bulb(0, -40, .9, tt) : /person|dipend|stipend|commess|camerier|cuoc|istrutt|staff/.test(x) ? person({ x: 0, y: 70, s: .42, t: tt, hair: 'bun', hairC: '#8B4A2B', shirt: PU }) : /program|softw|internet|telef/.test(x) ? laptop(0, 20, .28) : /commercial|tasse|assicur|banc/.test(x) ? person({ x: 0, y: 70, s: .42, t: tt, hair: 'short', hairC: '#777', shirt: GR, glasses: true, tie: BL }) : /macchin|attrezz|forn|furgon|auto|leasing/.test(x) ? oggetto('auto', 0, -20, .45) : coin(0, -30, 1.4, tt * 40) };
  let s = sfondo(C) + prot(C, 960, 1000, 1, t, { mood: 'worried', aL: 40 + 10 * Math.sin(t * 5), aR: -40 - 10 * Math.sin(t * 5) });
  let tot = 0;
  V.forEach((v, i) => { const q = tappa(t, d, i, V.length + 1); if (!q) return; tot += (+v.valore || 0) * cl(q); const [x, y] = pos[i]; s += tr(x, y, q, ico(v.nome, t) + label(0, 110, 1, `${S(v.nome)} ${S(v.testo || eur(+v.valore || 0, 0))}`, '#fff', INK, 34)) });
  const totv = +p.totale || V.reduce((a, b) => a + (+b.valore || 0), 0);
  s += tr(960, 470, tappa(t, d, V.length, V.length + 1), rr(-330, -66, 660, 132, 40, INK) + T(0, 24, `${num(Math.min(tot, totv) || totv)} € ${S(p.periodo || 'al mese')}`, 58, Y));
  return s;
};

// domanda / colpo di scena: protagonista grande + scritta
TPL.domanda = (t, d, p, C) => {
  const m = mood(p.emozione || 'stupito'), L = lato(C);
  let s = sfondo(C, !!p.scuro) + `<circle cx="${L > 0 ? 1300 : 620}" cy="560" r="${380 + 16 * Math.sin(t * 3)}" fill="#fff" opacity=".5"/>`;
  s += prot(C, L > 0 ? 1300 : 620, 1010, 1.2, t, { mood: m, sweat: m === 'worried' || m === 'wow', aL: m === 'happy' ? 150 : 120, aR: m === 'happy' ? -150 : -120 });
  if (m === 'wow' || m === 'worried') for (let i = 0; i < 6; i++) { const ph = (t * .5 + i / 6) % 1; s += T(L > 0 ? 300 + (i * 173) % 600 : 1100 + (i * 173) % 600, -60 + ph * 1100, '?', 90 + (i % 3) * 30, [R, BL, PU][i % 3], { op: .7 }) }
  if (p.testo) s += tr(L > 0 ? 560 : 1360, 420, pop(t, .4), bubble(0, 0, Math.min(860, larg(S(p.testo), 66) + 120), 220, TF(0, 22, S(p.testo), 66, 760, INK, {}, 46)));
  return s;
};

// bilancia: due cose a confronto per peso
TPL.bilancia = (t, d, p, C) => {
  const tilt = lerp(0, p.pende === 'sinistra' ? 12 : p.pende === 'destra' ? -12 : 0, E(pr(t, d * .4, .8)));
  return sfondo(C) + titoletto(p.titolo, t, 140) + `<path d="M960 320 V900" ${SW} stroke-width="16"/><path d="M820 900 h280" ${SW} stroke-width="16"/>` +
    tr(960, 320, 1, `<path d="M-500 0 H500" ${SW} stroke-width="16"/>` + [[-500, p.sinistra, DG], [500, p.destra, PU]].map(([x, txt, c]) => tr(x, 60, 1, `<path d="M-170 0 h340 l-40 80 h-260z" fill="${GR}" ${SW}/>` + TF(0, 170, S(txt || ''), 90, 400, c, {}, 52), -tilt)).join(''), tilt);
};

// calendario del mese con i giorni accesi
TPL.calendario = (t, d, p, C) => {
  const n = Math.max(1, Math.min(31, +p.giorni || 25));
  let s = sfondo(C) + `<rect x="360" y="140" width="1200" height="760" rx="30" fill="#fff" ${SW}/><rect x="360" y="140" width="1200" height="110" rx="30" fill="${BL}" ${SW}/>` + TF(960, 215, S(p.titolo || 'UN MESE'), 56, 1120, '#fff');
  for (let i = 0; i < 30; i++) { const lit = i < n && pr(t, .4 + i * .04, .2) >= 1; s += `<rect x="${410 + (i % 7) * 160}" y="${290 + Math.floor(i / 7) * 120}" width="130" height="100" rx="14" fill="${lit ? G : '#F6F7FB'}" ${SW5}/>` + T(475 + (i % 7) * 160, 355 + Math.floor(i / 7) * 120, i + 1, 40, lit ? '#fff' : '#9AA3C0') }
  if (p.testo) s += label(1500, 920, pop(t, d * .6), S(p.testo), G, '#fff', 44);
  return s;
};

// soldi che escono verso chi li riceve
TPL.soldi = (t, d, p, C) => {
  const D = (p.destinazioni || []).slice(0, 4), pos = [[300, 230], [1620, 230], [300, 850], [1620, 850]];
  let s = sfondo(C) + note(760, 420, 400, 220, S(p.centro || ''), '#8FD18B', 60);
  D.forEach((n, i) => { const q = tappa(t, d, i, D.length); if (!q) return; const [x, y] = pos[i]; s += tr(x, y, q, label(0, 0, 1, S(n), '#fff', INK, 44)); const f = (t * .7 + i * .25) % 1; s += coin(lerp(960, x, f), lerp(530, y, f), .6, t * 200) });
  return s;
};

// indicatori (cruscotto)
TPL.cruscotto = (t, d, p, C) => {
  const V = (p.voci || []).slice(0, 4), n = V.length || 1;
  let s = BG(SCURI[C.i % SCURI.length]) + `<path d="M120 900 q840 -900 1680 0z" fill="#2E3550" ${SW}/>` + titoletto(p.titolo, t, 180, Y, INK);
  V.forEach((v, i) => { const on = tappa(t, d, i, n); const x = 960 + (i - (n - 1) / 2) * 400; s += tr(x, 620, 1, gauge(0, 0, .8, .15 + .6 * cl(on) * (+v.valore || .7), '', on > .5 ? COLS[i] : '#5A5F73') + TF(0, 80, S(v.nome || v), 38, 360, on > .5 ? '#fff' : '#5A5F73', {}, 28)) });
  return s;
};

// timbro grande su un oggetto (PERDITA, PIENO, PAREGGIO...)
TPL.timbro = (t, d, p, C) => sfondo(C) + oggetto(p.oggetto || C.oggetto, 960, 520, 2.2 * pop(t, 0, .5), t) + stamp(960, 520, pop(t, Math.min(1, d * .4)) * 1.1, S(p.testo || ''), p.colore === 'verde' ? G : R, -8) + (p.nota ? label(960, 900, pop(t, d * .6), S(p.nota), INK, '#fff', 50) : '');

// linea che sale o scende nel tempo
TPL.andamento = (t, d, p, C) => {
  const V = (p.valori || []).map(Number), n = V.length, mx = Math.max(...V, 1), mn = Math.min(...V, 0), g = E(pr(t, .3, Math.max(1.2, d * .6)));
  let s = sfondo(C) + `<rect x="200" y="200" width="1520" height="700" rx="30" fill="#fff" ${SW}/>` + titoletto(p.titolo, t, 130);
  const px = i => 280 + 1360 * i / Math.max(1, n - 1), py = v => 840 - 560 * (v - mn) / (mx - mn || 1);
  let path = ''; const k = g * (n - 1);
  for (let i = 0; i <= Math.floor(k); i++) path += `${i ? 'L' : 'M'}${px(i)} ${py(V[i])} `;
  if (k % 1 && Math.floor(k) + 1 < n) { const i = Math.floor(k), f = k - i; path += `L${lerp(px(i), px(i + 1), f)} ${lerp(py(V[i]), py(V[i + 1]), f)}` }
  s += `<path d="${path}" fill="none" stroke="${p.colore === 'rosso' ? R : G}" stroke-width="16" stroke-linecap="round" stroke-linejoin="round"/>`;
  (p.etichette || []).slice(0, n).forEach((e, i) => s += T(px(i), 890, S(e), 34, '#5A5F73'));
  return s;
};

// la fila di clienti (entrano, escono, aspettano)
TPL.persone = (t, d, p, C) => {
  const n = Math.max(1, Math.min(9, +p.n || 6)), az = p.azione || 'fila';
  let s = sfondo(C) + floor(860, '#D9DEE8');
  for (let i = 0; i < n; i++) { let x = 200 + i * (1520 / Math.max(1, n - 1 || 1)); if (az === 'escono' && i >= n - (+p.escono || 1)) x = lerp(x, 2200, E(pr(t, .6 + i * .1, 2))); if (az === 'entrano') x = lerp(-300, x, OUT(pr(t, i * .2, 1.6))); s += comparsa(C, i, x, 980, .6, t, { walk: az !== 'fila' }) }
  if (p.testo) s += label(960, 180, pop(t, .4), S(p.testo), BL, '#fff', 60);
  return s;
};

// orologio + ore della giornata che si riempiono
TPL.orologio = (t, d, p, C) => {
  const n = Math.max(1, Math.min(16, +p.ore || 10)), k = Math.min(n, Math.round((+p.piene || n) * E(pr(t, .4, d * .6))));
  let s = BG(SCURI[C.i % SCURI.length]) + clock(420, 520, 1.4, t * 3, 4);
  for (let i = 0; i < n; i++) s += tr(980 + (i % 4) * 220, 260 + Math.floor(i / 4) * 200, .85, rr(-90, -70, 180, 140, 24, i < k ? Y : '#2E3550') + T(0, 18, (8 + i) + ':00', 40, i < k ? INK : '#9AA3C0'));
  if (p.testo) s += label(1310, 960, pop(t, d * .6), S(p.testo), Y, INK, 50);
  return s;
};

// salvadanaio che si riempie o si svuota
TPL.salvadanaio = (t, d, p, C) => {
  const su = p.direzione !== 'svuota', f = su ? .1 + .8 * E(pr(t, .3, d * .7)) : .9 - .8 * E(pr(t, .3, d * .7));
  let s = sfondo(C) + piggy(960, 560, 1.6, f);
  if (su) for (let i = 0; i < 4; i++) { const g = (t * 1.2 + i / 4) % 1; s += coin(960 + (i - 1.5) * 60, lerp(140, 400, g), .7) }
  else for (let i = 0; i < 4; i++) { const g = (t * 1 + i / 4) % 1; s += coin(1200 + i * 60, lerp(600, 1000, g), .7) }
  if (p.testo) s += label(960, 160, pop(t, .3), S(p.testo), su ? G : R, '#fff', 58);
  return s;
};

// tre leve (prezzo, fornitore, costi fissi o altre)
TPL.leve = (t, d, p, C) => {
  const V = (p.voci || ['PREZZO', 'FORNITORE', 'COSTI FISSI']).slice(0, 4), n = V.length;
  let s = sfondo(C) + `<rect x="${960 - n * 210}" y="360" width="${n * 420}" height="520" rx="40" fill="#5A5F73" ${SW}/>` + TF(960, 300, S(p.titolo || 'LE LEVE'), 70, 1700, INK);
  V.forEach((v, i) => s += lever(960 + (i - (n - 1) / 2) * 400, 700, tappa(t, d, i, n), -20 + 20 * Math.sin(t * 2 + i) + (i === +p.evidenzia ? -30 : 0), S(v).toUpperCase(), COLS[i]));
  return s;
};

// riassunto finale: schede numerate
TPL.riepilogo = (t, d, p, C) => {
  const V = (p.voci || []).slice(0, 4), n = V.length || 1;
  let s = sfondo(C) + titoletto(p.titolo || 'DA RICORDARE', t, 140);
  // frase a capo per parole intere (mai tagliata a meta' parola): max 5 righe da ~15 caratteri
  const capo = v => { const r = ['']; String(v).split(/\s+/).forEach(w => { const l = r[r.length - 1]; if (l && (l + ' ' + w).length > 15) r.push(w); else r[r.length - 1] = l ? l + ' ' + w : w }); return r.slice(0, 5) };
  V.forEach((v, i) => { const x = 960 + (i - (n - 1) / 2) * 440, R = capo(v), fs = Math.min(R.length > 3 ? 38 : 44, ...R.map(l => fit(S(l), 44, 350))); s += card(x, 580, tappa(t, d, i, n), 400, 460, String(i + 1), R.map((l, k) => T(0, 20 + (k - (R.length - 1) / 2) * fs * 1.25, S(l), fs, INK)).join(''), COLS[i]) });
  return s;
};

// gancio al prossimo episodio
TPL.prossimo = (t, d, p, C) => {
  let s = luogo(p.luogo || 'negozio', t, C, p.insegna);
  s += comparsa(C, 2, 1300, 1000, 1, t, { mood: 'wow' }) + oggetto(p.oggetto || 'scatola', 700, 600, 1.2, t);
  s += tr(960, 280, pop(t, Math.min(d * .5, 2)), `<rect x="-560" y="-100" width="1120" height="200" rx="50" fill="${R}" ${SW}/>` + TF(0, 34, S(p.testo || 'NEL PROSSIMO EPISODIO'), 80, 1040, '#fff', {}, 56), -2);
  return s;
};

const TIPI = Object.keys(TPL);
