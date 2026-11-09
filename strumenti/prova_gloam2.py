#!/usr/bin/env python3
"""PROVA STILE GLOAM v2 (9 nov, Giorgio: "troppo noioso, il canale originale alterna immagini, video..."):
1 minuto in inglese. Base = clip Pexels in movimento (>= 80%), numeri che corrono disegnati in codice, al massimo 2 immagini 3D (fal) come accento,
musica di tensione bassa sotto la voce. Tagli netti a ritmo (una scena ogni 3-5 s). Non carica niente.
Uscita: prove_video/Prova_Gloam2/ (video_prova.mp4, copertina.jpg, fotogrammi, copione.json, costo.txt)."""
import io, json, os, random, re, subprocess, time, urllib.parse, urllib.request
from PIL import Image, ImageDraw, ImageFont

E = os.environ.get
OUT = 'prove_video/Prova_Gloam2'; os.makedirs(OUT, exist_ok=True)
LAV = '/tmp/gloam2'; os.makedirs(LAV, exist_ok=True)
VOCE = E('VOCE') or 'pNInz6obpgDQGcFmaJgB'
TEMA = E('TEMA') or 'How Knight Capital Lost $440,000,000 in 45 Minutes (August 1, 2012)'
FONT = 'ctr_test/Anton.ttf'
W, H = 1920, 1080
COSTO = {'claude': 0.0, 'fal_immagini': 0, 'voce_caratteri': 0, 'clip_pexels': 0}
log = lambda *a: print(time.strftime('%H:%M:%S'), *a, flush=True)
STILE3D = ('Glossy stylized 3D render like a premium finance documentary: smooth faceless mannequin figures, red for the problem, blue for people, '
           'shiny gold money, deep dark navy background, cinematic rim light, ONE clear subject. No text, no letters, no numbers, no logos. ')
COL = {'red': (232, 57, 70), 'gold': (245, 184, 40), 'blue': (52, 120, 246)}


def http(url, data=None, headers=None, raw=False, timeout=300):
    body = json.dumps(data).encode() if isinstance(data, (dict, list)) else data
    h = {'Content-Type': 'application/json'} if isinstance(data, (dict, list)) else {}
    h.update(headers or {})
    with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=h), timeout=timeout) as r:
        b = r.read()
    return b if raw else json.loads(b.decode() or '{}')


def copione():
    fc = os.path.join(OUT, 'copione.json')
    if os.path.exists(fc) and not E('TEMA'):   # copione gia' pagato in un giro fallito: si riusa
        c = json.load(open(fc)); log('copione ripreso:', c['titolo']); return c
    prompt = f"""You write for a new English YouTube channel in the style of "Gloam" (finance disasters told minute by minute; fast documentary editing that ALTERNATES real footage, animated numbers and a few 3D illustrations).
Topic: {TEMA}. Only well documented facts; no invented quotes.
Write a 60-second test episode, 120-140 spoken words in total, split into 13-16 shots of 6-12 words each (one cut every 3-5 seconds).
Shot 1 = brutal hook with the big number. Build tension minute by minute. End with a sharp twist + "Subscribe for the next one."
Each shot has "voce" (numbers written as words) and ONE visual "tipo":
- "clip": real stock footage searchable on Pexels; give "cerca" = 2-4 plain English words of something FILMABLE (e.g. "stock market screen", "server room lights", "trader stressed office", "new york street night", "clock ticking", "money counting machine"). Never people's names or brands.
- "numero": a big animated number counting up over footage; give "da", "a" (integers), "prefisso" (e.g. "$"), "suffisso" (e.g. "M", " MIN", "%"), and "cerca" for the background footage.
- "3d": glossy 3D illustration; give "immagine" (one clear symbolic subject, faceless figures). Use "3d" EXACTLY 2 times (not in shot 1), never two 3d in a row.
At least 70% of shots must be "clip" or "numero". Optional "etichetta" (max 3 words, CAPITALS) on clip shots for dates/key facts, and "colore" (red|gold|blue).
Also "copertina": {{"immagine": "...", "scritta": "max 3 words, CAPITALS"}} and "titolo".
Reply ONLY with JSON: {{"titolo": "...", "copertina": {{...}}, "shots": [{{"voce": "...", "tipo": "clip", "cerca": "...", "etichetta": "", "colore": "red"}}]}}"""
    for k in range(3):
        j = http('https://api.anthropic.com/v1/messages', {'model': 'claude-sonnet-5-5', 'max_tokens': 16000, 'thinking': {'type': 'between_tools'},
                                                            'output_config': {'effort': 'low'}, 'messages': [{'role': 'user', 'content': prompt}]},
                 {'x-api-key': E('ANTHROPIC_API_KEY', ''), 'anthropic-version': '2023-06-01'})
        u = j.get('usage') or {}
        COSTO['claude'] += u.get('input_tokens', 0) * 3e-6 + u.get('output_tokens', 0) * 15e-6
        t = ''.join(b.get('text', '') for b in j['content'] if b.get('type') == 'text')
        if '{' in t:
            break
        log('risposta senza JSON, riprovo:', j.get('stop_reason'))
    m = re.search(r'\{.*\}', t, re.S).group(0)
    try:
        c = json.loads(m)
    except Exception:
        from json_repair import repair_json
        c = json.loads(repair_json(m))
    json.dump(c, open(os.path.join(OUT, 'copione.json'), 'w'), ensure_ascii=False, indent=1)
    log('copione:', c['titolo'], len(c['shots']), 'scene', sum(len(s['voce'].split()) for s in c['shots']), 'parole')
    return c


