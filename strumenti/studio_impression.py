#!/usr/bin/env python3
"""STUDIO IMPRESSION (sola lettura, gratis): perche' sullo stesso canale alcuni video hanno impression e altri zero.
Per ogni token YouTube (segreti YT_REFRESH_TOKEN*) legge TUTTI i video del canale (playlist caricamenti: pubblici, non in elenco,
privati/programmati) con tutte le parti utili di videos.list (anche quelle visibili solo al proprietario), playlist,
YouTube Analytics (views a vita, fonti di traffico, views per giorno) e il report "reach" della Reporting API
(impression per video per giorno, senza crearne di nuovi). Aggiunge le righe dei file di produzione (Channel Configs).
Scrive studio_impression/<canale>.json e studio_impression/riepilogo.csv. Non modifica nulla.
Quota Data API: ~1 unita' per chiamata (videos/playlistItems/playlists); captions.list (50 unita') solo se CAPTIONS=SI."""
import csv, datetime as dt, hashlib, io, json, os, re, sys, urllib.error, urllib.parse, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

E = os.environ.get
API = 'https://www.googleapis.com/youtube/v3/'
OUT = 'studio_impression'; os.makedirs(OUT, exist_ok=True)
OGGI = dt.date.today()
CAPTIONS = E('CAPTIONS', 'NO').upper() == 'SI'
CAP_MAX = int(E('CAPTIONS_MAX', '4') or 4)


def http(url, h=None, raw=False, dati=None):
    req = urllib.request.Request(url, data=dati, headers=dict({'User-Agent': 'ambience-studio/1.0'}, **(h or {})))
    r = urllib.request.urlopen(req, timeout=90).read()
    return r if raw else json.loads(r or b'{}')


def errore(e):
    try:
        return f'{e.code} ' + e.read().decode()[:300]
    except Exception:
        return str(e)[:300]


def token(rt):
    d = urllib.parse.urlencode({'client_id': E('YT_CLIENT_ID'), 'client_secret': E('YT_CLIENT_SECRET'), 'refresh_token': rt, 'grant_type': 'refresh_token'}).encode()
    t = http('https://oauth2.googleapis.com/token', dati=d)
    return t['access_token'], t.get('scope', '')


def slug(s):
    return re.sub(r'[^a-z0-9]+', '_', str(s).lower()).strip('_')


def sec(iso):
    m = re.match(r'P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', iso or '')
    g, hh, mi, s = (int(x or 0) for x in m.groups()) if m else (0, 0, 0, 0)
    return g * 86400 + hh * 3600 + mi * 60 + s


def ahash(b):
    """impronta media 8x8 dell'immagine (per capire se la copertina e' uno dei fotogrammi automatici)."""
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(b)).convert('L')
        w, hgt = im.size   # le hqdefault hanno bande nere sopra e sotto: si taglia il 4:3 al centro 16:9
        im = im.crop((0, int(hgt * .125), w, int(hgt * .875))).resize((8, 8))
        px = list(im.getdata()); m = sum(px) / 64
        return ''.join('1' if p > m else '0' for p in px)
    except Exception:
        return None


def dist(a, b):
    return None if not a or not b else sum(x != y for x, y in zip(a, b))


def copertina(vid):
    out = {}
    for nome in ('hqdefault', 'hq1', 'hq2', 'hq3', 'maxresdefault'):
        try:
            b = http(f'https://i.ytimg.com/vi/{vid}/{nome}.jpg', raw=True)
            out[nome] = {'bytes': len(b), 'md5': hashlib.md5(b).hexdigest(), 'ahash': ahash(b)}
        except urllib.error.HTTPError as e:
            out[nome] = {'errore': e.code}
        except Exception as e:
            out[nome] = {'errore': str(e)[:60]}
    hq = (out.get('hqdefault') or {}).get('ahash')
    d = [dist(hq, (out.get(k) or {}).get('ahash')) for k in ('hq1', 'hq2', 'hq3')]
    d = [x for x in d if x is not None]
    out['dist_min_da_fotogrammi_auto'] = min(d) if d else None
    out['probabile_personalizzata'] = (min(d) > 10) if d else None
    return out


