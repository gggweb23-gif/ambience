#!/usr/bin/env python3
"""
PROVA ARCHIVIO (per tutti i canali) — video di prova breve fatto SOLO con archivi gratuiti (oggi: NASA), niente cartoni.
Serve a vedere un formato PRIMA di aprire un canale.
- copione gia' scritto nel PAYLOAD (nessun costo Claude), diviso in inquadrature con la ricerca d'archivio di ciascuna
- voce ElevenLabs con i tempi di ogni lettera -> ogni immagine cambia esattamente quando cambia la frase
- inquadrature MAI oltre 'max_secondi' (se una frase dura di piu', si divide su piu' immagini diverse)
- la stessa immagine non torna mai due volte nel video
- clip video NASA dove richiesto ("clip": true), altrimenti foto con movimento lento alternato (avanti / indietro / laterale)
- musica bassa dalla libreria, nessun altro suono
PAYLOAD = {"nome": "astronauti_it", "voce": "<id ElevenLabs>", "velocita": 1.06, "musica": "curiosita_001.mp3", "volume_musica": 0.07,
           "max_secondi": 4, "scene": [{"testo": "...", "q": "ricerca NASA", "scritta": "FACOLTATIVA", "clip": false}]}
Uscita: prove_video/archivio/<nome>/ (prova.mp4, fotogrammi.jpg, fonti.txt, costi.txt)
"""
import base64, io, json, os, subprocess, time, urllib.parse, urllib.request
from PIL import Image, ImageDraw, ImageFont

E = os.environ.get
P = json.loads(E('PAYLOAD') or '{}')
CART = os.path.join('prove_video', 'archivio', P.get('nome') or 'prova'); os.makedirs(CART, exist_ok=True)
LAV = '/tmp/lav'; os.makedirs(LAV, exist_ok=True)
MAXS = float(P.get('max_secondi') or 4)
W, H, FPS = 1920, 1080, 30
UA = {'User-Agent': 'ambience-prova-archivio/1.0 (gggweb23@gmail.com)'}
log = lambda *a: print(time.strftime('%H:%M:%S'), *a, flush=True)


def get(u, dati=None, h=None, raw=False, timeout=120):
    req = urllib.request.Request(u, data=json.dumps(dati).encode() if dati is not None else None,
                                 headers=dict(UA, **({'Content-Type': 'application/json'} if dati is not None else {}), **(h or {})))
    with urllib.request.urlopen(req, timeout=timeout) as r:
        b = r.read()
        return b if raw else json.loads(b.decode() or '{}')


def run(c):
    subprocess.run([str(x) for x in c], check=True)


# ---------------- 1) voce con i tempi ----------------
scene = P['scene']
testo = ' '.join(s['testo'].strip() for s in scene)
j = get(f"https://api.elevenlabs.io/v1/text-to-speech/{P.get('voce') or 'glnsgBC77wt5zOYU0szz'}/with-timestamps?output_format=mp3_44100_128",
        {'text': testo, 'model_id': 'eleven_multilingual_v2',
         'voice_settings': {'stability': .5, 'similarity_boost': .75, 'speed': float(P.get('velocita') or 1.06)}},
        {'xi-api-key': E('ELEVENLABS_API_KEY', '')})
VOCE = os.path.join(LAV, 'voce.mp3'); open(VOCE, 'wb').write(base64.b64decode(j['audio_base64']))
al = j['alignment']; ts = al['character_start_times_seconds']; te = al['character_end_times_seconds']
durata_voce = te[-1]
pos, inizi = 0, []
for s in scene:
    inizi.append(0.0 if not inizi else ts[min(pos, len(ts) - 1)])
    pos += len(s['testo'].strip()) + 1
fine_tot = durata_voce + 0.8
tempi = [(inizi[k], inizi[k + 1] if k + 1 < len(inizi) else fine_tot) for k in range(len(scene))]
log('voce', round(durata_voce, 1), 's,', len(testo), 'caratteri')

# ---------------- 2) archivio NASA ----------------
USATI = set()


def nasa(q, tipo):
    r = get('https://images-api.nasa.gov/search?' + urllib.parse.urlencode({'q': q, 'media_type': tipo}))
    return r.get('collection', {}).get('items', [])


