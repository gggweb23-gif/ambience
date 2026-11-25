#!/usr/bin/env python3
"""AVVIO GIORNALIERO dei canali che prima faceva partire n8n (ORCHESTRATORE + "MULTICHANNEL - GitHub Video"), tutto su GitHub.
Per ogni riga di Channel Configs con videos_per_day >= 1 e motore GitHub (github_workflow = video_produzione.yml, oppure
render_workflow = video_storia.yml / video_mappe.yml): prende la prima riga "Pronto" del file di produzione, la mette
"In produzione" e lancia il video con lo stesso payload che mandava n8n. A fine video il workflow scrive l'esito nel foglio
(strumenti/esito_foglio.py). I canali d'archivio (video_archivio.yml) restano su avvio_archivio.py.
Mai due video Pexels insieme: se un video Pexels e' gia' in lavorazione, gli altri canali Pexels aspettano il giro successivo."""
import datetime as dt, json, os, re, urllib.parse, urllib.request
from zoneinfo import ZoneInfo


def modelli_validi(nome):
    """21 nov (Giorgio): un gemello si fa SOLO da un nostro video che ha dimostrato di funzionare (sopra gemelli_min_views, 50.000 views).
    Titoli dei vincenti attuali del canale (coach/vincenti.json): le righe GEMELLO nate da video sotto soglia non si usano."""
    try:
        v = json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'coach', 'vincenti.json')))
        return {str(w.get('titolo') or '').strip() for w in (v.get(str(nome)) or {}).get('video') or []}
    except Exception:
        return set()
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import iscrizione as ISC
CONFIGS = os.environ.get('FOGLIO_CONFIGS', '1COMpgHJshcmz_a9s-WsjCO5xbhwxBazt-ZB0G_C7Rb0')
REPO = os.environ.get('GITHUB_REPOSITORY', 'gggweb23-gif/ambience')
PEXELS = {'video_produzione.yml', 'video_storia.yml', 'video_gloam.yml'}   # motori che usano Pexels (si lanciano uno alla volta; 9 nov: + Gloam / Billion Ruin)
PEXELS_IN_CORSO = PEXELS | {'video_kao.yml', 'video_agora.yml', 'filosofo.yml', 'kao_render.yml'}   # come WORKFLOW_PEXELS dei workflow
_TK = {}


def kao_pronto(prod, quota, nome=''):
    """15 nov (Giorgio, 50-50): KAO copia al 100%. I gemelli sono video di La Psicologia Invisible simili al nostro vincente (nome_canale = GEMELLO):
    se la quota dei gemelli negli ultimi 10 video e' sotto quota_gemelli si fa un gemello, altrimenti la prima riga Pronto normale."""
    pronte = [i for i, r in enumerate(prod) if str(r.get('status')).strip() == 'Pronto']
    validi = modelli_validi(nome)   # 21 nov: niente gemelli di video sotto 50.000 views
    scarta = [i for i in pronte if str(prod[i].get('nome_canale') or '').strip().upper() == 'GEMELLO' and str(prod[i].get('gemello_di') or '').strip() not in validi]
    pronte = [i for i in pronte if i not in scarta]
    gem = [i for i in pronte if str(prod[i].get('nome_canale') or '').strip().upper() == 'GEMELLO']
    fatti = [r for r in prod if str(r.get('status')).strip() in ('Completato', 'Da caricare a mano')][-10:]
    ora = (sum(1 for r in fatti if str(r.get('nome_canale') or '').strip().upper() == 'GEMELLO') / len(fatti) * 100) if fatti else 0
    if quota > 0 and gem and ora < quota:
        return gem[0]
    altre = [i for i in pronte if i not in gem]
    return altre[0] if altre else (gem[0] if quota > 0 and gem else None)


def primo_pronto(prod):
    """12 nov (Giorgio): se lo scout ha trovato un video del filone che sta funzionando da un competitor (riga con data_scoperta),
    si fa prima quello (solo gancio e struttura, testo nostro); altrimenti la prima riga Pronto (titoli creati da noi). KAO escluso: ha un solo competitor."""
    pronte = [i for i, r in enumerate(prod) if str(r.get('status')).strip() == 'Pronto']
    return next((i for i in pronte if str(prod[i].get('data_scoperta') or '').strip()), pronte[0] if pronte else None)


