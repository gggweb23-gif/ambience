#!/usr/bin/env python3
"""Pagina HTML della copertina -> immagine PNG con Chromium (fa quello che faceva il servizio hcti.io per n8n).
Uso: python3 html_png.py pagina.html uscita.png larghezza altezza attesa_ms selettore"""
import sys
from playwright.sync_api import sync_playwright

pagina, uscita = sys.argv[1], sys.argv[2]
w, h, attesa = int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
sel = sys.argv[6] if len(sys.argv) > 6 else '.container'
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={'width': w, 'height': h}, device_scale_factor=1)
    pg.set_content(open(pagina, encoding='utf-8').read(), wait_until='networkidle', timeout=120000)
    pg.wait_for_timeout(attesa)
    el = pg.query_selector(sel)
    (el or pg).screenshot(path=uscita)
    b.close()
print('copertina:', uscita)
