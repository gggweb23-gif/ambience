#!/usr/bin/env python3
"""VERIFICA (sola lettura, gratis): per ogni canale di Channel Configs dice con che motore produce, se il file di produzione
e' leggibile/scrivibile dall'account del coach, quante righe ha per stato e com'e' fatta l'ultima riga completata."""
import collections, json, os, sys, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import avvio_canali as A

_, _, canali = A.righe(A.CONFIGS)
for cfg in canali:
    cid = str(cfg.get('channel_id') or '').strip()
    if not cid:
        continue
    print('=' * 70)
    print(cid, '| videos_per_day', cfg.get('videos_per_day'), '| github_workflow', cfg.get('github_workflow'), '| render_workflow', cfg.get('render_workflow'),
          '| privacy', cfg.get('privacy'), '| carica', cfg.get('carica'), '| publish_time', cfg.get('publish_time'), '| motore ->', A.motore(cfg))
    fid = str(cfg.get('scout_production_sheet_id') or '').strip()
    if not fid:
        print('  nessun file di produzione'); continue
    try:
        sch, h, prod, gid = A.righe(fid, con_gid=True)
    except Exception as e:
        print('  FILE NON LEGGIBILE:', str(e)[:150]); continue
    try:
        meta = A.api(fid, 'GET', '?fields=sheets.properties.title,sheets.protectedRanges')
        print('  scrittura: account del coach editor =', A.puo_scrivere(fid))
    except Exception as e:
        print('  controllo scrittura non riuscito', str(e)[:100])
    print('  colonne:', h)
    print('  stati:', dict(collections.Counter(str(r.get('status')).strip() for r in prod)))
    fatte = [r for r in prod if str(r.get('youtube_video_id') or '').strip()]
    if fatte:
        print('  ultima completata:', json.dumps({k: str(v)[:80] for k, v in fatte[-1].items() if str(v).strip()}, ensure_ascii=False))
    pronta = next((r for r in prod if str(r.get('status')).strip() == 'Pronto'), None)
    if pronta:
        print('  prossima Pronto:', json.dumps({k: str(v)[:80] for k, v in pronta.items() if str(v).strip()}, ensure_ascii=False))