def token(scopes=('https://www.googleapis.com/auth/spreadsheets',)):
    import time as _t
    if scopes not in _TK or _t.time() - _TK[scopes][1] > 45 * 60:   # 7 nov: il token dura 1 ora, i lavori lunghi (Short) lo superavano (401)
        from google.oauth2 import service_account
        from google.auth.transport.requests import Request
        cr = service_account.Credentials.from_service_account_info(json.loads(os.environ['GOOGLE_SA_KEY']), scopes=list(scopes))
        cr.refresh(Request()); _TK[scopes] = (cr.token, _t.time())
    return _TK[scopes][0]


def api(foglio, metodo, percorso, corpo=None):
    req = urllib.request.Request('https://sheets.googleapis.com/v4/spreadsheets/' + foglio + percorso, data=json.dumps(corpo).encode() if corpo is not None else None,
                                 method=metodo, headers={'Authorization': 'Bearer ' + token(), 'Content-Type': 'application/json'})
    return json.loads(urllib.request.urlopen(req, timeout=60).read() or b'{}')


def righe(foglio, con_gid=False):
    tutte = api(foglio, 'GET', '?fields=sheets.properties')['sheets']
    pr = next((x['properties'] for x in tutte if not x['properties']['title'].startswith('Performance')), tutte[0]['properties'])   # mai le schede Performance
    v = api(foglio, 'GET', '/values/' + urllib.parse.quote(f"'{pr['title']}'!A1:AZZ3000")).get('values', [])
    h = [str(x).strip() for x in v[0]]
    rr = [dict(zip(h, r + [''] * (len(h) - len(r)))) for r in v[1:]]
    return (pr['title'], h, rr, pr.get('sheetId')) if con_gid else (pr['title'], h, rr)


def puo_scrivere(fid):
    try:
        u = f'https://www.googleapis.com/drive/v3/files/{fid}?fields=capabilities(canEdit)&supportsAllDrives=true'
        r = urllib.request.urlopen(urllib.request.Request(u, headers={'Authorization': 'Bearer ' + token(('https://www.googleapis.com/auth/drive.metadata.readonly',))}), timeout=60)
        return json.loads(r.read())['capabilities']['canEdit']
    except Exception as e:
        return 'non verificabile (' + str(e)[:60] + ')'


def lettera(n):
    s = ''
    while n:
        n, r = divmod(n - 1, 26); s = chr(65 + r) + s
    return s


def num(x):
    try:
        return float(str(x).replace(',', '.'))
    except Exception:
        return 0.0


def motore(cfg):
    rw, gw = str(cfg.get('render_workflow') or '').strip(), str(cfg.get('github_workflow') or '').strip()
    if rw == 'video_archivio.yml':
        return None   # avvio_archivio.py
    if gw == 'video_produzione.yml':
        return 'video_produzione.yml'
    if rw in ('video_storia.yml', 'video_mappe.yml', 'video_cartoni.yml', 'video_gloam.yml', 'video_possesso.yml'):   # 7 nov: video_cartoni.yml = cartoni + grafici in codice (Quanto Ti Resta); 9 nov: video_gloam.yml (Billion Ruin), video_possesso.yml (Costo Vero)
        return rw
    return None


def gh(metodo, percorso, corpo=None):
    req = urllib.request.Request('https://api.github.com/repos/' + REPO + percorso, data=json.dumps(corpo).encode() if corpo is not None else None, method=metodo,
                                 headers={'Authorization': 'Bearer ' + os.environ['GH_TOKEN'], 'Accept': 'application/vnd.github+json'})
    return json.loads(urllib.request.urlopen(req, timeout=60).read() or b'{}')


def pexels_in_corso():
    escludi = str(os.environ.get('ESCLUDI_RUN') or '').strip()   # il video Pexels che ha appena finito e ha lanciato questo avvio
    n = 0
    for wf in PEXELS_IN_CORSO:
        for st in ('in_progress', 'queued'):
            n += sum(1 for r in gh('GET', f'/actions/workflows/{wf}/runs?status={st}&per_page=50').get('workflow_runs', []) if str(r.get('id')) != escludi)
    return n


