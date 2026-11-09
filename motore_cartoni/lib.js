// ===== LIBRERIA GRAFICA "quanto si guadagna davvero" — tutto disegnato in codice (costo zero)
const INK = '#1E2235', Y = '#FFC93C', G = '#2BB673', R = '#F2545B', BL = '#4C6FFF', PU = '#8E7CFF', OR = '#FFA24C', SK = '#F5C49B', SK2 = '#D9A679', SK3 = '#8D5A3B', GR = '#B8C1D9', WH = '#FFFFFF', DG = '#167A48';
const cl = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
const lerp = (a, b, x) => a + (b - a) * x;
const E = x => { x = cl(x); return x < .5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2 };
const OUT = x => { x = cl(x); return 1 - Math.pow(1 - x, 3) };
const BACK = x => { x = cl(x); const c1 = 1.9, c3 = c1 + 1; return 1 + c3 * Math.pow(x - 1, 3) + c1 * Math.pow(x - 1, 2) };
const pr = (t, a, d) => cl((t - a) / d);
const pop = (t, a, d = .45) => t < a ? 0 : BACK(pr(t, a, d));
const tr = (x, y, s, inner, r = 0) => `<g transform="translate(${x} ${y}) rotate(${r}) scale(${s})">${inner}</g>`;
const op = (o, inner) => `<g opacity="${cl(o)}">${inner}</g>`;
const T = (x, y, s, size, fill = INK, o = {}) => `<text x="${x}" y="${y}" font-size="${size}" font-weight="${o.w || 800}" fill="${fill}" text-anchor="${o.a || 'middle'}" ${o.st ? `stroke="${o.st}" stroke-width="${o.sw || 10}" paint-order="stroke" stroke-linejoin="round"` : ''} ${o.op !== undefined ? `opacity="${cl(o.op)}"` : ''}>${s}</text>`;
// 9 nov (Giorgio): ogni scritta deve stare DENTRO il suo riquadro. Larghezza misurata col carattere vero (canvas), poi si rimpicciolisce o si va a capo.
const _cx = (typeof document !== 'undefined') ? document.createElement('canvas').getContext('2d') : null;
const _un = v => String(v ?? '').replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>');
const larg = (txt, size, w = 800) => { if (_cx) { _cx.font = `${w} ${size}px B, Inter, sans-serif`; return _cx.measureText(_un(txt)).width * 1.03 } return _un(txt).length * size * .6 };
const fit = (txt, size, maxW, w = 800) => Math.max(14, Math.min(size, size * maxW / Math.max(1, larg(txt, size, w))));
// testo in un riquadro largo maxW: una riga se ci sta almeno a min, altrimenti due righe (a parole intere), mai fuori
function TF(x, y, txt, size, maxW, fill = INK, o = {}, min = size * .7) {
  const f1 = fit(txt, size, maxW, o.w || 800);
  const p = String(txt).split(' ');
  if (f1 >= min || p.length < 2) return T(x, y, txt, f1, fill, o);
  let best = null;
  for (let k = 1; k < p.length; k++) { const a = p.slice(0, k).join(' '), b = p.slice(k).join(' '), m = Math.max(larg(a, size), larg(b, size)); if (!best || m < best[2]) best = [a, b, m] }
  const fs = Math.min(size, fit(larg(best[0], size) > larg(best[1], size) ? best[0] : best[1], size, maxW, o.w || 800));
  return T(x, y - fs * .55, best[0], fs, fill, o) + T(x, y + fs * .55, best[1], fs, fill, o);
}
const SW = `stroke="${INK}" stroke-width="7" stroke-linejoin="round" stroke-linecap="round"`;
const SW5 = `stroke="${INK}" stroke-width="5" stroke-linejoin="round" stroke-linecap="round"`;
const num = (v, d = 0) => { const s = v.toFixed(d).split('.'); return s[0].replace(/\B(?=(\d{3})+(?!\d))/g, '.') + (d ? ',' + s[1] : '') };
const eur = (v, d = 2) => num(v, d) + ' €';
const BG = c => `<rect width="1920" height="1080" fill="${c}"/>`;
const floor = (y, c) => `<rect y="${y}" width="1920" height="${1080 - y}" fill="${c}"/><path d="M0 ${y} H1920" ${SW}/>`;
const rr = (x, y, w, h, r, f, extra = '') => `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${r}" fill="${f}" ${SW} ${extra}/>`;

