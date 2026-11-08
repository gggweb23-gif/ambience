#!/usr/bin/env python3
"""8 nov (Giorgio): rifa' SOLO la copertina di un video d'archivio (Orbital Days, WWII Testimony) gia' fatto, con lo stesso codice
di strumenti/video_archivio.py (ritocco AI ~0,04 $ + scritta nello stile del canale), con l'impaginazione scelta (copertina_variante 0/1/2).
Ingresso (env): PAYLOAD = {"copertina_stile", "copertina_soggetto", "copertina_variante", "testo_copertina", "titolo"} ; VIDEO = file mp4
Uscita: copertina in prove_video/archivio_copertine/<NOME>.jpg"""
import base64, io, json, os, re, subprocess, sys, time, urllib.request
from PIL import Image, ImageDraw, ImageFont

SRC = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'video_archivio.py'), encoding='utf-8').read()
P = json.loads(os.environ.get('PAYLOAD') or '{}')
E = lambda k, d='': os.environ.get(k, d)
log = lambda *a: print(time.strftime('%H:%M:%S'), *a, flush=True)
NOME = re.sub(r'\W+', '_', P.get('nome') or 'copertina')
CART = os.path.join('prove_video', 'archivio_copertine'); os.makedirs(CART, exist_ok=True)
LAV = '/tmp/va'; os.makedirs(LAV, exist_ok=True)
VIDEO = E('VIDEO')
BUDGET_USD = 0.15
SPESA = {'usd': 0.0, 'voci': []}
g = dict(globals())


def blocco(inizio, fine):
    i = SRC.index(inizio); j = SRC.index(fine, i)
    return SRC[i:j]


for nome in ('get', 'spendi', 'json_sicuro', 'claude'):
    exec(blocco('def ' + nome + '(', '\n\n\n'), g)
# il soggetto della scena: lo scrive Claude dal titolo (come fa il copione del video)
sogg = P.get('copertina_soggetto') or 'a FICTIONAL astronaut'
t = g['claude'](f'YouTube video title: "{P.get("titolo", "")}". Write ONE sentence in English: the scene of the thumbnail, {sogg} in close-up with a strong readable emotion '
                'that matches the title. Only the sentence.', modello='claude-haiku-4-5-20251001', max_tokens=200)
c = {'copertina_prompt': t.strip(), 'testo_copertina': P.get('testo_copertina', '')}
log('scena:', c['copertina_prompt'])
g.update(P=P, c=c, VIDEO=VIDEO, LAV=LAV, CART=CART, SPESA=SPESA, BUDGET_USD=BUDGET_USD, log=log, E=E)
codice = blocco('# ---------------- 5) copertina stile C', "COP = os.path.join(CART, 'copertina.jpg'); im.save(COP, quality=92)")
codice = codice.replace("open(FP, 'wb').write(get('https://github.com/google/fonts/raw/main/ofl/anton/Anton-Regular.ttf', raw=True))",
                        "None if os.path.exists(FP) else open(FP, 'wb').write(get('https://cdn.jsdelivr.net/gh/google/fonts@main/ofl/anton/Anton-Regular.ttf', raw=True))")
codice = codice.replace("    from PIL import ImageOps as _IO, ImageEnhance as _IE\n",
                        "    im.save(os.path.join(CART, NOME + '_base.jpg'), quality=92)   # base senza scritte: si riscrive gratis\n    from PIL import ImageOps as _IO, ImageEnhance as _IE\n", 1)
exec(codice, g)
out = os.path.join(CART, NOME + '.jpg'); g['im'].save(out, quality=92)
log('copertina pronta:', out, '| spesa', round(SPESA['usd'], 3), '$')
