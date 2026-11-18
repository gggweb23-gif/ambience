#!/usr/bin/env python3
"""18 nov 2026 (Giorgio: "dobbiamo ridurre i costi"): prova di 1 minuto della stessa voce notizie con
 - ElevenLabs Flash v2.5 (mezzo credito per carattere, stesse voci)
 - MiniMax Speech-02 HD su fal (0,10 $ ogni 1.000 caratteri, non usa i crediti ElevenLabs)
Testo: inizio del copione notizie di oggi (inglese e italiano). Salva in prove_voci/<data>/."""
import datetime as dt, glob, json, os, urllib.request

E = os.environ.get
OGGI = dt.date.today().isoformat()
OUT = os.path.join('prove_voci', OGGI); os.makedirs(OUT, exist_ok=True)
VOCI_11 = {'en': 'uju3wxzG5OhpWcoi3SMy', 'it': 'glnsgBC77wt5zOYU0szz'}   # voce E (inglese) e voce C (italiano) dei canali notizie
VOCI_MM = {'en': ['Deep_Voice_Man', 'Imposing_Manner'], 'it': ['Deep_Voice_Man', 'Determined_Man']}


def testo(lingua):
    f = sorted(glob.glob(f'notizie/auto/*_{lingua}.json'))[-1]
    t, n = '', json.load(open(f))
    for s in n['scene']:
        if len(t) > 850:
            break
        t += s['testo'].strip() + ' '
    return t.strip(), f


def post(url, dati, testate):
    r = urllib.request.Request(url, data=json.dumps(dati).encode(), headers=dict(testate, **{'Content-Type': 'application/json'}))
    return urllib.request.urlopen(r, timeout=300)


for lingua in ('en', 'it'):
    t, f = testo(lingua)
    print(lingua, len(t), 'caratteri da', f)
    # ElevenLabs Flash v2.5
    try:
        r = post(f'https://api.elevenlabs.io/v1/text-to-speech/{VOCI_11[lingua]}?output_format=mp3_44100_128',
                 {'text': t, 'model_id': 'eleven_flash_v2_5', 'language_code': lingua,
                  'voice_settings': {'stability': .45, 'similarity_boost': .75}}, {'xi-api-key': E('ELEVENLABS_API_KEY', '')})
        open(os.path.join(OUT, f'{lingua}_elevenlabs_flash.mp3'), 'wb').write(r.read()); print('  ok elevenlabs flash')
    except Exception as e:
        print('  ERRORE elevenlabs flash', str(e)[:200])
    # MiniMax su fal
    for v in VOCI_MM[lingua]:
        try:
            j = json.loads(post('https://fal.run/fal-ai/minimax/speech-02-hd',
                                {'text': t, 'output_format': 'url', 'language_boost': 'English' if lingua == 'en' else 'Italian',
                                 'voice_setting': {'voice_id': v, 'speed': 1.0}}, {'Authorization': 'Key ' + E('FAL_KEY', '')}).read())
            a = urllib.request.urlopen(j['audio']['url'], timeout=120).read()
            open(os.path.join(OUT, f'{lingua}_minimax_{v}.mp3'), 'wb').write(a); print('  ok minimax', v)
        except Exception as e:
            print('  ERRORE minimax', v, str(e)[:300])