ANTICIPO = int(float(os.environ.get('ANTICIPO_GIORNI', '') or 0))   # video in anticipo (6 nov, Giorgio): esce tra N giorni


def nel_filone(cfg, r):
    """9 nov (Giorgio): entra in produzione SOLO un video del filone del canale (colonna scout_filone). Claude Haiku legge il titolo
    (meno di 0,001 $). Senza filone o senza chiave: si va avanti come prima."""
    if str(cfg.get('channel_id') or '').strip().upper().startswith('KAO'):   # regola filone esclusa per KAO (Giorgio, 2 nov)
        return True
    fil = str(cfg.get('scout_filone') or '').strip(); key = os.environ.get('ANTHROPIC_API_KEY', '')
    tit = str(r.get('titolo_originale') or r.get('titolo_italiano') or '').strip()
    if not fil or not key or not tit:
        return True
    try:
        req = urllib.request.Request('https://api.anthropic.com/v1/messages', method='POST', data=json.dumps({
            'model': 'claude-haiku-4-5-20251001', 'max_tokens': 20, 'messages': [{'role': 'user', 'content':
            f'Channel topic (filone): {fil}\nVideo title: "{tit}"\nIs this video clearly about the SAME topic/filone of the channel? Answer only SI or NO.'}]}).encode(),
            headers={'x-api-key': key, 'anthropic-version': '2023-06-01', 'content-type': 'application/json'})
        t = ''.join(b.get('text', '') for b in json.loads(urllib.request.urlopen(req, timeout=60).read()).get('content', []))
        return not t.strip().upper().startswith('NO')
    except Exception as e:
        print('controllo filone non riuscito (vado avanti):', str(e)[:120]); return True


def gia_pronto(prod, quando):
    """C'e' gia' un video per quel giorno di uscita (es. fatto in anticipo)? Allora stanotte non se ne fa un altro."""
    g = quando[:10]
    return any(str(r.get('status')).strip() in ('Completato', 'Da caricare a mano', 'In produzione') and str(r.get('data_pubblicazione') or '').strip()[:10] == g for r in prod)


FORZA = os.environ.get('FORZA', '').strip().upper() == 'SI'   # 10 nov: lancio a mano anche se oggi c'e' gia' stata una prova


