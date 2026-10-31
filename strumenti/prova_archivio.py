#!/usr/bin/env python3
"""
PROVA ARCHIVIO (per tutti i canali) — video di prova breve fatto SOLO con archivi gratuiti (oggi: NASA), niente cartoni.
Serve a vedere un formato PRIMA di aprire un canale.
Regole (Giorgio, 31 ott 2026): YouTube e' VIDEO -> almeno l'80% del video sono clip in movimento, nei primi 30 s quasi solo clip;
le foto solo ogni tanto. Montaggio dinamico: tagli netti alternati a effetti brevi (nero, lampo, zoom, dissolvenza, scorrimento).
- copione gia' scritto nel PAYLOAD (nessun costo Claude), diviso in scene con la ricerca d'archivio di ciascuna
- voce ElevenLabs con i tempi di ogni lettera -> ogni inquadratura cambia quando cambia la frase
- inquadrature MAI oltre 'max_secondi' (una frase lunga si divide su piu' inquadrature diverse)
- la stessa clip / foto non torna mai due volte; scartate le clip di conferenze, interviste, dirette
- musica bassa dalla libreria, nessun altro suono
PAYLOAD = {"nome": "...", "voce": "<id ElevenLabs>", "velocita": 1.08, "musica": "epico_002.mp3", "volume_musica": 0.08,
           "max_secondi": 3.5, "solo_video_fino_a": 30, "escludi": ["<nasa_id>"],
           "scene": [{"testo": "...", "q": "ricerca NASA", "scritta": "FACOLTATIVA", "tipo": "clip|foto", "a_terra": false}]}
Uscita: prove_video/archivio/<nome>/ (prova.mp4, fotogrammi.jpg, fonti.txt, costi.txt)
"""
import base64, io, json, os, random, re, subprocess, time, urllib.parse, urllib.request
from PIL import Image, ImageDraw, ImageFont

E = os.environ.get
P = json.loads(E('PAYLOAD') or '{}')
CART = os.path.join('prove_video', 'archivio', P.get('nome') or 'prova'); os.makedirs(CART, exist_ok=True)
LAV = '/tmp/lav'; os.makedirs(LAV, exist_ok=True)
MAXS = float(P.get('max_secondi') or 3.5)
SOLO_VIDEO = float(P.get('solo_video_fino_a') or 30)
W, H, FPS = 1920, 1080, 30
UA = {'User-Agent': 'ambience-prova-archivio/1.0 (gggweb23@gmail.com)'}
NO_CLIP = re.compile(r'brief|conference|interview|news|q ?& ?a|panel|talk|chat|replay|update|event|coverage|town hall|live|speech|remarks|'
                     r'podcast|webinar|explain|animation|graphic|trailer|countdown|speaks|call|engagement|discuss|student|school|media|magazine|'
                     r'governor|official|tour|education|in-?flight|virtual|ceremony|award|reporter|answers|questions', re.I)
B_ROLL = re.compile(r'b-?roll|time ?lapse|timelapse|footage', re.I)   # riprese senza persone che parlano in camera
if P.get('animazioni'):   # canali sui pianeti: ammesse le animazioni ufficiali NASA/JPL (pubblico dominio, in movimento)
    NO_CLIP = re.compile(NO_CLIP.pattern.replace('animation|graphic|', '').replace('|launch', ''), re.I)
    B_ROLL = re.compile(r'b-?roll|time ?lapse|timelapse|footage|animation|visuali[sz]ation|simulation|artist', re.I)
random.seed(7)
log = lambda *a: print(time.strftime('%H:%M:%S'), *a, flush=True)


def get(u, dati=None, h=None, raw=False, timeout=120):
    req = urllib.request.Request(u, data=json.dumps(dati).encode() if dati is not None else None,
                                 headers=dict(UA, **({'Content-Type': 'application/json'} if dati is not None else {}), **(h or {})))
    with urllib.request.urlopen(req, timeout=timeout) as r:
        b = r.read()
        return b if raw else json.loads(b.decode() or '{}')


def run(c):
    subprocess.run([str(x) for x in c], check=True)


def durata(p):
    return float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', p],
                                capture_output=True, text=True).stdout.strip() or 0)


