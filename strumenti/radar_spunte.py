#!/usr/bin/env python3
"""26 nov 2026 (Giorgio): nel foglio RADAR, scheda Canali, una spunta per ogni criterio di scelta (gratis, nessuna chiamata a Claude).
Quando sono tutte verdi il canale e' VALIDATO. Criteri:
  1. meno di 30.000 iscritti
  2. aperto da 1 a 6 mesi (primo video tra 30 e 183 giorni fa)
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
NUOVE = ['✓ Sotto 30.000 iscritti', '✓ Aperto da 1-6 mesi', '✓ Video virale (>100.000 views)',
         '✓ Cresce costante (3 settimane)', '✓ 3+ concorrenti in crescita', '✓ Tendenza positiva (views settimana su)', 'Concorrenti nello stesso filone', '✅ VALIDATO (tutto verde)']


def num(x):
    try:
        return float(str(x).replace('.', '').replace(',', '.')) if re.search(r'\d', str(x)) else None
    except Exception:
        return None


def leggi(nome):
    v = A.api(FOGLIO, 'GET', '/values/' + urllib.parse.quote(f"'{nome}'!A1:BZ20000") + '?valueRenderOption=UNFORMATTED_VALUE').get('values', [])
    return [str(x).strip() for x in v[0]], v[1:]


GENERICHE = set('storia storica storico storiche documentari documentario documentary educazione educativa educativo spiegata spiegate spiegati '
                'curiosita curiosità analisi video video, canale contenuti animata animate animati illustrata racconti storie stories history '
                'relax rilassante rilassanti musica ambience ambient natura naturali americana americano americani mondiale mondo'.split())
SINONIMI = [(r'seconda guerra mondiale|ww2|wwii|world war', ' ww2 '), (r'guerra fredda|cold war', ' guerrafredda '),
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
    try:
        return dt.date.fromisoformat(str(x)[:10])
    except Exception:
        return None


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
        pv = giorno(r.get('Primo video')); c2 = ATT if not pv else (SI if 30 <= (OGGI - pv).days <= 183 else NO)
        best = num(r.get('Views video migliore')); c3 = ATT if best is None else (SI if best >= 100000 else NO)
        oggi_s = max(serie.get(cid, {}) or [OGGI])
        p = [views_al(cid, oggi_s - dt.timedelta(days=7 * k)) for k in range(4)]
        if None in p:
            c4 = ATT
        else:
            w1, w2, w3 = p[0] - p[1], p[1] - p[2], p[2] - p[3]
            un_solo = best is not None and p[0] > 0 and best / p[0] > .6
            c4 = SI if (w1 > 0 and w1 >= w2 * .95 and w2 >= w3 * .95 and not un_solo) else NO
        mie = parole(r.get('Nicchia'))
        conc = [x for x in in_crescita if x is not r and str(x.get('channel_id')) != cid and len(mie & parole(x.get('Nicchia'))) >= 2] if mie else []
        c5 = SI if len(conc) >= 3 else NO
        cx = num(r.get('Crescita x')); c6 = ATT if cx is None else (SI if cx > 1 else NO)
        nomi = f"{len(conc)}: " + ', '.join(str(x.get('Canale'))[:30] for x in conc[:4]) if conc else '0'
        tutto = SI if all(c == SI for c in (c1, c2, c3, c4, c5, c6)) else ''
        out.append([c1, c2, c3, c4, c5, c6, nomi, tutto])
    k0 = h.index(NUOVE[0]) + 1
    if out:
        A.api(FOGLIO, 'PUT', '/values/' + urllib.parse.quote(f"'Canali'!{A.lettera(k0)}2:{A.lettera(k0 + len(NUOVE) - 1)}{len(out) + 1}") + '?valueInputOption=RAW',
              {'values': out})
    val = [(r, o) for r, o in zip(rr, out) if o[-1] == SI]
    print(f'canali: {len(rr)} | validati (tutto verde): {len(val)}')
    for r, o in sorted(zip(rr, out), key=lambda ro: -sum(c == SI for c in ro[1][:6]))[:25]:
        print(sum(c == SI for c in o[:6]), '/6', '|', r.get('Canale'), '|', r.get('Nicchia'), '|', o[:6], '| conc', o[6][:80], '| RPM', r.get('RPM stimato $'),
              '| v/g', r.get('Views al giorno (ultima settimana)'), '| isc', r.get('Iscritti'), '|', r.get('Link canale'))


if __name__ == '__main__':
    main()
