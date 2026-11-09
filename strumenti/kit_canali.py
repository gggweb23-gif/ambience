#!/usr/bin/env python3
"""KIT DI APERTURA dei 2 nuovi canali (9 nov, Giorgio): avatar 800x800 e banner 2560x1440 (zona sicura centrale 1546x423, visibile su telefono).
COSTO VERO (italiano, stile copertina 3 "scontrino") e il canale stile Gloam in inglese (nome scelto BILLION RUIN, si rigenera col nome scelto: NOME_EN).
Sfondi dei banner con FLUX.2 Klein 4B (circa 0,01 $ l'uno); loghi e scritte in codice. Uscita: prove_video/Kit_Canali/"""
import io, os, sys, time
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prova_gloam3 as G3

E = os.environ.get
OUT = 'prove_video/Kit_Canali'; os.makedirs(OUT, exist_ok=True)
MB = 'fonts_gloam/montserrat_black.woff'; SERIF = 'fonts_gloam/serif.woff'; MONO = 'fonts_gloam/mono.woff'
F = lambda f, s: ImageFont.truetype(f, s)
NOME_EN = (E('NOME_EN') or 'Billion Ruin').upper()
ROSSO, GIALLO, ARANCIO, BIANCO, NERO, ORO = (225, 35, 45), (255, 210, 40), (255, 140, 40), (255, 255, 255), (20, 20, 25), (232, 182, 60)


def klein(p, w, h):
    hd = {'Authorization': 'Key ' + E('FAL_KEY', '')}
    inv = G3.http('https://queue.fal.run/fal-ai/flux-2/klein/4b', {'prompt': p, 'image_size': {'width': w, 'height': h}, 'num_images': 1, 'output_format': 'jpeg'}, hd)
    for _ in range(100):
        time.sleep(2)
        if G3.http(inv['status_url'], headers=hd).get('status') == 'COMPLETED':
            break
    u = G3.http(inv['response_url'], headers=hd)['images'][0]['url']
    return Image.open(io.BytesIO(G3.http(u, raw=True))).convert('RGB')


def scontrino(w, h):
    s = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(s)
    d.rectangle((0, 18, w, h), fill=(252, 250, 242, 255))
    for i in range(0, w, 36):
        d.polygon([(i, 18), (i + 18, 0), (i + 36, 18)], fill=(252, 250, 242, 255))
    return s


def avatar_costo_vero():
    im = Image.new('RGB', (800, 800), ARANCIO); d = ImageDraw.Draw(im)
    for r in range(560, 0, -8):   # sfumatura calda al centro
        c = int(40 * (1 - r / 560)); d.ellipse((400 - r, 400 - r, 400 + r, 400 + r), fill=(255, 140 + c, 40 + c // 2))
    sc = scontrino(400, 560); sd = ImageDraw.Draw(sc)
    for j in range(3):
        sd.rectangle((50, 80 + j * 60, 50 + 200 - j * 40, 100 + j * 60), fill=(170, 170, 170, 255))
    sd.text((200, 400), '€', font=F(MB, 260), fill=ROSSO, anchor='mm')
    sc = sc.rotate(-8, expand=True, resample=Image.BICUBIC)
    im.paste(sc, ((800 - sc.width) // 2, (800 - sc.height) // 2 + 10), sc)
    im.save(os.path.join(OUT, 'costo_vero_avatar.png'))


def banner_costo_vero():
    bg = klein('DIGITAL PAINTED ILLUSTRATION, warm bright orange and yellow palette, a row of everyday things people own seen from afar: a family SUV, a small house, '
               'a golden retriever, a motorbike, a smartphone, a small boat, arranged along a wide panoramic horizon, lots of empty calm space in the CENTER, '
               'no text, no letters, no numbers, no logos.', 1920, 1088)
    im = bg.resize((2560, 1440), Image.LANCZOS).convert('RGBA')
    vel = Image.new('RGBA', (2560, 1440), (0, 0, 0, 0)); ImageDraw.Draw(vel).rectangle((507, 508, 2053, 931), fill=(255, 150, 40, 215)); im.alpha_composite(vel)
    d = ImageDraw.Draw(im)
    d.text((1280, 640), 'COSTO VERO', font=F(MB, 170), fill=BIANCO, anchor='mm', stroke_width=12, stroke_fill=NERO)
    d.text((1280, 800), 'QUANTO COSTA DAVVERO POSSEDERE LE COSE?', font=F(MB, 58), fill=NERO, anchor='mm')
    d.text((1280, 880), 'AUTO · CASA · CANE · BARCA · NUOVO VIDEO OGNI GIORNO', font=F(MB, 36), fill=BIANCO, anchor='mm')
    im.convert('RGB').save(os.path.join(OUT, 'costo_vero_banner.jpg'), quality=92)


def avatar_en():
    im = Image.new('RGB', (800, 800), (16, 16, 18)); d = ImageDraw.Draw(im)
    d.ellipse((90, 90, 710, 710), outline=ORO, width=22)
    ini = ''.join(p[0] for p in NOME_EN.split()[:2])
    d.text((400, 400), ini, font=F(SERIF, 330), fill=(245, 238, 222), anchor='mm')
    d.line((170, 560, 640, 250), fill=ROSSO, width=26)   # la "crepa" rossa del crollo
    im.save(os.path.join(OUT, 'en_avatar.png'))


def banner_en():
    bg = klein('Glossy stylized 3D render, premium finance documentary: a dark charcoal space with floating gold coins and particles, on the far LEFT a cracked golden bank vault '
               'with coins spilling out, on the far RIGHT a glossy red faceless mannequin walking away with a sack of gold, the CENTER is calm dark empty space, cinematic rim light, '
               'no text, no letters, no numbers, no logos.', 1920, 1088)
    im = bg.resize((2560, 1440), Image.LANCZOS).convert('RGBA'); d = ImageDraw.Draw(im)
    d.text((1280, 650), NOME_EN, font=F(SERIF, 190), fill=(245, 238, 222), anchor='mm')
    w = F(SERIF, 190).getlength(NOME_EN); d.rectangle((1280 - w / 2, 760, 1280 + w / 2, 772), fill=ROSSO)
    t = 'HOW BILLIONS DISAPPEAR · ONE COLLAPSE AT A TIME'
    d.text((1280, 840), t, font=F(MONO, 44), fill=(220, 214, 200), anchor='mm')
    im.convert('RGB').save(os.path.join(OUT, 'en_banner.jpg'), quality=92)


def main():
    avatar_costo_vero(); banner_costo_vero(); avatar_en(); banner_en()
    print('FATTO')


if __name__ == '__main__':
    main()