def analytics(auth, **p):
    return http('https://youtubeanalytics.googleapis.com/v2/reports?' + urllib.parse.urlencode(dict({'ids': 'channel==MINE'}, **p)), auth)


def tabella(r):
    cols = [c['name'] for c in r.get('columnHeaders', [])]
    return [dict(zip(cols, x)) for x in r.get('rows', []) or []]


def reach(auth):
    """impression per video e per giorno dai report gia' esistenti della Reporting API (nessun job nuovo)."""
    info = {'jobs': [], 'giorni': [], 'per_video': {}, 'colonne': None}
    try:
        jobs = http('https://youtubereporting.googleapis.com/v1/jobs', auth).get('jobs', [])
    except urllib.error.HTTPError as e:
        info['errore'] = errore(e); return info
    info['jobs'] = [{k: j.get(k) for k in ('id', 'reportTypeId', 'name', 'createTime')} for j in jobs]
    for job in [j for j in jobs if 'reach' in str(j.get('reportTypeId', ''))]:
        reps, pg = [], ''
        for _ in range(20):
            r = http(f'https://youtubereporting.googleapis.com/v1/jobs/{job["id"]}/reports?' + urllib.parse.urlencode({'pageSize': 100, 'pageToken': pg}), auth)
            reps += r.get('reports', []); pg = r.get('nextPageToken')
            if not pg:
                break
        giorno = {}
        for rp in reps:
            g = str(rp.get('startTime', ''))[:10]
            if g and rp.get('downloadUrl') and (g not in giorno or str(rp.get('createTime')) > str(giorno[g].get('createTime'))):
                giorno[g] = rp
        for g, rp in sorted(giorno.items()):
            try:
                righe = list(csv.reader(io.StringIO(http(rp['downloadUrl'], auth, raw=True).decode('utf-8', 'ignore'))))
            except Exception as e:
                info['giorni'].append({'giorno': g, 'job': job['reportTypeId'], 'errore': str(e)[:80]}); continue
            if not righe:
                continue
            hd = righe[0]; info['colonne'] = hd
            info['giorni'].append({'giorno': g, 'job': job['reportTypeId'], 'creato': rp.get('createTime'), 'righe': len(righe) - 1})
            if 'video_thumbnail_impressions' not in hd:
                continue
            iV, iI, iC = hd.index('video_id'), hd.index('video_thumbnail_impressions'), hd.index('video_thumbnail_impressions_ctr')
            iT = hd.index('traffic_source_type') if 'traffic_source_type' in hd else None
            iS = hd.index('subscribed_status') if 'subscribed_status' in hd else None
            for x in righe[1:]:
                if len(x) <= iC or not x[iV]:
                    continue
                try:
                    imp = float(x[iI] or 0); ctr = float(x[iC] or 0)
                except ValueError:
                    continue
                z = info['per_video'].setdefault(x[iV], {'giorni': {}, 'fonti': {}, 'iscritti': {}, 'imp': 0.0, 'clic_stimati': 0.0})
                z['giorni'][g] = z['giorni'].get(g, 0) + imp; z['imp'] += imp
                z['clic_stimati'] += imp * (ctr / 100 if ctr > 1 else ctr)
                if iT is not None:
                    z['fonti'][x[iT]] = z['fonti'].get(x[iT], 0) + imp
                if iS is not None:
                    z['iscritti'][x[iS]] = z['iscritti'].get(x[iS], 0) + imp
        break   # un solo job reach basta
    return info


def configs():
    try:
        import avvio_canali as A
        _, _, cc = A.righe(A.CONFIGS)
        return A, cc
    except Exception as e:
        print('Channel Configs non letto:', str(e)[:150]); return None, []


def chiave_cfg(cfg):
    cid = str(cfg.get('channel_id') or '').strip()
    return str(cfg.get('chiave_youtube') or '').strip() or {'Storia in Minuti': 'YT_REFRESH_TOKEN_STORIA', 'KAO PSICOLOGIA': 'YT_REFRESH_TOKEN_KAO'}.get(cid, '') \
        or 'YT_REFRESH_TOKEN_' + re.sub(r'[^A-Z0-9]+', '_', cid.upper()).strip('_')


