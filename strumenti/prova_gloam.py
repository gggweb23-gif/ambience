#!/usr/bin/env python3
"""PROVA STILE GLOAM (9 nov, richiesta di Giorgio): 1 minuto in inglese, scene 3D lucide (fal nano-banana-2),
voce ElevenLabs, movimento lento su ogni immagine + etichette/numeri disegnati in codice.
Uscita: prove_video/Prova_Gloam/ (video_prova.mp4, copertina.jpg, fotogrammi, copione.json, costo.txt). Non carica niente."""
import base64, io, json, os, re, subprocess, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageDraw, ImageFont

E = os.environ.get
OUT = 'prove_video/Prova_Gloam'; os.makedirs(OUT, exist_ok=True)
LAV = '/tmp/gloam'; os.makedirs(LAV, exist_ok=True)
VOCE = E('VOCE') or 'pNInz6obpgDQGcFmaJgB'
TEMA = E('TEMA') or 'How Knight Capital Lost $440,000,000 in 45 Minutes (August 1, 2012)'
FONT = 'Anton-Regular.ttf'
W, H = 1920, 1080
COSTO = {'claude': 0.0, 'fal_immagini': 0, 'voce_caratteri': 0}
log = lambda *a: print(time.strftime('%H:%M:%S'), *a, flush=True)
STILE = ('Glossy stylized 3D render like a premium finance documentary on YouTube: smooth faceless mannequin-like human figures with no facial features, '
         'solid colours (the villain or the problem in red, ordinary people and employees in blue, money and gold objects in shiny gold), '
         'deep dark navy background with soft cinematic rim light and subtle glow, clean studio lighting, shallow depth of field, simple strong composition '
         'with ONE clear subject. Absolutely no text, no letters, no numbers, no logos, no watermark. ')


def http(url, data=None, headers=None, raw=False, timeout=300):
    body = json.dumps(data).encode() if isinstance(data, (dict, list)) else data
    h = {'Content-Type': 'application/json'} if isinstance(data, (dict, list)) else {}
    h.update(headers or {})
    with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=h), timeout=timeout) as r:
        b = r.read()
    return b if raw else json.loads(b.decode() or '{}')


def copione():
    prompt = f"""You write for a new English YouTube channel in the style of "Gloam" (finance disasters told minute by minute, glossy 3D visuals).
Topic: {TEMA}. Only well documented facts; round numbers; no invented quotes.
Write a 55-65 second test episode: 9 shots. Shot 1 is a brutal hook with the big number. Build tension minute by minute, end on a sharp twist + "Subscribe to see how the next one happened."
Each shot: "voce" (16-24 spoken words, numbers written as words, e.g. "four hundred forty million dollars"),
"immagine" (what to render, in English, ONE clear subject, faceless 3D figures and symbolic objects: servers, trading screens without readable text, golden coins, a glowing red button, a clock, an empty office),
"etichetta" (on-screen label, max 3 words, CAPITALS, e.g. "$440,000,000", "45 MINUTES", "9:30 AM"), "colore" (red|gold|blue).
Also "copertina": {{"immagine": "...", "scritta": "max 3 words, CAPITALS"}} and "titolo".
Reply ONLY with JSON: {{"titolo": "...", "copertina": {{...}}, "shots": [{{"voce": "...", "immagine": "...", "etichetta": "...", "colore": "red"}}]}}"""
    j = http('https://api.anthropic.com/v1/messages', {'model': 'claude-sonnet-5-5', 'max_tokens': 4000, 'messages': [{'role': 'user', 'content': prompt}]},
             {'x-api-key': E('ANTHROPIC_API_KEY', ''), 'anthropic-version': '2023-06-01'})
    u = j.get('usage') or {}
    COSTO['claude'] += u.get('input_tokens', 0) * 3e-6 + u.get('output_tokens', 0) * 15e-6
    t = ''.join(b.get('text', '') for b in j['content'] if b.get('type') == 'text')
    m = re.search(r'\{.*\}', t, re.S).group(0)
    try:
        c = json.loads(m)
    except Exception:
        from json_repair import repair_json
        c = json.loads(repair_json(m))
    json.dump(c, open(os.path.join(OUT, 'copione.json'), 'w'), ensure_ascii=False, indent=1)
    log('copione:', c['titolo'], len(c['shots']), 'scene')
    return c


def immagine(i, desc):
    f = os.path.join(LAV, f'img_{i:02d}.jpg')
    hd = {'Authorization': 'Key ' + E('FAL_KEY', '')}
    for k in range(3):
        try:
            inv = http('https://queue.fal.run/fal-ai/nano-banana-2', {'prompt': STILE + desc, 'aspect_ratio': '16:9', 'output_format': 'jpeg', 'num_images': 1}, hd)
            for _ in range(150):
                time.sleep(3)
                if http(inv['status_url'], headers=hd).get('status') == 'COMPLETED':
                    break
            url = http(inv['response_url'], headers=hd)['images'][0]['url']
            Image.open(io.BytesIO(http(url, raw=True))).convert('RGB').resize((W, H), Image.LANCZOS).save(f, quality=94)
            COSTO['fal_immagini'] += 1
            return f
        except Exception as e:
            log('immagine non riuscita, riprovo:', str(e)[:150]); time.sleep(5)
    raise RuntimeError('immagine non riuscita')


