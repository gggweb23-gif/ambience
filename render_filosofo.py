#!/usr/bin/env python3
"""
MULTICHANNEL - Montaggio "filosofo" (formato The Hodos) per i canali con render_engine = github.

Livelli del video:
  1) sfondo: le clip Pexels di ogni scena, sfocate e in movimento, con stacchi netti tra una scena e l'altra;
  2) primo piano: il ritratto del filosofo (immagine AI scontornata) a sinistra, entra dal basso nel primo secondo;
  3) sottotitoli "macchina da scrivere": testo serif bianco su riquadro nero, lettera per lettera, con cursore.

Riceve da n8n (variabile PAYLOAD) solo: id, url del file JSON con le scene (su Drive), resume_url.
Il file JSON contiene: titolo, scene [{testo, audio, media}], personaggio (facoltativo), musica, volume_musica.
Alla fine carica il video su Fal (link pubblico) e chiama resume_url con {"movie": {"status": "done", "url", "duration"}}.
"""
import json, os, re, shutil, zlib, sys, time, traceback, subprocess, urllib.request
from render import scarica, http_json, fal, run, durata, log

LAVORO = os.path.join(os.getcwd(), 'lavoro_filosofo')
W, H, FPS = 1920, 1080, 30
FONT_DIR = os.path.join(os.getcwd(), 'font')

FILOSOFI = ['Marcus Aurelius', 'Seneca', 'Epictetus', 'Socrates', 'Plato', 'Aristotle', 'Diogenes', 'Heraclitus', 'Pythagoras',
            'Zeno', 'Epicurus', 'Confucius', 'Lao Tzu', 'Sun Tzu', 'Schopenhauer', 'Nietzsche', 'Kant', 'Kierkegaard', 'Montaigne',
            'Pascal', 'Spinoza', 'Descartes', 'Voltaire', 'Rousseau', 'Hegel', 'Goethe', 'Emerson', 'Thoreau', 'Dostoevsky',
            'Tolstoy', 'Cicero', 'Plutarch', 'Seneca the Younger', 'Leonardo da Vinci', 'Machiavelli']


def ffprobe_dur(p):
    try:
        return durata(p)
    except Exception:
        return 0.0


def scarica_sicuro(url, path):
    if url.startswith('https://drive.google.com/uc?') and 'confirm=' not in url:
        url = url.replace('https://drive.google.com/uc?', 'https://drive.usercontent.google.com/download?') + '&confirm=t'
    return scarica(url, path)


def scarica_dati(url):
    """Il file JSON con le scene (anche piccolo: niente controllo dimensione)."""
    if url.startswith('https://drive.google.com/uc?') and 'confirm=' not in url:
        url = url.replace('https://drive.google.com/uc?', 'https://drive.usercontent.google.com/download?') + '&confirm=t'
    for k in range(4):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read().decode('utf-8-sig'))
        except Exception as e:
            log('file dati non scaricato (' + str(e)[:120] + '), riprovo'); time.sleep(5 * (k + 1))
    raise RuntimeError('impossibile leggere il file dati ' + url)


def chi_e(dati):
    """Il filosofo del video: colonna render_character, poi il nome nel titolo, poi il piu' citato nel testo."""
    if str(dati.get('personaggio') or '').strip():
        return str(dati['personaggio']).strip()
    norm = lambda n: 'Seneca' if n == 'Seneca the Younger' else n
    titolo = str(dati.get('titolo') or '').lower()
    nel_titolo = [(titolo.find(n.lower()), n) for n in FILOSOFI if n.lower() in titolo]
    if nel_titolo:
        return norm(sorted(nel_titolo)[0][1])
    testo = ' '.join(str(s.get('testo', '')) for s in dati.get('scene', [])).lower()
    conti = sorted(((testo.count(n.lower()), -testo.find(n.lower()), n) for n in FILOSOFI if n.lower() in testo), reverse=True)
    if conti:
        return norm(conti[0][2])
    return 'an ancient Greek philosopher'


