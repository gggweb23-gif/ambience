#!/usr/bin/env python3
"""PROVA VOCI NOTIZIE (16 nov 2026, Giorgio: "voce meno AI, una persona autorevole che spiega, quasi umana").
Stesso testo (~25 s), piu' voci e impostazioni: la voce attuale, la voce attuale con impostazioni da giornalista, il modello eleven_v3,
e le voci italiane maschili piu' usate della libreria ElevenLabs per notizie/racconto (aggiunte all'account solo per la prova e poi tolte).
Solo crediti dell'abbonamento ElevenLabs, nessuna spesa in dollari. Uscita: prove_video/voci_notizie/*.mp3 + elenco.txt"""
import json, os, re, urllib.parse, urllib.request
K = os.environ['ELEVENLABS_API_KEY']; OUT = 'prove_video/voci_notizie'; os.makedirs(OUT, exist_ok=True)
TESTO = ("Revolut è appena stata commissariata. Lo ha deciso oggi il Tribunale di Milano. Per un anno, la filiale italiana della banca digitale "
         "da oltre sei milioni di clienti sarà affiancata da due amministratori giudiziari. Il motivo? Secondo la Procura, ci sono operazioni "
         "per settantasei virgola cinque milioni di euro.")
ATTUALE = 'glnsgBC77wt5zOYU0szz'
GIORNALISTA = {'stability': .6, 'similarity_boost': .8, 'style': .08, 'speed': 1.0, 'use_speaker_boost': True}


def el(percorso, dati=None, metodo=None, raw=False):
    req = urllib.request.Request('https://api.elevenlabs.io' + percorso, data=json.dumps(dati).encode() if dati is not None else None,
                                 headers={'xi-api-key': K, 'Content-Type': 'application/json'}, method=metodo)
    with urllib.request.urlopen(req, timeout=180) as r:
        b = r.read()
    return b if raw else json.loads(b or b'{}')


def parla(nome, voce, modello, imp):
    try:
        a = el(f'/v1/text-to-speech/{voce}?output_format=mp3_44100_192', {'text': TESTO, 'model_id': modello, 'voice_settings': imp}, raw=True)
        open(f'{OUT}/{nome}.mp3', 'wb').write(a); print('fatta', nome, flush=True); return True
    except Exception as e:
        print('non riuscita', nome, getattr(e, 'read', lambda: b'')()[:300], str(e)[:120], flush=True); return False


righe = []
if parla('A_attuale', ATTUALE, 'eleven_multilingual_v2', {'stability': .42, 'similarity_boost': .78, 'style': .28, 'speed': 1.08, 'use_speaker_boost': True}):
    righe.append('A_attuale: voce di oggi (quella dei video di prova), impostazioni di oggi')
if parla('B_attuale_giornalista', ATTUALE, 'eleven_multilingual_v2', GIORNALISTA):
    righe.append('B_attuale_giornalista: stessa voce, piu stabile e calma, velocita normale')
if parla('C_attuale_v3', ATTUALE, 'eleven_v3', {'stability': .5, 'similarity_boost': .8, 'style': 0, 'use_speaker_boost': True}):
    righe.append('C_attuale_v3: stessa voce col modello piu nuovo e naturale (eleven_v3)')
# voci italiane maschili della libreria, le piu' usate, per notizie e racconto
cand, visti = [], set()
for uc in ('news', 'narrative_story', 'informative_educational'):
    try:
        j = el('/v1/shared-voices?' + urllib.parse.urlencode({'language': 'it', 'gender': 'male', 'use_cases': uc, 'page_size': 30, 'sort': 'cloned_by_count'}))
    except Exception as e:
        print('libreria non letta', uc, str(e)[:100]); continue
    for v in j.get('voices', []):
        if v['voice_id'] not in visti and v['voice_id'] != ATTUALE:
            visti.add(v['voice_id']); cand.append(v)
cand.sort(key=lambda v: -(v.get('cloned_by_count') or 0))
print('candidate:', [(v.get('name'), v.get('use_case'), v.get('cloned_by_count'), v.get('age'), v.get('accent')) for v in cand[:10]])
lettere = 'DEFG'
for v in cand[:4]:
    nome = f"{lettere[len([r for r in righe if r[0] in lettere])]}_{re.sub(r'[^A-Za-z0-9]+', '_', v.get('name') or 'voce')[:30]}"
    aggiunta = None
    try:
        r = el(f"/v1/voices/add/{v['public_owner_id']}/{v['voice_id']}", {'new_name': 'PROVA ' + (v.get('name') or '')[:40]})
        aggiunta = r.get('voice_id') or v['voice_id']
        if parla(nome, aggiunta, 'eleven_multilingual_v2', GIORNALISTA):
            righe.append(f"{nome}: libreria ElevenLabs '{v.get('name')}' ({v.get('use_case')}, {v.get('age')}, accento {v.get('accent')}, "
                         f"usata da {v.get('cloned_by_count')} persone) voice_id {v['voice_id']}")
    except Exception as e:
        print('voce non aggiunta', v.get('name'), str(e)[:150])
    finally:
        if aggiunta:
            try:
                el(f'/v1/voices/{aggiunta}', metodo='DELETE'); print('tolta dall account', v.get('name'))
            except Exception as e:
                print('non tolta', str(e)[:100])
open(f'{OUT}/elenco.txt', 'w').write('\n'.join(righe) + '\n\nTESTO: ' + TESTO + '\n')
print(open(f'{OUT}/elenco.txt').read())
