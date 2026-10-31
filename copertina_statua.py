#!/usr/bin/env python3
"""COPERTINA "STATUA" (stile Stoic Journal + firma del canale) e IMMAGINE DEL VIDEO dalla STESSA statua.
Per tutti i canali con copertina_stile = statua (Channel Configs). Una statua NUOVA a ogni video (fal, ~0,10 $):
marmo grigio, uomo giovane e muscoloso, gesto diverso; se il titolo parla di persone che provocano, la scena "antagonisti"
(lui calmo, dietro due uomini di pietra che urlano).
Copertina: statua a destra, a sinistra 2-3 righe grandi (font della copertina), parola chiave nel blocco del colore d'accento,
etichetta "RULE #N" (copertina_regola = SI), firma del canale in basso.
Video: la stessa immagine specchiata (statua a SINISTRA, spazio per il testo a destra) -> statua_video.png (lo usa render_filosofo.py).

PAYLOAD = {"titolo": "...", "testo_copertina": "...", "cartella": "lavoro_statua", "config": {riga di Channel Configs}}
Colonne usate: thumbnail_accent_color, thumbnail_font_url, thumbnail_firma_testo, copertina_regola, language, statua_aspetto (facoltativa).
Uscita: <cartella>/copertina.jpg, statua.png, statua_video.png, risultato.json"""
import io, json, math, os, random, re, time, urllib.request
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps
import costi as CO

P = json.loads(os.environ.get('PAYLOAD') or '{}')
CFG = P.get('config') or {}
CART = P.get('cartella') or 'lavoro_statua'; os.makedirs(CART, exist_ok=True)
W, H = 1280, 720
E = lambda k, d='': os.environ.get(k, d)


def log(*a):
    print('[copertina statua]', *a, flush=True)


def esa(c, rif='#39FF14'):
    c = str(c or rif).strip().lstrip('#')
    if not re.fullmatch(r'[0-9a-fA-F]{6}', c):
        c = rif.lstrip('#')
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


ACC = esa(CFG.get('thumbnail_accent_color'))
BIANCO = esa(CFG.get('thumbnail_highlight_text_color'), '#FFFFFF')


def http(url, dati=None, h=None, raw=False):
    req = urllib.request.Request(url, data=json.dumps(dati).encode() if dati is not None else None,
                                 headers=dict({'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'}, **(h or {})))
    with urllib.request.urlopen(req, timeout=300) as r:
        b = r.read()
        return b if raw else json.loads(b.decode() or '{}')


def font_copertina():
    url = str(CFG.get('thumbnail_font_url') or '').strip() or 'https://cdn.jsdelivr.net/gh/google/fonts@main/ofl/anton/Anton-Regular.ttf'
    f = os.path.join('font', 'copertina_' + re.sub(r'\W+', '_', url.split('/')[-1]))
    os.makedirs('font', exist_ok=True)
    if not os.path.exists(f):
        tmp = f + '.%d' % os.getpid()
        open(tmp, 'wb').write(http(url, raw=True)); os.replace(tmp, f)
    return f


FONT = font_copertina()


# ------------------------------------------------------------------ 1) piano: scritte, gesto, scena (Claude)
GESTI = ['pointing his index finger DIRECTLY at the viewer with the arm extended forward',
         'both hands pressed together with fingertips touching in front of his chest, calm but menacing',
         'one index finger pressed against his temple, piercing stare',
         'one open hand raised with the palm toward the viewer in a firm STOP gesture',
         'arms crossed firmly on his massive chest, chin slightly raised',
         'one fist clenched in front of his chest, jaw tight',
         'one hand on his chin, thinking deeply, eyes locked on the viewer',
         'leaning forward with both elbows on his knees, seated, hands clasped']
ASPETTI = ['thick voluminous curly hair and a full thick curly beard', 'short curly hair and a short sculpted beard',
           'long wavy hair tied back and a long flowing beard', 'shaved head and a dense square beard',
           'wild curly hair and a rough beard', 'neat short hair and a thick trimmed beard']


