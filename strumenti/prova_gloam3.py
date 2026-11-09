#!/usr/bin/env python3
"""PROVA STILE GLOAM v3 (9 nov, Giorgio: "alzare il livello"): sopra la v2 aggiunge orologio del disastro + contatore delle perdite fissi in alto,
schermo di borsa disegnato in codice che crolla in diretta, colpo di zoom + lampo rosso + suono sui numeri, capitoli a schermo, scarto delle clip su fondo verde.
(base v2:
1 minuto in inglese. Base = clip Pexels in movimento (>= 80%), numeri che corrono disegnati in codice, al massimo 2 immagini 3D (fal) come accento,
musica di tensione bassa sotto la voce. Tagli netti a ritmo (una scena ogni 3-5 s). Non carica niente.
Uscita: prove_video/Prova_Gloam2/ (video_prova.mp4, copertina.jpg, fotogrammi, copione.json, costo.txt)."""
import io, json, os, random, re, subprocess, time, urllib.parse, urllib.request
from PIL import Image, ImageDraw, ImageFont

E = os.environ.get
OUT = 'prove_video/Prova_Gloam3'; os.makedirs(OUT, exist_ok=True)
LAV = '/tmp/gloam3'; os.makedirs(LAV, exist_ok=True)
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
Write a 60-second test episode, 125-140 spoken words in total, split into 15-19 shots: 7-12 words per shot at the start, 4-7 words per shot during the crash (cuts get faster).
Shot 1 = brutal hook with the big number. Within the first 10 seconds open a loop ("but the worst part wasn't the money...") that is answered only in the last 10 seconds.
Build tension minute by minute. End with the answer to the open loop + "Subscribe for the next one."
Every shot also has "ora" (the clock time of the event at that moment, e.g. "9:30 AM"; it only moves forward) and "perdita" (cumulative loss in millions of dollars at the END of that shot, integer, 0 before the problem starts, matching documented facts).
Put "capitolo" (2-4 words, CAPITALS, e.g. "THE GLITCH") on 3-4 shots where a new phase starts.
Each shot has "voce" (numbers written as words) and ONE visual "tipo":
- "clip": real stock footage searchable on Pexels; give "cerca" = 2-4 plain English words of something FILMABLE (e.g. "stock market screen", "server room lights", "trader stressed office", "new york street night", "clock ticking", "money counting machine"). Never people's names or brands.
- "numero": a big animated number counting up over footage; give "da", "a" (integers), "prefisso" (e.g. "$"), "suffisso" (e.g. "M", " MIN", "%"), and "cerca" for the background footage.
- "borsa": a trading screen drawn in code where a price line collapses live; give "ticker" (stock symbol, e.g. "KCG") and "da", "a" (price before/after, numbers). Use it 1-2 times during the crash.
- "3d": glossy 3D illustration; give "immagine" (one clear symbolic subject, faceless figures). Use "3d" EXACTLY 2 times (not in shot 1), never two 3d in a row.
At least 70% of shots must be "clip", "numero" or "borsa". Optional "etichetta" (max 3 words, CAPITALS) on clip shots for dates/key facts, and "colore" (red|gold|blue).
Also "copertina": {{"immagine": "...", "scritta": "max 3 words, CAPITALS"}} and "titolo".
Reply ONLY with JSON: {{"titolo": "...", "copertina": {{...}}, "shots": [{{"voce": "...", "tipo": "clip", "cerca": "...", "etichetta": "", "colore": "red", "ora": "9:30 AM", "perdita": 0, "capitolo": ""}}]}}"""
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
            if fondo_verde(f):
                log(f'clip {v["id"]} scartata: fondo verde'); continue
            COSTO['clip_pexels'] += 1
            log(f'clip {i}: "{q}" -> {v["id"]} ({v.get("duration")} s)')
            return f, v.get('duration', 8)
    raise RuntimeError('nessuna clip per ' + cerca)


def fondo_verde(f):
    """True se la clip e' girata su fondo verde (chroma key): piu' del 20% di pixel verde acceso in uno dei fotogrammi controllati."""
    for ss in ('0.5', '2'):
        g = os.path.join(LAV, 'gv.png')
        if subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', ss, '-i', f, '-frames:v', '1', '-vf', 'scale=160:-1', g]).returncode or not os.path.exists(g):
            continue
        px = list(Image.open(g).convert('RGB').getdata())
        if sum(1 for r, gg, b in px if gg > 110 and gg > r + 45 and gg > b + 45) / max(1, len(px)) > .2:
            return True
    return False


def borsa(i, s, dur, out):
    """Schermo di borsa disegnato in codice: griglia, linea del prezzo che crolla in diretta con bagliore rosso, prezzo che scende, nastro rosso che scorre."""
    da, a = float(s.get('da') or 100), float(s.get('a') or 30); tick = str(s.get('ticker') or 'STOCK')[:6].upper()
    random.seed(i); n = 120
    pts = [da * (1 + .01 * random.uniform(-1, 1)) for _ in range(n // 3)]
    for k in range(n - n // 3):
        f = k / (n - n // 3 - 1); pts.append(da + (a - da) * (f ** 1.6) + da * .025 * random.uniform(-1, 1))
    lo, hi = min(pts) * .9, max(pts) * 1.05
    fa = ImageFont.truetype(FONT, 90); fb = ImageFont.truetype(FONT, 44); fc = ImageFont.truetype(FONT, 40)
    enc = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', '30', '-i', '-',
                            '-c:v', 'libx264', '-preset', 'medium', '-crf', '19', '-pix_fmt', 'yuv420p', out], stdin=subprocess.PIPE)
    nf = int(dur * 30) + 1
    nastro = '   '.join(f'{x} ▼{random.uniform(2, 31):.1f}%' for x in ['NYSE', tick, 'NASDAQ', 'S&P', tick, 'DOW', tick, 'NYSE'] * 3)
    for k in range(nf):
        t = k / 30; prog = min(1, (t + .2) / (dur * .8)); m = max(2, int(n * prog))
        im = Image.new('RGB', (W, H), (8, 12, 24)); d = ImageDraw.Draw(im)
        for x in range(120, W - 80, 120):
            d.line((x, 170, x, 900), fill=(22, 30, 50), width=2)
        for y in range(170, 901, 90):
            d.line((120, y, W - 80, y), fill=(22, 30, 50), width=2)
        X = lambda j: 120 + (W - 200) * j / (n - 1); Yp = lambda v: 900 - 730 * (v - lo) / (hi - lo)
        P = [(X(j), Yp(pts[j])) for j in range(m)]
        glow = Image.new('RGB', (W, H), (0, 0, 0)); ImageDraw.Draw(glow).line(P, fill=(232, 57, 70), width=22)
        from PIL import ImageFilter, ImageChops
        im = ImageChops.add(im, glow.filter(ImageFilter.GaussianBlur(14))); d = ImageDraw.Draw(im)
        d.line(P, fill=(255, 80, 90), width=7)
        cur = pts[m - 1]; ch = (cur - da) / da * 100
        d.text((120, 50), tick, font=fa, fill=(230, 235, 245))
        d.text((420, 50), f'${cur:,.2f}', font=fa, fill=(255, 80, 90))
        d.text((900, 80), f'{ch:+.1f}%', font=fb, fill=(255, 80, 90))
        d.rectangle((0, 960, W, 1040), fill=(150, 20, 30))
        off = int(t * 420) % 2400
        d.text((W - off, 975), nastro, font=fc, fill=(255, 255, 255))
        enc.stdin.write(im.tobytes())
    enc.stdin.close(); enc.wait()


def suoni():
    """Colpo (boom) e soffio (whoosh) generati in codice: gratis."""
    b, w = os.path.join(LAV, 'boom.wav'), os.path.join(LAV, 'whoosh.wav')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', "aevalsrc='0.9*sin(2*PI*(70-50*t)*t)*exp(-5*t)':s=44100:d=0.9", '-ac', '2', b], check=True)
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'anoisesrc=d=0.6:c=pink:a=0.5', '-af', 'bandpass=f=1200:w=900,afade=t=in:d=0.25,afade=t=out:st=0.3:d=0.3,volume=0.6', '-ar', '44100', '-ac', '2', w], check=True)
    return b, w


def hud(s, prec_perdita, dur):
    """Orologio del disastro + contatore delle perdite fissi in alto a destra (il contatore corre dal valore della scena prima)."""
    ora = esc(s.get('ora') or ''); p1 = int(s.get('perdita') or 0)
    if not ora:
        return ''
    tc = max(.5, dur * .8)
    cnt = f"%{{eif\\:{prec_perdita}+({p1}-{prec_perdita})*min(1\\,t/{tc:.2f})\\:d}}"
    return (f",drawbox=x=iw-560:y=40:w=520:h=170:color=black@0.62:t=fill"
            f",drawtext=fontfile={FONT}:text='{ora}':fontsize=64:fontcolor=white:x=w-530:y=58"
            f",drawtext=fontfile={FONT}:text='LOSS -${cnt}M':fontsize=64:fontcolor=0xFF4F5A:x=w-530:y=128")


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


def scena(i, s, dur, out, prec_perdita=0):
    """clip: spezzone Pexels (parte casuale) + etichetta; numero: clip scurita + numero grande che corre; 3d: immagine con leggera spinta."""
    tipo = s.get('tipo', 'clip')
    lab = os.path.join(LAV, f'lab_{i:02d}.png'); etichetta(str(s.get('etichetta') or '').upper()[:22] if tipo == 'clip' else '', s.get('colore'), lab)
    cap = str(s.get('capitolo') or '').upper()[:28]
    if cap:   # capitolo: banda gialla in alto a sinistra per i primi 1,8 s
        L = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(L); fn = ImageFont.truetype(FONT, 70)
        w = int(fn.getlength(cap)); d.rounded_rectangle((70, 60, 70 + w + 70, 60 + 120), 20, fill=(245, 184, 40, 255)); d.text((105, 78), cap, font=fn, fill=(20, 20, 30))
        L.save(lab.replace('.png', '_cap.png'))
    if tipo == 'borsa':
        raw = out.replace('.mp4', '_raw.mp4'); borsa(i, s, dur, raw)
        vf = f"[0:v]null{hud(s, prec_perdita, dur)},format=yuv420p[o]"
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', raw, '-filter_complex', vf, '-map', '[o]', '-an', '-c:v', 'libx264', '-preset', 'medium', '-crf', '19', out], check=True)
        return
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
        # colpo di zoom + lampo rosso all'entrata del numero
        vf += f";[b2]scale=w='iw*(1+0.10*exp(-7*t))':h=-2:eval=frame,crop={W}:{H},drawbox=x=0:y=0:w=iw:h=ih:color=red@0.35:t=fill:enable='lt(t,0.12)'[b3]"
        last = 'b3'
    else:
        last = 'b'
    capf = lab.replace('.png', '_cap.png')
    vf += f";[1:v]format=rgba[l];[{last}][l]overlay=0:0[k]"
    if cap:
        vf += f";[2:v]format=rgba[c];[k][c]overlay=0:0:enable='lt(t,1.8)'[k2]"; last2 = 'k2'
    else:
        last2 = 'k'
    vf += f";[{last2}]null{hud(s, prec_perdita, dur)},format=yuv420p[o]"
    extra = ['-loop', '1', '-t', f'{dur:.3f}', '-i', capf] if cap else []
    subprocess.run(['ffmpeg', '-v', 'error', '-y', *inp, '-loop', '1', '-t', f'{dur:.3f}', '-i', lab, *extra, '-filter_complex', vf, '-map', '[o]',
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
        if s.get('tipo') == 'borsa':
            continue
        s['_clip'] = pexels(s.get('cerca') or 'stock market screen', i)
    boom, whoosh = suoni(); prec = 0
    parti, audio = [], []
    for i, s in enumerate(shots):
        v = voce(i, s['voce']); d = durata(v) + 0.12
        out = os.path.join(LAV, f'scena_{i:02d}.mp4'); scena(i, s, d, out, prec); parti.append(out); prec = int(s.get('perdita') or prec)
        a = os.path.join(LAV, f'a_{i:02d}.wav')
        fx = boom if s.get('tipo') in ('numero', 'borsa') else (whoosh if s.get('capitolo') else None)
        if fx:
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', v, '-i', fx, '-filter_complex', f'[0:a]aresample=44100,aformat=channel_layouts=stereo,apad,atrim=0:{d:.3f}[v];[1:a]volume=0.55[f];[v][f]amix=inputs=2:duration=first:normalize=0',
                            '-ar', '44100', '-ac', '2', a], check=True)
        else:
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', v, '-af', f'apad,atrim=0:{d:.3f}', '-ar', '44100', '-ac', '2', a], check=True)
        audio.append(a)
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
    mov = sum(1 for s in shots if s.get('tipo') != '3d') / max(1, len(shots))   # borsa disegnata = in movimento
    costo = (f"durata {tot:.0f} s | scene {len(shots)} (movimento {mov:.0%}) | Claude {COSTO['claude']:.3f} $ | immagini 3D {COSTO['fal_immagini']} (circa {COSTO['fal_immagini'] * 0.08:.2f} $) | "
             f"clip Pexels {COSTO['clip_pexels']} (gratis) | voce {COSTO['voce_caratteri']} crediti")
    open(os.path.join(OUT, 'costo.txt'), 'w').write(costo + '\n'); log('FATTO:', costo)


if __name__ == '__main__':
    main()
