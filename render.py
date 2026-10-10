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
import base64, json, math, os, shutil, subprocess, sys, time, traceback
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
def prepara_clip(urls, max_sec, fps, tipo_media='video', nome='clip'):
    """Normalizza le clip a 1920x1080. Con tipo_media = foto ogni url e' un'immagine ferma (come l'originale con foto fissa)."""
    foto = str(tipo_media).lower() == 'foto'
    clips = []
    for i, u in enumerate(urls):
        raw = scarica(u, os.path.join(LAVORO, f'{nome}_raw_{i}' + ('.jpg' if foto else '.mp4')))
        out = os.path.join(LAVORO, f'{nome}_{i}.mp4')
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
    # tagli in FOTOGRAMMI (non in secondi): nessun fotogramma doppio o mancante nel punto in cui il loop riparte
    f_inizio = round(d * fps)
    f_fine = round((offset + d) * fps)       # escluso: l'ultimo fotogramma e' quello subito prima della ripartenza
    filtri.append(f'[{prec}]trim=start_frame={f_inizio}:end_frame={f_fine},setpts=PTS-STARTPTS[out]')
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


# ---------------------------------------------------------------- EFFETTO METEO (pioggia o neve che cade)
def effetto_meteo(base, base_sec, effetto, intensita, bitrate, fps):
    """Aggiunge pioggia o neve che cade sopra la scena (come i video originali con inquadratura ferma).
    Il movimento compie un numero intero di giri nella durata della base, cosi' il loop resta senza scatti."""
    effetto = str(effetto or '').strip().lower()
    if effetto not in ('pioggia', 'neve'):
        return base
    forza = {'leggera': 0.6, 'media': 1.0, 'forte': 1.6}.get(str(intensita or 'media').strip().lower(), 1.0)
    n = max(1, round(base_sec * fps))
    giri = lambda vel: max(1, round(n * vel)) / n         # velocita' corretta: giri interi nella base
    tex = os.path.join(LAVORO, 'meteo.png')
    dens = (0.0018 if effetto == 'pioggia' else 0.0006) * forza
    run(['ffmpeg', '-y', '-v', 'error', '-f', 'lavfi', '-i', f"nullsrc=s=1920x1080,format=gray,geq=lum='if(lt(random(1),{dens:.5f}),255,0)'",
         '-frames:v', '1', tex])
    if effetto == 'pioggia':
        vicino = f"gblur=sigma=0.6:sigmaV=22,lutyuv=y='min(255,val*9)',scroll=v={-giri(0.05):.6f}"
        lontano = f"scale=960:540,gblur=sigma=0.4:sigmaV=10,lutyuv=y='min(255,val*7)',scale=1920:1080,scroll=v={-giri(0.025):.6f}"
        opac = min(0.75, 0.45 * forza)
    else:
        vicino = f"gblur=sigma=2.2,lutyuv=y='min(255,val*14)',scroll=v={-giri(0.006):.6f}"
        lontano = f"scale=960:540,gblur=sigma=1.2,lutyuv=y='min(255,val*10)',scale=1920:1080,scroll=v={-giri(0.003):.6f}"
        opac = min(0.9, 0.7 * forza)
    filtro = (f"[1]format=gray,split[a][b];[a]{vicino},format=gbrp[v1];[b]{lontano},format=gbrp,colorchannelmixer=rr=0.6:gg=0.6:bb=0.6[v2];"
              f"[v1][v2]blend=all_mode=screen[m];[0]format=gbrp[bg];[bg][m]blend=all_mode=screen:all_opacity={opac:.2f},format=yuv420p[out]")
    out = os.path.join(LAVORO, 'base_meteo.mp4')
    kbit = int(str(bitrate).lower().rstrip('k'))
    run(['ffmpeg', '-y', '-v', 'error', '-i', base, '-loop', '1', '-framerate', fps, '-i', tex, '-filter_complex', filtro, '-map', '[out]',
         '-frames:v', n, '-c:v', 'libx264', '-preset', 'medium', '-b:v', f'{kbit}k', '-maxrate', f'{int(kbit * 1.5)}k', '-bufsize', f'{kbit * 2}k',
         '-g', fps * 2, '-keyint_min', fps * 2, '-sc_threshold', '0', '-r', fps, '-pix_fmt', 'yuv420p', '-movflags', '+faststart', out])
    log(f'effetto {effetto} aggiunto ({intensita or "media"})')
    return out