# ---------------- 1) voce con i tempi ----------------
scene = P['scene']
testo = ' '.join(s['testo'].strip() for s in scene)
import hashlib
_chiave_voce = hashlib.md5((testo + str(P.get('voce')) + str(P.get('velocita'))).encode()).hexdigest()[:12]
_cache_voce = os.path.join(LAV, f'voce_{_chiave_voce}.json')
if os.path.exists(_cache_voce):   # riparazione: stessa voce gia' pagata, non si rifa'
    j = json.load(open(_cache_voce)); log('voce ripresa dal tentativo precedente (nessun credito in piu\')')
else:
    j = get(f"https://api.elevenlabs.io/v1/text-to-speech/{P.get('voce') or 'glnsgBC77wt5zOYU0szz'}/with-timestamps?output_format=mp3_44100_128",
            {'text': testo, 'model_id': 'eleven_multilingual_v2',
             'voice_settings': {'stability': float(P.get('stabilita') or .45), 'similarity_boost': .75, 'style': float(P.get('stile_voce') or 0),
                                'speed': float(P.get('velocita') or 1.06)}},
            {'xi-api-key': E('ELEVENLABS_API_KEY', '')})
    json.dump(j, open(_cache_voce, 'w'))
VOCE = os.path.join(LAV, 'voce.mp3'); open(VOCE, 'wb').write(base64.b64decode(j['audio_base64']))
al = j['alignment']; ts = al['character_start_times_seconds']; te = al['character_end_times_seconds']
pos, inizi = 0, []
for s in scene:
    inizi.append(0.0 if not inizi else ts[min(pos, len(ts) - 1)])
    pos += len(s['testo'].strip()) + 1
fine_tot = te[-1] + 0.9
tempi = [(inizi[k], inizi[k + 1] if k + 1 < len(inizi) else fine_tot) for k in range(len(scene))]
log('voce', round(te[-1], 1), 's,', len(testo), 'caratteri,', round(len(testo.split()) / te[-1], 2), 'parole/s')

# ---------------- 2) archivio NASA ----------------
USATI = set(P.get('escludi') or [])
SERIE = set()   # foto della stessa serie (iss053e079613 / iss053e079615) = immagine ripetuta -> scartata
ORBITA = re.compile(r'^(iss\d|s\d{2,3}e|sts\d|nm\d)', re.I)   # foto scattate in orbita (non a Terra, non in addestramento)
CLIP_CACHE = {}   # nasa_id -> (file, lunghezza, segmenti gia' usati)

# ---- libreria di spezzoni gia' etichettati (strumenti/libreria_clip.py): prima scelta, costo zero ----
LIB = []
if P.get('libreria'):
    try:
        LIB = [x for x in json.load(open(os.path.join('libreria_clip', P['libreria'], 'indice.json'))) if x.get('ok')]
    except Exception as e:
        log('libreria non letta', str(e)[:80])
LIB_USATI, LIB_FILE, ULTIMA_SORGENTE, PER_SORGENTE = set(), {}, [''], {}   # max 3 spezzoni dalla stessa ripresa per video


def parole(t):
    return set(re.findall(r'[a-z]+', str(t).lower())) - {'the', 'a', 'an', 'of', 'in', 'on', 'and', 'with', 'from', 'to', 'at', 'is'}


# parole troppo generiche per dire che una clip e' coerente con la frase (prima: pomodori in un video sul freddo)
GENERICHE = {'space', 'station', 'astronaut', 'astronauts', 'iss', 'earth', 'inside', 'outside', 'orbit', 'crew', 'nasa', 'view', 'module',
             'spacecraft', 'international', 'working', 'work', 'activity', 'activities', 'equipment', 'onboard', 'aboard'}


