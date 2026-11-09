#!/usr/bin/env python3
"""PROVA STILE GLOAM v4 (9 nov, Giorgio con 8 fotogrammi del video Binance di Gloam: "se parliamo di aziende e notizie vanno aggiunte anche foto Pexels coerenti").
Il vero stile di Gloam e' EDITORIALE / DOSSIER, non 3D: carta beige, serif elegante + scritte a macchina (mono) spaziate, timbri rossi, fonti citate,
foto e filmati incorniciati e inclinati con etichetta "■ LUOGO · DATA", numeri enormi in serif su fondo scuro, calendari, classifiche su carta,
cartelli con parola rossa + parola nera su carta strappata. Qui tutto e' disegnato in codice (gratis) con foto/clip Pexels coerenti; niente filmati di TG (diritti).
Uscita: prove_video/Prova_Gloam4/. Non carica niente."""
import io, json, math, os, random, re, subprocess, sys, time, urllib.parse
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prova_gloam3 as G3   # http, pexels (clip, scarta fondo verde), voce, durata, suoni, borsa

E = os.environ.get
OUT = 'prove_video/Prova_Gloam4'; os.makedirs(OUT, exist_ok=True)
LAV = '/tmp/gloam4'; os.makedirs(LAV, exist_ok=True)
TEMA = E('TEMA') or 'How Knight Capital Lost $440,000,000 in 45 Minutes (August 1, 2012)'
W, H, FPS = 1920, 1080, 30
SERIF, MONO, BOLD = 'fonts_gloam/serif.woff', 'fonts_gloam/mono.woff', 'fonts_gloam/oswald.woff'
CARTA, INCH, ROSSO, CREMA = (232, 224, 203), (28, 26, 24), (178, 34, 34), (240, 236, 226)
log = G3.log
_F = {}
F = lambda f, s: _F.setdefault((f, s), ImageFont.truetype(f, s))
cl = lambda x: max(0.0, min(1.0, x))
ease = lambda x: 1 - (1 - cl(x)) ** 3


