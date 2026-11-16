#!/usr/bin/env python3
"""RADAR NOTIZIE (16 nov 2026, Giorgio: "ogni giorno le notizie piu' viste del filone, sempre con una PERSONA da mettere in copertina").
Ogni mattina, per un filone (es. tech):
  1) raccoglie le notizie del giorno: Google News (sezione del filone, inglese e italiano) + Google Trends (USA e Italia), gratis
  2) Claude le raggruppa in storie e tiene SOLO quelle riconducibili a una persona nota (se e' un'azienda: il fondatore/proprietario/CEO)
  3) misura l'onda su YouTube: views dei video degli ultimi 3 giorni e views all'ora (la velocita' dice se l'onda sale)
  4) sceglie la storia: si resta sull'onda di ieri (con un angolo nuovo) finche' e' tra le piu' forti; si cambia quando ne arriva una piu' potente
Uscita: notizie/radar/<filone>/<data>.json e ultimo.md (classifica leggibile) + notizie/radar/<filone>/onda.json (la storia che si sta cavalcando).
Costo: Claude ~0,03 $ al giorno; YouTube ~100 unita' di quota per ricerca (YT_API_KEY_NOTIZIE se c'e', altrimenti la chiave del radar).
Env: FILONE (tech), MAX_STORIE (6), ANTHROPIC_API_KEY, YT_API_KEY_NOTIZIE / YT_API_KEY_RADAR"""
import datetime as dt, html, json, os, re, sys, time, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

E = os.environ.get
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILONE = (E('FILONE') or 'tech').strip().lower()
CART = os.path.join(ROOT, 'notizie', 'radar', FILONE); os.makedirs(CART, exist_ok=True)
OGGI = dt.datetime.now(ZoneInfo('Europe/Rome')).date().isoformat()
ORA = dt.datetime.now(dt.timezone.utc)
YT = E('YT_API_KEY_NOTIZIE') or E('YT_API_KEY_RADAR') or ''
MAX_STORIE = int(E('MAX_STORIE') or 6)

# fonti del filone (gratis). Per un filone nuovo basta aggiungere qui le sue sezioni / ricerche.
FILONI = {
    'tech': {
        'descrizione': 'technology and AI business news: big tech companies, AI labs, chips, social networks, smartphones, startups, '
                       'tech billionaires and CEOs (Musk, Huang, Altman, Amodei, Zuckerberg, Cook, Bezos, Pichai, Nadella, Storonsky...)',
        'rss': ['https://news.google.com/rss/headlines/section/topic/TECHNOLOGY?hl=en-US&gl=US&ceid=US:en',
                'https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=en-US&gl=US&ceid=US:en',
                'https://news.google.com/rss/headlines/section/topic/TECHNOLOGY?hl=it&gl=IT&ceid=IT:it',
                'https://news.google.com/rss/search?q=CEO+tech+when:1d&hl=en-US&gl=US&ceid=US:en'],
        'trends': ['US', 'IT'],
    },
}


def log(*a):
    print(*a, flush=True)


def get(url, timeout=40, raw=False, headers=None):
    h = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36'}
    h.update(headers or {})
    with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout) as r:
        b = r.read()
    return b if raw else json.loads(b)


def notizie_rss(url):
    out = []
    try:
        x = ET.fromstring(get(url, raw=True))
        for it in x.iter('item'):
            t = html.unescape(it.findtext('title') or '').strip()
            fonte = (it.find('source').text if it.find('source') is not None else '') or ''
            if t:
                out.append({'titolo': t, 'fonte': fonte, 'data': it.findtext('pubDate') or ''})
    except Exception as e:
        log('rss non letto', url[:80], str(e)[:80])
    return out


def trends(geo):
    """Google Trends: le ricerche in salita del giorno, con il traffico stimato e i titoli delle notizie collegate."""
    out = []
    try:
        x = ET.fromstring(get(f'https://trends.google.com/trending/rss?geo={geo}', raw=True))
        ns = {'ht': 'https://trends.google.com/trending/rss'}
        for it in x.iter('item'):
            q = it.findtext('title') or ''
            traffico = it.findtext('ht:approx_traffic', namespaces=ns) or ''
            tit = [n.findtext('ht:news_item_title', namespaces=ns) or '' for n in it.findall('ht:news_item', ns)]
            out.append({'ricerca': q, 'traffico': traffico, 'notizie': [html.unescape(t) for t in tit if t][:3], 'paese': geo})
    except Exception as e:
        log('trends non letto', geo, str(e)[:80])
    return out


