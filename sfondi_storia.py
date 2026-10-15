#!/usr/bin/env python3
"""
MULTICHANNEL - Sfondi "simbolo" per il canale Storia dei Paesi (prova con 2 paesi).
Genera con Fal (nano-banana-2, 1K) sfondi a cartone SENZA persone: gli omini li aggiunge e anima il renderer.
Risultato: cartella sfondi/ (artifact "sfondi-storia").
"""
import json, os, time, urllib.request

OUT = os.path.join(os.getcwd(), 'sfondi')
STILE = ('Wide 2D cartoon illustration for an animated history video, clean thick black outlines, flat warm colours with soft simple shading, '
         'like a modern illustrated children history book. The scene is EMPTY: absolutely no people, no animals in the foreground. '
         'The lower 30% of the image is open flat ground where characters will be placed later. The top-right corner is plain sky. '
         'No text, no letters, no signs with writing, no logos, no watermark.')
SFONDI = {
    'giappone_1_risaie': 'Terraced rice paddies with water reflections, a few thatched huts, Mount Fuji with a snowy top in the distance, ancient Japan around 300 BC.',
    'giappone_2_palazzo': 'An ancient Japanese imperial palace of the Nara period with red wooden columns and curved tiled roofs, a wide gravel courtyard in front.',
    'giappone_3_castello': 'A white feudal Japanese castle with layered dark roofs on a stone base, cherry trees in bloom, a dirt road in front, 1500s.',
    'giappone_4_porto': 'A quiet Japanese harbour of the Edo period with wooden boats tied to a pier, tiled houses along the shore, calm sea.',
    'giappone_5_meiji': 'A Tokyo street in the Meiji era around 1880: brick buildings, gas lamps, rickshaws parked, a steam railway line in the background.',
    'giappone_6_tokyo': 'Modern Tokyo at night: glowing skyscrapers, neon colours, an elevated railway, a wide empty plaza in front.',
    'lasvegas_1_deserto': 'The Mojave desert before cities: a dry valley with a small spring and green bushes, red mountains in the distance, a clear sky.',
    'lasvegas_2_ferrovia': 'A dusty railroad town in 1905: a wooden train station, a few wooden shops and tents along a dirt main street, desert mountains behind.',
    'lasvegas_3_diga': 'A huge concrete dam under construction in a rocky canyon in the 1930s, cranes and scaffolding, the river below.',
    'lasvegas_4_neon50': 'A 1950s casino street with glowing neon signs (no readable words), vintage casino buildings, evening sky.',
    'lasvegas_5_strip': 'The modern Las Vegas Strip at night: huge resort hotels, a big glowing sphere building, fountains, palm trees, a wide pavement in front.',
    'lasvegas_6_oggi': 'Las Vegas today seen from the desert at sunset: the skyline of tall hotels far away, suburbs, highway, desert in front.',
}

def http_json(url, data=None, headers=None):
    body = json.dumps(data).encode() if data is not None else None
    h = {'Content-Type': 'application/json'} if data is not None else {}
    h.update(headers or {})
    with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=h), timeout=120) as r:
        return json.loads(r.read().decode() or '{}')

def fal(modello, dati):
    h = {'Authorization': 'Key ' + os.environ['FAL_KEY']}
    inv = http_json('https://queue.fal.run/' + modello, dati, h)
    for _ in range(100):
        time.sleep(5)
        st = http_json(inv['status_url'], headers=h)
        if st.get('status') == 'COMPLETED':
            return http_json(inv['response_url'], headers=h)
        if st.get('status') not in ('IN_QUEUE', 'IN_PROGRESS'):
            raise RuntimeError(json.dumps(st)[:300])
    raise RuntimeError('tempo scaduto')

os.makedirs(OUT, exist_ok=True)
for nome, scena in SFONDI.items():
    try:
        res = fal('fal-ai/nano-banana-2', {'prompt': scena + ' ' + STILE, 'aspect_ratio': '16:9', 'resolution': '1K', 'output_format': 'jpeg', 'num_images': 1})
        req = urllib.request.Request(res['images'][0]['url'], headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=120) as r, open(os.path.join(OUT, nome + '.jpg'), 'wb') as f:
            f.write(r.read())
        print('fatto', nome, flush=True)
    except Exception as e:
        print('NON riuscito', nome, e, flush=True)
print(sorted(os.listdir(OUT)))