# ---------------------------------------------------------------- copione
def copione():
    fc = os.path.join(OUT, 'copione.json')
    if os.path.exists(fc) and not E('TEMA'):
        c = json.load(open(fc)); log('copione ripreso'); return c
    prompt = f"""You write for a new English YouTube channel copying the style of "Gloam" (finance/company disasters told like an investigation: calm, precise narrator; editorial "dossier" visuals).
Topic: {TEMA}. ONLY well documented facts with correct dates and times; if unsure of a detail, leave it out. No invented quotes.
60-second test episode: 130-150 spoken words, 14-17 shots (one every 3-5 s). Shot 1 = hook with the big number. Open a loop in the first 10 s, answer it in the last 10 s. End with "Subscribe for the next one."
Each shot: "voce" (numbers in words) + ONE "tipo" with its fields:
- "foto": a real photo framed and tilted like an archive print. "cerca" = 2-4 plain English words for a COHERENT stock photo (place, building, object, people at work: e.g. "new york stock exchange", "wall street sign", "trading floor traders", "server room", "jersey city office"). "etichetta" = "PLACE · DATE" (e.g. "NEW YORK · AUG 1, 2012").
- "clip": full-screen stock footage. "cerca" as above (filmable). Optional "cartello" = 2-4 words, CAPITALS, where the FIRST word is the key word (shown in red), e.g. "NOBODY PRESSED STOP".
- "dossier": a file card. "scheda" (tab, e.g. "COMPANY FILE", "THE CODE"), "nome" (title), "righe": 3-5 [label, value] pairs (short, factual), "cerca_foto" (stock photo for the card, or "" for a silhouette).
- "dato": a huge number. "numero" (e.g. "$440M", "~75%", "45 MIN"), "didascalia" (max 8 words, what it means), "fonte" (e.g. "SEC FILING 2013").
- "calendario": a date page. "mese" (3 letters), "giorno" (number), "titolo" (max 4 words), "sotto" (max 10 words), "timbro" (max 3 words or "").
- "classifica": paper chart. "titolo", "barre": 2-4 [label, value number, value text], "timbro" (max 4 words, e.g. "4x A NORMAL DAY"), "fonte".
- "borsa": a live trading screen where the stock collapses: "ticker", "da", "a" (prices). Max 1 time, only if the stock really fell (check the real numbers and timing).
Mix: at least 6 "foto"/"clip" (real images, coherent with the story), and use each graphic type at least once. Never two identical types in a row.
Also "titolo" and "copertina": {{"cerca": "stock photo words", "scritta": "max 3 words, CAPITALS"}}.
Reply ONLY with JSON: {{"titolo": "...", "copertina": {{...}}, "shots": [{{"voce": "...", "tipo": "foto", ...}}]}}"""
    for k in range(3):
        j = G3.http('https://api.anthropic.com/v1/messages', {'model': 'claude-sonnet-5-5', 'max_tokens': 16000, 'thinking': {'type': 'between_tools'},
                                                               'output_config': {'effort': 'medium'}, 'messages': [{'role': 'user', 'content': prompt}]},
                    {'x-api-key': E('ANTHROPIC_API_KEY', ''), 'anthropic-version': '2023-06-01'})
        u = j.get('usage') or {}
        G3.COSTO['claude'] += u.get('input_tokens', 0) * 3e-6 + u.get('output_tokens', 0) * 15e-6
        t = ''.join(b.get('text', '') for b in j['content'] if b.get('type') == 'text')
        if '{' in t:
            break
    m = re.search(r'\{.*\}', t, re.S).group(0)
    try:
        c = json.loads(m)
    except Exception:
        from json_repair import repair_json
        c = json.loads(repair_json(m))
    json.dump(c, open(fc, 'w'), ensure_ascii=False, indent=1)
    log('copione:', c['titolo'], len(c['shots']), 'scene', [s.get('tipo') for s in c['shots']])
    return c


# ---------------------------------------------------------------- foto Pexels coerenti
FOTO_USATE = set()


def foto_pexels(cerca, i):
    for q in [cerca, ' '.join(str(cerca).split()[:2]), 'wall street', 'office building']:
        try:
            j = G3.http('https://api.pexels.com/v1/search?' + urllib.parse.urlencode({'query': q, 'orientation': 'landscape', 'per_page': 15}),
                        headers={'Authorization': E('PEXELS_API_KEY', ''), 'User-Agent': 'Mozilla/5.0'})
        except Exception as e:
            log('pexels foto:', e); continue
        for p in j.get('photos', []):
            if p['id'] in FOTO_USATE:
                continue
            FOTO_USATE.add(p['id'])
            im = Image.open(io.BytesIO(G3.http(p['src']['large2x'], raw=True, headers={'User-Agent': 'Mozilla/5.0'}))).convert('RGB')
            log(f'foto {i}: "{q}" -> {p["id"]}')
            return im
    return Image.new('RGB', (1600, 1000), (60, 60, 60))


# ---------------------------------------------------------------- materiali grafici
def carta(w, h, seme=0):
    """Carta beige con grana e bordi piu' scuri."""
    random.seed(seme)
    base = Image.new('RGB', (w, h), CARTA)
    rum = Image.effect_noise((w, h), 18).convert('RGB')
    base = Image.blend(base, rum, .06)
    vig = Image.new('L', (w, h), 0); d = ImageDraw.Draw(vig)
    d.rectangle((0, 0, w, h), fill=60); d.rectangle((25, 25, w - 25, h - 25), fill=0)
    vig = vig.filter(ImageFilter.GaussianBlur(30))
    scuro = Image.new('RGB', (w, h), (170, 150, 115))
    return Image.composite(scuro, base, vig)