POSE = [
    'seated in an antique carved wooden armchair, one hand thoughtfully touching his chin, the other resting on the armrest',
    'seated in an antique armchair holding a closed old leather book on his lap with both hands',
    'seated in an antique armchair, hands calmly folded on his lap, shoulders relaxed',
    'seated in an antique armchair, leaning slightly forward, forearms resting on his knees, fingers interlaced',
    'seated in an antique armchair, one hand raised to his temple as if thinking deeply',
    'seated in an antique armchair holding an old quill pen and a folded letter',
    'seated in an antique armchair, one arm on the armrest and the other hand open in a calm explaining gesture',
    'seated in an antique armchair, one index finger raised near his lips as if asking for silence',
]
ACCORDO = ('His whole body faces the viewer: chest, shoulders and knees toward the camera, turned only very slightly (about 15 degrees) '
           'toward the right side of the image, like a classic seated portrait painting. His head and eyes look STRAIGHT into the camera, '
           'directly at the viewer, calm, serious and wise expression. '
           'His clothing belongs to his era but is elegant, clean and well kept, made of fine quality fabric in deep rich colours '
           '(an ancient philosopher wears a clean fine wool tunic with a neatly draped cloak with a subtle embroidered border; '
           'a modern thinker wears a well-tailored dark frock coat, waistcoat and white cravat). Dignified and refined, '
           'never ragged, worn, torn or dirty, and never royal, flashy or covered in jewels. '
           'Tight framing from the top of the head down to the knees: the figure fills the whole height of the image. '
           'Soft warm window light from the right, cinematic photorealism, highly detailed skin and fabric. '
           'Plain flat light-grey studio background, nothing else in the background. No text, no logo, no watermark.')


def ritratto(nome, cartella, seme=0):
    """Ritratto del filosofo per QUESTO video. Restituisce (png scontornato, url dell'immagine con lo sfondo).
    - Il VOLTO e' fisso: la prima volta si crea un ritratto 'master' del filosofo e si salva nel repository (cartella ritratti).
    - La POSA cambia a ogni video: si parte dal master (stesso viso, stessi vestiti) e si cambia solo la posizione.
    - Lo sguardo e' sempre dritto verso lo spettatore. L'url serve anche alla copertina, cosi' e' lo stesso personaggio."""
    slug = re.sub(r'[^a-z0-9]+', '_', nome.lower()).strip('_')
    master = os.path.join(os.getcwd(), 'ritratti', slug + '_master_v2.png')   # v2 = frontale e vestiti eleganti
    dest = os.path.join(cartella, 'ritratto.png')
    if not (os.path.exists(master) and os.path.getsize(master) > 2000):
        os.makedirs(os.path.dirname(master), exist_ok=True)
        prompt = (f'Photorealistic portrait of {nome}, the historical philosopher, faithful to his known portraits and busts, '
                  f'{POSE[0]}. Period clothing appropriate to his era. ' + ACCORDO)
        img = fal('fal-ai/nano-banana-2', {'prompt': prompt, 'aspect_ratio': '3:4', 'resolution': '2K', 'output_format': 'png', 'num_images': 1})
        scarica(img['images'][0]['url'], master if 'ancient Greek philosopher' not in nome else dest)
        if 'ancient Greek philosopher' in nome:
            master = dest
        log('nuovo volto per ' + nome)
    else:
        log('volto gia\' pronto per ' + nome)
    url_master = carica_file(master, 'image/png')
    posa = POSE[seme % len(POSE)]
    url = url_master
    try:
        ed = fal('fal-ai/nano-banana-2/edit', {
            'prompt': ('The same man as in the attached image: keep exactly the same face, hair, beard, age, skin and the same elegant clothing. '
                       f'New pose for this video: he is {posa}. ' + ACCORDO),
            'image_urls': [url_master], 'aspect_ratio': '3:4', 'resolution': '2K', 'output_format': 'png', 'num_images': 1})
        url = ed['images'][0]['url']
        log('posa del video: ' + posa)
    except Exception as e:
        log('cambio posa non riuscito (' + str(e)[:100] + '), uso il ritratto base')
    sc = fal('fal-ai/birefnet', {'image_url': url})
    url2 = (sc.get('image') or {}).get('url') or url
    scarica(url2, dest)
    return dest, url


