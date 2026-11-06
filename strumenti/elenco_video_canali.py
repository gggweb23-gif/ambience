#!/usr/bin/env python3
"""Elenco (solo lettura) degli ultimi video di ogni canale, anche privati e programmati: titolo, durata, stato, uscita."""
import json, os, re, sys, urllib.parse, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import avvio_canali as A
import performance as PF

E = os.environ.get
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
    ids = [x['contentDetails']['videoId'] for x in g('playlistItems', part='contentDetails', playlistId=up, maxResults=int(E('QUANTI', '25'))).get('items', [])]
    print('=====', cid)
    for v in g('videos', part='snippet,status,contentDetails,statistics', id=','.join(ids)).get('items', []):
        print(f"  {v['id']} | {v['contentDetails']['duration']:>9} | {v['status']['privacyStatus']:>8} | {v['status'].get('publishAt', v['snippet']['publishedAt'])[:16]} | {v['snippet']['title'][:95]}")
        if E('DETTAGLI'):   # tutte le impostazioni che possono frenare le impression
            st, sn, cd = v['status'], v['snippet'], v['contentDetails']
            print(f"      upload={st.get('uploadStatus')} kids={st.get('madeForKids')}/{st.get('selfDeclaredMadeForKids')} AI={st.get('containsSyntheticMedia')} "
                  f"embed={st.get('embeddable')} stats={st.get('publicStatsViewable')} lic={st.get('license')} cat={sn.get('categoryId')} "
                  f"lingua={sn.get('defaultLanguage')}/{sn.get('defaultAudioLanguage')} tag={len(sn.get('tags') or [])} def={cd.get('definition')} "
                  f"caption={cd.get('caption')} blocchi={cd.get('regionRestriction')} rating={cd.get('contentRating')} views={v.get('statistics', {}).get('viewCount')}")