def piano():
    lingua = {'it': 'italiano', 'en': 'English'}.get(str(CFG.get('language') or 'en')[:2].lower(), 'English')
    regola = str(CFG.get('copertina_regola') or '').strip().upper() == 'SI'
    prompt = (f"Titolo del video YouTube: \"{P.get('titolo', '')}\". Testo copertina proposto: \"{P.get('testo_copertina', '')}\".\n"
              f"Scrivi le scritte della COPERTINA in {lingua}, stile canali stoici di successo: comando o verdetto diretto allo spettatore, "
              "2 o 3 righe, MASSIMO 5 parole in tutto, ogni riga al massimo 11 caratteri, tutto MAIUSCOLO. "
              "Una sola riga e' la parola chiave da evidenziare (la piu' emotiva).\n"
              "Scegli anche la SCENA: \"antagonisti\" se il titolo parla di persone che provocano, manipolano, mancano di rispetto, nemici, rabbia verso altri; "
              "altrimenti \"sola\". Scegli il GESTO della statua (indice 0-7) piu' adatto al messaggio: " +
              ' | '.join(f'{i}: {g}' for i, g in enumerate(GESTI)) + ". "
              "Scegli l'ASPETTO (indice 0-5): " + ' | '.join(f'{i}: {a}' for i, a in enumerate(ASPETTI)) + ". " +
              ("Dai anche un numero di regola da 1 a 12 coerente col titolo (se il titolo ha un numero di principi, usalo). " if regola else '') +
              (f"ISTRUZIONI DEL CANALE (hanno la precedenza): {CFG.get('copertina_istruzioni')}. " if str(CFG.get('copertina_istruzioni') or '').strip() else '') +
              'Rispondi SOLO con JSON: {"righe": ["...", "..."], "evidenza": 0, "scena": "sola", "gesto": 0, "aspetto": 0, "regola": 1}')
    try:
        mod = E('MODELLO_COPERTINA', 'claude-sonnet-5-5')
        r = http('https://api.anthropic.com/v1/messages', {'model': mod, 'max_tokens': 400,
                                                          'messages': [{'role': 'user', 'content': prompt}]},
                 {'x-api-key': E('ANTHROPIC_API_KEY'), 'anthropic-version': '2023-06-01'})
        CO.registra('claude', mod, r.get('usage'), nota='piano copertina')
        t = r['content'][0]['text']
        j, _ = json.JSONDecoder().raw_decode(t[t.index('{'):])
        righe = [str(x).strip().upper() for x in j.get('righe') or [] if str(x).strip()][:3]
        if not righe:
            raise ValueError('nessuna riga')
        pn = {'righe': righe, 'evidenza': max(0, min(len(righe) - 1, int(j.get('evidenza') or 0))),
              'scena': 'antagonisti' if str(j.get('scena')).lower().startswith('antag') else 'sola',
              'gesto': int(j.get('gesto') or 0) % len(GESTI), 'aspetto': int(j.get('aspetto') or 0) % len(ASPETTI),
              'regola': int(j.get('regola') or 0) if regola else 0}
        forza = str(CFG.get('statua_scena') or '').strip().lower()   # colonna statua_scena: sola | antagonisti (vuota = decide Claude)
        if forza in ('sola', 'antagonisti'):
            pn['scena'] = forza
        ammessi = [int(x) for x in re.findall(r'\d+', str(CFG.get('statua_gesti') or '')) if int(x) < len(GESTI)]   # es. "0,2,3"
        if ammessi and pn['gesto'] not in ammessi:
            pn['gesto'] = ammessi[sum(map(ord, P.get('titolo', ''))) % len(ammessi)]
        return pn
    except Exception as e:
        log('piano con Claude non riuscito (' + str(e)[:120] + '): uso il testo copertina')
        parole = (str(P.get('testo_copertina') or P.get('titolo') or 'STAY STRONG').upper().split())[:5]
        righe = [' '.join(parole[i:i + 2]) for i in range(0, len(parole), 2)][:3]
        sem = sum(map(ord, P.get('titolo', '')))
        return {'righe': righe, 'evidenza': len(righe) - 1, 'scena': 'sola', 'gesto': sem % len(GESTI),
                'aspetto': sem % len(ASPETTI), 'regola': (sem % 12 + 1) if regola else 0}


