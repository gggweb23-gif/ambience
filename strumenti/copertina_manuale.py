#!/usr/bin/env python3
"""Copertine A3a fatte a mano (per i video dove il controllo automatico non ha trovato la foto). Non carica niente.
PAYLOAD = {"cartella": "...", "copertine": [{"file": "id.jpg", "nome": "ISRAELE", "anni": "37 a.C. → 2026", "simboli": [...], "folla_ok": true}
           | {"file": "...", "nome": "AFGHANISTAN", "anni": "...", "sagoma": "AFG", "riempi": "Hindu Kush mountains"}]}"""
import io, json, os, sys, urllib.request
import numpy as np
sys.path.insert(0, os.getcwd())
import copertina_foto as CF
from PIL import Image, ImageDraw, ImageFilter, ImageOps
P = json.loads(os.environ.get('PAYLOAD') or '{}')
CART = P.get('cartella') or 'prove_video/copertine_manuali'; os.makedirs(CART, exist_ok=True)


def sagoma_foto(iso, query):
    """Fondo blu notte con la sagoma del paese riempita con una foto (montagne, deserto...) e il bordo giallo luminoso."""
    g = json.load(open('risorse_mappe/paesi50.geojson'))['features']
    anelli = []
    for f in g:
        p = f['properties']
        if iso in {str(p.get('ADM0_A3')), str(p.get('ISO_A3'))}:
            gm = f['geometry']; polys = gm['coordinates'] if gm['type'] == 'MultiPolygon' else [gm['coordinates']]
            anelli = sorted([np.array(pp[0]) for pp in polys], key=len, reverse=True)
    w, h = 1300, 720
    tutti = np.concatenate(anelli[:4]); lo0, lo1, la0, la1 = tutti[:, 0].min(), tutti[:, 0].max(), tutti[:, 1].min(), tutti[:, 1].max()
    sc = min(w * .78 / (lo1 - lo0), h * .82 / (la1 - la0)); ox = (w - (lo1 - lo0) * sc) / 2; oy = (h - (la1 - la0) * sc) / 2
    pt = lambda lo, la: (ox + (lo - lo0) * sc, oy + (la1 - la) * sc)
    m = Image.new('L', (w, h), 0); dm = ImageDraw.Draw(m)
    for r in anelli[:4]:
        dm.polygon([pt(*q) for q in r], fill=255)
    foto = CF._pexels(query)[0]
    im_f = Image.open(io.BytesIO(urllib.request.urlopen(urllib.request.Request(foto['src']['large2x'], headers={'User-Agent': 'Mozilla/5.0'}), timeout=60).read())).convert('RGB')
    base = Image.new('RGB', (w, h), (10, 24, 52))
    alone = m.filter(ImageFilter.MaxFilter(17)).filter(ImageFilter.GaussianBlur(14))
    base.paste(Image.new('RGB', (w, h), CF.GIALLO), (0, 0), alone.point(lambda x: int(x * .8)))
    base.paste(Image.new('RGB', (w, h), CF.BIANCO), (0, 0), m.filter(ImageFilter.MaxFilter(7)))
    base.paste(ImageOps.fit(im_f, (w, h)), (0, 0), m)
    return base, [.1, .1, .9, .9]


for c in P.get('copertine') or []:
    try:
        if c.get('sagoma'):
            foto, box = sagoma_foto(c['sagoma'], c.get('riempi') or 'mountains')
        else:
            foto, box = CF.foto_simbolo(c['nome'], c['simboli'], pulita=not c.get('folla_ok'))
        if foto is None:
            print('nessuna foto per', c['nome']); continue
        CF.disegna(c['nome'], c['anni'], foto, box, os.path.join(CART, c['file']))
        print('fatta', c['file'])
    except Exception as e:
        print('errore', c.get('nome'), str(e)[:200])
open(os.path.join(CART, 'controlli.txt'), 'w').write('\n'.join(CF.REGISTRO) + '\n')
