#!/usr/bin/env python3
"""PROVA BREVE DEL MOTORE "statua + karaoke" (gli stessi programmi dei video veri, su ~40 secondi):
1) copertina_statua.py  -> copertina + immagine del video dalla stessa statua nuova (fal ~0,10 $)
2) voce ElevenLabs delle frasi (voce e modello della riga del canale)
3) render_filosofo.py con render_style della riga (testo karaoke + cenere + musica a rotazione + volume -14 LUFS), senza caricare nulla.
PAYLOAD = {"cartella": "prove_video/Agora_of_Sages/motore", "titolo": "...", "testo_copertina": "...", "frasi": ["...", "..."], "config": {riga Channel Configs}}"""
import json, os, shutil, subprocess, urllib.request

P = json.loads(os.environ['PAYLOAD'])
CFG = P['config']; CART = P.get('cartella') or 'prove_video/prova_motore'
os.makedirs(CART, exist_ok=True)
ROOT = os.getcwd(); LAV = os.path.join(ROOT, 'lavoro_prova_statua'); os.makedirs(LAV, exist_ok=True)


def log(*a):
    print(*a, flush=True)
    open(os.path.join(CART, 'log.txt'), 'a').write(' '.join(str(x) for x in a) + '\n')


open(os.path.join(CART, 'log.txt'), 'w').close()
# 1) copertina + statua
subprocess.run(['python3', 'copertina_statua.py'], env={**os.environ, 'PAYLOAD': json.dumps({'titolo': P['titolo'], 'testo_copertina': P.get('testo_copertina', ''),
                                                                                          'cartella': 'lavoro_statua', 'config': CFG})})
ris = json.load(open(os.path.join(ROOT, 'lavoro_statua', 'risultato.json')))
log('copertina statua:', json.dumps(ris)[:400])
if not ris.get('ok'):
    raise SystemExit('copertina statua non riuscita')
shutil.copy(ris['copertina'], os.path.join(CART, 'copertina.jpg'))
# 2) voce delle frasi
scene = []
for i, t in enumerate(P['frasi']):
    req = urllib.request.Request(f"https://api.elevenlabs.io/v1/text-to-speech/{CFG.get('voice_id')}",
                                 data=json.dumps({'text': t, 'model_id': CFG.get('voice_model_id') or 'eleven_multilingual_v2'}).encode(),
                                 headers={'xi-api-key': os.environ['ELEVENLABS_API_KEY'], 'Content-Type': 'application/json', 'Accept': 'audio/mpeg'})
    f = os.path.join(LAV, f'scena_{i}.mp3'); open(f, 'wb').write(urllib.request.urlopen(req, timeout=300).read())
    scene.append({'testo': t, 'audio': 'file://' + f})
log('voce:', len(scene), 'scene')
# 3) montaggio con il motore vero
stile = CFG.get('render_style') or {}
if isinstance(stile, str):
    stile = json.loads(stile or '{}')
dati = {'titolo': P['titolo'], 'scene': scene, 'stile': stile, 'config': CFG, 'statua_video': os.path.join(ROOT, ris['statua_video'])}
fd = os.path.join(LAV, 'dati.json'); json.dump(dati, open(fd, 'w'))
r = subprocess.run(['python3', 'render_filosofo.py'], env={**os.environ, 'PAYLOAD': json.dumps({'id': 'prova', 'dati_url': 'file://' + fd, 'resume_url': ''}),
                                                           'DRY_RUN': '1', 'LINGUA': str(CFG.get('language') or 'en')[:2]})
fin = os.path.join(ROOT, 'lavoro_filosofo', 'video_finale.mp4')
if not os.path.exists(fin):
    raise SystemExit('montaggio non riuscito (codice %s)' % r.returncode)
out = os.path.join(CART, 'video.mp4')
subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', fin, '-vf', 'scale=1920:1080', '-c:v', 'libx264', '-crf', '21', '-preset', 'medium', '-c:a', 'copy', out], check=True)
d = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', out], capture_output=True, text=True).stdout)
for i in range(1, 7):
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-ss', f'{d * (i - .5) / 6:.2f}', '-i', out, '-frames:v', '1', '-vf', 'scale=960:-1', os.path.join(CART, f'fotogramma_{i}.jpg')])
lufs = subprocess.run(['ffmpeg', '-i', out, '-af', 'ebur128', '-f', 'null', '-'], capture_output=True, text=True).stderr
log('FATTO', round(d, 1), 's |', [l.strip() for l in lufs.splitlines() if 'I:' in l][-1:])