def ritaglia(path):
    """Toglie il bordo trasparente intorno alla figura: cosi' l'altezza scelta e' quella del filosofo, non della tela."""
    try:
        from PIL import Image
        im = Image.open(path).convert('RGBA')
        box = im.getchannel('A').point(lambda a: 255 if a > 24 else 0).getbbox()
        if box:
            out = path.replace('.png', '_ritaglio.png')
            im.crop(box).save(out)
            log(f'ritratto ritagliato: {im.size} -> {box[2] - box[0]}x{box[3] - box[1]}')
            return out
    except Exception as e:
        log('ritaglio non riuscito (' + str(e)[:80] + '), uso il ritratto intero')
    return path


def pulisci(t):
    t = str(t or '').replace('’', "'").lower()
    t = re.sub(r"[^\w\s']", ' ', t, flags=re.UNICODE)
    return re.sub(r'\s+', ' ', t).strip()


def blocchi(testo, max_riga=24, max_righe=2):
    """Divide il testo in riquadri da al massimo 2 righe di ~26 caratteri, come l'originale."""
    parole, out, righe, riga = testo.split(), [], [], ''
    for p in parole:
        if len(riga) + len(p) + (1 if riga else 0) <= max_riga or not riga:
            riga = (riga + ' ' + p).strip()
        else:
            righe.append(riga); riga = p
            if len(righe) == max_righe:
                out.append(righe); righe = []
    if riga:
        righe.append(riga)
    if righe:
        out.append(righe)
    return out


