#!/usr/bin/env python3
"""COPIONE NOTIZIA (16 nov 2026). Dalla storia scelta dal radar (notizie/radar/<filone>/onda.json) al file del video per video_notizie.py,
in inglese e in italiano (stesse immagini, si rifanno solo testo e voce).
  1) Claude Sonnet cerca le fonti sul web (ricerca web dell'API) e scrive copione e regia di 9-10 minuti: SOLO fatti delle fonti,
     accuse sempre attribuite e al condizionale, mai citazioni inventate; ogni inquadratura a cartone ha un'immagine NUOVA (mai ripetuta);
     niente Pexels (16 nov sera): solo scene disegnate, mappe, dossier e frasi a effetto (stile dinamico); il protagonista torna spesso ed e' in copertina
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
PAROLE = int(MINUTI * 175)   # 17 nov: la voce legge ~170 parole al minuto e la verifica fatti toglie il 10-15% delle frasi -> si scrive di piu', il video deve restare sopra gli 8 minuti (7:02 e 7:59 il 17 nov)
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


def libreria_luoghi():
    """Luoghi gia' disegnati nei giorni scorsi (gratis), non usati negli ultimi 7 giorni: chi guarda ogni giorno non rivede le stesse immagini."""
    f = os.path.join(ROOT, 'notizie', 'libreria_scene.json')
    if not os.path.exists(f):
        return {}
    limite = (OGGI_D - dt.timedelta(days=7)).isoformat(); out = {}
    for k, e in json.load(open(f)).items():
        if e.get('filone') == FILONE and max(e.get('usato') or ['0']) < limite:
            out[k] = (e.get('luogo') + ': ' if e.get('luogo') else '') + e.get('descr', '')[:140]
    return dict(list(out.items())[-60:])


def libreria():
    """Personaggi gia' disegnati (si riusano gratis): caricature/<nome>/<posa>.png"""
    d = os.path.join(ROOT, 'caricature'); out = {}
    for p in sorted(os.listdir(d)) if os.path.isdir(d) else []:
        pose = [x[:-4] for x in os.listdir(os.path.join(d, p)) if x.endswith('.png')]
        if pose:
            out[p] = pose
    return out


SCHEMA = """{
 "titolo": "YouTube title, max 70 characters, with the main person's name, made for the HOMEPAGE (curiosity + stakes), no clickbait lies",
 "angolo": "the angle of this video in one line",
 "descrizione": "YouTube description, 3-5 sentences, first sentence = the title",
 "tag": ["10-15 tags, the first one = the title"],
 "fonti_link": ["every URL you used"],
 "personaggi": {"slug_lowercase": {"commons": "Full Name exactly as on Wikipedia", "chi": "Full Name, short role", "pose": {"pose_name": {"posa": "pose and expression, one line, full body"}}}},
 "sets": {"unique_key": {"descr": "cartoon scene in English (place, objects, light, mood), EMPTY of people, no text/logos/flags with writing",
                         "luogo": "PLACE, COUNTRY (optional, real place of the scene)", "effetto": "pioggia|neve|mirino|none",
                         "cast": [{"chi": "slug", "posa": "pose_name", "lato": "sx|dx"}], "lib": "library id (optional, only to reuse a library place)"}},
 "scene": [{"testo": "what the narrator says (1-3 short sentences)", "fonti": ["URL(s) that prove it"],
   "capitolo": "CHAPTER TITLE (only on the first scene of a chapter)", "titolo_card": true,
   "visivo": {"tipo": "set", "set": "unique_key"},
   "grafica": {"tipo": "numero", "valore": 76.5, "decimali": 1, "prefisso": "", "unita": "MILLION BARRELS", "sopra": "EVERY DAY"},
   "citazione": {"chi": "slug", "posa": "pose_name", "testo": "the EXACT words this person said, as quoted by the source"}}],
 "copertina": {"sfondo": "dramatic scene description, empty of people", "personaggi": ["slug of the MAIN person", "optional 2nd", "optional 3rd"], "pose": {"slug": "pose_name"}, "personaggio": "slug of the MAIN person", "posa": "pose_name of the main person", "lato": "dx|sx", "righe": ["BIG NUMBER OR 1-2 SHOCK WORDS", "1-2 WORDS"], "box": "2-3 word label (optional)", "evidenzia": 1, "parola": "ONE SHOCK WORD (max 10 chars)", "etichetta": "2-4 word label (max 24 chars)", "domanda": "CURIOSITY QUESTION (max 18 chars)", "frase": "real quote of the main person, max 14 chars, or empty"}
}
Other "visivo" types (use them often, they are free):
 {"tipo": "mappa", "centro": [lon, lat], "larghezza": 24, "paesi": [{"iso": "UKR", "colore": "blu"}, {"iso": "RUS", "colore": "rosso"}],
  "punti": [{"lon": 30.52, "lat": 50.45, "nome": "KYIV"}], "frecce": [{"da": [lon, lat], "a": [lon, lat], "colore": "rosso"}], "zoom_su": [lon, lat]}
   (larghezza = degrees of longitude visible, 8-60; ISO3 codes; colori: rosso, blu, giallo, verde, arancio, viola; real coordinates only)
 {"tipo": "dossier", "chi": "slug", "posa": "pose_name", "righe": ["3 short handwritten facts, max 26 chars each"], "timbro": "ONE OR TWO WORDS"}
 {"tipo": "frase", "testo": "the same short punch sentence the narrator says (max 9 words)"}
"grafica" can also be {"tipo": "titolo", "testo": "MAX 22 CHARS", "sotto": "max 48 chars"}."""