# ---------------------------------------------------------------- MOTORE AI (Fal.ai): immagine simile all'originale + animazione
FAL_IMG = 'fal-ai/nano-banana-2/edit'
FAL_VID = 'fal-ai/kling-video/v2.6/pro/image-to-video'


def fal(modello, dati, attesa_max=1200):
    """Chiamata alla coda di Fal.ai: invia, aspetta il risultato, lo restituisce."""
    chiave = os.environ.get('FAL_KEY', '')
    if not chiave:
        raise RuntimeError('manca il secret FAL_KEY nel repository GitHub')
    h = {'Authorization': 'Key ' + chiave}
    inviato, _ = http_json('https://queue.fal.run/' + modello, dati, headers=h)
    stato_url, risultato_url = inviato['status_url'], inviato['response_url']
    t0 = time.time()
    while time.time() - t0 < attesa_max:
        time.sleep(8)
        st, _ = http_json(stato_url, headers=h)
        if st.get('status') == 'COMPLETED':
            res, _ = http_json(risultato_url, headers=h)
            return res
        if st.get('status') not in ('IN_QUEUE', 'IN_PROGRESS'):
            raise RuntimeError('Fal.ai: ' + json.dumps(st)[:300])
    raise RuntimeError('Fal.ai: tempo scaduto per ' + modello)


def url_esiste(u):
    try:
        with urllib.request.urlopen(urllib.request.Request(u, method='HEAD', headers={'User-Agent': 'Mozilla/5.0'}), timeout=30) as r:
            return r.status == 200 and int(r.headers.get('Content-Length') or 2000) > 1500
    except Exception:
        return False


def scena_ai(p):
    """1) Nano Banana ricrea la scena dell'originale (stessa composizione, immagine nuova, senza scritte).
       2) Kling la anima (con loop_ai = catena main() aggiunge poi la clip di ritorno)."""
    rif = [u for u in (p.get('riferimenti') or []) if url_esiste(u)][:1]
    if not rif:
        raise RuntimeError('nessuna immagine di riferimento raggiungibile del video originale')
    log('riferimento: ' + rif[0])
    # variazione (Impostazioni: variazione = nessuna / leggera / media / forte, vuota = media):
    # stessa atmosfera e stesso tipo di scena dell'originale, ma un'immagine NOSTRA, non una copia riconoscibile
    var = str(p.get('variazione') or 'media').strip().lower()
    if var == 'nessuna':
        guida = 'Recreate this exact scene as a brand-new photorealistic 16:9 image: same composition, framing, subjects, lighting, colors, weather and mood. '
    elif var == 'leggera':
        guida = ('Create a new photorealistic 16:9 image of the same kind of scene: same mood, weather, lighting and color palette, '
                 'similar framing, but with small changes in the details (shape and position of plants, trees and objects). ')
    elif var == 'forte':
        guida = ('Create a new original photorealistic 16:9 image inspired by this scene: same theme, weather and mood, '
                 'but a different place, different viewpoint and different arrangement of all elements. ')
    else:
        guida = ('Create a new photorealistic 16:9 image inspired by this scene: keep the same theme, mood, weather, time of day, '
                 'lighting and color palette, match the reference colors and saturation (same vivid greens), but change the specific details: different plants and trees, different arrangement '
                 'of the elements, slightly different viewpoint. It must look like a different shot of a similar place, not a copy. ')
    prompt_img = guida + str(p.get('prompt_immagine') or '') + ' No text, no letters, no logos, no watermark, no people.'
    img = fal(FAL_IMG, {'prompt': prompt_img, 'image_urls': rif, 'aspect_ratio': '16:9',
                        'resolution': p.get('risoluzione_ai') or '2K', 'output_format': 'jpeg', 'num_images': 1})
    img_url = img['images'][0]['url']
    log('immagine AI: ' + img_url)
    prompt_vid = ('Static locked-off camera, no camera movement, no zoom, no pan. ' + str(p.get('prompt_movimento') or '') +
                  ' Clearly visible motion for the whole clip, only of the elements that naturally move in this scene '
                  '(for example falling rain, dripping water, leaves, flames, smoke, waves, mist). Realistic, continuous, natural motion at real-time speed '
                  '(filmed at normal speed, never slow motion, constant speed for the whole clip).')
    dati = {'prompt': prompt_vid, 'start_image_url': img_url, 'duration': str(p.get('secondi_ai') or '10'), 'generate_audio': False,
            'negative_prompt': 'slow motion, time-lapse, speed changes, still image, frozen, static scene, camera movement, zoom, pan, shake, people, text, watermark, blur, distortion, low quality'}
    if modo_loop(p) == 'fine_uguale':   # primo = ultimo fotogramma: loop perfetto ma l'AI tende a muovere poco
        dati['end_image_url'] = img_url
    vid = fal(FAL_VID, dati)
    vid_url = vid['video']['url']
    log('video AI: ' + vid_url)
    p['_dati_kling'] = dati
    return [vid_url], img_url


