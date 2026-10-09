#!/usr/bin/env python3
"""
MULTICHANNEL - Ambience Lunghi
Riceve da n8n (variabile PAYLOAD, JSON) le clip Pexels e i suoni, crea un video lungo in loop
(es. 3 ore) con FFmpeg, lo carica su YouTube e avvisa n8n con il risultato.

Il loop e' senza scatti: ogni clip sfuma nella successiva e l'ultima sfuma di nuovo nella prima,
cosi' quando il video riparte da capo non si vede il punto di giunzione. Stessa cosa per l'audio.

Variabili d'ambiente:
  PAYLOAD            JSON preparato da n8n (vedi PAYLOAD_ESEMPIO in fondo)
  YT_CLIENT_ID       OAuth client del progetto Google (lo stesso del Publisher)
  YT_CLIENT_SECRET
  YT_REFRESH_TOKEN   refresh token del canale YouTube di destinazione
  DRY_RUN=1          crea il video ma non lo carica (per le prove)
"""
import json, math, os, shutil, subprocess, sys, time, traceback
import urllib.request, urllib.error, urllib.parse

LAVORO = os.environ.get('CARTELLA_LAVORO') or os.path.join(os.getcwd(), 'lavoro')
FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'


def log(*a):
    print('[ambience]', *a, flush=True)


def run(cmd):
    log(' '.join(str(c) for c in cmd)[:400])
    subprocess.run([str(c) for c in cmd], check=True)


def durata(path):
    out = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', path],
                         check=True, capture_output=True, text=True).stdout.strip()
    return float(out)


def scarica(url, path):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    for tentativo in range(4):
        try:
            with urllib.request.urlopen(req, timeout=120) as r, open(path, 'wb') as f:
                shutil.copyfileobj(r, f, 1024 * 1024)
            if os.path.getsize(path) < 2000:
                raise RuntimeError('file troppo piccolo, probabilmente non e\' un media: ' + url)
            return path
        except Exception as e:
            log('download fallito (' + str(e) + '), riprovo')
            time.sleep(5 * (tentativo + 1))
    raise RuntimeError('impossibile scaricare ' + url)


def http_json(url, data=None, headers=None, method=None):
    body = json.dumps(data).encode() if isinstance(data, (dict, list)) else data
    h = {'Content-Type': 'application/json'} if isinstance(data, (dict, list)) else {}
    h.update(headers or {})
    req = urllib.request.Request(url, data=body, headers=h, method=method)
    with urllib.request.urlopen(req, timeout=120) as r:
        txt = r.read().decode() or '{}'
        return json.loads(txt), r


