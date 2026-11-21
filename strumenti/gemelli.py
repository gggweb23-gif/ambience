#!/usr/bin/env python3
"""VIDEO GEMELLI - metodo 50-50 (15 nov 2026, Giorgio).
Quando un NOSTRO video ha dimostrato di funzionare (coach/vincenti.json, scritto ogni mattina dal report Performance: almeno 50.000 views,
colonna gemelli_min_views, e CTR >= 4% o >= 3 volte le views medie del canale) si continua su quell'angolo. Per ogni canale con quota_gemelli > 0 (Channel Configs, la
decide Giorgio) si tengono in coda GEMELLI_CODA righe Pronto "gemelle" (nome_canale = GEMELLO):
 - canali con testo nostro: Claude scrive titoli NUOVI con lo stesso schema del vincente; il motore riscrive il copione partendo dal
   testo del vincente (Link video = il vincente) con argomento nuovo;
 - KAO (copia al 100% La Psicologia Invisible): si scelgono i video del competitor non ancora fatti piu' simili al vincente.
Quale riga si fa ogni giorno lo decidono avvio_archivio.py / avvio_canali.py rispettando la quota sugli ultimi 10 video.
Spesa: una chiamata Claude Sonnet a basso sforzo per canale, solo quando la coda gemelli e' sotto il minimo (~0,02 $)."""
import datetime as dt, json, os, re, sys, urllib.parse, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import avvio_canali as A
E = os.environ.get
CODA = int(E('GEMELLI_CODA') or 3)


def claude(prompt):
    req = urllib.request.Request('https://api.anthropic.com/v1/messages', method='POST', data=json.dumps({
        'model': 'claude-sonnet-5-5', 'max_tokens': 6000, 'thinking': {'type': 'between_tools'}, 'output_config': {'effort': 'low'},
        'messages': [{'role': 'user', 'content': prompt}]}).encode(),
        headers={'x-api-key': E('ANTHROPIC_API_KEY', ''), 'anthropic-version': '2023-06-01', 'content-type': 'application/json'})
    j = json.loads(urllib.request.urlopen(req, timeout=300).read())
    u = j.get('usage') or {}
    print(f"  Claude {u.get('input_tokens', 0) * 3e-6 + u.get('output_tokens', 0) * 15e-6:.3f} $")
    t = ''.join(b.get('text', '') for b in j['content'] if b.get('type') == 'text')
    m = re.search(r'\[.*\]', t, re.S)
    return json.loads(m.group(0)) if m else []


