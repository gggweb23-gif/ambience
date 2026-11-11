#!/usr/bin/env python3
"""11 nov (Giorgio): rifa' la copertina di un video Costo Vero gia' uscito nello stile SHOCK (protagonista sconvolto + prezzo barrato -> costo vero).
Riferimento del protagonista rigenerato dal copione (Klein, circa 0,02 $) + copertina (Klein edit Full HD, circa 0,04 $). Non carica:
salva in prove_video/Costo_Vero/rifatte/<NOME>.jpg. Ingresso (env): COPIONE (percorso), NOME, PREZZO, COSTO_VERO, ANNI, K (impaginazione)."""
import json, os, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ['PAYLOAD'] = json.dumps({'riga': {'titolo_italiano': 'copertina'}})
import video_possesso as V
import copertine_possesso as CP
E = os.environ.get
c = json.load(open(E('COPIONE')))
V.DATI = {'prezzo': float(E('PREZZO')), 'costo_vero': float(E('COSTO_VERO')), 'anni': int(E('ANNI'))}
os.makedirs(V.LAV, exist_ok=True)
rif = V.immagine(os.path.join(V.LAV, 'riferimento.jpg'), CP.STILE + f"Main character: {c.get('protagonista')}. Scene: {c.get('riferimento')}")
url = rif[1] if isinstance(rif, tuple) else None
ogg = str((c.get('copertina') or {}).get('oggetto') or '').split(',')[0]
out = V.copertina_shock(CP, ogg, url, int(E('K', '0')))
d = os.path.join('prove_video', 'Costo_Vero', 'rifatte'); os.makedirs(d, exist_ok=True)
shutil.copy(out, os.path.join(d, E('NOME', 'copertina') + '.jpg')); print('pronta')
