#!/usr/bin/env python3
"""COPIONE NOTIZIA (16 nov 2026). Dalla storia scelta dal radar (notizie/radar/<filone>/onda.json) al file del video per video_notizie.py,
in inglese e in italiano (stesse immagini, si rifanno solo testo e voce).
  1) Claude Sonnet cerca le fonti sul web (ricerca web dell'API) e scrive copione e regia di 9-10 minuti: SOLO fatti delle fonti,
     accuse sempre attribuite e al condizionale, mai citazioni inventate; ogni inquadratura a cartone ha un'immagine NUOVA (mai ripetuta);
     meta' circa clip vere Pexels; il protagonista (la persona della notizia) torna spesso ed e' in copertina
  2) secondo passaggio di verifica: Claude ricontrolla ogni frase sulle fonti e corregge o toglie quelle non provate
  3) traduzione italiana di tutte le parti scritte e dette (le immagini restano quelle del video inglese)
Uscita: notizie/auto/<data>_<slug>_en.json e _it.json. Costo stimato: 0,30-0,60 $ (ricerche web + token).
Env: FILONE (tech), LINGUE (en,it), ANTHROPIC_API_KEY, BUDGET_VIDEO (3), MINUTI (9.5)"""
import datetime as dt, json, os, re, sys, time, urllib.error, urllib.request
from zoneinfo import ZoneInfo

E = os.environ.get
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILONE = (E('FILONE') or 'tech').strip().lower()
OGGI_D = dt.datetime.now(ZoneInfo('Europe/Rome')).date(); OGGI = OGGI_D.isoformat()
MESI_IT = ['GENNAIO', 'FEBBRAIO', 'MARZO', 'APRILE', 'MAGGIO', 'GIUGNO', 'LUGLIO', 'AGOSTO', 'SETTEMBRE', 'OTTOBRE', 'NOVEMBRE', 'DICEMBRE']
LINGUE = [x.strip() for x in (E('LINGUE') or 'en,it').split(',') if x.strip()]
MINUTI = float(E('MINUTI') or 9.5)
PAROLE = int(MINUTI * 150)   # la voce legge circa 150 parole al minuto
VOCI = {'it': 'glnsgBC77wt5zOYU0szz', 'en': E('VOCE_EN') or 'uju3wxzG5OhpWcoi3SMy'}   # 16 nov (Giorgio): inglese = voce E, Michael C. Vincent (eleven_v3)
SPESA = [0.0]


def log(*a):
    print(*a, flush=True)


def claude(messaggi, strumenti=None, max_tokens=32000, sforzo='medium'):
    """Chiamata a Claude Sonnet; con la ricerca web l'API fa le ricerche da sola (pause_turn: si continua)."""
    corpo = {'model': 'claude-sonnet-5-5', 'max_tokens': max_tokens, 'thinking': {'type': 'between_tools'}, 'output_config': {'effort': sforzo},
             'messages': messaggi}
    if strumenti:
        corpo['tools'] = strumenti
    for giro in range(6):
        for k in range(3):
            try:
                req = urllib.request.Request('https://api.anthropic.com/v1/messages', data=json.dumps(corpo).encode(),
                                             headers={'x-api-key': E('ANTHROPIC_API_KEY', ''), 'anthropic-version': '2023-06-01', 'content-type': 'application/json'})
                j = json.loads(urllib.request.urlopen(req, timeout=900).read()); break
            except urllib.error.HTTPError as e:
                log('Claude errore', e.code, e.read()[:300]); time.sleep(20 * (k + 1))
        else:
            raise RuntimeError('Claude non risponde')
        u = j.get('usage') or {}
        ricerche = (u.get('server_tool_use') or {}).get('web_search_requests', 0)
        SPESA[0] += u.get('input_tokens', 0) * 3e-6 + u.get('output_tokens', 0) * 15e-6 + (u.get('cache_read_input_tokens') or 0) * 3e-7 + ricerche * 0.01
        if j.get('stop_reason') == 'pause_turn':   # la ricerca web si e' fermata a meta': si riprende
            corpo['messages'] = corpo['messages'] + [{'role': 'assistant', 'content': j['content']}]
            continue
        return ''.join(b.get('text', '') for b in j['content'] if b.get('type') == 'text')
    raise RuntimeError('troppi giri di ricerca')


