#!/usr/bin/env python3
"""COSTO VERO - 3 PROVE DI STILE da 1 minuto (12 nov 2026, Giorgio: "i video sono troppo fermi e la persona si annoia; piu' animati,
max 20% di clip Pexels estremamente collegate; 3 prove diverse sullo stesso argomento: la piscina uscita oggi").
Stessa voce del primo minuto del video della piscina (gia' pagata), stesse illustrazioni per le 3 prove, cambia SOLO la grafica:
  A "CONTATORE":  tagli veloci ogni ~2,5 s con spinta e scivolata, numeri che "sbattono" al centro, contatore della spesa sempre in alto.
  B "SCONTRINO":  lo scontrino gigante a destra che si stampa riga per riga mentre la voce parla, a sinistra le immagini in una cornice.
  C "CONFRONTO":  due barre in basso (prezzo vs costo vero) che crescono mentre si parla, parole chiave che saltano fuori, scorrimenti laterali.
Clip Pexels: massimo 20% del tempo, scelte con parole precise (piscina, escavatore, calcolatrice...).
I tempi delle parole vengono dalla trascrizione (faster-whisper, gratis): i numeri compaiono quando la voce li dice.
Spesa: circa 11 illustrazioni Klein (~0,25 $). Esce in prove_video/Costo_Vero/stili/."""
import io, json, math, os, random, re, subprocess, sys, time, urllib.parse, urllib.request
from PIL import Image, ImageDraw, ImageFilter, ImageFont

QUI = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, QUI); sys.path.insert(0, os.path.dirname(QUI))
os.environ.setdefault('COSTI_FILE', '/tmp/stili_costi.jsonl')
import costi as CO
import motore_yt as YT

E = os.environ.get
SRC = 'prove_video/Costo_Vero/possesso'
OUT = E('OUT') or 'prove_video/Costo_Vero/stili'; os.makedirs(OUT, exist_ok=True)
LAV = '/tmp/stili'; os.makedirs(LAV, exist_ok=True)
W, H, FPS = 1920, 1080, 30
FA, FB = 'ctr_test/Anton.ttf', 'fonts_gloam/montserrat_black.woff'
INK, Y, R, G, BL, BIANCO, GR = (30, 34, 53), (255, 201, 60), (232, 57, 70), (43, 182, 115), (60, 120, 235), (255, 255, 255), (95, 100, 120)
SUONI = 'libreria_mappe/suoni/'
_F = {}
F = lambda p, s: _F.setdefault((p, int(s)), ImageFont.truetype(p, int(s)))
log = lambda *a: print(time.strftime('%H:%M:%S'), *a, flush=True)
ease = lambda x: 0 if x <= 0 else 1 if x >= 1 else 1 - (1 - x) ** 3
cl = lambda x: max(0.0, min(1.0, x))


def pop(x):
    if x <= 0: return 0
    if x >= 1: return 1
    return 1 + 0.25 * math.sin(x * math.pi) if x > .55 else ease(x / .55) * 1.1


def ultimo(t, T, chiavi, finestra):
    """Solo l'ultima scritta comparsa (mai due una sopra l'altra): la chiave con il momento piu' recente gia' passato, se ancora dentro la sua finestra."""
    att = [k for k in chiavi if T.get(k) is not None and 0 <= t - T[k] < finestra]
    return max(att, key=lambda k: T[k]) if att else None


def eur(v):
    return f'{round(v):,}'.replace(',', '.') + ' €'


# ------------------------------------------------------------------ voce e tempi delle parole
AUDIO = os.path.join(SRC, 'audio_primo_minuto.mp3')
DUR = float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', AUDIO]).decode())


def parole():
    f = os.path.join(LAV, 'parole.json')
    if os.path.exists(f):
        return json.load(open(f))
    from faster_whisper import WhisperModel
    m = WhisperModel('small', device='cpu', compute_type='int8')
    import numpy as np   # l'audio lo decodifica ffmpeg (la libreria av installata non e' compatibile con faster-whisper)
    pcm = subprocess.run(['ffmpeg', '-v', 'error', '-i', AUDIO, '-f', 's16le', '-ac', '1', '-ar', '16000', '-'], capture_output=True, check=True).stdout
    seg, _ = m.transcribe(np.frombuffer(pcm, np.int16).astype(np.float32) / 32768.0, language='it', word_timestamps=True)
    pw = [{'w': w.word.strip().lower(), 'a': w.start, 'b': w.end} for s in seg for w in s.words]
    json.dump(pw, open(f, 'w')); log('parole trascritte:', len(pw)); return pw