def dalla_libreria(s, dur):
    """Lo spezzone piu' adatto alla scena (parole chiave della scena contro etichetta), mai ripetuto,
    mai due volte di fila dalla stessa ripresa."""
    chiave = parole(' '.join(s.get('tag') or []) + ' ' + s['q']) - GENERICHE   # solo parole che dicono DAVVERO di cosa parla la frase
    best, bp = None, 0
    for x in LIB:
        if x['n'] in LIB_USATI or x['nasa_id'] == ULTIMA_SORGENTE[0] or PER_SORGENTE.get(x['nasa_id'], 0) >= 3 or float(x.get('durata') or 0) + .2 < dur:
            continue
        et = parole(' '.join(x.get('tag') or []) + ' ' + str(x.get('cosa') or '') + ' ' + str(x.get('luogo') or '').replace('_', ' '))
        pt = len(chiave & et) * 10 + int(x.get('qualita') or 0) + min(3, float(x.get('movimento') or 0) / 5)
        obbligo = parole(' '.join(s.get('obbligo') or []))   # parole che DEVONO esserci (es. l'apertura deve far capire subito l'argomento)
        if obbligo and not (obbligo & et):
            continue
        if len(chiave & et) and pt > bp:
            best, bp = x, pt
    if not best:
        return None
    LIB_USATI.add(best['n']); ULTIMA_SORGENTE[0] = best['nasa_id']; PER_SORGENTE[best['nasa_id']] = PER_SORGENTE.get(best['nasa_id'], 0) + 1
    if best['url'] not in LIB_FILE:
        f = os.path.join(LAV, 'lib_' + re.sub(r'\W', '_', best['nasa_id'])[:60] + '.mp4')
        open(f, 'wb').write(get(best['url'], raw=True, timeout=600)); LIB_FILE[best['url']] = f
    f_ = LIB_FILE[best['url']]
    if best['nasa_id'] not in CLIP_CACHE:
        CLIP_CACHE[best['nasa_id']] = (f_, durata(f_), [])
    CLIP_CACHE[best['nasa_id']][2].append(float(best['da']))
    return f_, float(best['da']), best['nasa_id'], 'LIBRERIA: ' + str(best.get('cosa'))


def nasa(q, tipo):
    try:
        return get('https://images-api.nasa.gov/search?' + urllib.parse.urlencode({'q': q, 'media_type': tipo})).get('collection', {}).get('items', [])
    except Exception as e:
        log('ricerca non riuscita', q, str(e)[:80]); return []


def foto(q, a_terra=False):
    for it in nasa(q, 'image'):
        nid = it['data'][0]['nasa_id']; serie = re.sub(r'\d{3}$', '', nid)
        if nid in USATI or serie in SERIE or (not a_terra and not ORBITA.match(nid)):
            continue
        href = (it.get('links') or [{}])[0].get('href', '')
        for v in ('~large.', '~medium.', '~orig.'):
            try:
                im = Image.open(io.BytesIO(get(href.replace('~thumb.', v), raw=True))).convert('RGB')
            except Exception:
                continue
            if im.width < 900 or im.width < im.height:
                break
            USATI.add(nid); SERIE.add(serie); return im, nid, it['data'][0].get('title', '')
    return None


CLIP_ORBITA = re.compile(r'^iss\d{3}m', re.I)   # riprese grezze girate in orbita (downlink ISS): niente scritte, studi, addestramenti a Terra


def bande_nere(p, da, dur):
    """True se il pezzo ha bande nere (video 4:3 o con cornice): da scartare."""
    o = subprocess.run(['ffmpeg', '-v', 'info', '-ss', f'{da:.2f}', '-t', f'{min(dur, 3):.2f}', '-i', p, '-vf', 'cropdetect=limit=24:round=2:reset=0',
                        '-an', '-f', 'null', '-'], capture_output=True, text=True).stderr
    m = re.findall(r'crop=(\d+):(\d+):', o)
    if not m:
        return False
    cw, ch = map(int, m[-1])
    w, h = map(int, subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height', '-of', 'csv=p=0', p],
                                   capture_output=True, text=True).stdout.strip().split(',')[:2])
    return cw < w * .92 or ch < h * .88