USATI = set()


def pexels(cerca, i):
    """Clip orizzontale Full HD, mai la stessa due volte. Se la ricerca non trova nulla, prova con parole piu' generiche."""
    for q in [cerca, ' '.join(cerca.split()[:2]), 'stock market', 'city night']:
        try:
            j = http('https://api.pexels.com/videos/search?' + urllib.parse.urlencode({'query': q, 'orientation': 'landscape', 'per_page': 15, 'size': 'medium'}),
                     headers={'Authorization': E('PEXELS_API_KEY', ''), 'User-Agent': 'Mozilla/5.0'})
        except Exception as e:
            log('pexels:', e); continue
        for v in j.get('videos', []):
            if v['id'] in USATI or v.get('duration', 0) < 4:
                continue
            fs = sorted([f for f in v['video_files'] if (f.get('width') or 0) >= 1280 and f.get('file_type') == 'video/mp4'], key=lambda f: abs((f.get('width') or 0) - 1920))
            if not fs:
                continue
            USATI.add(v['id']); f = os.path.join(LAV, f'pex_{i:02d}.mp4')
            open(f, 'wb').write(http(fs[0]['link'], raw=True, headers={'User-Agent': 'Mozilla/5.0'}))
            COSTO['clip_pexels'] += 1
            log(f'clip {i}: "{q}" -> {v["id"]} ({v.get("duration")} s)')
            return f, v.get('duration', 8)
    raise RuntimeError('nessuna clip per ' + cerca)


def immagine3d(i, desc):
    f = os.path.join(LAV, f'img_{i:02d}.jpg')
    hd = {'Authorization': 'Key ' + E('FAL_KEY', '')}
    inv = http('https://queue.fal.run/fal-ai/nano-banana-2', {'prompt': STILE3D + desc, 'aspect_ratio': '16:9', 'output_format': 'jpeg', 'num_images': 1}, hd)
    for _ in range(150):
        time.sleep(3)
        if http(inv['status_url'], headers=hd).get('status') == 'COMPLETED':
            break
    url = http(inv['response_url'], headers=hd)['images'][0]['url']
    Image.open(io.BytesIO(http(url, raw=True))).convert('RGB').resize((W, H), Image.LANCZOS).save(f, quality=94)
    COSTO['fal_immagini'] += 1
    return f


