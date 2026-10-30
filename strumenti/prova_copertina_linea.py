#!/usr/bin/env python3
"""Prova: la copertina A3a con la linea del tempo del video, in 3 posizioni (pannello, foto in alto, base). Non carica niente.
PAYLOAD = {"cartella": "...", "video": [{"titolo": "...", "tappe": [-3100, -1279, -30, 642, 1952, 2026]}]}"""
import json, os, sys
sys.path.insert(0, os.getcwd())
import copertina_foto as CF
from PIL import Image
P = json.loads(os.environ.get('PAYLOAD') or '{}')
CART = P.get('cartella') or 'prove_video/copertine_linea'; os.makedirs(CART, exist_ok=True)
righe = []
for k, v in enumerate(P.get('video') or []):
    p = CF.piano(v['titolo'], 'it'); foto, box = CF.foto_simbolo(p['nome'], p.get('simboli') or [])
    if foto is None:
        print('nessuna foto per', v['titolo']); continue
    imgs = []
    for lin in ('pannello', 'foto', 'base'):
        out = os.path.join(CART, f'{k}_{lin}.jpg')
        CF.disegna(str(p['nome']).upper(), str(p.get('anni') or ''), foto, box, out, tappe=v['tappe'], linea=lin); imgs.append(Image.open(out))
    riga = Image.new('RGB', (1280 * 3 + 40, 720), 'white')
    for i, im in enumerate(imgs):
        riga.paste(im, (i * 1300, 0))
    righe.append(riga)
if righe:
    t = Image.new('RGB', (righe[0].width, len(righe) * 740), 'white')
    for i, r in enumerate(righe):
        t.paste(r, (0, i * 740))
    t.resize((t.width // 2, t.height // 2)).save(os.path.join(CART, 'confronto.jpg'), quality=88)
open(os.path.join(CART, 'controlli.txt'), 'w').write('\n'.join(CF.REGISTRO) + '\n')
