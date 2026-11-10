#!/usr/bin/env python3
"""10 nov (Giorgio): rifa' SOLO la copertina di un video Costo Vero gia' pubblicato, con lo stesso codice del motore (video_possesso.py):
sfondo nuovo FLUX.2 Klein (circa 0,009 $) + scontrino MANO LIBERA. Non carica nulla: la copertina va in prove_video/Costo_Vero/rifatte/<NOME>.jpg
e si carica dopo il controllo con carica_copertina.yml.
Ingresso (env PAYLOAD): {"nome", "titolo", "oggetto", "costo_vero" (numero), "k" (impaginazione, numero)}"""
import json, os, shutil, sys
Q = json.loads(os.environ.get('PAYLOAD') or '{}')
os.environ['PAYLOAD'] = json.dumps({'riga': {'titolo_italiano': Q.get('titolo', ''), 'oggetto': Q.get('oggetto', '')}, 'riga_produzione': Q.get('k', 0)})
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import video_possesso as V
V.DATI = {'costo_vero': float(Q['costo_vero'])}
out = V.copertina({'copertina': {'oggetto': Q.get('oggetto', '')}}, None)
d = os.path.join('prove_video', 'Costo_Vero', 'rifatte'); os.makedirs(d, exist_ok=True)
dest = os.path.join(d, Q.get('nome', 'copertina') + '.jpg'); shutil.copy(out, dest)
print('copertina pronta:', dest)
