#!/usr/bin/env python3
"""8 nov (Giorgio): rifa' la copertina "cartellino" di un video Rich Borders gia' fatto, con un'impaginazione diversa (paesi scambiati,
parola grande in giallo), senza nuove spese AI: usa il piano gia' deciso (luoghi, prezzi, scritta).
PAYLOAD = {"script": "rifai_cartellino.py", "nome": "...", "video": "ID", "luoghi": [...], "scritta": "...", "scambia": true, "giallo": true}
Uscita: prove_angoli/<nome>/<video>.jpg (poi si carica con ripara_video.yml)"""
import json, os, sys
sys.argv = sys.argv[:1]
P0 = json.loads(os.environ.get('PAYLOAD') or '{}')
os.environ['PAYLOAD'] = json.dumps({'copertina_presentatore': ''})
sys.path.insert(0, os.getcwd())
import video_mappe as VM
import copertina_cartellino as CC
CC.VM = VM
CC.VARIANTE['scambia'] = bool(P0.get('scambia', True))
if P0.get('giallo', True):
    CC.VARIANTE['colore_parola'] = (255, 214, 0)
cart = os.path.join('prove_angoli', P0.get('nome') or 'rifai'); os.makedirs(cart, exist_ok=True)
out = os.path.join(cart, P0['video'] + '.jpg')
CC.copertina_b2(P0['luoghi'], P0.get('scritta') or 'WHY?', out)
print('copertina pronta:', out, '| variante', CC.VARIANTE)
