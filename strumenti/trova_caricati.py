#!/usr/bin/env python3
"""VIDEO CARICATI A MANO -> FILE DI PRODUZIONE (gratis, solo lettura su YouTube).
Per ogni canale con righe "Da caricare a mano" (colonna carica = MANUALE): cerca tra gli ultimi video del canale (anche privati e programmati)
quello con lo stesso titolo e scrive nella riga youtube_video_id, data_pubblicazione e stato Completato.
Cosi' Performance e Coach lavorano come per i video caricati in automatico."""
import json, os, re, sys, unicodedata, urllib.parse, urllib.request
import datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import avvio_canali as A
import performance as PF
import manuale as M
import descrizione as DESCR

E = os.environ.get


def norm(t):
    t = unicodedata.normalize('NFKD', str(t or '')).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', ' ', t).strip()


def get(url, auth):
    return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=auth), timeout=60).read())


def main():
    _, _, canali = A.righe(A.CONFIGS)
    for cfg in canali:
        cid = str(cfg.get('channel_id') or '').strip()
        fid = str(cfg.get('scout_production_sheet_id') or '').strip()
        if not cid or not fid:
            continue
        try:
            sch, h, prod = A.righe(fid)
        except Exception as e:
            print(cid, ': file di produzione non leggibile', str(e)[:100]); continue
        rip = json.loads(E('RIPRISTINA', '') or '{}').get(cid)   # correzione: riga rimessa "Da caricare a mano"
        if rip:
            A.api(fid, 'POST', '/values:batchUpdate', {'valueInputOption': 'RAW', 'data': [
                {'range': f"'{sch}'!{A.lettera(h.index(c) + 1)}{rip}", 'values': [[v]]} for c, v in (('status', M.STATO), ('youtube_video_id', '')) if c in h]})
            prod[int(rip) - 2]['status'] = M.STATO; prod[int(rip) - 2]['youtube_video_id'] = ''
            print(cid, 'riga', rip, ': rimessa Da caricare a mano')
        attesa = [(i + 2, r) for i, r in enumerate(prod) if str(r.get('status')).strip() == M.STATO]
        if not attesa:
            continue
        for n, r in attesa:   # titolo giusto (con accenti e punteggiatura) in cima alla descrizione e come primo tag
            t = str(r.get('titolo_italiano') or '').strip()
            nuovi = {'descrizione_youtube': DESCR.con_titolo(t, r.get('descrizione_youtube')), 'tag_seo': ', '.join(DESCR.tag_con_titolo(t, str(r.get('tag_seo') or '')))}
            nuovi = {c: v for c, v in nuovi.items() if c in h and v != str(r.get(c) or '').strip()}
            if t and nuovi:
                A.api(fid, 'POST', '/values:batchUpdate', {'valueInputOption': 'RAW', 'data': [
                    {'range': f"'{sch}'!{A.lettera(h.index(c) + 1)}{n}", 'values': [[v]]} for c, v in nuovi.items()]})
                print(cid, 'riga', n, ': titolo aggiunto in', ', '.join(nuovi))
        chiave = str(cfg.get('chiave_youtube') or '').strip() or {'Storia in Minuti': 'YT_REFRESH_TOKEN_STORIA', 'KAO PSICOLOGIA': 'YT_REFRESH_TOKEN_KAO'}.get(cid, '') \
            or 'YT_REFRESH_TOKEN_' + re.sub(r'[^A-Z0-9]+', '_', cid.upper()).strip('_')
        rt = PF.SEGRETI.get(chiave) or E(chiave)
        if not rt:
            print(cid, ': manca il segreto', chiave); continue
        auth = {'Authorization': 'Bearer ' + PF.token(rt)[0]}
        up = get('https://www.googleapis.com/youtube/v3/channels?part=contentDetails&mine=true', auth)['items'][0]['contentDetails']['relatedPlaylists']['uploads']
        voci = get('https://www.googleapis.com/youtube/v3/playlistItems?' + urllib.parse.urlencode({'part': 'snippet', 'playlistId': up, 'maxResults': 50}), auth).get('items', [])
        video = {norm(x['snippet']['title']): x['snippet']['resourceId']['videoId'] for x in voci}
        gia = {str(r.get('youtube_video_id') or '').strip() for r in prod}
        for n, r in attesa:
            t = norm(r.get('titolo_italiano') or r.get('titolo_originale'))
            vid = video.get(t) or next((v for k, v in video.items() if t and (k.startswith(t[:40]) or t.startswith(k[:40]))), None)
            if not vid or vid in gia:
                print(cid, 'riga', n, ': non ancora caricato |', r.get('titolo_italiano')); continue
            st = get('https://www.googleapis.com/youtube/v3/videos?part=status,snippet&id=' + vid, auth)['items'][0]
            if st['status'].get('privacyStatus') != 'public' and not st['status'].get('publishAt'):
                print(cid, 'riga', n, ': caricato ma ancora privato e non programmato, aspetto |', r.get('titolo_italiano')); continue   # gli Short partono solo da video pubblici o programmati
            quando = st['status'].get('publishAt') or st['snippet'].get('publishedAt') or ''
            try:
                quando = dt.datetime.fromisoformat(quando.replace('Z', '+00:00')).astimezone(M.ROMA).strftime('%Y-%m-%d %H:%M')
            except Exception:
                pass
            v = {'status': 'Completato', 'youtube_video_id': vid, 'data_pubblicazione': quando}
            A.api(fid, 'POST', '/values:batchUpdate', {'valueInputOption': 'RAW', 'data': [
                {'range': f"'{sch}'!{A.lettera(h.index(c) + 1)}{n}", 'values': [[x]]} for c, x in v.items() if c in h]})
            gia.add(vid)
            print(cid, 'riga', n, ': TROVATO', vid, '| esce', quando, '|', r.get('titolo_italiano'))


if __name__ == '__main__':
    main()
