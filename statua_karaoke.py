#!/usr/bin/env python3
"""VIDEO "STATUA + TESTO KARAOKE" (render_style "testo": "karaoke"), stesso stile della copertina statua:
- la statua della copertina FERMA a sinistra (statua_video.png, fatta da copertina_statua.py);
- sopra, cenere grigio-chiara che sale lenta (effetto: render_style "effetto": "cenere" | "nessuno");
- a destra il testo grande con il font e i colori della copertina: max 3 righe, la parola detta si accende del colore d'accento.
  Tempi parola per parola con faster-whisper (riserva: stimati), mai due testi insieme.
Usato da render_filosofo.py."""
import math, os, random, re, subprocess
from PIL import Image, ImageDraw, ImageFilter

W, H, FPS = 1920, 1080, 30


def _ass_col(c, rif):
    c = str(c or rif).strip().lstrip('#')
    if not re.fullmatch(r'[0-9a-fA-F]{6}', c):
        c = rif.lstrip('#')
    return f'&H00{c[4:6]}{c[2:4]}{c[0:2]}&'.upper()


def font_file(cfg, cartella='font'):
    """il font della copertina (colonna thumbnail_font_url, di solito Anton) nella cartella dei font"""
    import urllib.request
    url = str(cfg.get('thumbnail_font_url') or '').strip() or 'https://cdn.jsdelivr.net/gh/google/fonts@main/ofl/anton/Anton-Regular.ttf'
    f = os.path.join(cartella, 'copertina_' + re.sub(r'\W+', '_', url.split('/')[-1]))
    os.makedirs(cartella, exist_ok=True)
    if not os.path.exists(f):
        tmp = f + '.%d' % os.getpid()
        open(tmp, 'wb').write(urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=60).read())
        os.replace(tmp, f)
    return f


