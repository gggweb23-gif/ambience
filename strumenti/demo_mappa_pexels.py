#!/usr/bin/env python3
"""DEMO VISIVE (30 s, senza voce, musica e suoni) di 3 modi di unire mappa animata e clip Pexels, sul tema Egitto:
1 = ZOOM DENTRO LA MAPPA (mappa -> zoom nella clip del luogo -> mappa)   2 = MINI-MAPPA nell'angolo (clip a schermo intero, mappa che si ingrandisce nei momenti forti)
3 = MAPPA PALCOSCENICO con finestre Pexels. Tutte con la linea del tempo in alto. Salva in prove_video/<cartella>/demo_N.mp4 (720p, leggere)."""
import json, os, re, subprocess, sys, urllib.parse, urllib.request
sys.path.insert(0, os.getcwd())
os.environ.setdefault('PAYLOAD', '{}')
P = json.loads(os.environ['PAYLOAD'])
os.environ['PAYLOAD'] = json.dumps({'filo_storia': 'SI', 'language': 'it', 'mascotte': 'NO',
                                    'tema_colori': P.get('tema_colori') or 'navy=#1446A0, rosso=#3ED3C4, crema=#FFFFFF, carta=#FFFFFF, oro=#2F80ED, verde=#F2C94C, luce=#FFFFFF, accento=#2F80ED'})
import video_mappe as VM
from PIL import Image, ImageDraw, ImageFilter
CART = P.get('cartella') or 'prove_video/demo'; os.makedirs(CART, exist_ok=True)
LAV = os.path.abspath('lav_demo'); os.makedirs(LAV, exist_ok=True); VM.LAV = LAV
W, H, FPS = VM.W, VM.H, VM.FPS


def run(c):
    subprocess.run([str(x) for x in c], check=True)


def clip_pexels(q, dur, nome):
    """Clip Pexels HD tagliata a 'dur' secondi, 1920x1080, senza audio."""
    out = os.path.join(LAV, nome + '.mp4')
    url = 'https://api.pexels.com/videos/search?' + urllib.parse.urlencode({'query': q, 'per_page': 5, 'orientation': 'landscape'})
    r = json.loads(urllib.request.urlopen(urllib.request.Request(url, headers={'Authorization': os.environ['PEXELS_API_KEY'], 'User-Agent': 'Mozilla/5.0'}), timeout=60).read())
    for v in r.get('videos') or []:
        if v.get('duration', 0) < dur:
            continue
        f = sorted([x for x in v['video_files'] if (x.get('width') or 0) >= 1280], key=lambda x: abs((x.get('width') or 0) - 1920))
        if not f:
            continue
        grezzo = os.path.join(LAV, nome + '_src.mp4')
        open(grezzo, 'wb').write(urllib.request.urlopen(urllib.request.Request(f[0]['link'], headers={'User-Agent': 'Mozilla/5.0'}), timeout=120).read())
        run(['ffmpeg', '-v', 'error', '-y', '-i', grezzo, '-t', dur, '-an', '-vf', f'scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS}',
             '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-pix_fmt', 'yuv420p', out])
        print('clip', q, '->', v['url']); return out
    raise RuntimeError('nessuna clip per ' + q)


def scena_mappa(nome, vista, dur, eventi, oro=('EGY',), verde=(), epoca='oggi', traccia=None):
    out = os.path.join(LAV, nome + '.mp4')
    VM.disegna_scena({'scena': {'testo': '', 'vista': vista, 'epoca': epoca, 'oro': list(oro), 'verde': list(verde)}, 'dur': dur,
                      'eventi': eventi, 'path': out, 'traccia': traccia or []})
    return out