PW = []


def quando(chiave, dopo=0.0, default=None):
    """Il momento in cui la voce dice una parola (la prima dopo 'dopo')."""
    k = chiave.lower()
    for p in PW:
        if p['a'] >= dopo and k in re.sub(r'[^\wàèéìòù]', '', p['w']):
            return p['a']
    return default


# ------------------------------------------------------------------ illustrazioni (Klein) e clip Pexels
STILE = ('DIGITAL PAINTED ILLUSTRATION, NOT a photograph: warm editorial illustration style with soft painted shading, consistent in every image. '
         'Ordinary Italian middle-class setting, sunny. NO text, NO words, NO letters, NO numbers anywhere. ')
MARCO = 'Marco: an Italian man, 44, short dark hair with grey temples, light blue polo shirt, beige trousers'


def fal(ep, dati):
    hd = {'Authorization': 'Key ' + E('FAL_KEY', '')}
    inv = YT.http('https://queue.fal.run/' + ep, dati, hd, timeout=120)
    for _ in range(150):
        time.sleep(2)
        if YT.http(inv['status_url'], headers=hd, timeout=60).get('status') == 'COMPLETED':
            break
    return YT.http(inv['response_url'], headers=hd, timeout=60)['images'][0]['url']


def illustrazione(nome, descr, rif=None):
    f = os.path.join(OUT, 'img_' + nome + '.jpg')
    if os.path.exists(f):
        return f
    for _ in range(3):
        try:
            if rif:
                u = fal('fal-ai/flux-2/klein/4b/edit', {'prompt': STILE + 'SAME man as in the reference image (same face, hair, clothes). ' + descr,
                                                         'image_urls': [rif], 'image_size': {'width': 1920, 'height': 1080}, 'num_images': 1, 'output_format': 'png'})
                CO.registra('fal', 'flux-2-klein-4b-edit', dollari=0.038, nota='prova stili costo vero')
            else:
                u = fal('fal-ai/flux-2/klein/4b', {'prompt': STILE + descr, 'image_size': {'width': 1920, 'height': 1080}, 'num_images': 1, 'output_format': 'png'})
                CO.registra('fal', 'flux-2-klein-4b', dollari=0.02, nota='prova stili costo vero')
            Image.open(io.BytesIO(YT.http(u, raw=True, timeout=120))).convert('RGB').resize((W, H), Image.LANCZOS) \
                .filter(ImageFilter.UnsharpMask(1.5, 50, 2)).save(f, quality=96)
            open(f + '.url', 'w').write(u)
            return f
        except Exception as e:
            log('immagine non riuscita:', str(e)[:120]); time.sleep(4)
    return None


def clip_pexels(nome, q, sec):
    f = os.path.join(LAV, 'clip_' + nome + '.mp4')
    if os.path.exists(f):
        return f
    r = json.loads(urllib.request.urlopen(urllib.request.Request('https://api.pexels.com/videos/search?' + urllib.parse.urlencode(
        {'query': q, 'per_page': 8, 'orientation': 'landscape', 'size': 'large'}), headers={'Authorization': E('PEXELS_API_KEY', ''), 'User-Agent': 'Mozilla/5.0'}), timeout=60).read())
    for v in r.get('videos', []):
        if v.get('duration', 0) < sec + 1:
            continue
        fs = sorted([x for x in v['video_files'] if (x.get('width') or 0) >= 1920 and x.get('file_type') == 'video/mp4'], key=lambda x: x['width'])
        if not fs:
            continue
        raw = os.path.join(LAV, 'raw_' + nome + '.mp4')
        open(raw, 'wb').write(urllib.request.urlopen(urllib.request.Request(fs[0]['link'], headers={'User-Agent': 'Mozilla/5.0'}), timeout=180).read())
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', '1', '-i', raw, '-t', f'{sec + .5:.2f}', '-vf', f'scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS}',
                        '-an', '-c:v', 'libx264', '-crf', '16', f], check=True)
        log('clip pexels', nome, '->', v.get('url'))
        return f
    return None


