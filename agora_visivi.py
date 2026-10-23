#!/usr/bin/env python3
"""
AGORA OF SAGES - immagini del video in stile "Stoic Journal" (usato da render_filosofo.py quando render_style ha "visivi": "pexels_libreria").

  1) Tempi: le parole della voce (faster-whisper allineato al copione; riserva: tempi stimati).
  2) Frasi per i sottotitoli (una riga al centro) e "inquadrature" da 4-6,5 s che cambiano a fine frase.
  3) Per ogni inquadratura Claude sceglie l'emozione (ambra | notte | tempesta | alba) e la fonte:
       - un'immagine della LIBRERIA AI (libreria_agora/indice.json, creata una volta sola: costo 0 a video), mai due volte nello stesso video
         e il meno possibile tra un video e l'altro (libreria_agora/storico.json);
       - oppure una clip PEXELS con i 4 controlli (ricerche precise, Claude Haiku guarda 3 fotogrammi con regole_immagini,
         stock_exclude_words, niente riprese doppie).
     La statua del filosofo (= copertina) apre il video e torna ogni ~35 s.
  4) Ogni inquadratura: colore per emozione (neri profondi, poca saturazione), lento zoom/panoramica, dissolvenza breve.
  5) Sopra tutto: polvere e cenere che fluttuano + qualche brace, grana da pellicola, vignettatura, logo piccolo in basso a destra.
Se una fonte manca: si prova l'altra; se mancano tutte e due si allunga l'inquadratura precedente (mai un'immagine a caso).
"""
import json, math, os, random, re, shutil, subprocess

import render_kao as RK   # motore Pexels con i controlli, whisper, musica a rotazione, font, Claude

W, H, FPS = 1920, 1080, 30
DISS = 0.4   # secondi di dissolvenza tra due inquadrature
ENC = ['-an', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '19', '-pix_fmt', 'yuv420p', '-r', str(FPS)]
LIB = os.path.join(os.getcwd(), 'libreria_agora')
STORICO = os.path.join(LIB, 'storico.json')

# colore per emozione: neri schiacciati, poca saturazione, dominante calda / fredda / grigia / tenue
GRADO = {
    'ambra': "eq=contrast=1.10:brightness=-0.03:saturation=0.78,colorbalance=rs=0.08:gs=0.02:bs=-0.10:rm=0.07:gm=0.02:bm=-0.08:rh=0.05:bh=-0.07,"
             "curves=all='0/0 0.12/0.04 0.5/0.46 1/0.96'",
    'notte': "eq=contrast=1.10:brightness=-0.06:saturation=0.55,colorbalance=rs=-0.07:gs=0.0:bs=0.12:rm=-0.05:gm=0.02:bm=0.09:rh=-0.03:bh=0.05,"
             "curves=all='0/0 0.14/0.04 0.5/0.43 1/0.93'",
    'tempesta': "eq=contrast=1.16:brightness=-0.04:saturation=0.28,colorbalance=bs=0.04:bm=0.03,curves=all='0/0 0.15/0.05 0.5/0.47 1/0.95'",
    'alba': "eq=contrast=1.05:brightness=-0.02:saturation=0.62,colorbalance=rs=0.02:bs=0.03:rh=0.04:gh=0.02,curves=all='0/0 0.1/0.04 0.5/0.48 1/0.97'",
}


def log(*a):
    print('[agora]', *a, flush=True)


def run(cmd):
    subprocess.run([str(c) for c in cmd], check=True)