def fondo_scuro(t):
    """Fondo nero caldo con vignetta e grana che si muove (mai immagine ferma)."""
    if not hasattr(fondo_scuro, 'b'):
        b = Image.new('RGB', (W, H), (10, 9, 8)); d = ImageDraw.Draw(b)
        for r in range(900, 0, -30):
            c = int(34 * (1 - r / 900)); d.ellipse((W / 2 - r * 1.4, H / 2 - r, W / 2 + r * 1.4, H / 2 + r), fill=(10 + c, 9 + c, 8 + c))
        fondo_scuro.b = b.filter(ImageFilter.GaussianBlur(60))
    g = Image.effect_noise((W // 4, H // 4), 22).convert('RGB').resize((W, H))
    return Image.blend(fondo_scuro.b, g, .035)


def ombra_incolla(fr, card, x, y, ang=0, sc=1.0, alpha=1.0):
    if sc != 1.0:
        card = card.resize((max(1, int(card.width * sc)), max(1, int(card.height * sc))), Image.BILINEAR)
    c = card.convert('RGBA').rotate(ang, resample=Image.BICUBIC, expand=True)
    m = c.split()[3]
    if alpha < 1:
        m = m.point(lambda v: int(v * alpha)); c.putalpha(m)
    sh = Image.new('RGBA', c.size, (0, 0, 0, 0)); sh.putalpha(m.point(lambda v: int(v * .55)))
    sh = sh.filter(ImageFilter.GaussianBlur(18))
    fr.alpha_composite(sh, (int(x - c.width / 2 + 14), int(y - c.height / 2 + 22)))
    fr.alpha_composite(c, (int(x - c.width / 2), int(y - c.height / 2)))


def timbro(testo, colore=ROSSO):
    f = F(BOLD, 86); w = int(f.getlength(testo)) + 70
    im = Image.new('RGBA', (w, 150), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rectangle((6, 6, w - 6, 144), outline=colore + (230,), width=9)
    d.text((35, 22), testo, font=f, fill=colore + (230,))
    rum = Image.effect_noise(im.size, 60).point(lambda v: 255 if v > 95 else 120)   # inchiostro irregolare
    a = im.split()[3]; im.putalpha(Image.composite(a, Image.new('L', im.size, 0), rum))
    return im.rotate(-8, expand=True, resample=Image.BICUBIC)


def spazia(t, n=4):
    return (' ' * 0).join(ch + ' ' * (1 if n else 0) for ch in t).strip()


def scrivi(d, xy, t, f, col, spaz=0, anc='la'):
    if spaz:
        x, y = xy
        if anc != 'la':
            tot = sum(f.getlength(ch) + spaz for ch in t); x = x - tot / 2 if anc == 'ma' else x - tot
        for ch in t:
            d.text((x, y), ch, font=f, fill=col); x += f.getlength(ch) + spaz
    else:
        d.text(xy, t, font=f, fill=col, anchor=anc)


def adatta(f_path, t, size, maxw):
    while F(f_path, size).getlength(t) > maxw and size > 20:
        size -= 2
    return F(f_path, size)


# ---------------------------------------------------------------- scene disegnate (fotogrammi)
def scena_foto(s, img, t, d):
    fr = fondo_scuro(t).convert('RGBA')
    fw, fh = 1380, 820
    z = 1 + .06 * t / d; iw, ih = int(fw * z), int(fh * z)
    ph = ImageOps.fit(img, (iw, ih), Image.BILINEAR).crop(((iw - fw) // 2, (ih - fh) // 2, (iw - fw) // 2 + fw, (ih - fh) // 2 + fh))
    card = Image.new('RGB', (fw + 36, fh + 36), CREMA); card.paste(ph, (18, 18))
    e = ease(t / .5)
    ombra_incolla(fr, card, W / 2, H / 2 + 30 + 60 * (1 - e), ang=2.2 - 1.2 * e, alpha=e)
    d_ = ImageDraw.Draw(fr)
    if s.get('etichetta'):
        d_.rectangle((80, 52, 92, 64), fill=(230, 160, 40))
        scrivi(d_, (110, 40), str(s['etichetta']).upper()[:40], F(MONO, 30), (215, 210, 200), spaz=3)
    return fr


def scena_dossier(s, img, t, d):
    fr = fondo_scuro(t).convert('RGBA')
    if not hasattr(s, '_c') and '_card' not in s:
        cw, ch = 1300, 760
        c = carta(cw, ch, 1).convert('RGBA'); dd = ImageDraw.Draw(c)
        tab = Image.new('RGBA', (360, 80), CARTA + (255,)); ImageDraw.Draw(tab).text((34, 22), str(s.get('scheda') or 'FILE').upper()[:16], font=F(MONO, 32), fill=(80, 75, 65))
        foto = Image.new('RGB', (360, 450), (60, 62, 66)); fd = ImageDraw.Draw(foto)
        if img is not None:
            foto = ImageOps.fit(img, (360, 450)).convert('L').convert('RGB')
        else:
            fd.ellipse((110, 90, 250, 250), fill=(25, 25, 28)); fd.rounded_rectangle((60, 240, 300, 470), 80, fill=(25, 25, 28))
            fd.text((180, 160), '?', font=F(SERIF, 70), fill=(70, 70, 75), anchor='mm')
        cf = Image.new('RGB', (390, 480), CREMA); cf.paste(foto, (15, 15)); c.paste(cf.rotate(1.5, expand=True, fillcolor=CARTA), (70, 120))
        if img is None:
            dd.text((265, 650), 'No photograph', font=F(MONO, 26), fill=(110, 100, 85), anchor='mm')
        nome = str(s.get('nome') or '')
        dd.text((540, 110), nome, font=adatta(SERIF, nome, 110, 700), fill=INCH)
        dd.line((540, 250, 1230, 250), fill=(90, 85, 75), width=3)
        for k, (a, b) in enumerate((s.get('righe') or [])[:5]):
            y = 290 + k * 80
            scrivi(dd, (540, y + 10), str(a).upper()[:14], F(MONO, 26), (110, 100, 85), spaz=3)
            dd.text((760, y), str(b)[:28], font=adatta(MONO, str(b)[:28], 42, 470), fill=INCH)
        s['_card'] = (c, tab)
    c, tab = s['_card']
    full = Image.new('RGBA', (c.width, c.height + 70), (0, 0, 0, 0)); full.alpha_composite(tab, (60, 0)); full.alpha_composite(c, (0, 70))
    e = ease(t / .55)
    ombra_incolla(fr, full, W / 2 - 40, H / 2 + 20 + 80 * (1 - e), ang=-1.2 + .8 * e, sc=1 + .03 * t / d, alpha=e)
    return fr


def scena_dato(s, img, t, d):
    fr = fondo_scuro(t).convert('RGBA'); dd = ImageDraw.Draw(fr)
    num = str(s.get('numero') or '')
    m = re.match(r'^([^\d]*)([\d.,]+)(.*)$', num)
    if m:   # il numero corre fino al valore
        v = float(m.group(2).replace(',', '')); k = ease(t / max(.8, d * .45))
        dec = len(m.group(2).split('.')[1]) if '.' in m.group(2) else 0
        num = m.group(1) + (f'{v * k:,.{dec}f}') + m.group(3)
    f = adatta(SERIF, str(s.get('numero') or ''), 300, 1500)
    a = int(255 * ease(t / .4))
    lay = Image.new('RGBA', (W, H), (0, 0, 0, 0)); ld = ImageDraw.Draw(lay)
    ld.text((W / 2, 430), num, font=f, fill=CREMA + (a,), anchor='mm')
    if t > .6:
        b = int(255 * ease((t - .6) / .5))
        scrivi(ld, (W / 2, 640), str(s.get('didascalia') or '').upper()[:60], adatta(MONO, str(s.get('didascalia') or '').upper()[:60], 38, 1300 / 1.4), (200, 195, 185, b), spaz=6, anc='ma')
        if s.get('fonte'):
            scrivi(ld, (W / 2, 715), ('SOURCE: ' + str(s['fonte'])).upper()[:50], F(MONO, 22), (120, 115, 108, b), spaz=5, anc='ma')
    fr.alpha_composite(lay)
    return fr


def scena_calendario(s, img, t, d):
    fr = fondo_scuro(t).convert('RGBA')
    e = ease(t / .5)
    pag = Image.new('RGBA', (420, 460), CREMA + (255,)); pd = ImageDraw.Draw(pag)
    pd.rectangle((0, 0, 420, 80), fill=ROSSO); scrivi(pd, (210, 18), str(s.get('mese') or '').upper()[:3], F(MONO, 38), (245, 240, 230), spaz=10, anc='ma')
    pd.text((210, 280), str(s.get('giorno') or ''), font=F(SERIF, 260), fill=INCH, anchor='mm')
    ombra_incolla(fr, pag, 420, 540 + 40 * (1 - e), alpha=e)
    lay = Image.new('RGBA', (W, H), (0, 0, 0, 0)); ld = ImageDraw.Draw(lay)
    b = int(255 * ease((t - .4) / .5))
    tit = str(s.get('titolo') or '')
    ld.text((760, 380), tit, font=adatta(SERIF, tit, 110, 1080), fill=CREMA + (b,))
    sot = str(s.get('sotto') or '').upper()[:60]
    scrivi(ld, (765, 540), sot, adatta(MONO, sot, 32, 1060 / 1.45), (190, 185, 175, b), spaz=5)
    fr.alpha_composite(lay)
    if s.get('timbro') and t > d * .45:
        k = cl((t - d * .45) / .18); tb = timbro(str(s['timbro']).upper()[:20])
        ombra_incolla(fr, tb, 1500, 170, sc=1.6 - .6 * ease(k), alpha=k)
    return fr


def scena_classifica(s, img, t, d):
    fr = fondo_scuro(t).convert('RGBA')
    if '_card' not in s:
        c = carta(1300, 640, 2).convert('RGBA'); s['_card'] = c
    c = s['_card'].copy(); dd = ImageDraw.Draw(c)
    scrivi(dd, (70, 60), str(s.get('titolo') or '').upper()[:48], F(MONO, 34), (60, 56, 50), spaz=4)
    dd.line((70, 120, 1230, 120), fill=(120, 110, 95), width=2)
    B = (s.get('barre') or [])[:4]; mx = max([float(b[1]) for b in B] + [1])
    for k, b in enumerate(B):
        y = 160 + k * (380 // max(1, len(B)))
        scrivi(dd, (70, y), str(b[0]).upper()[:40], F(MONO, 28), (60, 56, 50), spaz=3)
        g = ease((t - .3 - k * .35) / .8); w = int(820 * float(b[1]) / mx * g)
        dd.rectangle((70, y + 50, 70 + max(w, 4), y + 120), fill=ROSSO if k == 0 else (55, 60, 72))
        if g > .5:
            dd.text((95 + w, y + 46), str(b[2]), font=F(SERIF, 68), fill=INCH)
    if s.get('fonte'):
        scrivi(dd, (70, 585), ('SOURCES: ' + str(s['fonte'])).upper()[:60], F(MONO, 22), (110, 100, 85), spaz=3)
    e = ease(t / .5)
    ombra_incolla(fr, c, W / 2, H / 2 + 50 * (1 - e), ang=-1, alpha=e, sc=1 + .025 * t / d)
    if s.get('timbro') and t > d * .55:
        k = cl((t - d * .55) / .18); tb = timbro(str(s['timbro']).upper()[:22])
        ombra_incolla(fr, tb, 1380, 760, sc=1.6 - .6 * ease(k), alpha=k)
    return fr


DISEGNA = {'foto': scena_foto, 'dossier': scena_dossier, 'dato': scena_dato, 'calendario': scena_calendario, 'classifica': scena_classifica}


def rendi(i, s, img, dur, out):
    enc = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                            '-c:v', 'libx264', '-preset', 'medium', '-crf', '19', '-pix_fmt', 'yuv420p', out], stdin=subprocess.PIPE)
    for k in range(int(dur * FPS) + 1):
        enc.stdin.write(DISEGNA[s['tipo']](s, img, k / FPS, dur).convert('RGB').tobytes())
    enc.stdin.close(); enc.wait()


def cartello_png(testo, f):
    """Cartello su carta strappata: prima parola rossa, il resto nero (come "NOBODY WALKED IN")."""
    p = testo.upper().split(); fo = F(BOLD, 110)
    w = int(sum(fo.getlength(x + ' ') for x in p)) + 90
    c = carta(w, 170, 3).convert('RGBA'); d = ImageDraw.Draw(c); x = 45
    for k, parola in enumerate(p):
        d.text((x, 12), parola, font=fo, fill=ROSSO if k == 0 else INCH); x += fo.getlength(parola + ' ')
    m = Image.new('L', c.size, 255); md = ImageDraw.Draw(m); random.seed(len(testo))   # bordi strappati
    for xx in range(0, w, 6):
        md.rectangle((xx, 0, xx + 6, random.randint(0, 9)), fill=0); md.rectangle((xx, 170 - random.randint(0, 9), xx + 6, 170), fill=0)
    c.putalpha(m)
    lay = Image.new('RGBA', (W, H), (0, 0, 0, 0)); ombra_incolla(lay, c.rotate(-1.5, expand=True), W / 2, H - 230)
    lay.save(f)


def scena_clip(i, s, dur, out):
    f, d0 = s['_clip']; ss = max(0.0, random.uniform(0, max(0.0, d0 - dur - .5)))
    base = f'scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps=30,setsar=1,eq=saturation=0.85:contrast=1.06'
    if s.get('cartello'):
        lab = os.path.join(LAV, f'cart_{i}.png'); cartello_png(str(s['cartello'])[:30], lab)
        vf = f"[0:v]{base}[b];[1:v]format=rgba,fade=t=in:st=0.5:d=0.2:alpha=1[l];[b][l]overlay=0:0,format=yuv420p[o]"
        inp = ['-loop', '1', '-t', f'{dur:.3f}', '-i', lab]
    else:
        vf = f"[0:v]{base},format=yuv420p[o]"; inp = []
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{ss:.2f}', '-stream_loop', '-1', '-i', f, *inp, '-filter_complex', vf, '-map', '[o]',
                    '-t', f'{dur:.3f}', '-r', '30', '-an', '-c:v', 'libx264', '-preset', 'medium', '-crf', '19', out], check=True)


def main():
    c = copione(); shots = c['shots']
    imgs = {}
    for i, s in enumerate(shots):
        tp = s.get('tipo')
        if tp == 'clip':
            s['_clip'] = G3.pexels(s.get('cerca') or 'wall street', i)
        elif tp == 'foto':
            imgs[i] = foto_pexels(s.get('cerca') or 'wall street', i)
        elif tp == 'dossier' and s.get('cerca_foto'):
            imgs[i] = foto_pexels(s['cerca_foto'], i)
    boom, whoosh = G3.suoni()
    parti, audio = [], []
    for i, s in enumerate(shots):
        v = G3.voce(i, s['voce']); d = G3.durata(v) + .15
        out = os.path.join(LAV, f'scena_{i:02d}.mp4')
        tp = s.get('tipo')
        if tp == 'clip':
            scena_clip(i, s, d, out)
        elif tp == 'borsa':
            G3.borsa(i, s, d, out)
        else:
            if tp not in DISEGNA:
                s['tipo'] = tp = 'foto'; imgs[i] = foto_pexels(s.get('cerca') or 'wall street', i)
            rendi(i, s, imgs.get(i), d, out)
        parti.append(out)
        a = os.path.join(LAV, f'a_{i:02d}.wav')
        fx = boom if (tp in ('calendario', 'classifica') and s.get('timbro')) or tp in ('dato', 'borsa') else (whoosh if tp in ('foto', 'dossier') else None)
        ritardo = int((d * (.45 if tp == 'calendario' else .55 if tp == 'classifica' else 0)) * 1000)
        if fx:
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', v, '-i', fx, '-filter_complex',
                            f'[0:a]aresample=44100,aformat=channel_layouts=stereo,apad,atrim=0:{d:.3f}[v];[1:a]adelay={ritardo}|{ritardo},volume=0.45[f];[v][f]amix=inputs=2:duration=first:normalize=0',
                            '-ar', '44100', '-ac', '2', a], check=True)
        else:
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', v, '-af', f'apad,atrim=0:{d:.3f}', '-ar', '44100', '-ac', '2', a], check=True)
        audio.append(a); log('scena', i + 1, tp, f'{d:.1f} s')
    open(os.path.join(LAV, 'v.txt'), 'w').write(''.join(f"file '{p}'\n" for p in parti))
    open(os.path.join(LAV, 'a.txt'), 'w').write(''.join(f"file '{p}'\n" for p in audio))
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', os.path.join(LAV, 'v.txt'), '-c', 'copy', os.path.join(LAV, 'video.mp4')], check=True)
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', os.path.join(LAV, 'a.txt'), os.path.join(LAV, 'voce.wav')], check=True)
    tot = G3.durata(os.path.join(LAV, 'voce.wav'))
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', os.path.join(LAV, 'video.mp4'), '-i', os.path.join(LAV, 'voce.wav'), '-stream_loop', '-1', '-i', 'libreria_musica/mistero_003.mp3',
                    '-filter_complex', f'[2:a]volume=0.10,afade=t=out:st={max(0, tot - 2):.2f}:d=2[m];[1:a][m]amix=inputs=2:duration=first:normalize=0[a]',
                    '-map', '0:v', '-map', '[a]', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '160k', '-t', f'{tot:.2f}', os.path.join(OUT, 'video_prova.mp4')], check=True)
    # copertina: foto coerente incorniciata + cartello strappato (stile del canale)
    cp = c.get('copertina') or {}
    fr = scena_foto({'etichetta': ''}, foto_pexels(cp.get('cerca') or 'wall street', 99), 2, 4)
    lab = os.path.join(LAV, 'cart_cop.png'); cartello_png(str(cp.get('scritta') or 'GONE')[:24], lab)
    fr.alpha_composite(Image.open(lab)); fr.convert('RGB').resize((1280, 720), Image.LANCZOS).save(os.path.join(OUT, 'copertina.jpg'), quality=92)
    tv = G3.durata(os.path.join(OUT, 'video_prova.mp4'))
    for k in range(1, 9):
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{tv * (k - .5) / 8:.2f}', '-i', os.path.join(OUT, 'video_prova.mp4'), '-frames:v', '1', '-vf', 'scale=960:-1',
                        os.path.join(OUT, f'fotogramma_{k}.jpg')], check=True)
    costo = f"durata {tv:.0f} s | scene {len(shots)} | Claude {G3.COSTO['claude']:.3f} $ | immagini AI 0 | foto e clip Pexels gratis | voce {G3.COSTO['voce_caratteri']} crediti"
    open(os.path.join(OUT, 'costo.txt'), 'w').write(costo + '\n'); log('FATTO:', costo)


if __name__ == '__main__':
    main()
