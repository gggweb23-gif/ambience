#!/usr/bin/env python3
"""SCRITTURA SU CHANNEL CONFIGS (Google Sheets API, account di servizio) con LUCCHETTI.
Lucchetti (decisi da Giorgio il 30 ott 2026), controllati qui E con gli intervalli protetti del foglio:
- la riga di KAO PSICOLOGIA non si tocca mai;
- le colonne videos_per_day (canale acceso/spento) e publish_schedule_days non si toccano mai;
- nessuna colonna di budget (budget_video, coach_budget_video) si tocca mai;
- le colonne dei parametri di Giorgio (coach_*, durata_min_minuti, durata_max_minuti) si possono solo COMPILARE se vuote.
PAYLOAD = {"nuova_riga": {"channel_id": "...", "copia_da": "Orbital Days" (facoltativo), "valori": {...}} (canale nuovo, mai colonne bloccate),
           "modifiche": [{"canale": "Agora of Sages", "colonna": "render_engine", "valore": "github_completo"}, ...],
           "nuove_colonne": ["coach_auto", ...], "prova": "SI" (solo controllo, non scrive)}
Segreto: GOOGLE_SA_KEY (JSON dell'account di servizio, con il foglio condiviso in modifica con la sua email)."""
import json, os, re, sys, time, urllib.parse, urllib.request

FOGLIO = os.environ.get('FOGLIO_CONFIGS', '1COMpgHJshcmz_a9s-WsjCO5xbhwxBazt-ZB0G_C7Rb0')
RIGHE_BLOCCATE = {'KAO PSICOLOGIA'}
COLONNE_BLOCCATE = {'channel_id', 'videos_per_day', 'publish_schedule_days'}
SOLO_SE_VUOTE = {'coach_auto', 'coach_obiettivo_ctr', 'coach_obiettivo_ret30', 'coach_obiettivo_ret60', 'coach_finestra_video',
                 'coach_min_impression', 'durata_min_minuti', 'durata_max_minuti'}


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


def riga_produzione(R, tk):
    """File di produzione di un canale: aggiorna UNA riga solo se il titolo corrisponde (mai budget o colonne protette).
    {"riga_produzione": {"foglio": "<id>", "riga": 2, "titolo": "...", "valori": {"status": "Completato", ...}}}"""
    global FOGLIO
    vecchio, FOGLIO = FOGLIO, R['foglio']
    try:
        sch = api('GET', '?fields=sheets.properties', tk=tk)['sheets'][0]['properties']['title']
        val = api('GET', '/values/' + urllib.parse.quote(f"'{sch}'!A1:AZ200"), tk=tk).get('values', [])
        h, n = [str(x).strip() for x in val[0]], int(R['riga'])
        riga = val[n - 1] if n - 1 < len(val) else []
        if str(R.get('titolo') or '').strip().lower() not in ' | '.join(str(x) for x in riga).lower():
            return f'riga {n} NON aggiornata: il titolo non corrisponde'
        vv = dict(R.get('valori') or {})
        if 'titolo_nostro' in vv:   # il NOSTRO titolo va nella colonna che il motore legge (titolo_italiano, altrimenti titolo_originale)
            vv['titolo_italiano' if 'titolo_italiano' in h else 'titolo_originale'] = vv.pop('titolo_nostro')
        R['valori'] = vv
        dati = [{'range': f"'{sch}'!{lettera(h.index(k) + 1)}{n}", 'values': [[v]]} for k, v in vv.items()
                if k in h and not re.search(r'budget', k, re.I)]
        try:
            api('POST', '/values:batchUpdate', {'valueInputOption': 'USER_ENTERED', 'data': dati}, tk)
        except Exception as e:   # riga oltre la fine della griglia del foglio: si aggiunge in fondo (righe nuove)
            if n - 1 < len(val) and any(str(x).strip() for x in riga):
                raise
            nuova = [''] * len(h)
            for k, v in vv.items():
                if k in h and not re.search(r'budget', k, re.I):
                    nuova[h.index(k)] = v
            api('POST', '/values/' + urllib.parse.quote(f"'{sch}'!A1") + ':append?valueInputOption=USER_ENTERED&insertDataOption=INSERT_ROWS', {'values': [nuova]}, tk)
            return 'file di produzione, riga AGGIUNTA in fondo: ' + ', '.join(f'{k}={v}' for k, v in vv.items() if k in h)
        return f'file di produzione, riga {n}: ' + ', '.join(f'{k}={v}' for k, v in (R.get('valori') or {}).items() if k in h)
    finally:
        FOGLIO = vecchio


