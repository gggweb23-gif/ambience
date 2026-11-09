#!/usr/bin/env python3
"""PERFORMANCE DEI VIDEO (al posto del workflow n8n "Performance"), gratis, ogni mattina.
Per ogni canale di Channel Configs con chiave_youtube e file di produzione: prende gli ultimi N video pubblicati
(colonna youtube_video_id del file di produzione) e riscrive la scheda "Performance" dello stesso file con
views, impression, CTR, ritenzione a 30 s e a 60 s (le colonne che legge il Coach, coach/coach_calcola.py).
- views, durata media, ritenzione: YouTube Analytics API (dati con 1-3 giorni di ritardo)
- impression e CTR della copertina: report "reach" della YouTube Reporting API (il primo report arriva ~2 giorni dopo l'attivazione)
Il token YouTube del canale deve avere il permesso yt-analytics.readonly.
5 nov 2026 (Giorgio, proposta 1 dello studio impression): i download dei report che falliscono (429/5xx) si riprovano con attesa
crescente e un giorno mancante non si salta mai in silenzio; colonne in fondo giorni_report / copertura_report: quanti giorni di
report coprono il video e se sono completi. Video senza giorni di report: impression e ctr = "in attesa report" (non 0).
Il job dei report impression si crea appena il canale ha il token, anche senza video (proposta 2)."""
import csv, datetime as dt, io, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import avvio_canali as A

E = os.environ.get
SEGRETI = json.loads(E('SEGRETI', '') or '{}')
N_VIDEO = int(E('N_VIDEO', '20'))
SOLO = E('SOLO_CANALE', '').strip()
# stessi nomi di colonna che usava n8n (li legge il Coach), piu' qualche colonna in fondo
COLONNE = ['data_rilevazione', 'youtube_video_id', 'titolo', 'giorni_dalla_pubblicazione', 'views', 'durata_media_sec', 'perc_media_guardata',
           'ritenzione_30s', 'iscritti', 'impression', 'ctr', 'ritenzione_60s', 'data_pubblicazione', 'durata_video_sec', 'mi_piace',
           'giorni_report', 'copertura_report']   # ultime 2 (5 nov): giorni di report reach sul video (il Coach usa solo video con >= 3 giorni completi)
IN_ATTESA = 'in attesa report'
PT = A.ZoneInfo('America/Los_Angeles')   # i giorni dei report reach di YouTube sono in ora del Pacifico
REPORT = []
DATI_EXCEL = {}   # 9 nov: dati per il foglio Excel del mattino (strumenti/report_excel.py)


def log(*a):
    s = ' '.join(str(x) for x in a); print(s, flush=True); REPORT.append(s)


def http(url, corpo=None, headers=None, metodo=None, raw=False, tentativi=6):
    """429 / 5xx / errori di rete: si riprova con attesa crescente (5, 10, 20, 40, 60 s) prima di arrendersi."""
    for prova in range(tentativi):
        req = urllib.request.Request(url, data=json.dumps(corpo).encode() if corpo is not None else None, method=metodo,
                                     headers=dict({'Content-Type': 'application/json'}, **(headers or {})))
        try:
            r = urllib.request.urlopen(req, timeout=90).read()
            return r if raw else json.loads(r or b'{}')
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503, 504) or prova == tentativi - 1:
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if prova == tentativi - 1:
                raise
        time.sleep(min(60, 5 * 2 ** prova))


def num(v, d=None):
    try:
        return float(str(v).replace('%', '').replace(',', '.'))
    except Exception:
        return d


def token(rt):
    d = urllib.parse.urlencode({'client_id': E('YT_CLIENT_ID'), 'client_secret': E('YT_CLIENT_SECRET'), 'refresh_token': rt, 'grant_type': 'refresh_token'}).encode()
    t = json.loads(urllib.request.urlopen(urllib.request.Request('https://oauth2.googleapis.com/token', data=d), timeout=30).read())
    return t['access_token'], t.get('scope', '')


def secondi(iso):
    m = re.match(r'P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', iso or '')
    if not m:
        return 0
    g, h, mi, s = (int(x or 0) for x in m.groups())
    return g * 86400 + h * 3600 + mi * 60 + s