# ---------------------------------------------------------------- 1-2) tempi, frasi, inquadrature
def frasi_e_inquadrature(scene, tempi_scene, voce, stile):
    sp = [str(s.get('testo') or '').split() for s in scene]
    parole = [p for ps in sp for p in ps]
    if not parole:
        return [], []
    tw = RK.tempi_parole(voce, parole, [a for a, b in tempi_scene], [b for a, b in tempi_scene], sp)
    totale = tempi_scene[-1][1]
    max_par = int(RK.num(stile.get('parole_riga'), 8))
    max_car = int(RK.num(stile.get('caratteri_riga'), 44))
    # frasi (sottotitoli): fino alla punteggiatura o a ~8 parole, mai a cavallo di due scene
    frasi, k = [], 0
    for ps in sp:
        cur = []
        for p in ps:
            cur.append(k); k += 1
            testo = ' '.join(parole[i] for i in cur)
            if (re.search(r'[.,;:!?…]["»”)]*$', p) and len(cur) >= 2) or len(cur) >= max_par or len(testo) >= max_car:
                frasi.append(cur); cur = []
        if cur:
            if frasi and len(cur) <= 2 and len(' '.join(parole[i] for i in frasi[-1] + cur)) <= max_car + 10 and frasi[-1][-1] == cur[0] - 1:
                frasi[-1] += cur
            else:
                frasi.append(cur)
    righe = []
    for n, f in enumerate(frasi):
        a, b = tw[f[0]][0], tw[f[-1]][1]
        if n + 1 < len(frasi):
            b = min(max(b, tw[frasi[n + 1][0]][0]), b + 0.6)
        testo = ' '.join(parole[i] for i in f)
        righe.append({'a': a, 'b': b, 'testo': testo, 'fine_frase': bool(re.search(r'[.!?…]["»”)]*$', testo))})
    # inquadrature: 4-6,5 s, tagli a fine frase (meglio a fine periodo)
    mn, mx = RK.num(stile.get('secondi_min'), 4.0), RK.num(stile.get('secondi_max'), 6.5)
    inq, inizio, testi = [], 0.0, []
    for n, r in enumerate(righe):
        testi.append(r['testo'])
        fine = righe[n + 1]['a'] if n + 1 < len(righe) else totale
        d = fine - inizio
        if n + 1 == len(righe) or (d >= mn and (r['fine_frase'] or d >= (mn + mx) / 2)) or d >= mx:
            while fine - inizio > mx + 2.5:   # frase lunghissima: due inquadrature sulla stessa frase
                inq.append({'a': inizio, 'b': inizio + (mn + mx) / 2, 'testo': ' '.join(testi)}); inizio += (mn + mx) / 2
            inq.append({'a': inizio, 'b': fine, 'testo': ' '.join(testi)})
            inizio, testi = fine, []
    if inq:
        inq[0]['a'] = 0.0; inq[-1]['b'] = totale
    log(f'{len(righe)} frasi di sottotitolo, {len(inq)} inquadrature (media {totale / max(1, len(inq)):.1f} s)')
    return righe, inq


# ---------------------------------------------------------------- 3) scelta delle immagini
def libreria():
    try:
        ind = json.load(open(os.path.join(LIB, 'indice.json'), encoding='utf-8'))
        return [x for x in ind if os.path.exists(os.path.join(LIB, x['file']))]
    except Exception:
        return []


def piano_claude(inq, titolo, lib, quota):
    """Per ogni inquadratura: emozione, fonte preferita, 3 immagini della libreria adatte, 2 ricerche Pexels."""
    piano = {}
    elenco_lib = '\n'.join(f"{x['file']} | {x['soggetto']} | {x['emozione']} | {x['descrizione'][:110]}" for x in lib)
    for i0 in range(0, len(inq), 40):
        blocco = list(range(i0, min(i0 + 40, len(inq))))
        elenco = '\n'.join(f'{i}. {inq[i]["testo"][:300]}' for i in blocco)
        dom = f"""Video YouTube di filosofia stoica in stile "Stoic Journal": "{titolo}". Immagini scure e cinematografiche dell'antichita'.
Per ogni inquadratura (il testo e' cio' che dice la voce) decidi:
- "emo": il colore emotivo: "ambra" (forza, fuoco, energia, ricordo caldo), "notte" (introspezione, solitudine, mistero, calma profonda), "tempesta" (dolore, lotta, rabbia, difficolta'), "alba" (speranza, rinascita, serenita', inizio);
- "fonte": "libreria" (immagini AI: statue, figure, simboli: ideali per concetti interiori e astratti) oppure "pexels" (clip reali: natura, mare, cieli, rovine vere, candele, mani, luoghi). Circa il {int(quota * 100)}% "libreria", il resto "pexels"; alterna, mai 3 uguali di fila;
- "lib": i 3 file della LIBRERIA piu' adatti per significato ed emozione (dalla lista sotto), anche se la fonte e' pexels (servono di riserva);
- "q": 2 ricerche Pexels in INGLESE (2-5 parole), concrete e visive, coerenti con l'antichita' e con la frase (es. "stormy sea waves rocks", "ancient marble statue close up", "candle flame dark", "greek temple ruins sunset"). Mai citta' moderne, uffici, telefoni, persone moderne.
LIBRERIA (file | soggetto | emozione | descrizione):
{elenco_lib}
INQUADRATURE:
{elenco}
Rispondi SOLO JSON: [{{"n": 0, "emo": "...", "fonte": "...", "lib": ["...", "...", "..."], "q": ["...", "..."]}}, ...]"""
        try:
            t = RK.claude([{'type': 'text', 'text': dom}], RK.MODELLO_AI, 8000)
            for x in json.loads(t[t.find('['): t.rfind(']') + 1]):
                piano[int(x['n'])] = x
        except Exception as e:
            log('piano Claude non riuscito per un blocco:', str(e)[:150])
    return piano