def pubblica_il(cfg, ora):
    m = re.match(r'(\d{1,2})[:.](\d{2})', str(cfg.get('publish_time') or '17:00'))
    tz = ZoneInfo('Europe/Rome'); loc = ora.astimezone(tz) + dt.timedelta(days=ANTICIPO)
    q = loc.replace(hour=int(m.group(1)) if m else 17, minute=int(m.group(2)) if m else 0, second=0, microsecond=0)
    # come faceva n8n: oggi all'ora del foglio; se il video finisce dopo quell'ora, il motore lo pubblica subito
    return q.astimezone(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')


def main():
    _, _, canali = righe(CONFIGS)
    ora = dt.datetime.now(dt.timezone.utc)
    SOLO = os.environ.get('SOLO_CANALE', '').strip()
    pex = pexels_in_corso()
    print('video Pexels gia\' in lavorazione:', pex)
    for cfg in canali:
        cid = str(cfg.get('channel_id') or '').strip()
        wf = motore(cfg)
        if not cid or not wf or num(cfg.get('videos_per_day')) < 1 or (SOLO and cid != SOLO):
            continue
        # 21 nov (Giorgio): video ogni N giorni (colonna ogni_quanti_giorni: KAO 3, gli altri 2; vuota = ogni giorno)
        ogni = int(num(cfg.get('ogni_quanti_giorni')) or 1)
        fid = str(cfg.get('scout_production_sheet_id') or '').strip()
        try:
            sch, h, prod, gid = righe(fid, con_gid=True)
        except Exception as e:
            print(cid, ': file di produzione non leggibile', str(e)[:120]); continue
        occupata = False
        for r in prod:
            if str(r.get('status')).strip() == 'In produzione':
                try:
                    ini = dt.datetime.fromisoformat(str(r.get('data_inizio_produzione')).strip().replace('Z', '+00:00').replace(' ', 'T'))
                    ini = ini if ini.tzinfo else ini.replace(tzinfo=ZoneInfo('Europe/Rome'))
                    occupata = occupata or (ora - ini).total_seconds() < num(cfg.get('production_timeout_hours') or 6) * 3600
                except Exception:
                    pass
        if occupata:
            print(cid, ': un video e\' gia\' in produzione'); continue
        # 25 nov (Giorgio): "uno ogni N giorni" si conta dall'ULTIMO video fatto (non dal calendario pari/dispari):
        # se un video esce un giorno fuori turno, il successivo arriva N giorni dopo quello.
        if ogni > 1 and not SOLO and not FORZA:
            ultimo = None
            for r in prod:
                if str(r.get('status')).strip() not in ('Completato', 'In produzione', 'Da caricare a mano'):
                    continue
                try:
                    ini = dt.datetime.fromisoformat(str(r.get('data_inizio_produzione')).strip().replace('Z', '+00:00').replace(' ', 'T'))
                    ini = (ini if ini.tzinfo else ini.replace(tzinfo=ZoneInfo('Europe/Rome'))).astimezone(ZoneInfo('Europe/Rome')).date()
                    ultimo = max(ultimo, ini) if ultimo else ini
                except Exception:
                    pass
            oggi_r = dt.datetime.now(ZoneInfo('Europe/Rome')).date()
            if ultimo and (oggi_r - ultimo).days < ogni:
                print(cid, f': oggi niente video (uno ogni {ogni} giorni, ultimo il {ultimo})'); continue
        # quanti video di questo canale sono gia' partiti OGGI (ora italiana): mai piu' di videos_per_day al giorno
        oggi = ora.astimezone(ZoneInfo('Europe/Rome')).date(); fatti_oggi = tentativi_oggi = 0
        for r in prod:
            try:
                ini = dt.datetime.fromisoformat(str(r.get('data_inizio_produzione')).strip().replace('Z', '+00:00').replace(' ', 'T'))
                ini = ini if ini.tzinfo else ini.replace(tzinfo=ZoneInfo('Europe/Rome'))
            except Exception:
                continue
            if ini.astimezone(ZoneInfo('Europe/Rome')).date() == oggi:
                tentativi_oggi += 1
                fatti_oggi += str(r.get('status')).strip() in ('Completato', 'In produzione', 'Prova', 'Da caricare a mano')
        uscita = dt.datetime.fromisoformat(pubblica_il(cfg, ora).replace('Z', '+00:00')).astimezone(ZoneInfo('Europe/Rome')).strftime('%Y-%m-%d %H:%M')
        RIFAI_RIGA = int(num(os.environ.get('RIFAI_RIGA') or 0) or 0) if SOLO else 0   # 15 nov: rifare il video di una riga gia' fatta (con COPIONE_DA = stesso copione)
        if gia_pronto(prod, uscita) and not RIFAI_RIGA:
            print(cid, ': video per il', uscita[:10], 'gia\' pronto'); continue
        if fatti_oggi >= num(cfg.get('videos_per_day')) and not ANTICIPO and not FORZA and not RIFAI_RIGA:
            print(cid, ': video di oggi gia\' fatto'); continue
        if tentativi_oggi >= num(cfg.get('videos_per_day')) + 2 and not ANTICIPO and not FORZA and not RIFAI_RIGA:
            print(cid, ': troppi tentativi falliti oggi, si riprova domani'); continue
        try:   # 9 nov (Giorgio): se i titoli stanno finendo se ne aggiungono altri dello stesso filone (colonna titoli_auto = SI)
            import rifornisci_titoli as RT
            if RT.rifornisci(cfg, fid, sys.modules[__name__]):
                sch, h, prod, gid = righe(fid, con_gid=True)
        except Exception as e:
            print(cid, ': rifornimento titoli non riuscito', str(e)[:150])
        k = primo_pronto(prod) if not cid.upper().startswith('KAO') else kao_pronto(prod, num(cfg.get('quota_gemelli')), str(cfg.get('channel_name') or cid))
        while k is not None and not nel_filone(cfg, prod[k]):   # 9 nov: fuori filone -> Scartato, si passa alla riga dopo
            print(cid, ': FUORI FILONE, scartato:', prod[k].get('titolo_originale'))
            api(fid, 'POST', '/values:batchUpdate', {'valueInputOption': 'RAW', 'data': [{'range': f"'{sch}'!{lettera(h.index('status') + 1)}{k + 2}", 'values': [['Scartato (fuori filone)']]}]})
            prod[k]['status'] = 'Scartato (fuori filone)'
            k = primo_pronto(prod) if not cid.upper().startswith('KAO') else kao_pronto(prod, num(cfg.get('quota_gemelli')), str(cfg.get('channel_name') or cid))
        if k is None:
            print(cid, ': nessuna riga Pronto'); continue
        if RIFAI_RIGA:
            k = RIFAI_RIGA - 2; print(cid, ': RIFACCIO la riga', RIFAI_RIGA, '-', prod[k].get('titolo_italiano') or prod[k].get('titolo_originale'))
        if wf in PEXELS and pex:
            print(cid, ': aspetta il prossimo giro (un altro video Pexels e\' in lavorazione)'); continue
        r = prod[k]; n = k + 2; link = str(r.get('Link video') or '').strip()
        dati = [{'range': f"'{sch}'!{lettera(h.index('status') + 1)}{n}", 'values': [['In produzione']]}]
        if 'data_inizio_produzione' in h:
            dati.append({'range': f"'{sch}'!{lettera(h.index('data_inizio_produzione') + 1)}{n}", 'values': [[ora.isoformat(timespec='seconds')]]})
        if ANTICIPO and 'data_pubblicazione' in h:
            dati.append({'range': f"'{sch}'!{lettera(h.index('data_pubblicazione') + 1)}{n}", 'values': [[uscita]]})
        api(fid, 'POST', '/values:batchUpdate', {'valueInputOption': 'RAW', 'data': dati})
        P = {k_: v for k_, v in cfg.items() if not re.search(r'token|secret|password|api_key', k_, re.I)}
        if wf == 'video_storia.yml':
            P.pop('callback_url', None)   # n8n Storia non risponde piu': 3 tentativi = 7 minuti persi a fine video
        riga = {'row_number': n, **{k_: v for k_, v in r.items() if str(v).strip() != ''}}
        fatti = [f"{x.get('paese')} = {x.get('Link video')}" for x in prod if str(x.get('paese') or '').strip() and str(x.get('youtube_video_id') or '').strip()]
        isc = ISC.impostazioni(cfg)   # 6 nov (Giorgio): pulsante con i suoni su tutti i video; colonne vuote = quelli standard nella lingua del canale
        P.update({'iscrizione': {'img': isc['img'], 'sec': cfg.get('subscribe_overlay_second') or '',
                                 'clic': isc['clic'], 'clic_ritardo': '',
                                 'campana': isc['campana'], 'campana_ritardo': ''},
                  'id': link, 'foglio': fid, 'gid': str(gid), 'link': link, 'canale': cid, 'pubblica_il': pubblica_il(cfg, ora), 'prova': 'NO',
                  'titolo_originale': r.get('titolo_originale') or '', 'paesi_fatti': fatti, 'riga': riga,
                  'categoria_originale': str(r.get('competitor_category_id') or '').replace('.0', ''),
                  'riga_produzione': n, 'foglio_produzione': fid})
        if RIFAI_RIGA and os.environ.get('COPIONE_DA', '').strip():
            P['copione_da'] = os.environ['COPIONE_DA'].strip()
        if os.environ.get('PRIVACY', '').strip():   # 10 nov (Giorgio): video da guardare prima, es. unlisted = NON IN ELENCO, li pubblica lui
            P['privacy'] = os.environ['PRIVACY'].strip(); P['pubblica_il'] = ''
        inputs = {'link_competitor': link, 'prova': 'NO', 'carica': str(cfg.get('carica') or 'SI').strip().upper() or 'SI',
                  'voce': str(cfg.get('voice_id') or ''), 'payload': json.dumps(P, ensure_ascii=False)}
        gh('POST', f'/actions/workflows/{wf}/dispatches', {'ref': 'main', 'inputs': inputs})
        if wf in PEXELS:
            pex += 1
        print(cid, ': lanciato', wf, '|', r.get('titolo_originale'), '(riga', n, ') | esce', P['pubblica_il'])


if __name__ == '__main__':
    main()