def job_reach(auth, cfg):
    """Il job del report impression/CTR (reach); se il canale non ce l'ha si crea subito (anche senza video: i report
    partono ~2 giorni dopo la creazione, prima si attiva meglio e'). Restituisce il job o None se appena creato."""
    jobs = http('https://youtubereporting.googleapis.com/v1/jobs', headers=auth).get('jobs', [])
    job = next((j for j in jobs if j.get('id') == str(cfg.get('reach_job_id') or '').strip()), None) or \
        next((j for j in jobs if 'reach' in str(j.get('reportTypeId', ''))), None)
    if not job:
        tipi = http('https://youtubereporting.googleapis.com/v1/reportTypes', headers=auth).get('reportTypes', [])
        tipo = next((t['id'] for t in tipi if t['id'] == 'channel_reach_basic_a1'), None) or next((t['id'] for t in tipi if 'reach' in t['id']), None)
        if tipo and E('PROVA') != 'SI':
            http('https://youtubereporting.googleapis.com/v1/jobs', {'reportTypeId': tipo, 'name': 'reach_ctr'}, auth, metodo='POST')
            log('  attivato il report impression/CTR: i primi dati arrivano tra circa 2 giorni')
        elif tipo:
            log('  (prova) il report impression/CTR non e\' attivo: nel giro vero verrebbe attivato')
    return job


def impression_ctr(auth, cfg):
    """{'per': {video: [impression, clic, {giorni con dati}]}, 'giorni': giorni scaricati, 'mancanti': giorni non scaricati
    nonostante i tentativi, 'primo'/'ultimo': primo e ultimo giorno disponibile} dai report reach (ultimi 60 giorni).
    None se il canale non ha ancora il job."""
    job = job_reach(auth, cfg)
    if not job:
        return None
    reps, pg = [], ''
    for _ in range(10):
        r = http(f'https://youtubereporting.googleapis.com/v1/jobs/{job["id"]}/reports?' + urllib.parse.urlencode({'pageSize': 100, 'pageToken': pg}), headers=auth)
        reps += r.get('reports', []); pg = r.get('nextPageToken')
        if not pg:
            break
    giorno = {}
    for rp in reps:   # per ogni giorno l'ultima versione del report
        g = str(rp.get('startTime', ''))[:10]
        if g and rp.get('downloadUrl') and (g not in giorno or str(rp.get('createTime')) > str(giorno[g].get('createTime'))):
            giorno[g] = rp
    per, fatti, mancanti = {}, set(), []
    scelti = sorted(giorno.items())[-60:]
    for g, rp in scelti:
        try:
            righe = list(csv.reader(io.StringIO(http(rp['downloadUrl'], headers=auth, raw=True).decode('utf-8', 'ignore'))))
        except Exception as e:   # mai piu' saltato in silenzio: il giorno resta segnato come mancante
            mancanti.append(g); log(f'  !! report del {g} NON scaricato dopo i tentativi ({str(e)[:80]}): i video di quel giorno risultano "incompleto"')
            continue
        if not righe or 'video_thumbnail_impressions' not in righe[0]:
            fatti.add(g); continue   # giorno senza impression (report vuoto): e' un dato, non un buco
        h = righe[0]; iV, iI, iC = h.index('video_id'), h.index('video_thumbnail_impressions'), h.index('video_thumbnail_impressions_ctr')
        dati = [(x[iV], num(x[iI], 0), num(x[iC], 0)) for x in righe[1:] if len(x) > iC and x[iV]]
        scala = 100 if any(d[2] > 1 for d in dati) else 1
        for v, imp, ctr in dati:
            z = per.setdefault(v, [0.0, 0.0]); z[0] += imp; z[1] += imp * ctr / scala
        fatti.add(g)
    giorni = sorted(g for g, _ in scelti)
    if giorni:   # giorni che YouTube non ha (ancora) pubblicato in mezzo all'intervallo: anche questi sono buchi
        a, b = dt.date.fromisoformat(giorni[0]), dt.date.fromisoformat(giorni[-1])
        mancanti += [x for x in ((a + dt.timedelta(i)).isoformat() for i in range((b - a).days + 1)) if x not in giorno and x not in mancanti]
    log(f'  report impression/CTR: {len(giorno)} giorni disponibili, {len(fatti)} letti, ultimo {giorni[-1] if giorni else "-"}'
        + (f' | GIORNI MANCANTI: {", ".join(sorted(mancanti))}' if mancanti else ''))
    return {'per': per, 'fatti': fatti, 'mancanti': set(mancanti), 'primo': giorni[0] if giorni else None, 'ultimo': giorni[-1] if giorni else None}