def scrivi_en(onda, lib):
    tipo = {'tech': 'tech-news', 'guerra': 'world-conflicts news (wars, ceasefires, sanctions, military and diplomatic moves)'}.get(FILONE, FILONE + ' news')
    prompt = f"""You are the head writer of a fast, credible {tipo} YouTube channel (English, US audience). Format: our cartoon editorial
caricatures of the REAL people in drawn cartoon scenes + animated maps + animated graphics. Pace and storytelling like the channel Paper Billions:
a story you cannot stop watching, but every word is TRUE. Today is {OGGI}.

STORY TO COVER: {onda['storia']}
MAIN PERSON (must be the face of the video and of the thumbnail): {onda['persona']} ({onda.get('ruolo', '')}, {onda.get('azienda', '')})
WHAT IS NEW TODAY: {onda.get('novita_oggi', '')}
DAY {onda.get('giorni', 1)} OF THIS WAVE. Angles already used on previous days (do NOT repeat them, find a fresh angle on the latest developments): {onda.get('angoli_fatti') or 'none'}

1) RESEARCH FIRST with web search: the latest facts ONLY from authoritative news organizations and official sources (Reuters, AP, Bloomberg, FT, WSJ,
CNBC, BBC, NYT, Al Jazeera, Kyiv Independent, ANSA, Il Sole 24 Ore, Corriere, government and company statements). NEVER use YouTube videos, TikTok,
social posts, Substack, blogs or content farms as sources. The core fact of the video must be confirmed by at least TWO different major outlets
(or an official statement). Say exactly what is confirmed and what is only reported ("is weighing a return, according to the FT" is NOT "is returning").
2) WRITE the video: {int(PAROLE * .9)}-{int(PAROLE * 1.1)} words of narration in total ({MINUTI} minutes; count them, never more), {max(8, int(MINUTI * 11))}-{max(10, int(MINUTI * 13))} scenes.
TRUTH RULES (all mandatory):
- ONLY facts found in your sources. Every scene lists the URL(s) that prove it. Never invent quotes, numbers, dates or motives.
- Allegations, reports and rumors: always attributed ("according to Reuters...") and never stated as fact. Never name private individuals.
  Be fair: include the other side / official denials when they exist. Strictly neutral: no opinions, no mocking; for wars give each side's
  position with attribution; no graphic violence; casualty figures only with their source.
- "citazione": ONLY real statements, word for word as quoted by a source you list (translated to English if needed, as the source did).
  Use 4-7 of them across the video (the key people speaking: leaders, ministers, spokespeople). A second voice reads them.
STORYTELLING (like a documentary, not a list of news):
- COLD OPEN: scene 1-3 drop the viewer into the most dramatic TRUE moment of the story (the result first), then the scene with "titolo_card": true
  (around 20-40 seconds in) where the narrator says the video's big question in one sentence.
- Then 4-6 CHAPTERS ("capitolo" on their first scene, 2-5 words, intriguing, e.g. "THE MAN WITH THE KEY", "48 HOURS IN GENEVA"):
  who the main person is and how they got here (backstory with real facts) -> how the crisis built up -> what happened now -> what it means /
  what happens next (only what officials and analysts quoted by sources say).
- Every 30-45 seconds an OPEN LOOP: announce something concrete that is coming and pay it off later ("in a moment you'll see the one number
  that scared Nvidia's board", "but the real problem was another one"). The viewer must always want to know what happens next, like a thriller.
  Short sentences, decisive, like an authoritative journalist. Tension, stakes, consequences for real people.
- 18 nov (Giorgio: "deve catturare come un film", dati: chi guarda esce presto): in the first 60 seconds the scenes are even SHORTER,
  6-10 words each (a new image every 2-3 seconds), the strongest images and facts first.
- Last scene: one line asking to subscribe because the story is still moving.
DIRECTION (regia) - like a film: EVERY scene has its OWN new drawn image ("set"), shown once (~4-6 seconds), never seen again:
- Scenes are SHORT: 1-2 sentences, 10-16 words. "sets": one NEW set for every scene that is not a map/dossier/frase
  (about {max(6, int(MINUTI * 7))}-{max(8, int(MINUTI * 8))} sets in total). Never reuse a set, never come back to an old one. Every set must
  look clearly different from the previous one (different place or angle, light, colors, time of day, objects in the foreground).
- COHERENCE IS THE MOST IMPORTANT RULE (18 nov, Giorgio): every set must show the exact place, object or situation the narrator talks about
  in THAT scene (a big tech CEO -> the company's HQ, a data center, a chip factory, a keynote stage, a stock exchange floor, a courtroom...;
  never a generic home interior, living room or kitchen unless the sentence is about homes). A viewer must understand the topic from the image alone.
- Each set: concrete and coherent with what is said (real places: the Kremlin office, a Kyiv street at night, a tanker in the Strait of Hormuz,
  the Oval Office, a UN hall...), rich in detail, EMPTY of people (people are only our caricatures in "cast"), NO writing anywhere (no documents,
  newspapers, screens with text, signs, flags with text). "effetto" when it fits (rain at night, snow in Ukraine winter, "mirino" = seen through a
  spy/surveillance camera). "luogo" = the real place shown on screen the first time.
- LIBRARY of places already drawn on previous days (free, not shown in the last 7 days): {json.dumps(libreria_luoghi(), ensure_ascii=False)}
  Reuse one ONLY when it shows exactly the place/subject of that sentence (never just because it is free): add "lib": "<its id>" to the set
  (keep a "descr" anyway). At most 1 set out of 3.
- "cast": 0-2 real people per set, standing on opposite sides (sx/dx), with a pose that fits the moment. The main person appears often
  (max 4 poses for the main person, 2 for the others). Real public figures only. Characters already drawn in our library (reuse these slugs and
  pose names when they fit, it's free): {json.dumps(lib)}
- Use "mappa" for EVERY geographic fact (front lines, cities hit, routes, who borders whom, where troops/ships move): {max(2, int(MINUTI * .8))}+ maps,
  with correct real coordinates, highlighted countries, pins and arrows.
- Use 1-2 "dossier" (who is this person: 3 short real facts) and {max(1, int(MINUTI * .5))}+ "frase" (short punch line, white handwritten text
  over the scene; the narrator says exactly that sentence). Never put "frase" as the first scene.
- "grafica" on many scenes: big exact numbers from sources ("numero") and key phrases ("titolo", UPPERCASE).
- Thumbnail (copertina): the MOST IMPORTANT people of the story as it is trending on the web (our caricatures, listed in "personaggi", main first):
  1 person if the story is mainly about one person; 2 if it is a clash, deal or rivalry between two (e.g. two leaders facing each other);
  up to 3 for a summit, round table or big confrontation. Each one must also be in "personaggi" with the pose given in "pose".
  IMPACT (17 nov, Giorgio: "boom, big face, big text, one strong message"): "righe" = 2 VERY short UPPERCASE lines, max 12 characters each
  (e.g. ["1.336", "DRONES"], ["-$500B", "HE WANTS IT BACK"] -> prefer ["RIVUOLE", "NVIDIA"]); mix a real number and words when the story has a strong number,
  without exaggerating; "box" = optional 2-3 word label that completes the message (e.g. "BOARD SAYS NO"). Everything must be TRUE (never "fired" if he resigned).
  Plus 2 short UPPERCASE lines (max 3 words each, high-impact words of the story,
  no final period); evidenza = index of the line on the red box; a dramatic background empty of people.
  23 nov (Giorgio): the MAIN person in the thumbnail is ALWAYS the most RECOGNIZABLE person linked to the story for the general public
  (e.g. Putin, Trump, Zelensky), never a less known commentator. Also give: "parola" = ONE true shock word for the scene (e.g. "BURNING",
  "COLLAPSED"); "etichetta" = short true label that completes it (e.g. "NEAR NATO"); "domanda" = a curiosity question that claims nothing
  unverified (e.g. "WHO HIT IT?"); "frase" = a REAL short quote said by the main person in this story (in quotes, e.g. "MY FRIEND"), or "" if none.
  The background ("sfondo") must show the strongest moment of the story (fire, collapse, explosion, crowd), bright and clear.
  THUMBNAIL POSE of the main person (23 nov, Giorgio): a CLEAR EMOTION that fits the story (tense, worried, angry, smug, shocked, determined),
  natural and believable, never exaggerated or grotesque. Reuse the library emotion poses when they exist (e.g. putin: teso/arrabbiato/compiaciuto;
  trump: compiaciuto/arrabbiato/preoccupato/sorpreso; zelensky: determinato/preoccupato/arrabbiato); a new one costs 0.08 $ once.
Answer with ONLY the JSON (no markdown), exactly this structure:
{SCHEMA}"""
    t = claude([{'role': 'user', 'content': prompt}], [{'type': 'web_search_20250305', 'name': 'web_search', 'max_uses': 8}], sforzo='medium')
    v = json_da(t)
    # in copertina sempre la persona principale della notizia
    per = v.get('personaggi') or {}; cop = v.setdefault('copertina', {})
    cognome = (onda.get('persona') or '').split()[-1].lower() if onda.get('persona') else ''
    princ = next((k for k, p in per.items() if cognome and cognome in (p.get('chi', '') + ' ' + p.get('commons', '') + ' ' + k).lower()), None)
    if princ and cop.get('personaggio') != princ:
        cop['personaggio'] = princ; cop['posa'] = next(iter(per[princ].get('pose') or {'posa': ''}))
    # 17 nov (Giorgio): 1, 2 o 3 persone in copertina (le piu' importanti della notizia), la principale sempre per prima
    lista = [x for x in (cop.get('personaggi') or []) if x in per]
    if cop.get('personaggio') in per and cop['personaggio'] not in lista[:1]:
        lista = [cop['personaggio']] + [x for x in lista if x != cop['personaggio']]
    cop['personaggi'] = lista[:3]
    cop['pose'] = {x: (cop.get('pose') or {}).get(x) if (cop.get('pose') or {}).get(x) in (per[x].get('pose') or {}) else
                   (cop.get('posa') if x == cop.get('personaggio') else next(iter(per[x].get('pose') or {'posa': ''}))) for x in cop['personaggi']}
    return v


