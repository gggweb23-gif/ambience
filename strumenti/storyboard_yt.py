#!/usr/bin/env python3
"""FOTOGRAMMI COMPETITOR (gratis, 21 nov 2026, Giorgio: "guarda bene se dentro c'e' AI o animazioni, altrimenti copiandoli con Pexels siamo lontani").
Per ogni video: scarica a 360p tre pezzi (inizio, meta', fine) con yt-dlp e ne prende 16 fotogrammi -> un foglio unico.
Env: VIDEO = id separati da virgola, NOME. Uscita: prove_video/storyboard/<NOME>/<id>.jpg (+ durata dei tagli: quante inquadrature al minuto)"""
import json, os, subprocess
from PIL import Image, ImageDraw

OUT = os.path.join('prove_video', 'storyboard', os.environ.get('NOME') or 'sb'); os.makedirs(OUT, exist_ok=True)
LAV = '/tmp/sb'; os.makedirs(LAV, exist_ok=True)
for vid in [v.strip() for v in os.environ.get('VIDEO', '').split(',') if v.strip()]:
    try:
        info = json.loads(subprocess.run(['yt-dlp', '-J', '--no-warnings', '--extractor-args', 'youtube:player_client=tv,ios,mweb,web_safari',
                                          'https://www.youtube.com/watch?v=' + vid], capture_output=True, text=True, timeout=120).stdout or '{}')
        dur = float(info.get('duration') or 600)
    except Exception:
        dur = 600
    fr = []
    for k, ini in enumerate([20, dur * .45, dur * .8]):
        base = os.path.join(LAV, f'{vid}_{k}')
        subprocess.run(['yt-dlp', '-q', '--no-warnings', '--extractor-args', 'youtube:player_client=tv,ios,mweb,web_safari',
                        '-f', 'bv*[height<=360][ext=mp4]/b[height<=360]/b', '--download-sections', f'*{int(ini)}-{int(ini) + 40}',
                        '-o', base + '.%(ext)s', 'https://www.youtube.com/watch?v=' + vid], timeout=300)
        src = next((os.path.join(LAV, x) for x in os.listdir(LAV) if x.startswith(f'{vid}_{k}.')), None)
        if not src:
            continue
        for j in range(6):
            o = f'{base}_{j}.jpg'
            subprocess.run(['ffmpeg', '-y', '-v', 'error', '-ss', str(2 + j * 6), '-i', src, '-frames:v', '1', '-vf', 'scale=480:270', o])
            if os.path.exists(o):
                fr.append(Image.open(o).convert('RGB'))
    if not fr:
        print(vid, 'non scaricato'); continue
    g = Image.new('RGB', (480 * 6, 270 * (-(-len(fr) // 6))))
    for i, im in enumerate(fr):
        g.paste(im, ((i % 6) * 480, (i // 6) * 270))
    ImageDraw.Draw(g).text((10, 10), f"{vid} {info.get('title', '')[:80]}", fill=(255, 255, 0))
    g.save(os.path.join(OUT, vid + '.jpg'), quality=80); print(vid, 'ok', len(fr), 'fotogrammi', info.get('title', '')[:60])
