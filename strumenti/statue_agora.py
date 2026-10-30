#!/usr/bin/env python3
"""PROVA STATUE PER LE COPERTINE (a pagamento, con tetto di spesa): genera con fal (nano-banana-2) statue di marmo
eroiche, muscolose, quasi vere, a mezzo busto, su fondo grigio scuro liscio (facili da scontornare).
PAYLOAD = {"cartella": "prove_video/Agora_of_Sages/statue_ai", "max_spesa": 0.40,
           "statue": [{"nome": "A_dito", "prompt": "..."}, ...]}
Uscita: <cartella>/<nome>.png + spesa.txt (salvati nel repository)."""
import json, os, time, urllib.request

P = json.loads(os.environ.get('PAYLOAD') or '{}')
CART = P.get('cartella') or 'prove_video/statue_ai'; os.makedirs(CART, exist_ok=True)
MAX_SPESA = float(P.get('max_spesa') or 0.40); PREZZO = float(P.get('prezzo') or 0.10); SPESA = {'tot': 0.0}
K = os.environ['FAL_KEY']

BASE = ('Photorealistic white-grey marble statue that looks ALMOST ALIVE, like a real man carved in stone: {soggetto}. '
        'Heroic, powerful, very muscular athletic body with defined chest, shoulders, arms and abs, a draped toga over one shoulder. '
        'Waist-up, big in the frame, filling the whole height of the image. {posa}. '
        'Intense, stern, emotional expression, deep frown, the eyes look STRAIGHT at the viewer. '
        'Realistic marble texture with fine veins, carved curly hair and full beard. Dramatic cinematic side light, deep shadows, very high contrast. '
        'Plain flat dark-grey studio background, nothing else in the background. No text, no logo, no watermark.')


def http(url, dati=None, raw=False):
    req = urllib.request.Request(url, data=json.dumps(dati).encode() if dati is not None else None,
                                 headers={'Content-Type': 'application/json', 'Authorization': 'Key ' + K})
    with urllib.request.urlopen(req, timeout=300) as r:
        b = r.read()
        return b if raw else json.loads(b.decode() or '{}')


def fal(modello, dati):
    if SPESA['tot'] + PREZZO > MAX_SPESA + 1e-9:
        raise RuntimeError('tetto di spesa %.2f $ raggiunto' % MAX_SPESA)
    SPESA['tot'] += PREZZO   # contata subito: fal fa pagare anche se poi qualcosa va storto
    inv = http('https://queue.fal.run/' + modello, dati)
    for _ in range(150):
        time.sleep(4)
        st = http(inv['status_url'])
        if st.get('status') == 'COMPLETED':
            return http(inv['response_url'])
        if st.get('status') not in ('IN_QUEUE', 'IN_PROGRESS'):
            raise RuntimeError(json.dumps(st)[:300])
    raise RuntimeError('Fal: tempo scaduto')


righe = []
for s in P.get('statue', []):
    prompt = s.get('prompt') or BASE.format(soggetto=s.get('soggetto', 'an ancient Stoic philosopher'), posa=s.get('posa', ''))
    try:
        r = fal(P.get('modello') or 'fal-ai/nano-banana-2', {'prompt': prompt, 'aspect_ratio': s.get('formato') or '3:4',
                                                             'resolution': P.get('risoluzione') or '1K', 'output_format': 'png', 'num_images': 1})
        f = os.path.join(CART, s['nome'] + '.png')
        open(f, 'wb').write(http(r['images'][0]['url'], raw=True))
        righe.append(f"{s['nome']}: ok")
    except Exception as e:
        righe.append(f"{s['nome']}: NON RIUSCITA {str(e)[:200]}")
    print(righe[-1], flush=True)
righe.append('spesa stimata: %.2f $' % SPESA['tot'])
open(os.path.join(CART, 'spesa.txt'), 'w').write('\n'.join(righe) + '\n')
print(righe[-1])
