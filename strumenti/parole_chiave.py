#!/usr/bin/env python3
"""PAROLE CHIAVE di un filone (14 nov, Giorgio: "come su Google: le parole che la gente cerca devono stare in titolo e testo").
Gratis: niente Claude, niente ricerche YouTube a pagamento di quota (solo letture da 1 unita') + suggerimenti di ricerca di YouTube
(i completamenti automatici: sono le frasi che la gente scrive davvero nella barra di ricerca).
Env: NOME, CANALI (link/@handle dei canali del filone), SEMI (frasi di partenza, separate da ;), LINGUA (en/it), N (30), TOP (video per canale, 10).
Output: prove_video/parole_chiave/<NOME>.txt e .json"""
import collections, json, math, os, re, sys, time, urllib.parse, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scout as S
E = os.environ.get
LING = E('LINGUA') or 'en'
STOP = set('''a an the of in on at to for from by with and or but is are was were be been it its this that these those how why what when who which
vs into than then so as do does did not no your you my our their his her we they i he she them us about after before over under just very most more
la il lo le gli i un una uno di da del della dei delle degli in con per tra fra e o ma che come perche cosa quando chi non piu al alla ai alle
explained explain video full documentary minutes minute part ep episode shorts short'''.split())


def suggerimenti(q):
    u = 'https://suggestqueries.google.com/complete/search?' + urllib.parse.urlencode({'client': 'firefox', 'ds': 'yt', 'hl': LING, 'q': q})
    for _ in range(3):
        try:
            r = json.loads(urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0'}), timeout=20).read().decode('utf-8', 'ignore'))
            return [s.lower() for s in r[1]]
        except Exception:
            time.sleep(1.5)
    return []


def parole(t):
    return [w for w in re.findall(r"[a-zà-ú0-9']+", t.lower()) if len(w) > 1]


def ngram(t, n):
    w = parole(t)
    for i in range(len(w) - n + 1):
        g = w[i:i + n]
        if g[0] in STOP or g[-1] in STOP or all(x in STOP for x in g):
            continue
        yield ' '.join(g)


def main():
    top = int(E('TOP') or 10); vids = []
    for l in [x for x in re.split(r'[;,\s]+', E('CANALI') or '') if x.strip()]:
        try:
            nome, vv = S.video_canale(S.id_canale(l), 4)
        except Exception as e:
            print('canale non letto', l, e); continue
        vv = sorted([v for v in vv if v['sec'] >= 180], key=lambda v: v['views'], reverse=True)[:top]
        if vv:   # tag e descrizione dei video migliori (1 unita' ogni 50 video)
            info = {x['id']: x['snippet'] for x in S.yt('videos', part='snippet', id=','.join(v['id'] for v in vv)).get('items', [])}
            for v in vv:
                v['tag'] = info.get(v['id'], {}).get('tags', []); v['descr'] = info.get(v['id'], {}).get('description', '')[:500]
        print(f'== {nome}: {len(vv)} video migliori'); vids += vv
        for v in vv:
            print(f"   {v['views']:>10,} | {v['titolo']}")
    # 1) frasi candidate dai titoli e dai tag dei video migliori, pesate con le visualizzazioni
    peso, quanti = collections.Counter(), collections.Counter()
    for v in vids:
        w = math.log10(max(10, v['views']))
        testi = [v['titolo']] + v.get('tag', [])
        visti = set()
        for t in testi:
            for n in (1, 2, 3):
                for g in ngram(t, n):
                    if g not in visti:
                        visti.add(g); peso[g] += w * (1.6 if n > 1 else 1); quanti[g] += 1
    cand = [g for g, _ in peso.most_common(90) if quanti[g] >= 2 or ' ' in g]
    # 2) domanda reale: i completamenti automatici di YouTube (frasi davvero cercate)
    semi = [s.strip().lower() for s in (E('SEMI') or '').split(';') if s.strip()]
    cercate = collections.Counter()
    for q in semi + cand[:40]:
        for s in suggerimenti(q):
            cercate[s] += 1
        time.sleep(.3)
    # 3) punteggio: e' cercata (compare nei completamenti) + quanto la usano i video che funzionano
    righe = []
    for g in cand:
        n_s = sum(c for s, c in cercate.items() if g in s)
        righe.append({'parola': g, 'cercata': n_s, 'video_top_che_la_usano': quanti[g], 'punteggio': round(peso[g] + 4 * min(n_s, 6), 1)})
    for s, c in cercate.most_common(60):   # frasi complete cercate dalla gente, anche se i competitor non le usano ancora
        if not any(r['parola'] == s for r in righe) and len(s.split()) <= 6:
            uso = sum(1 for v in vids if all(w in parole(v['titolo'] + ' ' + ' '.join(v.get('tag', []))) for w in parole(s)))
            righe.append({'parola': s, 'cercata': c, 'video_top_che_la_usano': uso, 'punteggio': round(3 * c + 2 * uso, 1), 'frase_cercata': True})
    righe.sort(key=lambda r: r['punteggio'], reverse=True)
    sc, finali = set(), []
    for r in righe:   # niente doppioni (una frase gia' contenuta in un'altra piu' forte)
        if any(r['parola'] in x and r['parola'] != x for x in sc) and not r.get('frase_cercata'):
            continue
        sc.add(r['parola']); finali.append(r)
        if len(finali) >= int(E('N') or 30):
            break
    out = 'prove_video/parole_chiave'; os.makedirs(out, exist_ok=True); nome = re.sub(r'\W+', '_', E('NOME') or 'filone')
    json.dump({'video': [{k: v[k] for k in ('titolo', 'views', 'canale', 'tag')} for v in vids], 'parole': finali,
               'cercate': cercate.most_common(80)}, open(f'{out}/{nome}.json', 'w'), ensure_ascii=False, indent=1)
    with open(f'{out}/{nome}.txt', 'w') as f:
        for r in finali:
            f.write(f"{r['parola']} | cercata {r['cercata']} | nei video top {r['video_top_che_la_usano']} | punti {r['punteggio']}\n")
    print(open(f'{out}/{nome}.txt').read())


if __name__ == '__main__':
    main()