def foto(q):
    for it in nasa(q, 'image'):
        nid = it['data'][0]['nasa_id']
        if nid in USATI:
            continue
        href = (it.get('links') or [{}])[0].get('href', '')
        for v in ('~large.', '~medium.', '~orig.'):
            try:
                im = Image.open(io.BytesIO(get(href.replace('~thumb.', v), raw=True))).convert('RGB')
            except Exception:
                continue
            if im.width < 900 or im.width < im.height:      # niente foto piccole o verticali
                break
            USATI.add(nid); return im, nid, it['data'][0].get('title', '')
    return None


def clip(q, dur):
    for it in nasa(q, 'video')[:6]:
        nid = it['data'][0]['nasa_id']
        if nid in USATI:
            continue
        try:
            files = get(it['href'])
            mp4 = next((f for suf in ('~small.mp4', '~mobile.mp4', '~medium.mp4') for f in files if f.endswith(suf)), None)
            if not mp4:
                continue
            p = os.path.join(LAV, nid.replace('/', '_') + '.mp4')
            open(p, 'wb').write(get(mp4.replace('http://', 'https://'), raw=True, timeout=300))
            lung = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', p],
                                        capture_output=True, text=True).stdout.strip() or 0)
            if lung < dur + 2:
                continue
            USATI.add(nid); return p, lung, nid, it['data'][0].get('title', '')
        except Exception as e:
            log('clip non usata', nid, str(e)[:80])
    return None


# ---------------- 3) scritte ----------------
FONT = os.path.join(LAV, 'anton.ttf')
open(FONT, 'wb').write(get('https://github.com/google/fonts/raw/main/ofl/anton/Anton-Regular.ttf', raw=True))


