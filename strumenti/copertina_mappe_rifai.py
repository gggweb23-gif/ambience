#!/usr/bin/env python3
"""Rifa' le copertine "cartellino" (B2) di video gia' caricati e le carica su YouTube.
PAYLOAD = {"channel_name": "Rich Borders", "copertine": [{"video_id": "...", "luoghi": [{"nome","iso","prezzo","ricco"}], "scritta": "SAME CONTINENT? 3X"}]}
Salva ogni copertina in prove_video/<canale>/copertina_<video_id>.jpg per controllarla."""
import json, os, re, sys
sys.path.insert(0, os.getcwd())
import video_mappe as VM
import copertina_cartellino as CC
CC.VM = VM
P = VM.P
canale = re.sub(r'\W+', '_', str(P.get('channel_name') or 'rich_borders')).strip('_').lower()
cart = os.path.join('prove_video', canale); os.makedirs(cart, exist_ok=True)
for c in P.get('copertine') or []:
    path = os.path.join(cart, f"copertina_{c['video_id']}.jpg")
    CC.copertina_b2(c['luoghi'], c['scritta'], path)
    esito = VM.carica_copertina(c['video_id'], path) if str(P.get('carica') or 'SI').upper() == 'SI' else 'non caricata (carica=NO)'
    VM.log('copertina', c['video_id'], c['scritta'], '->', esito or 'CARICATA su YouTube')