def scegli(inq, statue, titolo, stile, seme):
    """Assegna a ogni inquadratura: ('img', path) | ('clip', url) | ('continua', None), con l'emozione."""
    rnd = random.Random(seme)
    lib = libreria()
    quota = RK.num(stile.get('quota_libreria'), 0.45)
    storico = []
    try:
        storico = json.load(open(STORICO))
    except Exception:
        pass
    usate = set()
    piano = {} if RK.OFFLINE or not os.environ.get('ANTHROPIC_API_KEY') else piano_claude(inq, titolo, lib, quota)
    ogni = RK.num(stile.get('statua_ogni'), 35.0)
    ultima_statua, k_statua = -999.0, 0
    out = []
    for i, s in enumerate(inq):
        p = piano.get(i) or {}
        emo = p.get('emo') if p.get('emo') in GRADO else ['ambra', 'notte', 'tempesta', 'alba'][i % 4]
        if statue and (i == 0 or s['a'] - ultima_statua >= ogni):
            out.append({'tipo': 'img', 'src': statue[k_statua % len(statue)], 'emo': 'ambra' if i == 0 else emo, 'statua': True})
            ultima_statua, k_statua = s['a'], k_statua + 1
            continue
        fonte = p.get('fonte') or ('libreria' if rnd.random() < quota else 'pexels')
        cand_lib = [f for f in (p.get('lib') or []) if f in {x['file'] for x in lib}]
        cand_lib += [x['file'] for x in lib if x['emozione'] == emo]   # riserva: stessa emozione
        cand_lib = [f for f in dict.fromkeys(cand_lib) if f not in usate]
        cand_lib.sort(key=lambda f: (f in storico[-40:], (p.get('lib') or []).index(f) if f in (p.get('lib') or []) else 9))

        def da_lib():
            if cand_lib:
                f = cand_lib[0]; usate.add(f)
                return {'tipo': 'img', 'src': os.path.join(LIB, f), 'emo': emo, 'file': f}
            return None

        def da_pexels():
            if RK.OFFLINE:
                prove = [x for x in os.environ.get('TEST_CLIPS', '').split(',') if x]
                return {'tipo': 'clip', 'src': prove[i % len(prove)], 'emo': emo} if prove else None
            qs = [q for q in (p.get('q') or []) if str(q).strip()] or ([' '.join(re.findall(r'[A-Za-z]{5,}', s['testo'])[:3]) + ' ancient'])
            m = RK.scegli_media(qs, s['testo'], 1, 'video')
            return {'tipo': 'clip', 'src': m[0]['url'], 'emo': emo, 'foto': m[0].get('tipo') == 'foto'} if m else None

        x = (da_lib() or da_pexels()) if fonte == 'libreria' else (da_pexels() or da_lib())
        out.append(x or {'tipo': 'continua', 'emo': emo})
    n_lib = sum(1 for x in out if x.get('file')); n_clip = sum(1 for x in out if x['tipo'] == 'clip')
    log(f"immagini: {k_statua} statua, {n_lib} libreria AI, {n_clip} Pexels, {sum(1 for x in out if x['tipo'] == 'continua')} allungate")
    try:   # storico tra un video e l'altro: le immagini appena usate passano in fondo alla fila la prossima volta
        json.dump((storico + [x['file'] for x in out if x.get('file')])[-120:], open(STORICO, 'w'))
    except Exception:
        pass
    return out