def tempo_ass(s):
    s = max(0.0, s)
    h = int(s // 3600); m = int(s % 3600 // 60); sec = s % 60
    return f'{h}:{m:02d}:{sec:05.2f}'


def sottotitoli(scene, tempi, cartella, font, size, x, y, max_riga=24):
    """Effetto macchina da scrivere: un evento ASS per ogni lettera, con il cursore bianco alla fine."""
    righe = ['[Script Info]', 'ScriptType: v4.00+', f'PlayResX: {W}', f'PlayResY: {H}', 'WrapStyle: 2', '',
             '[V4+ Styles]',
             'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, '
             'StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding',
             f'Style: T,{font},{size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,3,7,0,7,0,0,0,1',
             '', '[Events]', 'Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text']
    cursore = r'{\fnDejaVu Sans\c&HFFFFFF&}' + '█'
    for (t0, t1), sc in zip(tempi, scene):
        bl = blocchi(pulisci(sc.get('testo', '')), max_riga)
        if not bl:
            continue
        tot = sum(len(' '.join(b)) for b in bl) or 1
        t = t0
        for b in bl:
            testo = '\\N'.join(b)
            n = len(' '.join(b))
            dur = (t1 - t0) * n / tot
            scrivi = dur * 0.8                              # le lettere compaiono nell'80% del tempo, poi resta ferma
            passo = scrivi / max(1, len(testo))
            vis = ''
            for k, ch in enumerate(testo):
                vis += ch
                if ch == '\\' or (k > 0 and testo[k - 1] == '\\'):
                    continue
                a = t + k * passo
                fine = t + (k + 1) * passo if k < len(testo) - 1 else t + dur - 0.05
                righe.append(f'Dialogue: 0,{tempo_ass(a)},{tempo_ass(fine)},T,,0,0,0,,{{\\pos({x},{y})}}{vis}{cursore}')
            t += dur
    p = os.path.join(cartella, 'sottotitoli.ass')
    open(p, 'w', encoding='utf-8').write('\n'.join(righe) + '\n')
    return p


def carica_file(path, tipo='video/mp4'):
    h = {'Authorization': 'Key ' + os.environ.get('FAL_KEY', '')}
    ini, _ = http_json('https://rest.alpha.fal.ai/storage/upload/initiate?storage_type=fal-cdn-v3',
                       {'content_type': tipo, 'file_name': os.path.basename(path)}, headers=h)
    with open(path, 'rb') as f:
        req = urllib.request.Request(ini['upload_url'], data=f.read(), method='PUT', headers={'Content-Type': tipo})
    with urllib.request.urlopen(req, timeout=1800):
        pass
    return ini['file_url']


def rispondi(url, corpo):
    if not url:
        log('nessun resume_url: ' + json.dumps(corpo)[:300]); return
    for k in range(5):
        try:
            http_json(url, corpo); return
        except Exception as e:
            log('risposta a n8n non riuscita (' + str(e)[:120] + '), riprovo'); time.sleep(10 * (k + 1))


def main():
    p = json.loads(os.environ['PAYLOAD'])
    os.makedirs(LAVORO, exist_ok=True)
    t_inizio = time.time()
    try:
        dati = scarica_dati(p['dati_url'])
        scene = [s for s in dati.get('scene', []) if s.get('audio')]
        if not scene:
            raise RuntimeError('nessuna scena con audio nel file dati')
        stile = dati.get('stile') or {}
        # 1) audio delle scene e loro durata
        tempi, voci, t = [], [], 0.0
        for i, s in enumerate(scene):
            a = scarica_sicuro(s['audio'], os.path.join(LAVORO, f'voce_{i:03d}.mp3'))
            d = ffprobe_dur(a)
            voci.append(a); tempi.append((t, t + d)); t += d
        totale = t
        log(f'{len(scene)} scene, {totale / 60:.1f} minuti di voce')
        lista = os.path.join(LAVORO, 'voci.txt')
        open(lista, 'w').write(''.join(f"file '{v}'\n" for v in voci))
        voce = os.path.join(LAVORO, 'voce.m4a')
        run(['ffmpeg', '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', lista, '-c:a', 'aac', '-b:a', '192k', voce])
        # 2) sfondo: le clip di ogni scena (anche piu' di una, con il loro secondo di partenza), sfocate e scurite.
        #    Ogni pezzo e' tagliato a fotogrammi esatti sulla voce, cosi' video e audio non si sfasano mai.
        blur = float(stile.get('sfocatura') or 12)
        luce = float(stile.get('luminosita') or -0.06)
        vf = (f'scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},'
              f'gblur=sigma={blur},eq=brightness={luce}:saturation=0.9,format=yuv420p')
        enc = ['-an', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p']
        pezzi, scaricati = [], {}
        for i, (s, (a, b)) in enumerate(zip(scene, tempi)):
            m = s.get('media') or []
            lista_m = [{'src': m, 'start': 0}] if isinstance(m, str) else [x for x in m if isinstance(x, dict)]
            lista_m = sorted([x for x in lista_m if str(x.get('src') or '').strip()], key=lambda x: float(x.get('start') or 0)) or [{'src': '', 'start': 0}]
            for k, x in enumerate(lista_m):
                inizio = a + (0 if k == 0 else min(b - a, float(x.get('start') or 0)))
                fine = b if k == len(lista_m) - 1 else a + min(b - a, float(lista_m[k + 1].get('start') or 0))
                nf = int(round(fine * FPS)) - int(round(inizio * FPS))
                if nf <= 0:
                    continue
                out = os.path.join(LAVORO, f'sfondo_{i:03d}_{k}.mp4')
                u = str(x.get('src') or '').strip()
                try:
                    if not u:
                        raise RuntimeError('nessun media')
                    foto = x.get('tipo') == 'image' or re.search(r'\.(jpe?g|png|webp)(\?|$)', u, re.I) or 'images.pexels' in u
                    if u not in scaricati:
                        scaricati[u] = scarica_sicuro(u, os.path.join(LAVORO, f'media_{len(scaricati):04d}' + ('.jpg' if foto else '.mp4')))
                    src = scaricati[u]
                    if not foto:
                        run(['ffmpeg', '-y', '-v', 'error', '-stream_loop', '-1', '-i', src, '-frames:v', str(nf), '-vf', vf] + enc + [out])
                    else:
                        zoom = f"zoompan=z='1+0.0006*on':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={nf + 1}:s={W}x{H}:fps={FPS},"
                        run(['ffmpeg', '-y', '-v', 'error', '-loop', '1', '-i', src, '-frames:v', str(nf), '-vf', zoom + vf] + enc + [out])
                except Exception as e:
                    log(f'scena {i}: sfondo non disponibile ({str(e)[:80]}), uso quello precedente')
                    if pezzi:
                        run(['ffmpeg', '-y', '-v', 'error', '-stream_loop', '-1', '-i', pezzi[-1], '-frames:v', str(nf)] + enc + [out])
                    else:
                        run(['ffmpeg', '-y', '-v', 'error', '-f', 'lavfi', '-i', f'color=c=0x1a140f:s={W}x{H}:r={FPS}',
                             '-frames:v', str(nf)] + enc + [out])
                pezzi.append(out)
        lista_s = os.path.join(LAVORO, 'sfondi.txt')
        open(lista_s, 'w').write(''.join(f"file '{x}'\n" for x in pezzi))
        sfondo = os.path.join(LAVORO, 'sfondo.mp4')
        run(['ffmpeg', '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', lista_s, '-c', 'copy', sfondo])
        # 3) ritratto del filosofo
        nome = chi_e(dati)
        log('personaggio: ' + nome)
        rit, url_ritratto = ritratto(nome, LAVORO, zlib.crc32(str(dati.get('titolo') or p.get('id') or '').encode()))
        rit = ritaglia(rit)
        num = lambda k, d: float(stile[k]) if str(stile.get(k, '')).strip() != '' else d
        alt = int(H * num('altezza_ritratto', 1.06))      # come l'originale: la figura occupa tutta l'altezza
        x_r = int(W * num('x_ritratto', 0.0))             # attaccata al bordo sinistro
        y_r = int(H * num('y_ritratto', 0.005))
        entra = float(stile.get('entrata_sec') or 0.7)
        # 4) sottotitoli
        font = stile.get('font') or 'Cormorant Garamond SemiBold'
        ass = sottotitoli(scene, tempi, LAVORO, font, int(num('dimensione_testo', 92)),
                          int(W * num('x_testo', 0.50)), int(H * num('y_testo', 0.44)), int(num('caratteri_riga', 24)))
        # 5) montaggio finale (+ musica se presente)
        musica = str(dati.get('musica') or '').strip()
        ingressi = ['-i', sfondo, '-loop', '1', '-i', rit, '-i', voce]
        filtro = (f"[1:v]scale=-1:{alt},format=rgba[r];"
                  f"[0:v][r]overlay=x={x_r}:y='if(lt(t,{entra}),{H}-({H}-{y_r})*(1-pow(1-t/{entra},3)),{y_r})':eval=frame:shortest=1,"
                  f"ass={ass}:fontsdir={FONT_DIR}[v]")
        amap = '2:a'
        if musica:
            try:
                mf = scarica_sicuro(musica, os.path.join(LAVORO, 'musica.mp3'))
                ingressi += ['-stream_loop', '-1', '-i', mf]
                vol = float(dati.get('volume_musica') or 0.08)
                fine_m = max(0.0, totale - 4)
                filtro += (f";[3:a]volume={vol},afade=t=in:d=3,afade=t=out:st={fine_m:.2f}:d=4[m];"
                           f"[2:a][m]amix=inputs=2:duration=first:normalize=0[a]")
                amap = '[a]'
            except Exception as e:
                log('musica non disponibile: ' + str(e)[:100])
        finale = os.path.join(LAVORO, 'video_finale.mp4')
        run(['ffmpeg', '-y', '-v', 'error'] + ingressi + ['-filter_complex', filtro, '-map', '[v]', '-map', amap,
             '-t', f'{totale:.3f}', '-c:v', 'libx264', '-preset', 'faster', '-crf', '21', '-r', str(FPS), '-pix_fmt', 'yuv420p',
             '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', finale])
        log(f'video pronto: {durata(finale) / 60:.1f} min, {os.path.getsize(finale) / 1e6:.0f} MB')
        if os.environ.get('DRY_RUN') == '1':
            log('prova: il video resta come artifact, nessun caricamento')
            return
        url = carica_file(finale)
        log('video caricato: ' + url)
        rispondi(p.get('resume_url'), {'movie': {'status': 'done', 'url': url, 'duration': round(durata(finale), 2), 'ritratto_url': url_ritratto,
                                                 'minuti_lavoro': round((time.time() - t_inizio) / 60, 1)}})
    except Exception as e:
        traceback.print_exc()
        rispondi(p.get('resume_url'), {'movie': {'status': 'failed', 'message': str(e)[:500]}})
        sys.exit(1)


if __name__ == '__main__':
    main()
