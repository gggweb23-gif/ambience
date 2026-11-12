#!/usr/bin/env python3
"""KAO A CARTONE (11 nov 2026, Giorgio: "video KAO interamente a cartone con il personaggio KAO, dinamici e piu' coerenti con il canale
rispetto a Pexels, fino a 1 EUR a video"). Il video e' un piccolo cartone con una trama visiva:
  1) copione + regia (Claude Sonnet): per ogni frase la posa di KAO (libreria personaggi/kao, 32 pose), il luogo, l'inquadratura,
     un personaggio secondario quando si parla di altri, la parola chiave da mostrare nella nuvoletta;
  2) voce ElevenLabs del canale (con i tempi di ogni lettera: sottotitoli parola per parola e nuvolette sincronizzate);
  3) luoghi a cartone nello stesso stile di KAO (FLUX.2 Klein, circa 0,02 $ l'uno), salvati in personaggi/kao/luoghi: si riusano
     nei video successivi, quindi la spesa scende video dopo video;
  4) montaggio in codice: entrata a scatto del personaggio, respiro, camminate, spinta lenta sullo sfondo, cambio di inquadratura
     a meta' delle frasi lunghe, nuvoletta bianca con scritta magenta (stile copertine KAO), "pop" a ogni cambio, musica bassa;
  5) video finale a 1440p.
PAYLOAD: {"tema", "minuti" (1 = prova da un minuto), "voce" (voice_id), "cartella"}."""
import base64, hashlib, shutil, io, json, math, os, random, re, subprocess, sys, time, urllib.request
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'strumenti'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import motore_yt as YT
import costi as CO

E = os.environ.get
P = json.loads(E('PAYLOAD') or '{}')
TEMA = str(P.get('tema') or 'Perché le persone sensibili si stancano prima degli altri').strip()
MINUTI = float(P.get('minuti') or 1)
VOCE = str(P.get('voce') or 'glnsgBC77wt5zOYU0szz')
CART = P.get('cartella') or 'prove_video/kao_cartone'
PERS = 'personaggi/kao'
LUOGHI = os.path.join(PERS, 'luoghi')
LAV = '/tmp/kao_cartone'
for d_ in (CART, LUOGHI, LAV):
    os.makedirs(d_, exist_ok=True)
W, H, FPS = 1920, 1080, 30
MAGENTA, GIALLO, NERO, BIANCO = (216, 27, 142), (242, 179, 61), (20, 20, 25), (255, 255, 255)
CFG = json.load(open(os.path.join(PERS, 'pose.json')))
POSE, SECONDARI = CFG['pose'], CFG['secondari']
STILE_LUOGO = ('Flat 2D cartoon background illustration in the SAME style as a simple modern explainer cartoon: thick clean black outlines, '
               'flat colours, soft warm palette, simple shapes, no gradients, no texture. Wide shot at eye level, the floor is visible in the lower '
               'quarter of the image. EMPTY place: no people, no animals, no characters, no text, no letters, no logos. ')
log = YT.log
SENZA_SOTTOTITOLI = False   # True quando il montaggio KAO mette i suoi sottotitoli (render_kao.py)


def font(nome, url):
    f = os.path.join(LAV, nome)
    if not os.path.exists(f):
        open(f, 'wb').write(YT.http(url, raw=True, timeout=120))
    return f


F_SUB = font('archivo.ttf', 'https://github.com/google/fonts/raw/main/ofl/archivoblack/ArchivoBlack-Regular.ttf')
F_NUV = font('luckiest.ttf', 'https://github.com/google/fonts/raw/main/apache/luckiestguy/LuckiestGuy-Regular.ttf')


# ============================================================ 1) COPIONE E REGIA
def claude(prompt, max_tokens=16000):
    req = urllib.request.Request('https://api.anthropic.com/v1/messages', data=json.dumps({
        'model': 'claude-sonnet-5-5', 'max_tokens': max_tokens, 'thinking': {'type': 'between_tools'}, 'output_config': {'effort': 'low'},
        'messages': [{'role': 'user', 'content': prompt}]}).encode(),
        headers={'x-api-key': E('ANTHROPIC_API_KEY', ''), 'anthropic-version': '2023-06-01', 'content-type': 'application/json'})
    j = json.loads(urllib.request.urlopen(req, timeout=600).read())
    CO.registra('claude', 'claude-sonnet-5-5', usage=j.get('usage'), nota='copione KAO cartone')
    t = ''.join(b.get('text', '') for b in j['content'] if b.get('type') == 'text')
    return json.loads(t[t.find('{'): t.rfind('}') + 1])


def copione():
    f = os.path.join(CART, 'copione.json')
    if os.path.exists(f):
        return json.load(open(f))
    parole = int(MINUTI * 150)
    prompt = f"""Sei l'autore del canale YouTube italiano KAO PSICOLOGIA: psicologia spiegata in modo semplice, caldo e diretto, dando del tu allo spettatore.
Il video e' un CARTONE ANIMATO con un solo protagonista, KAO (omino calvo con la maglia magenta), che vive la situazione di cui si parla.
Tema del video: "{TEMA}". Lunghezza: circa {parole} parole di parlato in italiano ({MINUTI:g} minuti).
Regole del copione: parti SUBITO con un gancio forte (la cosa piu' sorprendente prima), spiega il problema con esempi di vita quotidiana italiana,
dai punti di vista utili senza giudizi assoluti, niente elenchi di dati.{' Inserisci a meta una domanda che invita a rispondere nei commenti.' if MINUTI >= 3 else ''}
Dividi il parlato in scene di 1-2 frasi (8-24 parole). Per ogni scena sei anche il REGISTA: la scena deve far VEDERE quello che la voce dice,
come in un film a cartoni con una trama visiva continua (stesso luogo per piu' scene di fila, si cambia luogo solo quando la storia si sposta).
Pose di KAO disponibili (scegli SOLO tra queste): {json.dumps({k: v[:70] for k, v in POSE.items()}, ensure_ascii=False)}
Personaggi secondari disponibili (opzionali, solo quando la frase parla di un'altra persona): {json.dumps({k: v[:60] for k, v in SECONDARI.items()}, ensure_ascii=False)}
Rispondi SOLO con JSON:
{{"titolo": "...",
 "luoghi": [{{"id": "soggiorno", "prompt_en": "a cosy Italian living room with a sofa, a window and a lamp"}}],
 "scene": [{{"testo": "parlato della scena", "luogo": "id del luogo", "posa": "posa di KAO", "posa2": "seconda posa per la seconda meta' della scena (facoltativa, diversa dalla prima)",
            "inquadratura": "larga|media|stretta", "secondario": "id del personaggio secondario o ''", "parola": "1-3 parole chiave da mostrare grandi in una nuvoletta (solo in circa meta' delle scene, altrimenti '')"}}]}}
Luoghi: {max(2, int(MINUTI * 2.5))}-{max(3, int(MINUTI * 3.5))} in tutto, luoghi italiani di tutti i giorni (casa, ufficio, strada, bar, parco, cucina, camera da letto),
descritti in inglese senza persone. Alterna le inquadrature (mai 3 uguali di fila). Varia le pose: mai la stessa posa in due scene di fila."""
    c = claude(prompt)
    c['scene'] = [s for s in c.get('scene', []) if str(s.get('testo') or '').strip()]
    for s in c['scene']:
        for k in ('posa', 'posa2'):
            if s.get(k) and s[k] not in POSE:
                s[k] = 'parla' if k == 'posa' else ''
        if s.get('secondario') and s['secondario'] not in SECONDARI:
            s['secondario'] = ''
    json.dump(c, open(f, 'w'), ensure_ascii=False, indent=1)
    log('copione:', len(c['scene']), 'scene,', sum(len(s['testo'].split()) for s in c['scene']), 'parole,', len(c.get('luoghi', [])), 'luoghi')
    return c