def fotogrammi_clip(f):
    """I fotogrammi di una clip come immagini PIL (le clip sono corte: 2-3 s)."""
    d = os.path.join(LAV, os.path.basename(f) + '_fr'); os.makedirs(d, exist_ok=True)
    if not os.listdir(d):
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', f, '-q:v', '2', os.path.join(d, '%04d.jpg')], check=True)
    return [os.path.join(d, x) for x in sorted(os.listdir(d))]


# ------------------------------------------------------------------ disegno
def testo(im, xy, t, font, size, col, anc='la', alpha=1.0, ombra=True, stroke=0, maxw=None, scala=1.0):
    if alpha <= 0 or not t:
        return
    size = size * scala
    while maxw and size > 20 and F(font, size).getlength(t) > maxw:
        size -= 4
    lay = Image.new('RGBA', im.size, (0, 0, 0, 0)); d = ImageDraw.Draw(lay); f = F(font, size)
    if ombra:
        d.text((xy[0] + 5, xy[1] + 7), t, font=f, fill=(0, 0, 0, int(110 * alpha)), anchor=anc, stroke_width=stroke, stroke_fill=(0, 0, 0, int(110 * alpha)))
    d.text(xy, t, font=f, fill=col + (int(255 * alpha),), anchor=anc, stroke_width=stroke, stroke_fill=(20, 20, 30, int(255 * alpha)))
    im.alpha_composite(lay)


