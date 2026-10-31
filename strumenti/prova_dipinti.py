#!/usr/bin/env python3
"""
PROVA DIPINTI (per tutti i canali) — video di prova breve fatto con DIPINTI DI PUBBLICO DOMINIO (Wikimedia Commons, solo licenze
libere verificate: Public domain / PD / CC0) piu' clip Pexels in movimento dove servono (forgia, fuoco, acqua, cielo).
Niente cartoni, niente AI. Ogni inquadratura e' un'immagine DIVERSA (mai la stessa, nemmeno con un altro zoom), con movimento
di camera (avvicinamento a un dettaglio, panoramica), inquadrature al massimo di 'max_secondi'.
PAYLOAD = {"nome": "...", "voce": "<id ElevenLabs>", "velocita": 1.08, "stabilita": 0.4, "stile_voce": 0.25, "musica": "epico_002.mp3",
           "max_secondi": 3.0, "scene": [{"testo": "...", "q": ["ricerca Commons", ...], "pexels": "ricerca clip (facoltativa)", "scritta": ""}]}
Uscita: prove_video/archivio/<nome>/ (prova.mp4, fotogrammi.jpg, fonti.txt con autore e licenza di ogni immagine, costi.txt)
"""
import base64, hashlib, io, json, os, random, re, subprocess, time, urllib.parse, urllib.request
from PIL import Image, ImageDraw, ImageFont

E = os.environ.get
P = json.loads(E('PAYLOAD') or '{}')
CART = os.path.join('prove_video', 'archivio', P.get('nome') or 'dipinti'); os.makedirs(CART, exist_ok=True)
LAV = '/tmp/pd'; os.makedirs(LAV, exist_ok=True)
MAXS = float(P.get('max_secondi') or 3.0)
W, H, FPS = 1920, 1080, 30
UA = {'User-Agent': 'ambience-prova-dipinti/1.0 (gggweb23@gmail.com)'}
random.seed(11)
log = lambda *a: print(time.strftime('%H:%M:%S'), *a, flush=True)
LIBERE = re.compile(r'public domain|^pd|cc0|cc-zero|no restrictions', re.I)
NO_FILE = re.compile(r'\.(svg|pdf|djvu|tif|tiff|gif)$|map|diagram|chart|coat of arms|logo|flag|book|page|letter|manuscript page|signature|stamp|coin|'
                     r'\bIMO\b|ship|vessel|boat|DSC|IMG_|\bphoto|museum|exhibit|statue of|car\b|train|aircraft', re.I)   # foto moderne, navi col nome della spada...


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
cache = os.path.join(LAV, 'voce_' + hashlib.md5(testo.encode()).hexdigest()[:10] + '.json')
if os.path.exists(cache):
    j = json.load(open(cache))
else:
    j = get(f"https://api.elevenlabs.io/v1/text-to-speech/{P.get('voce')}/with-timestamps?output_format=mp3_44100_128",
            {'text': testo, 'model_id': 'eleven_multilingual_v2',
             'voice_settings': {'stability': float(P.get('stabilita') or .4), 'similarity_boost': .75, 'style': float(P.get('stile_voce') or .25),
                                'speed': float(P.get('velocita') or 1.08)}}, {'xi-api-key': E('ELEVENLABS_API_KEY', '')})
    json.dump(j, open(cache, 'w'))
VOCE = os.path.join(LAV, 'voce.mp3'); open(VOCE, 'wb').write(base64.b64decode(j['audio_base64']))
al = j['alignment']; ts = al['character_start_times_seconds']; te = al['character_end_times_seconds']
pos, inizi = 0, []
for s in scene:
    inizi.append(0.0 if not inizi else ts[min(pos, len(ts) - 1)]); pos += len(s['testo'].strip()) + 1
fine = te[-1] + 0.8
tempi = [(inizi[k], inizi[k + 1] if k + 1 < len(inizi) else fine) for k in range(len(scene))]
log('voce', round(te[-1], 1), 's')

# ---------------- 2) fonti ----------------
USATI = set()


def commons(q, quanti):
    """Dipinti con licenza LIBERA verificata, grandi, mai gia' usati."""
    out = []
    try:
        j = get('https://commons.wikimedia.org/w/api.php?' + urllib.parse.urlencode({
            'action': 'query', 'format': 'json', 'generator': 'search', 'gsrnamespace': 6, 'gsrsearch': q, 'gsrlimit': 40,
            'prop': 'imageinfo', 'iiprop': 'url|size|extmetadata', 'iiurlwidth': 2400}))
    except Exception as e:
        log('Commons non risponde per', q, str(e)[:80]); return out
    pagine = sorted((j.get('query') or {}).get('pages', {}).values(), key=lambda p: p.get('index', 99))
    for p in pagine:
        t = p.get('title', ''); ii = (p.get('imageinfo') or [{}])[0]; m = ii.get('extmetadata') or {}
        lic = (m.get('LicenseShortName') or {}).get('value', '') + ' ' + (m.get('License') or {}).get('value', '')
        if t in USATI or NO_FILE.search(t) or not LIBERE.search(lic.strip()) or min(ii.get('width', 0), ii.get('height', 0)) < 900:
            continue
        autore = re.sub(r'<[^>]+>', '', (m.get('Artist') or {}).get('value', ''))[:80]
        out.append({'url': ii.get('thumburl') or ii.get('url'), 'titolo': t[5:], 'licenza': lic.strip()[:40], 'autore': autore})
        USATI.add(t)
        if len(out) >= quanti:
            break
    return out