def copertura(rep, pub):
    """(giorni_report, testo) per un video pubblicato a pub (datetime UTC): giorni di report dal giorno di uscita (ora del Pacifico)
    all'ultimo report disponibile; 'incompleto' se in mezzo manca un giorno."""
    if not rep or not rep.get('ultimo'):
        return 0, 'report non attivo'
    g0 = pub.astimezone(PT).date(); ult = dt.date.fromisoformat(rep['ultimo']); primo = dt.date.fromisoformat(rep['primo'])
    if g0 > ult:
        return 0, 'non ancora disponibile (report fino al ' + ult.strftime('%d/%m') + ')'
    giorni = [(max(g0, primo) + dt.timedelta(i)).isoformat() for i in range((ult - max(g0, primo)).days + 1)]
    buchi = [x for x in giorni if x in rep['mancanti'] or x not in rep['fatti']]
    n = len(giorni) - len(buchi)
    if buchi:
        return n, 'incompleto: mancano ' + ', '.join(dt.date.fromisoformat(x).strftime('%d/%m') for x in buchi[:6])
    return n, 'completa fino al ' + ult.strftime('%d/%m') + (' (ultimi 60 giorni)' if g0 < primo else '')


def analytics(auth, params):
    return http('https://youtubeanalytics.googleapis.com/v2/reports?' + urllib.parse.urlencode(dict({'ids': 'channel==MINE'}, **params)), headers=auth)


def ritenzione(auth, vid, inizio, durata):
    """% di spettatori ancora presenti a 30 e a 60 secondi (curva audienceWatchRatio di YouTube)."""
    r = analytics(auth, {'startDate': inizio, 'endDate': dt.date.today().isoformat(), 'metrics': 'audienceWatchRatio',
                         'dimensions': 'elapsedVideoTimeRatio', 'filters': f'video=={vid}'})
    pts = sorted((float(x[0]), float(x[1])) for x in r.get('rows', []) or [])
    if not pts or not durata:
        return None, None

    def a(sec):
        t = sec / durata
        if t >= pts[-1][0]:
            return None
        for (x0, y0), (x1, y1) in zip([(0.0, pts[0][1])] + pts, pts):
            if x0 <= t <= x1:
                return round(100 * (y0 + (y1 - y0) * (t - x0) / max(1e-9, x1 - x0)), 1)
        return None
    return a(30), a(60)


def scrivi(fid, valori):
    if E('PROVA') == 'SI':   # sola lettura: mostra la scheda attuale e cosa verrebbe scritto
        try:
            v = A.api(fid, 'GET', '/values/' + urllib.parse.quote("'Performance'!A1:Z6")).get('values', [])
            log('  scheda Performance attuale:', json.dumps(v, ensure_ascii=False)[:800])
        except Exception as e:
            log('  scheda Performance non presente', str(e)[:80])
        log('  verrebbe scritto (video | impression | ctr | giorni_report | copertura_report):')
        for r in valori[1:]:
            log(f'    {r[1]} | {r[9]} | {r[10]} | {r[15]} | {r[16]}')
        return
    meta = A.api(fid, 'GET', '?fields=sheets.properties')
    nomi = [s['properties']['title'] for s in meta['sheets']]
    for s_ in meta['sheets']:   # le schede Performance mai in prima posizione (tutti i programmi leggono i video dalla prima scheda)
        if s_['properties']['title'].startswith('Performance') and s_['properties'].get('index', 0) == 0 and len(nomi) > 1:
            A.api(fid, 'POST', ':batchUpdate', {'requests': [{'updateSheetProperties': {'properties': {'sheetId': s_['properties']['sheetId'], 'index': len(nomi)},
                                                                                       'fields': 'index'}}]})
            log('  scheda', s_['properties']['title'], 'spostata in fondo')
    if 'Performance' not in nomi:
        A.api(fid, 'POST', ':batchUpdate', {'requests': [{'addSheet': {'properties': {'title': 'Performance', 'index': len(nomi)}}}]})
    elif 'Performance storico n8n' not in nomi:   # la prima volta: lo storico scritto da n8n si conserva in una scheda a parte
        sid = next(s_['properties']['sheetId'] for s_ in meta['sheets'] if s_['properties']['title'] == 'Performance')
        A.api(fid, 'POST', ':batchUpdate', {'requests': [{'duplicateSheet': {'sourceSheetId': sid, 'newSheetName': 'Performance storico n8n',
                                                                               'insertSheetIndex': len(nomi)}}]})   # in fondo: la prima scheda resta quella dei video
        log('  storico di n8n copiato nella scheda "Performance storico n8n"')
    A.api(fid, 'POST', '/values/' + urllib.parse.quote("'Performance'!A1:Z2000") + ':clear', {})
    A.api(fid, 'PUT', '/values/' + urllib.parse.quote("'Performance'!A1") + '?valueInputOption=RAW', {'values': valori})