def clip(q, dur, a_terra=False):
    """Una clip NASA nuova per la ricerca; restituisce (file, inizio, nasa_id, titolo)."""
    tentate = 0
    for it in nasa(q, 'video'):
        d0 = it['data'][0]; nid = d0['nasa_id']; tit = d0.get('title', '')
        if nid in USATI or NO_CLIP.search(tit + ' ' + ' '.join(d0.get('keywords') or [])):
            continue
        if not B_ROLL.search(tit + ' ' + d0.get('description', '')[:300]) or (not a_terra and not (CLIP_ORBITA.match(nid) or re.search(r'space station|ISS|orbit|spacewalk|expedition', tit + d0.get('description', '')[:300], re.I))):
            continue
        tentate += 1
        if tentate > 6:
            break
        try:
            files = get(it['href'])
            mp4 = next((f for suf in ('~small.mp4', '~mobile.mp4', '~medium.mp4', '~preview.mp4') for f in files if f.endswith(suf)), None)
            if not mp4:
                continue
            p = os.path.join(LAV, re.sub(r'\W', '_', nid) + '.mp4')
            open(p, 'wb').write(get(mp4.replace('http://', 'https://'), raw=True, timeout=300))
            lung = durata(p)
            if lung < dur + 3:
                continue
            ok = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height', '-of', 'csv=p=0', p],
                                capture_output=True, text=True).stdout.strip().split(',')
            if len(ok) < 2 or int(ok[0]) < int(ok[1]) or int(ok[0]) < 600:   # niente clip verticali o minuscole
                continue
            for _ in range(4):
                da = random.uniform(lung * .15, max(lung * .15, lung * .85 - dur))   # mai l'inizio (titoli) ne' la fine (crediti)
                if not bande_nere(p, da, dur):
                    break
            else:
                log('clip con bande nere, scartata', nid); continue
            USATI.add(nid)
            CLIP_CACHE[nid] = (p, lung, [da])
            return p, da, nid, tit
        except Exception as e:
            log('clip non usata', nid, str(e)[:80])
    return None


def altro_pezzo(nid, dur):
    """Un altro momento (lontano almeno 6 s) della stessa clip, se la ricerca non da' clip nuove."""
    if nid not in CLIP_CACHE:   # (prima: spezzone di libreria non registrato -> KeyError e montaggio fermo)
        return None
    p, lung, usati = CLIP_CACHE[nid]
    for _ in range(20):
        da = random.uniform(lung * .1, max(lung * .1, lung * .9 - dur))
        if all(abs(da - u) > dur + 6 for u in usati):
            usati.append(da); return p, da
    return None


# ---------------- 3) scritte ----------------
FONT = os.path.join(LAV, 'anton.ttf')
open(FONT, 'wb').write(get('https://github.com/google/fonts/raw/main/ofl/anton/Anton-Regular.ttf', raw=True))