# ---------------------------------------------------------------- 4) pezzi di video
def pezzo(x, nf, k, out, cartella, scaricati):
    grado = GRADO.get(x.get('emo'), GRADO['ambra'])
    z0, z1 = (1.0, 1.10) if k % 3 != 1 else (1.10, 1.0)    # zoom avanti (o indietro, ogni tanto)
    px = [0.5, 0.42, 0.58][k % 3]                           # piccolo spostamento laterale
    f_z = f"({z0}+({z1 - z0})*if(isnan(n),0,n)/{max(1, nf)})"
    muovi = (f"scale=w='2*trunc({W // 2}*{f_z}+1)':h='2*trunc({H // 2}*{f_z}+1)':eval=frame,crop={W}:{H}:'(iw-{W})*{px}':'(ih-{H})*0.5'")
    if x['tipo'] == 'img' or x.get('foto'):
        src = x['src']
        if src.startswith('http'):
            if src not in scaricati:
                scaricati[src] = RK.scarica(src, os.path.join(cartella, f'm_{len(scaricati):04d}.jpg'))
            src = scaricati[src]
        vf = f"scale={int(W * 1.12)}:{int(H * 1.12)}:force_original_aspect_ratio=increase,crop={int(W * 1.12)}:{int(H * 1.12)},{muovi},{grado},setsar=1,format=yuv420p"
        run(['ffmpeg', '-y', '-v', 'error', '-loop', '1', '-framerate', str(FPS), '-i', src, '-frames:v', str(nf), '-vf', vf] + ENC + [out])
    else:
        src = x['src']
        if src.startswith('http'):
            if src not in scaricati:
                scaricati[src] = RK.scarica(src, os.path.join(cartella, f'm_{len(scaricati):04d}.mp4'))
            src = scaricati[src]
        try:
            dur = RK.durata(src)
        except Exception:
            dur = 0
        ss = max(0.0, min(dur - nf / FPS - 0.2, dur * 0.2)) if dur > nf / FPS + 1 else 0.0
        vf = (f"fps={FPS},scale={int(W * 1.12)}:{int(H * 1.12)}:force_original_aspect_ratio=increase,crop={int(W * 1.12)}:{int(H * 1.12)},"
              f"{muovi},{grado},setsar=1,format=yuv420p")
        run(['ffmpeg', '-y', '-v', 'error', '-ss', f'{ss:.2f}', '-stream_loop', '-1', '-i', src, '-frames:v', str(nf), '-vf', vf] + ENC + [out])
    return out


