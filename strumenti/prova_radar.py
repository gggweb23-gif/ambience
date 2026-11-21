#!/usr/bin/env python3
"""PROVA RADAR (21 nov 2026, Giorgio: "per i 5 canali selezionati dal RADAR, la miglior versione alla massima qualita' al minimo prezzo,
massimo 1 euro a video, e una prova di 1 minuto per ognuno").
Un minuto di video nel formato del canale da copiare (IMPRONTA: gancio e struttura del loro video migliore, testo tutto nostro):
  1) Claude Sonnet (sforzo basso) scrive il copione: titolo nuovo sullo schema del vincente, gancio subito (prima il risultato),
     domande aperte, solo fatti veri; ogni scena con la ricerca delle clip.
  2) Voce ElevenLabs Flash v2.5 (meta' crediti) con i tempi di ogni lettera: ogni inquadratura cambia con la frase.
  3) Clip VERE in movimento (100% video, niente foto): Pexels (gratis) oppure film d'epoca di pubblico dominio da archive.org
     (Prelinger). Ogni clip controllata da Claude Haiku su un fotogramma piccolo (c'entra con la frase? niente scritte/loghi).
     Inquadrature mai oltre MAX_S secondi, la stessa clip non torna mai, niente movimenti di camera.
  4) Scritte d'impatto ogni tanto (Anton), lampi/dissolvenze brevi tra le scene, musica bassa di sottofondo. 2560x1440.
Uscita: prove_video/radar/<canale>/ (prova.mp4, fotogrammi.jpg, copione.json, fonti.txt, costi.txt).
Env: CANALE (chiave in strumenti/prova_radar_canali.json), SECONDI (60), ANTHROPIC_API_KEY, ELEVENLABS_API_KEY, PEXELS_API_KEY."""
import base64, io, json, os, random, re, subprocess, sys, time, urllib.error, urllib.parse, urllib.request
from PIL import Image, ImageDraw, ImageFont, ImageFilter

E = os.environ.get
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CANALI = json.load(open(os.path.join(ROOT, 'strumenti', 'prova_radar_canali.json')))
NOME = E('CANALE') or 'ominiam'
C = CANALI[NOME]
SECONDI = float(E('SECONDI') or 60)
OUT = os.path.join(ROOT, 'prove_video', 'radar', NOME); os.makedirs(OUT, exist_ok=True)
LAV = '/tmp/radar_' + NOME; os.makedirs(LAV, exist_ok=True)
W, H, FPS = 2560, 1440, 30
MAX_S = float(C.get('max_secondi') or 3.4)
FONT = os.path.join(ROOT, 'ctr_test', 'Anton.ttf')
UA = {'User-Agent': 'ambience-prova-radar/1.0 (+https://github.com/gggweb23-gif/ambience)'}
COSTI = {'claude_sonnet_$': 0.0, 'claude_haiku_$': 0.0, 'elevenlabs_crediti': 0, 'pexels_$': 0.0}
FONTI = []
random.seed(NOME)


def log(*a):
    print(*a, flush=True)


def http(url, dati=None, headers=None, raw=False, timeout=180, tentativi=3):
    for t in range(tentativi):
        try:
            r = urllib.request.Request(url, data=json.dumps(dati).encode() if dati is not None else None,
                                       headers=dict(UA, **({'Content-Type': 'application/json'} if dati is not None else {}), **(headers or {})))
            b = urllib.request.urlopen(r, timeout=timeout).read()
            return b if raw else json.loads(b)
        except urllib.error.HTTPError as e:
            msg = e.read()[:300]
            log('HTTP', e.code, url[:80], msg)
            if e.code in (400, 401, 403, 404):
                raise
            time.sleep(10 * (t + 1))
        except Exception as e:
            log('rete', url[:80], str(e)[:100]); time.sleep(10 * (t + 1))
    raise RuntimeError('non risponde: ' + url[:80])