def verifica(v):
    """Secondo passaggio: ogni frase controllata sulle fonti; le frasi non provate si correggono o si tolgono."""
    testi = [{'i': i, 'testo': s['testo'], 'fonti': s.get('fonti', []), **({'citazione_testuale': s['citazione'].get('testo', '')} if s.get('citazione') else {})}
             for i, s in enumerate(v['scene'])]
    prompt = ("You are a strict fact-checker for a news video. Sources must be authoritative news organizations or official statements: any sentence "
              "that relies on YouTube, social media, blogs or unknown sites must be corrected using a reliable source or dropped. Reports and rumors must "
              "never sound like confirmed facts. Check EVERY sentence below against its sources (use web search to open and "
              "verify them, and to verify anything doubtful). A sentence passes only if the sources support it exactly (numbers, dates, names, "
              "who said what). Reports/allegations must be attributed. Return ONLY JSON: "
              '{"correzioni": [{"i": 0, "testo": "corrected sentence(s), same length and tone, or an empty string to drop the scene", "togli_citazione": false, "perche": "short reason"}], '
              '"citazione_testuale" must be the exact words reported by a reliable source, otherwise set togli_citazione true. '
              '"ok": true/false}. Only list scenes that need a change.\n\n' + json.dumps(testi, ensure_ascii=False))
    r = json_da(claude([{'role': 'user', 'content': prompt}], [{'type': 'web_search_20250305', 'name': 'web_search', 'max_uses': 6}], max_tokens=16000))
    tolte = 0
    for c in r.get('correzioni', []):
        i = c.get('i')
        if isinstance(i, int) and 0 <= i < len(v['scene']):
            log(f"verifica scena {i}: {c.get('perche', '')[:120]}")
            if 'testo' in c:
                v['scene'][i]['testo'] = (c.get('testo') or '').strip()
                f = (v['scene'][i].get('visivo') or {})
                if f.get('tipo') == 'frase' and v['scene'][i]['testo']:
                    if len(v['scene'][i]['testo'].split()) <= 14:
                        f['testo'] = v['scene'][i]['testo']   # la frase a schermo resta uguale a quella detta
                    else:   # la frase corretta e' diventata lunga: torna una scena normale
                        prec = next((x.get('visivo', {}).get('set') for x in reversed(v['scene'][:i]) if (x.get('visivo') or {}).get('tipo', 'set') == 'set'), None)
                        v['scene'][i]['visivo'] = {'tipo': 'set', 'set': prec} if prec else f
            if c.get('togli_citazione'):
                v['scene'][i].pop('citazione', None)
    prima = len(v['scene'])
    v['scene'] = [s for s in v['scene'] if s['testo']]
    tolte = prima - len(v['scene'])
    v['verifica'] = {'correzioni': len(r.get('correzioni', [])), 'scene_tolte': tolte}
    return v


