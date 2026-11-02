#!/usr/bin/env python3
"""PROVA MODELLI VOCE (2 nov 2026): stessa frase (~1 minuto), stessa voce del canale, modelli ElevenLabs diversi, per decidere a orecchio
se un modello piu' economico basta. Per ogni canale attivo (videos_per_day >= 1) con voice_id in Channel Configs.
Crediti consumati misurati davvero (abbonamento prima/dopo ogni audio). Risultato in prove_video/prova_modelli_voce/."""
import json, os, re, sys, urllib.request
P = json.loads(os.environ.get('PAYLOAD') or '{}')
MODELLI = P.get('modelli') or ['eleven_multilingual_v2', 'eleven_turbo_v2_5', 'eleven_flash_v2_5']
CART = 'prove_video/prova_modelli_voce'; os.makedirs(CART, exist_ok=True)
K = os.environ['ELEVENLABS_API_KEY']
TESTI = {
    'it': ("Nel 1929 nessuno immaginava che quel deserto silenzioso sarebbe diventato il luogo piu' luminoso della Terra. "
           "Eppure, in pochi anni, tutto cambio'. Una diga gigantesca, migliaia di operai, e una decisione che nessuno aveva previsto. "
           "Ma la vera domanda e' un'altra: perche' proprio li'? Perche' in mezzo al nulla, dove l'acqua mancava e il caldo uccideva in poche ore? "
           "La risposta e' piu' sorprendente di quanto pensi. E comincia con un errore. Un errore che, per una volta, ha cambiato la storia in meglio. "
           "Oggi ti racconto come e' andata davvero, passo dopo passo, senza miti e senza leggende."),
    'en': ("In 1929, nobody imagined that this silent desert would become the brightest place on Earth. "
           "And yet, within a few years, everything changed. A gigantic dam, thousands of workers, and a decision nobody saw coming. "
           "But the real question is a different one: why there? Why in the middle of nowhere, where water was scarce and the heat could kill you in hours? "
           "The answer is more surprising than you think. And it begins with a mistake. A mistake that, for once, changed history for the better. "
           "Today I'll tell you how it really happened, step by step, with no myths and no legends."),
}


INTEST = {}


def el(percorso, dati=None):
    req = urllib.request.Request('https://api.elevenlabs.io' + percorso, data=json.dumps(dati).encode() if dati else None,
                                 headers={'xi-api-key': K, 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=180) as r:
        INTEST.clear(); INTEST.update({k.lower(): v for k, v in r.headers.items()})
        return r.read()


def usati():
    return json.loads(el('/v1/user/subscription')).get('character_count') or 0


CONFIGS = os.environ.get('FOGLIO_CONFIGS', '1COMpgHJshcmz_a9s-WsjCO5xbhwxBazt-ZB0G_C7Rb0')


def num(x):
    try:
        return float(str(x).replace(',', '.'))
    except Exception:
        return 0.0


def leggi_configs():   # sola lettura di Channel Configs
    from google.oauth2 import service_account
    from google.auth.transport.requests import Request
    import urllib.parse
    cr = service_account.Credentials.from_service_account_info(json.loads(os.environ['GOOGLE_SA_KEY']), scopes=['https://www.googleapis.com/auth/spreadsheets.readonly'])
    cr.refresh(Request()); H = {'Authorization': 'Bearer ' + cr.token}
    g = lambda u: json.loads(urllib.request.urlopen(urllib.request.Request('https://sheets.googleapis.com/v4/spreadsheets/' + CONFIGS + u, headers=H), timeout=60).read())
    sch = g('?fields=sheets.properties')['sheets'][0]['properties']['title']
    v = g('/values/' + urllib.parse.quote(f"'{sch}'!A1:AZZ200")).get('values', [])
    h = [str(x).strip() for x in v[0]]
    return [dict(zip(h, r + [''] * (len(h) - len(r)))) for r in v[1:]]


canali = [c for c in leggi_configs() if num(c.get('videos_per_day')) >= 1 and str(c.get('voice_id') or '').strip()]
if P.get('solo'):
    canali = [c for c in canali if c.get('channel_name') in P['solo']]
righe = []
for c in canali:
    nome = str(c.get('channel_name') or 'canale'); slug = re.sub(r'\W+', '_', nome.lower()).strip('_')
    lingua = 'it' if str(c.get('language') or '').lower().startswith('it') else 'en'
    testo = P.get('testo_' + lingua) or TESTI[lingua]
    vel = num(c.get('voice_speed')) or 1.0
    for m in MODELLI:
        f = os.path.join(CART, f'{slug}_{m}.mp3')
        if os.path.exists(f):   # gia' fatto in un giro precedente: non si ripaga
            continue
        try:
            audio = el(f"/v1/text-to-speech/{str(c['voice_id']).strip()}?output_format=mp3_44100_128",
                       {'text': testo, 'model_id': m, 'voice_settings': {'stability': .45, 'similarity_boost': .75, 'speed': max(.7, min(1.2, vel))}})
        except Exception as e:
            righe.append(f'{nome} | {m} | ERRORE {str(e)[:120]}'); print(righe[-1]); continue
        open(f, 'wb').write(audio)
        crediti = INTEST.get('character-cost') or INTEST.get('x-character-count') or '?'   # crediti scalati per questo audio (intestazione della risposta)
        righe.append(f'{nome} | {lingua} | {m} | {len(testo)} caratteri | crediti usati {crediti} | {f}'); print(righe[-1])
righe.append('intestazioni ultima risposta: ' + ', '.join(f'{k}={v}' for k, v in INTEST.items() if 'char' in k or 'cost' in k or 'credit' in k))
try:
    righe.append(f'crediti usati in tutto nel mese: {usati()}')
except Exception as e:
    righe.append('abbonamento non letto: ' + str(e)[:80])
open(os.path.join(CART, 'esito.txt'), 'w').write('\n'.join(righe) + '\n')