def voce(i, testo):
    f = os.path.join(LAV, f'voce_{i:02d}.mp3')
    open(f, 'wb').write(http(f'https://api.elevenlabs.io/v1/text-to-speech/{VOCE}?output_format=mp3_44100_128',
                             {'text': testo, 'model_id': 'eleven_multilingual_v2', 'voice_settings': {'stability': .4, 'similarity_boost': .8, 'style': .25}},
                             {'xi-api-key': E('ELEVENLABS_API_KEY', '')}, raw=True))
    COSTO['voce_caratteri'] += len(testo)
    return f


def durata(f):
    return float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f]).decode().strip())


def etichetta(testo, colore, f):
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    if testo:
        fs = 110; fn = ImageFont.truetype(FONT, fs)
        while fn.getlength(testo) > W * .5 and fs > 60:
            fs -= 6; fn = ImageFont.truetype(FONT, fs)
        b = fn.getbbox(testo); w, h = b[2] - b[0], b[3] - b[1]
        x, y = 90, H - 110 - h - 50
        d.rounded_rectangle((x + 8, y + 10, x + w + 68, y + h + 60), 22, fill=(0, 0, 0, 120))
        d.rounded_rectangle((x, y, x + w + 60, y + h + 50), 22, fill=COL.get(colore, COL['red']) + (255,))
        d.text((x + 30 - b[0], y + 25 - b[1]), testo, font=fn, fill='white')
    im.save(f)


def esc(s):
    return str(s).replace('\\', '\\\\').replace(':', '\\:').replace("'", "’").replace('%', '\\%').replace(',', '\\,')


def scena(i, s, dur, out):
    """clip: spezzone Pexels (parte casuale) + etichetta; numero: clip scurita + numero grande che corre; 3d: immagine con leggera spinta."""
    tipo = s.get('tipo', 'clip')
    lab = os.path.join(LAV, f'lab_{i:02d}.png'); etichetta(str(s.get('etichetta') or '').upper()[:22] if tipo == 'clip' else '', s.get('colore'), lab)
    base = f'scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps=30,setsar=1'
    if tipo == '3d':
        fr = int(dur * 30) + 1
        inp = ['-loop', '1', '-t', f'{dur:.3f}', '-i', s['_img']]
        v0 = f"[0:v]scale=3840:-1,zoompan=z='1+0.07*on/{fr}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={fr}:s={W}x{H}:fps=30,setsar=1[b]"
    else:
        f, d0 = s['_clip']
        ss = max(0.0, random.uniform(0, max(0.0, d0 - dur - .5)))
        inp = ['-ss', f'{ss:.2f}', '-stream_loop', '-1', '-i', f]
        v0 = f'[0:v]{base},eq=saturation=1.1:contrast=1.08[b]' if tipo == 'clip' else f'[0:v]{base},eq=brightness=-0.22:saturation=0.7,boxblur=4[b]'
    vf = v0
    if tipo == 'numero':
        da, a = int(s.get('da') or 0), int(s.get('a') or 0); tc = max(1.0, dur * .7)
        expr = f"%{{eif\\:{da}+({a}-{da})*min(1\\,t/{tc:.2f})\\:d}}"
        testo = esc(s.get('prefisso') or '') + expr + esc(s.get('suffisso') or '')
        col = {'red': '0xE83946', 'gold': '0xF5B828', 'blue': '0x3478F6'}.get(s.get('colore'), '0xF5B828')
        vf += f";[b]drawtext=fontfile={FONT}:text='{testo}':fontsize=230:fontcolor={col}:borderw=10:bordercolor=black@0.6:x=(w-text_w)/2:y=(h-text_h)/2[b2]"
        last = 'b2'
    else:
        last = 'b'
    vf += f";[1:v]format=rgba[l];[{last}][l]overlay=0:0,format=yuv420p[o]"
    subprocess.run(['ffmpeg', '-v', 'error', '-y', *inp, '-loop', '1', '-t', f'{dur:.3f}', '-i', lab, '-filter_complex', vf, '-map', '[o]',
                    '-t', f'{dur:.3f}', '-r', '30', '-an', '-c:v', 'libx264', '-preset', 'medium', '-crf', '19', out], check=True)