def canale(chiave, rt, A, cc, gia):
    tk, scope = token(rt)
    h = {'Authorization': 'Bearer ' + tk}
    ch = http(API + 'channels?part=snippet,status,contentDetails,brandingSettings,statistics,topicDetails&mine=true', h)['items'][0]
    if ch['id'] in gia:
        print(chiave, '-> stesso canale di', gia[ch['id']], ': salto'); return None
    gia[ch['id']] = chiave
    nome = ch['snippet']['title']; print('===', nome, ch['id'], chiave)
    up = ch['contentDetails']['relatedPlaylists']['uploads']
    ids, pg = [], ''
    while True:
        r = http(API + 'playlistItems?' + urllib.parse.urlencode({'part': 'contentDetails,snippet,status', 'maxResults': 50, 'playlistId': up, 'pageToken': pg}), h)
        ids += [i['contentDetails']['videoId'] for i in r.get('items', [])]
        pg = r.get('nextPageToken')
        if not pg:
            break
    parti = 'snippet,contentDetails,status,statistics,topicDetails,localizations,recordingDetails,processingDetails,fileDetails,suggestions,liveStreamingDetails'
    vids = {}
    for k in range(0, len(ids), 50):
        try:
            for x in http(API + 'videos?' + urllib.parse.urlencode({'part': parti, 'id': ','.join(ids[k:k + 50])}), h).get('items', []):
                vids[x['id']] = x
        except urllib.error.HTTPError as e:
            print('  videos.list con tutte le parti fallito:', errore(e), '-> riprovo senza suggestions/fileDetails')
            for x in http(API + 'videos?' + urllib.parse.urlencode({'part': parti.replace(',suggestions', '').replace(',fileDetails', ''), 'id': ','.join(ids[k:k + 50])}), h).get('items', []):
                vids[x['id']] = x
    # playlist del canale e appartenenza
    pls, pg = [], ''
    while True:
        r = http(API + 'playlists?' + urllib.parse.urlencode({'part': 'snippet,status,contentDetails', 'mine': 'true', 'maxResults': 50, 'pageToken': pg}), h)
        pls += r.get('items', []); pg = r.get('nextPageToken')
        if not pg:
            break
    membri = {}
    for p in pls:
        pg = ''
        while True:
            r = http(API + 'playlistItems?' + urllib.parse.urlencode({'part': 'contentDetails,snippet', 'maxResults': 50, 'playlistId': p['id'], 'pageToken': pg}), h)
            for it in r.get('items', []):
                membri.setdefault(it['contentDetails']['videoId'], []).append({'playlist': p['snippet']['title'], 'aggiunto': it['snippet'].get('publishedAt')})
            pg = r.get('nextPageToken')
            if not pg:
                break
    # Analytics
    inizio = ch['snippet']['publishedAt'][:10]
    ana = {'errori': []}
    vita = {}
    try:
        r = analytics(h, startDate=inizio, endDate=OGGI.isoformat(), dimensions='video', maxResults=200, sort='-views',
                      metrics='views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,likes,subscribersGained,shares,comments')
        vita = {x['video']: x for x in tabella(r)}
    except urllib.error.HTTPError as e:
        ana['errori'].append('vita: ' + errore(e))
    for m in ('videoThumbnailImpressions,videoThumbnailImpressionsClickRate', 'impressions,impressionsClickThroughRate'):
        try:
            r = analytics(h, startDate=inizio, endDate=OGGI.isoformat(), dimensions='video', maxResults=200, sort='-views', metrics='views,' + m)
            ana['impression_da_analytics'] = {x['video']: x for x in tabella(r)}; break
        except urllib.error.HTTPError as e:
            ana['errori'].append(m + ': ' + errore(e))
    try:
        ana['canale_per_giorno'] = tabella(analytics(h, startDate=inizio, endDate=OGGI.isoformat(), dimensions='day', metrics='views,estimatedMinutesWatched,subscribersGained'))
    except urllib.error.HTTPError as e:
        ana['errori'].append('canale_giorno: ' + errore(e))
    try:
        ana['canale_fonti'] = tabella(analytics(h, startDate=inizio, endDate=OGGI.isoformat(), dimensions='insightTrafficSourceType', metrics='views,estimatedMinutesWatched'))
    except urllib.error.HTTPError as e:
        ana['errori'].append('canale_fonti: ' + errore(e))
    rc = reach(h)
    giorni_reach = sorted(g['giorno'] for g in rc['giorni'] if 'errore' not in g)
    # file di produzione
    righe_prod = {}
    cfg_canale = []
    for cfg in cc:
        if chiave_cfg(cfg) != chiave and not (chiave == 'YT_REFRESH_TOKEN' and chiave_cfg(cfg) == 'YT_REFRESH_TOKEN_WWII_TESTIMONY'):
            continue
        cfg_canale.append({k: v for k, v in cfg.items() if not re.search(r'token|secret|password|api_key|callback', k, re.I)})
        fid = str(cfg.get('scout_production_sheet_id') or '').strip()
        if not fid or not A:
            continue
        try:
            _, hd, prod = A.righe(fid)
            for n, rr in enumerate(prod):
                v = str(rr.get('youtube_video_id') or '').strip()
                if v:
                    righe_prod.setdefault(v, []).append(dict({'_foglio_config': cfg.get('channel_id'), '_riga': n + 2},
                                                               **{k: str(x)[:300] for k, x in rr.items() if k and not re.search(r'copione|script|testo_completo', k, re.I)}))
        except Exception as e:
            print('  produzione non letta', cfg.get('channel_id'), str(e)[:100])
    # per video
    out = []
    cap_fatti = {'con': 0, 'zero': 0}
    for v in ids:
        x = vids.get(v)
        if not x:
            out.append({'id': v, 'mancante_in_videos_list': True}); continue
        sn, st, cd = x.get('snippet', {}), x.get('status', {}), x.get('contentDetails', {})
        z = rc['per_video'].get(v, {})
        d = {'id': v, 'titolo': sn.get('title'), 'publishedAt': sn.get('publishedAt'), 'privacy': st.get('privacyStatus'), 'publishAt': st.get('publishAt'),
             'durata_sec': sec(cd.get('duration')), 'impression_reach': z.get('imp', 0.0), 'clic_stimati': round(z.get('clic_stimati', 0.0), 1),
             'reach_giorni': z.get('giorni', {}), 'reach_fonti': z.get('fonti', {}), 'reach_iscritti': z.get('iscritti', {}),
             'analytics_vita': vita.get(v), 'playlist': membri.get(v, []), 'produzione': righe_prod.get(v, []), 'api': x}
        pub = sn.get('publishedAt')
        if st.get('privacyStatus') == 'public' and pub:
            try:
                d['fonti_traffico'] = tabella(analytics(h, startDate=pub[:10], endDate=OGGI.isoformat(), dimensions='insightTrafficSourceType',
                                                        metrics='views,estimatedMinutesWatched', filters='video==' + v))
                d['views_per_giorno'] = tabella(analytics(h, startDate=pub[:10], endDate=OGGI.isoformat(), dimensions='day', metrics='views', filters='video==' + v))
                d['luoghi_riproduzione'] = tabella(analytics(h, startDate=pub[:10], endDate=OGGI.isoformat(), dimensions='insightPlaybackLocationType',
                                                             metrics='views', filters='video==' + v))
            except urllib.error.HTTPError as e:
                d['errore_analytics'] = errore(e)
            d['copertina'] = copertina(v)
            gruppo = 'con' if d['impression_reach'] > 0 else 'zero'
            if CAPTIONS and cap_fatti[gruppo] < CAP_MAX:
                try:
                    d['captions'] = [c_['snippet'] for c_ in http(API + 'captions?part=snippet&videoId=' + v, h).get('items', [])]
                    cap_fatti[gruppo] += 1
                except urllib.error.HTTPError as e:
                    d['captions_errore'] = errore(e)
        out.append(d)
    dati = {'raccolto': dt.datetime.utcnow().isoformat() + 'Z', 'chiave': chiave, 'scope_token': scope, 'canale': ch, 'channel_configs': cfg_canale,
            'reach': {'jobs': rc['jobs'], 'colonne': rc['colonne'], 'giorni': rc['giorni'], 'primo_giorno': giorni_reach[0] if giorni_reach else None,
                      'ultimo_giorno': giorni_reach[-1] if giorni_reach else None, 'errore': rc.get('errore')},
            'analytics_canale': ana, 'playlist': [{'id': p['id'], 'titolo': p['snippet']['title'], 'creata': p['snippet']['publishedAt'],
                                                     'privacy': p.get('status', {}).get('privacyStatus'), 'n': p.get('contentDetails', {}).get('itemCount')} for p in pls],
            'video_nel_reach_non_in_uploads': {k: v_['imp'] for k, v_ in rc['per_video'].items() if k not in vids},
            'video': out}
    json.dump(dati, open(os.path.join(OUT, slug(nome) + '.json'), 'w'), ensure_ascii=False, indent=1)
    print(f'  {len(ids)} video, reach {dati["reach"]["primo_giorno"]} -> {dati["reach"]["ultimo_giorno"]} ({len(giorni_reach)} giorni), errori analytics: {ana["errori"]}')
    return nome, dati


