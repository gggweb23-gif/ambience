#!/usr/bin/env python3
"""SCRITTURA SU CHANNEL CONFIGS (Google Sheets API, account di servizio) con LUCCHETTI.
Lucchetti (decisi da Giorgio il 30 ott 2026), controllati qui E con gli intervalli protetti del foglio:
- la riga di KAO PSICOLOGIA non si tocca mai;
- le colonne videos_per_day (canale acceso/spento) e publish_schedule_days non si toccano mai;
- le colonne dei parametri di Giorgio (coach_*, durata_min_minuti, durata_max_minuti) si possono solo COMPILARE se vuote.
PAYLOAD = {"modifiche": [{"canale": "Agora of Sages", "colonna": "render_engine", "valore": "github_completo"}, ...],
           "nuove_colonne": ["coach_auto", ...], "prova": "SI" (solo controllo, non scrive)}
Segreto: GOOGLE_SA_KEY (JSON dell'account di servizio, con il foglio condiviso in modifica con la sua email)."""
import json, os, sys, time, urllib.parse, urllib.request

FOGLIO = os.environ.get('FOGLIO_CONFIGS', '1COMpgHJshcmz_a9s-WsjCO5xbhwxBazt-ZB0G_C7Rb0')
RIGHE_BLOCCATE = {'KAO PSICOLOGIA'}
COLONNE_BLOCCATE = {'channel_id', 'videos_per_day', 'publish_schedule_days'}
SOLO_SE_VUOTE = {'coach_auto', 'coach_obiettivo_ctr', 'coach_obiettivo_ret30', 'coach_obiettivo_ret60', 'coach_finestra_video',
                 'coach_min_impression', 'coach_budget_video', 'durata_min_minuti', 'durata_max_minuti'}


def token():
    from google.oauth2 import service_account
    from google.auth.transport.requests import Request
    cr = service_account.Credentials.from_service_account_info(json.loads(os.environ['GOOGLE_SA_KEY']),
                                                               scopes=['https://www.googleapis.com/auth/spreadsheets'])
    cr.refresh(Request())
    return cr.token


def api(metodo, percorso, corpo=None, tk=None):
    req = urllib.request.Request('https://sheets.googleapis.com/v4/spreadsheets/' + FOGLIO + percorso,
                                 data=json.dumps(corpo).encode() if corpo is not None else None, method=metodo,
                                 headers={'Authorization': 'Bearer ' + tk, 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode() or '{}')


def lettera(n):   # 1 -> A
    s = ''
    while n:
        n, r = divmod(n - 1, 26); s = chr(65 + r) + s
    return s


def main():
    P = json.loads(os.environ.get('PAYLOAD') or '{}')
    tk = token()
    meta = api('GET', '?fields=sheets.properties', tk=tk)
    scheda = meta['sheets'][0]['properties']['title']
    rng = lambda a: '/values/' + urllib.parse.quote(f"'{scheda}'!{a}")
    valori = api('GET', rng('A1:AZZ200'), tk=tk).get('values', [])
    intest = [str(x).strip() for x in valori[0]]
    esito = []
    nuove = [c for c in P.get('nuove_colonne', []) if c not in intest]
    if nuove:
        da = len(intest) + 1
        if P.get('prova') != 'SI':
            api('PUT', rng(f'{lettera(da)}1') + '?valueInputOption=RAW', {'values': [nuove]}, tk)
        intest += nuove
        esito.append(f'colonne nuove: {", ".join(nuove)} (da {lettera(da)})')
    righe = {str(r[0]).strip(): i + 1 for i, r in enumerate(valori) if r and i > 0}
    dati = []
    for m in P.get('modifiche', []):
        can, col, val = str(m['canale']).strip(), str(m['colonna']).strip(), m['valore']
        if can in RIGHE_BLOCCATE:
            esito.append(f'BLOCCATO: la riga {can} non si tocca'); continue
        if col in COLONNE_BLOCCATE:
            esito.append(f'BLOCCATO: la colonna {col} la decide solo Giorgio'); continue
        if can not in righe:
            esito.append(f'canale non trovato: {can}'); continue
        if col not in intest:
            esito.append(f'colonna non trovata: {col}'); continue
        r, c = righe[can], intest.index(col) + 1
        attuale = (valori[r - 1][c - 1] if r - 1 < len(valori) and c - 1 < len(valori[r - 1]) else '')
        if col in SOLO_SE_VUOTE and str(attuale).strip() != '':
            esito.append(f'BLOCCATO: {col} di {can} e\' gia\' compilata ({attuale}): la cambia solo Giorgio'); continue
        dati.append({'range': f"'{scheda}'!{lettera(c)}{r}", 'values': [[val]]})
        esito.append(f'{can} | {col} ({lettera(c)}{r}): "{attuale}" -> "{val}"')
    if dati and P.get('prova') != 'SI':
        api('POST', '/values:batchUpdate', {'valueInputOption': 'USER_ENTERED', 'data': dati}, tk)
    print('\n'.join(esito) or 'niente da fare')
    os.makedirs('coach', exist_ok=True)
    with open('coach/modifiche_foglio.log', 'a') as f:
        f.write(time.strftime('%Y-%m-%d %H:%M') + (' [PROVA]' if P.get('prova') == 'SI' else '') + '\n' + '\n'.join('  ' + e for e in esito) + '\n')


if __name__ == '__main__':
    main()