def main():
    try:
        vincenti = json.load(open('coach/vincenti.json'))
    except Exception:
        print('nessun coach/vincenti.json: niente gemelli'); return
    _, _, canali = A.righe(A.CONFIGS)
    per_id = {str(c.get('channel_id') or '').strip(): c for c in canali}
    for nome, w in vincenti.items():
        cfg = per_id.get(w.get('channel_id')) or {}
        quota = A.num(cfg.get('quota_gemelli'))
        if quota <= 0 or not w.get('video'):
            print(nome, ': quota_gemelli 0 o nessun vincente, niente gemelli'); continue
        fid = str(cfg.get('scout_production_sheet_id') or '').strip()
        sch, h, prod = A.righe(fid)
        gem = [r for r in prod if str(r.get('status')).strip() == 'Pronto' and str(r.get('nome_canale') or '').strip().upper() == 'GEMELLO']
        manca = CODA - len(gem)
        if manca <= 0:
            print(nome, ': coda gemelli piena (', len(gem), ')'); continue
        # 21 nov (Giorgio): mai sempre la stessa struttura. Modelli = fino a 3 nostri vincenti (tutti sopra gemelli_min_views, 50.000 views):
        # si ALTERNANO a turno (1o, 2o, 3o, 1o...): ogni riga nuova va al modello con meno gemelli (in coda e gia' fatti).
        vv = sorted(w['video'], key=lambda x: x.get('posto') or 99)[:3]
        PESI = [1 / len(vv)] * len(vv)   # 21 nov: a turno, pesi uguali (prima 50/30/20)
        conta = [sum(1 for r in prod if str(r.get('nome_canale') or '').strip().upper() == 'GEMELLO'
                     and (str(r.get('gemello_di') or '').strip() == x['titolo'] or x['id'] in str(r.get('Link video') or ''))) for x in vv]
        modelli = []
        for _ in range(max(manca, 0)):
            tot = sum(conta) + 1
            k = max(range(len(vv)), key=lambda i: PESI[i] * tot - conta[i])
            conta[k] += 1; modelli.append(vv[k])
        titoli_v = '\n'.join(f"- {x['titolo']} ({int(x.get('views') or 0)} views, CTR {x.get('ctr')}%)" for x in vv)
        fatti = [str(r.get('titolo_italiano') or r.get('titolo_originale') or '').strip() for r in prod][-150:]
        ora = dt.datetime.now(A.ZoneInfo('Europe/Rome')).strftime('%Y-%m-%d %H:%M')
        righe = []
        if str(cfg.get('channel_id') or '').upper().startswith('KAO'):
            import scout as S
            gia = {m.group(1) for r in prod for m in [re.search(r'(?:v=|youtu\.be/)([\w-]{11})', str(r.get('Link video') or ''))] if m}
            cand = []
            for l in [x for x in re.split(r'[;,\s]+', str(cfg.get('canali_da_copiare') or '')) if x.strip()]:
                try:
                    cand += [v for v in S.video_canale(S.id_canale(l), 10)[1] if v['sec'] >= 300 and v['id'] not in gia]
                except Exception as e:
                    print(nome, ': competitor non letto', str(e)[:100])
            cand = sorted(cand, key=lambda v: v['views'], reverse=True)[:150]
            if not cand:
                print(nome, ': nessun video del competitor ancora da fare'); continue
            slot = '\n'.join(f'{j}. twin of our video "{m["titolo"]}"' for j, m in enumerate(modelli))
            scelte = claude(f"""Below are videos of the channel we translate (Spanish). For EACH slot pick ONE video whose topic and title pattern are the MOST similar
to OUR video named in that slot (same kind of promise, e.g. "the psychology of people who..."), every pick different, never a topic we already made: {' | '.join(fatti[-80:])}
Slots:
{slot}
Answer ONLY JSON: [{{"slot": number, "i": number}}]
Videos:
""" + '\n'.join(f"{i}. {c['titolo']}" for i, c in enumerate(cand)))
            usati = set()
            for s in scelte[:manca]:
                c = cand[int(s['i'])] if str(s.get('i', '')).isdigit() and int(s['i']) < len(cand) and int(s['i']) not in usati else None
                m = modelli[int(s['slot'])] if str(s.get('slot', '')).isdigit() and int(s['slot']) < len(modelli) else modelli[0]
                if c:
                    usati.add(int(s['i']))
                    righe.append({'Link video': f"https://www.youtube.com/watch?v={c['id']}", 'titolo_originale': c['titolo'], 'views_at_discovery': c['views'],
                                  'nome_canale': 'GEMELLO', 'data_scoperta': ora, 'gemello_di': m['titolo'], '_modello': m['titolo']})
        else:
            slot = '\n'.join(f'{j}. twin of "{m["titolo"]}"' for j, m in enumerate(modelli))
            titoli = claude(f"""Our YouTube channel "{cfg.get('channel_name')}" ({cfg.get('language') or 'en'}). These are OUR videos that worked much better than the others:
{titoli_v}
Write one NEW video title for EACH slot below: the TWIN of the video named in the slot, same title pattern (same kind of promise, question and twist,
same rhythm and length), same filone, but on a DIFFERENT documented subject. The viewer who loved that video must want to click it on the YouTube homepage.
All titles different from each other. Never a subject we already made: {' | '.join(fatti)}
Language: {cfg.get('language') or 'en'} only, correct spelling, max 90 characters, no emoji, never the word "davvero".
Slots:
{slot}
Answer ONLY JSON: [{{"slot": number, "titolo": "..."}}]""")
            for t in titoli[:manca]:
                da = modelli[int(t['slot'])] if str(t.get('slot', '')).isdigit() and int(t['slot']) < len(modelli) else modelli[0]
                if 15 < len(str(t.get('titolo') or '')) <= 100:
                    righe.append({'Link video': f"https://www.youtube.com/watch?v={da['id']}", 'titolo_originale': da['titolo'], 'titolo_italiano': t['titolo'],
                                  'nome_canale': 'GEMELLO', 'target_durata': '9-10', 'gemello_di': da['titolo'], '_modello': da['titolo']})
        for r in righe:
            r['status'] = 'Pronto'
            print(nome, ': GEMELLO aggiunto ->', r.get('titolo_italiano') or r.get('titolo_originale'), '| gemello di:', r.get('_modello'))
        if righe and E('PROVA') != 'SI' and 'gemello_di' not in h:   # 15 nov (Giorgio): colonna che dice di quale nostro video vincente e' gemella la riga
            A.api(fid, 'PUT', f"/values/{urllib.parse.quote(chr(39) + sch + chr(39) + '!' + A.lettera(len(h) + 1) + '1')}?valueInputOption=RAW", {'values': [['gemello_di']]})
            h = h + ['gemello_di']; print(nome, ': colonna gemello_di aggiunta al file di produzione')
        if righe and E('PROVA') != 'SI':
            A.api(fid, 'POST', f"/values/{urllib.parse.quote(chr(39) + sch + chr(39) + '!A1')}:append?valueInputOption=RAW&insertDataOption=INSERT_ROWS",
                  {'values': [[r.get(x, '') for x in h] for r in righe]})


if __name__ == '__main__':
    main()