# ------------------------------------------------------------------ 2) statua (fal)
STATUA = ('Hyper-detailed photorealistic statue carved in smooth dark-grey and charcoal marble, monochrome stone, in the style of epic Stoic YouTube thumbnails. '
          'A YOUNG, vigorous, powerful Greek warrior-philosopher in his early 30s, with a HUGE bodybuilder physique: massive chest, broad shoulders, '
          'enormous arms, thick neck, deeply carved abs and visible veins. {aspetto}, strong jaw. '
          'Intense, fierce, dominant stare with a deep frown, the eyes look straight at the viewer. {posa}. '
          'Dramatic cinematic light from above and the side, strong rim light on the muscles, deep black shadows, very high contrast, '
          'polished clean stone surface with fine sculpted detail, conveys perfection and raw power. {fondo} No text, no logo, no watermark.')


def fal(modello, dati):
    CO.registra('fal', modello, dollari=0.08 if 'nano-banana' in modello else 0.005)
    h = {'Authorization': 'Key ' + E('FAL_KEY')}
    inv = http('https://queue.fal.run/' + modello, dati, h)
    for _ in range(150):
        time.sleep(4)
        st = http(inv['status_url'], h=h)
        if st.get('status') == 'COMPLETED':
            return http(inv['response_url'], h=h)
        if st.get('status') not in ('IN_QUEUE', 'IN_PROGRESS'):
            raise RuntimeError(json.dumps(st)[:300])
    raise RuntimeError('fal: tempo scaduto')


def statua(pn):
    aspetto = str(CFG.get('statua_aspetto') or '').strip() or ASPETTI[pn['aspetto']]
    if pn['scena'] == 'antagonisti':
        posa = ('Seen from the knees up, seated cross-legged in a calm meditation pose in the center-right of the image, hands on the knees. '
                'Behind him, out of focus, two furious men carved in rough stone scream and shout at him, but he is perfectly calm and untouched. '
                'The LEFT 45% of the image is empty dark space')
        fondo, formato = 'Dark grey smoky background with vignette.', '16:9'
    else:
        posa = 'Waist-up, big in the frame, ' + GESTI[pn['gesto']]
        fondo, formato = 'Plain dark-grey gradient studio background with a little soft smoke at the bottom, nothing else.', '3:4'
    r = fal(E('MODELLO_STATUA', 'fal-ai/nano-banana-2'), {'prompt': STATUA.format(aspetto=aspetto[0].upper() + aspetto[1:], posa=posa, fondo=fondo),
                                                          'aspect_ratio': formato, 'resolution': '1K', 'output_format': 'png', 'num_images': 1})
    f = os.path.join(CART, 'statua.png')
    open(f, 'wb').write(http(r['images'][0]['url'], raw=True))
    log('statua pronta:', pn['scena'], '|', posa[:70])
    if pn['scena'] == 'sola':   # statua scontornata: sempre lo STESSO fondo scuro del canale, senza stacchi
        try:
            sc = fal('fal-ai/birefnet', {'image_url': r['images'][0]['url']})
            open(f, 'wb').write(http((sc.get('image') or {}).get('url'), raw=True))
            log('statua scontornata')
        except Exception as e:
            log('scontorno non riuscito (' + str(e)[:100] + '): uso il fondo originale')
    return f