def main():
    c = copione(); shots = c['shots']
    n3d = 0
    for i, s in enumerate(shots):
        if s.get('tipo') == '3d' and n3d < 2 and i > 0:
            try:
                s['_img'] = immagine3d(i, s.get('immagine') or s.get('cerca') or 'falling gold coins'); n3d += 1; continue
            except Exception as e:
                log('3d non riuscita, uso una clip:', e)
        if s.get('tipo') == '3d':
            s['tipo'] = 'clip'; s['cerca'] = s.get('cerca') or 'stock market screen'
        s['_clip'] = pexels(s.get('cerca') or 'stock market screen', i)
    parti, audio = [], []
    for i, s in enumerate(shots):
        v = voce(i, s['voce']); d = durata(v) + 0.12
        out = os.path.join(LAV, f'scena_{i:02d}.mp4'); scena(i, s, d, out); parti.append(out)
        a = os.path.join(LAV, f'a_{i:02d}.wav')
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', v, '-af', f'apad,atrim=0:{d:.3f}', '-ar', '44100', '-ac', '2', a], check=True); audio.append(a)
    open(os.path.join(LAV, 'v.txt'), 'w').write(''.join(f"file '{p}'\n" for p in parti))
    open(os.path.join(LAV, 'a.txt'), 'w').write(''.join(f"file '{p}'\n" for p in audio))
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', os.path.join(LAV, 'v.txt'), '-c', 'copy', os.path.join(LAV, 'video.mp4')], check=True)
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', os.path.join(LAV, 'a.txt'), os.path.join(LAV, 'voce.wav')], check=True)
    mus = 'libreria_musica/tensione_003.mp3'
    tot = durata(os.path.join(LAV, 'voce.wav'))
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', os.path.join(LAV, 'video.mp4'), '-i', os.path.join(LAV, 'voce.wav'), '-stream_loop', '-1', '-i', mus,
                    '-filter_complex', f'[2:a]volume=0.12,afade=t=out:st={max(0, tot - 2):.2f}:d=2[m];[1:a][m]amix=inputs=2:duration=first:normalize=0[a]',
                    '-map', '0:v', '-map', '[a]', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '160k', '-t', f'{tot:.2f}', os.path.join(OUT, 'video_prova.mp4')], check=True)
    # copertina: immagine 3D dedicata + scritta del video (stile canale)
    try:
        ci = immagine3d(99, c['copertina']['immagine'])
        cop = Image.open(ci).resize((1280, 720)); lab = os.path.join(LAV, 'lab_cop.png')
        etichetta(str(c['copertina'].get('scritta') or '').upper()[:22], 'red', lab)
        L = Image.open(lab).resize((1280, 720)); cop.paste(L, (0, 0), L); cop.save(os.path.join(OUT, 'copertina.jpg'), quality=92)
    except Exception as e:
        log('copertina non fatta:', e)
    tot = durata(os.path.join(OUT, 'video_prova.mp4'))
    for k in range(1, 9):
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{tot * (k - .5) / 8:.2f}', '-i', os.path.join(OUT, 'video_prova.mp4'), '-frames:v', '1', '-vf', 'scale=960:-1',
                        os.path.join(OUT, f'fotogramma_{k}.jpg')], check=True)
    mov = sum(1 for s in shots if s.get('tipo') != '3d') / max(1, len(shots))
    costo = (f"durata {tot:.0f} s | scene {len(shots)} (movimento {mov:.0%}) | Claude {COSTO['claude']:.3f} $ | immagini 3D {COSTO['fal_immagini']} (circa {COSTO['fal_immagini'] * 0.08:.2f} $) | "
             f"clip Pexels {COSTO['clip_pexels']} (gratis) | voce {COSTO['voce_caratteri']} crediti")
    open(os.path.join(OUT, 'costo.txt'), 'w').write(costo + '\n'); log('FATTO:', costo)


if __name__ == '__main__':
    main()