// ----- PERSONAGGI (origine ai piedi, alti ~480 px a scala 1)
function person(o) {
  const t = o.t || 0, s = o.s || 1;
  const bob = (o.walk ? Math.abs(Math.sin(t * 9)) * -14 : Math.sin(t * 2.6 + (o.seed || 0)) * 4) + (o.jump ? -Math.abs(Math.sin(t * 7)) * 60 : 0);
  const skin = o.skin || SK, sh = o.shirt || BL, pants = o.pants || '#3A3F58';
  const step = o.walk ? Math.sin(t * 9) * 16 : 0;
  const aL = (o.aL ?? 8) + (o.walk ? Math.sin(t * 9) * 14 : 0) + (o.wave ? Math.sin(t * 8) * 25 : 0), aR = (o.aR ?? -8) - (o.walk ? Math.sin(t * 9) * 14 : 0);
  const blink = ((t + (o.seed || 0)) % 3.4) < .13, mood = o.mood || 'happy';
  let m = '';
  if (o.talk && Math.sin(t * 17) > -.2) m = `<ellipse cx="0" cy="-352" rx="16" ry="${8 + Math.abs(Math.sin(t * 17)) * 9}" fill="#7A2430" ${SW5}/>`;
  else if (mood === 'sad' || mood === 'worried') m = `<path d="M-20 -342 q20 -16 40 0" fill="none" ${SW} stroke-width="6"/>`;
  else if (mood === 'wow') m = `<ellipse cx="0" cy="-350" rx="13" ry="17" fill="#7A2430" ${SW5}/>`;
  else if (mood === 'calm') m = `<path d="M-16 -354 q16 10 32 0" fill="none" ${SW} stroke-width="6"/>`;
  else m = `<path d="M-24 -358 q24 26 48 0" fill="#fff" ${SW} stroke-width="6"/>`;
  const eye = x => blink ? `<path d="M${x - 10} -400 h20" ${SW} stroke-width="6"/>` : `<circle cx="${x}" cy="-400" r="11" fill="${INK}"/><circle cx="${x + 4}" cy="-404" r="3.5" fill="#fff"/>`;
  const brow = mood === 'worried' || mood === 'sad' ? `<path d="M-42 -432 l26 8 M42 -432 l-26 8" ${SW} stroke-width="6"/>` : mood === 'wow' ? `<path d="M-40 -440 q14 -10 28 0 M12 -440 q14 -10 28 0" fill="none" ${SW} stroke-width="6"/>` : '';
  const hc = o.hairC || '#5B3A29';
  let hair = '';
  if (o.hair === 'marco') hair = `<path d="M-72 -410 q-6 -86 72 -88 q80 2 74 88 q-14 -40 -40 -46 q-30 26 -106 46z" fill="${hc}" ${SW}/><path d="M-60 -372 q8 64 60 66 q52 -2 60 -66 q-10 30 -30 34 q-30 -14 -60 0 q-20 -4 -30 -34z" fill="${hc}" ${SW5}/>`;
  else if (o.hair === 'giulia') hair = `<path d="M70 -440 q70 10 60 120 q-20 -50 -50 -70z" fill="${hc}" ${SW}/><path d="M-74 -400 q-4 -98 74 -100 q80 2 76 100 q-20 -50 -76 -54 q-50 4 -74 54z" fill="${hc}" ${SW}/>`;
  else if (o.hair === 'cap') hair = `<path d="M-74 -420 q0 -78 74 -80 q76 2 76 80z" fill="${o.capC || R}" ${SW}/><path d="M40 -424 h80 q6 14 -10 18 h-70z" fill="${o.capC || R}" ${SW}/>`;
  else if (o.hair === 'bun') hair = `<circle cx="0" cy="-506" r="30" fill="${hc}" ${SW}/><path d="M-74 -404 q-2 -94 74 -96 q78 2 76 96 q-30 -46 -76 -48 q-46 2 -74 48z" fill="${hc}" ${SW}/>`;
  else if (o.hair === 'short') hair = `<path d="M-74 -404 q-6 -94 74 -96 q80 2 76 96 q-8 -34 -24 -44 q-50 10 -104 0 q-16 10 -22 44z" fill="${hc}" ${SW}/>`;
  else if (o.hair === 'long') hair = `<path d="M-80 -300 q-16 -200 80 -200 q96 0 80 200 q-20 -10 -24 -100 q-56 -40 -112 0 q-4 90 -24 100z" fill="${hc}" ${SW}/>`;
  else if (o.hair === 'curly') hair = [...Array(9)].map((_, i) => `<circle cx="${-70 + i * 17.5}" cy="${-456 - Math.sin(i / 8 * Math.PI) * 30}" r="26" fill="${hc}" ${SW5}/>`).join('');
  else if (o.hair === 'chef') hair = `<rect x="-62" y="-500" width="124" height="60" fill="#fff" ${SW}/><circle cx="-40" cy="-510" r="36" fill="#fff" ${SW}/><circle cx="0" cy="-526" r="40" fill="#fff" ${SW}/><circle cx="40" cy="-510" r="36" fill="#fff" ${SW}/><rect x="-60" y="-498" width="120" height="40" fill="#fff"/>`;
  else if (o.hair === 'bald') hair = `<path d="M-74 -390 q-6 -30 6 -44 M74 -390 q6 -30 -6 -44" fill="none" stroke="${hc}" stroke-width="14" stroke-linecap="round"/>`;
  const glasses = o.glasses ? `<circle cx="-26" cy="-400" r="22" fill="none" ${SW5}/><circle cx="26" cy="-400" r="22" fill="none" ${SW5}/><path d="M-4 -402 h8" ${SW5}/>` : '';
  const shades = o.shades ? `<path d="M-52 -414 h104 v20 q-10 22 -40 18 q-12 -16 -12 -16 q-12 0 -12 0 q0 0 -12 16 q-30 4 -40 -18z" fill="${INK}"/>` : '';
  const apron = o.apron ? `<path d="M-58 -300 h116 v170 q-58 20 -116 0z" fill="${o.apron}" ${SW} stroke-width="6"/><path d="M-30 -230 h60" ${SW5}/>` : '';
  const tie = o.tie ? `<path d="M0 -326 l-14 14 l14 110 l14 -110z" fill="${o.tie}" ${SW5}/>` : '';
  const arm = (x, a, held) => `<g transform="translate(${x} -300) rotate(${a})"><rect x="-21" y="-6" width="42" height="150" rx="21" fill="${sh}" ${SW}/><circle cx="0" cy="156" r="25" fill="${skin}" ${SW}/>${held || ''}</g>`;
  const sweat = o.sweat ? `<path d="M80 -440 q14 24 0 34 q-14 -10 0 -34z" fill="#7CC4FF" ${SW5} transform="translate(0 ${(t * 60) % 40})"/>` : '';
  return tr(o.x, o.y + bob, s, `
    <ellipse cx="0" cy="${-bob / s}" rx="110" ry="18" fill="#000" opacity=".10"/>
    <rect x="${-52 + step}" y="-150" width="44" height="150" rx="20" fill="${pants}" ${SW}/>
    <rect x="${8 - step}" y="-150" width="44" height="150" rx="20" fill="${pants}" ${SW}/>
    <ellipse cx="${-34 + step}" cy="-4" rx="34" ry="16" fill="${INK}"/><ellipse cx="${34 - step}" cy="-4" rx="34" ry="16" fill="${INK}"/>
    ${arm(-78, aL, o.heldL)}
    <rect x="-82" y="-330" width="164" height="200" rx="52" fill="${sh}" ${SW}/>
    ${apron}${tie}
    ${arm(78, aR, o.heldR)}
    <rect x="-18" y="-344" width="36" height="24" fill="${skin}"/>
    ${o.hair === 'long' ? hair : ''}
    <circle cx="0" cy="-396" r="74" fill="${skin}" ${SW}/>
    <circle cx="-74" cy="-392" r="14" fill="${skin}" ${SW5}/><circle cx="74" cy="-392" r="14" fill="${skin}" ${SW5}/>
    ${o.hair !== 'long' ? hair : ''}${eye(-26)}${eye(26)}${brow}${glasses}${shades}
    <circle cx="-44" cy="-366" r="12" fill="#FF8C8C" opacity=".45"/><circle cx="44" cy="-366" r="12" fill="#FF8C8C" opacity=".45"/>
    ${m}${sweat}`);
}
const MARCO = (x, y, s, t, e = {}) => person(Object.assign({ x, y, s, t, hair: 'marco', shirt: '#3BAFDA', apron: G, seed: 0 }, e));
const GIULIA = (x, y, s, t, e = {}) => person(Object.assign({ x, y, s, t, hair: 'giulia', hairC: '#2B1B14', skin: SK2, shirt: '#FFFFFF', apron: R, seed: 1.3 }, e));
const CLIENTI = [
  { hair: 'cap', capC: PU, shirt: '#FF9F43', pants: '#2F5D9B' }, { hair: 'long', hairC: '#E0A33A', shirt: '#FF7FB6', pants: '#5A3E8E' },
  { hair: 'curly', hairC: '#2B1B14', skin: SK3, shirt: G, pants: '#3A3F58' }, { hair: 'short', hairC: '#9A9A9A', shirt: '#9B6BD6', pants: '#3A3F58', glasses: true },
  { hair: 'bun', hairC: '#8B4A2B', shirt: Y, pants: '#2F5D9B' }, { hair: 'cap', capC: G, skin: SK2, shirt: R, pants: '#3A3F58' }, { hair: 'bald', hairC: '#5B3A29', shirt: '#4CC9F0', pants: '#5A5F73' }];