# ------------------------------------------------------------------ 3) composizione (copertina e immagine del video)
def grigio(im):
    g = ImageOps.autocontrast(ImageOps.grayscale(im), cutoff=0.5).point(lambda v: int(255 * (v / 255) ** 0.8))
    return ImageEnhance.Contrast(g.convert('RGB')).enhance(1.1)


def scala(im, h):
    return im.resize((int(im.width * h / im.height), h), Image.LANCZOS)


def fondo_canale(w, h):
    """grigio scuro con luce dietro la statua (a destra) e fumo basso: lo stesso per copertina e video"""
    c = Image.new('RGB', (w, h), (14, 14, 16))
    luce = Image.new('L', (w, h), 0); ImageDraw.Draw(luce).ellipse([w * .45, -h * .2, w * 1.15, h * 1.1], fill=255)
    c = Image.composite(Image.new('RGB', (w, h), (78, 78, 82)), c, luce.filter(ImageFilter.GaussianBlur(w * .12)))
    rnd = random.Random(3); fw, fh = w // 16, h // 16
    n = Image.new('L', (fw, fh)); n.putdata([rnd.randint(0, 255) for _ in range(fw * fh)])
    n = n.resize((w, h), Image.BICUBIC).filter(ImageFilter.GaussianBlur(w * .02))
    basso = Image.linear_gradient('L').resize((w, h)).point(lambda v: max(0, v - 120) * 2)
    fumo = ImageChops_multiply(ImageOps.autocontrast(n), basso).point(lambda v: int(v * .55))
    return Image.composite(Image.new('RGB', (w, h), (150, 150, 155)), c, fumo)


def ImageChops_multiply(a, b):
    from PIL import ImageChops
    return ImageChops.multiply(a, b)


