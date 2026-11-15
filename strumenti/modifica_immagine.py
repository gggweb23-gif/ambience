#!/usr/bin/env python3
"""Modifica un'immagine del repository con Nano Banana 2 edit (~0,04-0,08 $ a immagine, 2K).
PAYLOAD = {"immagine": "percorso nel repo", "prompt": "...", "out": "percorso di uscita", "quante": 2}
Serve per rifare il disegno di una copertina lasciando spazio alla scritta (15 nov, KAO)."""
import base64, json, os, time, urllib.request
P = json.loads(os.environ['PAYLOAD']); FAL = {'Authorization': 'Key ' + os.environ['FAL_KEY'], 'Content-Type': 'application/json'}


def http(u, dati=None, h=None, raw=False):
    r = urllib.request.urlopen(urllib.request.Request(u, data=json.dumps(dati).encode() if dati is not None else None, headers=h or {}), timeout=180).read()
    return r if raw else json.loads(r)


img = 'data:image/jpeg;base64,' + base64.b64encode(open(P['immagine'], 'rb').read()).decode()
for n in range(int(P.get('quante') or 1)):
    inv = http('https://queue.fal.run/fal-ai/nano-banana-2/edit', {'prompt': P['prompt'], 'image_urls': [img], 'aspect_ratio': '16:9', 'resolution': '2K',
                                                                  'output_format': 'jpeg', 'num_images': 1}, FAL)
    for _ in range(150):
        time.sleep(4)
        st = http(inv['status_url'], h=FAL)
        if st.get('status') == 'COMPLETED':
            break
    out = http(inv['response_url'], h=FAL)
    dest = P['out'].replace('.jpg', f'_{n + 1}.jpg')
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    open(dest, 'wb').write(http(out['images'][0]['url'], raw=True))
    print('salvata', dest)
