#!/usr/bin/env python3
"""PROVINI DI UN FILM D'ARCHIVIO (gratis, 26 nov 2026): scarica un film di pubblico dominio (archive.org, poi Wikimedia Commons)
e salva fogli di fotogrammi con il minutaggio, per scegliere a mano gli spezzoni di una prova (es. The War They Filmed).
Env: CERCA = titolo del film, NOME = cartella, PASSO = secondi tra un fotogramma e l'altro (default 4).
Uscita: libreria_clip/<NOME>/provini_XX.jpg + film.json (url del file scaricato, durata)."""
import json, os, re, subprocess, urllib.parse, urllib.request
from PIL import Image, ImageDraw

CERCA, NOME = os.environ['CERCA'], os.environ.get('NOME') or 'film'
PASSO = float(os.environ.get('PASSO') or 4)
OUT = os.path.join('libreria_clip', NOME); os.makedirs(OUT, exist_ok=True)
UA = {'User-Agent': 'ambience-provini/1.0 (+https://github.com/gggweb23-gif/ambience)'}
get = lambda u: urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=120).read()


def da_archive():
    j = json.loads(get('https://archive.org/advancedsearch.php?' + urllib.parse.urlencode(
        {'q': f'title:("{CERCA}") AND mediatype:movies', 'fl[]': ['identifier', 'title'], 'rows': 10, 'output': 'json'}, doseq=True)))
    for d in j['response']['docs']:
        m = json.loads(get('https://archive.org/metadata/' + d['identifier']))
        fs = [f for f in m.get('files', []) if re.search(r'\.(mp4|mpeg4|ogv|mpg)$', f['name'], re.I)]
        fs.sort(key=lambda f: (not f['name'].lower().endswith('.mp4'), -int(f.get('size') or 0)))
        if fs:
            print('archive.org:', d['identifier'], d.get('title'), fs[0]['name'])
            return 'https://archive.org/download/' + d['identifier'] + '/' + urllib.parse.quote(fs[0]['name'])


def da_commons():
    j = json.loads(get('https://commons.wikimedia.org/w/api.php?' + urllib.parse.urlencode({
        'action': 'query', 'format': 'json', 'generator': 'search', 'gsrnamespace': 6, 'gsrsearch': CERCA + ' filetype:video', 'gsrlimit': 10,
        'prop': 'imageinfo', 'iiprop': 'url|size'})))
    for pg in (j.get('query') or {}).get('pages', {}).values():
        print('commons:', pg['title']); return pg['imageinfo'][0]['url']


url = None
for f in (da_archive, da_commons):
    try:
        url = url or f()
    except Exception as e:
        print(f.__name__, 'errore', str(e)[:120])
if not url:
    raise SystemExit('film non trovato')
subprocess.run(['curl', '-sL', '-A', UA['User-Agent'], '-o', '/tmp/film', url], check=True)
dur = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', '/tmp/film'],
                           capture_output=True, text=True).stdout.strip() or 0)
print('durata', dur, 'url', url)
os.makedirs('/tmp/pv', exist_ok=True)
subprocess.run(['ffmpeg', '-v', 'error', '-i', '/tmp/film', '-vf', f'fps=1/{PASSO},scale=320:-2', '/tmp/pv/f_%04d.jpg'], check=True)
fr = sorted(os.listdir('/tmp/pv'))
for k in range(0, len(fr), 40):   # fogli da 40 fotogrammi (8 x 5)
    ims = [Image.open('/tmp/pv/' + x) for x in fr[k:k + 40]]
    w, h = ims[0].size
    g = Image.new('RGB', (w * 8, h * 5))
    for i, im in enumerate(ims):
        g.paste(im, ((i % 8) * w, (i // 8) * h))
        t = (k + i) * PASSO
        ImageDraw.Draw(g).text(((i % 8) * w + 4, (i // 8) * h + 4), f'{int(t // 60)}:{int(t % 60):02d}', fill=(255, 255, 0))
    g.save(os.path.join(OUT, f'provini_{k // 40:02d}.jpg'), quality=80)
json.dump({'url': url, 'durata': dur, 'passo': PASSO, 'cerca': CERCA}, open(os.path.join(OUT, 'film.json'), 'w'), indent=1)
print('fogli', -(-len(fr) // 40))
