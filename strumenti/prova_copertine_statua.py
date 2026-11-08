#!/usr/bin/env python3
"""PROVE COPERTINA STATUA (8 nov 2026): piu' varianti della copertina dei canali con copertina_stile = statua, SENZA video e senza YouTube.
PAYLOAD = {"cartella": "prove_video/Agora_of_Sages/copertine_prova", "prove": [{"nome": "A_miss_you", "titolo": "...", "config": {...}}]}
Ogni prova: copertina_statua.py (~0,09 $: statua fal + scontorno). Uscita: <cartella>/<nome>.jpg + confronto.jpg."""
import json, os, shutil, subprocess
from PIL import Image, ImageDraw

P = json.loads(os.environ['PAYLOAD'])
CART = P['cartella']; os.makedirs(CART, exist_ok=True)
fatte = []
for pr in P['prove']:
    lav = 'lavoro_statua_' + pr['nome']
    subprocess.run(['python3', 'copertina_statua.py'], env={**os.environ, 'COSTI_FILE': os.path.join(os.getcwd(), 'costi_prove.jsonl'),
                   'PAYLOAD': json.dumps({'titolo': pr['titolo'], 'testo_copertina': pr.get('testo_copertina', ''), 'cartella': lav, 'config': pr['config']})})
    try:
        ris = json.load(open(os.path.join(lav, 'risultato.json')))
    except Exception:
        ris = {'ok': False}
    print(pr['nome'], json.dumps(ris)[:300], flush=True)
    if ris.get('ok'):
        dst = os.path.join(CART, pr['nome'] + '.jpg'); shutil.copy(ris['copertina'], dst); fatte.append((pr['nome'], dst))
if fatte:
    tw, th, col = 640, 360, 3
    S = Image.new('RGB', (tw * col, (th + 30) * ((len(fatte) + col - 1) // col)), 'white'); d = ImageDraw.Draw(S)
    for i, (n, f) in enumerate(fatte):
        x, y = (i % col) * tw, (i // col) * (th + 30)
        S.paste(Image.open(f).convert('RGB').resize((tw, th)), (x, y + 30)); d.text((x + 8, y + 8), n, fill='black')
    S.save(os.path.join(CART, 'confronto.jpg'), quality=88)
