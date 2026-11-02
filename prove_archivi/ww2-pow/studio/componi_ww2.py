import math, random
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageEnhance, ImageFilter
F = '/tmp/claude-0/-home-claude/42780c28-4eb1-5b2d-abae-e2eeedb35095/scratchpad/font/'
C = '/home/claude/ambience/prove_archivi/ww2-pow/'
ANTON = lambda s: ImageFont.truetype(F + 'Anton.ttf', s)
TYPE = lambda s: ImageFont.truetype(F + 'SpecialElite.ttf', s)
W, H = 1280, 720
GIALLO, ROSSO = (255, 214, 0), (214, 20, 20)
# (file, soggetto x,y, secondo dettaglio x,y, testo A, testo B, testo C, titolo)
COP = [('storico_5_4.jpg', (.22, .40), (.55, .33), 'ONE FIGHTER?!', 'HE NAMED ONE FIGHTER', 'ONE FIGHTER.', 'They Asked Göring Why the Luftwaffe Lost. He Named One Fighter.'),
       ('storico_3_3.jpg', (.47, .47), (.27, .84), 'SOUP?!', "THEY DIDN'T BELIEVE IT", 'NOT A TRICK.', 'German POWs Expected to Starve. The Americans Brought Soup.'),
       ('storico_3_1.jpg', (.71, .42), (.42, .45), 'A TRICK?!', 'THEY THOUGHT IT WAS A TRICK', 'A TRICK?', 'German POWs Got Christmas Dinner in America. They Thought It Was a Trick.'),
       ('storico_5_1.jpg', (.62, .41), (.25, .25), 'ONE DAY?!', 'HE NAMED ONE DAY', 'ONE DAY.', 'They Asked Göring When He Knew the War Was Lost. He Named One Day.')]


def base(f, sx, sy, bw=True):
    im = Image.open(C + 'cand/' + f).convert('RGB')
    w, h = im.size
    if w / h > W / H:
        nw = int(h * W / H); x0 = int(min(max(sx * w - nw / 2, 0), w - nw)); im = im.crop((x0, 0, x0 + nw, h))
    else:
        nh = int(w * H / W); y0 = int(min(max(sy * h - nh / 2, 0), h - nh)); im = im.crop((0, y0, w, y0 + nh))
    im = im.resize((W, H), Image.LANCZOS)
    if bw:
        im = ImageOps.grayscale(im).convert('RGB')
    im = ImageEnhance.Contrast(im).enhance(1.25)
    return im


def pos(f, p):   # coordinate del soggetto dopo il ritaglio
    im = Image.open(C + 'cand/' + f); w, h = im.size
    if w / h > W / H:
        nw = h * W / H; x0 = min(max(p[0] * w - nw / 2, 0), w - nw); return ((p[0] * w - x0) / nw * W, p[1] * H)
    nh = w * H / W; y0 = min(max(p[1] * h - nh / 2, 0), h - nh); return (p[0] * W, (p[1] * h - y0) / nh * H)


def testo_bordo(d, xy, t, f, fill, bordo=8):
    d.text(xy, t, font=f, fill=fill, stroke_width=bordo, stroke_fill='black')


def stile_a(c):   # CERCHIO ROSSO (come The World War Archive): foto vera, scritta gialla, cerchio e freccia sul dettaglio
    f, s, s2, ta = c[0], c[1], c[2], c[3]
    im = base(f, *s); d = ImageDraw.Draw(im)
    x, y = pos(f, s); r = 95
    for k in range(10):
        d.ellipse((x - r - k, y - r * .8 - k, x + r + k, y + r * .8 + k), outline=ROSSO)
    fn = ANTON(150); tw = d.textlength(ta, font=fn)
    tx = 40 if x > W / 2 else W - tw - 40
    testo_bordo(d, (tx, 30), ta, fn, GIALLO, 10)
    ax, ay = tx + tw / 2, 230; bx, by = x + (-r if x > ax else r) * .9, y - r * .5
    d.line((ax, ay, bx, by), fill='white', width=16); d.line((ax, ay, bx, by), fill=ROSSO, width=10)
    ang = math.atan2(by - ay, bx - ax)
    pts = [(bx, by), (bx - 45 * math.cos(ang - .5), by - 45 * math.sin(ang - .5)), (bx - 45 * math.cos(ang + .5), by - 45 * math.sin(ang + .5))]
    d.polygon(pts, fill=ROSSO)
    return im


