#!/usr/bin/env python3
"""TRASCRIZIONE DI UN VIDEO COMPETITOR (RapidAPI youtube-transcript3) -> competitor_trascrizioni/<id>.txt
Regola (22 nov 2026, Giorgio): nessun copione dei canali da copiare parte senza la trascrizione del video competitor."""
import json, os, re, sys, time, urllib.request
os.makedirs('competitor_trascrizioni', exist_ok=True)
ok = 0
for vid in [v.strip() for v in os.environ.get('VIDEO', '').split(',') if v.strip()]:
    for k in range(3):
        try:
            r = urllib.request.Request('https://youtube-transcript3.p.rapidapi.com/api/transcript?videoId=' + vid,
                                       headers={'X-RapidAPI-Key': os.environ.get('RAPIDAPI_KEY', ''), 'X-RapidAPI-Host': 'youtube-transcript3.p.rapidapi.com'})
            j = json.loads(urllib.request.urlopen(r, timeout=120).read())
            righe = j.get('transcript') or []
            t = ' '.join(str(x.get('text', '')) for x in righe) if isinstance(righe, list) else str(righe)
            t = re.sub(r'\s+', ' ', re.sub(r'\[(?:Music|Applause)\]', ' ', t)).strip()
            if len(t.split()) > 100:
                open(f'competitor_trascrizioni/{vid}.txt', 'w').write(t); print(vid, 'ok', len(t.split()), 'parole'); ok += 1; break
            print(vid, 'vuota', json.dumps(j)[:200])
        except Exception as e:
            print(vid, 'errore', str(e)[:200]); time.sleep(5)
sys.exit(0 if ok else 1)
