#!/usr/bin/env python3
"""SCENE AI (27 nov 2026): crea le inquadrature di una prova con l'AI e le mette in una libreria di clip,
poi la prova si monta con strumenti/prova_archivio.py (voce, tagli, musica) usando "libreria": <nome>.
- ogni scena: un'immagine (fal flux-2 klein 4b, ~0,02 $) e, se moto = "clip", un video AI dall'immagine
  (minimax/h3-max-turbo/image-to-video 768P, ~0,04 $ al secondo) altrimenti movimento lento fatto in codice (gratis)
- stile = prefisso comune a tutti i prompt (coerenza); cornice = "tv_epoca" aggiunge bordo arrotondato, grana e seppia
PAYLOAD = {"nome": "...", "stile": "...", "cornice": "", "secondi_clip": 5,
           "scene": [{"id": "a1", "prompt": "...", "moto": "clip|foto", "movimento": "camera push in slowly"}]}
Uscita: libreria_clip/<nome>/ (scena_<id>.mp4, immagine_<id>.png, indice.json, costi.json)"""
import base64, json, os, subprocess, time, urllib.request
from PIL import Image, ImageDraw, ImageFilter

E = os.environ.get
P = json.loads(E('PAYLOAD') or '{}')
NOME = P['nome']; OUT = os.path.join('libreria_clip', NOME); os.makedirs(OUT, exist_ok=True)
REPO = E('GITHUB_REPOSITORY', 'gggweb23-gif/ambience')
HD = {'Authorization': 'Key ' + E('FAL_KEY', ''), 'Content-Type': 'application/json'}
W, H, FPS = 1920, 1080, 30
spesa = []
log = lambda *a: print(time.strftime('%H:%M:%S'), *a, flush=True)


def http(u, dati=None, timeout=120):
    r = urllib.request.Request(u, data=json.dumps(dati).encode() if dati is not None else None, headers=HD)
    return json.load(urllib.request.urlopen(r, timeout=timeout))


