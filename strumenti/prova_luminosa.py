#!/usr/bin/env python3
"""Prova della copertina "mappa luminosa" (Rich Borders, 9 nov) su alcuni titoli, senza caricare nulla. PAYLOAD: {"script": "prova_luminosa.py", "titoli": [...], "giorni": [...]}"""
import json, os, sys
P0 = json.loads(os.environ.get('PAYLOAD') or '{}')
os.environ['PAYLOAD'] = json.dumps({'copertina_presentatore': ''})
sys.argv = sys.argv[:1]; sys.path.insert(0, os.getcwd())
import video_mappe as VM
import copertina_cartellino as CC
CC.VM = VM
os.makedirs('prove_angoli/luminosa', exist_ok=True)
for i, t in enumerate(P0['titoli']):
    pl = CC.piano_luminosa({}, t); print('piano:', json.dumps(pl, ensure_ascii=False), flush=True)
    CC.copertina_luminosa(pl, f'prove_angoli/luminosa/{i + 1}.jpg', giorno=(P0.get('giorni') or [0, 1, 2, 3])[i])
