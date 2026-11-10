#!/usr/bin/env python3
"""10 nov (Giorgio): rifa' SOLO la copertina di un video Quanto Ti Resta gia' fatto, con lo stesso codice del motore (video_cartoni.copertina_ai):
stile COSTA / LO VENDI rifinito con l'AI (0,08 $ a tentativo, massimo 4). Non carica: la copertina va in prove_video/Quanto_Ti_Resta/rifatte/<NOME>.jpg
e si carica dopo il controllo con carica_copertina.yml. Ingresso (env): COPIONE = percorso del copione.json, NOME"""
import json, os, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('PAYLOAD', json.dumps({'copertina_ai': 'SI'}))
import video_cartoni as V
from playwright.sync_api import sync_playwright
c = json.load(open(os.environ['COPIONE']))
ctx = {'protagonista': c.get('protagonista') or {}, 'oggetto': c.get('oggetto') or ''}
cop = os.path.join(V.LAV, 'copertina.jpg')
with sync_playwright() as p:
    br = p.chromium.launch(); pg = br.new_page(viewport={'width': 1280, 'height': 720})
    pg.goto('file://' + os.path.join(V.MOT, 'video.html')); pg.wait_for_timeout(500)
    V.copertina_ai(pg, c['copertina_ai'], ctx, cop)
    br.close()
d = os.path.join('prove_video', 'Quanto_Ti_Resta', 'rifatte'); os.makedirs(d, exist_ok=True)
shutil.copy(cop, os.path.join(d, os.environ.get('NOME', 'copertina') + '.jpg'))
for f in os.listdir(V.LAV):
    if f.startswith('copertina_ai'):
        shutil.copy(os.path.join(V.LAV, f), os.path.join(d, os.environ.get('NOME', 'copertina') + '_' + f))
print('copertina pronta')
