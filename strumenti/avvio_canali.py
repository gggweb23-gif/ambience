#!/usr/bin/env python3
"""AVVIO GIORNALIERO dei canali che prima faceva partire n8n (ORCHESTRATORE + "MULTICHANNEL - GitHub Video"), tutto su GitHub.
Per ogni riga di Channel Configs con videos_per_day >= 1 e motore GitHub (github_workflow = video_produzione.yml, oppure
render_workflow = video_storia.yml / video_mappe.yml): prende la prima riga "Pronto" del file di produzione, la mette
"In produzione" e lancia il video con lo stesso payload che mandava n8n. A fine video il workflow scrive l'esito nel foglio
(strumenti/esito_foglio.py). I canali d'archivio (video_archivio.yml) restano su avvio_archivio.py.
Mai due video Pexels insieme: se un video Pexels e' gia' in lavorazione, gli altri canali Pexels aspettano il giro successivo."""
import datetime as dt, json, os, re, urllib.parse, urllib.request
from zoneinfo import ZoneInfo
CONFIGS = os.environ.get('FOGLIO_CONFIGS', '1COMpgHJshcmz_a9s-WsjCO5xbhwxBazt-ZB0G_C7Rb0')
REPO = os.environ.get('GITHUB_REPOSITORY', 'gggweb23-gif/ambience')
PEXELS = {'video_produzione.yml', 'video_storia.yml'}   # motori che usano Pexels (si lanciano uno alla volta)
PEXELS_IN_CORSO = PEXELS | {'video_kao.yml', 'video_agora.yml', 'filosofo.yml', 'kao_render.yml'}   # come WORKFLOW_PEXELS dei workflow
_TK = {}


def token(scopes=('https://www.googleapis.com/auth/spreadsheets',)):
    if scopes not in _TK:
        from google.oauth2 import service_account
        from google.auth.transport.requests import Request
        cr = service_account.Credentials.from_service_account_info(json.loads(os.environ['GOOGLE_SA_KEY']), scopes=list(scopes))
        cr.refresh(Request()); _TK[scopes] = cr.token
    return _TK[scopes]


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
    if rw in ('video_storia.yml', 'video_mappe.yml'):
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


def pubblica_il(cfg, ora):
    m = re.match(r'(\d{1,2})[:.](\d{2})', str(cfg.get('publish_time') or '17:00'))
    tz = ZoneInfo('Europe/Rome'); loc = ora.astimezone(tz)
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
                fatti_oggi += str(r.get('status')).strip() in ('Completato', 'In produzione', 'Prova')
        if fatti_oggi >= num(cfg.get('videos_per_day')):
            print(cid, ': video di oggi gia\' fatto'); continue
        if tentativi_oggi >= num(cfg.get('videos_per_day')) + 2:
            print(cid, ': troppi tentativi falliti oggi, si riprova domani'); continue
        k = next((i for i, r in enumerate(prod) if str(r.get('status')).strip() == 'Pronto'), None)
        if k is None:
            print(cid, ': nessuna riga Pronto'); continue
        if wf in PEXELS and pex:
            print(cid, ': aspetta il prossimo giro (un altro video Pexels e\' in lavorazione)'); continue
        r = prod[k]; n = k + 2; link = str(r.get('Link video') or '').strip()
        dati = [{'range': f"'{sch}'!{lettera(h.index('status') + 1)}{n}", 'values': [['In produzione']]}]
        if 'data_inizio_produzione' in h:
            dati.append({'range': f"'{sch}'!{lettera(h.index('data_inizio_produzione') + 1)}{n}", 'values': [[ora.isoformat(timespec='seconds')]]})
        api(fid, 'POST', '/values:batchUpdate', {'valueInputOption': 'RAW', 'data': dati})
        P = {k_: v for k_, v in cfg.items() if not re.search(r'token|secret|password|api_key', k_, re.I)}
        if wf == 'video_storia.yml':
            P.pop('callback_url', None)   # n8n Storia non risponde piu': 3 tentativi = 7 minuti persi a fine video
        riga = {'row_number': n, **{k_: v for k_, v in r.items() if str(v).strip() != ''}}
        fatti = [f"{x.get('paese')} = {x.get('Link video')}" for x in prod if str(x.get('paese') or '').strip() and str(x.get('youtube_video_id') or '').strip()]
        P.update({'iscrizione': {'img': cfg.get('subscribe_overlay_url') or '', 'sec': cfg.get('subscribe_overlay_second') or '',
                                 'clic': cfg.get('subscribe_overlay_sound_url') or '', 'clic_ritardo': '',
                                 'campana': cfg.get('subscribe_overlay_bell_url') or '', 'campana_ritardo': ''},
                  'id': link, 'foglio': fid, 'gid': str(gid), 'link': link, 'canale': cid, 'pubblica_il': pubblica_il(cfg, ora), 'prova': 'NO',
                  'titolo_originale': r.get('titolo_originale') or '', 'paesi_fatti': fatti, 'riga': riga,
                  'categoria_originale': str(r.get('competitor_category_id') or '').replace('.0', ''),
                  'riga_produzione': n, 'foglio_produzione': fid})
        inputs = {'link_competitor': link, 'prova': 'NO', 'carica': str(cfg.get('carica') or 'SI').strip().upper() or 'SI',
                  'voce': str(cfg.get('voice_id') or ''), 'payload': json.dumps(P, ensure_ascii=False)}
        gh('POST', f'/actions/workflows/{wf}/dispatches', {'ref': 'main', 'inputs': inputs})
        if wf in PEXELS:
            pex += 1
        print(cid, ': lanciato', wf, '|', r.get('titolo_originale'), '(riga', n, ') | esce', P['pubblica_il'])


if __name__ == '__main__':
    main()
