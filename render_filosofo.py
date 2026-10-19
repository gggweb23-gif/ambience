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
import json, math, os, re, shutil, zlib, sys, time, traceback, subprocess, urllib.request, urllib.parse
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
           'Tight framing from the top of the head down to the knees: the figure fills the whole height of the image. '
           'Soft warm window light from the right, cinematic photorealism, highly detailed skin and fabric. '
           'Plain flat light-grey studio background, nothing else in the background. No text, no logo, no watermark.')


# Inquadratura per le situazioni del canale (render_style -> pose): in piedi, seduto o a cavallo.
ACCORDO_LIBERO = ('He faces the viewer, body turned only slightly toward the right side of the image. His face is always fully visible '
                  '(if he wears a helmet it is open-faced and does not hide his eyes), and he looks STRAIGHT into the camera, '
                  'directly at the viewer, with {espressione}. '
                  'He fills the whole height of the image, from the top of his head (or helmet crest) down to at least his knees; '
                  'if he is on horseback, show only him and the head and neck of the horse, tightly cropped, so the image stays tall and narrow. '
                  'Soft warm light from the right, cinematic photorealism, highly detailed skin, metal and fabric. '
                  'Plain flat light-grey studio background, nothing else in the background. No text, no logo, no watermark.')


# Personaggio scelto dall'AI per QUESTO video (colonna render_character_auto): uomo o donna, qualsiasi ruolo dell'epoca.
ACCORDO_AUTO = ('The person faces the viewer, body turned only slightly toward the right side of the image, face fully visible, '
                'looking STRAIGHT into the camera, directly at the viewer, with an expression that fits the role and the story. '
                'The figure fills the whole height of the image, from the top of the head (or headdress, helmet crest) down to at least the knees. '
                'Every piece of clothing, hairstyle, jewellery and object is historically accurate for the period, and fits the RANK of the person: '
                'emperors, generals, senators and nobles wear rich, clean, imposing clothes of fine materials; never ragged clothes unless the story says so. '
                'Soft warm light from the right, cinematic photorealism, highly detailed skin, fabric and metal. '
                'Plain flat light-grey studio background, nothing else in the background. No text, no logo, no watermark.')


VESTITI = ('He is dressed with the AUTHORITY of the highest rank he held in life, in historically accurate clothing of his era, '
           'made of rich, fine, perfectly clean materials: '
           'if he was a Roman EMPEROR (e.g. Marcus Aurelius) he wears an imperial white toga with a broad purple border and a gold-embroidered purple cloak, '
           'or a polished gilded muscle cuirass with a purple paludamentum, and a golden laurel wreath; '
           'if he was a Roman SENATOR or statesman (e.g. Seneca, Cicero) he wears an immaculate white senatorial toga praetexta with a wide purple stripe, '
           'fine linen tunic, gold signet ring; '
           'if he was a Greek philosopher he wears a pristine fine linen chiton and a large neatly draped himation in deep rich colours '
           '(royal blue, burgundy, cream) with a woven gold border, held by a gold fibula; '
           'a modern thinker wears a perfectly tailored dark frock coat, silk waistcoat and white cravat. '
           'He looks powerful, dignified and respected, like the most important man in the room: '
           'never ragged, rough, worn, torn, faded, dirty or poor-looking. ')


# Stile "statua" (render_style: "ritratto": "statua"): il personaggio del video e' la STESSA statua di marmo della copertina.
STATUA = ('Photorealistic white-grey marble statue of {nome}, the historical philosopher, faithful to his known busts, '
          'classical Greco-Roman sculpture with strong defined features, carved curly hair and beard, realistic marble texture with fine veins. '
          'The statue shows the head, shoulders and torso down to the waist, {posa}. '
          'Intense, wise expression, the stone eyes look STRAIGHT at the viewer. Body facing the viewer, turned only slightly toward the right side of the image. '
          'Dramatic cinematic side light from the right, deep shadows, very high contrast. '
          'Plain flat light-grey studio background, nothing else in the background. No text, no logo, no watermark.')
