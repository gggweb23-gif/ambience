#!/usr/bin/env python3
"""Varianti di copertina da proporre a Giorgio (qualsiasi canale): PAYLOAD {"out": "cartella", "varianti": [{"nome", "prompt", "righe": [...],
"lato": "sx"|"dx" (dove va la scritta), "cerchio": "cosa cerchiare" (facoltativo)}]}.
Foto: FLUX.2 Klein ~0,02 $ l'una. Scritta Anton bianca, ultima riga azzurra, bordo nero spesso (stile Orbital Days), mai in basso a destra."""
import io, json, os, sys, time
from PIL import Image, ImageDraw, ImageFont
QUI = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, QUI); sys.path.insert(0, os.path.dirname(QUI))
import motore_yt as YT
import costi as CO
import copertina_possesso_foto as PF

E = os.environ.get
W, H = 1280, 720
FA = os.path.join(os.path.dirname(QUI), 'ctr_test', 'Anton.ttf')


def foto(prompt):
    hd = {'Authorization': 'Key ' + E('FAL_KEY', '')}
    for _ in range(3):
        try:
            inv = YT.http('https://queue.fal.run/fal-ai/flux-2/klein/4b', {'prompt': prompt, 'image_size': {'width': 1920, 'height': 1080}, 'num_images': 1, 'output_format': 'png'}, hd, timeout=120)
            for _ in range(150):
                time.sleep(2)
                if YT.http(inv['status_url'], headers=hd, timeout=60).get('status') == 'COMPLETED':
                    break
            u = YT.http(inv['response_url'], headers=hd, timeout=60)['images'][0]['url']
            CO.registra('fal', 'flux-2-klein-4b', dollari=0.02, nota='varianti copertina')
            return Image.open(io.BytesIO(YT.http(u, raw=True, timeout=120))).convert('RGB').resize((W, H), Image.LANCZOS)
        except Exception as e:
            print('foto non riuscita, riprovo:', str(e)[:120], flush=True); time.sleep(4)
    raise RuntimeError('foto non riuscita')


def scritta(im, righe, lato):
    d = ImageDraw.Draw(im)
    righe = [r.upper() for r in righe]
    size = 200
    while size > 60:
        f = ImageFont.truetype(FA, size)
        if max(f.getlength(r) for r in righe) <= 560 and len(righe) * size * 1.02 <= 560:
            break
        size -= 6
    f = ImageFont.truetype(FA, size); tot = len(righe) * int(size * 1.02)
    y = max(40, (620 - tot) // 2)
    for i, r in enumerate(righe):
        x = 34 if lato == 'sx' else W - 34 - f.getlength(r)
        d.text((x, y), r, font=f, fill='#4FD2FF' if i == len(righe) - 1 and len(righe) > 1 else 'white', stroke_width=max(8, size // 11), stroke_fill=(0, 0, 0))
        y += int(size * 1.02)
    return im


def main():
    P = json.loads(E('PAYLOAD') or '{}'); out = P.get('out') or 'prove_video/copertine_varianti'; os.makedirs(out, exist_ok=True)
    for v in P.get('varianti', []):
        f_base = os.path.join(out, v['nome'] + '_base.jpg')
        base = Image.open(f_base).convert('RGB') if os.path.exists(f_base) else foto(v['prompt'])
        base.save(f_base, quality=95)
        im = base.copy()
        if v.get('cerchio'):
            b = PF.box_soggetto(im, v['cerchio'])
            if b:
                PF.cerchio(ImageDraw.Draw(im), b, seme=5)
        scritta(im, v['righe'], v.get('lato') or 'sx').save(os.path.join(out, v['nome'] + '.jpg'), quality=94)
        print('FATTO', v['nome'], flush=True)


if __name__ == '__main__':
    main()