def json_da(t):
    a, b = t.find('{'), t.rfind('}')
    return json.loads(t[a:b + 1])


def libreria():
    """Personaggi gia' disegnati (si riusano gratis): caricature/<nome>/<posa>.png"""
    d = os.path.join(ROOT, 'caricature'); out = {}
    for p in sorted(os.listdir(d)) if os.path.isdir(d) else []:
        pose = [x[:-4] for x in os.listdir(os.path.join(d, p)) if x.endswith('.png')]
        if pose:
            out[p] = pose
    return out


SCHEMA = '''{
 "titolo": "YouTube title, max 70 characters, with the person's name, made for the HOMEPAGE (curiosity + stakes), no clickbait lies",
 "angolo": "the angle of this video in one line",
 "descrizione": "YouTube description, 3-5 sentences, first sentence = the title",
 "tag": ["10-15 tags, the first one = the title"],
 "fonti_link": ["every URL you used"],
 "personaggi": {"slug_lowercase": {"commons": "Full Name exactly as on Wikipedia", "chi": "Full Name, role", "pose": {"pose_name": {"posa": "pose and expression, one line, full body"}}}},
 "sfondi": {"unique_key": "cartoon scene description in English, EMPTY of people unless a crowd is needed, no text/logos"},
 "scene": [{"testo": "what the voice says (2-4 sentences)", "fonti": ["URL(s) that prove it"],
   "inquadrature": [
     {"tipo": "cartone", "sfondo": "unique_key", "personaggio": "slug (optional)", "posa": "pose_name", "lato": "dx|sx",
      "grafica": {"tipo": "titolo", "testo": "MAX 22 CHARS", "sotto": "max 48 chars"}, "didascalia": "FULL NAME · ROLE (only first appearance)"},
     {"tipo": "pexels", "q": ["3 English stock-footage searches, real generic footage, no people names, no brands"],
      "grafica": {"tipo": "numero", "valore": 76.5, "decimali": 1, "prefisso": "", "unita": "MILLION EUROS", "sopra": "UP TO", "rosso": false}}
   ]}],
 "copertina": {"sfondo": "unique_key", "personaggio": "slug of the MAIN person", "posa": "pose_name", "lato": "dx|sx", "righe": ["LINE 1", "LINE 2"], "evidenzia": 1}
}'''


def scrivi_en(onda, lib):
    prompt = f"""You are the head writer of a fast, credible tech-news YouTube channel (English, US audience). Format: cartoon editorial
caricatures of the REAL people + real stock footage + animated graphics, like the channel Paper Billions. Today is {OGGI}.

STORY TO COVER: {onda['storia']}
MAIN PERSON (must be the face of the video and of the thumbnail): {onda['persona']} ({onda.get('ruolo', '')}, {onda.get('azienda', '')})
WHAT IS NEW TODAY: {onda.get('novita_oggi', '')}
DAY {onda.get('giorni', 1)} OF THIS WAVE. Angles already used on previous days (do NOT repeat them, find a fresh angle on the latest developments): {onda.get('angoli_fatti') or 'none'}

1) RESEARCH FIRST with web search: the latest facts from reliable outlets (Reuters, Bloomberg, AP, CNBC, FT, WSJ, The Verge, official statements,
SEC filings). Use several sources, cross-check numbers and dates.
2) WRITE the video: about {PAROLE} words of narration in total ({MINUTI} minutes), 45-60 scenes.
RULES (all mandatory):
- ONLY facts found in your sources. Every scene lists the URL(s) that prove it. Never invent quotes, numbers, dates or motives.
- Allegations, reports and rumors: always attributed ("according to Reuters...", "the Financial Times reported...") and never stated as fact.
  Never name private individuals who are not public figures. Be fair: include the other side / official denials when they exist.
- Hook: the first scene says the biggest, most surprising fact in 1-2 short sentences (the result first, then how we got here). No intro, no greetings.
- Rhythm: short sentences, clear and decisive, like an authoritative journalist. Build curiosity every 60-90 seconds ("but that's not the whole story...").
- Last scene: one line asking to subscribe because the story is still moving.
DIRECTION (regia):
- Each scene has 1-3 shots of 4-6 seconds each (about 2.8 words per second of voice).
- About HALF of all shots are "pexels" (real stock footage that matches what is said: offices, chips, servers, stock screens, cities, money,
  smartphones...), the other half "cartone".
- EVERY "cartone" shot uses its OWN new key in "sfondi": a background is NEVER reused (it's like a film: always something new). Background
  descriptions must be coherent with what is said in that moment and specific (place, objects, light, mood).
- The main person appears in a cartone shot at least every 60-90 seconds, with DIFFERENT poses that fit the moment (max 4 poses for the
  main person, 2 for the others). Other real people of the story (founders, CEOs, rivals) only if they are public figures, with their real name.
  Characters already drawn in our library (reuse these slugs and pose names when they fit, it's free): {json.dumps(lib)}
- Graphics: big numbers with "numero" (exact values from sources), key phrases with "titolo" (UPPERCASE). Not every shot needs a graphic.
- "lato": the person stands on the right ("dx") or left ("sx"); alternate.
- Thumbnail (copertina): the main person, 2 short UPPERCASE lines (max 3 words each, high-impact words of the story, no final period), evidenzia = index
  of the line on the red box. Its "sfondo" is a NEW key too.
Answer with ONLY the JSON (no markdown), exactly this structure:
{SCHEMA}"""
    t = claude([{'role': 'user', 'content': prompt}], [{'type': 'web_search_20250305', 'name': 'web_search', 'max_uses': 12}], sforzo='high')
    return json_da(t)


