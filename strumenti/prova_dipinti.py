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
import base64, hashlib, io, json, os, random, re, subprocess, time, urllib.error, urllib.parse, urllib.request
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
    for k in range(6):   # Wikimedia limita le richieste (429): si aspetta e si riprova, piano
        if 'wikimedia.org' in u or 'wikipedia.org' in u:
            time.sleep(0.6)
        req = urllib.request.Request(u, data=json.dumps(dati).encode() if dati is not None else None,
                                     headers=dict(UA, **({'Content-Type': 'application/json'} if dati is not None else {}), **(h or {})))
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                b = r.read()
                return b if raw else json.loads(b.decode() or '{}')
        except urllib.error.HTTPError as e:
            if e.code != 429 or k == 5:
                raise
            time.sleep(5 * (k + 1))


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

# ---------------- 2) fonti: candidate + CONTROLLO DI COERENZA ----------------
USATI, VISTI = set(), set()
IMPRONTE = []   # impronte visive delle immagini gia' viste
SPESA = {'usd': 0.0}
TEMA = P.get('tema') or ''


def norma(t):   # stesso dipinto in due file ("... repaired.png") = stessa immagine
    t = re.sub(r'\.(jpe?g|png|webm|ogv|tif)$', '', t.lower())
    return re.sub(r'\(.*?\)|repaired|restored|crop(ped)?|edit(ed)?|version|\d+|[^a-z]', '', t)[:40]


def commons(q, video=False, quanti=10):
    out = []
    try:
        j = get('https://commons.wikimedia.org/w/api.php?' + urllib.parse.urlencode({
            'action': 'query', 'format': 'json', 'generator': 'search', 'gsrnamespace': 6, 'gsrsearch': q + (' filetype:video' if video else ' filetype:bitmap'),
            'gsrlimit': 30, 'prop': 'imageinfo', 'iiprop': 'url|size|extmetadata', 'iiurlwidth': 2400 if not video else 640}))
    except Exception as e:
        log('Commons non risponde per', q, str(e)[:80]); return out
    for p in sorted((j.get('query') or {}).get('pages', {}).values(), key=lambda p: p.get('index', 99)):
        t = p.get('title', ''); ii = (p.get('imageinfo') or [{}])[0]; m = ii.get('extmetadata') or {}
        lic = ((m.get('LicenseShortName') or {}).get('value', '') + ' ' + (m.get('License') or {}).get('value', '')).strip()
        if norma(t) in VISTI or (NO_FILE.search(t) and not video) or not LIBERE.search(lic) or min(ii.get('width', 0), ii.get('height', 0)) < (480 if video else 900):
            continue
        VISTI.add(norma(t))
        out.append({'tipo': 'cvideo' if video else 'img', 'url': ii.get('url') if video else (ii.get('thumburl') or ii.get('url')),
                    'thumb': ii.get('thumburl') or '', 'titolo': t[5:], 'licenza': lic[:40],
                    'autore': re.sub(r'<[^>]+>', '', (m.get('Artist') or {}).get('value', ''))[:80]})
        if len(out) >= quanti:
            break
    return out


def pexels(q, quanti=8):
    out = []
    try:
        j = get('https://api.pexels.com/videos/search?' + urllib.parse.urlencode({'query': q, 'per_page': 20, 'orientation': 'landscape'}),
                h={'Authorization': E('PEXELS_API_KEY', '')})
    except Exception as e:
        log('Pexels non risponde', str(e)[:80]); return out
    for v in j.get('videos', []):
        if ('px', v['id']) in VISTI or v.get('duration', 0) < 6:
            continue
        f = sorted([x for x in v.get('video_files', []) if (x.get('width') or 0) >= 1280], key=lambda x: x.get('width') or 0)
        if f:
            VISTI.add(('px', v['id']))
            out.append({'tipo': 'pexels', 'url': f[0]['link'], 'thumb': v.get('image', ''), 'durata': v['duration'],
                        'titolo': f"Pexels {v['id']} ({v.get('user', {}).get('name', '')})", 'autore': '', 'licenza': 'Pexels'})
        if len(out) >= quanti:
            break
    return out


