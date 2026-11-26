#!/usr/bin/env python3
"""26 nov 2026 (Giorgio): nel foglio RADAR, scheda Canali, una spunta per ogni criterio di scelta (gratis, nessuna chiamata a Claude).
Quando sono tutte verdi il canale e' VALIDATO. Criteri:
  1. meno di 30.000 iscritti
  2. aperto da 0 a 6 mesi (primo video negli ultimi 183 giorni)
  3. almeno un video virale (video migliore sopra 100.000 views)
  4. cresce in modo costante: views delle ultime 3 settimane (scheda Storico) in crescita settimana dopo settimana
     e non vive di un solo video (il video migliore sotto il 60% delle views del canale)
  5. almeno 3 concorrenti dello stesso filone in crescita/esplosione nella scheda Canali
  6. tendenza positiva: views dell'ultima settimana sopra quelle della settimana prima (Crescita x > 1)
Gira dopo radar.py (che riscrive la scheda Canali) e riscrive ogni volta queste colonne in fondo."""
import datetime as dt, os, re, sys, urllib.parse
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import avvio_canali as A

FOGLIO = os.environ.get('RADAR_FOGLIO', '1cOLkymyVmU2SQYZWMNMPb99AHkk4qdH8RKMUPtwhcLI')
OGGI = dt.datetime.now(ZoneInfo('Europe/Rome')).date()
SI, NO, ATT = '✅', '❌', '⏳'
NUOVE = ['✓ Sotto 30.000 iscritti', '✓ Aperto da 0-6 mesi', '✓ Video virale (>100.000 views)',
         '✓ Cresce costante (3 settimane)', '✓ 3+ concorrenti in crescita', '✓ Tendenza positiva (views settimana su)', 'Concorrenti nello stesso filone', 'Fase dell\'onda', 'Pubblica in media (solo video lunghi)', 'Video lunghi sopra 100.000 views', '✅ VALIDATO (tutto verde)', '🏆 Classifica']


def num(x):
    try:
        return float(str(x).replace('.', '').replace(',', '.')) if re.search(r'\d', str(x)) else None
    except Exception:
        return None


def leggi(nome):
    v = A.api(FOGLIO, 'GET', '/values/' + urllib.parse.quote(f"'{nome}'!A1:BZ20000") + '?valueRenderOption=UNFORMATTED_VALUE&dateTimeRenderOption=FORMATTED_STRING').get('values', [])
    return [str(x).strip() for x in v[0]], v[1:]


GENERICHE = set('storia storica storico storiche documentari documentario documentary educazione educativa educativo spiegata spiegate spiegati '
                'curiosita curiosità analisi video video, canale contenuti animata animate animati illustrata racconti storie stories history '
                'relax rilassante rilassanti musica ambience ambient natura naturali americana americano americani mondiale mondo'.split())
SINONIMI = [(r'seconda guerra mondiale|guerra mondiale|ww2|wwii|world war', ' ww2 '), (r'guerra fredda|cold war', ' guerrafredda '),
            (r'economi\w*|finanz\w*|ricchezz\w*|debito', ' economia '), (r'geopolitic\w*|geografi\w*|mapp\w*', ' geopolitica '),
            (r'militar\w*|battagli\w*|armi|aviazione|navi da guerra', ' militare '), (r'archeolog\w*|antic\w*|misteri\w*', ' antico '),
            (r'jazz|fireplace|camino|cozy|sonno|meditazion\w*|asmr|autunn\w*', ' ambience '), (r'animali|wildlife|selvag\w*|fauna', ' animali '),
            (r'stoic\w*|filosofi\w*', ' filosofia '), (r'nostalgi\w*|vintage|anni 50|1950s|1960s', ' nostalgia '), (r'spazio|nasa|astronaut\w*|astronom\w*', ' spazio ')]


def parole(nicchia):
    t = ' ' + str(nicchia).lower() + ' '
    for a, b in SINONIMI:
        t = re.sub(a, b, t)
    return {w for w in re.findall(r'[a-zà-ù0-9]{4,}', t) if w not in GENERICHE}


def giorno(x):
    x = str(x).strip()
    for f in ('%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y'):
        try:
            return dt.datetime.strptime(x[:10], f).date()
        except Exception:
            pass
    try:   # numero di serie di Google Sheets
        return dt.date(1899, 12, 30) + dt.timedelta(days=int(float(x)))
    except Exception:
        return None


YT_KEY = os.environ.get('YT_API_KEY_RADAR', '')


def yt(path, **q):
    import json, urllib.request
    q['key'] = YT_KEY
    return json.load(urllib.request.urlopen('https://www.googleapis.com/youtube/v3/' + path + '?' + urllib.parse.urlencode(q), timeout=60))