# ============================================================ 2) VOCE
def voce(c):
    prec = ''
    for i, s in enumerate(c['scene']):
        os.makedirs(os.path.join(CART, 'voce'), exist_ok=True)
        f = os.path.join(CART, 'voce', f'voce_{i:02d}.mp3')
        if not os.path.exists(f):
            dopo = ' '.join(x['testo'] for x in c['scene'][i + 1:])[:400]
            for k in range(4):
                try:
                    req = urllib.request.Request(f'https://api.elevenlabs.io/v1/text-to-speech/{VOCE}/with-timestamps?output_format=mp3_44100_128',
                                                 data=json.dumps({'text': s['testo'], 'model_id': 'eleven_multilingual_v2', 'previous_text': prec[-400:], 'next_text': dopo,
                                                                  'voice_settings': {'stability': .5, 'similarity_boost': .75}}).encode(),
                                                 headers={'xi-api-key': E('ELEVENLABS_API_KEY', ''), 'Content-Type': 'application/json'})
                    j = json.loads(urllib.request.urlopen(req, timeout=180).read())
                    open(f, 'wb').write(base64.b64decode(j['audio_base64']))
                    json.dump(j.get('alignment') or {}, open(f[:-4] + '.json', 'w'))
                    CO.registra('elevenlabs', 'eleven_multilingual_v2', crediti=len(s['testo']))
                    break
                except Exception as e:
                    log('voce non riuscita, riprovo:', str(e)[:120]); time.sleep(5)
            else:
                raise RuntimeError('voce non riuscita per la scena %d' % i)
        prec += ' ' + s['testo']
        s['_audio'] = f
        s['_dur'] = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f], capture_output=True, text=True).stdout.strip())
        s['_parole'] = parole_tempi(json.load(open(f[:-4] + '.json')), s['_dur'])
    log('voce:', round(sum(s['_dur'] for s in c['scene']), 1), 's')


def parole_tempi(al, dur):
    """Parole con inizio e fine (secondi) dai tempi lettera per lettera di ElevenLabs."""
    ch, a, b = al.get('characters') or [], al.get('character_start_times_seconds') or [], al.get('character_end_times_seconds') or []
    out, cur, t0, t1 = [], '', None, None
    for c_, s_, e_ in zip(ch, a, b):
        if c_.isspace():
            if cur:
                out.append([cur, t0, t1]); cur = ''
            continue
        if not cur:
            t0 = s_
        cur += c_; t1 = e_
    if cur:
        out.append([cur, t0, t1])
    return out


# ============================================================ 3) LUOGHI (libreria che cresce)
def klein(prompt, f):
    hd = {'Authorization': 'Key ' + E('FAL_KEY', '')}
    inv = YT.http('https://queue.fal.run/fal-ai/flux-2/klein/4b', {'prompt': prompt, 'image_size': {'width': 1920, 'height': 1080}, 'num_images': 1, 'output_format': 'png'}, hd, timeout=120)
    for _ in range(150):
        time.sleep(2)
        if YT.http(inv['status_url'], headers=hd, timeout=60).get('status') == 'COMPLETED':
            break
    u = YT.http(inv['response_url'], headers=hd, timeout=60)['images'][0]['url']
    Image.open(io.BytesIO(YT.http(u, raw=True, timeout=120))).convert('RGB').save(f, quality=95)
    CO.registra('fal', 'flux-2-klein-4b', dollari=0.02, nota='luogo KAO cartone')


def luoghi(c):
    mappa = {}
    for l in c.get('luoghi', []):
        nome = re.sub(r'[^a-z0-9]+', '_', (l.get('prompt_en') or l['id']).lower())[:60].strip('_')
        f = os.path.join(LUOGHI, nome + '.jpg')
        if not os.path.exists(f):
            klein(STILE_LUOGO + 'Place: ' + l.get('prompt_en', l['id']) + '.', f)
            log('luogo nuovo:', nome)
        else:
            log('luogo dalla libreria (gratis):', nome)
        mappa[l['id']] = Image.open(f).convert('RGB').resize((int(W * 1.12), int(H * 1.12)), Image.LANCZOS)
    primo = next(iter(mappa.values()))
    for s in c['scene']:
        s['_bg'] = mappa.get(s.get('luogo')) or primo


# ============================================================ 4) MONTAGGIO
POSE_IMG = {}


def posa(nome, secondario=False):
    k = ('s:' if secondario else 'p:') + nome
    if k not in POSE_IMG:
        POSE_IMG[k] = Image.open(os.path.join(PERS, 'secondari' if secondario else 'pose', nome + '.png')).convert('RGBA')
    return POSE_IMG[k]


LARGHE = {'seduto_divano', 'seduto_sedia', 'computer', 'dorme', 'medita', 'solo_pensa'}
ALTEZZA = {'larga': .66, 'media': .86, 'stretta': 1.18}


def ease(x):
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


def pop(t, durata=.28):
    """Scala dell'entrata a scatto: 0.9 -> 1.04 -> 1.0."""
    if t >= durata:
        return 1.0
    x = t / durata
    return 0.9 + 0.14 * ease(x / .7) if x < .7 else 1.04 - 0.04 * ease((x - .7) / .3)


def disegna_personaggio(fr, img, cx, piedi, alt, t, flip=False, entrata=0.0, mov=0.0):
    sc = pop(t - entrata)
    resp = 1 + 0.012 * math.sin(2 * math.pi * t / 1.7)   # respiro
    h = int(alt * sc * resp); w = int(img.width * (alt * sc) / img.height)
    if h < 10 or w < 10:
        return
    im = img.resize((w, h), Image.BILINEAR)
    if flip:
        im = ImageOps.mirror(im)
    incolla(fr, im, int(cx + mov - w / 2), int(piedi - h))


def incolla(fr, im, x, y):
    """alpha_composite che accetta anche posizioni fuori dal quadro (inquadratura stretta: testa in alto, gambe tagliate)."""
    l, t = max(0, -x), max(0, -y); r, b = min(im.width, W - x), min(im.height, H - y)
    if r > l and b > t:
        fr.alpha_composite(im.crop((l, t, r, b)), (x + l, y + t))


