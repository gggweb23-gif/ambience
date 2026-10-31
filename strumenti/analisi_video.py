#!/usr/bin/env python3
"""
ANALISI VIDEO DI RIFERIMENTO (per tutti i canali, gratis) — per copiare il MONTAGGIO di un video che funziona:
dati del video (YouTube API), trascrizione con i tempi (parole al secondo), e se il video si scarica:
tagli di scena nei primi minuti (quanto dura ogni inquadratura) e fogli di fotogrammi per vedere transizioni ed effetti.
PAYLOAD = {"nome": "riferimento_guerra", "video": "<link o id>", "secondi": 90}
Uscita: prove_video/analisi/<nome>/ (dati.json, tagli.txt, fotogrammi_*.jpg, transizioni.jpg)
"""
import glob, json, os, re, subprocess, time, urllib.parse, urllib.request
from PIL import Image, ImageDraw

E = os.environ.get
P = json.loads(E('PAYLOAD') or '{}')
VID = re.search(r'(?:v=|youtu\.be/|shorts/|^)([\w-]{11})', P['video'].strip()).group(1)
CART = os.path.join('prove_video', 'analisi', P.get('nome') or VID); os.makedirs(CART, exist_ok=True)
SEC = int(P.get('secondi') or 90)
LAV = '/tmp/an'; os.makedirs(LAV, exist_ok=True)
log = lambda *a: print(time.strftime('%H:%M:%S'), *a, flush=True)


def get(u, dati=None, h=None, raw=False):
    req = urllib.request.Request(u, data=dati, headers=dict({'User-Agent': 'Mozilla/5.0'}, **(h or {})))
    with urllib.request.urlopen(req, timeout=120) as r:
        b = r.read()
        return b if raw else json.loads(b.decode() or '{}')


dati = {'id': VID}
# 1) dati del video
try:
    t = get('https://oauth2.googleapis.com/token', urllib.parse.urlencode({
        'client_id': E('YT_CLIENT_ID', ''), 'client_secret': E('YT_CLIENT_SECRET', ''), 'refresh_token': E('YT_REFRESH_TOKEN', ''),
        'grant_type': 'refresh_token'}).encode())['access_token']
    v = get('https://www.googleapis.com/youtube/v3/videos?part=snippet,statistics,contentDetails&id=' + VID, h={'Authorization': 'Bearer ' + t})['items'][0]
    dati.update(titolo=v['snippet']['title'], canale=v['snippet']['channelTitle'], canale_id=v['snippet']['channelId'],
                views=v['statistics'].get('viewCount'), durata=v['contentDetails']['duration'], pubblicato=v['snippet']['publishedAt'][:10],
                lingua_audio=v['snippet'].get('defaultAudioLanguage'), descrizione=v['snippet'].get('description', '')[:1500])
    log(dati['titolo'], '|', dati['canale'], '|', dati['views'], 'views')
except Exception as e:
    log('dati video non letti:', str(e)[:150])

# 2) trascrizione con i tempi (RapidAPI, piano gia' attivo)
try:
    j = get('https://youtube-transcript3.p.rapidapi.com/api/transcript?videoId=' + VID,
            h={'X-RapidAPI-Key': E('RAPIDAPI_KEY', ''), 'X-RapidAPI-Host': 'youtube-transcript3.p.rapidapi.com'})
    tr = j.get('transcript') or []
    primi = [x for x in tr if float(x.get('offset', 0)) < SEC]
    testo = ' '.join(x.get('text', '') for x in primi)
    dati['trascrizione_inizio'] = testo
    dati['parole_al_secondo'] = round(len(testo.split()) / max(1.0, SEC), 2)
    log('trascrizione:', len(tr), 'righe,', dati['parole_al_secondo'], 'parole/s nei primi', SEC, 's')
except Exception as e:
    log('trascrizione non letta:', str(e)[:150])

