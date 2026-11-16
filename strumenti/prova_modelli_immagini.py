#!/usr/bin/env python3
"""PROVA MODELLI IMMAGINI (16 nov 2026, Giorgio: "la qualita' puo' solo migliorare"). Stesse 3 scene della prova guerra di oggi,
disegnate con modelli piu' economici di Seedream 4.5 (0,04 $), affiancate all'originale per decidere guardando.
Env: NOTIZIA (json della prova), FAL_KEY. Uscita: prove_video/prova_modelli/<scena>.jpg (~0,25 $)."""
import io, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import video_notizie as V
from PIL import Image, ImageDraw

MODELLI = [('Seedream 5 Flash 0,027 $', 'bytedance/seedream/v5/flash/text-to-image', {'image_size': {'width': 3840, 'height': 2160}}, .027),
           ('Seedream 5 Lite 0,035 $', 'bytedance/seedream/v5/lite/text-to-image', {'image_size': {'width': 3840, 'height': 2160}}, .035),
           ('Z-Image Turbo 2560 0,018 $', 'fal-ai/z-image/turbo', {'image_size': {'width': 2560, 'height': 1440}}, .019)]
OUT = os.path.join(V.ROOT, 'prove_video', 'prova_modelli'); os.makedirs(OUT, exist_ok=True)
V.TETTO = 0.6
for k in ['cremlino', 'ponte_notte', 'ufficio_zelensky']:
    descr = V.descr_sfondo(k)
    prompt = V.STILE + f'Scene: {descr}. Wide 16:9 cinematic establishing shot, rich detail everywhere so that close crops still look good. ' + V.NO_TESTO
    orig = os.path.join(OUT, 'originali', f'{k}.jpg')
    righe = [('Seedream 4.5 (oggi) 0,04 $', Image.open(orig).convert('RGB') if os.path.exists(orig) else Image.new('RGB', (3840, 2160)))]
    for nome, ep, dim, costo in MODELLI:
        try:
            r = V.fal(ep, dict({'prompt': prompt, 'num_images': 1}, **dim), costo)
            im = Image.open(io.BytesIO(V.http(r['images'][0]['url'], raw=True, timeout=180))).convert('RGB')
            V.log(k, nome, im.size); righe.append((nome + f' {im.width}x{im.height}', im))
        except Exception as e:
            V.log('non riuscito', nome, str(e)[:200])
    # confronto: intera (in piccolo) + dettaglio al 100% (per vedere la nitidezza dei tagli ravvicinati)
    t = Image.new('RGB', (2 * 1280, len(righe) * 720), (20, 20, 20)); d = ImageDraw.Draw(t)
    for i, (nome, im) in enumerate(righe):
        t.paste(im.resize((1280, 720), Image.LANCZOS), (0, i * 720))
        cw = im.width // 3; ch = cw * 9 // 16
        t.paste(im.crop((im.width // 2 - cw // 2, im.height // 2 - ch // 2, im.width // 2 + cw // 2, im.height // 2 + ch // 2)).resize((1280, 720), Image.LANCZOS), (1280, i * 720))
        d.rectangle((0, i * 720, 900, i * 720 + 60), fill=(0, 0, 0)); d.text((14, i * 720 + 10), nome, fill=(255, 220, 0), font=V.font(V.F_TESTI, 36))
    t.save(os.path.join(OUT, f'{k}.jpg'), quality=88)
V.log(f'spesa prova {V.CO.totale():.3f} $')