def durata(iso):
    m = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', iso or '')
    return (int(m.group(1) or 0) * 3600 + int(m.group(2) or 0) * 60 + int(m.group(3) or 0)) if m else 0


def lunghi(cid):
    """26 nov (Giorgio): cadenza e video esplosi contando SOLO i video lunghi (niente Short: sopra i 3 minuti)."""
    ids, tok = [], None
    for _ in range(6):   # fino a 300 video
        q = dict(part='contentDetails', playlistId='UU' + cid[2:], maxResults=50)
        if tok:
            q['pageToken'] = tok
        r = yt('playlistItems', **q); ids += [x['contentDetails']['videoId'] for x in r.get('items', [])]; tok = r.get('nextPageToken')
        if not tok:
            break
    vv = []
    for i in range(0, len(ids), 50):
        for x in yt('videos', part='contentDetails,statistics,snippet', id=','.join(ids[i:i + 50])).get('items', []):
            if durata(x['contentDetails'].get('duration')) > 180:
                vv.append((x['snippet']['publishedAt'][:10], int(x['statistics'].get('viewCount', 0))))
    if len(vv) < 2:
        return '', str(sum(v >= 100000 for _, v in vv))
    dd = sorted(dt.date.fromisoformat(d) for d, _ in vv)
    g = (dd[-1] - dd[0]).days / (len(dd) - 1)
    return 'ogni ' + f'{g:.1f}'.replace('.', ',') + f' giorni ({len(dd)} lunghi)', str(sum(v >= 100000 for _, v in vv))