def claude(prompt, max_tokens=5000):
    req = urllib.request.Request('https://api.anthropic.com/v1/messages', data=json.dumps({
        'model': 'claude-sonnet-5-5', 'max_tokens': max_tokens, 'thinking': {'type': 'between_tools'}, 'output_config': {'effort': 'low'},
        'messages': [{'role': 'user', 'content': prompt}]}).encode(),
        headers={'x-api-key': E('ANTHROPIC_API_KEY', ''), 'anthropic-version': '2023-06-01', 'content-type': 'application/json'})
    j = json.loads(urllib.request.urlopen(req, timeout=300).read())
    u = j.get('usage') or {}
    log(f"Claude: {u.get('input_tokens', 0) * 3e-6 + u.get('output_tokens', 0) * 15e-6:.3f} $")
    t = ''.join(b.get('text', '') for b in j['content'] if b.get('type') == 'text')
    return json.loads(t[t.find('['): t.rfind(']') + 1])


def views_youtube(q, lingua, giorni=3):
    """Video degli ultimi N giorni sulla storia: views totali, views all'ora (velocita'), quanti video lunghi (concorrenza)."""
    if not YT:
        return {}
    time.sleep(1.5)
    try:
        r = get('https://www.googleapis.com/youtube/v3/search?' + urllib.parse.urlencode({
            'part': 'snippet', 'q': q, 'type': 'video', 'order': 'viewCount', 'maxResults': 15, 'relevanceLanguage': lingua, 'key': YT,
            'publishedAfter': (ORA - dt.timedelta(days=giorni)).strftime('%Y-%m-%dT%H:%M:%SZ')}))
        ids = [x['id']['videoId'] for x in r.get('items', [])]
        if not ids:
            return {'views': 0, 'views_ora': 0, 'video': 0, 'lunghi': 0, 'top': []}
        v = get('https://www.googleapis.com/youtube/v3/videos?' + urllib.parse.urlencode({'part': 'snippet,statistics,contentDetails', 'id': ','.join(ids), 'key': YT}))
    except Exception as e:
        log('youtube non letto', q, str(e)[:80]); return {}
    tot = vel = lunghi = 0; top = []
    for x in v.get('items', []):
        n = int(x['statistics'].get('viewCount', 0)); tot += n
        ore = max(1.0, (ORA - dt.datetime.fromisoformat(x['snippet']['publishedAt'].replace('Z', '+00:00'))).total_seconds() / 3600)
        vel += n / ore
        d = x['contentDetails']['duration']; m = re.search(r'(\d+)M', d); h = re.search(r'(\d+)H', d)
        lungo = bool(h) or (m and int(m.group(1)) >= 4)
        lunghi += 1 if lungo else 0
        top.append({'views': n, 'ore': round(ore), 'titolo': x['snippet']['title'][:90], 'canale': x['snippet']['channelTitle'][:30], 'lungo': bool(lungo)})
    top.sort(key=lambda t: -t['views'])
    return {'views': tot, 'views_ora': round(vel), 'video': len(top), 'lunghi': lunghi, 'top': top[:5]}