def canale(cfg):
    cid = str(cfg.get('channel_id') or '').strip()
    chiave = str(cfg.get('chiave_youtube') or '').strip() or {'Storia in Minuti': 'YT_REFRESH_TOKEN_STORIA', 'KAO PSICOLOGIA': 'YT_REFRESH_TOKEN_KAO'}.get(cid, '') \
        or 'YT_REFRESH_TOKEN_' + re.sub(r'[^A-Z0-9]+', '_', cid.upper()).strip('_')
    fid = str(cfg.get('scout_production_sheet_id') or '').strip()
    if not cid or not fid or not chiave:
        return
    log('===', cid)
    rt = SEGRETI.get(chiave) or E(chiave)
    if not rt:
        log('  manca il segreto', chiave, 'su GitHub: salto'); return
    tk, scope = token(rt)
    if 'yt-analytics' not in scope:
        log('  IL TOKEN NON HA IL PERMESSO yt-analytics.readonly: va rigenerato (salto)'); return
    auth = {'Authorization': 'Bearer ' + tk}
    try:   # proposta 2 (5 nov): il report impression si attiva appena c'e' il token, anche se il canale non ha ancora video
        job_reach(auth, cfg)
    except urllib.error.HTTPError as e:
        log('  job report impression non verificato:', e.code, e.read().decode()[:150])
    _, _, prod = A.righe(fid)
    ids = []
    for r in prod:
        v = str(r.get('youtube_video_id') or '').strip()
        if v and v not in ids:
            ids.append(v)
    if not ids:
        log('  nessun video nel file di produzione'); return
    info = {}
    for k in range(0, len(ids), 50):
        for x in http('https://www.googleapis.com/youtube/v3/videos?' + urllib.parse.urlencode(
                {'part': 'snippet,contentDetails,status', 'id': ','.join(ids[k:k + 50])}), headers=auth).get('items', []):
            info[x['id']] = x
    ora = dt.datetime.now(dt.timezone.utc)
    usciti = []
    for v, x in info.items():
        st = x.get('status', {})
        if st.get('privacyStatus') != 'public':   # privati, programmati e non in elenco: non contano
            continue
        pub = dt.datetime.fromisoformat(x['snippet']['publishedAt'].replace('Z', '+00:00'))
        usciti.append((pub, v, x))
    usciti = sorted(usciti)[-N_VIDEO:]
    if not usciti:
        log('  nessun video pubblico'); return
    inizio = (usciti[0][0].date() - dt.timedelta(days=1)).isoformat()
    tot = {}
    try:
        r = analytics(auth, {'startDate': inizio, 'endDate': dt.date.today().isoformat(), 'dimensions': 'video', 'maxResults': 200,
                             'metrics': 'views,averageViewDuration,averageViewPercentage,likes,subscribersGained',
                             'filters': 'video==' + ','.join(v for _, v, _ in usciti), 'sort': '-views'})
        for row in r.get('rows', []) or []:
            tot[row[0]] = row[1:]
    except urllib.error.HTTPError as e:
        log('  Analytics non letto:', e.code, e.read().decode()[:200])
    try:
        imp = impression_ctr(auth, cfg)
    except urllib.error.HTTPError as e:
        imp = None; log('  report impression non letti:', e.code, e.read().decode()[:200])
    oggi = dt.datetime.now(A.ZoneInfo('Europe/Rome')).strftime('%Y-%m-%d %H:%M')
    righe = [COLONNE]
    for pub, v, x in usciti:
        dur = secondi(x['contentDetails'].get('duration'))
        try:
            r30, r60 = ritenzione(auth, v, inizio, dur)
        except Exception:
            r30 = r60 = None
        t = tot.get(v, [0, None, None, None, None])
        ic = ((imp or {}).get('per') or {}).get(v)
        ctr = round(ic[1] / ic[0] * 100, 2) if ic and ic[0] else None
        vuoto = lambda z: '' if z is None else z
        ng, cop = copertura(imp, pub)
        if ng == 0:   # nessun giorno di report sul video: non e' zero, e' in attesa
            c_imp = c_ctr = IN_ATTESA
        else:
            c_imp = int(ic[0]) if ic else 0; c_ctr = vuoto(ctr)
        righe.append([oggi, v, x['snippet']['title'], round((ora - pub).total_seconds() / 86400, 1), int(t[0] or 0), vuoto(t[1]),
                      round(t[2], 1) if t[2] is not None else '', vuoto(r30), vuoto(t[4]), c_imp, c_ctr, vuoto(r60),
                      pub.astimezone(A.ZoneInfo('Europe/Rome')).strftime('%Y-%m-%d %H:%M'), dur, vuoto(t[3]), ng, cop])
    scrivi(fid, righe)
    DATI_EXCEL[str(cfg.get('channel_name') or cid)] = [dict(zip(COLONNE, r)) for r in righe[1:]]
    ultimi = [x for x in righe[1:] if num(x[15], 0) >= 3 and not str(x[16]).startswith('incompleto')][-5:]   # solo video con >= 3 giorni di report
    attesa = sum(1 for x in righe[1:] if num(x[15], 0) < 3 or str(x[16]).startswith('incompleto'))
    if attesa:
        log(f'  {attesa} video in attesa di report (meno di 3 giorni completi): esclusi da impression/CTR')
    imp5 = sum(num(x[9], 0) for x in ultimi); clic5 = sum(num(x[9], 0) * num(x[10], 0) / 100 for x in ultimi)
    log(f'  scritti {len(righe) - 1} video | ultimi 5: views {sum(num(x[4], 0) for x in ultimi):.0f}, impression {imp5:.0f}, '
        f'CTR medio {clic5 / imp5 * 100:.2f}%' if imp5 else f'  scritti {len(righe) - 1} video | impression non ancora disponibili')


