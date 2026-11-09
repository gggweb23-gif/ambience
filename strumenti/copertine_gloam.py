#!/usr/bin/env python3
"""3 STILI DI COPERTINA per il canale stile Gloam (9 nov, Giorgio: "proponi 3 stili di copertine diverse partendo dal video originale").
Originale Gloam (Binance, 2,4 mln views): figure 3D lucide senza volto, ROSSO = chi crea il problema, BLU = chi lo subisce, oggetto d'oro con il nome
dell'azienda, etichette a fumetto con la parola-ruolo, fondo scuro. Esempio sul video Barings Bank.
A = fedele all'originale (3D, ruoli, cassaforte d'oro); B = dossier (foto vera + numero enorme + timbro); C = prima/dopo (3D diviso in due con freccia).
Immagini: FLUX.2 Klein 4B (circa 0,01 $ l'una). Scritte disegnate in codice (sempre leggibili da telefono). Uscita: prove_video/Copertine_Gloam/."""
import io, json, os, sys, time, urllib.parse
from PIL import Image, ImageDraw, ImageFilter, ImageFont
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prova_gloam3 as G3
import prova_gloam4 as G4

E = os.environ.get
OUT = 'prove_video/Copertine_Gloam'; os.makedirs(OUT, exist_ok=True)
W, H = 1280, 720
MB = 'fonts_gloam/montserrat_black.woff'
F = lambda s: ImageFont.truetype(MB, s)
STILE = ('Glossy stylized 3D render, premium YouTube finance documentary thumbnail: smooth faceless mannequin figures with glossy plastic material, '
         'dark charcoal background with soft spotlight and floating gold particles, cinematic lighting, simple bold composition, '
         'absolutely no text, no letters, no numbers, no logos. ')


def klein(prompt):
    hd = {'Authorization': 'Key ' + E('FAL_KEY', '')}
    inv = G3.http('https://queue.fal.run/fal-ai/flux-2/klein/4b', {'prompt': prompt, 'image_size': {'width': 1280, 'height': 720}, 'num_images': 1, 'output_format': 'jpeg'}, hd)
    for _ in range(100):
        time.sleep(2)
        if G3.http(inv['status_url'], headers=hd).get('status') == 'COMPLETED':
            break
    u = G3.http(inv['response_url'], headers=hd)['images'][0]['url']
    return Image.open(io.BytesIO(G3.http(u, raw=True))).convert('RGB').resize((W, H))


def etichetta(im, x, y, testo, col, size=64, punta=True):
    """Etichetta a fumetto come Gloam: rettangolo pieno, scritta bianca, punta verso il soggetto."""
    d = ImageDraw.Draw(im); f = F(size); w = f.getlength(testo); h = size * 1.05
    d.rectangle((x, y, x + w + 44, y + h + 26), fill=col)
    if punta:
        cx = x + (w + 44) / 2; d.polygon([(cx - 16, y + h + 26), (cx + 16, y + h + 26), (cx, y + h + 46)], fill=col)
    d.text((x + 22, y + 10), testo, font=f, fill='white')


def scritta_oro(im, cx, cy, testo, size):
    d = ImageDraw.Draw(im); f = F(size)
    d.text((cx, cy), testo, font=f, fill=(40, 30, 10), anchor='mm', stroke_width=0)


def main():
    rosso, blu = (220, 30, 40), (30, 90, 230)
    # A) fedele all'originale
    a = klein(STILE + 'On the left a glossy RED mannequin trader sitting at a small desk with a laptop, frantically trading; in the middle a glossy BLUE mannequin '
              'manager standing with arms crossed, unaware; on the right a huge glossy GOLD bank vault with an old classic door, gold coins and banknotes flying out '
              'of the vault toward the red trader. Three subjects well separated, empty space above each one.')
    etichetta(a, 40, 90, 'ROGUE TRADER', rosso); etichetta(a, 470, 70, 'THE BANK', blu)
    d = ImageDraw.Draw(a); d.rectangle((880, 330, 1215, 400), fill=(245, 200, 60)); d.text((1047, 365), 'BARINGS', font=F(52), fill=(40, 30, 10), anchor='mm')
    a.save(os.path.join(OUT, 'A_ruoli_3D.jpg'), quality=92)
    # B) dossier: foto vera + numero enorme + timbro (lo stile dei video)
    b = G4.foto_pexels('london financial district', 0).convert('RGB')
    from PIL import ImageOps
    b = ImageOps.fit(b, (W, H)).filter(ImageFilter.GaussianBlur(2)); b = Image.blend(b, Image.new('RGB', (W, H), (10, 10, 12)), .45).convert('RGBA')
    d = ImageDraw.Draw(b); d.text((70, 150), '£827M', font=ImageFont.truetype(G4.SERIF, 260), fill=(245, 240, 228))
    d.rectangle((80, 450, 900, 462), fill=(190, 30, 30))
    G4.ombra_incolla(b, G4.timbro('ONE TRADER').resize((520, 170)), 960, 560, ang=0)
    b.convert('RGB').save(os.path.join(OUT, 'B_dossier.jpg'), quality=92)
    # C) prima / dopo diviso in due
    c = klein(STILE + 'Split composition: LEFT half bright warm golden light, a proud glossy gold classic bank building with columns standing tall; RIGHT half dark red light, '
              'the same bank building cracked and collapsing into rubble, falling gold coins, a glossy RED mannequin trader walking away. Strong contrast between the two halves.')
    d = ImageDraw.Draw(c)
    etichetta(c, 60, 60, '233 YEARS', (40, 140, 70), 60, punta=False); etichetta(c, 760, 60, 'ONE MAN', rosso, 60, punta=False)
    d.polygon([(560, 330), (700, 330), (700, 290), (780, 360), (700, 430), (700, 390), (560, 390)], fill='white')
    c.save(os.path.join(OUT, 'C_prima_dopo.jpg'), quality=92)
    g = Image.new('RGB', (W, H * 3 + 40), 'white')
    for k, im in enumerate([a, b.convert('RGB'), c]):
        g.paste(im, (0, k * (H + 20)))
    g.resize((W // 2, (H * 3 + 40) // 2)).save(os.path.join(OUT, 'tre_stili.jpg'), quality=90)
    print('FATTO')


if __name__ == '__main__':
    main()