def voce(i, testo):
    f = os.path.join(LAV, f'voce_{i:02d}.mp3')
    j = http(f'https://api.elevenlabs.io/v1/text-to-speech/{VOCE}?output_format=mp3_44100_128',
             {'text': testo, 'model_id': 'eleven_multilingual_v2', 'voice_settings': {'stability': .45, 'similarity_boost': .8}},
             {'xi-api-key': E('ELEVENLABS_API_KEY', '')}, raw=True)
    open(f, 'wb').write(j); COSTO['voce_caratteri'] += len(testo)
    return f


def durata(f):
    return float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f]).decode().strip())


COL = {'red': (232, 57, 70), 'gold': (245, 184, 40), 'blue': (52, 120, 246)}


def etichetta(testo, colore, f):
    """Etichetta tipo Gloam: rettangolo pieno arrotondato con scritta bianca grande, in basso a sinistra (mai al centro sul soggetto)."""
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    fs = 120
    fn = ImageFont.truetype(FONT, fs)
    while fn.getlength(testo) > W * .5 and fs > 60:
        fs -= 6; fn = ImageFont.truetype(FONT, fs)
    b = fn.getbbox(testo); w, h = b[2] - b[0], b[3] - b[1]
    x, y = 90, H - 110 - h - 50
    d.rounded_rectangle((x + 8, y + 10, x + w + 68, y + h + 60), 22, fill=(0, 0, 0, 120))
    d.rounded_rectangle((x, y, x + w + 60, y + h + 50), 22, fill=COL.get(colore, COL['red']) + (255,))
    d.text((x + 30 - b[0], y + 25 - b[1]), testo, font=fn, fill='white')
    im.save(f)


def clip(i, img, lab, dur, out):
    """Movimento lento continuo (spinta in avanti 1.00 -> 1.10, leggera deriva), etichetta che entra a 0,4 s."""
    fr = int(dur * 30) + 1
    dx = ['iw/2-(iw/zoom/2)', 'iw/2-(iw/zoom/2)+on*0.4', 'iw/2-(iw/zoom/2)-on*0.4'][i % 3]
    vf = (f"[0:v]scale=3840:-1,zoompan=z='1+0.10*on/{fr}':x='{dx}':y='ih/2-(ih/zoom/2)':d={fr}:s={W}x{H}:fps=30[v];"
          f"[1:v]format=rgba,fade=t=in:st=0.4:d=0.25:alpha=1[l];[v][l]overlay=0:0:enable='gte(t,0.4)',format=yuv420p[o]")
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-loop', '1', '-t', f'{dur:.3f}', '-i', img, '-loop', '1', '-t', f'{dur:.3f}', '-i', lab,
                    '-filter_complex', vf, '-map', '[o]', '-t', f'{dur:.3f}', '-r', '30', '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', out], check=True)


def main():
    c = copione()
    shots = c['shots']
    with ThreadPoolExecutor(5) as ex:
        imgs = list(ex.map(lambda a: immagine(*a), [(i, s['immagine']) for i, s in enumerate(shots)] + [(99, c['copertina']['immagine'])]))
    voci = [voce(i, s['voce']) for i, s in enumerate(shots)]
    parti, audio = [], []
    for i, s in enumerate(shots):
        d = durata(voci[i]) + 0.25
        lab = os.path.join(LAV, f'lab_{i:02d}.png'); etichetta(str(s.get('etichetta') or '').upper()[:22], s.get('colore'), lab)
        out = os.path.join(LAV, f'clip_{i:02d}.mp4'); clip(i, imgs[i], lab, d, out); parti.append(out)
        a = os.path.join(LAV, f'a_{i:02d}.wav')
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', voci[i], '-af', f'apad,atrim=0:{d:.3f}', '-ar', '44100', '-ac', '2', a], check=True); audio.append(a)
    open(os.path.join(LAV, 'v.txt'), 'w').write(''.join(f"file '{p}'\n" for p in parti))
    open(os.path.join(LAV, 'a.txt'), 'w').write(''.join(f"file '{p}'\n" for p in audio))
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', os.path.join(LAV, 'v.txt'), '-f', 'concat', '-safe', '0', '-i', os.path.join(LAV, 'a.txt'),
                    '-c:v', 'copy', '-c:a', 'aac', '-b:a', '160k', '-shortest', os.path.join(OUT, 'video_prova.mp4')], check=True)
    # copertina: immagine 3D + scritta grande in basso a sinistra (stile del canale, testo solo del video)
    cop = Image.open(imgs[-1]).resize((1280, 720)); lab = os.path.join(LAV, 'lab_cop.png')
    etichetta(str(c['copertina'].get('scritta') or '').upper()[:22], 'red', lab)
    cop.paste(Image.open(lab).resize((1280, 720)), (0, 0), Image.open(lab).resize((1280, 720)))
    cop.save(os.path.join(OUT, 'copertina.jpg'), quality=92)
    tot = durata(os.path.join(OUT, 'video_prova.mp4'))
    for k in range(1, 9):
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{tot * (k - .5) / 8:.2f}', '-i', os.path.join(OUT, 'video_prova.mp4'), '-frames:v', '1', '-vf', 'scale=960:-1',
                        os.path.join(OUT, f'fotogramma_{k}.jpg')], check=True)
    costo = f"durata {tot:.0f} s | Claude {COSTO['claude']:.3f} $ | immagini fal {COSTO['fal_immagini']} (circa {COSTO['fal_immagini'] * 0.08:.2f} $) | voce {COSTO['voce_caratteri']} crediti"
    open(os.path.join(OUT, 'costo.txt'), 'w').write(costo + '\n'); log('FATTO:', costo)


if __name__ == '__main__':
    main()