def verifica(v):
    """Secondo passaggio: ogni frase controllata sulle fonti; le frasi non provate si correggono o si tolgono."""
    testi = [{'i': i, 'testo': s['testo'], 'fonti': s.get('fonti', [])} for i, s in enumerate(v['scene'])]
    prompt = ("You are a strict fact-checker for a news video. Check EVERY sentence below against its sources (use web search to open and "
              "verify them, and to verify anything doubtful). A sentence passes only if the sources support it exactly (numbers, dates, names, "
              "who said what). Reports/allegations must be attributed. Return ONLY JSON: "
              '{"correzioni": [{"i": 0, "testo": "corrected sentence(s), same length and tone, or an empty string to drop the scene", "perche": "short reason"}], '
              '"ok": true/false}. Only list scenes that need a change.\n\n' + json.dumps(testi, ensure_ascii=False))
    r = json_da(claude([{'role': 'user', 'content': prompt}], [{'type': 'web_search_20250305', 'name': 'web_search', 'max_uses': 10}], max_tokens=16000))
    tolte = 0
    for c in r.get('correzioni', []):
        i = c.get('i')
        if isinstance(i, int) and 0 <= i < len(v['scene']):
            log(f"verifica scena {i}: {c.get('perche', '')[:120]}")
            v['scene'][i]['testo'] = (c.get('testo') or '').strip()
    prima = len(v['scene'])
    v['scene'] = [s for s in v['scene'] if s['testo']]
    tolte = prima - len(v['scene'])
    v['verifica'] = {'correzioni': len(r.get('correzioni', [])), 'scene_tolte': tolte}
    return v


