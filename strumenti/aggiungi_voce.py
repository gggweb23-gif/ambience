#!/usr/bin/env python3
"""Aggiunge stabilmente all'account ElevenLabs una voce della libreria condivisa (es. la voce scelta da Giorgio per un canale).
Env: VOICE_ID (della libreria), CERCA (nome della voce per trovarla), ELEVENLABS_API_KEY. Stampa il voice_id da usare."""
import json, os, urllib.parse, urllib.request
K = os.environ['ELEVENLABS_API_KEY']; VID = os.environ['VOICE_ID']


def el(p, d=None):
    r = urllib.request.Request('https://api.elevenlabs.io' + p, data=json.dumps(d).encode() if d is not None else None, headers={'xi-api-key': K, 'Content-Type': 'application/json'})
    return json.loads(urllib.request.urlopen(r, timeout=60).read() or b'{}')


miei = el('/v2/voices?page_size=100').get('voices', [])
if any(v['voice_id'] == VID for v in miei):
    print('voce gia nell account:', VID)
else:
    j = el('/v1/shared-voices?' + urllib.parse.urlencode({'search': os.environ.get('CERCA', ''), 'page_size': 30}))
    v = next(x for x in j['voices'] if x['voice_id'] == VID)
    r = el(f"/v1/voices/add/{v['public_owner_id']}/{VID}", {'new_name': v['name'][:60]})
    print('voce aggiunta all account:', r.get('voice_id'), v['name'])