# 3) video: tagli di scena e fotogrammi
try:
    subprocess.run(['yt-dlp', '-q', '--no-warnings', '-f', 'bv*[height<=480][ext=mp4]+ba[ext=m4a]/b[height<=480]/b',
                    '--download-sections', f'*0-{SEC}', '--force-keyframes-at-cuts', '-o', f'{LAV}/v.%(ext)s',
                    f'https://www.youtube.com/watch?v={VID}'], check=True, timeout=900)
    src = sorted(glob.glob(f'{LAV}/v.*'))[0]
    # tagli: cambi di scena forti (0.30) e morbidi (dissolvenze, 0.12)
    o = subprocess.run(['ffmpeg', '-v', 'info', '-i', src, '-t', str(SEC), '-vf', "select='gt(scene,0.12)',metadata=print", '-an', '-f', 'null', '-'],
                       capture_output=True, text=True).stderr
    tagli = []
    for m in re.finditer(r'pts_time:([\d.]+)[^\n]*\n[^\n]*scene_score=([\d.]+)', o):
        tagli.append((float(m.group(1)), float(m.group(2))))
    netti = [t for t, s in tagli if s >= .30]
    durate = [round(b - a, 2) for a, b in zip([0.0] + netti, netti)]
    dati['tagli_netti'] = len(netti); dati['inquadratura_media_s'] = round(sum(durate) / max(1, len(durate)), 2)
    open(os.path.join(CART, 'tagli.txt'), 'w').write('\n'.join(f'{t:7.2f}s  forza {s:.2f}' for t, s in tagli) + '\n')
    log('tagli netti', len(netti), 'inquadratura media', dati['inquadratura_media_s'], 's')
    # fotogrammi: 2 al secondo nei primi 30 s, poi 1 al secondo
    def foglio(da, a, fps, nome):
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', str(da), '-t', str(a - da), '-i', src, '-vf', f'fps={fps},scale=320:-2',
                        f'{LAV}/{nome}_%04d.jpg'], check=True)
        fs = sorted(glob.glob(f'{LAV}/{nome}_*.jpg'))
        if not fs:
            return
        w, h = Image.open(fs[0]).size; col = 8
        G = Image.new('RGB', (col * w, ((len(fs) + col - 1) // col) * (h + 16)), 'black'); d = ImageDraw.Draw(G)
        for i, f in enumerate(fs):
            x, y = (i % col) * w, (i // col) * (h + 16)
            G.paste(Image.open(f), (x, y + 16)); d.text((x + 4, y + 2), f'{da + i / fps:.1f}s', fill='yellow')
        G.save(os.path.join(CART, f'{nome}.jpg'), quality=80)
    foglio(0, min(30, SEC), 2, 'fotogrammi_0_30s')
    if SEC > 30:
        foglio(30, SEC, 1, 'fotogrammi_30s_oltre')
    # transizioni: 6 fotogrammi ravvicinati attorno ai primi 12 tagli (si vede se e' taglio netto, dissolvenza, scorrimento...)
    righe = []
    for t, s in tagli[:12]:
        fr = []
        for k, dt in enumerate((-.4, -.2, -.07, .07, .2, .4)):
            p = f'{LAV}/tr_{t:.2f}_{k}.jpg'
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{max(0, t + dt):.2f}', '-i', src, '-frames:v', '1', '-vf', 'scale=240:-2', p])
            if os.path.exists(p):
                fr.append(p)
        if fr:
            righe.append((t, s, fr))
    if righe:
        w, h = Image.open(righe[0][2][0]).size
        G = Image.new('RGB', (6 * w + 90, len(righe) * h), 'black'); d = ImageDraw.Draw(G)
        for i, (t, s, fr) in enumerate(righe):
            d.text((4, i * h + 4), f'{t:.1f}s\n{s:.2f}', fill='yellow')
            for k, p in enumerate(fr):
                G.paste(Image.open(p), (90 + k * w, i * h))
        G.save(os.path.join(CART, 'transizioni.jpg'), quality=80)
except Exception as e:
    dati['video_non_scaricato'] = str(e)[:300]; log('video non scaricato:', str(e)[:200])

json.dump(dati, open(os.path.join(CART, 'dati.json'), 'w'), ensure_ascii=False, indent=1)
log('FATTO')