def traduci_it(v):
    """Tutte le parti scritte e dette in italiano; immagini, clip e personaggi restano identici."""
    voci = []
    def add(chiave, testo):
        if testo:
            voci.append({'k': chiave, 't': testo})
    add('titolo', v.get('titolo')); add('descrizione', v.get('descrizione'))
    for j, t in enumerate(v.get('tag', [])):
        add(f'tag.{j}', t)
    for i, s in enumerate(v['scene']):
        add(f's.{i}', s['testo'])
        for q, inq in enumerate(s['inquadrature']):
            g = inq.get('grafica') or {}
            for c in ('testo', 'sotto', 'unita', 'sopra'):
                add(f'g.{i}.{q}.{c}', g.get(c))
            add(f'd.{i}.{q}', inq.get('didascalia'))
    for j, r in enumerate(v['copertina'].get('righe', [])):
        add(f'c.{j}', r)
    prompt = ("Translate into natural, fluent Italian for an Italian YouTube news channel (authoritative journalist tone, short sentences). "
              "Keep names, numbers and meaning exactly. Texts in UPPERCASE stay UPPERCASE and short (graphics: max 22 chars for 'g.*.testo'). "
              "Use Italian number style in graphics units (e.g. MILIARDI DI DOLLARI). The title (titolo) max 70 chars, for the homepage. "
              'Return ONLY JSON: {"k": "translation", ...} with the same keys.\n\n' + json.dumps(voci, ensure_ascii=False))
    tr = json_da(claude([{'role': 'user', 'content': prompt}], max_tokens=24000, sforzo='low'))
    it = json.loads(json.dumps(v))
    it['titolo'] = tr.get('titolo', v['titolo']); it['descrizione'] = tr.get('descrizione', v.get('descrizione', ''))
    it['tag'] = [tr.get(f'tag.{j}', t) for j, t in enumerate(v.get('tag', []))]
    for i, s in enumerate(it['scene']):
        s['testo'] = tr.get(f's.{i}', s['testo'])
        for q, inq in enumerate(s['inquadrature']):
            g = inq.get('grafica') or {}
            for c in ('testo', 'sotto', 'unita', 'sopra'):
                if g.get(c):
                    g[c] = tr.get(f'g.{i}.{q}.{c}', g[c])
            if inq.get('didascalia'):
                inq['didascalia'] = tr.get(f'd.{i}.{q}', inq['didascalia'])
    it['copertina']['righe'] = [tr.get(f'c.{j}', r) for j, r in enumerate(v['copertina'].get('righe', []))]
    return it


def main():
    onda = json.load(open(os.path.join(ROOT, 'notizie', 'radar', FILONE, 'onda.json')))
    slug = re.sub(r'[^a-z0-9]+', '_', onda['storia'].lower()).strip('_')[:40]
    nome = f'{OGGI}_{slug}'
    v = scrivi_en(onda, libreria())
    log(f"copione EN: {len(v['scene'])} scene, {sum(len(s['testo'].split()) for s in v['scene'])} parole, spesa {SPESA[0]:.3f} $")
    v = verifica(v)
    log(f"verificato: {v['verifica']}, spesa {SPESA[0]:.3f} $")
    base = {'lingua': 'en', 'nome': nome + '_en', 'data': f"{OGGI_D.strftime('%B').upper()} {OGGI_D.day}, {OGGI_D.year}", 'etichetta': 'BREAKING',
            'musica': 'tensione', 'voce': VOCI['en'], 'budget_dollari': float(E('BUDGET_VIDEO') or 3), 'storia': onda['storia'], 'filone': FILONE}
    out = os.path.join(ROOT, 'notizie', 'auto'); os.makedirs(out, exist_ok=True)
    en = dict(v, **base)
    json.dump(en, open(os.path.join(out, nome + '_en.json'), 'w'), ensure_ascii=False, indent=1)
    file_ok = [os.path.join('notizie', 'auto', nome + '_en.json')]
    if 'it' in LINGUE:
        it = traduci_it(v)
        it.update(base, lingua='it', nome=nome + '_it', data=f'{OGGI_D.day} {MESI_IT[OGGI_D.month - 1]} {OGGI_D.year}', etichetta="ULTIM'ORA",
                  voce=VOCI['it'], materiali_da=nome + '_en')
        json.dump(it, open(os.path.join(out, nome + '_it.json'), 'w'), ensure_ascii=False, indent=1)
        file_ok.append(os.path.join('notizie', 'auto', nome + '_it.json'))
    # l'angolo entra tra quelli fatti: domani se si resta sull'onda se ne cerca uno nuovo
    onda.setdefault('angoli_fatti', []).append(v.get('angolo', '')); json.dump(onda, open(os.path.join(ROOT, 'notizie', 'radar', FILONE, 'onda.json'), 'w'), ensure_ascii=False, indent=1)
    log(f"copioni pronti: {file_ok} | titolo: {v.get('titolo')} | spesa Claude {SPESA[0]:.3f} $")
    if os.environ.get('GITHUB_OUTPUT'):
        open(os.environ['GITHUB_OUTPUT'], 'a').write('file=' + ' '.join(file_ok) + '\n')


if __name__ == '__main__':
    main()
