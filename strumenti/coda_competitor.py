#!/usr/bin/env python3
"""Coda dai competitor senza Claude (14 nov, Giorgio: "non dobbiamo mai fermarci"; KAO copia al 100% e traduce).
MODO=lista: legge i canali CANALI (link di un video, @handle o UC...), toglie i video gia' nel file di produzione FOGLIO (stesso link o stesso titolo)
e stampa i candidati dal piu' visto. MODO=scrivi: aggiunge come righe Pronto i video IDS (id YouTube separati da virgola), nell'ordine dato.
Quota YouTube: poche unita' (niente ricerche)."""
import datetime as dt, json, os, re, sys, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scout as S
A = S.A
E = os.environ.get


def main():
    fid = E('FOGLIO'); sch, h, prod = A.righe(fid)
    c_link, c_stato = S.colonna(h, 'Link video', 'video_originale'), S.colonna(h, 'status', 'stato')
    gia = {m.group(1) for r in prod for m in [re.search(r'(?:v=|youtu\.be/)([\w-]{11})', str(r.get(c_link) or ''))] if m}
    tit = {S.norm(r.get('titolo_originale') or '') for r in prod} - {''}
    cand = {}
    for l in [x for x in re.split(r'[;,\s]+', E('CANALI') or '') if x.strip()]:
        try:
            nome, vids = S.video_canale(S.id_canale(l), int(E('PAGINE') or 10))
        except Exception as e:
            print('canale non letto', l, str(e)[:120]); continue
        lunghi = [v for v in vids if v['sec'] >= int(E('MIN_SEC') or 300)]
        nuovi = [v for v in lunghi if v['id'] not in gia and S.norm(v['titolo']) not in tit]
        print(f'== {nome}: {len(vids)} video, {len(lunghi)} lunghi, {len(nuovi)} non ancora fatti')
        for v in nuovi:
            cand[v['id']] = v
    if (E('MODO') or 'lista') == 'lista':
        for v in sorted(cand.values(), key=lambda v: v['views'], reverse=True)[:int(E('N') or 60)]:
            print(f"CAND {v['id']} | {v['views']:>9,} | {v['sec'] // 60}m | {v['pub'][:10]} | {v['canale']} | {v['titolo']}")
        return
    righe = []
    for i in [x.strip() for x in (E('IDS') or '').split(',') if x.strip()]:
        v = cand.get(i)
        if not v:
            print('non trovato o gia fatto:', i); continue
        val = {c_link: f"https://www.youtube.com/watch?v={v['id']}", c_stato: 'Pronto', 'titolo_originale': v['titolo'], 'views_at_discovery': v['views'],
               'nome_canale': v['canale'], 'competitor_category_id': v['cat'], 'data_scoperta': dt.datetime.now(A.ZoneInfo('Europe/Rome')).strftime('%Y-%m-%d %H:%M')}
        righe.append([val.get(x, '') for x in h])
        print('AGGIUNTO', v['id'], v['titolo'])
    if righe:
        A.api(fid, 'POST', f"/values/{urllib.parse.quote(chr(39) + sch + chr(39) + '!A1')}:append?valueInputOption=RAW&insertDataOption=INSERT_ROWS", {'values': righe})


if __name__ == '__main__':
    main()
