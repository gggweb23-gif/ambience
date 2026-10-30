#!/usr/bin/env python3
"""Elenco GRATUITO delle voci ElevenLabs adatte a un canale (libreria condivisa): nome, ID, descrizione e anteprima mp3 (gia' pronta, non costa).
PAYLOAD = {"lingua": "it", "uso": "narrative_story", "quante": 12, "cartella": "prove_video/voci_it"}"""
import json, os, re, urllib.parse, urllib.request
P = json.loads(os.environ.get('PAYLOAD') or '{}')
K = os.environ['ELEVENLABS_API_KEY']
cart = P.get('cartella') or f"prove_video/voci_{P.get('lingua', 'it')}"; os.makedirs(cart, exist_ok=True)


def get(url):
    return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers={'xi-api-key': K}), timeout=60).read())


if P.get('solo_abbonamento'):   # controllo crediti: quanti caratteri restano nel mese
    try:
        a = get('https://api.elevenlabs.io/v1/user/subscription')
        t = (f"piano {a.get('tier')} | caratteri usati {a.get('character_count')} su {a.get('character_limit')} | "
             f"rinnovo {a.get('next_character_count_reset_unix')} | stato {a.get('status')}")
    except Exception as e:
        t = 'controllo non riuscito: ' + str(e)[:300]
    print(t); open(os.path.join(cart, 'abbonamento.txt'), 'w').write(t + '\n'); raise SystemExit
righe, visti = [], set()
# filtri facoltativi: "genere" (male/female), "eta" (young/middle_aged/old), "cerca" (lista di parole, es. ["deep", "wise old"])
ricerche = []
for uso in [P.get('uso') or 'narrative_story', 'informative_educational']:
    for parola in (P.get('cerca') or ['']):
        f_ = {'page_size': 50, 'language': P.get('lingua', 'it'), 'use_cases': uso, 'sort': P.get('ordine') or 'trending'}
        if P.get('genere'): f_['gender'] = P['genere']
        if P.get('eta'): f_['age'] = P['eta']
        if parola: f_['search'] = parola
        ricerche.append(f_)
for f_ in ricerche:
    q = urllib.parse.urlencode(f_)
    try:
        trovate = get('https://api.elevenlabs.io/v1/shared-voices?' + q).get('voices', [])
    except Exception as e:
        print('ricerca non riuscita', f_, str(e)[:120]); continue
    for v in trovate:
        if v['voice_id'] in visti:
            continue
        visti.add(v['voice_id']); righe.append(v)
if P.get('ordina_per_uso'):   # prima le voci piu' usate dagli altri creator (di solito le migliori)
    righe.sort(key=lambda v: -(v.get('cloned_by_count') or 0))
righe = righe[:int(P.get('quante') or 12)]
out = []
for i, v in enumerate(righe, 1):
    nome = re.sub(r'\W+', '_', v.get('name', 'voce'))[:30]
    f = os.path.join(cart, f'{i:02d}_{nome}.mp3')
    try:
        if v.get('preview_url'):
            open(f, 'wb').write(urllib.request.urlopen(v['preview_url'], timeout=60).read())
    except Exception as e:
        f = 'anteprima non scaricata: ' + str(e)[:80]
    out.append(f"{i:02d} | {v.get('name')} | voice_id={v['voice_id']} | {v.get('gender')} {v.get('age')} {v.get('accent')} | "
               f"uso={v.get('use_case')} | usata da {v.get('cloned_by_count')} | {str(v.get('description') or '')[:160]} | {f}")
open(os.path.join(cart, 'elenco.txt'), 'w').write('\n'.join(out) + '\n')
print('\n'.join(out))