POSE_STATUA = [
    'arms crossed firmly on the chest',
    'one hand thoughtfully touching his chin',
    'one index finger raised as if teaching a lesson',
    'one hand on his heart, the other relaxed',
    'holding a rolled scroll against his chest',
    'one hand open toward the viewer in a calm explaining gesture',
    'one hand raised to his temple as if thinking deeply',
    'arms relaxed along the body, chin slightly raised, proud',
]


def ritratto_statua(nome, cartella, seme=0):
    """Statua del filosofo: volto fisso (master salvato in 'ritratti'), posa diversa a ogni video."""
    slug = re.sub(r'[^a-z0-9]+', '_', nome.lower()).strip('_')[:60]
    master = os.path.join(os.getcwd(), 'ritratti', slug + '_statua_v1.png')
    dest = os.path.join(cartella, 'ritratto.png')
    if not (os.path.exists(master) and os.path.getsize(master) > 2000):
        os.makedirs(os.path.dirname(master), exist_ok=True)
        img = fal('fal-ai/nano-banana-2', {'prompt': STATUA.format(nome=nome, posa=POSE_STATUA[0]), 'aspect_ratio': '3:4',
                                           'resolution': '2K', 'output_format': 'png', 'num_images': 1})
        scarica(img['images'][0]['url'], master)
        log('nuova statua per ' + nome)
    else:
        log('statua gia\' pronta per ' + nome)
    url = url_master = carica_file(master, 'image/png')
    posa = POSE_STATUA[seme % len(POSE_STATUA)]
    try:
        ed = fal('fal-ai/nano-banana-2/edit', {
            'prompt': ('The same marble statue as in the attached image: keep exactly the same face, hair, beard, marble material and lighting. '
                       f'New pose for this video: the statue shows head and torso, {posa}. Stone eyes looking straight at the viewer. '
                       'Plain flat light-grey studio background. No text, no logo.'),
            'image_urls': [url_master], 'aspect_ratio': '3:4', 'resolution': '2K', 'output_format': 'png', 'num_images': 1})
        url = ed['images'][0]['url']
        log('posa della statua: ' + posa)
    except Exception as e:
        log('cambio posa non riuscito (' + str(e)[:100] + '), uso la statua base')
    sc = fal('fal-ai/birefnet', {'image_url': url})
    scarica((sc.get('image') or {}).get('url') or url, dest)
    return dest, url


def sfondo_nero(path, fumo=True):
    """Sfondo come la copertina: nero profondo con un fumo grigio leggero dietro la statua (a sinistra)."""
    from PIL import Image, ImageDraw, ImageFilter
    im = Image.new('RGB', (W, H), (6, 6, 7))
    if fumo:
        st = Image.new('L', (W, H), 0)
        d = ImageDraw.Draw(st)
        for (cx, cy, r, v) in ((0.20, 0.45, 0.42, 70), (0.08, 0.85, 0.30, 45), (0.38, 0.15, 0.25, 30), (0.80, 0.90, 0.22, 18)):
            d.ellipse([W * cx - W * r, H * cy - W * r * 0.7, W * cx + W * r, H * cy + W * r * 0.7], fill=v)
        st = st.filter(ImageFilter.GaussianBlur(160))
        im = Image.composite(Image.new('RGB', (W, H), (150, 150, 155)), im, st)
    im.save(path)
    return path