def pexels(q):
    try:
        j = get('https://api.pexels.com/videos/search?' + urllib.parse.urlencode({'query': q, 'per_page': 15, 'orientation': 'landscape'}),
                h={'Authorization': E('PEXELS_API_KEY', '')})
    except Exception as e:
        log('Pexels non risponde', str(e)[:80]); return None
    for v in j.get('videos', []):
        if v['id'] in USATI or v.get('duration', 0) < 6:
            continue
        f = sorted([x for x in v.get('video_files', []) if (x.get('width') or 0) >= 1280], key=lambda x: x.get('width') or 0)
        if f:
            USATI.add(v['id']); return {'url': f[0]['link'], 'titolo': f"Pexels {v['id']} ({v.get('user', {}).get('name', '')})", 'durata': v['duration']}
    return None


# ---------------- 3) inquadrature ----------------
FONT = os.path.join(LAV, 'anton.ttf')
open(FONT, 'wb').write(get('https://github.com/google/fonts/raw/main/ofl/anton/Anton-Regular.ttf', raw=True))


def scritta_png(t, k):
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im); s = 170
    while d.textlength(t, font=ImageFont.truetype(FONT, s)) > W - 240 and s > 70:
        s -= 6
    d.text((W // 2, H - 90), t, font=ImageFont.truetype(FONT, s), fill='white', stroke_width=s // 11, stroke_fill='black', anchor='md')
    p = os.path.join(LAV, f's_{k}.png'); im.save(p); return p


MOSSE = ['dentro', 'destra', 'fuori', 'sinistra', 'su', 'dettaglio']
pezzi, fonti, nvideo = [], [], 0
for k, (s, (a, b)) in enumerate(zip(scene, tempi)):
    d = b - a; parti = max(1, int(-(-d // MAXS)))
    imgs = []
    for q in (s.get('q') or []):
        imgs += commons(q, parti - len(imgs))
        if len(imgs) >= parti:
            break
    for i in range(parti):
        L0 = d / parti; n = len(pezzi); out = os.path.join(LAV, f'p_{n:03d}.mp4')
        T = .3 if (n + 1) % 3 == 0 else .04   # il pezzo dura un po' di piu' per la transizione verso il successivo
        L = L0 + T
        sc = scritta_png(s['scritta'], n) if (s.get('scritta') and i == 0) else None
        usa_video = s.get('pexels') and (i == 0 or not imgs)
        cv = pexels(s['pexels']) if usa_video else None
        if cv:
            src = os.path.join(LAV, f'v_{n}.mp4'); open(src, 'wb').write(get(cv['url'], raw=True, timeout=300))
            da = random.uniform(1, max(1, cv['durata'] - L - 1))
            vf = f'[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},setsar=1[v]'
            cmd = ['ffmpeg', '-y', '-v', 'error', '-ss', round(da, 2), '-t', round(L, 3), '-i', src]
            fonti.append(f'{n:03d} VIDEO {cv["titolo"]}'); nvideo += 1
        else:
            im_ = imgs.pop(0) if imgs else None
            for q in ([q_ + ' painting' for q_ in s.get('q') or []] + [' '.join(q_.split()[:2]) for q_ in s.get('q') or []] + list(P.get('riserva') or [])):
                if im_:
                    break
                im_ = next(iter(commons(q, 1)), None)   # ricerca piu' larga, poi le riserve del video (sempre a tema)
            if not im_:
                raise RuntimeError('nessun dipinto libero per: ' + str(s.get('q')))
            img = Image.open(io.BytesIO(get(im_['url'], raw=True))).convert('RGB')
            r = max(W * 1.25 / img.width, H * 1.25 / img.height); img = img.resize((int(img.width * r) + 1, int(img.height * r) + 1), Image.LANCZOS)
            srcf = os.path.join(LAV, f'f_{n}.jpg'); img.save(srcf, quality=93)
            fr = int(L * FPS) + 1; m = MOSSE[n % len(MOSSE)]
            # movimento di camera dentro il quadro: avvicinamento, panoramica, allontanamento, salita verso un dettaglio
            z = {'dentro': f"1+0.18*on/{fr}", 'fuori': f"1.18-0.18*on/{fr}", 'dettaglio': f"1.15+0.20*on/{fr}"}.get(m, '1.12')
            x = {'destra': f"(iw-iw/zoom)*on/{fr}", 'sinistra': f"(iw-iw/zoom)*(1-on/{fr})", 'dettaglio': "(iw-iw/zoom)*0.3"}.get(m, 'iw/2-(iw/zoom/2)')
            y = {'su': f"(ih-ih/zoom)*(1-on/{fr})", 'dettaglio': "(ih-ih/zoom)*0.35"}.get(m, 'ih/2-(ih/zoom/2)')
            vf = (f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},scale={W * 2}:{H * 2},"
                  f"zoompan=z='{z}':x='{x}':y='{y}':d={fr}:s={W}x{H}:fps={FPS},setsar=1[v]")
            cmd = ['ffmpeg', '-y', '-v', 'error', '-loop', '1', '-i', srcf]
            fonti.append(f'{n:03d} DIPINTO {im_["titolo"]} | {im_["autore"]} | {im_["licenza"]}')
        if sc:
            cmd += ['-i', sc]; vf += ';[v][1:v]overlay=0:0[v]'
        run(cmd + ['-filter_complex', vf + ';[v]format=yuv420p[o]', '-map', '[o]', '-frames:v', int(round(L * FPS)), '-an', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '19', out])
        pezzi.append((out, L0, T))
        log(f'{n:02d}', fonti[-1][:90])

# ---------------- 4) montaggio: tagli netti con un effetto breve ogni 3 ----------------
EFF = ['fadeblack', 'fadewhite', 'zoomin', 'dissolve', 'slideleft', 'circleopen']
ins, fl, acc, prec = [], [], 0.0, '0:v'
for p, L, T in pezzi:
    ins += ['-i', p]
for i in range(1, len(pezzi)):
    acc += pezzi[i - 1][1]; T = pezzi[i - 1][2]
    t = EFF[(i // 3) % len(EFF)] if T > .1 else 'fade'
    fl.append(f'[{prec}][{i}:v]xfade=transition={t}:duration={T}:offset={acc:.3f}[x{i}]'); prec = f'x{i}'
fl.append(f'[{prec}]vignette=angle=PI/5,noise=alls=4:allf=t,format=yuv420p[vf]')
muto = os.path.join(LAV, 'muto.mp4')
run(['ffmpeg', '-y', '-v', 'error'] + ins + ['-filter_complex', ';'.join(fl), '-map', '[vf]', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '22', muto])
mus = os.path.join('libreria_musica', P.get('musica') or 'epico_002.mp3')
OUT = os.path.join(CART, 'prova.mp4')
run(['ffmpeg', '-y', '-v', 'error', '-i', muto, '-i', VOCE, '-stream_loop', '-1', '-i', mus, '-filter_complex',
     f'[1:a]aformat=sample_rates=44100:channel_layouts=stereo[v];[2:a]aformat=sample_rates=44100:channel_layouts=stereo,volume=0.08,afade=t=out:st={fine - 1.5:.2f}:d=1.5[m];'
     f'[v][m]amix=inputs=2:duration=first:normalize=0[a]', '-map', '0:v', '-map', '[a]', '-t', round(fine, 2), '-c:v', 'copy', '-c:a', 'aac', '-b:a', '160k', OUT])

# ---------------- 5) controlli ----------------
fot = []
for i, (p, L, _) in enumerate(pezzi):
    q = p[:-4] + '.png'; run(['ffmpeg', '-y', '-v', 'error', '-ss', f'{L / 2:.2f}', '-i', p, '-frames:v', 1, '-vf', 'scale=384:216', q]); fot.append(q)
col = 5; G = Image.new('RGB', (col * 390, ((len(fot) + col - 1) // col) * 222), 'black'); dg = ImageDraw.Draw(G)
for i, q in enumerate(fot):
    G.paste(Image.open(q), ((i % col) * 390, (i // col) * 222)); dg.text(((i % col) * 390 + 6, (i // col) * 222 + 4), str(i), fill='yellow')
G.save(os.path.join(CART, 'fotogrammi.jpg'), quality=85)
quota = 100 * sum(L for (p, L, _), f in zip(pezzi, fonti) if ' VIDEO ' in f) / max(.1, sum(L for p, L, _ in pezzi))
open(os.path.join(CART, 'fonti.txt'), 'w').write('\n'.join(fonti) + '\n')
open(os.path.join(CART, 'costi.txt'), 'w').write(f'ElevenLabs: {len(testo)} crediti | Commons e Pexels: 0 | Claude: 0 (testo nel payload)\n'
                                                f'inquadrature: {len(pezzi)} | durata {fine:.1f} s | media {fine / len(pezzi):.1f} s | clip video: {quota:.0f}% | dipinti con movimento: {100 - quota:.0f}%\n')
log('FATTO', OUT)