def main():
    h, rr = leggi('Canali')
    for c in NUOVE:
        if c not in h:
            h.append(c)
    A.api(FOGLIO, 'PUT', '/values/' + urllib.parse.quote(f"'Canali'!A1:{A.lettera(len(h))}1") + '?valueInputOption=RAW', {'values': [h]})
    rr = [dict(zip(h, list(r) + [''] * (len(h) - len(r)))) for r in rr]

    # Storico: views totali del canale giorno per giorno
    hs, rs = leggi('Storico')
    ix = {c: hs.index(c) for c in ('data', 'channel_id', 'views')}
    serie = {}
    for r in rs:
        r = list(r) + [''] * 6
        d, cid, v = giorno(r[ix['data']]), str(r[ix['channel_id']]), num(r[ix['views']])
        if d and v is not None:
            serie.setdefault(cid, {})[d] = v

    def views_al(cid, d):
        s = serie.get(cid, {})
        for k in (0, -1, 1, -2, 2):
            if d + dt.timedelta(days=k) in s:
                return s[d + dt.timedelta(days=k)]
        return None

    in_crescita = [r for r in rr if any(x in str(r.get('Crescita')) for x in ('esplosione', 'crescita'))]
    out = []
    for r in rr:
        cid = str(r.get('channel_id'))
        isc = num(r.get('Iscritti')); c1 = ATT if isc is None else (SI if isc < 30000 else NO)
        pv = giorno(r.get('Primo video')); c2 = ATT if not pv else (SI if 0 <= (OGGI - pv).days <= 183 else NO)
        best = num(r.get('Views video migliore')); c3 = ATT if best is None else (SI if best >= 100000 else NO)
        oggi_s = max(serie.get(cid, {}) or [OGGI])
        p = [views_al(cid, oggi_s - dt.timedelta(days=7 * k)) for k in range(4)]
        onda = '⏳ dati in raccolta'
        if None not in p[:3]:
            a, b = p[0] - p[1], p[1] - p[2]
            onda = ('🌊 sale (accelera)' if a > b * 1.2 else '〰️ in cima (cresce piano)' if a >= b * .95 else '📉 scende') if b > 0 else ('🌊 sale' if a > 0 else '📉 ferma')
        nv, gg = num(r.get('Video nel canale')), num(r.get('Giorni dal primo video'))
        freq, n100 = '', ''
        if None in p:
            c4 = ATT
        else:
            w1, w2, w3 = p[0] - p[1], p[1] - p[2], p[2] - p[3]
            un_solo = best is not None and p[0] > 0 and best / p[0] > .6
            c4 = SI if (w1 > 0 and w1 >= w2 * .95 and w2 >= w3 * .95 and not un_solo) else NO
        mie = parole(r.get('Nicchia'))
        conc = [x for x in in_crescita if x is not r and str(x.get('channel_id')) != cid and len(mie & parole(x.get('Nicchia'))) >= (1 if min(len(mie), len(parole(x.get('Nicchia')))) <= 2 else 2)] if mie else []
        c5 = SI if len(conc) >= 3 else NO
        cx = num(r.get('Crescita x')); c6 = ATT if cx is None else (SI if cx > 1 else NO)
        nomi = f"{len(conc)}: " + ', '.join(str(x.get('Canale'))[:30] for x in conc[:4]) if conc else '0'
        tutto = SI if all(c == SI for c in (c1, c2, c3, c4, c5, c6)) else ''
        out.append([c1, c2, c3, c4, c5, c6, nomi, onda, freq, n100, tutto])
    fatti = 0
    for i, r in enumerate(rr):   # solo i canali promettenti (almeno 4 spunte su 6): risparmia quota YouTube
        if YT_KEY and sum(c == SI for c in out[i][:6]) >= 4 and str(r.get('channel_id')).startswith('UC'):
            try:
                out[i][8], out[i][9] = lunghi(str(r.get('channel_id'))); fatti += 1
                out[i][2] = SI if int(out[i][9] or 0) >= 1 else NO   # video esploso = almeno un video LUNGO sopra 100.000 views
                out[i][10] = SI if all(c == SI for c in out[i][:6]) else ''
            except Exception as e:
                out[i][8] = 'non letto'
    print('cadenza video lunghi calcolata per', fatti, 'canali')
    # 26 nov (Giorgio): sempre i 3 migliori evidenziati (giallo pieno, meno, meno ancora): prima i VALIDATI, poi il numero di spunte,
    # a parita' il guadagno potenziale (views al giorno x RPM)
    def pot(r):
        return (num(r.get('Views al giorno (ultima settimana)')) or 0) * (num(r.get('RPM stimato $')) or 0)
    ordine = sorted(range(len(rr)), key=lambda i: (out[i][-1] == SI, sum(c == SI for c in out[i][:6]), pot(rr[i])), reverse=True)
    for i in range(len(out)):
        out[i].append('')
    for pos, i in enumerate(ordine[:3]):
        out[i][-1] = f"{pos + 1}° " + ('VALIDATO' if out[i][-2] == SI else f"migliore ({sum(c == SI for c in out[i][:6])}/6)")
    k0 = h.index(NUOVE[0]) + 1
    if out:
        A.api(FOGLIO, 'PUT', '/values/' + urllib.parse.quote(f"'Canali'!{A.lettera(k0)}2:{A.lettera(k0 + len(NUOVE) - 1)}{len(out) + 1}") + '?valueInputOption=RAW',
              {'values': out})
    try:
        gid = next(x['properties']['sheetId'] for x in A.api(FOGLIO, 'GET', '?fields=sheets.properties')['sheets'] if x['properties']['title'] == 'Canali')
        bianco = {'red': 1, 'green': 1, 'blue': 1}
        gialli = [{'red': 1, 'green': .85, 'blue': .2}, {'red': 1, 'green': .92, 'blue': .55}, {'red': 1, 'green': .97, 'blue': .8}]
        rq = [{'repeatCell': {'range': {'sheetId': gid, 'startRowIndex': 1, 'endRowIndex': len(rr) + 1, 'startColumnIndex': 0, 'endColumnIndex': len(h)},
                              'cell': {'userEnteredFormat': {'backgroundColor': bianco}}, 'fields': 'userEnteredFormat.backgroundColor'}}]
        for pos, i in enumerate(ordine[:3]):
            rq.append({'repeatCell': {'range': {'sheetId': gid, 'startRowIndex': i + 1, 'endRowIndex': i + 2, 'startColumnIndex': 0, 'endColumnIndex': len(h)},
                                      'cell': {'userEnteredFormat': {'backgroundColor': gialli[pos]}}, 'fields': 'userEnteredFormat.backgroundColor'}})
        A.api(FOGLIO, 'POST', ':batchUpdate', {'requests': rq})
    except Exception as e:
        print('colori non messi:', str(e)[:150])
    for pos, i in enumerate(ordine[:3]):
        print('CLASSIFICA', out[i][-1], '|', rr[i].get('Canale'), '|', rr[i].get('Nicchia'), '| RPM', rr[i].get('RPM stimato $'), '| v/g', rr[i].get('Views al giorno (ultima settimana)'),
              '| isc', rr[i].get('Iscritti'), '|', out[i][7], '|', out[i][8], '| lunghi >100k:', out[i][9], '|', rr[i].get('Link canale'))
    val = [(r, o) for r, o in zip(rr, out) if o[-2] == SI]
    print(f'canali: {len(rr)} | validati (tutto verde): {len(val)}')
    for r, o in sorted(zip(rr, out), key=lambda ro: -sum(c == SI for c in ro[1][:6]))[:25]:
        print(sum(c == SI for c in o[:6]), '/6', '|', r.get('Canale'), '|', r.get('Nicchia'), '|', o[:6], '| conc', o[6][:80], '|', o[7], '|', o[8], '| RPM', r.get('RPM stimato $'),
              '| v/g', r.get('Views al giorno (ultima settimana)'), '| isc', r.get('Iscritti'), '|', r.get('Link canale'))


if __name__ == '__main__':
    main()