def cenere(dur, out, fps=FPS):
    """cenere grigio-chiara che sale lenta, fiocchi di 3 grandezze (i grandi sfocati = piu' vicini), in loop"""
    rnd = random.Random(11); w, h = W // 2, H // 2; nf = int(dur * fps)
    parts = []
    for _ in range(140):
        z = rnd.choice((1, 1, 1, 2, 2, 3))
        parts.append({'x': rnd.uniform(0, w), 'y0': rnd.uniform(0, h), 'v': rnd.uniform(6, 16) * z, 'r': rnd.uniform(.6, 1.3) * z,
                      'dx': rnd.uniform(-5, 5), 'f': rnd.uniform(.2, .9), 'fase': rnd.uniform(0, 6.3), 'z': z})
    pr = subprocess.Popen(['ffmpeg', '-y', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{w}x{h}', '-r', str(fps), '-i', '-',
                           '-vf', f'scale={W}:{H}', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p', out], stdin=subprocess.PIPE)
    for i in range(nf):
        t = i / fps
        lay = {z: Image.new('L', (w, h)) for z in (1, 2, 3)}
        for q in parts:
            y = (q['y0'] - q['v'] * t) % (h + 20) - 10
            x = (q['x'] + q['dx'] * t + 6 * math.sin(q['f'] * t + q['fase'])) % w
            luce = int((110 + 90 * math.sin(1.7 * t + q['fase'])) * (1.0 if q['z'] < 3 else .8))
            r = q['r']; ImageDraw.Draw(lay[q['z']]).ellipse([x - r, y - r, x + r, y + r], fill=max(40, luce))
        im = Image.merge('RGB', [lay[1]] * 3)
        for z, bl in ((2, 1.2), (3, 2.6)):
            im = Image.composite(Image.merge('RGB', [lay[z]] * 3).filter(ImageFilter.GaussianBlur(bl)), im, lay[z].filter(ImageFilter.GaussianBlur(bl)))
        pr.stdin.write(im.tobytes())
    pr.stdin.close(); pr.wait()
    return out


def sfondo(statua_video, totale, cartella, effetto='cenere', fps=FPS, log=print):
    """video di sfondo lungo quanto la voce: statua ferma + cenere"""
    out = os.path.join(cartella, 'sfondo_statua.mp4')
    if effetto == 'nessuno':
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-loop', '1', '-framerate', str(fps), '-i', statua_video, '-t', f'{totale:.3f}',
                        '-vf', f'scale={W}:{H},format=yuv420p', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', out], check=True)
        return out
    cen = cenere(12, os.path.join(cartella, 'cenere_grigia.mp4'), fps)
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-loop', '1', '-framerate', str(fps), '-i', statua_video, '-stream_loop', '-1', '-i', cen,
                    '-filter_complex', f'[0:v]scale={W}:{H},format=gbrp[a];[1:v]format=gbrp[b];[a][b]blend=all_mode=lighten,format=yuv420p[v]',
                    '-map', '[v]', '-t', f'{totale:.3f}', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', out], check=True)
    log('sfondo statua + ' + effetto + ' pronto')
    return out


def ass(scene, tempi, voce, cfg, stile, cartella, font_file, log=print):
    import render_kao as RK
    from PIL import ImageFont
    nome_font = ImageFont.truetype(font_file, 20).getname()[0]
    maiu = str(stile.get('maiuscolo') or 'SI').upper() == 'SI'
    CR, RM = int(stile.get('caratteri_riga') or 11), int(stile.get('righe_max') or 3)
    size = int(float(stile.get('dimensione_testo') or 205))
    xc, yc = int(W * float(stile.get('x_testo') or .735)), int(H * float(stile.get('y_testo') or .5))
    bianco = _ass_col(cfg.get('thumbnail_highlight_text_color'), '#FFFFFF')
    accento = _ass_col(cfg.get('thumbnail_accent_color'), '#39FF14')
    scene_parole = [str(s.get('testo', '')).split() for s in scene]
    parole = [p for ps in scene_parole for p in ps]
    os.environ.setdefault('LINGUA', str(cfg.get('language') or 'en')[:2])
    t_par = RK.tempi_parole(voce, parole, [a for a, b in tempi], [b for a, b in tempi], scene_parole)
    blocchi, righe, riga = [], [], []
    for i, w in enumerate(parole):
        ww = w.upper() if maiu else w
        if riga and len(' '.join(x[1] for x in riga + [(i, ww)])) > CR:
            righe.append(riga); riga = []
            if len(righe) == RM:
                blocchi.append(righe); righe = []
        riga.append((i, ww))
        if re.search(r'[.!?]["\')]*$', w):   # fine frase: blocco nuovo
            righe.append(riga); riga = []; blocchi.append(righe); righe = []
    if riga:
        righe.append(riga)
    if righe:
        blocchi.append(righe)
    ev = []
    for bl in blocchi:
        idx = [i for rg in bl for i, _ in rg]
        for k, i in enumerate(idx):
            inizio = t_par[i][0]
            fine = t_par[idx[k + 1]][0] if k + 1 < len(idx) else t_par[idx[-1]][1] + .25
            testo = '\\N'.join(' '.join(('{\\c' + (accento if j == i else bianco) + '}') + w for j, w in rg) for rg in bl)
            ev.append([inizio, fine, testo])
    for k in range(len(ev) - 1):   # mai due testi insieme
        nx = ev[k + 1][0]
        if nx - ev[k][1] < .6 or ev[k][1] > nx:
            ev[k][1] = nx
    ts = lambda s: f'{int(max(0, s) // 3600)}:{int(max(0, s) % 3600 // 60):02d}:{max(0, s) % 60:05.2f}'
    out = ['[Script Info]', 'ScriptType: v4.00+', f'PlayResX: {W}', f'PlayResY: {H}', 'WrapStyle: 2', '', '[V4+ Styles]',
           'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, '
           'ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding',
           f'Style: T,{nome_font},{size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,0,0,0,0,100,100,1,0,1,3,6,5,0,0,0,1', '',
           '[Events]', 'Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text']
    for a, b, t in ev:
        if b > a:
            out.append(f'Dialogue: 0,{ts(a)},{ts(b)},T,,0,0,0,,{{\\pos({xc},{yc})}}{t}')
    p = os.path.join(cartella, 'testo_karaoke.ass'); open(p, 'w', encoding='utf-8').write('\n'.join(out) + '\n')
    log(f'testo karaoke: {len(blocchi)} blocchi, {len(parole)} parole, font {nome_font}')
    return p, nome_font
