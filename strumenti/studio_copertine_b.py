#!/usr/bin/env python3
"""STUDIO COPERTINE STILE B (etichetta rossa) prima di accendere un canale d'archivio: per ogni titolo un fotogramma vero della libreria,
ritocco AI (fal seedream edit, ~0,04 $ l'una) in bianco e nero d'epoca con personaggio INVENTATO, poi fascia rossa con la frase
(stessa resa del motore video_archivio). Esce anche il foglio "come da telefono".
PAYLOAD = {"nome": "wwii_testimony", "libreria": "guerra_ww2", "max_spesa": 0.15,
           "copertine": [{"titolo": "...", "testo": "ONE CITY.", "clip_n": 4, "prompt": "scena della copertina"}]}"""
import base64, io, json, os, subprocess, time, urllib.request
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageEnhance

P = json.loads(os.environ.get('PAYLOAD') or '{}')
CART = os.path.join('prove_archivi', P.get('nome') or 'studio_b'); os.makedirs(CART, exist_ok=True)
LAV = '/tmp/scb'; os.makedirs(LAV, exist_ok=True)
H = {'Authorization': 'Key ' + os.environ.get('FAL_KEY', '')}
log = lambda *a: print(time.strftime('%H:%M:%S'), *a, flush=True)


def get(u, dati=None, h=None, raw=False):
    req = urllib.request.Request(u, data=json.dumps(dati).encode() if dati is not None else None,
                                 headers=dict({'User-Agent': 'ambience-studio-b/1.0', **({'Content-Type': 'application/json'} if dati is not None else {})}, **(h or {})))
    with urllib.request.urlopen(req, timeout=600) as r:
        b = r.read(); return b if raw else json.loads(b.decode() or '{}')


FP = os.path.join(LAV, 'anton.ttf'); open(FP, 'wb').write(get('https://github.com/google/fonts/raw/main/ofl/anton/Anton-Regular.ttf', raw=True))
LIB = {x['n']: x for x in json.load(open(os.path.join('libreria_clip', P['libreria'], 'indice.json')))}
spesa, fatte = 0.0, []
for k, cp in enumerate(P['copertine'], 1):
    x = LIB[int(cp['clip_n'])]; v = os.path.join(LAV, f'c{k}.mp4'); f = os.path.join(LAV, f'f{k}.jpg')
    open(v, 'wb').write(get(x['url'], raw=True))
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-ss', str(float(x['da']) + 1.5), '-i', v, '-frames:v', '1', f])
    w0, h0 = Image.open(f).size
    im = Image.open(f).convert('RGB'); nh = int(im.width * 9 / 16)
    im = (im.crop((0, (im.height - nh) // 2, im.width, (im.height - nh) // 2 + nh)) if im.height > nh else im).resize((1280, 720))
    if spesa + 0.04 <= float(P.get('max_spesa') or 0.15) and os.environ.get('FAL_KEY'):
        spesa += 0.04; buf = io.BytesIO(); im.save(buf, 'JPEG', quality=90)
        prompt = ('Use the reference photo only for the setting and the era. ' + cp['prompt'] +
                  ' Black and white 1940s archival photograph look, real film grain, documentary realism. The person is FICTIONAL and does not resemble any real '
                  'historical figure. No swastikas, no Nazi flags or armbands, no insignia, no text, no letters, no logos. The face is big and sharp, head and shoulders '
                  'filling the RIGHT 60% of the frame, strong readable emotion; the LEFT 40% simpler and darker.')
        try:
            inv = get('https://queue.fal.run/fal-ai/bytedance/seedream/v4.5/edit', {'prompt': prompt, 'image_urls': ['data:image/jpeg;base64,' + base64.b64encode(buf.getvalue()).decode()],
                                                                                    'image_size': {'width': 2560, 'height': 1440}, 'num_images': 1}, H)
            for _ in range(120):
                time.sleep(4); st = get(inv['status_url'], h=H)
                if st.get('status') == 'COMPLETED':
                    im = Image.open(io.BytesIO(get(get(inv['response_url'], h=H)['images'][0]['url'], raw=True))).convert('RGB').resize((1280, 720)); break
                if st.get('status') not in ('IN_QUEUE', 'IN_PROGRESS'):
                    log('ritocco non riuscito', st); break
        except Exception as e:
            log('ritocco non riuscito', str(e)[:150])
    im.save(os.path.join(CART, f'base_{k}.jpg'), quality=88)
    im = ImageEnhance.Contrast(ImageOps.grayscale(im).convert('RGB')).enhance(1.25); d = ImageDraw.Draw(im)
    parole = cp['testo'].upper().split()
    righe = [' '.join(parole)] if len(parole) <= 3 else [' '.join(parole[:len(parole) // 2]), ' '.join(parole[len(parole) // 2:])]
    s_ = 120
    while s_ > 80 and max(d.textlength(r_, font=ImageFont.truetype(FP, s_)) for r_ in righe) > 700:
        s_ -= 4
    fnt = ImageFont.truetype(FP, s_); hb = d.textbbox((0, 0), 'ABC', font=fnt)
    y = 720 - 50 - ((hb[3] - hb[1]) + 46) * len(righe)
    for r_ in righe:
        l_, t_, rr_, b_ = d.textbbox((0, 0), r_, font=fnt)
        d.rectangle((40, y, 40 + (rr_ - l_) + 44, y + (b_ - t_) + 36), fill=(200, 22, 22))
        d.text((62 - l_, y + 18 - t_), r_, font=fnt, fill='white')
        y += (b_ - t_) + 36 + 10
    im.save(os.path.join(CART, f'copertina_{k}.jpg'), quality=92); fatte.append((im, cp['titolo']))
    log(k, cp['titolo'], '| spesa finora', f'{spesa:.2f} $')
# come da telefono: copertina larga 340 px con il titolo sotto
T = Image.new('RGB', (len(fatte) * 360 + 20, 290), 'white'); dt = ImageDraw.Draw(T)
fs = ImageFont.truetype(FP, 15)
for i, (im, tit) in enumerate(fatte):
    T.paste(im.resize((340, 191), Image.LANCZOS), (20 + i * 360, 15))
    parole, riga, yy = tit.split(), '', 215
    for w in parole:
        if dt.textlength(riga + ' ' + w, font=fs) > 335:
            dt.text((20 + i * 360, yy), riga.strip(), font=fs, fill='black'); yy += 20; riga = ''
        riga += ' ' + w
    dt.text((20 + i * 360, yy), riga.strip(), font=fs, fill='black')
T.save(os.path.join(CART, 'telefono.jpg'), quality=92)
open(os.path.join(CART, 'costi.txt'), 'a').write(time.strftime('%Y-%m-%d %H:%M') + f' | studio copertine B: {len(fatte)} copertine | spesa {spesa:.2f} $\n')