def claude(prompt, modello='claude-sonnet-5-5', max_tokens=6000, immagine=None, sforzo='low'):
    cont = [{'type': 'text', 'text': prompt}]
    if immagine is not None:
        b = io.BytesIO(); immagine.convert('RGB').save(b, 'JPEG', quality=70)
        cont.insert(0, {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': base64.b64encode(b.getvalue()).decode()}})
    corpo = {'model': modello, 'max_tokens': max_tokens, 'messages': [{'role': 'user', 'content': cont}]}
    if 'sonnet' in modello:
        corpo['output_config'] = {'effort': sforzo}
    j = http('https://api.anthropic.com/v1/messages', corpo, {'x-api-key': E('ANTHROPIC_API_KEY', ''), 'anthropic-version': '2023-06-01'}, timeout=600)
    u = j.get('usage') or {}
    if 'haiku' in modello:
        COSTI['claude_haiku_$'] += u.get('input_tokens', 0) / 1e6 * 1 + u.get('output_tokens', 0) / 1e6 * 5
    else:
        COSTI['claude_sonnet_$'] += u.get('input_tokens', 0) / 1e6 * 3 + u.get('output_tokens', 0) / 1e6 * 15
    return ''.join(x.get('text', '') for x in j['content'] if x.get('type') == 'text')


# ---------------------------------------------------------------- 1) copione
def copione():
    parole = int(SECONDI * 2.55)
    fonte = ('PEXELS stock video search (short concrete visual query in English, 2-4 words, things a stock cameraman would film: '
             'e.g. "empty city street", "desert dunes aerial", "lion walking grass"; never people talking to camera, never text)'
             if C['fonte'] == 'pexels' else
             'ARCHIVE.ORG Prelinger public-domain films of 1940s-1960s America (2-4 words that appear in old educational/industrial film '
             'titles or descriptions: e.g. "drive-in theater", "soda fountain", "suburban family", "highway 1950s", "supermarket"; '
             'no modern things)')
    p = f"""You write YouTube documentary narration in English for a NEW channel that copies the STRUCTURE (not the words) of a winning channel.
Winning channel: {C['competitor']} — {C['descrizione']}
Their best videos (copy the hook and structure, NEVER the text): {C['modelli']}
Our video title (keep it, or improve it on the same pattern): {C['titolo']}
Write ONLY the first {int(SECONDI)} seconds of the video (about {parole} words in total, no more):
- open with the strongest hook immediately: say the result/the most surprising fact first, then promise the explanation;
- plant at least one open loop ("but that's not the strangest part..."), short punchy sentences, vivid and visual;
- EVERYTHING must be TRUE and verifiable: no invented numbers, no fake quotes; if unsure, don't say it;
- split into scenes of 6-11 words each (one sentence or half sentence per scene); every scene must be easy to show with real footage;
- for every scene give "q": the footage search for {fonte}; make each q different and concrete;
- "scritta": an optional on-screen keyword of 1-3 words in CAPS (a number or a strong word) for about one scene in four, else "".
Reply ONLY with JSON: {{"titolo": "...", "copertina": "2-4 word thumbnail text built on the title", "scene": [{{"testo": "...", "q": "...", "scritta": ""}}]}}"""
    t = claude(p, max_tokens=5000)
    j = json.loads(t[t.index('{'):t.rindex('}') + 1])
    n = sum(len(x['testo'].split()) for x in j['scene'])
    if n < parole * 0.88:   # troppo corto: la durata conta (video lunghi sempre sopra gli 8 minuti)
        t = claude(p + f'\n\nYour previous answer had only {n} words, far below {parole}. Here it is:\n' + json.dumps(j, ensure_ascii=False)
                   + f'\nRewrite it to {parole} words (count them), adding new TRUE facts and scenes, same rules, same JSON format.', max_tokens=6000)
        j = json.loads(t[t.index('{'):t.rindex('}') + 1])
    log('titolo:', j['titolo'], '| scene', len(j['scene']), '| parole', sum(len(s['testo'].split()) for s in j['scene']))
    return j


# ---------------------------------------------------------------- 2) voce
def voce(scene):
    testo = ' '.join(s['testo'].strip() for s in scene)
    j = http(f"https://api.elevenlabs.io/v1/text-to-speech/{C['voce']}/with-timestamps?output_format=mp3_44100_192",
             {'text': testo, 'model_id': 'eleven_flash_v2_5', 'language_code': 'en',
              'voice_settings': {'stability': .45, 'similarity_boost': .8, 'style': .2, 'speed': float(C.get('velocita') or 1.04), 'use_speaker_boost': True}},
             {'xi-api-key': E('ELEVENLABS_API_KEY', '')}, timeout=300)
    COSTI['elevenlabs_crediti'] += round(len(testo) * 0.5)
    f = os.path.join(LAV, 'voce.mp3'); open(f, 'wb').write(base64.b64decode(j['audio_base64']))
    al = j['alignment']; ini, fin = al['character_start_times_seconds'], al['character_end_times_seconds']
    tempi, pos = [], 0
    for s in scene:
        n = len(s['testo'].strip())
        a = ini[min(pos, len(ini) - 1)]; b = fin[min(pos + n - 1, len(fin) - 1)]
        tempi.append([a, b]); pos += n + 1
    for i in range(len(tempi)):   # nessun buco: ogni scena dura fino all'inizio della successiva
        tempi[i][0] = 0.0 if i == 0 else tempi[i - 1][1]
        if i + 1 < len(tempi):
            tempi[i][1] = tempi[i + 1][0]
    durata = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f], capture_output=True, text=True).stdout or fin[-1])
    tempi[-1][1] = durata + 0.6
    log('voce', round(durata, 1), 's', len(testo), 'caratteri')
    return f, tempi, durata


