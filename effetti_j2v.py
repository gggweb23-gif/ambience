#!/usr/bin/env python3
"""EFFETTI COME JSON2VIDEO, GRATIS SU GITHUB (colonna effetti_github = SI).

n8n prepara gia' gli elementi json2video di ogni scena (grafici HTML animati, foto in cornice, titoli delle scene
tipografiche, cifre in dollari, suoni). Qui li disegniamo con lo stesso browser (Chromium) che usa json2video:
stesso HTML, stesso CSS, stesse animazioni, stesse posizioni. Risultato identico, costo zero.

Elementi gestiti (formato json2video):
  - "html"  : pagina HTML in un riquadro (x, y, width, height), con start/duration, animazioni CSS comprese
  - "text"  : testo con le impostazioni CSS di json2video (settings), con start/duration
  - "video" : clip che copre la scena da "start" in poi (typo_fast_cut)
  - scena con background-color + primo elemento html = foto in cornice
  - "audio" : suoni della scena (cornice, cassa, ...), mixati nell'audio finale
"""
import html as H_
import json
import os
import re
import subprocess

W, H, FPS = 1920, 1080, 30
ANIM_SEC = 0.9          # durata delle animazioni CSS dei grafici (pop/crescita): fotogrammi fitti per questo tempo
_pw = {'p': None, 'b': None, 'page': None}


def log(*a):
    print('[effetti]', *a, flush=True)


def _pagina():
    if _pw['page'] is None:
        from playwright.sync_api import sync_playwright
        _pw['p'] = sync_playwright().start()
        _pw['b'] = _pw['p'].chromium.launch(args=['--force-color-profile=srgb', '--font-render-hinting=none'])
        _pw['page'] = _pw['b'].new_page(viewport={'width': W, 'height': H}, device_scale_factor=1)
    return _pw['page']


def chiudi():
    try:
        if _pw['b']:
            _pw['b'].close()
        if _pw['p']:
            _pw['p'].stop()
    except Exception:
        pass
    _pw.update(p=None, b=None, page=None)