const cliente = (i, x, y, s, t, e = {}) => person(Object.assign({ x, y, s, t, seed: i * .7 }, CLIENTI[i % CLIENTI.length], e));

// ----- OGGETTI
const tee = (x, y, s, c, r = 0) => tr(x, y, s, `<path d="M-60 -70 h36 q24 22 48 0 h36 l50 40 -26 36 -26 -16 v100 h-120 v-100 l-26 16 -26 -36z" fill="${c}" ${SW}/><path d="M-24 -70 q24 22 48 0" fill="none" ${SW5}/>`, r);
const tag = (x, y, s, label, c = '#fff', r = 0, tc = INK) => { const w = larg(label, 74) + 40; return tr(x, y, s, `<path d="M-6 -70 l60 -10 l${w} 0 q20 0 20 20 v120 q0 20 -20 20 h-${w} l-60 -10 l-40 -70z" fill="${c}" ${SW}/><circle cx="2" cy="0" r="12" fill="#fff" ${SW5}/>${T(64 + w / 2, 26, label, 74, tc)}`, r) };
const note = (x, y, w, h, label, c = '#8FD18B', ls = 110) => `<g><rect x="${x}" y="${y}" width="${w}" height="${h}" rx="22" fill="${c}" ${SW}/><rect x="${x + 22}" y="${y + 22}" width="${Math.max(0, w - 44)}" height="${Math.max(0, h - 44)}" rx="14" fill="none" stroke="#fff" stroke-width="6" stroke-dasharray="2 14" opacity=".8"/>${label ? T(x + w / 2, y + h / 2 + ls * .35, label, ls, INK) : ''}</g>`;
const coin = (x, y, s, r = 0) => tr(x, y, s, `<circle r="34" fill="${Y}" ${SW} stroke-width="6"/><circle r="20" fill="none" stroke="#E0A800" stroke-width="5"/>${T(0, 12, '€', 34, '#9A6B00')}`, r);
const coinStack = (x, y, n, s = 1) => tr(x, y, s, [...Array(n)].map((_, i) => `<ellipse cx="0" cy="${-i * 16}" rx="50" ry="16" fill="${Y}" ${SW5}/>`).join(''));
const bubble = (x, y, w, h, inner, s = 1) => tr(x, y, s, `<rect x="${-w / 2}" y="${-h / 2}" width="${w}" height="${h}" rx="60" fill="#fff" ${SW}/><path d="M-40 ${h / 2 - 4} l-30 70 l90 -66z" fill="#fff" ${SW}/><rect x="-60" y="${h / 2 - 16}" width="100" height="22" fill="#fff"/>${inner}`);
const label = (x, y, s, txt, bg = INK, fg = '#fff', size = 54, r = 0) => { size = fit(txt, size, 1760); const w = larg(txt, size) + 64; return tr(x, y, s, `<rect x="${-w / 2}" y="-${size * .85}" width="${w}" height="${size * 1.5}" rx="${size * .5}" fill="${bg}" ${SW} stroke-width="6"/>${T(0, size * .32, txt, size, fg)}`, r) };
const spark = (x, y, s, t) => tr(x, y, s, `<path d="M0 -40 L10 -10 L40 0 L10 10 L0 40 L-10 10 L-40 0 L-10 -10z" fill="${Y}" ${SW} stroke-width="4"/>`, t * 90);
const stato = (x, y, s) => tr(x, y, s, `<path d="M-200 -250 L0 -360 L200 -250z" fill="#E6E8F0" ${SW}/><rect x="-200" y="-250" width="400" height="34" fill="#E6E8F0" ${SW}/>${[-150, -75, 0, 75, 150].map(c => `<rect x="${c - 22}" y="-216" width="44" height="190" fill="#fff" ${SW} stroke-width="6"/>`).join('')}<rect x="-230" y="-26" width="460" height="40" fill="#E6E8F0" ${SW}/>${T(0, -272, 'STATO', 46, INK)}<rect x="-6" y="-470" width="10" height="112" fill="${INK}"/><rect x="4" y="-470" width="34" height="56" fill="${G}" ${SW} stroke-width="4"/><rect x="38" y="-470" width="34" height="56" fill="#fff" ${SW} stroke-width="4"/><rect x="72" y="-470" width="34" height="56" fill="${R}" ${SW} stroke-width="4"/>`);
const truck = (x, y, s, t, txt = 'FORNITORE', c = OR) => tr(x, y, s, `<rect x="-260" y="-260" width="330" height="210" rx="16" fill="#fff" ${SW}/>${T(-95, -140, txt, 46, INK)}<path d="M70 -200 h110 l70 80 v70 h-180z" fill="${c}" ${SW}/><rect x="110" y="-184" width="70" height="56" rx="8" fill="#CDEBFF" ${SW5}/>${[-170, 160].map(cx => tr(cx, -40, 1, `<circle r="48" fill="${INK}"/><circle r="20" fill="${GR}"/><path d="M0 -20 v40" stroke="${INK}" stroke-width="6"/>`, t * 300)).join('')}`);
const box = (x, y, s, c = '#C98A4B', r = 0) => tr(x, y, s, `<rect x="-70" y="-70" width="140" height="140" rx="10" fill="${c}" ${SW}/><path d="M-70 -20 h140 M-10 -70 v50" ${SW5}/>`, r);
const house = (x, y, s) => tr(x, y, s, `<path d="M-90 -10 L0 -100 L90 -10z" fill="${R}" ${SW}/><rect x="-70" y="-10" width="140" height="110" fill="#fff" ${SW}/><rect x="-22" y="40" width="44" height="60" fill="${OR}" ${SW5}/>`);
const bulb = (x, y, s, t) => tr(x, y, s, `<circle cx="0" cy="-20" r="70" fill="${Y}" opacity="${.25 + .2 * Math.sin(t * 8)}"/><path d="M-46 -30 a46 46 0 1 1 92 0 q0 30 -22 50 v24 h-48 v-24 q-22 -20 -22 -50z" fill="${Y}" ${SW}/><rect x="-24" y="44" width="48" height="30" rx="8" fill="${GR}" ${SW5}/>`);
const cup = (x, y, s, c = '#fff') => tr(x, y, s, `<path d="M-60 -60 h120 l-12 90 q-48 22 -96 0z" fill="${c}" ${SW}/><path d="M58 -40 q46 0 34 38 q-10 22 -40 18" fill="none" ${SW}/><ellipse cx="0" cy="-60" rx="60" ry="14" fill="#6B3E26" ${SW5}/><ellipse cx="0" cy="44" rx="90" ry="12" fill="#fff" ${SW5}/>`);
const calendar = (x, y, s, top = 'OGNI MESE', big = '30', c = R) => tr(x, y, s, `<rect x="-130" y="-130" width="260" height="260" rx="24" fill="#fff" ${SW}/><rect x="-130" y="-130" width="260" height="70" rx="24" fill="${c}" ${SW}/>${T(0, -78, top, 38, '#fff')}${T(0, 70, big, 120, INK)}`);
const shelf = (x, y, w) => `<rect x="${x}" y="${y}" width="${w}" height="22" rx="6" fill="#C98A4B" ${SW} stroke-width="6"/>`;
const register = (x, y, s, val) => tr(x, y, s, `<rect x="-110" y="-80" width="220" height="140" rx="18" fill="#5A5F73" ${SW}/><rect x="-84" y="-60" width="168" height="54" rx="8" fill="#9BE3B3" ${SW5}/>${T(0, -20, val, 40, INK)}${[...Array(6)].map((_, i) => `<rect x="${-80 + (i % 3) * 56}" y="${8 + Math.floor(i / 3) * 24}" width="44" height="16" rx="4" fill="#fff"/>`).join('')}<rect x="-130" y="60" width="260" height="40" rx="8" fill="#3A3F58" ${SW5}/>`);
const phone = (x, y, s, inner) => tr(x, y, s, `<rect x="-160" y="-300" width="320" height="600" rx="44" fill="${INK}"/><rect x="-140" y="-270" width="280" height="540" rx="26" fill="#fff"/>${inner}`);
const magnifier = (x, y, s, r = 0) => tr(x, y, s, `<rect x="70" y="60" width="40" height="160" rx="16" fill="#8B5A2B" ${SW} transform="rotate(-40 90 140)"/><circle r="110" fill="#CDEBFF" fill-opacity=".45" ${SW} stroke-width="14"/>`, r);
const card = (x, y, s, w, h, title, icon, c) => tr(x, y, s, `<rect x="${-w / 2}" y="${-h / 2}" width="${w}" height="${h}" rx="30" fill="#fff" ${SW}/><rect x="${-w / 2}" y="${-h / 2}" width="${w}" height="70" rx="30" fill="${c}" ${SW}/><rect x="${-w / 2 + 4}" y="${-h / 2 + 40}" width="${w - 8}" height="30" fill="${c}"/>${TF(0, -h / 2 + 50, title, 38, w - 40, '#fff', {}, 30)}${icon}`);
const calculator = (x, y, s, val = '') => tr(x, y, s, `<rect x="-130" y="-190" width="260" height="380" rx="30" fill="#3A3F58" ${SW}/><rect x="-100" y="-160" width="200" height="80" rx="12" fill="#9BE3B3" ${SW5}/>${T(84, -100, val, 48, INK, { a: 'end' })}${[...Array(12)].map((_, i) => `<rect x="${-100 + (i % 3) * 70}" y="${-60 + Math.floor(i / 3) * 60}" width="56" height="46" rx="10" fill="${i % 3 === 2 ? OR : '#fff'}" ${SW5}/>`).join('')}`);
const clock = (x, y, s, t, sp = 1) => tr(x, y, s, `<circle r="150" fill="#fff" ${SW} stroke-width="10"/>${[...Array(12)].map((_, i) => `<path d="M0 -130 v18" ${SW5} transform="rotate(${i * 30})"/>`).join('')}<path d="M0 0 V-90" ${SW} stroke-width="12" transform="rotate(${t * 30 * sp})"/><path d="M0 0 V-120" stroke="${R}" stroke-width="8" stroke-linecap="round" transform="rotate(${t * 360 * sp})"/><circle r="12" fill="${INK}"/>`);
const arrow = (x1, y1, x2, y2, c = INK, w = 10) => { const a = Math.atan2(y2 - y1, x2 - x1), h = 34; return `<path d="M${x1} ${y1} L${x2} ${y2}" stroke="${c}" stroke-width="${w}" stroke-linecap="round"/><path d="M${x2} ${y2} L${x2 - h * Math.cos(a - .5)} ${y2 - h * Math.sin(a - .5)} M${x2} ${y2} L${x2 - h * Math.cos(a + .5)} ${y2 - h * Math.sin(a + .5)}" stroke="${c}" stroke-width="${w}" stroke-linecap="round"/>` };
const donut = (x, y, r, frac, c, w = 60, bg = '#E6E8F0') => { const C = 2 * Math.PI * r; return `<g transform="translate(${x} ${y}) rotate(-90)"><circle r="${r}" fill="none" stroke="${INK}" stroke-width="${w + 14}"/><circle r="${r}" fill="none" stroke="${bg}" stroke-width="${w}"/><circle r="${r}" fill="none" stroke="${c}" stroke-width="${w}" stroke-dasharray="${C * cl(frac)} ${C}"/></g>` };
const letter = (x, y, s, title, amount, r = 0) => tr(x, y, s, `<rect x="-200" y="-140" width="400" height="280" rx="16" fill="#fff" ${SW}/><path d="M-200 -140 L0 10 L200 -140" fill="none" ${SW}/>${T(0, 70, title, 34, INK)}${T(0, 125, amount, 52, R)}`, r);
const bill = (x, y, s, title, amount, r = 0, c = '#FFF7D6') => tr(x, y, s, `<path d="M-150 -200 h300 v380 l-25 20 -25 -20 -25 20 -25 -20 -25 20 -25 -20 -25 20 -25 -20 -25 20 -25 -20 -25 20 -25 -20z" fill="${c}" ${SW}/>${TF(0, -130, title, 44, 250, INK)}<path d="M-110 -80 h220 M-110 -30 h160 M-110 20 h200" stroke="${GR}" stroke-width="10" stroke-linecap="round"/>${T(0, 120, amount, 60, R)}`, r);
const laptop = (x, y, s, inner = '') => tr(x, y, s, `<rect x="-300" y="-380" width="600" height="380" rx="24" fill="${INK}"/><rect x="-276" y="-356" width="552" height="332" rx="10" fill="#fff"/>${inner}<path d="M-360 0 h720 l-40 40 h-640z" fill="${GR}" ${SW}/>`);
const bag = (x, y, s, c = R) => tr(x, y, s, `<path d="M-60 -60 h120 l14 130 h-148z" fill="${c}" ${SW}/><path d="M-30 -60 q0 -50 30 -50 q30 0 30 50" fill="none" ${SW}/>`);
const pos = (x, y, s) => tr(x, y, s, `<rect x="-60" y="-100" width="120" height="200" rx="18" fill="#3A3F58" ${SW}/><rect x="-42" y="-80" width="84" height="60" rx="8" fill="#9BE3B3" ${SW5}/>${[...Array(9)].map((_, i) => `<rect x="${-42 + (i % 3) * 30}" y="${0 + Math.floor(i / 3) * 28}" width="22" height="18" rx="4" fill="#fff"/>`).join('')}`);
const labelTag = (x, y, s) => tr(x, y, s, `<rect x="-70" y="-44" width="140" height="88" rx="10" fill="#fff" ${SW}/><path d="M-50 -10 h100 M-50 14 h60" stroke="${GR}" stroke-width="10" stroke-linecap="round"/><path d="M-70 0 h-40" ${SW}/>`);
const sun = (x, y, s, t) => tr(x, y, s, `${[...Array(12)].map((_, i) => `<path d="M0 -120 v-50" stroke="${OR}" stroke-width="16" stroke-linecap="round" transform="rotate(${i * 30 + t * 20})"/>`).join('')}<circle r="100" fill="${Y}" ${SW}/>`);
const snow = (t, n = 40, c = '#fff') => [...Array(n)].map((_, i) => { const x = (i * 197) % 1920, y = ((t * 80 + i * 131) % 1100) - 20; return `<circle cx="${x + Math.sin(t + i) * 20}" cy="${y}" r="${6 + (i % 4) * 3}" fill="${c}"/>` }).join('');
const cone = (x, y, s, c1 = '#FF9EC4', c2 = '#9BE3B3') => tr(x, y, s, `<path d="M-50 0 L0 140 L50 0z" fill="#E8B97A" ${SW}/><circle cx="-20" cy="-30" r="44" fill="${c1}" ${SW}/><circle cx="24" cy="-30" r="44" fill="${c2}" ${SW}/><circle cx="0" cy="-80" r="44" fill="#FFE7A8" ${SW}/>`);
const piggy = (x, y, s, fill = 0) => tr(x, y, s, `<ellipse cx="0" cy="0" rx="170" ry="130" fill="#FF9EC4" ${SW}/><clipPath id="pg${Math.round(x)}"><ellipse cx="0" cy="0" rx="166" ry="126"/></clipPath><rect x="-170" y="${130 - 260 * cl(fill)}" width="340" height="260" fill="${Y}" opacity=".85" clip-path="url(#pg${Math.round(x)})"/><ellipse cx="160" cy="0" rx="34" ry="44" fill="#FF7FB6" ${SW}/><circle cx="90" cy="-50" r="12" fill="${INK}"/><path d="M-60 -126 l20 -40 l30 30" fill="#FF7FB6" ${SW}/><rect x="-40" y="-140" width="80" height="16" rx="8" fill="${INK}"/><rect x="-110" y="110" width="44" height="60" rx="14" fill="#FF7FB6" ${SW}/><rect x="60" y="110" width="44" height="60" rx="14" fill="#FF7FB6" ${SW}/>`);
const bread = (x, y, s, r = 0) => tr(x, y, s, `<path d="M-90 30 q-10 -90 90 -90 q100 0 90 90z" fill="#E09A4A" ${SW}/><path d="M-40 -40 l-14 40 M0 -50 l-14 40 M40 -40 l-14 40" ${SW5}/>`, r);
const postit = (x, y, s, txt, r = 0) => tr(x, y, s, `<rect x="-110" y="-110" width="220" height="220" fill="#FFF07A" ${SW}/><rect x="-40" y="-130" width="80" height="34" fill="#9BE3B3" opacity=".8"/>${T(0, 50, txt, 140, INK)}`, r);
const balloon = (x, y, s, txt, c = R, popped = 0) => popped >= 1 ? '' : tr(x, y, s * (1 + popped * .4), `<path d="M0 230 q-20 60 10 120" fill="none" ${SW5}/><ellipse cx="0" cy="0" rx="${240}" ry="${230}" fill="${c}" ${SW}/><path d="M-12 226 h24 l-12 -14z" fill="${c}" ${SW5}/>${T(0, 26, txt, 76, '#fff')}`);
const diamond = (x, y, s, t) => tr(x, y, s, `<path d="M-90 -40 L-50 -90 H50 L90 -40 L0 80z" fill="#7CE8FF" ${SW}/><path d="M-90 -40 H90 M-50 -90 L-20 -40 L0 80 L20 -40 L50 -90" fill="none" ${SW5}/>`, Math.sin(t * 2) * 8);
const safe = (x, y, s, open = 0) => tr(x, y, s, `<rect x="-160" y="-160" width="320" height="320" rx="24" fill="#5A5F73" ${SW}/><rect x="-130" y="-130" width="260" height="260" rx="14" fill="#3A3F58" ${SW5}/><g transform="rotate(${open * 200})"><circle r="56" fill="${GR}" ${SW}/><path d="M0 -40 v80 M-40 0 h80" ${SW}/></g>`);
const gauge = (x, y, s, v, title, c = G) => tr(x, y, s, `<path d="M-150 0 A150 150 0 0 1 150 0" fill="none" stroke="${INK}" stroke-width="54"/><path d="M-150 0 A150 150 0 0 1 150 0" fill="none" stroke="#E6E8F0" stroke-width="40"/><path d="M-150 0 A150 150 0 0 1 ${-150 * Math.cos(Math.PI * cl(v))} ${-150 * Math.sin(Math.PI * cl(v))}" fill="none" stroke="${c}" stroke-width="40"/><path d="M0 0 L${-120 * Math.cos(Math.PI * cl(v))} ${-120 * Math.sin(Math.PI * cl(v))}" ${SW} stroke-width="12"/><circle r="18" fill="${INK}"/>${T(0, 70, title, 40, INK)}`);
const scissors = (x, y, s, open) => tr(x, y, s, `<g transform="rotate(${-open * 20})"><path d="M0 0 L180 -12 L180 8z" fill="${GR}" ${SW5}/><circle cx="-50" cy="-30" r="34" fill="none" stroke="${R}" stroke-width="14"/></g><g transform="rotate(${open * 20})"><path d="M0 0 L180 12 L180 -8z" fill="${GR}" ${SW5}/><circle cx="-50" cy="30" r="34" fill="none" stroke="${R}" stroke-width="14"/></g><circle r="10" fill="${INK}"/>`);
const megaphone = (x, y, s) => tr(x, y, s, `<path d="M-80 -40 L60 -110 V110 L-80 40z" fill="${R}" ${SW}/><rect x="-120" y="-44" width="50" height="88" rx="12" fill="${GR}" ${SW}/><path d="M90 -60 q30 60 0 120 M120 -90 q50 90 0 180" fill="none" ${SW}/>`);
const creditCard = (x, y, s) => tr(x, y, s, `<rect x="-140" y="-90" width="280" height="180" rx="20" fill="${BL}" ${SW}/><rect x="-140" y="-50" width="280" height="36" fill="${INK}"/><rect x="-110" y="20" width="60" height="40" rx="8" fill="${Y}" ${SW5}/>`);
const bottle = (x, y, s, c = '#9BE3B3') => tr(x, y, s, `<rect x="-60" y="-120" width="120" height="200" rx="30" fill="${c}" ${SW}/><rect x="-30" y="-170" width="60" height="54" rx="10" fill="${PU}" ${SW}/><rect x="-40" y="-50" width="80" height="70" rx="10" fill="#fff" ${SW5}/>`);
const lever = (x, y, s, ang, txt, c) => tr(x, y, s, `<rect x="-60" y="0" width="120" height="60" rx="14" fill="#5A5F73" ${SW}/><g transform="rotate(${ang})"><rect x="-12" y="-200" width="24" height="200" rx="10" fill="${GR}" ${SW5}/><circle cx="0" cy="-200" r="40" fill="${c}" ${SW}/></g>${T(0, 120, txt, 40, INK)}`);
const wheel = (x, y, s, r) => tr(x, y, s, `<circle r="140" fill="none" stroke="#8B5A2B" stroke-width="30"/><circle r="140" fill="none" ${SW}/>${[...Array(8)].map((_, i) => `<g transform="rotate(${i * 45})"><rect x="-10" y="-200" width="20" height="200" fill="#8B5A2B" ${SW5}/><circle cy="-200" r="20" fill="#8B5A2B" ${SW5}/></g>`).join('')}<circle r="40" fill="${Y}" ${SW}/>`, r);
const tumbleweed = (x, y, s, t) => tr(x, y, s, [...Array(6)].map((_, i) => `<circle r="${60 - i * 8}" fill="none" stroke="#B88A4A" stroke-width="6" transform="rotate(${i * 30})" cx="${i * 3}"/>`).join(''), t * 200);
const fly = (x, y, t, i) => `<g transform="translate(${x + Math.sin(t * 5 + i) * 40} ${y + Math.cos(t * 7 + i) * 30})"><ellipse cx="-10" cy="-10" rx="12" ry="8" fill="#fff" ${SW5} opacity=".9"/><ellipse cx="10" cy="-10" rx="12" ry="8" fill="#fff" ${SW5} opacity=".9"/><circle r="10" fill="${INK}"/></g>`;
const confetti = (t, n = 50) => [...Array(n)].map((_, i) => { const x = (i * 173) % 1920, y = ((t * 300 + i * 97) % 1200) - 60; return `<rect x="${x}" y="${y}" width="18" height="30" fill="${[R, Y, G, BL, PU, OR][i % 6]}" transform="rotate(${t * 200 + i * 30} ${x + 9} ${y + 15})"/>` }).join('');
const moon = (x, y, s) => tr(x, y, s, `<circle r="90" fill="#FFF3B0" ${SW}/><circle cx="40" cy="-30" r="80" fill="#2A3366"/>`);
const stars = (t) => [...Array(30)].map((_, i) => `<circle cx="${(i * 263) % 1920}" cy="${(i * 97) % 500}" r="${3 + (i % 3) * 2}" fill="#fff" opacity="${.4 + .4 * Math.sin(t * 3 + i)}"/>`).join('');
const tick = (x, y, s) => tr(x, y, s, `<circle r="60" fill="${G}" ${SW}/><path d="M-28 0 l18 22 l36 -40" fill="none" stroke="#fff" stroke-width="16" stroke-linecap="round" stroke-linejoin="round"/>`);
const cross = (x, y, s) => tr(x, y, s, `<circle r="60" fill="${R}" ${SW}/><path d="M-24 -24 l48 48 M24 -24 l-48 48" stroke="#fff" stroke-width="16" stroke-linecap="round"/>`);
const stamp = (x, y, s, txt, c = R, r = -10) => { const fs = fit(txt, 100, 1200), w = larg(txt, fs) + 90; return tr(x, y, s, `<rect x="${-w / 2}" y="-80" width="${w}" height="150" rx="20" fill="none" stroke="${c}" stroke-width="14"/>` + T(0, fs * .34, txt, fs, c), r) };
const chip = (x, y, s, txt, c, icon = '') => label(x, y, s, txt, c, INK, 44);
// barra del prezzo diviso in fette
function barra(parts, y = 900, x = 260, W = 1400, tot = 20) {
  let out = `<rect x="${x}" y="${y}" width="${W}" height="90" rx="26" fill="#fff" ${SW}/>`, cx = x;
  for (const p of parts) {
    const w = W * p.v / tot * cl(p.f); if (w < 2) continue;
    out += `<rect x="${cx}" y="${y}" width="${w}" height="90" rx="20" fill="${p.c}" ${SW} stroke-width="6"/>`;
    if (p.f > .7) out += T(cx + w / 2, y + 62, p.l, 44, INK, { op: (p.f - .7) / .3 });
    cx += w;
  }
  return out;
}
// grafico del punto di pareggio (costi fissi F, margine m per pezzo)
function pareggio(o) {
  const C = Object.assign({ x0: 260, y0: 860, w: 1300, h: 620, xm: 500, ym: 5000, F: 3000, m: 9.4 }, o);
  const px = v => C.x0 + C.w * v / C.xm, py = e => C.y0 - C.h * e / C.ym, xb = C.F / C.m;
  let sc = `<rect x="${C.x0 - 40}" y="${C.y0 - C.h - 60}" width="${C.w + 100}" height="${C.h + 140}" rx="30" fill="#fff" ${SW}/><path d="M${C.x0} ${C.y0 - C.h} V${C.y0} H${C.x0 + C.w}" fill="none" ${SW}/>`;
  for (const v of [100, 200, 300, 400, 500]) if (Math.abs(v - xb) > 40) sc += T(px(v), C.y0 + 50, v, 36, '#5A5F73', { w: 600 });
  sc += T(C.x0 + C.w - 10, C.y0 - 20, C.unit || 'magliette vendute', 34, '#5A5F73', { a: 'end', w: 600 });
  if (C.loss > 0) sc += `<path d="M${px(0)} ${py(C.F)} L${px(xb)} ${py(C.F)} L${px(0)} ${py(0)}z" fill="${R}" opacity="${.22 * cl(C.loss)}"/>` + T(px(xb * .33), py(C.F * .78), 'PERDITA', 54, R, { op: C.loss });
  if (C.gain > 0) { const xe = C.xm, ye = Math.min(C.ym, xe * C.m); sc += `<path d="M${px(xb)} ${py(C.F)} L${px(xe)} ${py(C.F)} L${px(xe)} ${py(ye)}z" fill="${G}" opacity="${.3 * cl(C.gain)}"/>` + T(px(xb + (xe - xb) * .62), py(C.F + (ye - C.F) * .3), 'GUADAGNO', 52, DG, { op: C.gain }) }
  if (C.red > 0) sc += `<path d="M${px(0)} ${py(C.F)} H${px(C.xm * cl(C.red))}" stroke="${R}" stroke-width="14" stroke-linecap="round"/>` + T(px(8), py(C.F) - 26, 'costi fissi ' + eur(C.F, 0), 40, R, { a: 'start', op: C.red * 2 });
  if (C.green > 0) { const v = C.xm * cl(C.green); sc += `<path d="M${px(0)} ${py(0)} L${px(v)} ${py(v * C.m)}" stroke="${G}" stroke-width="16" stroke-linecap="round"/>` + tr(px(v), py(v * C.m), 1, C.icon ? C.icon : tee(0, -10, .32, Y)) }
  if (C.mark > 0) { const r = 26 + 8 * Math.sin((C.t || 0) * 6); sc += `<path d="M${px(xb)} ${py(C.F)} V${C.y0}" stroke="${INK}" stroke-width="6" stroke-dasharray="14 12"/><circle cx="${px(xb)}" cy="${py(C.F)}" r="${r * cl(C.mark)}" fill="${Y}" ${SW}/>` + tr(px(xb), C.y0 + 50, cl(C.mark), `<rect x="-66" y="-38" width="132" height="54" rx="14" fill="${Y}" ${SW5}/>` + T(0, 4, Math.ceil(xb - 1e-6), 40, INK)) }
  return sc;
}
// bancone di un negozio
const counter = (x, y, w, c = '#B87333', top = '#D9955A') => `<rect x="${x}" y="${y}" width="${w}" height="${1000 - y}" rx="18" fill="${c}" ${SW}/><rect x="${x - 20}" y="${y - 20}" width="${w + 40}" height="40" rx="14" fill="${top}" ${SW} stroke-width="6"/>`;
const shopFront = (x, y, w, h, name, c, open = true) => `<rect x="${x}" y="${y}" width="${w}" height="${h}" fill="${c}" ${SW}/><rect x="${x + 30}" y="${y + 130}" width="${w * .55}" height="${h - 160}" rx="10" fill="#CDEBFF" ${SW}/><rect x="${x + w * .65}" y="${y + 150}" width="${w * .28}" height="${h - 150}" rx="8" fill="#8B5A2B" ${SW}/><rect x="${x - 10}" y="${y}" width="${w + 20}" height="100" rx="12" fill="${INK}"/>${T(x + w / 2, y + 70, name, 54, Y)}${[...Array(Math.floor(w / 80))].map((_, i) => `<path d="M${x + i * 80} ${y + 100} q40 50 80 0" fill="${i % 2 ? '#fff' : R}" ${SW5}/>`).join('')}`;
