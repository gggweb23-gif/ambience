#!/usr/bin/env python3
"""Dopo ogni video (workflow GitHub): aggiunge il costo del video allo storico del canale coach/costi/<slug>.tsv
(data, costo $, crediti voce, prova SI/NO, dettaglio). Lo legge il coach automatico. Uso:
python3 coach/registra_costo.py <costi_video.jsonl>   (canale e prova presi da PAYLOAD)"""
import datetime as dt, json, os, sys
sys.path.insert(0, os.getcwd()); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import costi as CO
from ricetta import slug

f = sys.argv[1] if len(sys.argv) > 1 else ''
if not f or not os.path.exists(f):
    raise SystemExit(0)
P = json.loads(os.environ.get('PAYLOAD') or '{}')
can = P.get('channel_id') or P.get('canale') or ''
if not can:
    raise SystemExit(0)
rp = CO.riepilogo(f)
os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'costi'), exist_ok=True)
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'costi', slug(can) + '.tsv')
nuovo = not os.path.exists(out)
with open(out, 'a') as o:
    if nuovo:
        o.write('data\tcosto_dollari\tcrediti_voce\tprova\tlink\tdettaglio\n')
    o.write('\t'.join([dt.datetime.now().strftime('%Y-%m-%d %H:%M'), f"{rp['totale_dollari']:.3f}", str(rp['crediti_voce']),
                       str(P.get('prova') or os.environ.get('PROVA') or 'NO'), str(P.get('link') or ''),
                       json.dumps(rp['dettaglio'], ensure_ascii=False)]) + '\n')
print(CO.testo(rp))
