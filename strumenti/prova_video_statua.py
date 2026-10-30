#!/usr/bin/env python3
"""PROVA VIDEO "STATUA + TESTO" (stile copertina = stile video): la statua della copertina ferma a SINISTRA,
a DESTRA il testo grande con lo stesso font e gli stessi colori della copertina; la parola detta in quel momento
si accende del colore d'accento (karaoke, tempi presi dalla voce ElevenLabs).
PAYLOAD = {"cartella": "prove_video/Agora_of_Sages/video_30s", "immagine": "prove_video/.../SJ_A2.png",
           "testo": "...", "voce": "ppLqTilh7rH7fbUVlXsf", "modello_voce": "eleven_multilingual_v2",
           "font_url": "https://cdn.jsdelivr.net/gh/google/fonts@main/ofl/anton/Anton-Regular.ttf",
           "colore_testo": "#FFFFFF", "colore_accento": "#39FF14", "maiuscolo": "SI", "lufs": -14,
           "caratteri_riga": 13, "righe_max": 3, "specchia": "SI", "firma": "AGORA OF SAGES"}"""
import base64, json, os, re, subprocess, urllib.request
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

P = json.loads(os.environ.get('PAYLOAD') or '{}')
CART = P.get('cartella') or 'prove_video/prova_statua'; os.makedirs(CART, exist_ok=True)
LAV = 'lavoro_statua'; os.makedirs(LAV, exist_ok=True)
W, H, FPS = 1920, 1080, 30
K = os.environ['ELEVENLABS_API_KEY']


def log(*a):
    print(*a, flush=True)
    open(os.path.join(CART, 'log.txt'), 'a').write(' '.join(str(x) for x in a) + '\n')


def esa(c):
    c = c.lstrip('#'); return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def ass_col(c):
    r, g, b = esa(c); return f'&H00{b:02X}{g:02X}{r:02X}&'


# 1) font della copertina
fnt = os.path.join(LAV, 'font', 'copertina.ttf'); os.makedirs(os.path.dirname(fnt), exist_ok=True)
open(fnt, 'wb').write(urllib.request.urlopen(P.get('font_url') or 'https://cdn.jsdelivr.net/gh/google/fonts@main/ofl/anton/Anton-Regular.ttf', timeout=60).read())
from PIL import ImageFont as _F
NOME_FONT = _F.truetype(fnt, 20).getname()[0]
log('font:', NOME_FONT)

# 2) voce con i tempi di ogni lettera
testo = re.sub(r'\s+', ' ', P['testo']).strip()
cache_v, cache_j = os.path.join(CART, 'voce.mp3'), os.path.join(CART, 'voce.json')
if os.path.exists(cache_v) and os.path.exists(cache_j) and json.load(open(cache_j)).get('testo') == testo and json.load(open(cache_j)).get('voce') == P.get('voce'):
    r = json.load(open(cache_j)); r['audio_base64'] = base64.b64encode(open(cache_v, 'rb').read()).decode()
    log('voce gia\' pronta: riusata (nessun credito)')
else:
    r = None
if r is None:
  req = urllib.request.Request(f"https://api.elevenlabs.io/v1/text-to-speech/{P.get('voce') or 'ppLqTilh7rH7fbUVlXsf'}/with-timestamps",
                             data=json.dumps({'text': testo, 'model_id': P.get('modello_voce') or 'eleven_multilingual_v2',
                                              'voice_settings': {'stability': 0.5, 'similarity_boost': 0.8, 'style': 0.2}}).encode(),
                             headers={'xi-api-key': K, 'Content-Type': 'application/json'})
  r = json.loads(urllib.request.urlopen(req, timeout=300).read())
  open(cache_v, 'wb').write(base64.b64decode(r['audio_base64']))
  json.dump({'testo': testo, 'voce': P.get('voce'), 'alignment': r.get('alignment'), 'normalized_alignment': r.get('normalized_alignment')}, open(cache_j, 'w'))
voce = os.path.join(LAV, 'voce.mp3'); open(voce, 'wb').write(base64.b64decode(r['audio_base64']))
al = r.get('alignment') or r.get('normalized_alignment')
ch, t0s, t1s = al['characters'], al['character_start_times_seconds'], al['character_end_times_seconds']
parole, cur = [], None
for c, a, b in zip(ch, t0s, t1s):
    if c.isspace():
        if cur: parole.append(cur); cur = None
        continue
    if cur is None: cur = [c, a, b]
    else: cur[0] += c; cur[2] = b
if cur: parole.append(cur)
durata = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', voce], capture_output=True, text=True).stdout)
log(f'voce: {durata:.1f} s, {len(parole)} parole')