def scena_destra(png, scena, w, h):
    """statua a DESTRA, lato sinistro scurito per il testo (copertina). Il video usa la stessa scena specchiata."""
    src = Image.open(png)
    if src.mode == 'RGBA' and src.getchannel('A').getextrema()[0] < 20:   # scontornata: fondo del canale (grigio scuro + fumo in basso)
        a = src.getchannel('A'); im = grigio(src.convert('RGB')); im.putalpha(a)
        bb = a.getbbox() or (0, 0, im.width, im.height)
        im = im.crop(bb)   # solo la statua, senza margini vuoti
        zoom = float(str(CFG.get('statua_zoom') or 1.5).replace(',', '.'))   # >1 = primo piano: testa e busto grandi (da mobile si vede)
        im = scala(im, int(h * zoom))
        if im.width > w * .56:   # mai oltre ~56% della larghezza: a sinistra resta lo spazio delle scritte
            im = im.crop(((im.width - int(w * .56)) // 2, 0, (im.width + int(w * .56)) // 2, im.height))
            al = im.getchannel('A'); fade = int(im.width * .12)   # bordo sinistro sfumato: niente taglio netto
            gr = Image.linear_gradient('L').rotate(90).resize((fade, im.height))
            al.paste(ImageChops_multiply(al.crop((0, 0, fade, im.height)), gr), (0, 0)); im.putalpha(al)
        c = fondo_canale(w, h)
        c.paste(im, (w - im.width + int(w * .02), int(h * .03)), im)   # testa in alto, il corpo esce dal fondo
        v = Image.new('L', (w, h), 0); ImageDraw.Draw(v).rectangle([0, 0, w * .45, h], fill=120)
        return Image.composite(Image.new('RGB', (w, h), (8, 8, 10)), c, v.filter(ImageFilter.GaussianBlur(w * .08)))
    im = grigio(src.convert('RGB'))
    if scena == 'antagonisti':
        im = scala(im, h); im = im.crop((max(0, im.width - w), 0, im.width, h)).resize((w, h))
        c = im; buio = .42
    else:
        im = scala(im, int(h * 1.08)); bg = im.getpixel((8, im.height // 3))
        c = Image.new('RGB', (w, h), bg)
        m = Image.new('L', im.size, 255); dm = ImageDraw.Draw(m)
        for x in range(int(w * .09)):
            dm.line([(x, 0), (x, im.height)], fill=int(255 * x / (w * .09)))
        c.paste(im, (w - im.width, -int(h * .02)), m); buio = .5
    v = Image.new('L', (w, h), 0); ImageDraw.Draw(v).rectangle([0, 0, w * buio, h], fill=160)
    return Image.composite(Image.new('RGB', (w, h), (8, 8, 10)), c, v.filter(ImageFilter.GaussianBlur(w * .09)))


def riga(d, txt, x, y, larg, col, box, sz_max):
    sz = sz_max
    while sz > 30:
        f = ImageFont.truetype(FONT, sz); b = f.getbbox(txt)
        if b[2] - b[0] <= larg:
            break
        sz -= 3
    b = f.getbbox(txt); tw = b[2] - b[0]
    if box:
        p = sz * .1
        d.rectangle([x - p, y + b[1] - p * .7, x + tw + p, y + b[3] + p * .7], fill=box)
        d.text((x - b[0], y), txt, font=f, fill=(10, 10, 10))
    else:
        for dx, dy in ((5, 6), (2, 3)):
            d.text((x - b[0] + dx, y + dy), txt, font=f, fill=(0, 0, 0))
        d.text((x - b[0], y), txt, font=f, fill=col)
    return y + b[3] + sz * .06


def blocco(d, pn, x, y0, larg, y1):
    for sm in range(230, 60, -6):
        y = y0; dd = ImageDraw.Draw(Image.new('RGB', (8, 8)))
        for i, t in enumerate(pn['righe']):
            y = riga(dd, t, x, y, larg, BIANCO, ACC if i == pn['evidenza'] else None, sm)
        if y <= y1:
            break
    y = y0 + (y1 - y) / 2
    for i, t in enumerate(pn['righe']):
        y = riga(d, t, x, y, larg, BIANCO, ACC if i == pn['evidenza'] else None, sm)


def copertina(png, pn):
    c = scena_destra(png, pn['scena'], W, H); d = ImageDraw.Draw(c)
    x = 55; larg = (440 if pn['scena'] == 'antagonisti' else 600)
    if pn.get('regola'):
        f = ImageFont.truetype(FONT, 54); t = f'RULE #{pn["regola"]}'; b = f.getbbox(t)
        d.rounded_rectangle([x, 60, x + b[2] + 36, 138], radius=10, outline=ACC, width=5); d.text((x + 18, 66), t, font=f, fill=ACC)
    blocco(d, pn, x, 160 if pn.get('regola') else 70, larg, H - 90)
    firma = str(CFG.get('thumbnail_firma_testo') or '').strip()
    if firma:
        d.text((x + 2, H - 50), firma, font=ImageFont.truetype(FONT, 26), fill=ACC)
    f = os.path.join(CART, 'copertina.jpg'); c.save(f, quality=93)
    return f


def immagine_video(png, pn):
    """1920x1080: la scena della copertina SPECCHIATA (statua a sinistra, spazio a destra per il testo), senza scritte."""
    c = ImageOps.mirror(scena_destra(png, pn['scena'], 1920, 1080))
    f = os.path.join(CART, 'statua_video.png'); c.save(f)
    return f


if __name__ == '__main__':
    ris = {'ok': False}
    try:
        pn = piano(); log('piano:', pn)
        png = statua(pn)
        ris = {'ok': True, 'copertina': copertina(png, pn), 'statua': png, 'statua_video': immagine_video(png, pn), 'piano': pn}
        log('copertina e immagine del video pronte')
    except Exception as e:
        ris = {'ok': False, 'errore': str(e)[:300]}
        log('NON RIUSCITA:', ris['errore'])
    json.dump(ris, open(os.path.join(CART, 'risultato.json'), 'w'), ensure_ascii=False)
