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

# 11 nov: elenco completo dei canali con il primo video negli ultimi 30 giorni (per scegliere da quale partire)
for n, (h, rr) in tab.items():
    if 'Canali' in n and 'channel_id' in h:
        def _g(r):
            try:
                return float(str(r.get('Giorni dal primo video') or 999).replace(',', '.'))
            except Exception:
                return 999
        giovani = sorted([r for r in rr if _g(r) <= 30], key=lambda r: -float(str(r.get('Views al giorno (ultima settimana)') or 0).replace(',', '.') or 0))
        print(f'\n=== CANALI CON PRIMO VIDEO NEGLI ULTIMI 30 GIORNI: {len(giovani)}')
        for r in giovani:
            print(' | '.join(str(r.get(k, '')) for k in ('Canale', 'Crescita', 'Nicchia', 'Si può rifare?', 'Con cosa', 'RPM stimato $', 'Giorni dal primo video',
                  'Views al giorno (ultima settimana)', 'Views al giorno (settimana prima)', 'Iscritti', 'Video nel canale', 'Video migliore', 'Views video migliore', 'Motivo', 'Link canale'))[:600])

# 11 nov: video dei canali scelti per i nuovi filoni (link da copiare)
_scelti = [x.strip().lower() for x in os.environ.get('CANALI_VIDEO', 'IntoTheGreen,Untamed Atlas,Mutnan Explains,Rules of the Land,Genius Chronicle,Two Sides').split(',')]
for n, (h, rr) in tab.items():
    if 'Video trovati' in n:
        vis = set()
        print('\n=== VIDEO DEI CANALI SCELTI')
        for r in sorted(rr, key=lambda r: -float(str(r.get('views') or 0).replace(',', '.') or 0)):
            if str(r.get('canale') or '').strip().lower() in _scelti and r.get('video_id') not in vis:
                vis.add(r.get('video_id'))
                print(r.get('canale'), '|', r.get('views'), '|', r.get('durata_min'), 'min |', r.get('titolo'), '|', r.get('link'))