def modo_loop(p):
    """Impostazioni loop_ai: catena (vuota) = 2 clip AI che si chiudono sull'immagine iniziale, loop perfetto con movimento (~1,5 $);
    migliore = 1 clip, si ripete il tratto piu' simile (~0,80 $, la ripartenza puo' vedersi); fine_uguale = 1 clip con primo = ultimo fotogramma."""
    m = str(p.get('loop_ai') or '').strip().lower()
    if not m:
        m = 'fine_uguale' if str(p.get('fine_uguale') or '').upper() == 'SI' else 'catena'
    return m


def carica_su_fal(path, tipo='image/jpeg'):
    """Carica un file locale sullo spazio di Fal.ai e ne restituisce l'indirizzo; se non riesce usa il file incorporato (data URI)."""
    dati = open(path, 'rb').read()
    try:
        h = {'Authorization': 'Key ' + os.environ.get('FAL_KEY', '')}
        ini, _ = http_json('https://rest.alpha.fal.ai/storage/upload/initiate?storage_type=fal-cdn-v3',
                           {'content_type': tipo, 'file_name': os.path.basename(path)}, headers=h)
        req = urllib.request.Request(ini['upload_url'], data=dati, method='PUT', headers={'Content-Type': tipo})
        with urllib.request.urlopen(req, timeout=120):
            pass
        log('fotogramma caricato: ' + ini['file_url'])
        return ini['file_url']
    except Exception as e:
        log('caricamento su Fal non riuscito (' + str(e)[:120] + '): uso il fotogramma incorporato')
        return 'data:' + tipo + ';base64,' + base64.b64encode(dati).decode()


def fotogramma(path, n):
    """Estrae il fotogramma numero n (contando da 0) in JPEG di alta qualita'."""
    out = path.replace('.mp4', f'_f{n}.jpg')
    run(['ffmpeg', '-y', '-v', 'error', '-i', path, '-vf', f'select=eq(n\\,{n})', '-vsync', '0', '-frames:v', '1', '-q:v', '1', out])
    return out


def clip_ritorno(p, clip_a, img_url, fps):
    """Seconda clip AI: parte da un fotogramma della prima poco prima della fine (cosi' le due clip si sovrappongono
    e sfumano l'una nell'altra) e finisce sull'immagine iniziale: il video torna al punto di partenza, movimento continuo."""
    na = conta_fotogrammi(clip_a)
    k1 = max(1, min(int(round(float(p.get('dissolvenza_catena') or 1) * fps)), na // 4))
    s = na - 1 - k1
    f = carica_su_fal(fotogramma(clip_a, s))
    dati = dict(p.get('_dati_kling') or {})
    dati['start_image_url'] = f
    dati['end_image_url'] = img_url
    vid = fal(FAL_VID, dati)
    log('video AI di ritorno (parte dal fotogramma ' + str(s) + '): ' + vid['video']['url'])
    return vid['video']['url'], s


def conta_fotogrammi(path):
    return int(subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0', '-show_entries', 'stream=nb_read_frames',
                               '-of', 'csv=p=0', path], check=True, capture_output=True, text=True).stdout.strip())