# ---------------------------------------------------------------- VIDEO
def prepara_clip(urls, max_sec, fps, tipo_media='video'):
    """Normalizza le clip a 1920x1080. Con tipo_media = foto ogni url e' un'immagine ferma (come l'originale con foto fissa)."""
    foto = str(tipo_media).lower() == 'foto'
    clips = []
    for i, u in enumerate(urls):
        raw = scarica(u, os.path.join(LAVORO, f'clip_raw_{i}' + ('.jpg' if foto else '.mp4')))
        out = os.path.join(LAVORO, f'clip_{i}.mp4')
        vf = f'scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,fps={fps},format=yuv420p'
        if foto:
            run(['ffmpeg', '-y', '-v', 'error', '-loop', '1', '-i', raw, '-t', 20, '-vf', vf,
                 '-c:v', 'libx264', '-preset', 'veryfast', '-tune', 'stillimage', '-crf', '16', out])
        else:
            run(['ffmpeg', '-y', '-v', 'error', '-i', raw, '-an', '-t', max_sec, '-vf', vf,
                 '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '16', out])
        clips.append((out, durata(out)))
    return clips


def base_video(clips, d, bitrate, fps):
    """Concatena le clip con dissolvenze e chiude il cerchio sulla prima: il file risultante si ripete senza scatti."""
    clips = [c for c in clips if c[1] > 2 * d + 1]
    if not clips:
        raise RuntimeError('nessuna clip abbastanza lunga per la dissolvenza')
    seq = clips + [clips[0]]
    filtri, lung, prec = [], seq[0][1], '0:v'
    offset = 0
    for i in range(1, len(seq)):
        offset = lung - d
        etichetta = f'v{i}'
        filtri.append(f'[{prec}][{i}:v]xfade=transition=fade:duration={d}:offset={offset:.3f}[{etichetta}]')
        lung = lung + seq[i][1] - d
        prec = etichetta
    fine = offset + d - 1 / fps            # qui la prima clip e' di nuovo piena, un fotogramma prima del suo secondo d
    filtri.append(f'[{prec}]trim=start={d}:end={fine:.4f},setpts=PTS-STARTPTS[out]')
    out = os.path.join(LAVORO, 'base_video.mp4')
    cmd = ['ffmpeg', '-y', '-v', 'error']
    for p, _ in seq:
        cmd += ['-i', p]
    kbit = int(str(bitrate).lower().rstrip('k'))
    cmd += ['-filter_complex', ';'.join(filtri), '-map', '[out]', '-c:v', 'libx264', '-preset', 'medium',
            '-b:v', f'{kbit}k', '-maxrate', f'{int(kbit * 1.5)}k', '-bufsize', f'{kbit * 2}k',
            '-g', str(fps * 2), '-keyint_min', str(fps * 2), '-sc_threshold', '0', '-r', str(fps),
            '-pix_fmt', 'yuv420p', '-movflags', '+faststart', out]
    run(cmd)
    return out, durata(out)


# ---------------------------------------------------------------- AUDIO
def base_audio(urls, d_max):
    tracce = []
    for i, u in enumerate(urls):
        raw = scarica(u, os.path.join(LAVORO, f'audio_raw_{i}'))
        out = os.path.join(LAVORO, f'audio_{i}.wav')
        run(['ffmpeg', '-y', '-v', 'error', '-i', raw, '-vn', '-ac', '2', '-ar', '48000', out])
        tracce.append((out, durata(out)))
    d = min(d_max, min(t[1] for t in tracce) / 3)
    seq = tracce + [tracce[0]]
    filtri, lung, prec, offset = [], seq[0][1], '0:a', 0
    for i in range(1, len(seq)):
        offset = lung - d
        etichetta = f'a{i}'
        filtri.append(f'[{prec}][{i}:a]acrossfade=d={d:.3f}:c1=tri:c2=tri[{etichetta}]')
        lung = lung + seq[i][1] - d
        prec = etichetta
    fine = offset + d
    filtri.append(f'[{prec}]atrim=start={d:.3f}:end={fine:.3f},asetpts=PTS-STARTPTS[out]')
    out = os.path.join(LAVORO, 'base_audio.wav')
    cmd = ['ffmpeg', '-y', '-v', 'error']
    for p, _ in seq:
        cmd += ['-i', p]
    cmd += ['-filter_complex', ';'.join(filtri), '-map', '[out]', out]
    run(cmd)
    return out


def audio_finale(base, secondi, volume):
    out = os.path.join(LAVORO, 'audio_finale.m4a')
    run(['ffmpeg', '-y', '-v', 'error', '-stream_loop', '-1', '-i', base, '-t', secondi,
         '-af', f'volume={volume},afade=t=in:d=4,afade=t=out:st={max(0, secondi - 6)}:d=6',
         '-c:a', 'aac', '-b:a', '192k', out])
    return out


# ---------------------------------------------------------------- MONTAGGIO FINALE
def video_finale(base, base_sec, audio, secondi):
    ripetizioni = math.ceil(secondi / base_sec) + 1
    lista = os.path.join(LAVORO, 'lista.txt')
    with open(lista, 'w') as f:
        f.write(('file ' + "'" + base + "'\n") * ripetizioni)
    out = os.path.join(LAVORO, 'video_finale.mp4')
    run(['ffmpeg', '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', lista, '-i', audio,
         '-t', secondi, '-map', '0:v:0', '-map', '1:a:0', '-c', 'copy', out])
    for p in os.listdir(LAVORO):           # libera spazio: resta solo il video finale
        if p not in ('video_finale.mp4', 'copertina.jpg'):
            try: os.remove(os.path.join(LAVORO, p))
            except OSError: pass
    return out


def copertina(url, testo, video_base):
    """Copertina 1280x720: l'immagine indicata da n8n oppure, se manca, un fotogramma del video. Testo grande al centro."""
    raw = os.path.join(LAVORO, 'copertina_raw.jpg')
    if url:
        scarica(url, raw)
    else:
        run(['ffmpeg', '-y', '-v', 'error', '-ss', '1', '-i', video_base, '-frames:v', '1', '-q:v', '2', raw])
    out = os.path.join(LAVORO, 'copertina.jpg')
    vf = 'scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720'
    testo = (testo or '').replace('\\n', '\n').strip()
    if testo and os.path.exists(FONT):
        righe = [r.strip().upper() for r in testo.split('\n') if r.strip()][:4]
        size = 130 if len(righe) <= 2 else 95
        size = min(size, int(1180 / (0.72 * max(len(r) for r in righe))))   # le righe lunghe non escono dal bordo
        gap = int(size * 0.25)
        totale = len(righe) * size + (len(righe) - 1) * gap
        for i, r in enumerate(righe):          # una riga alla volta, cosi' ognuna e' centrata
            tf = os.path.join(LAVORO, f'testo_{i}.txt')
            with open(tf, 'w') as f:
                f.write(r)
            y = f'(h-{totale})/2+{i * (size + gap)}'
            vf += (f",drawtext=fontfile={FONT}:textfile={tf}:fontsize={size}:fontcolor=white:borderw=8:bordercolor=black@0.85"
                   f":x=(w-text_w)/2:y={y}")
    for q in (2, 4, 6, 9):
        run(['ffmpeg', '-y', '-v', 'error', '-i', raw, '-vf', vf, '-frames:v', '1', '-q:v', q, out])
        if os.path.getsize(out) < 1_900_000:
            break
    return out


# ---------------------------------------------------------------- YOUTUBE
def token():
    data = urllib.parse.urlencode({'client_id': os.environ['YT_CLIENT_ID'], 'client_secret': os.environ['YT_CLIENT_SECRET'],
                                   'refresh_token': os.environ['YT_REFRESH_TOKEN'], 'grant_type': 'refresh_token'}).encode()
    with urllib.request.urlopen(urllib.request.Request('https://oauth2.googleapis.com/token', data=data), timeout=60) as r:
        return json.loads(r.read().decode())['access_token']


def carica_youtube(path, p):
    tok = token()
    snippet = {'title': str(p.get('titolo', ''))[:100], 'description': str(p.get('descrizione', ''))[:4900],
               'tags': [t for t in (p.get('tag') or []) if t][:40], 'categoryId': str(p.get('categoria') or '22')}
    if p.get('lingua'):
        snippet['defaultLanguage'] = p['lingua']
        snippet['defaultAudioLanguage'] = p['lingua']
    status = {'privacyStatus': p.get('privacy') or 'public', 'selfDeclaredMadeForKids': False}
    if p.get('pubblica_il'):
        status['privacyStatus'] = 'private'
        status['publishAt'] = p['pubblica_il']
    meta = {'snippet': snippet, 'status': status}
    size = os.path.getsize(path)
    req = urllib.request.Request('https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status',
                                 data=json.dumps(meta).encode(), method='POST',
                                 headers={'Authorization': 'Bearer ' + tok, 'Content-Type': 'application/json; charset=UTF-8',
                                          'X-Upload-Content-Length': str(size), 'X-Upload-Content-Type': 'video/mp4'})
    with urllib.request.urlopen(req, timeout=120) as r:
        sessione = r.headers['Location']
    log(f'upload di {size / 1e9:.2f} GB')
    pezzo = 64 * 1024 * 1024
    inizio = 0
    errori = 0
    with open(path, 'rb') as f:
        while inizio < size:
            f.seek(inizio)
            dati = f.read(pezzo)
            fine = inizio + len(dati) - 1
            put = urllib.request.Request(sessione, data=dati, method='PUT',
                                         headers={'Authorization': 'Bearer ' + tok, 'Content-Length': str(len(dati)),
                                                  'Content-Range': f'bytes {inizio}-{fine}/{size}'})
            try:
                with urllib.request.urlopen(put, timeout=600) as r:
                    risposta = json.loads(r.read().decode())
                    log('upload completato: ' + risposta['id'])
                    return risposta['id']
            except urllib.error.HTTPError as e:
                if e.code == 308:
                    rng = e.headers.get('Range')
                    inizio = int(rng.split('-')[1]) + 1 if rng else 0
                    errori = 0
                    log(f'caricati {inizio / 1e9:.2f} GB')
                    continue
                if e.code == 401:
                    tok = token()
                elif e.code not in (500, 502, 503, 504):
                    raise RuntimeError('YouTube ha rifiutato il caricamento: ' + str(e.code) + ' ' + e.read().decode()[:500])
                errori += 1
            except Exception as e:
                errori += 1
                log('errore di rete: ' + str(e))
            if errori > 8:
                raise RuntimeError('troppi errori durante il caricamento')
            time.sleep(min(60, 5 * errori))
            stato = urllib.request.Request(sessione, data=b'', method='PUT',
                                           headers={'Authorization': 'Bearer ' + tok, 'Content-Length': '0',
                                                    'Content-Range': f'bytes */{size}'})
            try:
                with urllib.request.urlopen(stato, timeout=120) as r:
                    return json.loads(r.read().decode())['id']
            except urllib.error.HTTPError as e:
                if e.code == 308:
                    rng = e.headers.get('Range')
                    inizio = int(rng.split('-')[1]) + 1 if rng else 0
    raise RuntimeError('caricamento non concluso')


def carica_copertina(video_id, img):
    if not img:
        return ''
    try:
        with open(img, 'rb') as f:
            dati = f.read()
        req = urllib.request.Request(f'https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={video_id}',
                                     data=dati, method='POST', headers={'Authorization': 'Bearer ' + token(), 'Content-Type': 'image/jpeg'})
        urllib.request.urlopen(req, timeout=120).read()
        return 'ok'
    except Exception as e:
        return 'copertina non caricata: ' + str(e)[:200]


def avvisa(p, esito):
    url = p.get('callback_url')
    log('esito: ' + json.dumps(esito))
    if not url:
        return
    try:
        http_json(url, {'id': p.get('id'), **esito})
    except Exception as e:
        log('callback non riuscita: ' + str(e))


def main():
    p = json.loads(os.environ['PAYLOAD'])
    t0 = time.time()
    os.makedirs(LAVORO, exist_ok=True)
    try:
        secondi = int(float(p.get('durata_minuti') or 180) * 60)
        fps = int(p.get('fps') or 30)
        d = float(p.get('dissolvenza_sec') or 2)
        clips = prepara_clip(p['clips'], int(p.get('max_sec_clip') or 60), fps, p.get('tipo_media') or 'video')
        base, base_sec = base_video(clips, d, p.get('bitrate_video') or '4500k', fps)
        log(f'base video: {base_sec:.1f} s')
        a = audio_finale(base_audio(p['audio'], float(p.get('dissolvenza_audio_sec') or 3)), secondi, p.get('volume') or 1.0)
        img = copertina(p.get('copertina_url'), p.get('testo_copertina'), base)
        video = video_finale(base, base_sec, a, secondi)
        log(f'video pronto: {durata(video) / 60:.1f} min, {os.path.getsize(video) / 1e9:.2f} GB')
        if os.environ.get('DRY_RUN') == '1':
            avvisa(p, {'stato': 'PROVA OK', 'video_id': '', 'link': '', 'errore': '', 'minuti_lavoro': round((time.time() - t0) / 60, 1)})
            return
        vid = carica_youtube(video, p)
        nota = carica_copertina(vid, img)
        avvisa(p, {'stato': 'PUBBLICATO', 'video_id': vid, 'link': 'https://www.youtube.com/watch?v=' + vid,
                   'errore': '' if nota in ('', 'ok') else nota, 'minuti_lavoro': round((time.time() - t0) / 60, 1)})
    except Exception as e:
        traceback.print_exc()
        avvisa(p, {'stato': 'ERRORE', 'video_id': '', 'link': '', 'errore': str(e)[:500], 'minuti_lavoro': round((time.time() - t0) / 60, 1)})
        sys.exit(1)


PAYLOAD_ESEMPIO = {
    'id': 'AMB-001', 'durata_minuti': 180, 'clips': ['https://...pexels...mp4'], 'audio': ['https://drive.usercontent.google.com/download?id=...&export=download&confirm=t'],
    'titolo': 'Rain on Window Sounds for Sleeping | 3 Hours', 'descrizione': '...', 'tag': ['rain sounds'], 'categoria': '22',
    'privacy': 'public', 'pubblica_il': '', 'lingua': '', 'copertina_url': 'https://images.pexels.com/...', 'testo_copertina': 'RAIN\\n3 HOURS',
    'callback_url': 'https://.../webhook/ambience-fatto', 'bitrate_video': '4500k', 'dissolvenza_sec': 2,
}

if __name__ == '__main__':
    main()