def fal(ep, dati, attesa=600):
    inv = http('https://queue.fal.run/' + ep, dati)
    for _ in range(attesa // 3):
        time.sleep(3)
        st = http(inv['status_url']).get('status')
        if st == 'COMPLETED':
            return http(inv['response_url'])
        if st in ('FAILED', 'ERROR'):
            raise RuntimeError(ep + ' fallito')
    raise TimeoutError(ep)


def scarica(u, p):
    urllib.request.urlretrieve(u, p)


def cornice_png():
    """bordo da vecchio televisore/pellicola: nero fuori, angoli arrotondati sfumati"""
    m = Image.new('L', (W, H), 255)
    ImageDraw.Draw(m).rounded_rectangle((34, 26, W - 34, H - 26), radius=120, fill=0)
    m = m.filter(ImageFilter.GaussianBlur(22))
    o = Image.new('RGBA', (W, H), (8, 6, 4, 255)); o.putalpha(m)
    p = '/tmp/cornice.png'; o.save(p); return p


CORN = cornice_png() if P.get('cornice') == 'tv_epoca' else None
FILTRO = ('colorchannelmixer=.95:.08:0:0:.05:.88:.05:0:0:.08:.75,eq=contrast=1.06:saturation=0.8,'
          'noise=alls=10:allf=t,vignette=PI/4.5') if CORN else 'eq=contrast=1.03:saturation=1.05'


def rifinisci(src, dst, secondi):
    """porta a 1920x1080 30 fps, applica lo stile; se src e' un'immagine fa un movimento lento e fluido (niente tremolio)"""
    if src.endswith('.png'):
        n = int(secondi * FPS)
        vf = (f"scale=3840:2160:force_original_aspect_ratio=increase,crop=3840:2160,"
              f"zoompan=z='1+0.06*on/{n}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={n}:s={W}x{H}:fps={FPS},{FILTRO}")
        cmd = ['ffmpeg', '-y', '-v', 'error', '-loop', '1', '-i', src]
    else:
        vf = f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,crop={W}:{H},fps={FPS},{FILTRO}"
        cmd = ['ffmpeg', '-y', '-v', 'error', '-i', src]
    if CORN:
        cmd += ['-i', CORN, '-filter_complex', f'[0:v]{vf}[b];[b][1:v]overlay=0:0,format=yuv420p[v]', '-map', '[v]', '-map', '0:a?']
    else:
        cmd += ['-vf', vf + ',format=yuv420p', '-map', '0:v', '-map', '0:a?']
    subprocess.run(cmd + ['-t', str(secondi), '-c:a', 'aac', '-b:a', '128k', '-c:v', 'libx264', '-preset', 'medium', '-crf', '19', dst], check=True)


indice = []
for n, s in enumerate(P['scene']):
    sid = s['id']; img = os.path.join(OUT, f'immagine_{sid}.png'); mp4 = os.path.join(OUT, f'scena_{sid}{P.get("suffisso", "")}.mp4')
    if not os.path.exists(img):
        r = fal('fal-ai/flux-2/klein/4b', {'prompt': (P.get('stile', '') + ' ' + s['prompt']).strip(),
                                           'image_size': {'width': 1920, 'height': 1080}, 'num_images': 1, 'output_format': 'png'})
        scarica(r['images'][0]['url'], img); spesa.append(['immagine flux-2 klein 4b', sid, 0.02])
        log('immagine', sid)
    sec = float(s.get('secondi') or P.get('secondi_clip') or 5)
    if s.get('moto') == 'clip':
        grezzo = f'/tmp/grezzo_{sid}.mp4'
        with open(img, 'rb') as f:   # l'immagine passa come data URI (niente caricamenti intermedi)
            data_uri = 'data:image/png;base64,' + base64.b64encode(f.read()).decode()
        if P.get('modello_video', '').startswith('wan'):   # 27 nov: Wan 2.2 A14B turbo, prezzo a clip (~5 s): 480p 0,05 $, 580p 0,075 $, 720p 0,10 $
            ris = P.get('risoluzione_video') or '580p'
            r = fal('fal-ai/wan/v2.2-a14b/image-to-video/turbo', {'prompt': s.get('movimento') or s['prompt'], 'image_url': data_uri,
                                                                  'resolution': ris, 'aspect_ratio': '16:9', 'acceleration': 'regular'}, attesa=900)
            scarica(r['video']['url'], grezzo); spesa.append([f'video AI wan 2.2 turbo {ris}', sid, {'480p': .05, '580p': .075, '720p': .10}[ris]])
        elif P.get('modello_video') == 'ltx':   # 27 nov: LTX-Video 13B 0.9.8 distilled 720p, 0,02 $ al secondo (meta' di h3)
            r = fal('fal-ai/ltxv-13b-098-distilled/image-to-video', {'prompt': s.get('movimento') or s['prompt'], 'image_url': data_uri,
                                                                     'resolution': '720p', 'aspect_ratio': '16:9', 'num_frames': int(sec * 24) + 1}, attesa=900)
            scarica(r['video']['url'], grezzo); spesa.append(['video AI ltxv 13b distilled 720p', sid, round(0.02 * sec, 3)])
        else:
            r = fal('minimax/h3-max-turbo/image-to-video', {'prompt': s.get('movimento') or s['prompt'], 'image_url': data_uri,
                                                             'duration': sec, 'resolution': '768P', 'prompt_expansion_mode': 'disabled'}, attesa=900)
            scarica(r['video']['url'], grezzo); spesa.append(['video AI h3-max-turbo 768P', sid, round(0.04 * sec, 3)])
        log('clip AI', sid)
        if s.get('suoni'):   # 27 nov (Giorgio: si devono sentire tuoni, esplosioni...): suoni sincronizzati con la clip, mmaudio 0,001 $/s
            try:
                a = fal('fal-ai/mmaudio-v2', {'video_url': r['video']['url'], 'prompt': s['suoni'], 'negative_prompt': 'music, speech, voice, singing',
                                              'duration': min(30, sec + 1), 'num_steps': 25}, attesa=600)
                scarica(a['video']['url'], grezzo); spesa.append(['suoni mmaudio', sid, round(0.001 * (sec + 1), 4)])
                log('suoni', sid)
            except Exception as e:
                log('suoni non riusciti', sid, str(e)[:80])
        rifinisci(grezzo, mp4, sec)
    else:
        rifinisci(img, mp4, sec)
    indice.append({'n': n, 'nasa_id': f'{NOME}@{sid}', 'titolo': s['prompt'][:80], 'durata': sec, 'da': 0,
                   'url': f'https://raw.githubusercontent.com/{REPO}/main/{OUT}/scena_{sid}{P.get("suffisso", "")}.mp4', 'movimento': 8,
                   'licenza': 'generato con AI', 'cosa': s['prompt'][:120], 'luogo': '', 'epoca': '', 'parla_in_camera': False,
                   'scritte': False, 'animazione': True, 'cornice_voluta': bool(CORN), 'qualita': 8, 'tag': [sid], 'ok': True, 'anno': 2026})
json.dump(indice, open(os.path.join(OUT, 'indice.json'), 'w'), indent=1)
json.dump({'righe': spesa, 'totale_dollari': round(sum(x[2] for x in spesa), 2)}, open(os.path.join(OUT, 'costi.json'), 'w'), indent=1)
log('fatto, spesa stimata $', round(sum(x[2] for x in spesa), 2))
