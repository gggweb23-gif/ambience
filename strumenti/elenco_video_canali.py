#!/usr/bin/env python3
"""Elenco (solo lettura) degli ultimi video di ogni canale, anche privati e programmati: titolo, durata, stato, uscita."""
import json, os, re, sys, urllib.parse, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import avvio_canali as A
import dichiarazioni_yt as DICH
import performance as PF

E = os.environ.get
MODIFICHE = [0]   # 7 nov: tetto alle modifiche per non finire la quota YouTube del giorno
_, _, canali = A.righe(A.CONFIGS)
for cfg in canali:
    cid = str(cfg.get('channel_id') or '').strip()
    chiave = str(cfg.get('chiave_youtube') or '').strip() or {'Storia in Minuti': 'YT_REFRESH_TOKEN_STORIA', 'KAO PSICOLOGIA': 'YT_REFRESH_TOKEN_KAO'}.get(cid, '') \
        or 'YT_REFRESH_TOKEN_' + re.sub(r'[^A-Z0-9]+', '_', cid.upper()).strip('_')
    rt = E(chiave)
    if not rt:
        continue
    h = {'Authorization': 'Bearer ' + PF.token(rt)[0]}
    g = lambda p, **q: json.loads(urllib.request.urlopen(urllib.request.Request('https://www.googleapis.com/youtube/v3/' + p + '?' + urllib.parse.urlencode(q), headers=h), timeout=60).read())
    up = g('channels', part='contentDetails', mine='true')['items'][0]['contentDetails']['relatedPlaylists']['uploads']
    ids = [x['contentDetails']['videoId'] for x in g('playlistItems', part='contentDetails', playlistId=up, maxResults=min(int(E('QUANTI', '25')), 50)).get('items', [])]
    print('=====', cid)
    elenco = []
    for i in range(0, len(ids), 50):
        elenco += g('videos', part='snippet,status,contentDetails,statistics,paidProductPlacementDetails', id=','.join(ids[i:i + 50])).get('items', [])
    if E('PROMO_NO'):   # 6-7 nov (Giorgio): "Promozione a pagamento" = No e "Utilizzo dell'AI" = No su tutti i video e gli Short gia' caricati
        def sec(v):
            m = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', v['contentDetails'].get('duration', '')) or None
            return sum(int(x or 0) * k for x, k in zip(m.groups(), (3600, 60, 1))) if m else 9999
        for v in sorted(elenco, key=sec):   # prima gli Short; si tocca solo quello che manca (ogni modifica costa 50 unita' di quota YouTube)
            if MODIFICHE[0] >= int(E('MAX_MODIFICHE', '40')):
                print('   limite di modifiche raggiunto per oggi (quota YouTube): il resto domani'); break
            vid, st = v['id'], v['status']
            if (v.get('paidProductPlacementDetails') or {}).get('hasPaidProductPlacement') is not False:
                print('  ', vid, end=' '); DICH.nessuna_promozione(vid, h['Authorization'][7:]); MODIFICHE[0] += 1
            if st.get('containsSyntheticMedia') is not False:
                nuovo = {k: st[k] for k in ('privacyStatus', 'publishAt', 'embeddable', 'license', 'publicStatsViewable') if k in st}
                nuovo.update({'selfDeclaredMadeForKids': bool(st.get('selfDeclaredMadeForKids', False)), 'containsSyntheticMedia': False})
                try:
                    urllib.request.urlopen(urllib.request.Request('https://www.googleapis.com/youtube/v3/videos?part=status', method='PUT',
                        data=json.dumps({'id': vid, 'status': nuovo}).encode(), headers={**h, 'Content-Type': 'application/json'}), timeout=60).read()
                    print('  ', vid, 'utilizzo AI: No'); MODIFICHE[0] += 1
                except Exception as e:
                    print('  ', vid, 'utilizzo AI non impostato:', str(e)[:150], (e.read().decode(errors='ignore')[:200] if hasattr(e, 'read') else ''))
        quanti = len(elenco); elenco = g('videos', part='snippet,status,contentDetails,statistics,paidProductPlacementDetails', id=','.join(ids[:50])).get('items', [])
    for v in elenco:
        print(f"  {v['id']} | {v['contentDetails']['duration']:>9} | {v['status']['privacyStatus']:>8} | {v['status'].get('publishAt', v['snippet']['publishedAt'])[:16]} | {v['snippet']['title'][:95]}")
        if E('DETTAGLI'):   # tutte le impostazioni che possono frenare le impression
            st, sn, cd = v['status'], v['snippet'], v['contentDetails']
            print(f"      upload={st.get('uploadStatus')} kids={st.get('madeForKids')}/{st.get('selfDeclaredMadeForKids')} AI={st.get('containsSyntheticMedia')} promo={(v.get('paidProductPlacementDetails') or {}).get('hasPaidProductPlacement')} "
                  f"embed={st.get('embeddable')} stats={st.get('publicStatsViewable')} lic={st.get('license')} cat={sn.get('categoryId')} "
                  f"lingua={sn.get('defaultLanguage')}/{sn.get('defaultAudioLanguage')} tag={len(sn.get('tags') or [])} def={cd.get('definition')} "
                  f"caption={cd.get('caption')} blocchi={cd.get('regionRestriction')} rating={cd.get('contentRating')} views={v.get('statistics', {}).get('viewCount')}")