def scritta_png(t, k):
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    s = 160; f = ImageFont.truetype(FONT, s)
    while d.textlength(t, font=f) > W - 220 and s > 70:
        s -= 6; f = ImageFont.truetype(FONT, s)
    d.text((W // 2, H - 90), t, font=f, fill=(255, 255, 255), stroke_width=s // 11, stroke_fill=(0, 0, 0), anchor='md')
    p = os.path.join(LAV, f'scritta_{k}.png'); im.save(p); return p


# ---------------- 4) inquadrature ----------------
# transizioni tra un'inquadratura e la successiva: soprattutto tagli netti, ogni tanto un effetto breve
EFFETTI = [('fadeblack', .35), ('fadewhite', .18), ('zoomin', .35), ('dissolve', .40), ('slideleft', .30), ('smoothright', .30), ('circleopen', .35)]
TAGLIO = ('fade', .04)
piano = []   # [(durata sul timeline, scena, prima_parte)]
for k, (s, (a, b)) in enumerate(zip(scene, tempi)):
    d = b - a; parti = max(1, int(-(-d // MAXS)))
    for i in range(parti):
        piano.append((d / parti, s, i == 0, a + i * d / parti))
trans = []
for n in range(len(piano) - 1):
    trans.append(EFFETTI[(n // 3) % len(EFFETTI)] if n % 3 == 2 else TAGLIO)   # un effetto ogni 3 tagli
trans.append(('fade', 0))

pezzi, fonti, nclip = [], [], 0
MANCANTI = []   # ricerche delle scene senza spezzone adatto in libreria: la libreria le cerchera' nei giri successivi
for n, (d, s, prima, t0) in enumerate(piano):
    T = trans[n][1]; L = d + T                        # ogni pezzo dura un po' di piu' per la transizione
    out = os.path.join(LAV, f'p_{n:03d}.mp4')
    sc = scritta_png(s['scritta'], n) if (s.get('scritta') and prima) else None
    vuole_clip = s.get('tipo', 'clip') != 'foto' or t0 < SOLO_VIDEO
    c = dalla_libreria(s, L) if (vuole_clip and LIB) else None
    if vuole_clip and LIB and not c:
        MANCANTI.append(s.get('q') or '')
    if vuole_clip and not c:
        at = bool(s.get('a_terra')); c = clip(s['q'], L, at) or clip(' '.join(s['q'].split()[:2]), L, at)
        if not c and s.get('_ultima'):
            r = altro_pezzo(s['_ultima'], L)
            c = (r[0], r[1], s['_ultima'], '(altro momento)') if r else None
    if c:
        p, da, nid, tit = c; s['_ultima'] = nid; nclip += 1
        spinta = n % 2 == 0                            # una clip si' e una no: leggera spinta in avanti (punch-in)
        vf = (f'[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},setsar=1'
              + (f",zoompan=z='1+0.06*on/{int(L * FPS)}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={W}x{H}:fps={FPS}" if spinta else '') + '[v]')
        cmd = ['ffmpeg', '-y', '-v', 'error', '-ss', round(da, 2), '-t', round(L, 3), '-i', p]
        fonti.append(f'{n:03d} CLIP {nid} da {da:.1f}s | {tit}')
    else:
        f_ = foto(s['q'], bool(s.get('a_terra'))) or foto(' '.join(s['q'].split()[:3]), bool(s.get('a_terra'))) \
            or foto('astronaut International Space Station')
        if not f_:
            raise RuntimeError('nessuna immagine NASA per: ' + s['q'])
        im, nid, tit = f_
        r = max(W * 2 / im.width, H * 2 / im.height); im = im.resize((int(im.width * r) + 1, int(im.height * r) + 1), Image.LANCZOS)
        x0, y0 = (im.width - W * 2) // 2, (im.height - H * 2) // 3
        src = os.path.join(LAV, f'f_{n:03d}.jpg'); im.crop((x0, y0, x0 + W * 2, y0 + H * 2)).save(src, quality=92)
        fr = int(L * FPS) + 1; m = ['avanti', 'destra', 'indietro', 'sinistra'][n % 4]
        z = {'avanti': f"1+0.12*on/{fr}", 'indietro': f"1.12-0.12*on/{fr}"}.get(m, '1.12')
        x = {'destra': f"(iw-iw/zoom)*on/{fr}", 'sinistra': f"(iw-iw/zoom)*(1-on/{fr})"}.get(m, 'iw/2-(iw/zoom/2)')
        vf = f"[0:v]zoompan=z='{z}':x='{x}':y='ih/2-(ih/zoom/2)':d={fr}:s={W}x{H}:fps={FPS},setsar=1[v]"
        cmd = ['ffmpeg', '-y', '-v', 'error', '-i', src]
        fonti.append(f'{n:03d} FOTO {nid} | {tit}')
    if sc:
        cmd += ['-i', sc]; vf += ';[v][1:v]overlay=0:0[v]'
    run(cmd + ['-filter_complex', vf + ';[v]format=yuv420p[o]', '-map', '[o]', '-frames:v', int(round(L * FPS)), '-an',
               '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '19', out])
    pezzi.append((out, d, trans[n]))
    log(f'{n:02d}', 'CLIP' if c else 'FOTO', round(d, 2), 's', trans[n][0])

# ---------------- 5) montaggio con transizioni + audio ----------------
# a BLOCCHI di 24 inquadrature (video lunghi: 200 ingressi in un solo ffmpeg esauriscono la memoria); tra un blocco e l'altro taglio netto
def monta(blocco, out):
    ins, fl, acc, prec = [], [], 0.0, '0:v'
    for p, d, _ in blocco:
        ins += ['-i', p]
    # ogni pezzo con tempi azzerati e uguali (le clip d'archivio possono iniziare a 0,07 s: xfade allora si fermava al 1° pezzo)
    fl += [f'[{i}:v]settb=1/{FPS},setpts=PTS-STARTPTS,fps={FPS},format=yuv420p[n{i}]' for i in range(len(blocco))]
    prec = 'n0'
    for i in range(1, len(blocco)):
        acc += blocco[i - 1][1]
        tipo, T = blocco[i - 1][2]
        fl.append(f'[{prec}][n{i}]xfade=transition={tipo}:duration={T}:offset={acc:.3f}[x{i}]'); prec = f'x{i}'
    fl.append(f'[{prec}]vignette=angle=PI/6,noise=alls=3:allf=t,format=yuv420p,trim=duration={sum(d for _, d, _ in blocco):.3f}[vf]')
    run(['ffmpeg', '-y', '-v', 'error'] + ins + ['-filter_complex', ';'.join(fl), '-map', '[vf]', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '23', out])
muto = os.path.join(LAV, 'muto.mp4')
blocchi = [pezzi[i:i + 24] for i in range(0, len(pezzi), 24)]
if len(blocchi) == 1:
    monta(blocchi[0], muto)
else:
    parti = []
    for bi, bl in enumerate(blocchi):
        bl = bl[:-1] + [(bl[-1][0], bl[-1][1], ('fade', 0))]   # l'ultimo del blocco: taglio netto verso il blocco dopo
        o = os.path.join(LAV, f'blocco_{bi:02d}.mp4'); monta(bl, o); parti.append(o)
    lista = os.path.join(LAV, 'blocchi.txt'); open(lista, 'w').write(''.join(f"file '{x}'\n" for x in parti))
    run(['ffmpeg', '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', lista, '-c', 'copy', muto])
mus = os.path.join('libreria_musica', P.get('musica') or 'epico_002.mp3')
vm = float(P.get('volume_musica') or 0.08)
OUT = os.path.join(CART, 'prova.mp4')
run(['ffmpeg', '-y', '-v', 'error', '-i', muto, '-i', VOCE, '-stream_loop', '-1', '-i', mus, '-filter_complex',
     f'[1:a]aformat=sample_rates=44100:channel_layouts=stereo[v];'
     f'[2:a]aformat=sample_rates=44100:channel_layouts=stereo,volume={vm},afade=t=in:d=1,afade=t=out:st={fine_tot - 1.5:.2f}:d=1.5[m];'
     f'[v][m]amix=inputs=2:duration=first:normalize=0[a]',
     '-map', '0:v', '-map', '[a]', '-t', round(fine_tot, 2), '-c:v', 'copy', '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', OUT])

dv = float(subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v', '-show_entries', 'stream=duration', '-of', 'csv=p=0', OUT], capture_output=True, text=True).stdout.strip() or 0)
if dv < fine_tot - 1.5:   # mai piu' un video che si ferma alla 2a immagine con l'audio che continua
    raise RuntimeError(f'VIDEO ROTTO: immagini {dv:.1f} s, voce {fine_tot:.1f} s')
# ---------------- 6) controlli ----------------
fot = []
for i, (p, d, _) in enumerate(pezzi):
    q = p[:-4] + '.png'
    run(['ffmpeg', '-y', '-v', 'error', '-ss', f'{d / 2:.2f}', '-i', p, '-frames:v', 1, '-vf', 'scale=384:216', q]); fot.append(q)
col = 5; G = Image.new('RGB', (col * 390, ((len(fot) + col - 1) // col) * 222), 'black'); dg = ImageDraw.Draw(G)
for i, q in enumerate(fot):
    G.paste(Image.open(q), ((i % col) * 390, (i // col) * 222)); dg.text(((i % col) * 390 + 6, (i // col) * 222 + 4), str(i), fill='yellow')
G.save(os.path.join(CART, 'fotogrammi.jpg'), quality=85)
quota = 100 * sum(d for (p, d, _), f in zip(pezzi, fonti) if ' CLIP ' in f) / max(.1, sum(d for p, d, _ in pezzi))
open(os.path.join(CART, 'fonti.txt'), 'w').write('\n'.join(fonti) + '\n')
open(os.path.join(CART, 'mancanti.txt'), 'w').write('\n'.join(sorted(set(m for m in MANCANTI if m))) + '\n')
open(os.path.join(CART, 'costi.txt'), 'w').write(
    f'ElevenLabs: {len(testo)} crediti dell\'abbonamento | NASA: 0 | Claude: 0 (copione nel payload) | render GitHub: 0\n'
    f'inquadrature: {len(pezzi)} | durata: {fine_tot:.1f} s | inquadratura media {fine_tot / len(pezzi):.1f} s | video in movimento: {quota:.0f}%\n')
if quota < 80:
    log(f'ATTENZIONE: solo {quota:.0f}% di video in movimento (minimo 80%)')
log('FATTO', OUT, len(pezzi), 'inquadrature', round(fine_tot, 1), 's', f'{quota:.0f}% video')
