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
import base64, hashlib, io, json, math, os, random, re, subprocess, sys, time, urllib.request
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
        f = os.path.join(LAV, f'voce_{i:02d}.mp3')
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


def nuvoletta(fr, testo, t, dx_lato, centro=False):
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
    incolla(fr, card, cx - card.width // 2, cy - card.height // 2)


def sottotitolo(fr, parole, t):
    """3 parole alla volta, la parola detta in giallo (come i sottotitoli dei video KAO)."""
    if not parole:
        return
    i = max([k for k, p in enumerate(parole) if p[1] <= t] or [0])
    g = i // 3 * 3; grp = parole[g:g + 3]
    if t > grp[-1][2] + .4 and g + 3 >= len(parole):
        return
    f = ImageFont.truetype(F_SUB, 64); d = ImageDraw.Draw(fr)
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


def audio(c, shots, totale):
    voce_f = os.path.join(LAV, 'voce.wav')
    lista = os.path.join(LAV, 'voci.txt')
    open(lista, 'w').write(''.join(f"file '{s['_audio']}'\n" for s in c['scene']))
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