def unisci(pezzi, transizioni, out):
    """pezzi = [(file, durata)], transizioni = ['zoomin', ...] (xfade di 0,8 s tra un pezzo e l'altro)."""
    if len(pezzi) == 1:
        os.replace(pezzi[0][0], out); return out
    ins = sum([['-i', f] for f, _ in pezzi], []); fil, prec, t = [], '0:v', 0.0
    for i in range(1, len(pezzi)):
        t += pezzi[i - 1][1] - .8
        lab = f'x{i}'
        fil.append(f'[{prec}][{i}:v]xfade=transition={transizioni[i - 1]}:duration=0.8:offset={t:.2f}[{lab}]'); prec = lab
    run(['ffmpeg', '-v', 'error', '-y', *ins, '-filter_complex', ';'.join(fil), '-map', f'[{prec}]', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-pix_fmt', 'yuv420p', out])
    return out


def linea(video, tappe):
    """Linea del tempo in alto (come nel motore storia): tappe = [(secondo, anno)]."""
    import video_storia as VS
    VS.LINEA_TEMPO = 'alto'; VS.LAV = LAV; VS.FONT = os.path.abspath('risorse_mappe')
    if not os.path.exists(os.path.join(VS.FONT, 'Oswald-SemiBold.ttf')):
        import shutil; shutil.copy(os.path.join(VS.FONT, 'Anton-Regular.ttf'), os.path.join(VS.FONT, 'Oswald-SemiBold.ttf'))
    scene = [{'anno': a} for _, a in tappe]
    inizi = [s for s, _ in tappe] + [VS.durata(video)]
    return VS.linea_del_tempo(video, scene, [inizi[i + 1] - inizi[i] for i in range(len(tappe))])


def finale(video, n):
    out = os.path.join(CART, f'demo_{n}.mp4')
    run(['ffmpeg', '-v', 'error', '-y', '-i', video, '-vf', 'scale=1280:720', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '24', '-pix_fmt', 'yuv420p', '-an', out])
    print('pronto', out)


EGITTO = {'lon': 31.5, 'lat': 27.5, 'larghezza': 36}
MEDIT = {'lon': 26, 'lat': 34, 'larghezza': 40}
GIZA, ALESS, MEMFI, TEBE = (31.13, 29.98), (29.92, 31.2), (31.25, 29.85), (32.65, 25.7)

# ---------- DEMO 1: zoom dentro la mappa
def demo1():
    a = scena_mappa('d1_a', EGITTO, 7, [{'tipo': 'anno', 'testo': '3100 a.C.', '_t': .5}, {'tipo': 'etichetta', 'testo': 'IL NILO', 'lon': 31.3, 'lat': 27.0, '_t': 1.5},
                    {'tipo': 'folla', 'personaggio': 'peasant', 'n': 4, 'lon': 32.6, 'lat': 26.0, '_t': 2.5}, {'tipo': 'impulso', 'lon': GIZA[0], 'lat': GIZA[1], '_t': 4.5}])
    b = clip_pexels('Giza pyramids aerial', 8, 'd1_b')
    c = scena_mappa('d1_c', MEDIT, 7, [{'tipo': 'anno', 'testo': '332 a.C.', '_t': .5}, {'tipo': 'freccia', 'da': [22.5, 40.6], 'a': list(ALESS), 'icona': 'galleon', '_t': 1.2},
                    {'tipo': 'etichetta', 'testo': 'ALESSANDRO MAGNO', 'lon': 22.5, 'lat': 39.5, '_t': 1.5}, {'tipo': 'impulso', 'lon': ALESS[0], 'lat': ALESS[1], '_t': 4.5}],
                    traccia=[GIZA, ALESS])
    d = clip_pexels('Alexandria Egypt sea', 8.6, 'd1_d')
    v = unisci([(a, 7), (b, 8), (c, 7), (d, 8.6)], ['zoomin', 'fadeblack', 'zoomin'], os.path.join(LAV, 'd1.mp4'))
    finale(linea(v, [(0, -3100), (6.2, -2560), (13.4, -332), (20.6, -331)]), 1)


# ---------- DEMO 2: mini-mappa nell'angolo
def demo2():
    clips = [clip_pexels('Nile river Egypt', 10, 'd2_a'), clip_pexels('Giza pyramids', 10, 'd2_b'), clip_pexels('Cairo Egypt city', 10, 'd2_c')]
    v = unisci([(c, 10) for c in clips], ['fade', 'fade'], os.path.join(LAV, 'd2_base.mp4'))
    base, pt = VM.fondo(VM.camera(EGITTO), 0.0); mappa = base.convert('RGBA')
    VM.riempi(mappa, base, VM.anelli_visibili(['EGY'], pt), VM.ORO, 1, 10)
    tappe = [(0, (31.3, 30.4), 'IL DELTA'), (9.6, GIZA, 'GIZA'), (19.2, (31.24, 30.04), 'IL CAIRO')]
    cart = os.path.join(LAV, 'mini'); os.makedirs(cart, exist_ok=True)
    tot, fps_m = 28.4, 12
    piccolo = (W - 470, 150, 440, 248)   # x, y, larghezza, altezza del riquadro (sotto la linea del tempo)
    for i in range(int(tot * fps_m) + 1):
        t = i / fps_m
        k = 0.0   # 0 = mini-mappa, 1 = a tutto schermo (tra 11 e 16 s: il momento forte)
        if 11 <= t <= 16:
            k = min(1, (t - 11) / .7, (16 - t) / .7); k = k * k * (3 - 2 * k)
        x0 = piccolo[0] * (1 - k); y0 = piccolo[1] * (1 - k); w_ = piccolo[2] + (W - piccolo[2]) * k; h_ = piccolo[3] + (H - piccolo[3]) * k
        cur = [tp for tp in tappe if tp[0] <= t][-1]
        im = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        m = mappa.copy(); d = ImageDraw.Draw(m)
        x, y = pt(*cur[1]); r_ = 18 + 10 * abs(((t * 1.5) % 2) - 1)
        d.ellipse([x - r_ * 3, y - r_ * 3, x + r_ * 3, y + r_ * 3], outline=(255, 255, 255, 200), width=8)
        d.ellipse([x - 22, y - 22, x + 22, y + 22], fill=(255, 214, 0, 255), outline=(0, 0, 0), width=5)
        VM.etichetta(m, x, y + 90, cur[2], 1, 70 if k > .5 else 90, blocca=True)
        m = m.resize((max(2, int(w_)), max(2, int(h_))), Image.LANCZOS)
        if k < 1:
            mk = Image.new('L', m.size, 0); ImageDraw.Draw(mk).rounded_rectangle([0, 0, m.width - 1, m.height - 1], radius=int(26 * (1 - k)), fill=255)
            bordo = Image.new('RGBA', (m.width + 12, m.height + 12), (0, 0, 0, 0))
            ImageDraw.Draw(bordo).rounded_rectangle([0, 0, bordo.width - 1, bordo.height - 1], radius=int(30 * (1 - k)) + 1, fill=(255, 255, 255, 255))
            im.alpha_composite(bordo, (int(x0) - 6, int(y0) - 6)); m.putalpha(mk)
        im.alpha_composite(m, (int(x0), int(y0)))
        im.save(os.path.join(cart, f'm_{i:05d}.png'))
    out = os.path.join(LAV, 'd2.mp4')
    run(['ffmpeg', '-v', 'error', '-y', '-i', v, '-framerate', fps_m, '-i', os.path.join(cart, 'm_%05d.png'), '-filter_complex', f'[1:v]fps={FPS}[m];[0:v][m]overlay=0:0:shortest=1[o]',
         '-map', '[o]', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-pix_fmt', 'yuv420p', out])
    finale(linea(out, [(0, -5000), (9.6, -2560), (19.2, 2026)]), 2)


# ---------- DEMO 3: mappa palcoscenico con finestre Pexels
def demo3():
    m = scena_mappa('d3_mappa', EGITTO, 30, [{'tipo': 'anno', 'testo': '3100 a.C.', '_t': .5}, {'tipo': 'impulso', 'lon': 31.3, 'lat': 30.4, '_t': 2.0},
                    {'tipo': 'folla', 'personaggio': 'peasant', 'n': 4, 'lon': 32.6, 'lat': 26.0, '_t': 4.0}, {'tipo': 'anno', 'testo': '2560 a.C.', '_t': 10},
                    {'tipo': 'impulso', 'lon': GIZA[0], 'lat': GIZA[1], '_t': 11}, {'tipo': 'anno', 'testo': '2026', '_t': 20},
                    {'tipo': 'impulso', 'lon': 31.24, 'lat': 30.04, '_t': 21}, {'tipo': 'nota', 'testo': 'Una civilta lunga 5.000 anni', '_t': 24}],
                    traccia=[(31.3, 30.4), GIZA, (31.24, 30.04)])
    finestre = [(clip_pexels('Nile river Egypt boat', 8, 'd3_a'), 2.2, 'IL NILO'), (clip_pexels('Giza pyramids', 8, 'd3_b'), 11.2, 'GIZA'),
                (clip_pexels('Cairo Egypt city', 8, 'd3_c'), 21.2, 'IL CAIRO')]
    fw, fh, fx, fy = 720, 405, W - 720 - 80, 200
    mask = Image.new('L', (fw, fh), 0); ImageDraw.Draw(mask).rounded_rectangle([0, 0, fw - 1, fh - 1], radius=28, fill=255); mask.save(os.path.join(LAV, 'mask.png'))
    cornice = Image.new('RGBA', (fw + 16, fh + 70), (0, 0, 0, 0)); dc = ImageDraw.Draw(cornice)
    dc.rounded_rectangle([0, 0, fw + 15, fh + 15], radius=34, fill=(255, 255, 255, 255))
    ins, fil, prec = ['-i', m], [], '0:v'
    for j, (c, t0, nome) in enumerate(finestre):
        cj = cornice.copy(); dj = ImageDraw.Draw(cj); f = VM.font('Anton-Regular.ttf', 44); w_t = dj.textlength(nome, font=f)
        dj.rounded_rectangle([20, fh + 22, 20 + w_t + 40, fh + 68], radius=12, fill=VM.NAVY); dj.text((40, fh + 45), nome, font=f, fill='white', anchor='lm')
        cp = os.path.join(LAV, f'cornice_{j}.png'); cj.save(cp)
        ins += ['-i', c, '-loop', '1', '-i', os.path.join(LAV, 'mask.png'), '-loop', '1', '-i', cp]
        a, b, cc = 1 + j * 3, 2 + j * 3, 3 + j * 3
        fil.append(f'[{a}:v]scale={fw}:{fh},format=rgba,setpts=PTS-STARTPTS+{t0}/TB[c{j}];[{b}:v]format=gray,scale={fw}:{fh}[k{j}];[c{j}][k{j}]alphamerge[w{j}]')
        fil.append(f'[{cc}:v]format=rgba,setpts=PTS-STARTPTS[f{j}]')
        fil.append(f'[{prec}][f{j}]overlay={fx - 8}:{fy - 8}:enable=\'between(t,{t0},{t0 + 7.6})\'[p{j}];[p{j}][w{j}]overlay={fx}:{fy}:eof_action=pass:enable=\'between(t,{t0},{t0 + 7.6})\'[q{j}]')
        prec = f'q{j}'
    out = os.path.join(LAV, 'd3.mp4')
    run(['ffmpeg', '-v', 'error', '-y', *ins, '-filter_complex', ';'.join(fil), '-map', f'[{prec}]', '-t', 30, '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-pix_fmt', 'yuv420p', out])
    finale(linea(out, [(0, -3100), (10, -2560), (20, 2026)]), 3)


for n, fn in ((1, demo1), (2, demo2), (3, demo3)):
    if str(n) in str(P.get('demo') or '123'):
        try:
            fn()
        except Exception as e:
            import traceback; traceback.print_exc(); print('demo', n, 'non riuscita:', str(e)[:300])