def main():
    global FOGLIO
    P = json.loads(os.environ.get('PAYLOAD') or '{}')
    tk = token()
    if P.get('leggi_scheda'):   # 9 nov: sola lettura di una scheda qualsiasi (es. Performance) -> stampata nel registro del giro
        vecchio, FOGLIO = FOGLIO, P['leggi_scheda']['foglio']
        val = api('GET', '/values/' + urllib.parse.quote(f"'{P['leggi_scheda'].get('scheda') or 'Performance'}'!A1:Z300"), tk=tk).get('values', [])
        FOGLIO = vecchio
        print('\n'.join(' | '.join(str(x) for x in r) for r in val)); return
    if P.get('leggi_produzione'):   # sola lettura: titolo, testo copertina e stato di ogni riga del file di produzione
        vecchio, FOGLIO = FOGLIO, P['leggi_produzione']
        sch = api('GET', '?fields=sheets.properties', tk=tk)['sheets'][0]['properties']['title']
        val = api('GET', '/values/' + urllib.parse.quote(f"'{sch}'!A1:AZ200"), tk=tk).get('values', [])
        FOGLIO = vecchio
        h = [str(x).strip() for x in val[0]]
        col = lambda r, k: (r[h.index(k)] if k in h and h.index(k) < len(r) else '')
        out = [f"riga {i + 1} | {col(r, 'status')} | {col(r, 'titolo_italiano') or col(r, 'titolo_originale')} | {col(r, 'titolo_thumbnail')} | {col(r, 'youtube_video_id')}"
               for i, r in enumerate(val) if i > 0 and any(str(x).strip() for x in r)]
        with open('coach/modifiche_foglio.log', 'a') as f:
            f.write(time.strftime('%Y-%m-%d %H:%M') + ' LETTURA file di produzione\n' + '\n'.join(out) + '\n')
        print('\n'.join(out)); return
    if P.get('riga_produzione'):
        msg = '\n'.join(riga_produzione(R, tk) for R in (P['riga_produzione'] if isinstance(P['riga_produzione'], list) else [P['riga_produzione']])); print(msg)
        with open('coach/modifiche_foglio.log', 'a') as f:
            f.write(time.strftime('%Y-%m-%d %H:%M') + ' ' + msg + '\n')
        if not P.get('modifiche') and not P.get('nuove_colonne') and not P.get('nuova_riga') and not P.get('copia_celle') and not P.get('rinomina'):
            return
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
    nr = P.get('nuova_riga')   # {"channel_id": "...", "valori": {colonna: valore}}: canale NUOVO, riga in fondo
    if nr and str(nr.get('channel_id') or '').strip():
        can = str(nr['channel_id']).strip()
        if can in righe:
            esito.append(f'nuova riga NON creata: {can} esiste gia\' (riga {righe[can]})')
        else:
            vals = {}
            src = str(nr.get('copia_da') or '').strip()   # canale da cui partire: si copiano le sue celle compilate (mai KAO, mai budget o videos_per_day)
            if src and src not in RIGHE_BLOCCATE and src in righe:
                rs = valori[righe[src] - 1]
                vals = {intest[i]: x for i, x in enumerate(rs) if i < len(intest) and str(x).strip() != ''}
                esito.append(f'nuova riga partita da {src}: {len(vals)} celle copiate')
            elif src:
                esito.append(f'copia_da {src}: non usato (riga bloccata o inesistente)')
            vals.update(nr.get('valori') or {}); vals['channel_id'] = can
            vals = {k: x for k, x in vals.items() if str(x).strip() != '' or k in (nr.get('valori') or {})}
            vietate = [k for k in vals if k in ('videos_per_day', 'publish_schedule_days') or re.search(r'budget', k, re.I)]
            for k in vietate:
                vals.pop(k); esito.append(f'BLOCCATO: {k} la compila solo Giorgio')
            mancano = [k for k in vals if k not in intest]
            riga = [''] * len(intest)
            for k, x in vals.items():
                if k in intest:
                    riga[intest.index(k)] = x
            n = max(righe.values() or [1]) + 1
            while n <= len(valori) and any(str(c).strip() for c in valori[n - 1]):
                n += 1
            if P.get('prova') != 'SI':   # solo le celle compilate: le colonne protette del foglio (budget, videos_per_day...) non si toccano
                api('POST', '/values:batchUpdate', {'valueInputOption': 'USER_ENTERED', 'data': [
                    {'range': f"'{scheda}'!{lettera(intest.index(k) + 1)}{n}", 'values': [[x]]} for k, x in vals.items() if k in intest]}, tk)
            righe[can] = n
            esito.append(f'NUOVA RIGA {n}: {can} con {len(vals) - len(mancano)} colonne' + (f' (colonne inesistenti ignorate: {", ".join(mancano)})' if mancano else ''))
    for cc in P.get('copia_celle', []):   # {"da": "KAO PSICOLOGIA", "a": "Storia in Minuti", "colonna": "voice_id"}: si LEGGE da una riga (anche bloccata) e si scrive nell'altra
        try:
            v_ = valori[righe[str(cc['da']).strip()] - 1][intest.index(cc['colonna'])]
            P.setdefault('modifiche', []).append({'canale': cc['a'], 'colonna': cc['colonna'], 'valore': v_})
            esito.append(f"copiata {cc['colonna']} da {cc['da']} a {cc['a']}")
        except Exception as e:
            esito.append(f"copia non riuscita {cc}: {str(e)[:60]}")
    dati = []
    for rn in P.get('rinomina', []):   # 8 nov (Giorgio): {"da": "Main Street Atlas", "a": "Rich Borders"} cambia il channel_id, SOLO su sua richiesta esplicita
        da, a_ = str(rn.get('da') or '').strip(), str(rn.get('a') or '').strip()
        if P.get('richiesta_di_giorgio') != 'SI' or da in RIGHE_BLOCCATE or not a_ or da not in righe or a_ in righe:
            esito.append(f'rinomina NON fatta: {da} -> {a_} (serve richiesta di Giorgio, canale esistente e nome nuovo libero; mai KAO)'); continue
        r = righe.pop(da); righe[a_] = r
        dati.append({'range': f"'{scheda}'!{lettera(intest.index('channel_id') + 1)}{r}", 'values': [[a_]]})
        esito.append(f'RINOMINATO channel_id riga {r}: "{da}" -> "{a_}"')
    mods = []
    for m in P.get('modifiche', []):   # canale "*" = tutte le righe dei canali
        mods += [dict(m, canale=k) for k in righe] if str(m.get('canale')).strip() == '*' else [m]
    for m in mods:
        can, col, val = str(m['canale']).strip(), str(m['colonna']).strip(), m['valore']
        if can in RIGHE_BLOCCATE:
            esito.append(f'BLOCCATO: la riga {can} non si tocca'); continue
        if col in COLONNE_BLOCCATE or re.search(r'budget', col, re.I):
            esito.append(f'BLOCCATO: la colonna {col} la decide solo Giorgio'); continue
        if can not in righe:
            esito.append(f'canale non trovato: {can}'); continue
        if col not in intest:
            esito.append(f'colonna non trovata: {col}'); continue
        r, c = righe[can], intest.index(col) + 1
        attuale = (valori[r - 1][c - 1] if r - 1 < len(valori) and c - 1 < len(valori[r - 1]) else '')
        if col in SOLO_SE_VUOTE and str(attuale).strip() != '' and P.get('richiesta_di_giorgio') != 'SI':   # solo su richiesta esplicita di Giorgio
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