def coerenza(v):
    """18 nov (Giorgio): "le immagini devono essere estremamente coerenti con quello che dice la voce: se parla di una big tech e' inutile
    mostrare l'interno di una casa". Dopo la verifica dei fatti (che cambia alcune frasi) ogni scena disegnata si confronta con la sua frase:
    i luoghi che non c'entrano si riscrivono (e non si riusano dalla libreria). Solo testo: pochi centesimi."""
    sets = v.get('sets') or {}
    righe = []
    for i, sc in enumerate(v['scene']):
        vi = sc.get('visivo') or {}
        if vi.get('tipo', 'set') == 'set' and vi.get('set') in sets:
            st = sets[vi['set']]
            righe.append({'i': i, 'set': vi['set'], 'voce': sc['testo'], 'scena': st.get('descr', ''), 'luogo': st.get('luogo', '')})
    if not righe:
        return v
    prompt = ("You are the art director of a news explainer video. For each scene below you get what the NARRATOR says and the DRAWN SCENE shown "
              "at that moment. The image must show the exact place, object or situation the narrator talks about, so that the viewer understands the "
              "topic from the image alone (a big tech company -> its HQ, data center, keynote stage, chip factory, trading floor; a war -> the real "
              "front, city, base, port; never a generic home interior or unrelated place). For every scene that is NOT clearly coherent, write a new "
              "scene description: concrete real place, rich detail, EMPTY of people, no text/logos/flags with writing, different from the other "
              'scenes. Return ONLY JSON: {"rifare": [{"set": "key", "descr": "new scene in English", "luogo": "PLACE, COUNTRY or empty", '
              '"perche": "short reason"}]} (empty list if all are coherent).\n\n' + json.dumps(righe, ensure_ascii=False))
    try:
        r = json_da(claude([{'role': 'user', 'content': prompt}], max_tokens=8000, sforzo='low'))
    except Exception as e:
        log('coerenza immagini non controllata:', str(e)[:120]); return v
    n = 0
    for x in r.get('rifare', []):
        k = x.get('set')
        if k in sets and x.get('descr'):
            log(f"coerenza: scena {k} rifatta ({x.get('perche', '')[:100]})")
            sets[k]['descr'] = x['descr']; sets[k].pop('lib', None)
            if 'luogo' in x:
                sets[k]['luogo'] = x.get('luogo') or ''
            n += 1
    v['coerenza'] = {'scene_rifatte': n, 'controllate': len(righe)}
    return v