# ---------------------------------------------------------------- 3) clip
USATE = set()
PEX = {}


def pexels(q):
    if q in PEX:
        return PEX[q]
    try:
        PEX[q] = http('https://api.pexels.com/videos/search?' + urllib.parse.urlencode({'query': q, 'orientation': 'landscape', 'per_page': 15}),
                      headers={'Authorization': E('PEXELS_API_KEY', '')}, timeout=60).get('videos', [])
    except Exception:
        PEX[q] = []
    return PEX[q]


def fotogramma(f, t):
    g = os.path.join(LAV, os.path.basename(f) + f'_{t:.1f}.jpg')   # mai nella cartella delle prove (finiva nel repository)
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{t:.2f}', '-i', f, '-frames:v', '1', '-vf', 'scale=480:-2', g])
    return Image.open(g) if os.path.exists(g) else None


def scegli(imgs, testo, q):
    """UNA chiamata Haiku per scena: griglia numerata di anteprime piccole -> i numeri che c'entrano, dal migliore (costo ~0,001 $)."""
    if not imgs:
        return []
    cw, ch, cols = 320, 180, 4
    rows = -(-len(imgs) // cols)
    g = Image.new('RGB', (cw * cols, ch * rows), (0, 0, 0)); d = ImageDraw.Draw(g); fo = ImageFont.truetype(FONT, 40)
    for k, im in enumerate(imgs):
        x, y = (k % cols) * cw, (k // cols) * ch
        g.paste(im.convert('RGB').resize((cw, ch)), (x, y))
        d.rectangle((x, y, x + 52, y + 50), fill=(0, 0, 0)); d.text((x + 10, y + 2), str(k + 1), font=fo, fill=(255, 255, 0))
    r = claude(f'Numbered frames of candidate footage for a serious YouTube documentary. Narration: "{testo}" (search: "{q}").\n'
               'List the numbers of the frames that fit the narration well, best first, excluding any frame with visible text, subtitles, logos, '
               'watermarks, people posing for the camera, or blur. Reply only with numbers separated by commas, or NONE.',
               modello='claude-haiku-4-5-20251001', max_tokens=30, immagine=g)
    return [int(x) - 1 for x in re.findall(r'\d+', r) if 0 < int(x) <= len(imgs)]


def clip_pexels(q, testo, quanti):
    out = []
    for q_ in [q, ' '.join(q.split()[:2]), C.get('riserva') or q]:
        cand = []
        for v in pexels(q_):
            if v['id'] in USATE or v.get('duration', 0) < 3 or len(cand) >= 8:
                continue
            fs = sorted([x for x in v['video_files'] if x.get('file_type') == 'video/mp4' and (x.get('width') or 0) >= 1920],
                        key=lambda x: (abs((x.get('width') or 0) - 2560), -(x.get('fps') or 0)))
            if not fs:
                continue
            try:
                im = Image.open(io.BytesIO(http(v['image'], raw=True, timeout=60)))
            except Exception:
                continue
            cand.append((v, fs[0], im))
        for k in scegli([c_[2] for c_ in cand], testo, q_):
            if len(out) >= quanti:
                return out
            v, fl, _ = cand[k]
            if v['id'] in USATE:
                continue
            USATE.add(v['id'])
            f = os.path.join(LAV, f'pex_{v["id"]}.mp4')
            try:
                open(f, 'wb').write(http(fl['link'], raw=True, timeout=300))
            except Exception:
                continue
            out.append((f, float(v['duration']), 0.0)); FONTI.append(f'Pexels {v["id"]} {v.get("url", "")} (licenza Pexels, gratis)')
        if len(out) >= quanti:
            break
    return out


ARCH = {}


def film_archivio(q):
    """Film Prelinger di pubblico dominio su archive.org (licenza controllata), scaricati una volta e usati a pezzi diversi."""
    if q in ARCH:
        return ARCH[q]
    ARCH[q] = []
    try:
        r = http('https://archive.org/advancedsearch.php?' + urllib.parse.urlencode(
            [('q', f'({q}) AND collection:prelinger AND mediatype:movies'), ('fl[]', 'identifier'), ('rows', 12), ('output', 'json')]), timeout=60)
    except Exception:
        return ARCH[q]
    for d in r.get('response', {}).get('docs', []):
        ide = d['identifier']
        if ide in USATE:
            continue
        try:
            m = http('https://archive.org/metadata/' + urllib.parse.quote(ide), timeout=60)
        except Exception:
            continue
        lic = str(m.get('metadata', {}).get('licenseurl') or '')
        if 'publicdomain' not in lic:
            continue
        mp4 = [x for x in m.get('files', []) if str(x.get('name', '')).lower().endswith('.mp4') and 3e6 < float(x.get('size') or 0) < 2.5e8]
        if not mp4:
            continue
        x = sorted(mp4, key=lambda x: -float(x.get('size') or 0))[0]
        f = os.path.join(LAV, f'ia_{re.sub(r"[^A-Za-z0-9_]", "_", ide)[:40]}.mp4')
        try:
            open(f, 'wb').write(http('https://archive.org/download/' + urllib.parse.quote(ide) + '/' + urllib.parse.quote(x['name']), raw=True, timeout=600))
        except Exception:
            continue
        dur = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f], capture_output=True, text=True).stdout or 0)
        if dur < 30:
            continue
        USATE.add(ide); ARCH[q].append([f, dur, ide, []])
        FONTI.append(f'archive.org {ide} https://archive.org/details/{ide} (pubblico dominio: {lic})')
        if len(ARCH[q]) >= 2:
            break
    return ARCH[q]