def coerenti(cands, frase):
    """Claude Haiku guarda le miniature e tiene SOLO quelle che mostrano cio' che dice la voce (in ordine di adatte)."""
    if not cands or not E('ANTHROPIC_API_KEY'):
        return cands
    cont, tenute = [], []
    for c in cands:
        try:
            im = Image.open(io.BytesIO(get(c['thumb'] or c['url'], raw=True, timeout=60))).convert('RGB')
        except Exception:
            continue
        g = im.convert('L').resize((9, 8)); px = list(g.getdata())
        imp = sum(1 << i for i in range(64) if px[(i // 8) * 9 + i % 8] > px[(i // 8) * 9 + i % 8 + 1])
        if any(bin(imp ^ x).count('1') <= 6 for x in IMPRONTE):   # stessa immagine (anche ritagliata o restaurata): scartata
            continue
        IMPRONTE.append(imp); c['_im'] = im; tenute.append(c)
    cands = tenute
    for n, c in enumerate(cands):
        try:
            im = c.pop('_im'); im.thumbnail((400, 400))
            b = io.BytesIO(); im.save(b, 'JPEG', quality=75)
            cont += [{'type': 'text', 'text': f'Image {n}:'}, {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': base64.b64encode(b.getvalue()).decode()}}]
        except Exception:
            pass
    cont.append({'type': 'text', 'text': f"""Video topic: {TEMA}. The narration at this moment says: "{frase}".
Which images show what the narration says (the same subject, person, place or object, in the right era and style for the topic)? Reject modern photos and modern people (unless the narration talks about today), interviews, unrelated scenes, other stories, people from other eras, book covers and photos of objects, buildings or people that only share a name.
Answer ONE line: GOOD: <image numbers, best first, comma separated, or none>"""})
    try:
        r = get('https://api.anthropic.com/v1/messages', {'model': 'claude-haiku-4-5-20251001', 'max_tokens': 100, 'messages': [{'role': 'user', 'content': cont}]},
                {'x-api-key': E('ANTHROPIC_API_KEY'), 'anthropic-version': '2023-06-01'})
        u = r.get('usage', {}); SPESA['usd'] += (u.get('input_tokens', 0) + 5 * u.get('output_tokens', 0)) / 1e6
        t = ''.join(x.get('text', '') for x in r.get('content', []))
        m = re.search(r'GOOD:\s*([^\n]*)', t)
        idx = [int(x) for x in re.findall(r'\d+', m.group(1) if m else '') if int(x) < len(cands)]
        return [cands[x] for x in dict.fromkeys(idx)]
    except Exception as e:
        log('controllo di coerenza non riuscito:', str(e)[:100]); return []


def candidati(s, quanti):
    c = []
    for q in (s.get('pexels') if isinstance(s.get('pexels'), list) else [s['pexels']] if s.get('pexels') else []):
        c += pexels(q, 6)
    for q in s.get('qv') or []:
        c += commons(q, video=True, quanti=6)
    for q in s.get('q') or []:
        c += commons(q, quanti=8)
    buoni = coerenti(c[:14], s['testo'])
    if len(buoni) < quanti:   # ricerca piu' larga: le riserve del video, sempre a tema, ricontrollate
        extra = []
        for q in P.get('riserva') or []:
            extra += commons(q, quanti=6)
            if len(extra) >= 12:
                break
        buoni += coerenti(extra[:14], s['testo'])
    return buoni


# ---------------- 3) inquadrature ----------------
FONT = os.path.join(LAV, 'anton.ttf')
open(FONT, 'wb').write(get('https://github.com/google/fonts/raw/main/ofl/anton/Anton-Regular.ttf', raw=True))


def scritta_png(t, k):
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im); s = 170
    while d.textlength(t, font=ImageFont.truetype(FONT, s)) > W - 240 and s > 70:
        s -= 6
    d.text((W // 2, H - 90), t, font=ImageFont.truetype(FONT, s), fill='white', stroke_width=s // 11, stroke_fill='black', anchor='md')
    p = os.path.join(LAV, f's_{k}.png'); im.save(p); return p


def scheda(testo, k):   # ultima rete: parole chiave grandi su fondo scuro (mai un'immagine sbagliata)
    im = Image.new('RGB', (W * 2, H * 2), (14, 12, 10)); d = ImageDraw.Draw(im)
    parole = [w for w in re.findall(r"[A-Za-z0-9'-]+", testo) if len(w) > 4][:3] or testo.split()[:3]
    y = H - 250
    for w in parole:
        d.text((W, y), w.upper(), font=ImageFont.truetype(FONT, 260), fill=(255, 206, 38), stroke_width=12, stroke_fill='black', anchor='mm'); y += 280
    p = os.path.join(LAV, f'scheda_{k}.jpg'); im.save(p, quality=90); return p


MOSSE = ['dentro', 'destra', 'fuori', 'sinistra', 'su', 'dettaglio']
pezzi, fonti, nvideo = [], [], 0
for k, (s, (a, b)) in enumerate(zip(scene, tempi)):
    d = b - a; parti = max(1, int(-(-d // MAXS)))
    coda = candidati(s, parti)
    log(f'scena {k}: {len(coda)} immagini/clip coerenti per {parti} inquadrature')
    for i in range(parti):
        L0 = d / parti; n = len(pezzi); out = os.path.join(LAV, f'p_{n:03d}.mp4')
        T = .3 if (n + 1) % 3 == 0 else .04
        L = L0 + T
        sc = scritta_png(s['scritta'], n) if (s.get('scritta') and i == 0) else None
        c = coda.pop(0) if coda else None
        if c and c['tipo'] in ('pexels', 'cvideo'):
            src = os.path.join(LAV, f'v_{n}' + ('.mp4' if c['tipo'] == 'pexels' else '.webm')); open(src, 'wb').write(get(c['url'], raw=True, timeout=600))
            lung = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', src], capture_output=True, text=True).stdout.strip() or 0)
            da = random.uniform(min(1, lung * .1), max(min(1, lung * .1), lung * .85 - L))
            vf = f'[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},setsar=1,tpad=stop_mode=clone:stop_duration={L:.2f}[v]'   # clip piu' corta del previsto: allungata, mai buchi
            cmd = ['ffmpeg', '-y', '-v', 'error', '-ss', round(da, 2), '-t', round(L, 3), '-i', src]
            fonti.append(f'{n:03d} VIDEO {c["titolo"]} | {c["autore"]} | {c["licenza"]}'); nvideo += 1
        else:
            if c:
                img = Image.open(io.BytesIO(get(c['url'], raw=True))).convert('RGB')
                srcf = os.path.join(LAV, f'f_{n}.jpg')
                r = max(W * 1.25 / img.width, H * 1.25 / img.height); img.resize((int(img.width * r) + 1, int(img.height * r) + 1), Image.LANCZOS).save(srcf, quality=93)
                fonti.append(f'{n:03d} DIPINTO {c["titolo"]} | {c["autore"]} | {c["licenza"]}')
            else:
                srcf = scheda(s['testo'], n); fonti.append(f'{n:03d} SCHEDA (nessuna immagine coerente)')
            fr = int(L * FPS) + 1; m = MOSSE[n % len(MOSSE)]
            z = {'dentro': f"1+0.18*on/{fr}", 'fuori': f"1.18-0.18*on/{fr}", 'dettaglio': f"1.15+0.20*on/{fr}"}.get(m, '1.12')
            x = {'destra': f"(iw-iw/zoom)*on/{fr}", 'sinistra': f"(iw-iw/zoom)*(1-on/{fr})", 'dettaglio': "(iw-iw/zoom)*0.3"}.get(m, 'iw/2-(iw/zoom/2)')
            y = {'su': f"(ih-ih/zoom)*(1-on/{fr})", 'dettaglio': "(ih-ih/zoom)*0.35"}.get(m, 'ih/2-(ih/zoom/2)')
            vf = (f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},scale={W * 2}:{H * 2},"
                  f"zoompan=z='{z}':x='{x}':y='{y}':d={fr}:s={W}x{H}:fps={FPS},setsar=1[v]")
            cmd = ['ffmpeg', '-y', '-v', 'error', '-loop', '1', '-i', srcf]
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
fl += [f'[{i}:v]settb=1/{FPS},setpts=PTS-STARTPTS,fps={FPS},format=yuv420p[n{i}]' for i in range(len(pezzi))]   # tempi azzerati e uguali
prec = 'n0'
for i in range(1, len(pezzi)):
    acc += pezzi[i - 1][1]; T = pezzi[i - 1][2]
    t = EFF[(i // 3) % len(EFF)] if T > .1 else 'fade'
    fl.append(f'[{prec}][n{i}]xfade=transition={t}:duration={T}:offset={acc:.3f}[x{i}]'); prec = f'x{i}'
fl.append(f'[{prec}]vignette=angle=PI/5,noise=alls=4:allf=t,format=yuv420p[vf]')
muto = os.path.join(LAV, 'muto.mp4')
run(['ffmpeg', '-y', '-v', 'error'] + ins + ['-filter_complex', ';'.join(fl), '-map', '[vf]', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '22', muto])
mus = os.path.join('libreria_musica', P.get('musica') or 'epico_002.mp3')
OUT = os.path.join(CART, 'prova.mp4')
run(['ffmpeg', '-y', '-v', 'error', '-i', muto, '-i', VOCE, '-stream_loop', '-1', '-i', mus, '-filter_complex',
     f'[1:a]aformat=sample_rates=44100:channel_layouts=stereo[v];[2:a]aformat=sample_rates=44100:channel_layouts=stereo,volume=0.08,afade=t=out:st={fine - 1.5:.2f}:d=1.5[m];'
     f'[v][m]amix=inputs=2:duration=first:normalize=0[a]', '-map', '0:v', '-map', '[a]', '-t', round(fine, 2), '-c:v', 'copy', '-c:a', 'aac', '-b:a', '160k', OUT])

dv = float(subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v', '-show_entries', 'stream=duration', '-of', 'csv=p=0', OUT], capture_output=True, text=True).stdout.strip() or 0)
if dv < fine - 1.5:   # mai piu' un video che si ferma alla 2a immagine con l'audio che continua
    raise RuntimeError(f'VIDEO ROTTO: immagini {dv:.1f} s, voce {fine:.1f} s')
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
open(os.path.join(CART, 'costi.txt'), 'w').write(f'ElevenLabs: {len(testo)} crediti | Commons e Pexels: 0 | controllo coerenza Haiku: {SPESA["usd"]:.3f} $ | testo nel payload\n'
                                                f'inquadrature: {len(pezzi)} | durata {fine:.1f} s | media {fine / len(pezzi):.1f} s | clip video: {quota:.0f}% | dipinti con movimento: {100 - quota:.0f}%\n')
log('FATTO', OUT)