def traduci_it(v):
    """Tutte le parti scritte e dette in italiano; scene disegnate, mappe e personaggi restano identici."""
    voci = []
    def add(chiave, testo):
        if testo:
            voci.append({'k': chiave, 't': testo})
    add('titolo', v.get('titolo')); add('descrizione', v.get('descrizione'))
    for j, t in enumerate(v.get('tag', [])):
        add(f'tag.{j}', t)
    for k, st in (v.get('sets') or {}).items():
        add(f'l.{k}', st.get('luogo'))
    for k, pp in (v.get('personaggi') or {}).items():   # ruolo a schermo (etichetta col nome) in italiano
        add(f'p.{k}', pp.get('chi'))
    for i, s in enumerate(v['scene']):
        add(f's.{i}', s['testo']); add(f'cap.{i}', s.get('capitolo')); add(f'cit.{i}', (s.get('citazione') or {}).get('testo'))
        g = s.get('grafica') or {}
        for c in ('testo', 'sotto', 'unita', 'sopra'):
            add(f'g.{i}.{c}', g.get(c))
        vi = s.get('visivo') or {}
        add(f'fr.{i}', vi.get('testo') if vi.get('tipo') == 'frase' else None); add(f'tb.{i}', vi.get('timbro'))
        for j, r in enumerate(vi.get('righe') or []):
            add(f'r.{i}.{j}', r)
        for j, pt in enumerate(vi.get('punti') or []):
            add(f'pt.{i}.{j}', pt.get('nome'))
    for j, r in enumerate(v['copertina'].get('righe', [])):
        add(f'c.{j}', r)
    if (v.get('copertina') or {}).get('box'):
        add('c.box', v['copertina']['box'])
    for c_ in ('parola', 'etichetta', 'domanda', 'frase'):
        add('c.' + c_, (v.get('copertina') or {}).get(c_))
    prompt = ("Translate into natural, fluent Italian for an Italian YouTube news channel (authoritative journalist tone, short sentences). "
              "Keep names, numbers and meaning exactly. Texts in UPPERCASE stay UPPERCASE and short (graphics: max 22 chars for 'g.*.testo'). "
              "Use Italian number style in graphics units (e.g. MILIARDI DI DOLLARI). The title (titolo) max 70 chars, for the homepage. "
              "'p.*' are 'Full Name, role': keep the name, translate only the role. 'fr.N' must be exactly the same words as the matching sentence in 's.N'. Quotes ('cit.*') are translated faithfully, word for word. "
              'Return ONLY JSON: {"k": "translation", ...} with the same keys.\n\n' + json.dumps(voci, ensure_ascii=False))
    tr = json_da(claude([{'role': 'user', 'content': prompt}], max_tokens=24000, sforzo='low'))
    it = json.loads(json.dumps(v))
    it['titolo'] = tr.get('titolo', v['titolo']); it['descrizione'] = tr.get('descrizione', v.get('descrizione', ''))
    it['tag'] = [tr.get(f'tag.{j}', t) for j, t in enumerate(v.get('tag', []))]
    for k, pp in (it.get('personaggi') or {}).items():
        if pp.get('chi'):
            pp['chi'] = tr.get(f'p.{k}', pp['chi'])
    for k, st in (it.get('sets') or {}).items():
        if st.get('luogo'):
            st['luogo'] = tr.get(f'l.{k}', st['luogo'])
    for i, s in enumerate(it['scene']):
        s['testo'] = tr.get(f's.{i}', s['testo'])
        if s.get('capitolo'):
            s['capitolo'] = tr.get(f'cap.{i}', s['capitolo'])
        if (s.get('citazione') or {}).get('testo'):
            s['citazione']['testo'] = tr.get(f'cit.{i}', s['citazione']['testo'])
        g = s.get('grafica') or {}
        for c in ('testo', 'sotto', 'unita', 'sopra'):
            if g.get(c):
                g[c] = tr.get(f'g.{i}.{c}', g[c])
        vi = s.get('visivo') or {}
        if vi.get('tipo') == 'frase' and vi.get('testo'):
            vi['testo'] = tr.get(f'fr.{i}', vi['testo'])
        if vi.get('timbro'):
            vi['timbro'] = tr.get(f'tb.{i}', vi['timbro'])
        vi['righe'] = [tr.get(f'r.{i}.{j}', r) for j, r in enumerate(vi.get('righe') or [])] or vi.get('righe')
        for j, pt in enumerate(vi.get('punti') or []):
            if pt.get('nome'):
                pt['nome'] = tr.get(f'pt.{i}.{j}', pt['nome'])
        if not vi.get('righe'):
            vi.pop('righe', None)
    it['copertina']['righe'] = [tr.get(f'c.{j}', r) for j, r in enumerate(v['copertina'].get('righe', []))]
    if v['copertina'].get('box'):
        it['copertina']['box'] = tr.get('c.box', v['copertina']['box'])
    for c_ in ('parola', 'etichetta', 'domanda', 'frase'):
        if v['copertina'].get(c_):
            it['copertina'][c_] = tr.get('c.' + c_, v['copertina'][c_])
    return it