def base_catena(clip_a, clip_b, s, bitrate, fps, dissolvenza=1.0):
    """Unisce A e B senza giunture visibili, con due sfumature esatte fotogramma per fotogramma:
    1) A -> B: B parte dal fotogramma s di A, quindi gli ultimi fotogrammi di A e i primi di B mostrano la stessa scena
       e si sfumano (anche la velocita' del movimento passa gradualmente da una clip all'altra);
    2) B -> A: B finisce quasi sull'immagine iniziale; l'ultimo tratto di B sfuma nel primo tratto di A.
    Il file inizia subito dopo la seconda sfumatura e finisce esattamente sul fotogramma che la precede: ripetuto, non ha giunture."""
    na, nb = conta_fotogrammi(clip_a), conta_fotogrammi(clip_b)
    k1 = na - 1 - s                                                   # sovrapposizione A -> B
    k2 = max(1, min(int(round(dissolvenza * fps)), nb // 4, s // 2))  # sfumatura B -> A
    if k1 < 1 or s < k2 + 1 or nb < k1 + k2 + 2:
        raise RuntimeError(f'clip troppo corte per il loop a catena (A {na}, B {nb}, s {s})')
    filtro = (f'[0:v]split=3[a1][a2][a3];[1:v]split=3[b1][b2][b3];'
              f'[a1]trim=start_frame={k2}:end_frame={s},setpts=PTS-STARTPTS[p1];'
              f'[a2]trim=start_frame={s}:end_frame={s + k1},setpts=PTS-STARTPTS[ja];'
              f'[b1]trim=start_frame=0:end_frame={k1},setpts=PTS-STARTPTS[jb];'
              f"[ja][jb]blend=all_expr='A+(B-A)*(N+1)/{k1 + 1}'[p2];"
              f'[b2]trim=start_frame={k1}:end_frame={nb - k2},setpts=PTS-STARTPTS[p3];'
              f'[b3]trim=start_frame={nb - k2}:end_frame={nb},setpts=PTS-STARTPTS[cb];'
              f'[a3]trim=start_frame=0:end_frame={k2},setpts=PTS-STARTPTS[ca];'
              f"[cb][ca]blend=all_expr='A+(B-A)*(N+1)/{k2}'[p4];"
              f'[p1][p2][p3][p4]concat=n=4:v=1:a=0,settb=1/{fps},setpts=N[out]')
    out = os.path.join(LAVORO, 'base_video.mp4')
    kbit = int(str(bitrate).lower().rstrip('k'))
    run(['ffmpeg', '-y', '-v', 'error', '-i', clip_a, '-i', clip_b, '-filter_complex', filtro, '-map', '[out]',
         '-c:v', 'libx264', '-preset', 'medium', '-b:v', f'{kbit}k', '-maxrate', f'{int(kbit * 1.5)}k', '-bufsize', f'{kbit * 2}k',
         '-g', str(fps * 2), '-keyint_min', str(fps * 2), '-sc_threshold', '0', '-r', str(fps),
         '-pix_fmt', 'yuv420p', '-movflags', '+faststart', out])
    log(f'loop a catena: A {na} + B {nb} fotogrammi, sfumature {k1} (A->B) e {k2} (B->A) fotogrammi')
    return out, durata(out)


# ---------------------------------------------------------------- PUNTO DI LOOP MIGLIORE (clip AI)
def miglior_loop(path, fps, min_sec=5.0, coda_sec=1.0):
    """Cerca nella clip i due fotogrammi piu' simili tra loro (inizio e fine del loop) a distanza di almeno min_sec.
    Ripetendo solo quel tratto, il punto di ripartenza quasi non si vede. Confronto su immagini 64x36 in grigio."""
    w, h = 64, 36
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-vf', f'scale={w}:{h},format=gray', '-f', 'rawvideo', '-'],
                         check=True, capture_output=True).stdout
    n = len(raw) // (w * h)
    fr = [raw[k * w * h:(k + 1) * w * h] for k in range(n)]
    minimo = int(min_sec * fps)
    if n < minimo + 2:
        return 0.0, n / fps
    passo = 2                                   # un fotogramma ogni 2: abbastanza preciso e veloce
    best = None
    ultimo = n - int(coda_sec * fps) - 1         # dopo la fine del loop servono coda_sec di clip per la dissolvenza
    for i in range(0, max(1, ultimo - minimo), passo):
        a = fr[i]
        for j in range(i + minimo, ultimo, passo):
            b = fr[j]
            diff = sum(abs(x - y) for x, y in zip(a, b))
            if best is None or diff < best[0]:
                best = (diff, i, j)
    if best is None:
        return 0.0, max(min_sec, (n / fps) - coda_sec)
    _, i, j = best
    log(f'loop migliore: dal fotogramma {i} al {j} ({(j - i) / fps:.1f} s), differenza media {best[0] / (w * h):.1f}')
    return i / fps, j / fps


def taglia(path, inizio, fine, fps):
    out = path.replace('.mp4', '_loop.mp4')
    run(['ffmpeg', '-y', '-v', 'error', '-i', path, '-vf', f"trim=start_frame={round(inizio * fps)}:end_frame={round(fine * fps)},setpts=PTS-STARTPTS",
         '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '16', '-an', out])
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
            vf += (f",drawtext=fontfile={FONT}:textfile={tf}:expansion=none:fontsize={size}:fontcolor=white:borderw=8:bordercolor=black@0.85"
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
    if str(p.get('motore') or '').lower() == 'ai':
        status['containsSyntheticMedia'] = True    # dichiarazione obbligatoria per i contenuti realistici creati con l'AI
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
        tipo = p.get('tipo_media') or 'video'
        img_ai = ''
        if str(p.get('motore') or '').lower() == 'ai':
            # le clip AI escono a 24 fotogrammi al secondo: restiamo a 24 (niente scatti 24->30)
            # e allunghiamo la dissolvenza del loop a 4 secondi, cosi' la ripartenza non si nota
            fps = int(p.get('fps') or 24)
            d = float(p.get('dissolvenza_sec') or 4)
            p['clips'], img_ai = scena_ai(p)
            if not p.get('copertina_url'):
                p['copertina_url'] = img_ai    # copertina = la stessa immagine AI del video, come fa il canale copiato
            tipo = 'video'
            if str(p.get('effetto_su_ai') or 'SI').upper() == 'NO':
                p['effetto'] = ''          # senza la nostra pioggia: resta solo quella dell'AI
        clips = prepara_clip(p['clips'], int(p.get('max_sec_clip') or 60), fps, tipo)
        catena = str(p.get('motore') or '').lower() == 'ai' and len(clips) == 1 and modo_loop(p) == 'catena'
        if catena:
            # loop a catena: clip A (immagine -> movimento libero) + clip B (ultimo fotogramma di A -> immagine)
            ritorno, s_ritorno = clip_ritorno(p, clips[0][0], img_ai, fps)
            b = prepara_clip([ritorno], int(p.get('max_sec_clip') or 60), fps, 'video', nome='ritorno')[0]
            base, base_sec = base_catena(clips[0][0], b[0], s_ritorno, p.get('bitrate_video') or '4500k', fps, float(p.get('dissolvenza_catena') or 1))
        elif str(p.get('motore') or '').lower() == 'ai' and len(clips) == 1 and modo_loop(p) == 'migliore':
            # clip AI: si ripete solo il tratto tra i due fotogrammi piu' simili, con una dissolvenza breve
            a0, a1 = miglior_loop(clips[0][0], fps, float(p.get('loop_min_sec') or 5), float(p.get('dissolvenza_loop') or 1))
            seg = taglia(clips[0][0], a0, a1 + float(p.get('dissolvenza_loop') or 1), fps)
            clips = [(seg, durata(seg))]
            d = float(p.get('dissolvenza_loop') or 1)
        if not catena:
            base, base_sec = base_video(clips, d, p.get('bitrate_video') or '4500k', fps)
        log(f'base video: {base_sec:.1f} s')
        base = effetto_meteo(base, base_sec, p.get('effetto'), p.get('intensita_effetto'), p.get('bitrate_video') or '4500k', fps)
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
