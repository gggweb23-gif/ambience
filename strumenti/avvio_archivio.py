#!/usr/bin/env python3
"""AVVIO GIORNALIERO dei canali fatti con archivi gratuiti (motore video_archivio.yml), per tutti i canali.
Ogni giorno, per ogni riga di Channel Configs con render_workflow = video_archivio.yml e videos_per_day >= 1 (lo decide Giorgio):
prende la prima riga "Pronto" del file di produzione (scout_production_sheet_id), la mette "In produzione" e lancia il video.
Se una riga e' gia' "In produzione" da meno di production_timeout_hours (default 4) non lancia niente (mai due video insieme)."""
import datetime as dt, json, os, re, urllib.parse, urllib.request
CONFIGS = os.environ.get('FOGLIO_CONFIGS', '1COMpgHJshcmz_a9s-WsjCO5xbhwxBazt-ZB0G_C7Rb0')
REPO = os.environ.get('GITHUB_REPOSITORY', 'gggweb23-gif/ambience')


def token():
    from google.oauth2 import service_account
    from google.auth.transport.requests import Request
    cr = service_account.Credentials.from_service_account_info(json.loads(os.environ['GOOGLE_SA_KEY']), scopes=['https://www.googleapis.com/auth/spreadsheets'])
    cr.refresh(Request()); return cr.token


TK = token()


def api(foglio, metodo, percorso, corpo=None):
    req = urllib.request.Request('https://sheets.googleapis.com/v4/spreadsheets/' + foglio + percorso, data=json.dumps(corpo).encode() if corpo is not None else None,
                                 method=metodo, headers={'Authorization': 'Bearer ' + TK, 'Content-Type': 'application/json'})
    return json.loads(urllib.request.urlopen(req, timeout=60).read() or b'{}')


def righe(foglio):
    sch = api(foglio, 'GET', '?fields=sheets.properties')['sheets'][0]['properties']['title']
    v = api(foglio, 'GET', '/values/' + urllib.parse.quote(f"'{sch}'!A1:AZZ2000")).get('values', [])
    h = [str(x).strip() for x in v[0]]
    return sch, h, [dict(zip(h, r + [''] * (len(h) - len(r)))) for r in v[1:]]


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


_, _, canali = righe(CONFIGS)
ora = dt.datetime.now(dt.timezone.utc)
SOLO = os.environ.get('SOLO_CANALE', '').strip()          # lancio a mano di un solo canale (es. primo video di un canale nuovo)
PRIVACY = os.environ.get('PRIVACY_FORZATA', '').strip()   # es. unlisted per il primo video da controllare
for cfg in canali:
    if str(cfg.get('render_workflow') or '').strip() != 'video_archivio.yml' or num(cfg.get('videos_per_day')) < 1:
        continue
    if SOLO and str(cfg.get('channel_id')).strip() != SOLO:
        continue
    if PRIVACY:
        cfg = dict(cfg, privacy=PRIVACY)
    fid = str(cfg.get('scout_production_sheet_id') or '').strip()
    sch, h, prod = righe(fid)
    occupata = False
    for r in prod:
        if str(r.get('status')).strip() == 'In produzione':
            try:
                ini = dt.datetime.fromisoformat(str(r.get('data_inizio_produzione')).replace('Z', '+00:00'))
                ini = ini if ini.tzinfo else ini.replace(tzinfo=dt.timezone.utc)
                occupata = occupata or (ora - ini).total_seconds() < num(cfg.get('production_timeout_hours') or 4) * 3600
            except Exception:
                pass
    if occupata:
        print(cfg['channel_id'], ': un video e\' gia\' in produzione, oggi niente'); continue
    k = next((i for i, r in enumerate(prod) if str(r.get('status')).strip() == 'Pronto'), None)
    if k is None:
        print(cfg['channel_id'], ': nessuna riga Pronto'); continue
    r = prod[k]; n = k + 2
    api(fid, 'POST', '/values:batchUpdate', {'valueInputOption': 'RAW', 'data': [
        {'range': f"'{sch}'!{lettera(h.index('status') + 1)}{n}", 'values': [['In produzione']]},
        {'range': f"'{sch}'!{lettera(h.index('data_inizio_produzione') + 1)}{n}", 'values': [[ora.isoformat(timespec='seconds')]]}]})
    payload = {k_: v for k_, v in cfg.items() if v not in ('', None) and not re.search(r'token|secret|password|api_key', k_, re.I)}
    titolo = r.get('titolo_italiano') or r.get('titolo_originale')
    payload.update({'titolo': titolo, 'testo_copertina': r.get('titolo_thumbnail') or '', 'link_competitor': r.get('Link video') or '',
                    'nome': re.sub(r'[^a-z0-9]+', '_', (cfg['channel_id'] + '_' + titolo).lower())[:60], 'foglio_produzione': fid, 'riga_produzione': n})
    req = urllib.request.Request(f'https://api.github.com/repos/{REPO}/actions/workflows/video_archivio.yml/dispatches',
                                 data=json.dumps({'ref': 'main', 'inputs': {'payload': json.dumps(payload, ensure_ascii=False)}}).encode(),
                                 headers={'Authorization': 'Bearer ' + os.environ['GH_TOKEN'], 'Accept': 'application/vnd.github+json'})
    urllib.request.urlopen(req, timeout=60)
    print(cfg['channel_id'], ': lanciato', titolo, '(riga', n, ')')
