#!/usr/bin/env python3
"""Sola lettura: stampa lo stato del foglio RADAR (ordine schede, righe, intestazioni, Scelte/Note, ultime righe) per controllare un giro del RADAR."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import radar as R

props, tab = R.leggi_tutto()
print('Ordine schede:', ' | '.join(f"{n}{' (nascosta)' if p.get('hidden') else ''}" for n, p in props.items()))
for n, (h, rr) in tab.items():
    print(f'\n=== {n}: {len(rr)} righe | colonne: {", ".join(h)}')
    if 'Canali' in n and 'channel_id' in h:
        sc = [r for r in rr if str(r.get('⭐ Scelta') or '').strip() or str(r.get('Note') or '').strip()]
        print('Canali con Scelta/Note:', [(r.get('Canale'), r.get('⭐ Scelta'), r.get('Note')) for r in sc])
        print('Aggiornato il:', sorted({str(r.get('Aggiornato il')) for r in rr}))
        for r in rr[:5]:
            print('  ', json.dumps(r, ensure_ascii=False)[:500])
    elif n.endswith('Impostazioni'):
        for r in rr:
            if r.get('parametro') in ('budget_giorno', 'semi_parole', 'trend_pexels'):
                print('  ', json.dumps(r, ensure_ascii=False)[:300])
    elif 'Video trovati' in n or 'Storico' in n:
        print('per data (ultime):', sorted(__import__('collections').Counter(str(R.data(r.get('data_rilevazione') or r.get('data'))) for r in rr).items())[-4:])
        for r in rr[-3:]:
            print('  ', json.dumps(r, ensure_ascii=False)[:500])
    elif 'TREND' in n:
        for r in rr[:4]:
            print('  ', json.dumps(r, ensure_ascii=False)[:400])