def nuvoletta(fr, testo, t, dx_lato, centro=False, posto=None):
    s = ease(t / .22) * (1.0 if t > .22 else 1.08)
    if s <= .05:
        return
    testo = testo.upper()
    size = 110
    f = ImageFont.truetype(F_NUV, size)
    while f.getlength(testo) > W * .38 and size > 50:
        size -= 6; f = ImageFont.truetype(F_NUV, size)
    tw = int(f.getlength(testo)); th = size
    card = Image.new('RGBA', (tw + 90, th + 80), (0, 0, 0, 0)); d = ImageDraw.Draw(card)
    d.rounded_rectangle((6, 6, card.width - 6, card.height - 6), 36, fill=BIANCO, outline=NERO, width=7)
    d.text((45, 46), testo, font=f, fill=MAGENTA)
    rot = 3 if dx_lato else -3
    card = card.rotate(rot, expand=True, resample=Image.BICUBIC)
    card = card.resize((max(1, int(card.width * s)), max(1, int(card.height * s))), Image.BILINEAR)
    cx = int(W * (.5 if centro else .73 if dx_lato else .27)); cy = int(H * (.13 if centro else .2))
    if posto:
        cx, cy = int(posto[0]), int(posto[1])
    incolla(fr, card, cx - card.width // 2, cy - card.height // 2)


def sottotitolo(fr, parole, t):
    """3 parole alla volta, la parola detta in giallo (come i sottotitoli dei video KAO)."""
    if not parole:
        return
    i = max([k for k, p in enumerate(parole) if p[1] <= t] or [0])
    g = i // 3 * 3; grp = parole[g:g + 3]
    if t > grp[-1][2] + .4 and g + 3 >= len(parole):
        return
    f = ImageFont.truetype(F_SUB, 76); d = ImageDraw.Draw(fr)
    testi = [p[0] for p in grp]; tot = sum(f.getlength(x) for x in testi) + 22 * (len(testi) - 1)
    x = (W - tot) / 2; y = H - 150
    for k, x_ in enumerate(testi):
        d.text((x, y), x_, font=f, fill=GIALLO if g + k == i else BIANCO, stroke_width=7, stroke_fill=NERO)
        x += f.getlength(x_) + 22


def inquadrature(c):
    """Ogni scena 1 o 2 inquadrature (frasi lunghe: cambio a meta' con posa2 e un'altra inquadratura)."""
    out, lato, t0 = [], 0, 0.0
    ordine = ['larga', 'media', 'stretta']
    for i, s in enumerate(c['scene']):
        q = s.get('inquadratura') if s.get('inquadratura') in ALTEZZA else ordine[i % 3]
        if s.get('secondario'):
            q = 'larga'   # con un altro personaggio: tutti e due interi, nessuno tagliato
        lato = 1 - lato if (i == 0 or s.get('luogo') != c['scene'][i - 1].get('luogo') or i % 2 == 0) else lato   # MANO LIBERA: KAO cambia lato
        pezzi = [(0.0, s['_dur'], s.get('posa') or 'parla', q)]
        if s['_dur'] > 5.5 and s.get('posa2'):
            m = s['_dur'] / 2
            pezzi = [(0.0, m, s.get('posa') or 'parla', q), (m, s['_dur'], s['posa2'], q if s.get('secondario') else ordine[(ordine.index(q) + 1) % 3])]
        for a, b, p, qq in pezzi:
            out.append({'t0': t0 + a, 't1': t0 + b, 'scena': s, 'posa': p, 'q': qq, 'lato': lato, 'rel': a})
        t0 += s['_dur']
    return out, t0


def monta(c):
    shots, totale = inquadrature(c)
    log('inquadrature:', len(shots), '| durata', round(totale, 1), 's')
    out = os.path.join(LAV, 'video_muto.mp4')
    ff = subprocess.Popen(['ffmpeg', '-y', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                           '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '16', '-pix_fmt', 'yuv420p', out], stdin=subprocess.PIPE)
    n_fr = int(totale * FPS)
    si = 0
    for n in range(n_fr):
        t = n / FPS
        while si < len(shots) - 1 and t >= shots[si]['t1']:
            si += 1
        sh = shots[si]; s = sh['scena']; ts = t - sh['t0']; tsc = t - (sh['t0'] - sh['rel'])
        dur = sh['t1'] - sh['t0']
        # sfondo con spinta lenta (zoom 1.00 -> 1.06 sull'inquadratura), stretta = piu' vicino
        bg = s['_bg']; z0 = {'larga': 1.0, 'media': 1.04, 'stretta': 1.08}[sh['q']]
        z = z0 + 0.04 * ts / max(dur, .1)
        cw, ch = int(bg.width / (1.12 * z) * 1.0), int(bg.height / (1.12 * z))
        ox = (bg.width - cw) // 2 + int((sh['lato'] - .5) * 40); oy = (bg.height - ch) // 2
        fr = bg.crop((ox, oy, ox + cw, oy + ch)).resize((W, H), Image.BILINEAR).convert('RGBA')
        # personaggi
        p = sh['posa']; img = posa(p)
        alt = H * ALTEZZA[sh['q']] * (.62 if p in LARGHE else 1.0)
        piedi = H * .95 if sh['q'] == 'larga' else alt + H * .07   # media/stretta: testa sempre in alto nel quadro, gambe tagliate
        cx = W * (.32 if sh['lato'] == 0 else .68)
        mov = 0.0
        if p in ('cammina', 'corre'):
            mov = (ts / max(dur, .1) - .5) * (260 if p == 'cammina' else 520)
        if sh['q'] == 'larga':   # ombra sotto i piedi
            ImageDraw.Draw(fr).ellipse((cx + mov - alt * .22, piedi - 16, cx + mov + alt * .22, piedi + 14), fill=(0, 0, 0, 55))
        if s.get('secondario'):
            sec = posa(s['secondario'], True)
            disegna_personaggio(fr, sec, W * (.72 if sh['lato'] == 0 else .28), piedi, alt * .97, ts, flip=sh['lato'] == 0, entrata=.12)
        disegna_personaggio(fr, img, cx, piedi, alt, ts, flip=(p in ('cammina', 'corre') and False), mov=mov)
        # nuvoletta con la parola chiave, quando la voce la dice
        if s.get('parola'):
            pw = s['parola'].split()[0].lower().strip('.,!?')
            t_par = next((x[1] for x in s['_parole'] if x[0].lower().strip('.,!?;:«»"') == pw), s['_dur'] * .3)
            if tsc >= t_par:
                nuvoletta(fr, s['parola'], tsc - t_par, sh['lato'] == 0, centro=bool(s.get('secondario')))
        sottotitolo(fr, s['_parole'], tsc)
        ff.stdin.write(fr.convert('RGB').tobytes())
        if n % (FPS * 10) == 0:
            log(f'montaggio {int(100 * n / n_fr)}%')
    ff.stdin.close(); ff.wait()
    return out, shots, totale


# ============================================================ MODO "ILLUSTRATO" (11 nov sera, Giorgio: "e' fastidioso che il personaggio
# continui a muoversi; migliora nettamente la qualita' sotto ogni punto di vista, fino a 1,50 EUR per 9-10 minuti")
# Niente piu' figurine incollate che respirano: ogni QUADRO e' un'illustrazione intera (KAO dentro la scena, con luce, oggetti e
# altre persone), disegnata da FLUX.2 Klein partendo dall'identikit di KAO. L'immagine resta FERMA: il ritmo viene dai tagli
# (campo largo / primo piano di KAO / dettaglio) come in un film d'animazione, dalle nuvolette e dai sottotitoli.
RAW = 'https://raw.githubusercontent.com/' + E('GITHUB_REPOSITORY', 'gggweb23-gif/ambience') + '/main/'
QW, QH = [int(x) for x in str(P.get('quadro_risoluzione') or '1280x720').split('x')]   # risoluzione dei quadri (spesa) - il video esce comunque a 1440p
PREZZO_QUADRO = float(P.get('prezzo_quadro') or round(0.017 * QW * QH / (1280 * 720), 4))
# 12 nov (Giorgio: "la nitidezza non e' ancora il massimo"): ingrandimento AI x2 di ogni quadro (Real-ESRGAN per disegni, fal, ~0,002 $):
# il quadro passa da 1280x720 a 2560x1440, poi il video lo RIMPICCIOLISCE (piu' nitido) invece di ingrandirlo. Sempre attivo (12 nov, Giorgio); colonna quadro_ingrandimento = NO per spegnerlo.
INGRANDISCI = str(P.get('quadro_ingrandimento') or E('QUADRO_INGRANDIMENTO', '') or 'SI').strip().upper() != 'NO'   # 12 nov (Giorgio: "vai con questa soluzione"): sempre attivo
PREZZO_INGR = float(P.get('prezzo_ingrandimento') or 0.002)
SEC_IMG = float(P.get('secondi_immagine') or 4)   # 11 nov (Giorgio): mai la stessa immagine due volte, nemmeno zoomata: un'immagine NUOVA ogni ~4 s


def copione_illustrato():
    f = os.path.join(CART, 'copione.json')
    if os.path.exists(f):
        return json.load(open(f))
    parole = int(MINUTI * 150)
    n_quadri = max(5, round(MINUTI * float(P.get('quadri_al_minuto') or 4.5)))
    if SEC_IMG:
        return copione_unico(f, parole)
    prompt = f"""Sei l'autore e il regista del canale YouTube italiano KAO PSICOLOGIA: psicologia spiegata in modo semplice, caldo e diretto, dando del tu.
Il video e' un CARTONE ANIMATO di qualita' cinematografica con protagonista KAO (omino calvo, maglia magenta) che VIVE la situazione di cui si parla.
Tema: "{TEMA}". Lunghezza: circa {parole} parole di parlato in italiano ({MINUTI:g} minuti).
COPIONE: parti SUBITO con un gancio forte (la cosa piu' sorprendente prima), racconta il problema con una piccola storia di vita quotidiana italiana
che si sviluppa (KAO al lavoro, a casa, con gli amici...), spiega cosa succede dentro di noi, dai punti di vista utili, senza giudizi assoluti e senza elenchi di dati.{' A meta video una domanda che invita a rispondere nei commenti.' if MINUTI >= 3 else ''}
REGIA: esattamente {n_quadri} QUADRI (illustrazioni). Ogni quadro e' un momento della storia che mostra QUELLO CHE LA VOCE DICE in quel momento,
con KAO che fa un'azione chiara con un'espressione chiara, in un luogo pieno di dettagli realistici italiani. Stesso luogo per piu' quadri di fila
quando la storia resta li'. Altre persone solo quando servono alla storia: scegli tra {json.dumps(list(SECONDARI), ensure_ascii=False)}.
Dividi il parlato in scene di 1-2 frasi (8-24 parole); ogni scena appartiene a un quadro (1-3 scene per quadro). Per ogni scena scegli il TAGLIO:
"largo" (tutta l'illustrazione), "kao" (primo piano di KAO), "altro" (primo piano dell'altra persona o dell'oggetto importante); alterna i tagli come in un film.
Rispondi SOLO con JSON:
{{"titolo": "...",
 "quadri": [{{"id": "q1", "luogo": "in inglese, il posto con i suoi dettagli (es. 'a small Italian open-space office, desks with laptops, big windows, plants')",
             "azione": "in inglese, cosa fa KAO e con che espressione, e cosa fanno gli altri (es. 'KAO sits at his desk rubbing his tired eyes, the screen full of notifications; a colleague talks loudly on the phone behind him')",
             "kao": "left|right", "secondario": "id della persona o ''"}}],
 "scene": [{{"testo": "parlato", "quadro": "q1", "taglio": "largo|kao|altro", "parola": "1-3 parole chiave da mostrare grandi in una nuvoletta (in circa meta' delle scene, altrimenti '')"}}]}}"""
    c = claude(prompt)
    c['scene'] = [s for s in c.get('scene', []) if str(s.get('testo') or '').strip()]
    ids = {q['id'] for q in c.get('quadri', [])}
    for s in c['scene']:
        if s.get('quadro') not in ids:
            s['quadro'] = c['quadri'][0]['id']
    for q in c['quadri']:
        if q.get('secondario') and q['secondario'] not in SECONDARI:
            q['secondario'] = ''
    json.dump(c, open(f, 'w'), ensure_ascii=False, indent=1)
    log('copione:', len(c['scene']), 'scene,', sum(len(s['testo'].split()) for s in c['scene']), 'parole,', len(c['quadri']), 'quadri')
    return c


def copione_unico(f, parole):
    """Ogni scena ha le SUE immagini, tutte diverse (circa una ogni SEC_IMG secondi di voce = una ogni ~10 parole)."""
    per_img = max(6, int(SEC_IMG * 2.5))
    prompt = f"""Sei l'autore e il regista del canale YouTube italiano KAO PSICOLOGIA: psicologia spiegata in modo semplice, caldo e diretto, dando del tu.
Il video e' un CARTONE ANIMATO di qualita' cinematografica con protagonista KAO (omino calvo, maglia magenta) che VIVE la situazione di cui si parla.
Tema: "{TEMA}". Lunghezza: circa {parole} parole di parlato in italiano ({MINUTI:g} minuti).
COPIONE: parti SUBITO con un gancio forte (la cosa piu' sorprendente prima), racconta il problema con una piccola storia di vita quotidiana italiana
che si sviluppa (KAO al lavoro, a casa, con gli amici...), spiega cosa succede dentro di noi, dai punti di vista utili, senza giudizi assoluti e senza elenchi di dati.{' A meta video una domanda che invita a rispondere nei commenti.' if MINUTI >= 3 else ''}
Non chiamare mai il protagonista per nome nel parlato: parla a "te" (lo spettatore si riconosce in lui).
REGIA: dividi il parlato in scene di 1-2 frasi (8-24 parole). Ogni scena ha UNA immagine ogni circa {per_img} parole (quindi 1-3 immagini),
TUTTE DIVERSE tra loro in tutto il video (mai la stessa immagine, nemmeno con un'altra inquadratura): ogni immagine mostra QUELLO CHE LA VOCE DICE
in quel momento, con KAO che fa un'azione chiara con un'espressione chiara. Varia le inquadrature tra le immagini (campo largo, mezza figura, primo piano,
dettaglio di mani o oggetti, dall'alto, di spalle) come in un film. Stesso luogo per piu' immagini di fila quando la storia resta li'.
Altre persone solo quando servono alla storia: scegli tra {json.dumps(list(SECONDARI), ensure_ascii=False)}.
Rispondi SOLO con JSON:
{{"titolo": "...",
 "scene": [{{"testo": "parlato", "luogo": "in inglese, il posto con i suoi dettagli (es. 'a small Italian open-space office, desks with laptops, big windows, plants')",
            "secondario": "id della persona o ''", "parola": "1-3 parole chiave da mostrare grandi in una nuvoletta (in circa meta' delle scene, altrimenti '')",
            "immagini": [{{"azione": "in inglese: inquadratura + cosa fa KAO e con che espressione + cosa fanno gli altri (es. 'close-up: KAO rubs his tired eyes at his desk, notifications on the screen')",
                          "kao": "left|right"}}]}}]}}"""
    c = claude(prompt, max_tokens=32000)
    c['scene'] = [x for x in c.get('scene', []) if str(x.get('testo') or '').strip()]
    c['quadri'] = []
    for x in c['scene']:
        if x.get('secondario') and x['secondario'] not in SECONDARI:
            x['secondario'] = ''
        x['_quadri'] = []
        for im in (x.get('immagini') or [{'azione': x['testo'], 'kao': 'left'}]):
            q = {'id': f"q{len(c['quadri']) + 1}", 'luogo': x.get('luogo') or 'an Italian room', 'azione': im.get('azione') or x['testo'],
                 'kao': im.get('kao') or 'left', 'secondario': x.get('secondario') or ''}
            c['quadri'].append(q); x['_quadri'].append(q['id'])
        x['quadro'] = x['_quadri'][0]
    json.dump(c, open(f, 'w'), ensure_ascii=False, indent=1)
    log('copione:', len(c['scene']), 'scene,', sum(len(x['testo'].split()) for x in c['scene']), 'parole,', len(c['quadri']), 'immagini tutte diverse')
    return c


def klein_edit(prompt, refs, f):
    hd = {'Authorization': 'Key ' + E('FAL_KEY', '')}
    inv = YT.http('https://queue.fal.run/fal-ai/flux-2/klein/4b/edit', {'prompt': prompt, 'image_urls': refs, 'image_size': {'width': QW, 'height': QH},
                                                                       'num_images': 1, 'output_format': 'png'}, hd, timeout=120)
    for _ in range(150):
        time.sleep(2)
        if YT.http(inv['status_url'], headers=hd, timeout=60).get('status') == 'COMPLETED':
            break
    u = YT.http(inv['response_url'], headers=hd, timeout=60)['images'][0]['url']
    Image.open(io.BytesIO(YT.http(u, raw=True, timeout=120))).convert('RGB').save(f, quality=95)
    CO.registra('fal', 'flux-2-klein-4b-edit', dollari=PREZZO_QUADRO, nota='quadro KAO cartone')
    if INGRANDISCI:
        try:
            shutil.copy(f, f.replace('.jpg', '_orig.jpg'))   # il quadro com'era (per i confronti)
            inv = YT.http('https://queue.fal.run/fal-ai/esrgan', {'image_url': u, 'scale': 2, 'model': 'RealESRGAN_x4plus_anime_6B', 'output_format': 'png'}, hd, timeout=120)
            for _ in range(90):
                time.sleep(2)
                if YT.http(inv['status_url'], headers=hd, timeout=60).get('status') == 'COMPLETED':
                    break
            r = YT.http(inv['response_url'], headers=hd, timeout=60)
            u2 = (r.get('image') or {}).get('url') or (r.get('images') or [{}])[0].get('url')
            Image.open(io.BytesIO(YT.http(u2, raw=True, timeout=120))).convert('RGB').save(f, quality=96)
            CO.registra('fal', 'esrgan-anime-x2', dollari=PREZZO_INGR, nota='ingrandimento quadro KAO')
        except Exception as e:
            log('ingrandimento non riuscito, resta il quadro normale:', str(e)[:120])
    return u


def caselle(f):
    """Dove sono KAO e l'altra persona/oggetto nel quadro (Haiku, ~0,003 $): servono per i primi piani."""
    buf = io.BytesIO(); Image.open(f).convert('RGB').resize((960, 540)).save(buf, 'JPEG', quality=85)
    req = urllib.request.Request('https://api.anthropic.com/v1/messages', data=json.dumps({
        'model': 'claude-haiku-4-5-20251001', 'max_tokens': 200, 'messages': [{'role': 'user', 'content': [
            {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': base64.b64encode(buf.getvalue()).decode()}},
            {'type': 'text', 'text': 'Image 960x540. Give the bounding box (pixels) of the bald man in the magenta shirt (head and upper body) and of the most '
                                     'important OTHER person or object. Also check: ok = true only if the bald man wears a MAGENTA shirt and NOBODY else wears magenta, pink or purple. '
                                     'scritte = true if the image contains ANY written words, letters, captions or fake text (signs, posters, screens, paper included). '
                                     'Answer ONLY {"kao": [x1,y1,x2,y2], "altro": [x1,y1,x2,y2], "ok": true|false, "scritte": true|false}.'}]}]}).encode(),
        headers={'x-api-key': E('ANTHROPIC_API_KEY', ''), 'anthropic-version': '2023-06-01', 'content-type': 'application/json'})
    try:
        j = json.loads(urllib.request.urlopen(req, timeout=120).read())
        CO.registra('claude', 'claude-haiku-4-5-20251001', usage=j.get('usage'), nota='caselle quadro')
        t = ''.join(b.get('text', '') for b in j['content'] if b.get('type') == 'text')
        d = json.loads(t[t.find('{'): t.rfind('}') + 1])
        sc = Image.open(f).width / 960   # 11 nov: i quadri sono 1600 px, non 1920 (prima le caselle erano spostate)
        out = {k: [v * sc for v in d[k][:4]] for k in ('kao', 'altro') if isinstance(d.get(k), list) and len(d[k]) >= 4}
        out['_ok'] = d.get('ok') is not False and d.get('scritte') is not True   # 12 nov (Giorgio): mai parole finte nei disegni
        out['_scritte'] = d.get('scritte') is True
        return out
    except Exception as e:
        log('caselle non trovate:', str(e)[:100]); return {}


def _troppo_simile(a, b, soglia=9):   # misurato 12 nov: scene uguali ~5, scene diverse di fila >= 11,8
    """12 nov: due quadri di fila quasi identici (stessa scena) -> differenza media dei pixel su 32x18 in scala di grigi sotto la soglia."""
    try:
        A = Image.open(a).convert('L').resize((32, 18)); B = Image.open(b).convert('L').resize((32, 18))
        return sum(abs(x - y) for x, y in zip(A.getdata(), B.getdata())) / (32 * 18) < soglia
    except Exception:
        return False


def quadri(c):
    ultimo_luogo = {}
    for i, q in enumerate(c['quadri']):
        f = os.path.join(CART, f"quadro_{i:02d}.jpg")
        lato = 'LEFT' if q.get('kao') == 'left' else 'RIGHT'
        refs = [RAW + PERS + '/identikit.png']
        extra = ''
        if q.get('secondario'):
            refs.append(RAW + PERS + '/secondari/' + q['secondario'] + '.png')
            extra += ' The other person is EXACTLY the character of the second reference image (same face, hair and clothes).'
        if q['luogo'] in ultimo_luogo:
            refs.append(ultimo_luogo[q['luogo']])
            extra += ' The place is EXACTLY the same room/street as in the last reference image (same furniture, colours and layout), seen from a slightly different angle.'
        prompt = ('Flat 2D cartoon illustration, high quality animated film still, in exactly the drawing style of the first reference image: thick clean black '
                  'outlines, flat colours, simple rounded shapes. The main character is EXACTLY the man of the first reference image: bald round head, peach skin, '
                  'small black oval eyes, thin eyebrows, magenta long-sleeve shirt, black trousers, black shoes - same face and proportions, never change his clothes. '
                  f"Scene: {q['azione']}. Setting: {q['luogo']}.{extra} The main character is on the {lato} third of the frame, big and clearly visible "
                  '(at least half of the image height), his face and expression very readable. He is the ONLY person wearing magenta or pink: every other person wears completely different colours (grey, blue, green, white, brown). Rich, detailed, realistic Italian everyday environment, warm soft '
                  'cinematic light, 16:9 composition with depth. No text, no letters, no numbers, no speech bubbles, no logos.')
        nuovo = not os.path.exists(f)
        if nuovo:
            for k in range(3):
                try:
                    q['_url'] = klein_edit(prompt, refs, f); break
                except Exception as e:
                    log('quadro non riuscito, riprovo:', str(e)[:120]); time.sleep(5)
            else:
                raise RuntimeError('quadro non riuscito: ' + q['id'])
            log('quadro', i + 1, '/', len(c['quadri']), ':', q['azione'][:80])
        if q.get('_url'):
            ultimo_luogo[q['luogo']] = q['_url']
        fb = f[:-4] + '.json'
        q['_box'] = json.load(open(fb)) if os.path.exists(fb) else caselle(f)
        for rif in range(2 if nuovo else 0):   # solo i quadri appena fatti: quelli gia' controllati non si ripagano   # 11 nov: un altro personaggio vestito di magenta (o KAO con la maglia sbagliata) -> il quadro si rifa'
            uguale = i > 0 and _troppo_simile(f, os.path.join(CART, f"quadro_{i - 1:02d}.jpg"))   # 12 nov (Giorgio): mai la stessa scena di fila
            if q['_box'].get('_ok', True) and not uguale:
                break
            motivo = 'quasi uguale al precedente' if uguale else ('scritte nel disegno' if q['_box'].get('_scritte') else 'magenta su un altro personaggio')
            log('quadro', i + 1, 'bocciato (' + motivo + '): lo rifaccio')
            agg = ' IMPORTANT: only the bald main character wears magenta. Absolutely NO writing anywhere: no captions, no words, no letters, blank signs and screens.'
            if uguale:
                agg += ' Show a CLEARLY DIFFERENT shot from the previous image: different framing, different angle and a different action.'
            q['_url'] = klein_edit(prompt + agg, refs[:1] + refs[2:] if (q.get('secondario') and rif) or uguale else refs, f)
            q['_box'] = caselle(f)
        q['_box'].pop('_ok', None); q['_box'].pop('_scritte', None)
        json.dump(q['_box'], open(fb, 'w'))
        q['_img'] = Image.open(f).convert('RGB')


def ritaglio(q, taglio):
    """Il quadro intero o un primo piano (16:9) con il soggetto su un terzo, l'altro lato libero per la nuvoletta."""
    im = q['_img']; w, h = im.size
    b = q['_box'].get('kao' if taglio == 'kao' else 'altro') if taglio != 'largo' else None
    if not b:
        x0, y0, cw, ch = 0, 0, w, h
    else:
        cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
        cw = max(w * .64, min(w * .8, (b[2] - b[0]) * 2.6)); ch = cw * 9 / 16   # 11 nov: primo piano meno stretto (piu' nitido, si vede la scena)
        terzo = .38 if cx < w / 2 else .62
        x0 = min(max(0, cx - cw * terzo), w - cw); y0 = min(max(0, cy - ch * .42), h - ch)
        kb = q['_box'].get('kao')
        if kb:   # 11 nov: mai una testa tagliata: la testa di KAO (se e' nel taglio) resta tutta dentro, con un po' d'aria sopra
            if kb[2] > x0 and kb[0] < x0 + cw and kb[1] < y0 + ch * .5:
                y0 = max(0, min(y0, kb[1] - h * .04))
            if kb[0] < x0 < kb[2] or kb[0] < x0 + cw < kb[2]:   # KAO tagliato a meta' sul lato: o tutto dentro o tutto fuori
                dentro = kb[0] - w * .03, kb[2] + w * .03
                if dentro[1] - dentro[0] <= cw:
                    x0 = min(max(0, min(x0, dentro[0])), w - cw); x0 = max(x0, dentro[1] - cw)
                elif taglio == 'altro':
                    x0, y0, cw, ch = 0, 0, w, h
            if taglio == 'altro' and kb[2] > x0 and kb[0] < x0 + cw and kb[1] < y0:
                x0, y0, cw, ch = 0, 0, w, h   # non si riesce a tenere la testa: campo largo
    img = im.crop((int(x0), int(y0), int(x0 + cw), int(y0 + ch))).resize((W, H), Image.LANCZOS)
    img = img.filter(ImageFilter.UnsharpMask(radius=1.6, percent=70, threshold=2))   # 12 nov (Giorgio): contorni piu' netti, gratis
    # caselle delle persone nel fotogramma: la nuvoletta non deve MAI coprire una testa
    k = W / cw; occ = []
    for v in q['_box'].values():
        occ.append(((v[0] - x0) * k, (v[1] - y0) * k, (v[2] - x0) * k, (v[3] - y0) * k))
    return img, occ


def posto_nuvoletta(occ, testo, lato_kao=''):
    """Il posto per la nuvoletta che non tocca nessuna persona (soprattutto la testa); tra quelli liberi il piu' in alto."""
    lw = min(W * .42, 60 * len(testo) + 120); lh = 200
    cand = [(W * .25, H * .17), (W * .75, H * .17), (W * .5, H * .12), (W * .22, H * .42), (W * .78, H * .42), (W * .5, H * .62)]
    def sovrapp(c):
        x1, y1, x2, y2 = c[0] - lw / 2, c[1] - lh / 2, c[0] + lw / 2, c[1] + lh / 2
        tot = 0
        for a in occ:
            testa = (a[0], a[1], a[2], a[1] + (a[3] - a[1]) * .45)   # la testa conta il triplo
            for bb, peso in ((a, 1), (testa, 3)):
                ix, iy = max(0, min(x2, bb[2]) - max(x1, bb[0])), max(0, min(y2, bb[3]) - max(y1, bb[1]))
                tot += ix * iy * peso
        return tot
    if lato_kao in ('left', 'right'):   # 11 nov: la regia sa da che parte e' KAO: la nuvoletta va SEMPRE dall'altra parte (le caselle possono sbagliare)
        cand = [c for c in cand if (c[0] > W * .6 if lato_kao == 'left' else c[0] < W * .4)]
    return min(cand, key=lambda c: (sovrapp(c) > 0, sovrapp(c), cand.index(c)))


def movimento(img, n, x):
    """11 nov (Giorgio: "che ci sia sempre un po' di movimento"): ogni immagine si muove piano, e il movimento cambia da un'immagine
    all'altra: avanti (zoom dentro), indietro (zoom fuori), da sinistra a destra, da destra a sinistra. x = 0..1 dentro l'inquadratura."""
    x = x * x * (3 - 2 * x)   # partenza e arrivo morbidi
    tipo = n % 2   # 11 nov (Giorgio): solo avanti e indietro, niente spostamenti di lato, e piu' lento
    z = 1.0 + .045 * (x if tipo == 0 else 1 - x)
    cw, ch = W / z, H / z
    if tipo in (0, 1):
        x0, y0 = (W - cw) / 2, (H - ch) / 2
    else:
        lib = W - cw
        x0, y0 = (lib * x if tipo == 2 else lib * (1 - x)), (H - ch) / 2
    return img.resize((W, H), Image.LANCZOS, box=(x0, y0, x0 + cw, y0 + ch))   # 12 nov: lanczos (piu' nitido del bicubic)


def monta_illustrato(c):
    qid = {q['id']: q for q in c['quadri']}
    shots, t0 = [], 0.0
    for i, s in enumerate(c['scene']):
        q = qid[s['quadro']]
        tg = s.get('taglio') if s.get('taglio') in ('largo', 'kao', 'altro') else 'largo'
        if tg == 'altro' and not q['_box'].get('altro'):
            tg = 'kao'
        pezzi = [(0.0, s['_dur'], tg)]
        if s.get('_quadri'):   # immagini tutte diverse: la scena si divide tra le sue immagini, sempre intere
            n_ = len(s['_quadri']); dd = s['_dur'] / n_
            for j, idq in enumerate(s['_quadri']):
                shots.append({'t0': t0 + j * dd, 't1': t0 + (j + 1) * dd, 'scena': s, 'quadro': qid[idq], 'taglio': 'largo', 'rel': j * dd,
                              'nuovo_quadro': True})
            t0 += s['_dur']; continue
        if s['_dur'] > 6.0:   # frase lunga: cambio di taglio a meta' (come un montaggio da film)
            alt = 'kao' if tg == 'largo' else 'largo'
            pezzi = [(0.0, s['_dur'] / 2, tg), (s['_dur'] / 2, s['_dur'], alt)]
        for a, b, tgl in pezzi:
            shots.append({'t0': t0 + a, 't1': t0 + b, 'scena': s, 'quadro': q, 'taglio': tgl, 'rel': a,
                          'nuovo_quadro': not shots or shots[-1]['quadro'] is not q})
        t0 += s['_dur']
    totale = t0
    cache = {}
    out = os.path.join(LAV, 'video_muto.mp4')
    ff = subprocess.Popen(['ffmpeg', '-y', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                           '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '15', '-pix_fmt', 'yuv420p', out], stdin=subprocess.PIPE)
    n_fr = int(totale * FPS); si = 0; prec = None
    for n in range(n_fr):
        t = n / FPS
        while si < len(shots) - 1 and t >= shots[si]['t1']:
            prec = shots[si]; si += 1
        sh = shots[si]; s = sh['scena']; ts = t - sh['t0']; tsc = t - (sh['t0'] - sh['rel'])
        k = (id(sh['quadro']), sh['taglio'])
        if k not in cache:
            kp_ = (id(prec['quadro']), prec['taglio']) if prec else None
            for vecchio in [x for x in cache if x != kp_]:   # memoria: si tengono solo l'immagine attuale e la precedente
                del cache[vecchio]
            cache[k] = ritaglio(sh['quadro'], sh['taglio'])
        base, occ = cache[k]
        fr = movimento(base, si, ts / max(.1, sh['t1'] - sh['t0'])).convert('RGBA')
        if sh['nuovo_quadro'] and prec is not None and ts < .15:   # dissolvenza brevissima tra un'immagine e l'altra
            kp = (id(prec['quadro']), prec['taglio'])
            fr = Image.blend(movimento(cache[kp][0], si - 1, 1.0).convert('RGBA'), fr, ts / .15)
        if s.get('parola'):
            pw = s['parola'].split()[0].lower().strip('.,!?')
            t_par = next((x[1] for x in s['_parole'] if x[0].lower().strip('.,!?;:«»"') == pw), s['_dur'] * .3)
            if tsc >= t_par:
                nuvoletta(fr, s['parola'], tsc - t_par, True, posto=posto_nuvoletta(occ, s['parola'], sh['quadro'].get('kao', '')))
        if not SENZA_SOTTOTITOLI:
            sottotitolo(fr, s['_parole'], tsc)
        ff.stdin.write(fr.convert('RGB').tobytes())
        if n % (FPS * 15) == 0:
            log(f'montaggio {int(100 * n / n_fr)}%')
    ff.stdin.close(); ff.wait()
    # "pop" solo quando cambia il luogo (con un'immagine nuova ogni 4 s, un suono a ogni cambio stancherebbe)
    return out, [x for k_, x in enumerate(shots) if k_ == 0 or x['quadro']['luogo'] != shots[k_ - 1]['quadro']['luogo']], totale


def audio(c, shots, totale):
    voce_f = os.path.join(LAV, 'voce.wav')
    lista = os.path.join(LAV, 'voci.txt')
    open(lista, 'w').write(''.join(f"file '{os.path.abspath(s['_audio'])}'\n" for s in c['scene']))
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', lista, '-ar', '44100', '-ac', '2', voce_f], check=True)
    popf = os.path.join(LAV, 'pop.wav')   # "pop" morbido a ogni cambio di inquadratura (fatto in codice, gratis)
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-f', 'lavfi', '-i', "aevalsrc='0.5*sin(2*PI*(500+900*t)*t)*exp(-28*t)':s=44100:d=0.18", '-ac', '2', popf], check=True)
    brani = sorted(f for f in os.listdir('libreria_musica') if f.startswith('curiosita'))
    musica = os.path.join('libreria_musica', random.Random(TEMA).choice(brani)) if brani else None
    ins = ['-i', voce_f]; fl = ['[0:a]volume=1.0[v]']; mix = ['[v]']; k = 1
    if musica:
        ins += ['-stream_loop', '-1', '-i', musica]; fl.append(f'[{k}:a]volume=0.05,atrim=0:{totale:.2f}[m]'); mix.append('[m]'); k += 1
    momenti = [sh['t0'] for sh in shots[1:]]
    if momenti:
        ins += ['-i', popf]; fl.append(f'[{k}:a]volume=0.35,asplit={len(momenti)}' + ''.join(f'[p{j}]' for j in range(len(momenti))))
        for j, m in enumerate(momenti):
            fl.append(f'[p{j}]adelay={int(m * 1000)}|{int(m * 1000)}[q{j}]'); mix.append(f'[q{j}]')
    fl.append(''.join(mix) + f'amix=inputs={len(mix)}:normalize=0:duration=first[a]')
    out = os.path.join(LAV, 'audio.m4a')
    subprocess.run(['ffmpeg', '-y', '-v', 'error'] + ins + ['-filter_complex', ';'.join(fl), '-map', '[a]', '-c:a', 'aac', '-b:a', '192k', out], check=True)
    return out


def main():
    if str(P.get('modo') or 'illustrato') == 'illustrato':
        c = copione_illustrato()
        voce(c)
        quadri(c)
        muto, shots, totale = monta_illustrato(c)
    else:   # prima versione: figurine della libreria sugli sfondi
        c = copione()
        voce(c)
        luoghi(c)
        muto, shots, totale = monta(c)
    a = audio(c, shots, totale)
    v1080 = os.path.join(LAV, 'kao_1080.mp4')
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', muto, '-i', a, '-c:v', 'copy', '-c:a', 'copy', '-shortest', v1080], check=True)
    fin = YT.nitido(v1080, os.path.join(LAV, 'kao_1440.mp4'))
    nome = re.sub(r'[^a-z0-9]+', '_', TEMA.lower())[:40].strip('_')
    dest = os.path.join(CART, nome + '.mp4')
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', fin, '-c', 'copy', '-movflags', '+faststart', dest], check=True)
    # fotogrammi di controllo
    q = os.path.join(CART, nome + '_fotogrammi.jpg'); fot = Image.new('RGB', (4 * 480, 3 * 270))
    for k in range(12):
        tt = totale * (k + .5) / 12; f_ = os.path.join(LAV, f'f{k}.jpg')
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-ss', f'{tt:.2f}', '-i', v1080, '-frames:v', '1', '-vf', 'scale=480:270', f_])
        if os.path.exists(f_):
            fot.paste(Image.open(f_), ((k % 4) * 480, (k // 4) * 270))
    fot.save(q, quality=85)
    log('FATTO:', dest, round(totale, 1), 's |', CO.testo() if hasattr(CO, 'testo') else '')


if __name__ == '__main__':
    main()


# ============================================================ USO DAL MOTORE KAO (render_kao.py, colonna video_stile = CARTONE)
RISERVA = ['Medium shot: KAO sits by a window, thoughtful, looking outside at the street',
           'Close-up: KAO rubs his forehead, tired but calm',
           'Wide shot: KAO walks along a quiet Italian street at sunset, hands in pockets',
           'Detail shot: KAO\'s hands holding a warm cup of coffee on a kitchen table',
           'From behind: KAO stands on a balcony looking at the city lights',
           'Medium shot: KAO sits on a park bench, watching people pass by, pensive',
           'Close-up: KAO closes his eyes and breathes slowly, relieved',
           'Wide shot: KAO alone in a bright kitchen, preparing a simple meal, absorbed',
           'Top-down shot: KAO lying on his bed, staring at the ceiling, thinking',
           'Medium shot: KAO talking calmly with a friend at a cafe table']


def base_cartone(testi, durate, titolo, cartella, budget=3.10):
    """11 nov (Giorgio: "dal video che esce domani fallo con questo stile"): il video di KAO (copione tradotto dal competitor e voce gia'
    fatti dal motore) diventa un cartone: un'illustrazione NUOVA ogni ~4 s (mai ripetuta), zoom lento avanti/indietro, nuvolette.
    Restituisce il video muto 1920x1080 (sottotitoli, iscrizione, musica e audio li mette render_kao.py come sempre).
    budget = colonna cartone_budget_video ($): se le immagini non ci stanno, si allunga il tempo di ogni immagine (mai oltre il budget)."""
    global CART, SENZA_SOTTOTITOLI, TEMA
    CART = cartella; os.makedirs(CART, exist_ok=True); SENZA_SOTTOTITOLI = True; TEMA = titolo or TEMA
    totale = sum(durate)
    sec = SEC_IMG
    spesa_img = (PREZZO_QUADRO + (PREZZO_INGR if INGRANDISCI else 0)) * 1.12 + 0.003   # quadro (+ ingrandimento) + 12% di rifacimenti + controllo
    fisso = 0.30                                 # regia (Claude, a blocchi di 15 scene)
    n_max = max(len(testi), int((budget - fisso) / spesa_img))
    if totale / sec > n_max:
        sec = totale / n_max
        log(f'cartone: con il budget di {budget:.2f} $ un\'immagine ogni {sec:.1f} s (invece di {SEC_IMG:g})')
    n_img = [max(1, round(d / sec)) for d in durate]
    log('cartone:', len(testi), 'scene,', sum(n_img), 'immagini previste, circa', round(sum(n_img) * spesa_img + fisso, 2), '$')
    f = os.path.join(CART, 'regia.json')
    # 12 nov (Giorgio: "scene che non cambiano per minuti e parole non in italiano"): la regia in UNA chiamata per 125 scene si fermava
    # a ~30 scene e il resto diventava "KAO listens thoughtfully, <frase italiana>" -> stesso salotto per minuti e testo italiano storpiato
    # disegnato da Klein. Ora: regia a blocchi di 15 scene, ogni scena controllata (numero di immagini giusto), i buchi si richiedono,
    # e mai frasi italiane nel prompt del disegno.
    reg = json.load(open(f)) if os.path.exists(f) else {'scene': []}
    fatte = {int(x.get('i', -1)): x for x in reg.get('scene', []) if 0 <= int(x.get('i', -1)) < len(testi) and len(x.get('immagini') or []) >= 1}
    def _chiedi(idx, storia):
        elenco = [{'i': i, 'testo': testi[i], 'immagini': n_img[i]} for i in idx]
        prompt = f"""Sei il regista del canale YouTube italiano KAO PSICOLOGIA. Il video "{titolo}" diventa un CARTONE ANIMATO di qualita' cinematografica
con protagonista KAO (omino calvo, maglia magenta) che VIVE la situazione di cui parla la voce, in una storia di vita quotidiana italiana coerente dall'inizio alla fine.
{storia}
Per OGNI scena qui sotto (parlato gia' scritto) disegna ESATTAMENTE il numero di immagini indicato. TUTTE le immagini del video sono DIVERSE tra loro
(mai la stessa immagine, nemmeno con un'altra inquadratura): ognuna mostra QUELLO CHE LA VOCE DICE in quel momento, con KAO che fa un'azione chiara con
un'espressione chiara. Varia le inquadrature (campo largo, mezza figura, primo piano, dettaglio di mani o oggetti, dall'alto, di spalle) come in un film.
Cambia luogo spesso (casa, ufficio, strada, bar, parco, auto, cucina, camera, ricordi d'infanzia...): mai piu' di 4 immagini di fila nello stesso posto.
Altre persone solo quando servono: scegli tra {json.dumps(list(SECONDARI), ensure_ascii=False)}.
Concetti astratti (il cervello, le emozioni): mostrali con KAO in situazioni concrete o con metafore visive semplici, MAI scritte, cartelli, libri aperti con testo o schermi con parole.
Scene: {json.dumps(elenco, ensure_ascii=False)}
Rispondi SOLO con JSON con TUTTE le {len(idx)} scene: {{"scene": [{{"i": numero, "luogo": "in inglese, il posto con i suoi dettagli", "secondario": "id o ''",
 "parola": "1-3 parole chiave del parlato da mostrare in una nuvoletta (in circa un terzo delle scene, altrimenti '')",
 "immagini": [{{"azione": "in inglese: inquadratura + cosa fa KAO e con che espressione + cosa fanno gli altri", "kao": "left|right"}}]}}]}}"""
        try:
            r = claude(prompt, max_tokens=16000)
            return {int(x.get('i', -1)): x for x in (r.get('scene') or [])}
        except Exception as e:
            log('regia: blocco non riuscito', str(e)[:100]); return {}
    mancanti = [i for i in range(len(testi)) if i not in fatte]
    for giro in range(3):
        if not mancanti:
            break
        for b in range(0, len(mancanti), 15):
            idx = mancanti[b:b + 15]
            prec = [fatte[k] for k in sorted(fatte) if k < idx[0]][-2:]
            storia = ('Fin qui la storia: ' + json.dumps([{'luogo': x.get('luogo'), 'ultime azioni': [y.get('azione') for y in (x.get('immagini') or [])][-2:]} for x in prec], ensure_ascii=False)
                      + ' Continua da qui in modo coerente, senza ripetere le stesse immagini.') if prec else 'Questo e\' l\'inizio del video: parti con un gancio visivo forte.'
            for k, x in _chiedi(idx, storia).items():
                if k in idx and len(x.get('immagini') or []) >= 1:
                    fatte[k] = x
        mancanti = [i for i in range(len(testi)) if i not in fatte]
        log('regia: scene pronte', len(fatte), '/', len(testi), '| giro', giro + 1)
    reg = {'scene': [fatte[k] for k in sorted(fatte)]}
    json.dump(reg, open(f, 'w'), ensure_ascii=False)
    if mancanti:
        log('regia: ATTENZIONE', len(mancanti), 'scene senza regia: uso inquadrature di riserva (senza testo)')
    per_i = {int(x.get('i', -1)): x for x in reg.get('scene', [])}
    c = {'scene': [], 'quadri': []}
    luogo_prec = 'a cosy Italian living room'
    for i, (t, d, n) in enumerate(zip(testi, durate, n_img)):
        x = per_i.get(i) or {}
        luogo = x.get('luogo') or luogo_prec; luogo_prec = luogo
        sec_ = x.get('secondario') if x.get('secondario') in SECONDARI else ''
        imgs = (x.get('immagini') or [])[:n]
        while len(imgs) < n:   # 12 nov: mai un'immagine sola per tante frasi e mai la frase italiana nel prompt (Klein la disegna storpiata)
            j = (i * 3 + len(imgs)) % len(RISERVA)
            imgs.append({'azione': RISERVA[j], 'kao': 'left' if j % 2 else 'right'})
        parole = t.split(); passo = d / max(1, len(parole))
        sc = {'testo': t, '_dur': d, 'parola': x.get('parola') or '', 'secondario': sec_, 'luogo': luogo,
              '_parole': [[w, k * passo, (k + 1) * passo] for k, w in enumerate(parole)], '_quadri': []}
        for im in imgs:
            q = {'id': f"q{len(c['quadri']) + 1}", 'luogo': luogo, 'azione': im.get('azione') or t, 'kao': im.get('kao') or 'left', 'secondario': sec_}
            c['quadri'].append(q); sc['_quadri'].append(q['id'])
        sc['quadro'] = sc['_quadri'][0]
        c['scene'].append(sc)
    quadri(c)
    muto, _, _ = monta_illustrato(c)
    return muto
