#!/usr/bin/env python3
"""
MUSICA DA FILM (comune a tutti i motori): libreria condivisa libreria_musica/ (brani Eleven Music, nessun reclamo Content ID) divisa per UMORE.
Un brano si genera solo se per quell'umore non ce n'e' uno libero; poi resta e si riusa (la libreria cresce da sola, i video successivi non pagano).
Uso: traccia(tratti, stacchi, totale, lav, canale, stile, ...) -> wav con la musica a tratti, cambi in dissolvenza, buchi di silenzio prima delle rivelazioni.
"""
import glob, json, os, random, re, subprocess, urllib.request

UMORI = {
    'mistero': 'mysterious, curious and suspenseful, soft pulsing low strings, light plucks, slow build',
    'tensione': 'tense and urgent, ticking rhythm, deep drums and staccato strings, rising suspense',
    'epico': 'epic and grand, big war drums, brass and choir-like pads, powerful and heroic',
    'azione': 'fast action, driving percussion, aggressive strings, high energy chase',
    'curiosita': 'playful and light, quirky pizzicato strings and light percussion, curious and fun',
    'quotidiano': 'warm and lively daily life, gentle rhythm, plucked strings and soft flutes, relaxed',
    'malinconia': 'melancholic and emotional, slow solo instrument over soft strings, sad and reflective',
    'trionfo': 'triumphant and uplifting, bright brass and strings, celebratory climax',
}


def _run(cmd):
    subprocess.run([str(c) for c in cmd], check=True)


def _durata(f):
    return float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f], capture_output=True, text=True).stdout.strip() or 0)


def brano(lib, umore, evita, stile='', chiave='', log=print):
    os.makedirs(lib, exist_ok=True)
    gia = sorted(glob.glob(os.path.join(lib, f'{umore}_*.mp3')))
    liberi = [f for f in gia if os.path.basename(f) not in evita]
    if liberi:
        return random.choice(liberi)
    if not chiave:
        return random.choice(gia) if gia else None
    prompt = (f'Instrumental cinematic background score for a documentary-style YouTube video, {UMORI[umore]}. '
              + (f'Colour: {stile}. ' if stile else '') + 'No vocals, no lyrics, clean mix, steady loopable feel, no fade-out at the end.')
    req = urllib.request.Request('https://api.elevenlabs.io/v1/music', data=json.dumps({'prompt': prompt, 'music_length_ms': 90000, 'model_id': 'music_v1',
                                 'force_instrumental': True}).encode(), headers={'xi-api-key': chiave, 'Accept': 'audio/mpeg', 'Content-Type': 'application/json'})
    b = urllib.request.urlopen(req, timeout=600).read()
    n = 1 + max([int(re.search(r'_(\d+)\.mp3$', f).group(1)) for f in gia] or [0])
    p = os.path.join(lib, f'{umore}_{n:03d}.mp3'); open(p, 'wb').write(b)
    log('musica nuova in libreria:', os.path.basename(p), f'({len(b) // 1024} KB)')
    return p


def traccia(tratti, stacchi, totale, lav, canale='canale', stile='', lib='libreria_musica', chiave='', log=print, X=1.5, min_tratto=8):
    """tratti = [(inizio, fine, umore)], stacchi = [secondi]. Ritorna il wav della musica (volume pieno: il missaggio lo abbassa sotto la voce)."""
    pulito = []
    for a, b, u in tratti:
        u = u if u in UMORI else 'mistero'
        if pulito and (b - a < min_tratto or pulito[-1][2] == u):
            pulito[-1][1] = b
        else:
            pulito.append([a, b, u])
    if not pulito:
        return None
    pulito[-1][1] = max(pulito[-1][1], totale)
    usati_f = os.path.join(lib, 'usati_' + re.sub(r'\W', '_', str(canale)) + '.json')
    try:
        recenti = json.load(open(usati_f))
    except Exception:
        recenti = []
    pezzi, scelti = [], []
    for i, (a, b, u) in enumerate(pulito):
        f = brano(lib, u, set(recenti[-12:]) | set(scelti), stile, chiave, log)
        if not f:
            continue
        scelti.append(os.path.basename(f))
        lung = b - a + (X if i < len(pulito) - 1 else 0); dur_f = _durata(f)
        off = random.uniform(0, max(0, dur_f - lung - 1)) if dur_f > lung + 1 else 0
        out = os.path.join(lav, f'musf_{i:02d}.wav')
        giro = ['-stream_loop', '-1'] if dur_f < lung else []
        _run(['ffmpeg', '-y', '-v', 'error', *giro, '-ss', f'{off:.2f}', '-i', f, '-af', f'atrim=0:{lung:.2f},asetpts=PTS-STARTPTS,afade=t=in:d={.8 if i else 2}',
              '-ar', '44100', '-ac', '2', out])
        pezzi.append(out)
    if not pezzi:
        return None
    mus = os.path.join(lav, 'musica_film.wav')
    if len(pezzi) == 1:
        _run(['ffmpeg', '-y', '-v', 'error', '-i', pezzi[0], mus])
    else:
        fl, prev = [], '[0:a]'
        for n in range(1, len(pezzi)):
            o = f'[m{n}]' if n < len(pezzi) - 1 else '[mm]'
            fl.append(f'{prev}[{n}:a]acrossfade=d={X}:c1=tri:c2=tri{o}'); prev = o
        _run(['ffmpeg', '-y', '-v', 'error', *sum((['-i', p] for p in pezzi), []), '-filter_complex', ';'.join(fl), '-map', '[mm]', mus])
    buchi = '+'.join(f'between(t,{s - .9:.2f},{s:.2f})' for s in stacchi[:30] if s > 3)
    if buchi:
        m2 = mus[:-4] + '_s.wav'
        _run(['ffmpeg', '-y', '-v', 'error', '-i', mus, '-af', f"volume='1-0.95*({buchi})':eval=frame,afade=t=out:st={max(0, totale - 3):.2f}:d=3", m2]); mus = m2
    json.dump((recenti + scelti)[-40:], open(usati_f, 'w'))
    log('musica: ' + ' | '.join(f'{a:.0f}-{b:.0f}s {u}' for a, b, u in pulito), '| stacchi:', len(stacchi), '| brani:', ', '.join(scelti))
    return mus