def main():
    f = FILONI[FILONE]
    news = []
    for u in f['rss']:
        news += notizie_rss(u)
    tr = []
    for g in f.get('trends', []):
        tr += trends(g)
    log(f'{len(news)} notizie, {len(tr)} ricerche in tendenza')
    onda = json.load(open(os.path.join(CART, 'onda.json'))) if os.path.exists(os.path.join(CART, 'onda.json')) else {}
    prompt = (f"You are the news editor of a YouTube channel in this niche: {f['descrizione']}.\n"
              "Below are today's headlines (Google News) and today's rising Google searches (Google Trends, with traffic).\n"
              f"Group them into distinct STORIES of this niche only. Keep ONLY stories that can be tied to ONE well-known real PERSON whose face can go "
              "on the thumbnail (if the story is about a company, the person is its founder/owner/CEO, the face people know). Drop stories without "
              "such a person, drop politics-only stories and anything outside the niche.\n"
              + (f"The channel is currently riding this story: {onda.get('storia')} (person: {onda.get('persona')}). If it is still in today's news, "
                 "include it as a story and mark it continua=true.\n" if onda.get('storia') else '')
              + f"Return the {MAX_STORIE + 2} biggest stories, most important first, as JSON ONLY: "
              '[{"storia": "short English title of the story", "persona": "Full Name", "ruolo": "role (e.g. CEO of Nvidia)", "azienda": "...", '
              '"query_en": "3-5 word YouTube search in English that finds videos about THIS story", "query_it": "same in Italian", '
              '"novita": "what is new today, one sentence", "continua": false}]\n\nHEADLINES:\n'
              + '\n'.join(f"- {n['titolo']} ({n['fonte']})" for n in news[:220])
              + '\n\nRISING SEARCHES:\n' + '\n'.join(f"- {t['ricerca']} [{t['paese']}, {t['traffico']}]: {' | '.join(t['notizie'])}" for t in tr[:80]))
    storie = claude(prompt)[:MAX_STORIE]
    for s in storie:
        s['yt_en'] = views_youtube(s['query_en'], 'en')
        s['yt_it'] = views_youtube(s['query_it'], 'it')
        s['punteggio'] = (s['yt_en'].get('views_ora') or 0) + (s['yt_it'].get('views_ora') or 0)
        log(f"{s['punteggio']:>9,}/ora | {s['yt_en'].get('views', 0):>11,} views EN | {s['yt_it'].get('views', 0):>9,} IT | {s['persona']} | {s['storia']}")
    storie.sort(key=lambda s: -s['punteggio'])
    # scelta: si resta sull'onda finche' e' forte (almeno il 60% della piu' forte); si cambia quando arriva una storia piu' potente
    scelta, motivo = storie[0], 'la storia con piu\' views all\'ora oggi'
    cont = next((s for s in storie if s.get('continua')), None)
    if cont and cont is not storie[0] and cont['punteggio'] >= .6 * storie[0]['punteggio']:
        scelta, motivo = cont, 'l\'onda di ieri e\' ancora forte: si resta con un angolo nuovo'
    elif cont is storie[0]:
        motivo = 'l\'onda di ieri e\' ancora la piu\' forte: si resta con un angolo nuovo'
    stessa = bool(onda.get('storia')) and scelta.get('continua')
    nuova_onda = {'storia': scelta['storia'], 'persona': scelta['persona'], 'ruolo': scelta.get('ruolo'), 'azienda': scelta.get('azienda'),
                  'dal': onda.get('dal') if stessa else OGGI, 'giorni': (onda.get('giorni', 0) + 1) if stessa else 1,
                  'angoli_fatti': (onda.get('angoli_fatti') or []) if stessa else [], 'novita_oggi': scelta.get('novita'), 'aggiornato': OGGI}
    json.dump({'data': OGGI, 'filone': FILONE, 'scelta': scelta['storia'], 'motivo': motivo, 'storie': storie}, open(os.path.join(CART, f'{OGGI}.json'), 'w'), ensure_ascii=False, indent=1)
    json.dump(nuova_onda, open(os.path.join(CART, 'onda.json'), 'w'), ensure_ascii=False, indent=1)
    righe = [f'# Radar notizie {FILONE} — {OGGI}', '', f"**Scelta:** {scelta['storia']} ({scelta['persona']}) — {motivo}", '',
             '| # | Storia | Persona | Views all\'ora (EN+IT) | Views 3 gg EN | Views 3 gg IT | Video lunghi EN |', '|---|---|---|---|---|---|---|']
    for k, s in enumerate(storie, 1):
        righe.append(f"| {k} | {s['storia']} | {s['persona']} | {s['punteggio']:,} | {s['yt_en'].get('views', 0):,} | {s['yt_it'].get('views', 0):,} | {s['yt_en'].get('lunghi', 0)} |")
    open(os.path.join(CART, 'ultimo.md'), 'w').write('\n'.join(righe) + '\n')
    log('\n'.join(righe))
    if os.environ.get('GITHUB_OUTPUT'):
        open(os.environ['GITHUB_OUTPUT'], 'a').write(f"storia={scelta['storia']}\n")


if __name__ == '__main__':
    main()