def main():
    A, cc = configs()
    gia, riep = {}, []
    chiavi = sorted(k for k in os.environ if k.startswith('YT_REFRESH_TOKEN') and os.environ[k].strip())
    chiavi = [k for k in chiavi if k != 'YT_REFRESH_TOKEN'] + (['YT_REFRESH_TOKEN'] if 'YT_REFRESH_TOKEN' in chiavi else [])
    for k in chiavi:
        try:
            r = canale(k, os.environ[k].strip(), A, cc, gia)
        except Exception as e:
            print('ERRORE', k, str(e)[:300]); continue
        if not r:
            continue
        nome, d = r
        ug = d['reach']['ultimo_giorno']
        for v in d['video']:
            if v.get('mancante_in_videos_list'):
                continue
            st = v['api'].get('status', {}); sn = v['api'].get('snippet', {})
            pd = (v.get('produzione') or [{}])[0]
            riep.append({'canale': nome, 'id': v['id'], 'privacy': v['privacy'], 'publishedAt': v['publishedAt'], 'publishAt': v['publishAt'] or '',
                         'durata_sec': v['durata_sec'], 'views': v['api'].get('statistics', {}).get('viewCount'),
                         'impression_reach': round(v['impression_reach']), 'reach_ultimo_giorno': ug,
                         'madeForKids': st.get('madeForKids'), 'synthetic': st.get('containsSyntheticMedia'), 'license': st.get('license'),
                         'uploadStatus': st.get('uploadStatus'), 'lang': sn.get('defaultLanguage'), 'audio': sn.get('defaultAudioLanguage'),
                         'cat': sn.get('categoryId'), 'tags': len(sn.get('tags') or []), 'len_titolo': len(sn.get('title') or ''),
                         'len_descr': len(sn.get('description') or ''), 'cop_personalizzata': (v.get('copertina') or {}).get('probabile_personalizzata'),
                         'playlist': len(v.get('playlist') or []), 'fonti': json.dumps(v.get('fonti_traffico') or [], ensure_ascii=False)[:300],
                         'motore_foglio': pd.get('_foglio_config', ''), 'titolo': (v['titolo'] or '')[:90]})
    if riep:
        with open(os.path.join(OUT, 'riepilogo.csv'), 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(riep[0])); w.writeheader(); w.writerows(riep)
        for r in riep:
            print('|'.join(str(r[k]) for k in ('canale', 'id', 'privacy', 'publishedAt', 'impression_reach', 'views', 'cop_personalizzata', 'titolo')))


if __name__ == '__main__':
    main()