def scritta_png(t, k):
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    s = 150; f = ImageFont.truetype(FONT, s)
    while d.textlength(t, font=f) > W - 200 and s > 70:
        s -= 6; f = ImageFont.truetype(FONT, s)
    d.text((W // 2, 70), t, font=f, fill=(255, 255, 255), stroke_width=s // 12, stroke_fill=(0, 0, 0), anchor='ma')
    p = os.path.join(LAV, f'scritta_{k}.png'); im.save(p); return p


# ---------------- 4) inquadrature ----------------
pezzi, fonti, n = [], [], 0
MOTI = ['avanti', 'indietro', 'destra', 'sinistra']
for k, (s, (a, b)) in enumerate(zip(scene, tempi)):
    dur = b - a
    parti = max(1, int(-(-dur // MAXS)))          # quante immagini servono per non superare MAXS
    d1 = dur / parti
    for i in range(parti):
        out = os.path.join(LAV, f'p_{n:03d}.mp4')
        sc = scritta_png(s['scritta'], n) if (s.get('scritta') and i == 0) else None
        fatto = False
        if s.get('clip') and i == 0:
            c = clip(s['q'], d1)
            if c:
                p, lung, nid, tit = c
                da = min(max(1.0, lung * .25), lung - d1 - .5)
                filt = f'[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},setsar=1[v]'
                cmd = ['ffmpeg', '-y', '-v', 'error', '-ss', round(da, 2), '-t', round(d1, 3), '-i', p]
                if sc:
                    cmd += ['-i', sc]; filt += ';[v][1:v]overlay=0:0[v]'
                run(cmd + ['-filter_complex', filt, '-map', '[v]', '-an', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p', out])
                fonti.append(f'{n:03d} CLIP {nid} | {tit}'); fatto = True
        if not fatto:
            f_ = foto(s['q']) or foto(s['q'].split()[0] + ' ' + s['q'].split()[-1])
            if not f_:
                raise RuntimeError('nessuna immagine NASA per: ' + s['q'])
            im, nid, tit = f_
            # riempie 16:9 a doppia risoluzione (movimento fluido), poi movimento lento
            r = max(W * 2 / im.width, H * 2 / im.height); im = im.resize((int(im.width * r) + 1, int(im.height * r) + 1), Image.LANCZOS)
            x0, y0 = (im.width - W * 2) // 2, (im.height - H * 2) // 3
            im = im.crop((x0, y0, x0 + W * 2, y0 + H * 2)); src = os.path.join(LAV, f'f_{n:03d}.jpg'); im.save(src, quality=92)
            fr = max(2, int(round(d1 * FPS))); m = MOTI[n % 4]
            z = {'avanti': f"1+0.10*on/{fr}", 'indietro': f"1.10-0.10*on/{fr}"}.get(m, '1.10')
            x = {'destra': f"(iw-iw/zoom)*on/{fr}", 'sinistra': f"(iw-iw/zoom)*(1-on/{fr})"}.get(m, 'iw/2-(iw/zoom/2)')
            filt = f"[0:v]zoompan=z='{z}':x='{x}':y='ih/2-(ih/zoom/2)':d={fr}:s={W}x{H}:fps={FPS},setsar=1[v]"
            cmd = ['ffmpeg', '-y', '-v', 'error', '-i', src]
            if sc:
                cmd += ['-i', sc]; filt += ';[v][1:v]overlay=0:0[v]'
            run(cmd + ['-filter_complex', filt, '-map', '[v]', '-frames:v', fr, '-an', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p', out])
            fonti.append(f'{n:03d} FOTO {nid} | {tit}')
        pezzi.append(out); n += 1
    log('scena', k + 1, 'di', len(scene), round(dur, 1), 's ->', parti, 'inquadrature')

# ---------------- 5) montaggio + audio ----------------
lista = os.path.join(LAV, 'lista.txt'); open(lista, 'w').write(''.join(f"file '{p}'\n" for p in pezzi))
muto = os.path.join(LAV, 'muto.mp4'); run(['ffmpeg', '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', lista, '-c', 'copy', muto])
mus = os.path.join('libreria_musica', P.get('musica') or 'curiosita_001.mp3')
vm = float(P.get('volume_musica') or 0.07)
OUT = os.path.join(CART, 'prova.mp4')
run(['ffmpeg', '-y', '-v', 'error', '-i', muto, '-i', VOCE, '-stream_loop', '-1', '-i', mus, '-filter_complex',
     f'[1:a]aformat=sample_rates=44100:channel_layouts=stereo[v];'
     f'[2:a]aformat=sample_rates=44100:channel_layouts=stereo,volume={vm},afade=t=in:d=1,afade=t=out:st={fine_tot - 1.5:.2f}:d=1.5[m];'
     f'[v][m]amix=inputs=2:duration=first:normalize=0[a]',
     '-map', '0:v', '-map', '[a]', '-t', round(fine_tot, 2), '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '22', '-pix_fmt', 'yuv420p',
     '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', OUT])

# ---------------- 6) controlli ----------------
# un fotogramma a meta' di ogni inquadratura, in griglia, per il controllo visivo
fot = []
for p in pezzi:
    q = p[:-4] + '.png'
    run(['ffmpeg', '-y', '-v', 'error', '-sseof', '-1.2', '-i', p, '-frames:v', 1, '-vf', 'scale=384:216', q]); fot.append(q)
col = 5; G = Image.new('RGB', (col * 390, ((len(fot) + col - 1) // col) * 222), 'black'); dg = ImageDraw.Draw(G)
for i, q in enumerate(fot):
    G.paste(Image.open(q), ((i % col) * 390, (i // col) * 222)); dg.text(((i % col) * 390 + 6, (i // col) * 222 + 4), str(i), fill='yellow')
G.save(os.path.join(CART, 'fotogrammi.jpg'), quality=85)
open(os.path.join(CART, 'fonti.txt'), 'w').write('\n'.join(fonti) + '\n')
open(os.path.join(CART, 'costi.txt'), 'w').write(f'ElevenLabs: {len(testo)} crediti dell\'abbonamento | immagini NASA: 0 | Claude: 0 (copione nel payload) | render GitHub: 0\n'
                                                 f'inquadrature: {len(pezzi)} | durata: {fine_tot:.1f} s | inquadratura media {fine_tot / len(pezzi):.1f} s\n')
log('FATTO', OUT, len(pezzi), 'inquadrature', round(fine_tot, 1), 's')