def _num(v, d=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return d


def _famiglie(valore, fonti):
    """font-family di json2video: nome Google Fonts oppure URL di un .ttf (diventa @font-face)."""
    v = str(valore or '').strip().strip("'\"")
    if not v:
        return ''
    if v.startswith('http'):
        nome = 'F' + str(abs(hash(v)) % 10 ** 8)
        fonti['url'][nome] = v
        return f"'{nome}'"
    fonti['google'].add(v.split(',')[0].strip().strip("'\""))
    return f"'{v.split(',')[0].strip()}', sans-serif"


def _testo_html(el, k, fonti):
    s = dict(el.get('settings') or {})
    x, y = _num(el.get('x'), 0), _num(el.get('y'), 0)
    w, h = _num(el.get('width'), W) or W, _num(el.get('height'), H) or H
    vp = {'top': 'flex-start', 'center': 'center', 'bottom': 'flex-end'}.get(str(s.pop('vertical-position', 'center')), 'center')
    hp = {'left': 'flex-start', 'center': 'center', 'right': 'flex-end'}.get(str(s.pop('horizontal-position', 'center')), 'center')
    css = []
    for chiave, val in s.items():
        if chiave == 'font-family':
            val = _famiglie(val, fonti)
        if val in (None, ''):
            continue
        css.append(f'{chiave}:{val}')
    if not any(c.startswith('text-align') for c in css):
        css.append('text-align:center')
    testo = H_.escape(str(el.get('text') or '')).replace('\n', '<br>')
    return (f'<div id="L{k}" class="liv" style="left:{x}px;top:{y}px;width:{w}px;height:{h}px;display:flex;align-items:{vp};justify-content:{hp}">'
            f'<div style="{";".join(css)}">{testo}</div></div>')


def _html_html(el, k):
    x, y = _num(el.get('x'), 0), _num(el.get('y'), 0)
    w, h = _num(el.get('width'), W) or W, _num(el.get('height'), H) or H
    doc = '<!doctype html><html><head><meta charset="utf-8"></head><body>' + str(el.get('html') or '') + '</body></html>'
    return (f'<iframe id="L{k}" class="liv" style="left:{x}px;top:{y}px;width:{w}px;height:{h}px" '
            f'srcdoc="{H_.escape(doc, quote=True)}"></iframe>')


def _pagina_livelli(livelli, sfondo='transparent'):
    fonti = {'google': set(), 'url': {}}
    corpo = []
    for k, el in enumerate(livelli):
        if el.get('type') == 'text':
            corpo.append(_testo_html(el, k, fonti))
        elif el.get('type') == 'html':
            corpo.append(_html_html(el, k))
    teste = []
    for fam in sorted(fonti['google']):
        f = fam.replace(' ', '+')
        teste.append(f'<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family={f}&display=block">')
        teste.append(f'<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family={f}:wght@700;900&display=block">')
    ff = ''.join(f"@font-face{{font-family:'{n}';src:url('{u}');font-display:block}}" for n, u in fonti['url'].items())
    return ('<!doctype html><html><head><meta charset="utf-8">' + ''.join(teste) +
            f'<style>{ff}html,body{{margin:0;padding:0;width:{W}px;height:{H}px;overflow:hidden;background:{sfondo}}}'
            '.liv{position:absolute;border:0;background:transparent;overflow:visible}iframe.liv{overflow:hidden}</style></head><body>'
            + ''.join(corpo) + '</body></html>')


_JS_PRONTO = """async () => {
  const docs = [document, ...Array.from(document.querySelectorAll('iframe')).map(f => f.contentDocument).filter(Boolean)];
  for (const d of docs) { try { await d.fonts.ready; } catch (e) {} }
  const imgs = docs.flatMap(d => Array.from(d.images || []));
  await Promise.all(imgs.map(i => i.complete ? 0 : new Promise(r => { i.onload = i.onerror = r; setTimeout(r, 8000); })));
  for (const d of docs) { try { d.getAnimations().forEach(a => a.pause()); } catch (e) {} }
  return docs.length;
}"""

_JS_TEMPO = """([t, finestre]) => {
  for (const [id, a, b] of finestre) {
    const el = document.getElementById(id); if (!el) continue;
    const vis = t >= a - 1e-6 && t < b - 1e-6;
    el.style.visibility = vis ? 'visible' : 'hidden';
    const d = el.tagName === 'IFRAME' ? el.contentDocument : null;
    if (d) { try { d.getAnimations().forEach(x => { x.currentTime = Math.max(0, t - a) * 1000; }); } catch (e) {} }
  }
}"""


def _carica(html_txt, cartella, nome):
    p = os.path.join(cartella, nome + '.html')
    open(p, 'w', encoding='utf-8').write(html_txt)
    pg = _pagina()
    pg.goto('file://' + os.path.abspath(p), wait_until='load', timeout=60000)
    pg.evaluate(_JS_PRONTO)
    pg.wait_for_timeout(250)
    return pg


def foto_cornice(el, sfondo, cartella, nome):
    """Scena "foto in cornice": sfondo colorato + pagina HTML della cornice (stessa di json2video). PNG pieno."""
    pg = _carica(_pagina_livelli([dict(el, x=0, y=0, width=W, height=H, start=0)], sfondo or '#F5A623'), cartella, nome)
    out = os.path.join(cartella, nome + '.png')
    pg.screenshot(path=out)
    return out


def sovrimpressione(livelli, durata_scena, cartella, nome):
    """Livelli trasparenti di una scena (testi e html con start/durata e animazioni).
    Ritorna il file concat (immagini + durate) da sovrapporre, oppure None."""
    livelli = [l for l in livelli if l.get('type') in ('text', 'html')]
    if not livelli:
        return None
    finestre, tempi = [], {0.0}
    for k, el in enumerate(livelli):
        a = max(0.0, _num(el.get('start'), 0.0))
        d = _num(el.get('duration'), -2)
        b = durata_scena if d <= 0 else min(durata_scena, a + d)
        if a >= durata_scena:
            continue
        finestre.append([f'L{k}', a, b])
        tempi.update([a, b])
        if el.get('type') == 'html':   # animazioni CSS: fotogrammi fitti subito dopo la comparsa
            n = int(ANIM_SEC * FPS)
            tempi.update(a + j / FPS for j in range(1, n + 1))
    tempi = sorted(t for t in tempi if t < durata_scena - 1e-3)
    pg = _carica(_pagina_livelli(livelli), cartella, nome)
    righe = []
    for j, t in enumerate(tempi):
        pg.evaluate(_JS_TEMPO, [t, finestre])
        png = os.path.join(cartella, f'{nome}_{j:03d}.png')
        pg.screenshot(path=png, omit_background=True)
        fine = tempi[j + 1] if j + 1 < len(tempi) else durata_scena
        righe.append(f"file '{os.path.abspath(png)}'\nduration {max(1.0 / FPS, fine - t):.4f}\n")
    righe.append(f"file '{os.path.abspath(png)}'\n")   # il concat vuole l'ultima immagine ripetuta
    lista = os.path.join(cartella, nome + '_lista.txt')
    open(lista, 'w').write(''.join(righe))
    return lista


def applica(pezzo_in, pezzo_out, lista, video_sopra, inizio, durata, cartella, enc, vf_cover):
    """Sovrappone al pezzo (che parte a "inizio" secondi dentro la scena) i livelli della scena
    e le clip typo_fast_cut (video che coprono la scena da "start" in poi)."""
    ins = ['-i', pezzo_in]
    fl, cur, k = [], '[0:v]', 1
    for v in video_sopra:
        a = _num(v.get('start'), 0.0) - inizio
        if a >= durata or not v.get('locale'):
            continue
        a = max(0.0, a)
        ins += ['-stream_loop', '-1', '-t', f'{durata - a + 0.5:.3f}', '-i', v['locale']]
        fl.append(f"[{k}:v]{vf_cover},setpts=PTS-STARTPTS+{a:.3f}/TB[c{k}];{cur}[c{k}]overlay=eof_action=pass:enable='gte(t,{a:.3f})'[o{k}]")
        cur = f'[o{k}]'; k += 1
    if lista:
        ins += ['-ss', f'{inizio:.3f}', '-f', 'concat', '-safe', '0', '-i', lista]
        fl.append(f'[{k}:v]format=rgba,fps={FPS},setpts=PTS-STARTPTS[s{k}];{cur}[s{k}]overlay=eof_action=repeat:shortest=0[o{k}]')
        cur = f'[o{k}]'; k += 1
    if not fl:
        return pezzo_in
    nf = int(round(durata * FPS))
    subprocess.run(['ffmpeg', '-y', '-v', 'error'] + ins + ['-filter_complex', ';'.join(fl), '-map', cur, '-frames:v', str(nf)] + enc + [pezzo_out], check=True)
    return pezzo_out