def clip_archivio(q, testo, quanti):
    out = []
    for q_ in [q, ' '.join(q.split()[:2]), C.get('riserva') or 'america 1950s']:
        cand = []
        for film in film_archivio(q_):
            f, dur, ide, presi = film
            for _ in range(5):
                t = random.uniform(dur * 0.06, dur * 0.92 - 5)
                if any(abs(t - p_) < 10 for p_ in presi) or any(c_[0] == f and abs(c_[2] - t) < 10 for c_ in cand):
                    continue
                im = fotogramma(f, t + 1)
                if im:
                    cand.append((f, dur, t, im, presi))
        for k in scegli([c_[3] for c_ in cand][:12], testo, q_):
            if len(out) >= quanti:
                return out
            f, dur, t, _, presi = cand[k]
            if any(abs(t - p_) < 10 for p_ in presi):
                continue
            presi.append(t); out.append((f, dur, t))
        if len(out) >= quanti:
            break
    return out


# ---------------------------------------------------------------- 4) montaggio
def scritta_png(testo):
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    size = 230
    while size > 80:
        fo = ImageFont.truetype(FONT, size)
        if d.textlength(testo, font=fo) < W * 0.8:
            break
        size -= 10
    tw = d.textlength(testo, font=fo); x, y = (W - tw) / 2, H * 0.68
    ombra = Image.new('RGBA', (W, H), (0, 0, 0, 0)); ImageDraw.Draw(ombra).text((x + 8, y + 10), testo, font=fo, fill=(0, 0, 0, 200))
    im = Image.alpha_composite(im, ombra.filter(ImageFilter.GaussianBlur(10)))
    ImageDraw.Draw(im).text((x, y), testo, font=fo, fill=tuple(C.get('colore_scritta') or (255, 214, 0)) + (255,), stroke_width=6, stroke_fill=(0, 0, 0, 255))
    f = os.path.join(LAV, f'scritta_{abs(hash(testo))}.png'); im.save(f)
    return f