MIN_PAROLE = int(E('MIN_PAROLE') or 1250)   # 24 nov (Giorgio): video sopra gli 8 minuti; la voce EN legge ~140 parole/min (863 parole = 6:12)


def allunga(v):
    """24 nov (Giorgio): "tutti i video sopra gli 8 minuti, raccogliendo piu' informazioni, ma senza inventare: se non ci sono, si va avanti".
    Se il copione e' corto, Claude cerca altri fatti VERI (contesto, cronologia, persone, numeri, reazioni, cosa succede ora) e li aggiunge
    come scene nuove con le loro fonti; poi la verifica dei fatti ricontrolla tutto. Al massimo 2 giri."""
    for giro in range(2):
        n = sum(len(sc['testo'].split()) for sc in v['scene'])
        if n >= MIN_PAROLE * .95:
            break
        riass = [{'i': i, 'testo': sc['testo'], 'capitolo': sc.get('capitolo', '')} for i, sc in enumerate(v['scene'])]
        usati = sorted(v.get('sets') or {}); prossimo = len(usati) + 1
        prompt = f"""This is the narration of a news video ("{v.get('titolo')}"), {n} words. It must reach about {MIN_PAROLE + 100} words (over 8 minutes),
but ONLY with TRUE facts from reliable sources: NEVER invent, never pad with opinions or repetitions. Use web search to find more verified material on this
story: background and history, the timeline hour by hour, who the key people are, real numbers, official statements, reactions, what happens next.
Write new scenes in the same style (1-2 short sentences, 10-16 words, spoken narration, same language as the script) and say after which existing
scene each group goes (index "dopo"), so the story stays in order and the hook/structure are not broken. Every new scene has its sources and a NEW drawn set
(ids from s{prossimo:02d} on) described like the existing ones: {json.dumps(dict(list((v.get('sets') or {}).items())[:2]), ensure_ascii=False)[:600]}
If there is not enough real material, add only what is true (even nothing).
SCRIPT: {json.dumps(riass, ensure_ascii=False)}
Answer ONLY JSON: {{"aggiunte": [{{"dopo": 12, "scene": [{{"testo": "...", "fonti": ["https://..."], "visivo": {{"tipo": "set", "set": "s{prossimo:02d}"}}}}]}}], "sets": {{"s{prossimo:02d}": {{"descr": "...", "luogo": "...", "effetto": "none", "cast": []}}}}}}"""
        try:
            r = json_da(claude([{'role': 'user', 'content': prompt}], [{'type': 'web_search_20250305', 'name': 'web_search', 'max_uses': 8}], max_tokens=24000))
        except Exception as e:
            log('allungamento non riuscito:', str(e)[:120]); break
        v.setdefault('sets', {}).update({k: x for k, x in (r.get('sets') or {}).items() if k not in v['sets']})
        agg = sorted([a for a in r.get('aggiunte') or [] if isinstance(a.get('dopo'), int) and a.get('scene')], key=lambda a: -a['dopo'])
        tot = 0
        for a in agg:
            nuove = [sc for sc in a['scene'] if sc.get('testo') and sc.get('fonti') and (sc.get('visivo') or {}).get('set') in v['sets']]
            pos = max(0, min(len(v['scene']), a['dopo'] + 1)); v['scene'][pos:pos] = nuove; tot += len(nuove)
        log(f"allungato (giro {giro + 1}): +{tot} scene, ora {sum(len(sc['testo'].split()) for sc in v['scene'])} parole, spesa {SPESA[0]:.3f} $")
        if not tot:
            break
    return v