# 3) sfondo: la statua della copertina a sinistra (specchiata se in copertina e' a destra), lato testo scurito
im = Image.open(P['immagine']).convert('RGB')
if str(P.get('bn') or 'SI').upper() == 'SI':   # stesso trattamento della copertina: bianco e nero contrastato
    g = ImageOps.autocontrast(ImageOps.grayscale(im), cutoff=0.5).point(lambda v: int(255 * (v / 255) ** 0.8))
    im = ImageEnhance.Contrast(g.convert('RGB')).enhance(1.1)
if str(P.get('specchia') or 'NO').upper() == 'SI':
    im = ImageOps.mirror(im)
alt = int(H * 1.06); im = im.resize((int(im.width * alt / im.height), alt), Image.LANCZOS)
bg = im.getpixel((im.width - 8, im.height // 3))
c = Image.new('RGB', (W, H), bg)
m = Image.new('L', im.size, 255); dm = ImageDraw.Draw(m)
for x in range(160):
    dm.line([(im.width - 1 - x, 0), (im.width - 1 - x, im.height)], fill=int(255 * x / 160))
c.paste(im, (0, -int(H * .02)), m)
v = Image.new('L', (W, H), 0); ImageDraw.Draw(v).rectangle([W * .5, 0, W, H], fill=150)
c = Image.composite(Image.new('RGB', (W, H), (8, 8, 10)), c, v.filter(ImageFilter.GaussianBlur(170)))
if P.get('firma'):
    d = ImageDraw.Draw(c)
    try:
        f = ImageFont.truetype(fnt, 30)
        d.text((W - 60, H - 50), P['firma'], font=f, fill=esa(P.get('colore_accento') or '#39FF14'), anchor='rm')
    except Exception:
        pass
sfondo = os.path.join(LAV, 'sfondo.png'); c.save(sfondo)

# 4) testo a destra: blocchi di max N righe; la parola detta si accende del colore d'accento
MAI = str(P.get('maiuscolo') or 'SI').upper() == 'SI'
CR, RM = int(P.get('caratteri_riga') or 13), int(P.get('righe_max') or 3)
bianco, accento = ass_col(P.get('colore_testo') or '#FFFFFF'), ass_col(P.get('colore_accento') or '#39FF14')
blocchi, righe, riga = [], [], []
for i, (w, a, b) in enumerate(parole):
    ww = w.upper() if MAI else w
    if riga and len(' '.join(x[1] for x in riga + [(i, ww)])) > CR:
        righe.append(riga); riga = []
        if len(righe) == RM:
            blocchi.append(righe); righe = []
    riga.append((i, ww))
    if re.search(r'[.!?]$', w):   # fine frase: blocco nuovo
        righe.append(riga); riga = []; blocchi.append(righe); righe = []
if riga: righe.append(riga)
if righe: blocchi.append(righe)
size = int(P.get('dimensione') or 150)
xc, yc = int(W * float(P.get('x_testo') or .74)), int(H * .5)
ev = []
for bl in blocchi:
    idx = [i for rg in bl for i, _ in rg]
    for k, i in enumerate(idx):
        inizio = parole[i][1] if k else max(0, parole[i][1] - .05)
        fine = parole[idx[k + 1]][1] if k + 1 < len(idx) else (parole[idx[-1]][2] + .25)
        testo_ass = '\\N'.join(' '.join(('{\\c' + (accento if j == i else bianco) + '}') + w for j, w in rg) for rg in bl)
        ev.append((inizio, fine, testo_ass))
for k in range(len(ev) - 1):   # niente buchi tra un blocco e l'altro
    ev[k] = (ev[k][0], max(ev[k][1], ev[k + 1][0]) if ev[k + 1][0] - ev[k][1] < .6 else ev[k][1], ev[k][2])


def ts(s):
    s = max(0, s); return f'{int(s // 3600)}:{int(s % 3600 // 60):02d}:{s % 60:05.2f}'


ass = ['[Script Info]', 'ScriptType: v4.00+', f'PlayResX: {W}', f'PlayResY: {H}', 'WrapStyle: 2', '', '[V4+ Styles]',
       'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, '
       'ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding',
       f'Style: T,{NOME_FONT},{size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,0,0,0,0,100,100,1,0,1,3,6,5,0,0,0,1', '',
       '[Events]', 'Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text']
for a, b, t in ev:
    ass.append(f'Dialogue: 0,{ts(a)},{ts(b)},T,,0,0,0,,{{\\pos({xc},{yc})}}{t}')
pa = os.path.join(LAV, 'testo.ass'); open(pa, 'w').write('\n'.join(ass) + '\n')

# 5) MOVIMENTO: effetti sopra la statua ferma (cenere, zoom lento, fumo, luce che respira)
import math, random


def strato_cenere(dur, out):
    """cenere grigio-chiara che sale lenta, fiocchi di 3 grandezze (i grandi sfocati = piu' vicini). Si somma (schiarisci)."""
    rnd = random.Random(11); w, h = W // 2, H // 2; nf = int(dur * FPS)
    parts = []
    for _ in range(140):
        z = rnd.choice((1, 1, 1, 2, 2, 3))
        parts.append({'x': rnd.uniform(0, w), 'y0': rnd.uniform(0, h), 'v': rnd.uniform(6, 16) * z, 'r': rnd.uniform(.6, 1.3) * z,
                      'dx': rnd.uniform(-5, 5), 'f': rnd.uniform(.2, .9), 'fase': rnd.uniform(0, 6.3), 'z': z})
    pr = subprocess.Popen(['ffmpeg', '-y', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{w}x{h}', '-r', str(FPS), '-i', '-',
                           '-vf', f'scale={W}:{H}', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p', out], stdin=subprocess.PIPE)
    for i in range(nf):
        t = i / FPS
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


def strato_fumo(out, secondi=20):
    """nebbia bassa che scorre piano da sinistra a destra (texture larga che scorre in loop)"""
    rnd = random.Random(5); tw, th = W * 2, H
    tex = Image.new('L', (tw // 8, th // 8))
    tex.putdata([rnd.randint(0, 255) for _ in range((tw // 8) * (th // 8))])
    tex = tex.resize((tw, th), Image.BICUBIC).filter(ImageFilter.GaussianBlur(60))
    tex = ImageOps.autocontrast(tex)
    grad = Image.linear_gradient('L').resize((tw, th))   # piu' denso in basso
    tex = Image.composite(tex, Image.new('L', (tw, th)), grad).point(lambda v: int(v * .55))
    Image.merge('RGB', [tex] * 3).save(os.path.join(LAV, 'fumo.png'))
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-loop', '1', '-i', os.path.join(LAV, 'fumo.png'), '-t', str(secondi), '-r', str(FPS),
                    '-vf', f"crop={W}:{H}:x='(t/{secondi})*{W}':y=0,format=yuv420p", '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '22', out], check=True)
    return out


def monta(effetti, nome_out):
    dur = durata + .4
    ingr = ['-loop', '1', '-framerate', str(FPS), '-i', sfondo, '-i', voce]
    if 'zoom' in effetti:   # spinta lenta in avanti (1,00 -> 1,06), centrata sulla statua
        nf = int(dur * FPS)
        base = (f"[0:v]scale={W * 2}:{H * 2},zoompan=z='1+0.06*on/{nf}':x='(iw-iw/zoom)*0.3':y='(ih-ih/zoom)*0.35':"
                f"d=1:s={W}x{H}:fps={FPS}[b0]")
    else:
        base = '[0:v]null[b0]'
    f, cur, n = base, '[b0]', 2
    if 'respiro' in effetti:
        f += f";{cur}eq=brightness='0.025*sin(2*PI*t/6)':eval=frame[br]"; cur = '[br]'
    if 'fumo' in effetti:
        ingr += ['-stream_loop', '-1', '-i', strato_fumo(os.path.join(LAV, 'fumo.mp4'))]
        f += f";[{n}:v]format=gbrp[fm];{cur}format=gbrp[bb];[bb][fm]blend=all_mode=screen:all_opacity=0.45,format=yuv420p[fu]"; cur = '[fu]'; n += 1
    if 'cenere' in effetti:
        cen = os.path.join(LAV, 'cenere.mp4')
        if not os.path.exists(cen):
            strato_cenere(12, cen)
        ingr += ['-stream_loop', '-1', '-i', cen]
        f += f";[{n}:v]format=gbrp[cn];{cur}format=gbrp[bc];[bc][cn]blend=all_mode=lighten,format=yuv420p[ce]"; cur = '[ce]'; n += 1
    f += f";{cur}ass={pa}:fontsdir={os.path.dirname(fnt)},format=yuv420p[v];[1:a]loudnorm=I={lufs}:TP=-1.0:LRA=11,aresample=48000[a]"
    out = os.path.join(LAV, nome_out)
    subprocess.run(['ffmpeg', '-y', '-v', 'error'] + ingr + ['-filter_complex', f, '-map', '[v]', '-map', '[a]', '-t', f'{dur:.2f}',
                    '-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', out], check=True)
    os.replace(out, os.path.join(CART, nome_out))
    log('pronto:', nome_out, effetti)


lufs = float(P.get('lufs') or -14)
varianti = P.get('varianti') or {'video': P.get('effetti') or []}
for nome, eff in varianti.items():
    monta(eff, nome + '.mp4')
primo = os.path.join(CART, list(varianti)[0] + '.mp4')
for i, tt in enumerate([1.5, durata * .35, durata * .65, durata - 1], 1):
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-ss', f'{tt:.2f}', '-i', primo, '-frames:v', '1',
                    '-vf', 'scale=960:-1', os.path.join(CART, f'fotogramma_{i}.jpg')])
log('FATTO')