def inquadratura(src, da, dur, i, scritta=None, effetto=None):
    o = os.path.join(LAV, f'shot_{i:03d}.mp4')
    vf = (f'scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,crop={W}:{H},fps={FPS},setsar=1'
          + (',eq=contrast=1.05:saturation=0.9' if C['fonte'] == 'archivio' else '')
          + (f',fade=in:st=0:d=0.18:color={effetto}' if effetto else ''))
    cmd = ['ffmpeg', '-v', 'error', '-y', '-stream_loop', '-1', '-ss', f'{da:.2f}', '-t', f'{dur:.3f}', '-i', src]   # clip corta: ricomincia, mai buchi nei tempi
    if scritta:
        cmd += ['-loop', '1', '-t', f'{dur:.3f}', '-i', scritta_png(scritta),
                '-filter_complex', f'[0:v]{vf}[v];[1:v]format=rgba,fade=in:st=0.12:d=0.2:alpha=1[s];[v][s]overlay=0:0:shortest=1,format=yuv420p[o]', '-map', '[o]']
    else:
        cmd += ['-vf', vf + ',format=yuv420p']
    cmd += ['-an', '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-r', str(FPS), o]
    subprocess.run(cmd, check=True)
    return o


def main():
    t0 = time.time()
    c = copione()
    json.dump(c, open(os.path.join(OUT, 'copione.json'), 'w'), ensure_ascii=False, indent=1)
    fv, tempi, durata = voce(c['scene'])
    shots, n_clip, n_tot = [], 0, 0
    for i, (s, (a, b)) in enumerate(zip(c['scene'], tempi)):
        dur = b - a
        pezzi = max(1, int(-(-dur // MAX_S)))
        cl = (clip_pexels if C['fonte'] == 'pexels' else clip_archivio)(s['q'], s['testo'], pezzi)
        if not cl:
            log('SCENA SENZA CLIP', i, s['q']); cl = [shots[-1][0:3]] if shots else []
        n_ok = len(cl) if cl else 0
        pezzi = max(1, min(pezzi, n_ok or 1))   # meno clip trovate -> inquadrature un po' piu' lunghe, mai la stessa clip ripetuta
        d1 = dur / pezzi
        for k in range(pezzi):
            src = cl[k]
            if C['fonte'] == 'pexels':
                da = random.uniform(0.2, max(0.25, src[1] - d1 - 0.2)) if src[1] > d1 + 0.5 else 0.0
            else:
                da = src[2]
            shots.append((src[0], src[1], da, d1, s.get('scritta') if k == 0 and s.get('scritta') else None, ('white' if i % 5 == 4 else 'black' if i % 7 == 6 else None) if k == 0 else None))
        n_tot += pezzi; n_clip += pezzi if cl else 0
        log(f'scena {i + 1}/{len(c["scene"])}: {round(dur, 1)} s, {pezzi} inquadrature, q="{s["q"]}"')
    files = []
    for j, (src, _, da, d1, scr, eff) in enumerate(shots):
        files.append(inquadratura(src, da, d1, j, scr, eff))
    lista = os.path.join(LAV, 'lista.txt'); open(lista, 'w').write(''.join(f"file '{f}'\n" for f in files))
    muto = os.path.join(LAV, 'muto.mp4')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', lista, '-c', 'copy', muto], check=True)
    musica = os.path.join(ROOT, 'libreria_musica', C.get('musica') or 'mistero_003.mp3')
    finale = os.path.join(OUT, 'prova.mp4')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', muto, '-i', fv, '-stream_loop', '-1', '-i', musica,
                    '-filter_complex', '[1:a]volume=1.0[v];[2:a]volume=0.07,afade=in:d=1[m];[v][m]amix=inputs=2:duration=first:dropout_transition=0,'
                    'loudnorm=I=-14:TP=-1.5:LRA=11[a]', '-map', '0:v', '-map', '[a]', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-shortest', finale], check=True)
    # fotogrammi di controllo
    fr = []
    for j in range(12):
        im = fotogramma(finale, (durata / 12) * j + 0.8)
        if im:
            fr.append(im.resize((480, 270)))
    if fr:
        tav = Image.new('RGB', (480 * 4, 270 * 3)); [tav.paste(im, ((k % 4) * 480, (k // 4) * 270)) for k, im in enumerate(fr)]
        tav.save(os.path.join(OUT, 'fotogrammi.jpg'), quality=85)
    open(os.path.join(OUT, 'fonti.txt'), 'w').write('\n'.join(FONTI))
    usd_cr = 1.65 / 10000   # prezzo della ricarica (21 nov): 1,65 $ ogni 10.000 crediti
    voce_usd = COSTI['elevenlabs_crediti'] * usd_cr
    tot = COSTI['claude_sonnet_$'] + COSTI['claude_haiku_$'] + voce_usd
    # stima video intero: voce e controllo clip crescono con la durata; il copione no (una sola chiamata, ~0,10 $ per 9,5 minuti)
    per_min = (voce_usd + COSTI['claude_haiku_$']) / max(durata / 60, 0.1) + 0.10 / 9.5
    righe = [f'PROVA {NOME}: {c["titolo"]}', f'durata {round(durata, 1)} s | inquadrature {len(shots)} | clip in movimento {round(n_clip / max(n_tot, 1) * 100)}%',
             f'Claude Sonnet (copione) {COSTI["claude_sonnet_$"]:.3f} $ | Claude Haiku (controllo clip) {COSTI["claude_haiku_$"]:.3f} $',
             f'ElevenLabs Flash {COSTI["elevenlabs_crediti"]} crediti = {voce_usd:.3f} $ (prezzo ricarica) | Pexels/archive.org 0 $',
             f'TOTALE prova {tot:.3f} $ | stima video da 9,5 minuti: circa {per_min * 9.5:.2f} $', f'tempo {round((time.time() - t0) / 60, 1)} min']
    open(os.path.join(OUT, 'costi.txt'), 'w').write('\n'.join(righe))
    log('\n'.join(righe))


if __name__ == '__main__':
    main()