def particelle(cartella, secondi=12):
    """Due livelli in loop: polvere/cenere scura che fluttua (si moltiplica sull'immagine) e braci + pulviscolo chiaro (si somma)."""
    from PIL import Image, ImageDraw, ImageFilter
    rnd = random.Random(11)
    nf, w2, h2 = int(secondi * FPS), W // 2, H // 2
    scure = [{'x': rnd.uniform(0, W), 'y0': rnd.uniform(0, H), 'v': rnd.uniform(-18, 22), 'dx': rnd.uniform(-20, 20), 'r': rnd.uniform(1.2, 4.0),
              'f': rnd.uniform(0.2, 0.9), 'fase': rnd.uniform(0, 6.28), 'forma': rnd.random()} for _ in range(70)]
    chiare = [{'x': rnd.uniform(0, W), 'y0': rnd.uniform(0, H), 'v': rnd.uniform(20, 70), 'dx': rnd.uniform(-12, 12), 'r': rnd.uniform(1.5, 4.5),
               'f': rnd.uniform(0.3, 1.2), 'fase': rnd.uniform(0, 6.28), 'brace': rnd.random() < 0.25} for _ in range(45)]
    out = {}
    for nome, fondo in (('polvere', (255, 255, 255)), ('braci', (0, 0, 0))):
        p = os.path.join(cartella, nome + '.mp4')
        proc = subprocess.Popen(['ffmpeg', '-y', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{w2}x{h2}', '-r', str(FPS), '-i', '-',
                                 '-vf', f'scale={W}:{H}', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p', p], stdin=subprocess.PIPE)
        for i in range(nf):
            t = i / FPS
            im = Image.new('RGB', (w2, h2), fondo); d = ImageDraw.Draw(im)
            if nome == 'polvere':
                for q in scure:   # cenere scura: deriva lenta, a volte sale a volte scende, forme irregolari
                    y = (q['y0'] - q['v'] * t) % (H + 40) - 20
                    x = (q['x'] + q['dx'] * t + 18 * math.sin(q['f'] * t + q['fase'])) % W
                    r = q['r'] / 2; g = 40 + int(60 * q['forma'])
                    if q['forma'] < 0.5:
                        d.ellipse([x / 2 - r, y / 2 - r, x / 2 + r, y / 2 + r], fill=(g, g, g))
                    else:
                        d.polygon([(x / 2 - r, y / 2), (x / 2, y / 2 - r * 1.4), (x / 2 + r * 1.2, y / 2 + r * 0.3), (x / 2 - r * 0.3, y / 2 + r)], fill=(g, g, g))
                im = im.filter(ImageFilter.GaussianBlur(0.6))
            else:
                for q in chiare:   # braci arancioni e pulviscolo chiaro che salgono
                    y = (q['y0'] - q['v'] * t) % (H + 40) - 20
                    x = (q['x'] + q['dx'] * t + 10 * math.sin(q['f'] * t + q['fase'])) % W
                    luce = 0.5 + 0.5 * math.sin(2.1 * t + q['fase'])
                    col = (int(255 * luce), int(125 * luce), int(35 * luce)) if q['brace'] else (int(110 * luce),) * 3
                    r = q['r'] / 2
                    d.ellipse([x / 2 - r, y / 2 - r, x / 2 + r, y / 2 + r], fill=col)
                im = im.filter(ImageFilter.GaussianBlur(0.9))
            proc.stdin.write(im.tobytes())
        proc.stdin.close(); proc.wait()
        out[nome] = p
    return out


def logo_png(url, cartella):
    if not str(url or '').strip():
        return None
    try:
        p = RK.scarica(str(url).strip(), os.path.join(cartella, 'logo_src'), 500)
        from PIL import Image
        im = Image.open(p).convert('RGBA'); im.thumbnail((120, 120))
        a = im.split()[3].point(lambda v: int(v * 0.85)); im.putalpha(a)
        dest = os.path.join(cartella, 'logo.png'); im.save(dest)
        return dest
    except Exception as e:
        log('logo non disponibile:', str(e)[:100]); return None


def firma_png(stile, cartella):
    """Firma del canale (render_style: "firma": "meandro", "firma_colore", "firma_testo"): greca d'oro + marchio in lettere romane."""
    if str(stile.get('firma') or '').strip().lower() != 'meandro':
        return None
    from PIL import Image, ImageDraw, ImageFont
    col = str(stile.get('firma_colore') or '#D9AE4F').strip().lstrip('#')
    rgb = tuple(int(col[i:i + 2], 16) for i in (0, 2, 4)) if len(col) == 6 else (217, 174, 79)
    def greca(w, h=30):
        im = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im); s_ = h / 30
        modulo = [(2, 28), (2, 2), (28, 2), (28, 23), (9, 23), (9, 9), (21, 9), (21, 16), (15, 16)]
        for x0 in range(0, w - int(28 * s_) + 1, int(30 * s_)):
            d.line([(x0 + x * s_, y * s_) for x, y in modulo], fill=rgb + (255,), width=max(2, round(3 * s_)), joint='curve')
        return im
    out = {'greca': os.path.join(cartella, 'firma_greca.png'), 'marchio': None}
    greca(int(RK.num(stile.get('firma_larghezza'), 600))).save(out['greca'])
    testo = str(stile.get('firma_testo') or '').strip().upper()
    if testo:
        try:
            f = ImageFont.truetype(RK.font(stile.get('firma_font') or 'Cinzel'), int(RK.num(stile.get('firma_dimensione'), 34)))
        except Exception:
            f = ImageFont.truetype(RK.font('Anton'), int(RK.num(stile.get('firma_dimensione'), 34)))
        sp = 10
        larg = sum(f.getbbox(c)[2] - f.getbbox(c)[0] if c != ' ' else 14 for c in testo) + sp * (len(testo) - 1) + 20
        im = Image.new('RGBA', (larg, 70), (0, 0, 0, 0)); d = ImageDraw.Draw(im); x = 10
        for c in testo:
            if c == ' ':
                x += 14 + sp; continue
            d.text((x, 35), c, font=f, fill=rgb + (255,), anchor='lm', stroke_width=1, stroke_fill=(0, 0, 0, 160))
            x += f.getbbox(c)[2] - f.getbbox(c)[0] + sp
        out['marchio'] = os.path.join(cartella, 'firma_marchio.png'); im.save(out['marchio'])
    return out


def aggiungi_firma(ins, filtro, stile, cartella, righe, tot, cfg=None):
    """FIRMA DEL CANALE (render_style "firma"): marchio + greca d'oro in apertura e chiusura, greca sotto le domande al pubblico.
    Riceve il grafo che finisce in [vl] e lo chiude in [v]."""
    fi = firma_png(stile, cartella)
    if not fi:
        return filtro + ';[vl]null[v]'
    st = {'n': sum(1 for x in ins if x == '-i'), 'cur': 'vl'}
    y_txt = int(H * RK.num(stile.get('y_testo'), 0.50))
    y_top = int(H * RK.num(stile.get('firma_y'), 0.16))
    def strato(png, t0, t1, y, nome, dissolvi=True):
        ins.extend(['-loop', '1', '-t', f'{tot:.3f}', '-i', png])
        if isinstance(t0, list):
            fx, en = '', '+'.join(f'between(t,{a:.2f},{b:.2f})' for a, b in t0)
        else:
            fx = (f",fade=t=in:st={t0 + .2:.2f}:d=0.7:alpha=1,fade=t=out:st={max(t0, t1 - .8):.2f}:d=0.7:alpha=1" if dissolvi else '')
            en = f'between(t,{t0:.2f},{t1:.2f})'
        g = f";[{st['n']}:v]format=rgba{fx}[{nome}];[{st['cur']}][{nome}]overlay=x=(W-w)/2:y={y}:enable='{en}'[{nome}o]"
        st['n'] += 1; st['cur'] = nome + 'o'
        return g
    blocchi = [(0.0, min(4.5, tot / 3), 'ia')] + ([(tot - 5.0, tot, 'fz')] if tot > 30 else [])
    for t0, t1, nome in blocchi:
        if fi['marchio']:
            filtro += strato(fi['marchio'], t0, t1, y_top, nome + 'm')
        filtro += strato(fi['greca'], t0 + .2, t1, y_top + 64, nome + 'g')
    # greca sotto le domande ai commenti: ESATTAMENTE quante dice la colonna domande_commenti (vuota o 0 = nessuna)
    try:
        nd = int(float(str((cfg or {}).get('domande_commenti') or 0).replace(',', '.')))
    except ValueError:
        nd = 0
    cand = [r for r in righe if str(r['testo']).strip().endswith('?') and r['a'] > 5]
    parole = ('comment', 'below', 'tell me', 'let me know', 'write', 'share', 'commenti', 'scrivi', 'dimmi', 'sotto')
    dom = []
    for k in range(1, nd + 1):   # la domanda piu' vicina al punto in cui il copione la mette (k/(n+1) del video), preferendo quelle che invitano a commentare
        atteso = tot * k / (nd + 1)
        liberi = [r for r in cand if r not in dom]
        if not liberi:
            break
        dom.append(min(liberi, key=lambda r: (not any(w in str(r['testo']).lower() for w in parole), abs(r['a'] - atteso))))
    dom = sorted((r['a'], r['b']) for r in dom)
    if dom:
        filtro += strato(fi['greca'], dom, None, y_txt + int(RK.num(stile.get('dimensione_testo'), 60) * .9), 'dq', False)
    log(f"firma del canale: marchio + greca in apertura/chiusura, greca sotto {len(dom)} domande")
    return filtro + f";[{st['cur']}]null[v]"


def sfondo_stoico(scene, tempi_scene, voce, statue, titolo, cfg, stile, cartella, seme):
    """Video di sfondo completo (senza scritte) + le frasi per i sottotitoli."""
    if not os.environ.get('LINGUA'):   # lingua della voce per whisper, dalla colonna language
        lg = str(cfg.get('language') or 'en').strip().lower()
        os.environ['LINGUA'] = {'english': 'en', 'italiano': 'it', 'italian': 'it', 'espanol': 'es', 'español': 'es', 'spanish': 'es',
                                'deutsch': 'de', 'german': 'de', 'francais': 'fr', 'français': 'fr', 'french': 'fr',
                                'portugues': 'pt', 'português': 'pt', 'portuguese': 'pt'}.get(lg, lg[:2] or 'en')
    righe, inq = frasi_e_inquadrature(scene, tempi_scene, voce, stile)
    if not inq:
        raise RuntimeError('nessuna inquadratura')
    RK.Regole.testo = str(cfg.get('regole_immagini') or stile.get('regole_immagini') or
                          'Antichita\' classica e atmosfera filosofica: statue di marmo, rovine greche e romane, templi, colonne, biblioteche antiche, '
                          'candele, pergamene, mare in tempesta, montagne, nebbia, cieli drammatici. Mai citta\' moderne, auto, telefoni, uffici, '
                          'persone moderne, persone in posa o sorridenti in camera.')
    RK.Regole.escludi = [w.strip().lower() for w in str(cfg.get('stock_exclude_words') or '').split(',') if w.strip()]
    RK.Regole.suffisso = str(cfg.get('stock_query_suffix') or '').strip()
    RK.Regole.pubblico = str(cfg.get('language') or 'en')
    scelte = scegli(inq, statue, titolo, stile, seme)
    # durate a fotogrammi esatti sulla voce; dissolvenza: ogni pezzo (tranne l'ultimo del suo gruppo) dura DISS in piu'
    gruppo = 15
    nd = int(round(DISS * FPS))
    pezzi, scaricati, prev = [], {}, None
    for k, (s, x) in enumerate(zip(inq, scelte)):
        nf = int(round(s['b'] * FPS)) - int(round(s['a'] * FPS))
        ultimo = (k % gruppo == gruppo - 1) or k == len(inq) - 1
        nf_tot = nf + (0 if ultimo else nd)
        out = os.path.join(cartella, f'inq_{k:04d}.mp4')
        if x['tipo'] == 'continua' and prev:
            x = dict(prev, emo=prev.get('emo'))   # stessa immagine/clip di prima, movimento diverso
        try:
            if x['tipo'] == 'continua':
                raise RuntimeError('nessuna immagine')
            pezzo(x, nf_tot, k, out, cartella, scaricati); prev = x
        except Exception as e:
            log(f'inquadratura {k}: {str(e)[:100]}, uso la statua')
            pezzo({'tipo': 'img', 'src': statue[0], 'emo': x.get('emo')}, nf_tot, k, out, cartella, scaricati)
        pezzi.append((out, nf_tot, ultimo))
    # dissolvenze per gruppi (grafi piccoli), gruppi uniti con taglio netto
    gruppi_f = []
    for g0 in range(0, len(pezzi), gruppo):
        g = pezzi[g0:g0 + gruppo]
        out = os.path.join(cartella, f'gruppo_{g0 // gruppo:03d}.mp4')
        if len(g) == 1:
            shutil.copy(g[0][0], out)
        else:
            ins = sum((['-i', p[0]] for p in g), [])
            fl, prev_l, acc = [], '[0:v]', g[0][1] / FPS
            for j in range(1, len(g)):
                o = f'[x{j}]' if j < len(g) - 1 else '[v]'
                fl.append(f"{prev_l}[{j}:v]xfade=transition=fade:duration={DISS}:offset={acc - DISS:.4f}{o}")
                prev_l, acc = o, acc + g[j][1] / FPS - DISS
            run(['ffmpeg', '-y', '-v', 'error'] + ins + ['-filter_complex', ';'.join(fl), '-map', '[v]'] + ENC + [out])
        gruppi_f.append(out)
    lista = os.path.join(cartella, 'gruppi.txt')
    open(lista, 'w').write(''.join(f"file '{os.path.abspath(x)}'\n" for x in gruppi_f))
    base = os.path.join(cartella, 'base_stoica.mp4')
    run(['ffmpeg', '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', lista, '-c', 'copy', base])
    # effetti globali: cenere scura (moltiplica) + braci (somma) + grana + vignettatura + logo
    fx = particelle(cartella)
    logo = logo_png(cfg.get('thumbnail_watermark_url') or stile.get('logo'), cartella)
    grana = int(RK.num(stile.get('grana'), 4))
    filtro = (f"[0:v]format=gbrp[b];[1:v]format=gbrp[p];[b][p]blend=all_mode=multiply:shortest=1[b2];"
              f"[2:v]format=gbrp[c];[b2][c]blend=all_mode=screen:shortest=1,format=yuv420p,"
              f"noise=alls={grana}:allf=t,vignette=angle=PI/4.6[v0]")
    ins = ['-i', base, '-stream_loop', '-1', '-i', fx['polvere'], '-stream_loop', '-1', '-i', fx['braci']]
    if logo:
        ins += ['-i', logo]
        filtro += f";[v0][3:v]overlay=x=W-w-36:y=H-h-30[vl]"
    else:
        filtro = filtro.replace('[v0]', '[vl]')
    filtro = aggiungi_firma(ins, filtro, stile, cartella, righe, tempi_scene[-1][1], cfg)
    out = os.path.join(cartella, 'sfondo_stoico.mp4')
    run(['ffmpeg', '-y', '-v', 'error'] + ins + ['-filter_complex', filtro, '-map', '[v]', '-t', f'{tempi_scene[-1][1]:.3f}'] + ENC + [out])
    log('sfondo stoico pronto: colore per emozione, cenere, braci, grana, vignettatura' + (', logo' if logo else ''))
    return out, righe


# ---------------------------------------------------------------- sottotitoli: una frase alla volta, al centro
def sottotitoli_frasi(righe, stile, cartella):
    ttf = RK.font(stile.get('font') or 'Archivo Black')
    fam = RK.nome_font_ttf(ttf)
    size = int(RK.num(stile.get('dimensione_testo'), 60))
    y = int(H * RK.num(stile.get('y_testo'), 0.50))
    bordo = RK.num(stile.get('bordo_testo'), 3)
    minuscolo = str(stile.get('maiuscolo') or 'NO').upper() != 'SI'
    head = ['[Script Info]', 'ScriptType: v4.00+', f'PlayResX: {W}', f'PlayResY: {H}', 'WrapStyle: 0', '',
            '[V4+ Styles]',
            'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding',
            f'Style: F,{fam},{size},&H00FFFFFF,&H00FFFFFF,&H00101010,&H96000000,0,0,0,0,100,100,0,0,1,{bordo:g},2,5,260,260,0,1', '',
            '[Events]', 'Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text']
    for r in righe:
        t = r['testo'].replace('{', '(').replace('}', ')')
        t = re.sub(r'[.,;:]+$', '', t.strip())
        if minuscolo:
            t = t.lower()
        head.append(f"Dialogue: 0,{RK.tempo_ass(r['a'])},{RK.tempo_ass(r['b'])},F,,0,0,0,,{{\\pos({W // 2},{y})\\fad(120,120)}}{t}")
    p = os.path.join(cartella, 'frasi.ass')
    open(p, 'w', encoding='utf-8').write('\n'.join(head) + '\n')
    log(f'sottotitoli: {len(righe)} frasi al centro, font {fam} {size}px' + (', minuscolo' if minuscolo else ''))
    return p
