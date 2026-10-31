#!/usr/bin/env python3
"""LIBRERIA CHE CRESCE OGNI GIORNO (per tutti i canali con archivi video gratuiti).
Legge Channel Configs: per ogni canale con le colonne
  libreria               nome della libreria (es. nasa_spazio)
  libreria_budget_giorno dollari massimi al giorno per etichettare spezzoni nuovi (la compila e la blocca Giorgio; vuota = libreria ferma)
  libreria_ricerche      ricerche nell'archivio separate da ; (es. astronaut eating;astronaut sleeping) — vuota = ricerche di base
lancia strumenti/libreria_clip.py che AGGIUNGE spezzoni nuovi all'indice (mai oltre 0,50 $ a giro)."""
import json, os, re, subprocess, sys, urllib.parse, urllib.request
CONFIGS = os.environ.get('FOGLIO_CONFIGS', '1COMpgHJshcmz_a9s-WsjCO5xbhwxBazt-ZB0G_C7Rb0')


def token():
    from google.oauth2 import service_account
    from google.auth.transport.requests import Request
    cr = service_account.Credentials.from_service_account_info(json.loads(os.environ['GOOGLE_SA_KEY']), scopes=['https://www.googleapis.com/auth/spreadsheets.readonly'])
    cr.refresh(Request()); return cr.token


def api(tk, percorso):
    req = urllib.request.Request('https://sheets.googleapis.com/v4/spreadsheets/' + CONFIGS + percorso, headers={'Authorization': 'Bearer ' + tk})
    return json.loads(urllib.request.urlopen(req, timeout=60).read())


def num(v):
    try:
        return float(str(v).replace('$', '').replace('€', '').replace(',', '.').strip())
    except Exception:
        return 0.0


tk = token()
scheda = api(tk, '?fields=sheets.properties')['sheets'][0]['properties']['title']
v = api(tk, '/values/' + urllib.parse.quote(f"'{scheda}'!A1:AZZ200")).get('values', [])
h = [str(x).strip() for x in v[0]]
fatte = set()
for r in v[1:]:
    c = dict(zip(h, r + [''] * (len(h) - len(r))))
    nome, budget = str(c.get('libreria') or '').strip(), num(c.get('libreria_budget_giorno'))
    if not nome or budget <= 0 or nome in fatte:
        continue
    fatte.add(nome)
    ricerche = [q.strip() for q in str(c.get('libreria_ricerche') or '').split(';') if q.strip()]
    payload = {'nome': re.sub(r'[^a-z0-9_]', '', nome.lower()), 'max_spezzoni': int(budget / 0.0007), 'max_spesa': min(budget, 0.50)}
    if ricerche:
        payload['ricerche'] = ricerche
    print(f"libreria {payload['nome']} per {c.get('channel_id')}: budget {payload['max_spesa']:.2f} $, {len(ricerche)} ricerche", flush=True)
    subprocess.run([sys.executable, 'strumenti/libreria_clip.py'], env=dict(os.environ, PAYLOAD=json.dumps(payload)), check=False)
if not fatte:
    print('nessun canale con libreria e libreria_budget_giorno compilati: niente da fare')
