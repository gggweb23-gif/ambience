#!/usr/bin/env python3
"""VOCE PER SCENE (7 nov 2026): per le prove video fatte in codice. Una voce ElevenLabs per ogni scena (con i tempi di ogni lettera),
stessa voce e stesso modello dei video del canale indicato. Usa i crediti dell'abbonamento, nessun costo in dollari.
PAYLOAD = {"canale": "<channel_name di Channel Configs>" oppure "voce": "<voice_id>", "cartella": "prove_video/voce_scene/<nome>",
           "scene": ["testo scena 1", "testo scena 2", ...], "modello": "eleven_multilingual_v2" (facoltativo), "velocita": 1.0 (facoltativo)}"""
import base64, json, os, sys, time, urllib.request
P = json.loads(os.environ.get('PAYLOAD') or '{}')
K = os.environ['ELEVENLABS_API_KEY']
CART = P.get('cartella') or 'prove_video/voce_scene/prova'
os.makedirs(CART, exist_ok=True)
SCENE = P.get('scene') or []
if not SCENE:
    sys.exit('nessuna scena nel PAYLOAD')


def num(x, d):
    try:
        return float(str(x).replace(',', '.')) if str(x or '').strip() else d
    except Exception:
        return d


voce, vel = str(P.get('voce') or '').strip(), num(P.get('velocita'), 0)
if not voce and P.get('canale'):   # sola lettura di Channel Configs: voce e velocita' del canale
    from google.oauth2 import service_account
    from google.auth.transport.requests import Request
    import urllib.parse
    cr = service_account.Credentials.from_service_account_info(json.loads(os.environ['GOOGLE_SA_KEY']), scopes=['https://www.googleapis.com/auth/spreadsheets.readonly'])
    cr.refresh(Request()); H = {'Authorization': 'Bearer ' + cr.token}
    ID = os.environ.get('FOGLIO_CONFIGS', '1COMpgHJshcmz_a9s-WsjCO5xbhwxBazt-ZB0G_C7Rb0')
    g = lambda u: json.loads(urllib.request.urlopen(urllib.request.Request('https://sheets.googleapis.com/v4/spreadsheets/' + ID + u, headers=H), timeout=60).read())
    sch = g('?fields=sheets.properties')['sheets'][0]['properties']['title']
    v = g('/values/' + urllib.parse.quote(f"'{sch}'!A1:AZZ200")).get('values', [])
    h = [str(x).strip() for x in v[0]]
    for c in (dict(zip(h, r + [''] * (len(h) - len(r)))) for r in v[1:]):
        if str(c.get('channel_name') or '').strip().lower() == str(P['canale']).strip().lower():
            voce = str(c.get('voice_id') or '').strip(); vel = vel or num(c.get('voice_speed'), 1.0)
            break
if not voce:
    sys.exit('voce non trovata (canale o voice_id)')
vel = vel or 1.0
modello = P.get('modello') or 'eleven_multilingual_v2'
print('voce', voce, 'modello', modello, 'velocita', vel)
for i, testo in enumerate(SCENE, 1):
    f = os.path.join(CART, f'scena_{i:02d}.mp3')
    if os.path.exists(f):   # gia' fatta in un giro precedente: non si ripaga
        continue
    prima, dopo = ' '.join(SCENE[:i - 1])[-400:], ' '.join(SCENE[i:])[:400]
    for k in range(4):
        try:
            req = urllib.request.Request(f'https://api.elevenlabs.io/v1/text-to-speech/{voce}/with-timestamps?output_format=mp3_44100_128',
                                         data=json.dumps({'text': testo, 'model_id': modello, 'previous_text': prima, 'next_text': dopo,
                                                          'voice_settings': {'stability': .5, 'similarity_boost': .75, 'speed': max(.7, min(1.2, vel))}}).encode(),
                                         headers={'xi-api-key': K, 'Content-Type': 'application/json'})
            j = json.loads(urllib.request.urlopen(req, timeout=180).read())
            open(f, 'wb').write(base64.b64decode(j['audio_base64']))
            json.dump(j.get('alignment') or {}, open(f[:-4] + '.json', 'w'))
            print('scena', i, 'ok', len(testo), 'caratteri')
            break
        except Exception as e:
            print('scena', i, 'non riuscita, riprovo:', str(e)[:150]); time.sleep(4 * (k + 1))
    else:
        sys.exit(f'scena {i}: ElevenLabs non risponde')
json.dump({'voce': voce, 'modello': modello, 'velocita': vel, 'scene': SCENE}, open(os.path.join(CART, 'scene.json'), 'w'), ensure_ascii=False, indent=1)