def box(im, b, col, r=26, alpha=1.0, bordo=None):
    lay = Image.new('RGBA', im.size, (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    d.rounded_rectangle((b[0] + 6, b[1] + 10, b[2] + 6, b[3] + 10), r, fill=(0, 0, 0, int(70 * alpha)))
    d.rounded_rectangle(b, r, fill=col[:3] + (int((col[3] if len(col) > 3 else 255) * alpha),), outline=bordo, width=6 if bordo else 0)
    im.alpha_composite(lay)


def inquadra(src, t, d, k, forza=0.14):
    """Movimento deciso: spinta veloce all'inizio (punch-in) poi deriva lenta, direzione diversa per ogni inquadratura."""
    if isinstance(src, list):   # clip: fotogramma giusto
        img = Image.open(src[min(len(src) - 1, int(t * FPS))]).convert('RGB')
        z = 1.0 + 0.05 * (t / max(d, .1))
    else:
        img = src; t = max(0.0, t)
        a = ease(t / .35)
        z = 1.0 + forza * 0.45 * a + forza * 0.55 * (t / max(d, .1))
    w, h = W / z, H / z
    dx = [(.5, .5), (.3, .5), (.7, .5), (.5, .35), (.4, .6), (.6, .4)][k % 6]
    x0 = (W - w) * dx[0]; y0 = (H - h) * dx[1]
    return img.resize((W, H), Image.LANCZOS, box=(x0, y0, x0 + w, y0 + h)).convert('RGBA')


# ------------------------------------------------------------------ piano comune: inquadrature e momenti chiave
def piano():
    T = {}
    T['prezzo'] = quando('trentacinquemila', 0, 1.0)
    T['vero'] = quando('sessantamila', T['prezzo'], 4.5)
    T['mese'] = quando('mese', T['vero'], 8.0)
    T['voce'] = quando('voce', T['mese'], 10.0)
    T['vasca'] = quando('vasca', T['voce'], 13.0)
    T['marco'] = quando('marco', 0, 15.0)
    T['figli'] = quando('figli', T['marco'], 18.0)
    T['papa'] = quando('pap', T['figli'], 20.0)
    T['preventivo'] = quando('preventivo', T['papa'], 23.0)
    T['prev35'] = quando('trentacinquemila', T['preventivo'], T['preventivo'] + 1.2)
    T['firma'] = quando('firma', T['prev35'], 28.0)
    T['ingresso'] = quando('ingresso', T['firma'], 30.0)
    T['scavo'] = quando('scavo', T['ingresso'], 32.0)
    T['scavo35'] = quando('trentacinquemila', T['scavo'], T['scavo'] + 2.5)
    T['otto'] = quando('otto', T['scavo35'], T['scavo35'] + 3)
    T['escavatore'] = quando('escavatore', T['otto'], T['otto'] + 5)
    T['camion'] = quando('camion', T['escavatore'], T['escavatore'] + 3)
    T['cemento'] = quando('cemento', T['camion'], T['camion'] + 3)
    T['rivestimento'] = quando('rivestimento', T['cemento'], T['cemento'] + 3)
    T['bagno'] = quando('bagno', T['rivestimento'], T['rivestimento'] + 3)
    log('tempi:', {k: round(v, 1) for k, v in T.items()})
    return T


def inquadrature(T, I, C):
    """Elenco (inizio, sorgente, tipo) con tagli ogni ~2,5 s: le clip Pexels <= 20% del tempo, sempre sul tema detto in quel momento."""
    s = [(0.0, C['piscina'], 'clip'), (T['prezzo'] + .4, I['calcolatrice'], 'img'), (T['vero'] - .2, I['monete'], 'img'), (T['mese'] - .2, I['salvadanaio'], 'img'),
         (T['vasca'] - .3, C['acqua'], 'clip'), (T['marco'] - .2, I['marco'], 'img'), (T['figli'], I['ciabatte'], 'img'), (T['papa'] + .4, I['marco2'], 'img'),
         (T['preventivo'] - .1, I['firma'], 'img'), (T['ingresso'] - .6, C['calcolo'], 'clip'), (T['scavo'] - .2, I['scavo'], 'img'),
         (T['escavatore'] - .2, C['escavatore'], 'clip'), (T['camion'] - .1, I['camion'], 'img'), (T['cemento'] - .1, I['cemento'], 'img'),
         (T['rivestimento'], I['piastrelle'], 'img'), (T['bagno'] - .1, I['marco3'], 'img')]
    s = sorted([x for x in s if x[1] is not None], key=lambda x: x[0])
    out = []
    for k, (a, src, tipo) in enumerate(s):
        b = s[k + 1][0] if k + 1 < len(s) else DUR
        if b - a < .6:
            continue
        # spezza le inquadrature lunghe: mai piu' di 3 s sulla stessa senza un cambio di movimento
        n = max(1, round((b - a) / 3.0))
        for j in range(n):
            out.append({'a': a + j * (b - a) / n, 'b': a + (j + 1) * (b - a) / n, 'src': src, 'tipo': tipo, 'k': len(out)})
    if out:
        out[0]['a'] = 0.0   # la prima inquadratura parte da zero
    cl_t = sum(x['b'] - x['a'] for x in out if x['tipo'] == 'clip')
    log(f'inquadrature: {len(out)} | clip Pexels {cl_t:.1f} s su {DUR:.1f} s ({cl_t / DUR * 100:.0f}%)')
    return out


# ------------------------------------------------------------------ i 3 stili
def stile_A(fr, t, T, sh):
    """CONTATORE: numeri che sbattono al centro, contatore della spesa sempre in alto a sinistra."""
    # contatore della spesa in alto a sinistra: parte quando iniziano le voci di spesa e sale con ognuna
    if t >= T['scavo'] - .3:
        a = ease((t - T['scavo'] + .3) / .3)
        spesa = 35000 * ease((t - T['scavo35']) / 1.2) if t >= T['scavo35'] else 0
        box(fr, (50, 44, 640, 170), INK + (235,), r=22, alpha=a)
        testo(fr, (80, 58), 'SPESA FINORA', FB, 30, Y, ombra=False, alpha=a)
        testo(fr, (80, 92), eur(spesa), FA, 66, BIANCO, ombra=False, maxw=540, alpha=a)
    # obiettivo in alto a destra: dove si arriva
    if t >= T['vero']:
        box(fr, (1380, 44, 1870, 170), R + (235,), r=22)
        testo(fr, (1410, 58), 'IN 10 ANNI', FB, 30, BIANCO, ombra=False)
        testo(fr, (1410, 92), '60.500 €', FA, 66, BIANCO, ombra=False)
    # numeri che sbattono
    EV = {'prezzo': ('35.000 €', BIANCO, 'IL PREZZO'), 'vero': ('60.500 €', R, 'IL COSTO VERO'), 'mese': ('504 €', Y, 'AL MESE'),
          'prev35': ('35.000 €', BIANCO, 'IL PREVENTIVO'), 'scavo35': ('35.000 €', Y, 'SCAVO E COSTRUZIONE')}
    k_ = ultimo(t, T, EV, 2.3)
    if k_:
        txt, col, sotto = EV[k_]; dt = t - T[k_]
        if True:
            sc = 1.7 - .7 * ease(dt / .25) if dt < .25 else 1.0 + .03 * math.sin(dt * 9) * cl(1 - dt)
            a = cl((2.3 - dt) / .3)
            sx = int(18 * math.sin(dt * 60) * cl(1 - dt / .3))
            testo(fr, (W // 2 + sx, 470), txt, FA, 230, col, anc='mm', alpha=a, stroke=8, scala=sc)
            testo(fr, (W // 2, 630), sotto, FB, 56, BIANCO, anc='mm', alpha=a * ease((dt - .2) / .3), stroke=4)


def stile_B(fr, t, T, sh, base):
    """SCONTRINO: a destra lo scontrino che si stampa riga per riga; a sinistra le immagini in cornice inclinata."""
    fr.paste((246, 241, 230, 255), (0, 0, W, H))
    # immagine in cornice a sinistra
    pic = base.resize((1120, 630), Image.LANCZOS)
    cornice = Image.new('RGBA', (1160, 670), (255, 255, 255, 255)); cornice.paste(pic, (20, 20))
    ang = 2.2 * math.sin((sh['k'] % 4) * 1.3) * (1 - ease((t - sh['a']) / .5) * .3)
    slide = int(-140 * (1 - ease((t - sh['a']) / .3))) if sh['k'] > 0 else 0
    cr = cornice.rotate(ang, expand=True, resample=Image.BICUBIC)
    ombra = Image.new('RGBA', cr.size, (0, 0, 0, 0)); ombra.paste((0, 0, 0, 90), (0, 0, cr.width, cr.height), cr.split()[3])
    fr.alpha_composite(ombra.filter(ImageFilter.GaussianBlur(14)), (70 + slide + 10, 200 + 16))
    fr.alpha_composite(cr, (70 + slide, 200))
    # scontrino
    righe = [('prezzo', 'PISCINA (PREVENTIVO)', '35.000 €', INK), ('vero', 'COSTO VERO IN 10 ANNI', '60.500 €', R), ('mese', 'OGNI MESE', '504 €', R),
             ('scavo35', '1. SCAVO E COSTRUZIONE', '35.000 €', INK), ('escavatore', '   escavatore', '', GR), ('camion', '   camion di terra', '', GR),
             ('cemento', '   cemento e armature', '', GR), ('rivestimento', '   bordi e rivestimento', '', GR)]
    vis = [r for r in righe if t >= T[r[0]]]
    x0, y0, lw = 1250, 60, 630
    hpap = 150 + 92 * len(vis) + (40 if vis else 0)
    if t >= T['prezzo'] - .5:
        k = ease((t - T['prezzo'] + .5) / .4)
        lay = Image.new('RGBA', (lw, hpap), (255, 255, 255, 255)); d = ImageDraw.Draw(lay)
        for x in range(0, lw, 28):   # bordo seghettato in basso
            d.polygon([(x, hpap), (x + 14, hpap - 16), (x + 28, hpap)], fill=(246, 241, 230, 255))
        d.text((lw // 2, 40), 'COSTO VERO', font=F(FA, 54), fill=INK, anchor='mt')
        d.line((30, 115, lw - 30, 115), fill=(180, 180, 180), width=3)
        for i, (k_, a_, b_, col) in enumerate(vis):
            y = 140 + i * 92; dt = t - T[k_]
            n = int(len(a_) * cl(dt / .5))   # si stampa lettera per lettera
            d.text((30, y), a_[:n], font=F(FB, 30 if not a_.startswith('   ') else 26), fill=GR if a_.startswith('   ') else INK)
            if dt > .45:
                d.text((lw - 30, y + 40), b_, font=F(FA, 50), fill=col, anchor='rt')
        lay2 = lay.rotate(-1.5, expand=True, resample=Image.BICUBIC)
        sh_ = Image.new('RGBA', lay2.size, (0, 0, 0, 0)); sh_.paste((0, 0, 0, 80), (0, 0, lay2.width, lay2.height), lay2.split()[3])
        yy = int(y0 - (1 - k) * 300)
        fr.alpha_composite(sh_.filter(ImageFilter.GaussianBlur(12)), (x0 + 8, yy + 14)); fr.alpha_composite(lay2, (x0, yy))
    # timbro AL MESE / frase in basso a sinistra
    EV = {'marco': 'MARCO, 44 ANNI', 'papa': '"PAPÀ, FACCIAMO LA PISCINA?"', 'firma': 'FIRMA', 'ingresso': 'SOLO L\'INGRESSO'}
    k_ = ultimo(t, T, EV, 3.0)
    if k_:
        txt = EV[k_]; dt = t - T[k_]
        if True:
            a = ease(dt / .25) * cl((3.0 - dt) / .3)
            box(fr, (70, 900, 70 + min(1140, 60 + F(FB, 52).getlength(txt)), 1000), Y + (255,), r=18, alpha=a)
            testo(fr, (100, 950), txt, FB, 52, INK, anc='lm', alpha=a, ombra=False, maxw=1080)


def stile_C(fr, t, T, sh):
    """CONFRONTO: due barre in basso (prezzo vs costo vero) che crescono, parole chiave che saltano fuori."""
    # barre
    if t >= T['prezzo'] - .2:
        a = ease((t - T['prezzo'] + .2) / .4)
        box(fr, (60, 820, 1860, 1040), (255, 255, 255, 235), r=28, alpha=a)
        scala = 1700 / 60500
        lp = 35000 * scala * ease((t - T['prezzo']) / .8)
        lv = (35000 + 25500 * ease((t - T['vero']) / 1.3)) * scala if t >= T['vero'] else 0
        d = ImageDraw.Draw(fr)
        testo(fr, (100, 838), 'PREZZO', FB, 30, GR, ombra=False, alpha=a)
        d.rounded_rectangle((100, 875, 100 + max(10, lp), 925), 14, fill=BL + (255,))
        testo(fr, (min(110 + lp, 1700), 900), '35.000 €', FA, 44, BL if lp < 1500 else BIANCO, anc='lm' if lp < 1500 else 'rm', ombra=False)
        if t >= T['vero']:
            testo(fr, (100, 935), 'COSTO VERO IN 10 ANNI', FB, 30, R, ombra=False)
            d.rounded_rectangle((100, 972, 100 + max(10, lv), 1022), 14, fill=R + (255,))
            testo(fr, (90 + lv, 997), eur(lv / scala), FA, 44, BIANCO, anc='rm', ombra=False)
    # parole chiave che saltano fuori (in alto, mai sopra le barre)
    EV = {'mese': ('504 € AL MESE', Y), 'vasca': ('LA VASCA È SOLO L\'INIZIO', BIANCO), 'figli': ('2 FIGLI', BIANCO), 'papa': ('"FACCIAMO LA PISCINA?"', Y),
          'prev35': ('PREVENTIVO: 35.000 €', BIANCO), 'firma': ('FIRMA', Y), 'scavo35': ('SCAVO: 35.000 €', Y), 'otto': ('8 × 4 METRI', BIANCO),
          'escavatore': ('ESCAVATORE', BIANCO), 'camion': ('CAMION', BIANCO), 'cemento': ('CEMENTO', BIANCO), 'rivestimento': ('RIVESTIMENTO', BIANCO)}
    k_ = ultimo(t, T, EV, 1.8)
    if k_:
        txt, col = EV[k_]; dt = t - T[k_]
        if True:
            q = pop(dt / .3); a = cl((1.8 - dt) / .25)
            ang = (-4 if hash(k_) % 2 else 4)
            lay = Image.new('RGBA', (1500, 220), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
            f = F(FA, 120)
            tw = min(1400, f.getlength(txt))
            d.rounded_rectangle((750 - tw / 2 - 40, 20, 750 + tw / 2 + 40, 200), 26, fill=INK + (int(235 * a),))
            d.text((750, 110), txt, font=f if f.getlength(txt) < 1400 else F(FA, 90), fill=col + (int(255 * a),), anchor='mm')
            lay = lay.rotate(ang, resample=Image.BICUBIC).resize((max(1, int(1500 * q)), max(1, int(220 * q))), Image.BICUBIC)
            fr.alpha_composite(lay, (W // 2 - lay.width // 2, 300 - lay.height // 2))


def rendi(stile, T, shots, frames):
    out = os.path.join(LAV, f'muto_{stile}.mp4')
    ff = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                           '-c:v', 'libx264', '-preset', 'medium', '-crf', '14', '-pix_fmt', 'yuv420p', out], stdin=subprocess.PIPE)
    n = int(DUR * FPS); cache = {}
    for i in range(n):
        t = i / FPS
        sh = next((s for s in shots if s['a'] <= t < s['b']), shots[-1])
        src = frames.get(sh['src'], sh['src']) if sh['tipo'] == 'clip' else (cache.get(sh['src']) or cache.setdefault(sh['src'], Image.open(sh['src']).convert('RGB')))
        base = inquadra(src, t - sh['a'], sh['b'] - sh['a'], sh['k'], forza=.16 if stile == 'A' else .10)
        if stile == 'A' and sh['k'] > 0 and t - sh['a'] < .18:   # scivolata veloce tra le inquadrature (whip)
            u = ease((t - sh['a']) / .18)
            base = base.transform(base.size, Image.AFFINE, (1, 0, -int((1 - u) * 260), 0, 1, 0)).filter(ImageFilter.BoxBlur(int((1 - u) * 14)))
        if stile == 'C' and sh['k'] > 0 and t - sh['a'] < .25:   # scorrimento laterale tra le inquadrature
            prev = next((s for s in shots if s['k'] == sh['k'] - 1), sh)
            psrc = frames.get(prev['src'], prev['src']) if prev['tipo'] == 'clip' else (cache.get(prev['src']) or cache.setdefault(prev['src'], Image.open(prev['src']).convert('RGB')))
            pb = inquadra(psrc, prev['b'] - prev['a'], prev['b'] - prev['a'], prev['k'], .10)
            u = ease((t - sh['a']) / .25); dx = int(u * W)
            c_ = Image.new('RGBA', (W, H)); c_.paste(pb, (-dx, 0)); c_.paste(base, (W - dx, 0)); base = c_
        fr = base
        if stile == 'A':
            stile_A(fr, t, T, sh)
        elif stile == 'B':
            fr = Image.new('RGBA', (W, H)); stile_B(fr, t, T, sh, base)
        else:
            stile_C(fr, t, T, sh)
        ff.stdin.write(fr.convert('RGB').tobytes())
        if i % 300 == 0:
            log(f'stile {stile}: {i * 100 // n}%')
    ff.stdin.close(); ff.wait()
    return out


def audio(stile, T):
    """Voce + musica bassa + suoni sui numeri (cassa, monete, carta)."""
    ev = {'A': [('prezzo', 'cassa'), ('vero', 'cassa'), ('mese', 'monete'), ('prev35', 'cassa'), ('scavo35', 'cassa')],
          'B': [(k, 'carta') for k in ('prezzo', 'vero', 'mese', 'scavo35', 'escavatore', 'camion', 'cemento', 'rivestimento')] + [('vero', 'cassa')],
          'C': [('prezzo', 'alza'), ('vero', 'alza'), ('vero', 'cassa'), ('mese', 'monete'), ('scavo35', 'cassa')]}[stile]
    brani = sorted(x for x in os.listdir('libreria_musica') if re.match(r'(curiosita|epico)_\d+\.mp3$', x))
    ins = ['-i', AUDIO, '-stream_loop', '-1', '-i', os.path.join('libreria_musica', brani[3 % len(brani)])]
    fil = ['[0:a]volume=1.0[v]', '[1:a]volume=0.07,atrim=0:%.2f[m]' % DUR]; mix = ['[v]', '[m]']
    for j, (k_, s_) in enumerate(ev):
        ins += ['-i', SUONI + s_ + '.mp3']
        fil.append(f'[{j + 2}:a]volume=0.35,adelay={int(T[k_] * 1000)}|{int(T[k_] * 1000)}[s{j}]'); mix.append(f'[s{j}]')
    fil.append(''.join(mix) + f'amix=inputs={len(mix)}:normalize=0:duration=first[a]')
    out = os.path.join(LAV, f'audio_{stile}.m4a')
    subprocess.run(['ffmpeg', '-v', 'error', '-y'] + ins + ['-filter_complex', ';'.join(fil), '-map', '[a]', '-t', f'{DUR:.2f}', '-c:a', 'aac', '-b:a', '192k', out], check=True)
    return out


def main():
    global PW
    PW = parole(); T = piano()
    I = {}
    I['calcolatrice'] = illustrazione('calcolatrice', 'a calculator and a small pile of euro coins on a wooden garden table next to a blue swimming pool')
    I['monete'] = illustrazione('monete', 'tall towers of euro coins growing next to a sparkling in-ground swimming pool, dramatic low angle')
    I['salvadanaio'] = illustrazione('salvadanaio', 'a pink piggy bank cracked open on a garden table by a swimming pool, a few coins falling out')
    I['marco'] = illustrazione('marco', MARCO + ', standing in his backyard looking at the bare lawn, hands on hips, thoughtful, family house behind')
    rif = open(I['marco'] + '.url').read() if I['marco'] else None
    I['marco2'] = illustrazione('marco2', 'Marco smiling, his two young children pulling his hands toward the garden, summer afternoon', rif)
    I['marco3'] = illustrazione('marco3', 'Marco watching construction workers from the edge of a big pool hole, arms crossed, worried face', rif)
    I['firma'] = illustrazione('firma', 'Marco signing a contract with a pen at a kitchen table, a closed folder beside him, close-up on hands and face', rif)
    I['ciabatte'] = illustrazione('ciabatte', "two children's flip-flops and a colorful beach ball on a green lawn")
    I['scavo'] = illustrazione('scavo', 'yellow excavator digging a big rectangular hole in a residential Italian backyard')
    I['camion'] = illustrazione('camion', 'dump truck loaded with earth parked on an Italian suburban street next to a house')
    I['cemento'] = illustrazione('cemento', 'steel rebar framework and wet concrete inside an excavated pool shell, construction site')
    I['piastrelle'] = illustrazione('piastrelle', 'blue pool tiles and white plumbing pipes stacked next to an unfinished pool')
    C = {}
    C['piscina'] = clip_pexels('piscina', 'swimming pool garden aerial', 3)
    C['acqua'] = clip_pexels('acqua', 'swimming pool water surface sunlight', 3)
    C['calcolo'] = clip_pexels('calcolo', 'calculator bills hands', 3)
    C['escavatore'] = clip_pexels('escavatore', 'excavator digging soil', 3)
    shots = inquadrature(T, I, C)
    frames = {c: fotogrammi_clip(c) for c in C.values() if c}
    for st in (E('STILI') or 'ABC'):
        muto = rendi(st, T, shots, frames)
        au = audio(st, T)
        fin = os.path.join(OUT, f'stile_{st}.mp4')
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', muto, '-i', au, '-map', '0:v', '-map', '1:a', '-vf', 'scale=2560:1440:flags=lanczos',
                        '-c:v', 'libx264', '-preset', 'slow', '-crf', '23', '-maxrate', '5M', '-bufsize', '10M', '-pix_fmt', 'yuv420p', '-c:a', 'copy', '-shortest', fin], check=True)   # prova: sotto i 50 MB per GitHub
        for k, tt in enumerate((3, 12, 22, 33, 45)):
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', str(tt), '-i', fin, '-frames:v', '1', '-vf', 'scale=960:-2', os.path.join(OUT, f'stile_{st}_f{k}.jpg')])
        log('FATTO', fin)
    log('COSTO:', CO.riepilogo() if hasattr(CO, 'riepilogo') else '')


if __name__ == '__main__':
    main()