def font_anton():
    """Font della copertina (Anton) per le scritte del video."""
    p = os.path.join(FONT_DIR, 'Anton-Regular.ttf')
    if not os.path.exists(p):
        os.makedirs(FONT_DIR, exist_ok=True)
        for u in ('https://github.com/google/fonts/raw/main/ofl/anton/Anton-Regular.ttf',
                  'https://cdn.jsdelivr.net/gh/google/fonts@main/ofl/anton/Anton-Regular.ttf'):
            try:
                req = urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=60) as r:
                    b = r.read()
                if len(b) > 20000:
                    open(p, 'wb').write(b); break
            except Exception as e:
                log('font Anton non scaricato da ' + u[:40] + ': ' + str(e)[:80])
        if not os.path.exists(p):   # riserva: pacchetto npm @fontsource/anton
            try:
                run(['npm', 'pack', '@fontsource/anton@5.2.5', '--silent'])
                run(['tar', 'xzf', 'fontsource-anton-5.2.5.tgz'])
                from fontTools.ttLib import TTFont
                f = TTFont('package/files/anton-latin-400-normal.woff'); f.flavor = None; f.save(p)
            except Exception as e:
                log('font Anton non disponibile: ' + str(e)[:100])
    return 'Anton'


def colore_ass(hexc, rif='#FFFFFF'):
    h = (str(hexc or '').strip().lstrip('#') or rif.lstrip('#')).upper()
    if len(h) != 6:
        h = rif.lstrip('#')
    return f'&H00{h[4:6]}{h[2:4]}{h[0:2]}&'


def ritratto_auto(descrizione, cartella):
    """Personaggio diverso per ogni video, descritto dall'AI dello script: si crea direttamente (niente master salvato)."""
    dest = os.path.join(cartella, 'ritratto.png')
    img = fal('fal-ai/nano-banana-2', {'prompt': 'Photorealistic full-figure portrait of ' + descrizione.rstrip('. ') + '. ' + ACCORDO_AUTO,
                                       'aspect_ratio': '3:4', 'resolution': '2K', 'output_format': 'png', 'num_images': 1})
    url = img['images'][0]['url']
    sc = fal('fal-ai/birefnet', {'image_url': url})
    scarica((sc.get('image') or {}).get('url') or url, dest)
    log('personaggio del video (scelto dallo script): ' + descrizione[:160])
    return dest, url


