#!/usr/bin/env python3
"""FINE VIDEO -> FILE DI PRODUZIONE (al posto del workflow n8n "MULTICHANNEL - GitHub Video").
Legge l'esito che il motore ha scritto in esito_video.json (oppure ESITO dall'ambiente, es. RIMANDATO dal turno Pexels)
e aggiorna la riga del video nel file di produzione: stato, titolo, descrizione, tag, copertina, id YouTube, data di uscita, playlist.
Vale solo per i video lanciati da strumenti/avvio_canali.py (payload con foglio_produzione e riga_produzione, anche se la riga di
Channel Configs ha ancora un callback_url n8n: n8n non risponde piu' e la riga restava "In produzione", bloccando i giri successivi)."""
import datetime as dt, json, os, sys, urllib.parse
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import avvio_canali as A
import manuale as M

STATI = {'PUBBLICATO': 'Completato', 'CREATO': 'Completato', 'PROVA OK': 'Prova', 'ERRORE': 'Errore', 'DOPPIONE': 'Simile a Esistente', 'RIMANDATO': 'Pronto', 'SCARTATO': 'Scartato'}
CAMPI = {'titolo': 'titolo_italiano', 'descrizione': 'descrizione_youtube', 'tag': 'tag_seo', 'testo_copertina': 'titolo_thumbnail',
         'video_id': 'youtube_video_id', 'playlist': 'playlist', 'video_url': 'video_anteprima', 'copertina_url': 'thumbnail_anteprima', 'paese': 'paese'}


def main():
    P = json.loads(os.environ.get('PAYLOAD') or '{}')
    if not P.get('foglio_produzione') or (P.get('callback_url') and not P.get('riga_produzione')) or str(P.get('prova') or '').upper() == 'SI':
        print('video non lanciato da avvio_canali: niente da scrivere'); return
    if os.environ.get('ESITO'):
        esito = json.loads(os.environ['ESITO'])
    elif os.path.exists('esito_video.json'):
        esito = json.load(open('esito_video.json'))
    elif os.environ.get('STATO_JOB') == 'cancelled':   # giro annullato a mano: la riga torna Pronto
        esito = {'stato': 'RIMANDATO'}
    else:
        esito = {'stato': 'ERRORE', 'errore': 'il motore si e\' fermato senza esito (vedi il registro del workflow)'}
    fid, link = P['foglio_produzione'], str(P.get('link') or '').strip()
    sch, h, prod = A.righe(fid)
    n = next((i + 2 for i, r in enumerate(prod) if str(r.get('Link video') or '').strip() == link), None)
    if not n:
        raise SystemExit('riga non trovata nel file di produzione: ' + link)
    stato = str(esito.get('stato') or 'ERRORE').upper()
    if stato == 'SPOSTA':   # 7 nov: cambia solo il giorno di uscita della riga (es. due video pronti in ordine inverso), lo stato resta
        A.api(fid, 'POST', '/values:batchUpdate', {'valueInputOption': 'RAW', 'data': [
            {'range': f"'{sch}'!{A.lettera(h.index('data_pubblicazione') + 1)}{n}", 'values': [[str(esito['data'])]]}]})
        print(P.get('canale'), 'riga', n, '| uscita spostata a', esito['data']); return
    if stato == 'CORREGGI':   # 7 nov: correzione di testo nelle colonne della riga (es. via "[NO AI]" da titolo, descrizione e tag), lo stato resta
        r = prod[n - 2]; dati = []
        for col in esito.get('colonne') or ('titolo_italiano', 'descrizione_youtube', 'tag_seo'):
            if col not in h:
                continue
            x = str(r.get(col) or '')
            for a, b in (esito.get('sostituisci') or {}).items():
                x = x.replace(a, b)
            x = '\n'.join(' '.join(riga.split()) if riga.strip() else '' for riga in x.split('\n')).replace(' ,', ',')
            if x != str(r.get(col) or ''):
                dati.append({'range': f"'{sch}'!{A.lettera(h.index(col) + 1)}{n}", 'values': [[x]]})
        if dati:
            A.api(fid, 'POST', '/values:batchUpdate', {'valueInputOption': 'RAW', 'data': dati})
        print(P.get('canale'), 'riga', n, '| corrette', len(dati), 'colonne'); return
    v = {'status': STATI.get(stato, 'Errore')}
    for k, col in CAMPI.items():
        if str(esito.get(k) or '').strip():
            v[col] = esito[k]
    for col, x in (esito.get('colonne') or {}).items():
        if str(x or '').strip() and col not in v:
            v[col] = x
    if stato == 'PUBBLICATO' and esito.get('pubblica_il'):
        try:
            v['data_pubblicazione'] = dt.datetime.fromisoformat(str(esito['pubblica_il']).replace('Z', '+00:00')).astimezone(ZoneInfo('Europe/Rome')).strftime('%Y-%m-%d %H:%M')
        except Exception:
            v['data_pubblicazione'] = str(esito['pubblica_il'])
    if M.attivo(P) and stato == 'CREATO':   # carica = MANUALE: video pronto, lo carica Giorgio (testi da copiare in questa riga)
        v['status'] = M.STATO
        v['data_pubblicazione'] = M.orario(P)
        mancanti = [c for c in ('playlist', 'descrizione_youtube', 'tag_seo', 'titolo_thumbnail', 'data_pubblicazione') if c not in h and str(v.get(c) or '').strip()]
        for c in mancanti:   # colonne che il file di produzione non ha ancora: si aggiungono in fondo
            A.api(fid, 'POST', '/values:batchUpdate', {'valueInputOption': 'RAW', 'data': [{'range': f"'{sch}'!{A.lettera(len(h) + 1)}1", 'values': [[c]]}]})
            h.append(c)
    if stato == 'RIMANDATO':
        v['data_inizio_produzione'] = ''
    dati = [{'range': f"'{sch}'!{A.lettera(h.index(c) + 1)}{n}", 'values': [[x if isinstance(x, str) else json.dumps(x, ensure_ascii=False)]]} for c, x in v.items() if c in h]
    A.api(fid, 'POST', '/values:batchUpdate', {'valueInputOption': 'RAW', 'data': dati})
    print(P.get('canale'), 'riga', n, '|', stato, '->', ', '.join(c for c in v if c in h), '|', str(esito.get('errore') or '')[:300])


if __name__ == '__main__':
    main()
