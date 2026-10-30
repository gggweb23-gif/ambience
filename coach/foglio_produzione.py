#!/usr/bin/env python3
"""SCRITTURA SUI FILE DI PRODUZIONE dei canali (stesso account di servizio di foglio_configs.py).
Il file si trova dalla colonna scout_production_sheet_id di Channel Configs. LUCCHETTO: mai il canale KAO PSICOLOGIA.
PAYLOAD = {"canale": "Agora of Sages", "link": "https://www.youtube.com/watch?v=...", "valori": {"status": "In produzione",
           "data_inizio_produzione": "2026-10-30 19:45:00"}, "prova": "SI"|"NO"}"""
import json, os, sys, time, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import foglio_configs as FC

CANALI_BLOCCATI = {'KAO PSICOLOGIA'}


def main():
    P = json.loads(os.environ.get('PAYLOAD') or '{}')
    can = str(P['canale']).strip()
    if can in CANALI_BLOCCATI:
        print('BLOCCATO: il canale ' + can + ' non si tocca'); return
    tk = FC.token()
    meta = FC.api('GET', '?fields=sheets.properties', tk=tk)
    sch = meta['sheets'][0]['properties']['title']
    cfg = FC.api('GET', '/values/' + urllib.parse.quote(f"'{sch}'!A1:AZZ200"), tk=tk).get('values', [])
    h = [str(x).strip() for x in cfg[0]]
    riga = next((r for r in cfg[1:] if r and str(r[0]).strip() == can), None)
    if not riga:
        raise SystemExit('canale non trovato: ' + can)
    sid = riga[h.index('scout_production_sheet_id')]
    FC.FOGLIO = sid
    meta = FC.api('GET', '?fields=sheets.properties', tk=tk)
    sch = meta['sheets'][0]['properties']['title']
    val = FC.api('GET', '/values/' + urllib.parse.quote(f"'{sch}'!A1:AZ500"), tk=tk).get('values', [])
    ph = [str(x).strip() for x in val[0]]
    il = ph.index('Link video')
    n = next((i + 1 for i, r in enumerate(val) if i and len(r) > il and str(r[il]).strip() == str(P['link']).strip()), None)
    if not n:
        raise SystemExit('riga non trovata: ' + P['link'])
    dati, esito = [], []
    for col, v in P.get('valori', {}).items():
        if col not in ph:
            esito.append('colonna non trovata: ' + col); continue
        dati.append({'range': f"'{sch}'!{FC.lettera(ph.index(col) + 1)}{n}", 'values': [[v]]})
        esito.append(f'{can} riga {n} | {col} -> {v}')
    if dati and P.get('prova') != 'SI':
        FC.api('POST', '/values:batchUpdate', {'valueInputOption': 'USER_ENTERED', 'data': dati}, tk)
    print('\n'.join(esito))
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'modifiche_foglio.log'), 'a') as f:
        f.write(time.strftime('%Y-%m-%d %H:%M') + ' [produzione]' + (' [PROVA]' if P.get('prova') == 'SI' else '') + '\n' + '\n'.join('  ' + e for e in esito) + '\n')


if __name__ == '__main__':
    main()