def stile_b(c):   # ETICHETTA ROSSA (come WWII Desk / WWII PUB): bianco e nero sobrio, fascia rossa con la frase
    f, s, tb = c[0], c[1], c[4]
    im = base(f, *s)
    im = Image.composite(im, Image.new('RGB', (W, H), 'black'), Image.linear_gradient('L').rotate(0).resize((W, H)).point(lambda v: 255 - int(v * .55)))
    d = ImageDraw.Draw(im); fn = ANTON(82)
    tw = d.textlength(tb, font=fn); x0 = 60 if pos(f, s)[0] > W / 2 else W - tw - 100
    d.rectangle((x0, H - 190, x0 + tw + 50, H - 70), fill=ROSSO)
    d.text((x0 + 25, H - 183), tb, font=fn, fill='white')
    return im


def stile_c(c):   # FASCICOLO (tratto distintivo nostro): foto seppia, cartellino d'interrogatorio battuto a macchina, timbro rosso
    f, s, tc = c[0], c[1], c[5]
    im = base(f, *s)
    sep = ImageOps.colorize(ImageOps.grayscale(im), (25, 18, 10), (240, 225, 195)); im = sep
    d = ImageDraw.Draw(im)
    sx_ = pos(f, s)[0]; x0 = 50 if sx_ > W / 2 else W - 560
    card = Image.new('RGBA', (510, 250), (236, 226, 200, 255)); cd = ImageDraw.Draw(card)
    for k in range(6):
        cd.line((0, 70 + k * 45, 510, 70 + k * 45), fill=(170, 160, 140), width=1)
    cd.text((22, 14), 'INTERROGATION REPORT  1945', font=TYPE(30), fill=(40, 30, 25))
    sz = 130
    while cd.textlength(tc, font=ANTON(sz)) > 466 and sz > 50:
        sz -= 4
    fn = ANTON(sz); cd.text((22, 80), tc, font=fn, fill=(20, 20, 20))
    st = Image.new('RGBA', (360, 110), (0, 0, 0, 0)); sd = ImageDraw.Draw(st)
    sd.rectangle((4, 4, 356, 106), outline=(200, 20, 20, 230), width=7); sd.text((24, 14), 'CLASSIFIED', font=ANTON(74), fill=(200, 20, 20, 230))
    st = st.rotate(-8, expand=True)
    card = card.rotate(3, expand=True, fillcolor=(0, 0, 0, 0))
    sh = Image.new('RGBA', card.size, (0, 0, 0, 0)); sh.paste((0, 0, 0, 140), mask=card.split()[3]); sh = sh.filter(ImageFilter.GaussianBlur(10))
    im = im.convert('RGBA'); im.alpha_composite(sh, (x0 + 12, 60 + 14)); im.alpha_composite(card, (x0, 60)); im.alpha_composite(st, (x0 + 130, 300))
    return im.convert('RGB')


righe = []
for c in COP:
    righe.append([stile_a(c), stile_b(c), stile_c(c)])
for i, r in enumerate(righe, 1):
    for nome, im in zip('ABC', r):
        im.save(C + f'studio/{nome}_{i}.jpg', quality=90)
# foglio di confronto: riga 0 = loro (WWII Desk, i 4 piu' visti), poi una riga per stile
tw, th = 480, 270
S = Image.new('RGB', (4 * tw + 5 * 10 + 260, 4 * (th + 10) + 10), (18, 18, 18)); d = ImageDraw.Draw(S)
et = ['LORO\nWWII Desk', 'A\nCERCHIO\nROSSO', 'B\nETICHETTA\nROSSA', 'C\nFASCICOLO']
for rr in range(4):
    d.multiline_text((15, 10 + rr * (th + 10) + 70), et[rr], font=ANTON(40), fill=GIALLO if rr else 'white')
    for k in range(4):
        im = Image.open(C + f'loro_{k + 1}.jpg') if rr == 0 else righe[k][rr - 1]
        S.paste(im.resize((tw, th)), (260 + 10 + k * (tw + 10), 10 + rr * (th + 10)))
S.save(C + 'studio/confronto.jpg', quality=85)
# come da telefono: piccole
T = S.resize((S.width // 3, S.height // 3), Image.LANCZOS); T.save(C + 'studio/telefono.jpg', quality=85)
print('ok')