def coach_per_tutti(sch, h, canali):
    """Regola di Giorgio (4 nov 2026): ogni canale, presente e futuro, ha il controllo delle metriche.
    Canali attivi senza coach_auto -> SI nel foglio + ricetta di partenza. KAO escluso (regola di Giorgio del 30 ott)."""
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'coach'))
    import ricetta as R
    for i, cfg in enumerate(canali):
        cid = str(cfg.get('channel_id') or '').strip()
        if not cid or cid == 'KAO PSICOLOGIA' or A.num(cfg.get('videos_per_day')) < 1:
            continue
        if str(cfg.get('coach_auto') or '').strip().upper() != 'SI' and 'coach_auto' in h:
            A.api(A.CONFIGS, 'POST', '/values:batchUpdate', {'valueInputOption': 'RAW', 'data': [
                {'range': f"'{sch}'!{A.lettera(h.index('coach_auto') + 1)}{i + 2}", 'values': [['SI']]}]})
            log(f'coach_auto = SI messo per {cid}')
        f = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'coach', 'canali', R.slug(cid), 'ricetta.json')
        if not os.path.exists(f):
            os.makedirs(os.path.dirname(f), exist_ok=True)
            oggi = dt.datetime.now(A.ZoneInfo('Europe/Rome')).strftime('%Y-%m-%d %H:%M')
            json.dump({'channel_id': cid, 'competitor': str(cfg.get('competitor_1_name') or ''), 'stile_base': 'stile attuale del canale al ' + oggi[:10],
                       'versione_attiva': 1, 'migliore': None, 'stato': 'in_prova',
                       'versioni': [{'n': 1, 'dal': oggi, 'cosa': 'Stile di partenza del canale', 'leva': 'partenza', 'parametri': {}, 'risultati': None, 'decisione': None}],
                       'registro': [oggi[:10] + ': versione 1 di partenza creata in automatico (controllo delle metriche per ogni canale).']},
                      open(f, 'w'), ensure_ascii=False, indent=2)
            log(f'ricetta di partenza creata per {cid}')


def main():
    sch, h, canali = A.righe(A.CONFIGS)
    if E('PROVA') != 'SI':
        try:
            coach_per_tutti(sch, h, canali)
        except Exception as e:
            log('coach per tutti non riuscito:', str(e)[:150])
    for cfg in canali:
        if SOLO and str(cfg.get('channel_id') or '').strip() != SOLO:
            continue
        try:
            canale(cfg)
        except Exception as e:
            log('  ERRORE', cfg.get('channel_id'), str(e)[:200], (e.read().decode('utf-8', 'ignore')[:300] if hasattr(e, 'read') else ''))   # 7 nov: motivo del 403 nel registro
    os.makedirs('coach', exist_ok=True)
    json.dump(DATI_EXCEL, open('coach/performance_dati.json', 'w'), ensure_ascii=False, indent=1)
    open('coach/performance_ultimo.txt', 'w').write(dt.datetime.now().strftime('%Y-%m-%d %H:%M') + '\n' + '\n'.join(REPORT) + '\n')


if __name__ == '__main__':
    main()