def main():
    onda = json.load(open(os.path.join(ROOT, 'notizie', 'radar', FILONE, 'onda.json')))
    slug = re.sub(r'[^a-z0-9]+', '_', onda['storia'].lower()).strip('_')[:40]
    nome = f'{OGGI}_{slug}' + ('_prova' if (E('PROVA') or 'NO').upper() == 'SI' else '')
    v = scrivi_en(onda, libreria())
    log(f"copione EN: {len(v['scene'])} scene, {sum(len(s['testo'].split()) for s in v['scene'])} parole, spesa {SPESA[0]:.3f} $")
    if (E('ALLUNGA') or 'NO').upper() == 'SI':   # acceso solo con l'OK di Giorgio (costa immagini in piu')
        v = allunga(v)
    v = verifica(v)
    log(f"verificato: {v['verifica']}, spesa {SPESA[0]:.3f} $")
    v = coerenza(v)
    log(f"coerenza immagini: {v.get('coerenza')}, spesa {SPESA[0]:.3f} $")
    base = {'lingua': 'en', 'nome': nome + '_en', 'data': f"{OGGI_D.strftime('%B').upper()} {OGGI_D.day}, {OGGI_D.year}", 'etichetta': 'BREAKING',
            'musica': 'tensione', 'voce': VOCI['en'], 'budget_dollari': round(max(1.2, float(E('BUDGET_VIDEO') or 3) - SPESA[0]), 2), 'storia': onda['storia'], 'filone': FILONE}
    out = os.path.join(ROOT, 'notizie', 'auto'); os.makedirs(out, exist_ok=True)
    en = dict(v, **base)
    json.dump(en, open(os.path.join(out, nome + '_en.json'), 'w'), ensure_ascii=False, indent=1)
    file_ok = [os.path.join('notizie', 'auto', nome + '_en.json')]
    if 'it' in LINGUE:
        it = traduci_it(v)
        it.update(base, budget_dollari=0.6, lingua='it', nome=nome + '_it', data=f'{OGGI_D.day} {MESI_IT[OGGI_D.month - 1]} {OGGI_D.year}', etichetta="ULTIM'ORA",
                  voce=VOCI['it'], materiali_da=nome + '_en')
        json.dump(it, open(os.path.join(out, nome + '_it.json'), 'w'), ensure_ascii=False, indent=1)
        file_ok.append(os.path.join('notizie', 'auto', nome + '_it.json'))
    # l'angolo entra tra quelli fatti: domani se si resta sull'onda se ne cerca uno nuovo
    if (E('PROVA') or 'NO').upper() != 'SI':   # una prova non consuma l'angolo di domani
        onda.setdefault('angoli_fatti', []).append(v.get('angolo', '')); json.dump(onda, open(os.path.join(ROOT, 'notizie', 'radar', FILONE, 'onda.json'), 'w'), ensure_ascii=False, indent=1)
    log(f"copioni pronti: {file_ok} | titolo: {v.get('titolo')} | spesa Claude {SPESA[0]:.3f} $")
    if os.environ.get('GITHUB_OUTPUT'):
        open(os.environ['GITHUB_OUTPUT'], 'a').write('file=' + ' '.join(file_ok) + '\n')


if __name__ == '__main__':
    main()