def ritratto(nome, cartella, seme=0, su_misura=False, pose=None, abiti=None, espressione=''):
    """Ritratto del filosofo per QUESTO video. Restituisce (png scontornato, url dell'immagine con lo sfondo).
    - Il VOLTO e' fisso: la prima volta si crea un ritratto 'master' del filosofo e si salva nel repository (cartella ritratti).
    - La POSA cambia a ogni video: si parte dal master (stesso viso, stessi vestiti) e si cambia solo la posizione.
    - Lo sguardo e' sempre dritto verso lo spettatore. L'url serve anche alla copertina, cosi' e' lo stesso personaggio.
    - pose / abiti (facoltativi, da render_style): liste del canale. Con 'abiti' cambia anche il vestito a ogni video
      (stesso viso), cosi' chi guarda capisce subito che e' un video nuovo."""
    slug = re.sub(r'[^a-z0-9]+', '_', nome.lower()).strip('_')[:60]
    master = os.path.join(os.getcwd(), 'ritratti', slug + '_master_v3.png')   # v3 = abiti autorevoli del suo rango (imperatore, senatore, filosofo)
    dest = os.path.join(cartella, 'ritratto.png')
    if not (os.path.exists(master) and os.path.getsize(master) > 2000):
        os.makedirs(os.path.dirname(master), exist_ok=True)
        if su_misura:   # personaggio descritto in Channel Configs (render_character), es. il narratore del canale
            prompt = f'Photorealistic portrait of {nome}, {POSE[0]}. ' + ACCORDO
        else:
            prompt = (f'Photorealistic portrait of {nome}, the historical philosopher, faithful to his known portraits and busts, '
                      f'{POSE[0]}. ' + VESTITI + ACCORDO)
        img = fal('fal-ai/nano-banana-2', {'prompt': prompt, 'aspect_ratio': '3:4', 'resolution': '2K', 'output_format': 'png', 'num_images': 1})
        scarica(img['images'][0]['url'], master if 'ancient Greek philosopher' not in nome else dest)
        if 'ancient Greek philosopher' in nome:
            master = dest
        log('nuovo volto per ' + nome)
    else:
        log('volto gia\' pronto per ' + nome)
    url_master = carica_file(master, 'image/png')
    proprie = [str(x).strip() for x in (pose or []) if str(x).strip()]
    inquadra = ACCORDO_LIBERO.replace('{espressione}', str(espressione or '').strip() or 'a calm, confident expression') if proprie else ACCORDO
    pose = proprie or POSE
    abiti = [str(x).strip() for x in (abiti or []) if str(x).strip()]
    posa = pose[seme % len(pose)]
    url = url_master
    if abiti:
        abito = abiti[(seme // 7) % len(abiti)]   # scelta diversa da quella della posa: le combinazioni si ripetono di rado
        richiesta = ('The same man as in the attached image: keep exactly the same face, hair, beard, age, skin and the same body build. '
                     f'For this video he wears different clothes: {abito}. Historically accurate ancient Roman gear, real metal and leather. '
                     f'New pose for this video: he is {posa}. ' + inquadra)
        log('vestito del video: ' + abito)
    else:
        richiesta = ('The same man as in the attached image: keep exactly the same face, hair, beard, age, skin and the same clothing. '
                     f'New pose for this video: he is {posa}. ' + inquadra)
    try:
        ed = fal('fal-ai/nano-banana-2/edit', {
            'prompt': richiesta,
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


def livello(path, secondi=180):
    """Volume medio (dB) dei primi minuti di un file audio."""
    try:
        r = subprocess.run(['ffmpeg', '-hide_banner', '-t', str(secondi), '-i', path, '-af', 'volumedetect', '-f', 'null', '-'],
                           capture_output=True, text=True)
        m = re.search(r'mean_volume:\s*(-?[\d.]+) dB', r.stderr)
        return float(m.group(1)) if m else -20.0
    except Exception:
        return -20.0


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


def sottotitoli(scene, tempi, cartella, font, size, x, y, max_riga=24, copertina=None):
    """Effetto macchina da scrivere: un evento ASS per ogni lettera, con il cursore bianco alla fine.
    copertina = {'bianco', 'giallo'}: scritte come la copertina (maiuscole, senza riquadro, 1a riga bianca e 2a gialla)."""
    if copertina:
        stile_t = f'Style: T,{font},{size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,0,0,0,0,100,100,1,0,1,2,4,7,0,0,0,1'
    else:
        stile_t = f'Style: T,{font},{size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,3,7,0,7,0,0,0,1'
    righe = ['[Script Info]', 'ScriptType: v4.00+', f'PlayResX: {W}', f'PlayResY: {H}', 'WrapStyle: 2', '',
             '[V4+ Styles]',
             'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, '
             'StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding',
             stile_t, '', '[Events]', 'Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text']
    cursore = '{\\fnDejaVu Sans\\fs' + str(int(size * 0.78)) + '\\c&HFFFFFF&}' + '█'   # cursore alto come le lettere: righe tutte uguali
    if copertina:
        colori = [copertina['bianco'], copertina['giallo']]
        for (t0, t1), sc in zip(tempi, scene):
            bl = blocchi(pulisci(sc.get('testo', '')).upper(), max_riga)
            if not bl:
                continue
            tot = sum(len(' '.join(b)) for b in bl) or 1
            t = t0
            for b in bl:
                n = len(' '.join(b))
                dur = (t1 - t0) * n / tot
                passo = dur * 0.8 / max(1, n)
                k, ev = 0, []
                for ri, riga in enumerate(b):
                    for ci in range(len(riga)):
                        if riga[ci] != ' ':
                            vis = '\\N'.join('{\\c' + colori[min(j, 1)] + '}' + (b[j] if j < ri else riga[:ci + 1]) for j in range(ri + 1))
                            ev.append((t + k * passo, vis))
                        k += 1
                    k += 1   # lo spazio tra una riga e l'altra
                for e, (a, vis) in enumerate(ev):
                    fine = ev[e + 1][0] if e + 1 < len(ev) else t + dur - 0.05
                    righe.append(f'Dialogue: 0,{tempo_ass(a)},{tempo_ass(fine)},T,,0,0,0,,{{\\pos({x},{y})}}{vis}{cursore}')
                t += dur
        p = os.path.join(cartella, 'sottotitoli.ass')
        open(p, 'w', encoding='utf-8').write('\n'.join(righe) + '\n')
        return p
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
    """Carica un file su Fal (link pubblico). Sopra i 90 MB Fal vuole il caricamento a pezzi (multipart),
    altrimenti risponde 413 Payload Too Large: stesso metodo della libreria ufficiale fal-js."""
    h = {'Authorization': 'Key ' + os.environ.get('FAL_KEY', '')}
    dim = os.path.getsize(path)
    base = 'https://rest.alpha.fal.ai/storage/upload/'
    corpo = {'content_type': tipo, 'file_name': os.path.basename(path)}
    if dim <= 90 * 1024 * 1024:
        ini, _ = http_json(base + 'initiate?storage_type=fal-cdn-v3', corpo, headers=h)
        with open(path, 'rb') as f:
            req = urllib.request.Request(ini['upload_url'], data=f.read(), method='PUT', headers={'Content-Type': tipo})
        with urllib.request.urlopen(req, timeout=1800):
            pass
        return ini['file_url']
    ini, _ = http_json(base + 'initiate-multipart?storage_type=fal-cdn-v3', corpo, headers=h)
    u = urllib.parse.urlsplit(ini['upload_url'])
    radice = f'{u.scheme}://{u.netloc}{u.path}'
    coda = ('?' + u.query) if u.query else ''
    pezzo, parti = 10 * 1024 * 1024, []
    with open(path, 'rb') as f:
        n = 0
        while True:
            dati = f.read(pezzo)
            if not dati:
                break
            n += 1
            for tentativo in range(4):
                try:
                    req = urllib.request.Request(f'{radice}/{n}{coda}', data=dati, method='PUT')
                    with urllib.request.urlopen(req, timeout=600) as r:
                        testo = r.read().decode() or '{}'
                        try:
                            etag = json.loads(testo).get('etag')
                        except Exception:
                            etag = None
                        etag = etag or r.headers.get('ETag') or r.headers.get('etag')
                    if not etag:
                        raise RuntimeError('nessun etag per il pezzo ' + str(n))
                    parti.append({'partNumber': n, 'etag': etag})
                    break
                except Exception as e:
                    if tentativo == 3:
                        raise
                    log(f'pezzo {n} non caricato ({str(e)[:80]}), riprovo')
                    time.sleep(5 * (tentativo + 1))
    http_json(f'{radice}/complete{coda}', {'parts': parti})
    log(f'video caricato a pezzi: {len(parti)} pezzi, {dim / 1e6:.0f} MB')
    return ini['file_url']


def rispondi(url, corpo):
    if not url:
        log('nessun resume_url: ' + json.dumps(corpo)[:300]); return
    for k in range(5):
        try:
            http_json(url, corpo); return
        except Exception as e:
            log('risposta a n8n non riuscita (' + str(e)[:120] + '), riprovo'); time.sleep(10 * (k + 1))


def iscrizione(isc, ingressi, filtro, amap, totale):
    """Invito "iscriviti" (colonne subscribe_overlay_* di Channel Configs): immagine nella lingua del canale + clic + campanella.
    Stesse regole di json2video: al secondo N per 4 s, centrata in basso; clic dopo 0,6 s, campana 1 s dopo il clic."""
    img = str(isc.get('img') or '').strip()
    if not img:
        return filtro, amap
    try:
        num = lambda v, d: float(str(v).replace(',', '.')) if str(v if v is not None else '').strip() != '' else d
        sec = num(isc.get('sec'), 10.0)
        png = scarica_sicuro(img, os.path.join(LAVORO, 'iscriviti.png'))
        n = ingressi.count('-i')
        if f'fontsdir={FONT_DIR}[v]' not in filtro:
            raise RuntimeError('catena video non riconosciuta')
        nuovi = ['-loop', '1', '-t', f'{totale:.3f}', '-i', png]
        f2 = filtro.replace(f'fontsdir={FONT_DIR}[v]', f'fontsdir={FONT_DIR}[v0]', 1)
        f2 += (f";[{n}:v]scale=900:-1,format=rgba,fade=t=in:st={sec}:d=0.3:alpha=1,fade=t=out:st={sec + 3.6}:d=0.4:alpha=1[isc];"
                   f"[v0][isc]overlay=x=(W-w)/2:y=640:enable='between(t,{sec},{sec + 4})'[v]")
        suoni, k = [], n + 1
        clic = num(isc.get('clic_ritardo'), 0.6)
        for url, quando, nome in ((isc.get('clic'), sec + clic, 'clic'), (isc.get('campana'), sec + clic + num(isc.get('campana_ritardo'), 1.0), 'campana')):
            if not str(url or '').strip():
                continue
            try:
                f = scarica_sicuro(str(url).strip(), os.path.join(LAVORO, nome + '.mp3'))
            except Exception as e:
                log(nome + ' non disponibile: ' + str(e)[:80]); continue
            nuovi += ['-i', f]
            ms = int(quando * 1000)
            f2 += f";[{k}:a]adelay={ms}|{ms},volume=0.5[s{k}]"
            suoni.append(f'[s{k}]'); k += 1
        if suoni:
            sorgente = amap if amap.startswith('[') else f'[{amap}]'
            f2 += f";{sorgente}{''.join(suoni)}amix=inputs={len(suoni) + 1}:duration=first:normalize=0[aisc]"
            amap = '[aisc]'
        ingressi += nuovi; filtro = f2
        log(f'invito iscrizione al secondo {sec} con {len(suoni)} suoni')
    except Exception as e:
        log('invito iscrizione saltato: ' + str(e)[:150])
    return filtro, amap


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
        nero = str(stile.get('sfondo') or '').strip().lower() == 'nero'
        statua = str(stile.get('ritratto') or '').strip().lower() == 'statua'
        blur = float(stile.get('sfocatura') or 12)
        luce = float(stile.get('luminosita') or -0.06)
        vf = (f'scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},'
              f'gblur=sigma={blur},eq=brightness={luce}:saturation=0.9,format=yuv420p')
        enc = ['-an', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p']
        pezzi, scaricati = [], {}
        for i, (s, (a, b)) in enumerate(zip(scene, tempi)):
            if nero:
                break   # sfondo nero come la copertina: niente clip Pexels
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
        if nero:
            sfondo = sfondo_nero(os.path.join(LAVORO, 'sfondo_nero.png'), str(stile.get('fumo') or 'SI').upper() != 'NO')
            log('sfondo nero come la copertina')
        else:
            lista_s = os.path.join(LAVORO, 'sfondi.txt')
            open(lista_s, 'w').write(''.join(f"file '{x}'\n" for x in pezzi))
            sfondo = os.path.join(LAVORO, 'sfondo.mp4')
            run(['ffmpeg', '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', lista_s, '-c', 'copy', sfondo])
        # 3) ritratto del filosofo
        nome = chi_e(dati)
        log('personaggio: ' + nome)
        seme = zlib.crc32(str(dati.get('titolo') or p.get('id') or '').encode())
        rit = None
        if dati.get('personaggio_auto'):
            try:
                rit, url_ritratto = ritratto_auto(nome, LAVORO)
            except Exception as e:
                log('personaggio automatico non riuscito (' + str(e)[:120] + '), uso il personaggio fisso del canale')
                nome = str(dati.get('personaggio_riserva') or '').strip() or nome
        if rit is None and statua:
            try:
                rit, url_ritratto = ritratto_statua(nome, LAVORO, seme)
            except Exception as e:
                log('statua non riuscita (' + str(e)[:120] + '), uso il ritratto normale')
        if rit is None:
            rit, url_ritratto = ritratto(nome, LAVORO, seme,
                                         su_misura=bool(str(dati.get('personaggio') or '').strip()),
                                         pose=stile.get('pose'), abiti=stile.get('abiti'), espressione=stile.get('espressione'))
        rit = ritaglia(rit)
        num = lambda k, d: float(stile[k]) if str(stile.get(k, '')).strip() != '' else d
        alt = int(H * num('altezza_ritratto', 1.06))      # come l'originale: la figura occupa tutta l'altezza
        x_r = int(W * num('x_ritratto', 0.0))             # attaccata al bordo sinistro
        y_r = int(H * num('y_ritratto', 0.005))
        entra = float(stile.get('entrata_sec') or 0.7)
        # 4) sottotitoli
        come_cop = str(stile.get('testo') or '').strip().lower() == 'copertina'
        if come_cop:   # scritte come la copertina: Anton, maiuscole, bianco + giallo, senza riquadro
            font = stile.get('font') or font_anton()
            ass = sottotitoli(scene, tempi, LAVORO, font, int(num('dimensione_testo', 180)),
                              int(W * num('x_testo', 0.52)), int(H * num('y_testo', 0.36)), int(num('caratteri_riga', 16)),
                              copertina={'bianco': colore_ass(stile.get('colore_testo'), '#FFFFFF'),
                                         'giallo': colore_ass(stile.get('colore_evidenza'), '#FFD21F')})
        else:
            font = stile.get('font') or 'Cormorant Garamond SemiBold'
            ass = sottotitoli(scene, tempi, LAVORO, font, int(num('dimensione_testo', 92)),
                              int(W * num('x_testo', 0.50)), int(H * num('y_testo', 0.44)), int(num('caratteri_riga', 24)))
        # 5) montaggio finale (+ musica se presente)
        musica = str(dati.get('musica') or '').strip()
        ingressi = (['-loop', '1', '-framerate', str(FPS), '-t', f'{totale:.3f}', '-i', sfondo] if nero else ['-i', sfondo]) + ['-loop', '1', '-i', rit, '-i', voce]
        filtro = (f"[1:v]scale=-1:{alt},format=rgba[r];"
                  f"[0:v][r]overlay=x={x_r}:y='if(lt(t,{entra}),{H}-({H}-{y_r})*(1-pow(1-t/{entra},3)),{y_r})':eval=frame:shortest=1,"
                  f"ass={ass}:fontsdir={FONT_DIR}[v]")
        amap = '2:a'
        if musica:
            try:
                mf = scarica_sicuro(musica, os.path.join(LAVORO, 'musica.mp3'))
                ingressi += ['-stream_loop', '-1', '-i', mf]
                vol = float(dati.get('volume_musica') or 0.08)
                # Livello RELATIVO alla voce: 0,06 = musica 24 dB sotto la voce, 0,12 = 18 dB sotto,
                # qualunque sia il volume originale della traccia (le tracce ambient sono spesso molto basse).
                guadagno = (livello(voce) - livello(mf)) + 20 * math.log10(max(0.001, vol))
                log(f'musica: {vol:.3f} -> guadagno {guadagno:+.1f} dB')
                fine_m = max(0.0, totale - 4)
                filtro += (f";[3:a]volume={guadagno:.2f}dB,afade=t=in:d=3,afade=t=out:st={fine_m:.2f}:d=4[m];"
                           f"[2:a][m]amix=inputs=2:duration=first:normalize=0[a]")
                amap = '[a]'
            except Exception as e:
                log('musica non disponibile: ' + str(e)[:100])
        filtro, amap = iscrizione(dati.get('iscrizione') or {}, ingressi, filtro, amap, totale)
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
