#!/usr/bin/env python3
"""
MULTICHANNEL - Montaggio "KAO" su GitHub (sostituisce json2video per i canali con render_engine = github e render_workflow = kao_render.yml).

Cosa fa (stesso aspetto del template json2video di KAO, ma con le clip scelte qui con i controlli di Storia in Minuti):
  1) voce: gli audio delle scene (ElevenLabs, gia' fatti da n8n) in fila, durata vera di ogni scena;
  2) immagini: 100% Pexels. Per ogni scena Claude scrive ricerche precise (cosa dice la frase + luogo/pubblico del canale),
     Claude Haiku guarda 3 fotogrammi di ogni clip e scarta quelle fuori regola (colonna regole_immagini + stock_exclude_words),
     niente riprese doppie (stesso autore con titolo simile o stessi colori negli stessi punti). Una clip nuova ogni
     stock_clip_duration secondi (4 s). Se manca una clip giusta: si continua la clip precedente, mai un'immagine a caso;
  3) scene tipografiche (se il copione ne ha): texture del canale + scritta grande; grafici "numero"/"quota" semplici;
  4) sottotitoli come json2video "classic": Archivo Black 105 px, max 3 parole per riga, parola detta in giallo (#F2B33D),
     resto bianco, contorno nero 8, ombra 4. Tempi parola per parola con faster-whisper (riserva: tempi stimati);
  5) musica a rotazione: si parte da un brano a caso della lista, poi seguono gli altri, volume 0.03 (dal foglio);
  6) suono di transizione tra le scene (se c'e'), invito iscrizione (immagine + clic + campana).
Riceve da n8n (variabile PAYLOAD): {"id", "dati_url", "resume_url"}. Alla fine carica il video su Fal e chiama resume_url con
{"movie": {"status": "done", "url", "duration"}} (oppure {"status": "failed", "message"}).
"""
import base64, difflib, io, json, math, os, random, re, shutil, subprocess, sys, threading, time, traceback
import urllib.error, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
import effetti_j2v as EF   # effetti di json2video (grafici, cornici, cifre, suoni) disegnati con Chromium

E = os.environ.get
LAVORO = os.path.join(os.getcwd(), 'lavoro_kao')
FONT_DIR = os.path.join(os.getcwd(), 'font')
W, H, FPS = 1920, 1080, 30
ENC = ['-an', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '17', '-pix_fmt', 'yuv420p', '-r', str(FPS)]
MODELLO_AI = E('MODELLO_AI', '') or 'claude-sonnet-5-5'
MODELLO_CONTROLLO = E('MODELLO_CONTROLLO', '') or 'claude-haiku-4-5-20251001'
OFFLINE = E('OFFLINE', '') == '1'   # prova senza rete (media locali, niente Pexels/Claude/Fal)
FONT_URL = {
    'Archivo Black': 'https://github.com/google/fonts/raw/main/ofl/archivoblack/ArchivoBlack-Regular.ttf',
    'Anton': 'https://github.com/google/fonts/raw/main/ofl/anton/Anton-Regular.ttf',
    'Montserrat': 'https://github.com/google/fonts/raw/main/ofl/montserrat/Montserrat%5Bwght%5D.ttf',
    'Luckiest Guy': 'https://github.com/google/fonts/raw/main/apache/luckiestguy/LuckiestGuy-Regular.ttf',
}


def log(*a):
    print('[kao]', *a, flush=True)


def run(cmd):
    subprocess.run([str(c) for c in cmd], check=True)


def durata(p):
    out = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', p],
                         check=True, capture_output=True, text=True).stdout.strip()
    return float(out)


def http(url, dati=None, headers=None, raw=False, metodo=None, timeout=120):
    h = {'Content-Type': 'application/json'} if isinstance(dati, (dict, list)) else {}
    h.update(headers or {})
    body = json.dumps(dati).encode() if isinstance(dati, (dict, list)) else dati
    req = urllib.request.Request(url, data=body, headers=dict({'User-Agent': 'Mozilla/5.0'}, **h), method=metodo)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        b = r.read()
        return b if raw else json.loads(b.decode() or '{}')


def url_drive(u):
    u = str(u or '').strip()
    if u.startswith('https://drive.google.com/uc?') and 'confirm=' not in u:
        u = u.replace('https://drive.google.com/uc?', 'https://drive.usercontent.google.com/download?') + '&confirm=t'
    return u


def scarica(url, path, minimo=2000):
    if OFFLINE and os.path.exists(str(url)):
        shutil.copy(url, path); return path
    url = url_drive(url)
    for k in range(4):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=180) as r, open(path, 'wb') as f:
                shutil.copyfileobj(r, f, 1 << 20)
            if os.path.getsize(path) >= minimo:
                return path
            raise RuntimeError('file troppo piccolo')
        except Exception as e:
            log('download fallito (' + str(e)[:100] + '), riprovo'); time.sleep(4 * (k + 1))
    raise RuntimeError('impossibile scaricare ' + str(url)[:120])


def claude(cont, modello=None, max_tokens=4000, timeout=300):
    r = http('https://api.anthropic.com/v1/messages', {'model': modello or MODELLO_AI, 'max_tokens': max_tokens,
             'messages': [{'role': 'user', 'content': cont}]},
             {'x-api-key': E('ANTHROPIC_API_KEY', ''), 'anthropic-version': '2023-06-01'}, timeout=timeout)
    return ''.join(b.get('text', '') for b in r.get('content', []))


def num(v, d):
    try:
        s = str(v if v is not None else '').strip().replace(',', '.').replace('%', '')
        return float(s) if s else d
    except ValueError:
        return d


def font(nome):
    """Il file .ttf del font (scaricato da Google Fonts una volta sola)."""
    os.makedirs(FONT_DIR, exist_ok=True)
    nome = str(nome or 'Archivo Black').strip()
    if OFFLINE:
        return '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
    if nome.startswith('http'):
        p = os.path.join(FONT_DIR, 'custom_' + re.sub(r'[^\w]', '', nome)[-30:] + '.ttf')
        if not os.path.exists(p):
            try:
                scarica(nome, p, 10000)
            except Exception as e:
                log('font non scaricato:', str(e)[:80]); return font('Anton')
        return p
    base = nome.split(',')[0].strip().strip("'\"")
    p = os.path.join(FONT_DIR, base.replace(' ', '') + '.ttf')
    if not os.path.exists(p):
        u = FONT_URL.get(base)
        try:
            if not u:
                raise RuntimeError('font sconosciuto')
            scarica(u, p, 10000)
        except Exception as e:
            log(f'font {base} non disponibile ({str(e)[:60]}), uso DejaVu')
            return '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
    return p


def nome_font_ttf(path):
    """Nome di famiglia dentro il .ttf (serve ad ASS)."""
    try:
        from PIL import ImageFont
        return ImageFont.truetype(path, 20).getname()[0]
    except Exception:
        return 'DejaVu Sans'


# ============================================================ PEXELS con i 4 controlli (come Storia in Minuti)
_lock = threading.RLock()
_cache, _usati, _scelte, _impronte = {}, set(), [], {}
_conti = {'pexels': 0}
PEXELS_MAX = int(num(E('PEXELS_MAX', ''), 180))


class Regole:
    testo = ''        # regole_immagini del canale (testo libero)
    escludi = []      # stock_exclude_words
    suffisso = ''     # stock_query_suffix
    pubblico = ''     # lingua/pubblico del canale


def pexels_cerca(tipo, q):
    k = (tipo, q.lower().strip())
    with _lock:
        if k in _cache:
            return _cache[k]
        if _conti['pexels'] >= PEXELS_MAX:
            log('tetto ricerche Pexels raggiunto'); return []
        _conti['pexels'] += 1
    chiave = E('PEXELS_API_KEY', '')
    ris = []
    if chiave:
        base = 'https://api.pexels.com/videos/search' if tipo == 'video' else 'https://api.pexels.com/v1/search'
        for tent in range(3):
            try:
                j = http(base + '?' + urllib.parse.urlencode({'query': q, 'per_page': 40, 'orientation': 'landscape'}), headers={'Authorization': chiave})
                if tipo == 'video':
                    for v in j.get('videos', []):
                        fs = [f for f in v.get('video_files', []) if 'mp4' in (f.get('file_type') or '') and 0 < (f.get('height') or 0) <= 1440]
                        fs.sort(key=lambda f: -(f.get('height') or 0))
                        if fs and (v.get('duration') or 0) >= 3:
                            pics = [x.get('picture') for x in (v.get('video_pictures') or []) if x.get('picture')]
                            viste = [pics[int(i * (len(pics) - 1) / 2)] for i in range(3)] if len(pics) > 2 else [v.get('image') or ''] + pics
                            ris.append({'tipo': 'video', 'url': fs[0]['link'], 'anteprima': v.get('image') or '', 'viste': [x for x in viste if x][:3],
                                        'desc': (v.get('url') or '').lower(), 'autore': str((v.get('user') or {}).get('id') or ''),
                                        'durata': float(v.get('duration') or 0)})
                else:
                    for ph in j.get('photos', []):
                        ris.append({'tipo': 'foto', 'url': ph['src'].get('large2x') or ph['src'].get('original'), 'anteprima': ph['src'].get('medium') or '',
                                    'viste': [ph['src'].get('medium') or ''], 'desc': ((ph.get('alt') or '') + ' ' + (ph.get('url') or '')).lower(),
                                    'autore': str(ph.get('photographer_id') or ''), 'durata': 0})
                break
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    log('Pexels: troppe richieste, aspetto 60 s'); time.sleep(60); continue
                log('Pexels:', q, e.code); break
            except Exception as e:
                log('Pexels:', q, str(e)[:120]); time.sleep(3)
    # luoghi/parole escluse dal canale (stock_exclude_words): nel titolo o nel link della clip
    ris = [r for r in ris if r['url'] and not any(re.search(r'(^|[^a-z])' + re.escape(w) + r'([^a-z]|$)', r['desc'].replace('-', ' ')) for w in Regole.escludi)]
    with _lock:
        _cache[k] = ris
    return ris


def impronta(u):
    """Colori 4x4 dell'anteprima: due riprese dello stesso posto hanno gli stessi colori negli stessi punti."""
    if not u:
        return None
    if u in _impronte:
        return _impronte[u]
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(http(u, raw=True, timeout=30))).convert('RGB').resize((4, 4), Image.BOX)
        h = [x for px in im.getdata() for x in px]
    except Exception:
        h = None
    _impronte[u] = h
    return h


def parole_titolo(c):
    d = re.sub(r'https?://[^/]+/(video|photo)/', '', c.get('desc', '')).replace('-', ' ')
    return {w for w in re.findall(r'[a-z]{4,}', d) if w not in ('view', 'aerial', 'drone', 'footage', 'shot', 'video', 'photo', 'free', 'stock', 'person', 'people')}


def stessa_ripresa(c):
    h = impronta(c.get('anteprima'))
    pt = parole_titolo(c)
    for autore, pu, hu in _scelte:
        if autore and autore == c.get('autore') and pt and pu and len(pt & pu) / max(1, min(len(pt), len(pu))) >= 0.5:
            return True
        if h and hu and sum(abs(x - y) for x, y in zip(h, hu)) / len(h) <= 14:
            return True
    return False


def b64_img(u):
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(http(u, raw=True, timeout=30))).convert('RGB'); im.thumbnail((384, 384))
        buf = io.BytesIO(); im.save(buf, 'JPEG', quality=80)
        return {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': base64.b64encode(buf.getvalue()).decode()}}
    except Exception:
        return None


def controlla(cand, q, frase, quante):
    """Claude Haiku guarda 3 fotogrammi di ogni clip e restituisce, in ordine di preferenza, quelle adatte (max `quante`)."""
    if not E('ANTHROPIC_API_KEY', '') or not cand:
        return []
    cont, validi = [], 0
    for i, c in enumerate(cand):
        with ThreadPoolExecutor(3) as ex:
            imgs = [x for x in ex.map(b64_img, (c.get('viste') or [c.get('anteprima')])[:3]) if x]
        if imgs:
            validi += 1
        cont += [{'type': 'text', 'text': f'Clip {i}:' + ('' if imgs else ' (anteprima non disponibile: SCARTALA)')}] + imgs
    if not validi:
        return []
    cont.append({'type': 'text', 'text': f"""Video YouTube per un pubblico {Regole.pubblico or 'italiano'}. In questo momento la voce dice: "{frase[:500]}". Ricerca usata: "{q}".
Quali clip mostrano DAVVERO cio' che dice la voce, in modo coerente? Ogni clip ha piu' fotogrammi: giudicali TUTTI, basta un fotogramma sbagliato per scartarla.
REGOLE DEL CANALE (prevalgono): {Regole.testo or 'persone e ambienti in cui il pubblico si riconosce; niente fuori tema'}
SCARTA SEMPRE: scritte, loghi o marchi leggibili, watermark, schermate, contenuti fuori tema, scene che contraddicono la frase (es. la voce parla di tristezza e la clip e' una festa), luoghi o persone chiaramente di un altro paese/cultura se le regole lo chiedono, contenuti violenti o espliciti.
Ragiona in breve (max 3 righe) e chiudi con una riga ESATTAMENTE cosi': SCELTE: <numeri delle clip adatte separati da virgola, dalla migliore, al massimo {quante}; oppure -1 se nessuna>"""})
    try:
        txt = claude(cont, MODELLO_CONTROLLO, 400, 120)
        m = re.search(r'SCELTE:\s*([-\d,\s]+)', txt)
        ids = [int(x) for x in re.findall(r'-?\d+', m.group(1))] if m else []
        ids = [i for i in ids if 0 <= i < len(cand)]
        log(f'  controllo "{q}": {len(ids)}/{len(cand)} adatte')
        return [cand[i] for i in dict.fromkeys(ids)][:quante]
    except Exception as e:
        log('controllo non riuscito, nessuna clip usata:', str(e)[:150])
        return []


def scegli_media(queries, frase, quante, tipo_pref):
    """Fino a `quante` clip/foto diverse e controllate per una scena. Ordine: ricerche video (o foto), poi l'altro tipo."""
    presi = []
    tipi = ['video', 'foto'] if tipo_pref != 'photo' else ['foto', 'video']
    for tipo in tipi:
        for q in queries:
            if len(presi) >= quante:
                return presi
            tutti = pexels_cerca(tipo, q)
            with _lock:
                liberi = [c for c in tutti if c['url'] not in _usati]
            cand = []
            for c in liberi:
                if len(cand) >= 6:
                    break
                with _lock:
                    if not stessa_ripresa(c):
                        cand.append(c)
            if not cand:
                continue
            for c in controlla(cand, q, frase, quante - len(presi)):
                with _lock:
                    if c['url'] in _usati or stessa_ripresa(c):
                        continue
                    _usati.add(c['url'])
                    _scelte.append((c.get('autore') or '', parole_titolo(c), impronta(c.get('anteprima'))))
                presi.append(c)
        if tipo_pref == 'video' and presi:
            break   # solo video: le foto solo se non c'e' nessuna clip giusta
    return presi


def scrivi_ricerche(scene, titolo):
    """Claude scrive per ogni scena 2-3 ricerche Pexels precise (in inglese): la cosa concreta della frase + il contesto del pubblico."""
    out = {}
    blocchi = [list(range(i, min(i + 35, len(scene)))) for i in range(0, len(scene), 35)]
    for bl in blocchi:
        elenco = '\n'.join(f'{i}. {scene[i]["testo"][:400]}' for i in bl)
        dom = f"""Video YouTube di psicologia per un pubblico {Regole.pubblico or 'italiano'}: "{titolo}".
Per ogni frase scrivi 2-3 ricerche per Pexels (in INGLESE, 2-5 parole ciascuna) per trovare clip REALI che mostrano esattamente cio' che dice la frase:
- la cosa CONCRETA e visibile (persone, gesti, oggetti, luoghi, emozioni sul volto), mai concetti astratti;
- coerenti con le regole del canale: {Regole.testo or '-'}{(' Aggiungi dove ha senso il contesto "' + Regole.suffisso + '" (es. luoghi, persone).') if Regole.suffisso else ''}
- frasi vicine = immagini diverse (non ripetere la stessa ricerca in frasi consecutive);
- se la frase e' astratta, scegli una situazione quotidiana che la rappresenta (es. "ansia" -> "woman worried at kitchen table").
FRASI:
{elenco}
Rispondi SOLO JSON: [{{"n": 0, "q": ["...", "..."]}}, ...]"""
        try:
            t = claude([{'type': 'text', 'text': dom}], MODELLO_AI, 6000)
            for x in json.loads(t[t.find('['): t.rfind(']') + 1]):
                qs = [str(q).strip() for q in (x.get('q') or []) if str(q).strip()]
                if qs:
                    out[int(x['n'])] = qs[:3]
        except Exception as e:
            log('ricerche Claude non riuscite per un blocco:', str(e)[:150])
    for i, s in enumerate(scene):   # riserva: la ricerca di n8n, poi parole della frase
        if i not in out:
            base = str(s.get('stock_query') or '').strip() or ' '.join(re.findall(r'[A-Za-zÀ-ù]{5,}', s['testo'])[:3])
            out[i] = [(base + ' ' + Regole.suffisso).strip()] if base else []
    return out


# ============================================================ SOTTOTITOLI (stile json2video "classic")
def ass_colore(h, alfa=0):
    h = str(h or '#FFFFFF').lstrip('#')
    if len(h) != 6:
        h = 'FFFFFF'
    return f'&H{alfa:02X}{h[4:6]}{h[2:4]}{h[0:2]}'.upper()


def tempo_ass(t):
    t = max(0.0, t)
    return f'{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}'


def sostituzioni(testo, regole):
    """subtitle_replace: 'CAO PSICOLOGIA: KAO PSICOLOGIA, KO PSICOLOGIA: KAO PSICOLOGIA'."""
    for coppia in str(regole or '').split(','):
        if ':' in coppia:
            a, b = coppia.split(':', 1)
            if a.strip():
                testo = re.sub(re.escape(a.strip()), b.strip(), testo, flags=re.I)
    return testo


def tempi_parole(voce, parole, inizio_scene, fine_scene, scene_parole):
    """Tempi (inizio, fine) di ogni parola del copione. faster-whisper sulla voce intera + allineamento al testo;
    riserva: dentro ogni scena, tempo proporzionale alla lunghezza delle parole."""
    stimati = []
    for (a, b), ps in zip(zip(inizio_scene, fine_scene), scene_parole):
        pesi = [len(p) + 2 + (4 if re.search(r'[.,;:!?]$', p) else 0) for p in ps] or [1]
        tot, t = sum(pesi), a
        for p, w in zip(ps, pesi):
            d = (b - a) * w / tot
            stimati.append((t, t + d)); t += d
    if OFFLINE or E('SENZA_WHISPER', '') == '1':
        return stimati
    try:
        from faster_whisper import WhisperModel
        modello = WhisperModel(E('WHISPER_MODEL', '') or 'small', device='cpu', compute_type='int8')
        segs, _ = modello.transcribe(voce, language=E('LINGUA', '') or 'it', word_timestamps=True, vad_filter=False)
        ww = [(w.word.strip(), w.start, w.end) for s in segs for w in (s.words or []) if w.word.strip()]
        norm = lambda x: re.sub(r'[^a-z0-9àèéìòù]', '', x.lower())
        sm = difflib.SequenceMatcher(None, [norm(p) for p in parole], [norm(w[0]) for w in ww], autojunk=False)
        tempi = list(stimati)
        presi = 0
        for blocco in sm.get_matching_blocks():
            for k in range(blocco.size):
                i, j = blocco.a + k, blocco.b + k
                tempi[i] = (ww[j][1], ww[j][2]); presi += 1
        log(f'sottotitoli: {presi}/{len(parole)} parole con il tempo di whisper, le altre stimate')
        for i in range(1, len(tempi)):   # niente sovrapposizioni o salti indietro
            a, b = tempi[i]
            if a < tempi[i - 1][1]:
                a = tempi[i - 1][1]
            tempi[i] = (a, max(a + 0.05, b))
        return tempi
    except Exception as e:
        log('whisper non disponibile (' + str(e)[:100] + '): tempi stimati')
        return stimati


def sottotitoli(scene, tempi_scene, voce, cfg, cartella):
    font_nome = str(cfg.get('subtitle_font_family') or 'Archivo Black')
    ttf = font(font_nome)
    fam = nome_font_ttf(ttf)
    size = int(num(cfg.get('subtitle_font_size'), 105))
    parola_c = ass_colore(cfg.get('subtitle_word_color') or '#F2B33D')
    riga_c = ass_colore(cfg.get('subtitle_line_color') or '#FFFFFF')
    bordo_c = ass_colore(cfg.get('subtitle_outline_color') or '#000000')
    bordo = num(cfg.get('subtitle_outline_width'), 8)
    max_p = max(1, int(num(cfg.get('subtitle_max_words_per_line'), 3)))
    parole, sp = [], []
    for s in scene:
        ps = sostituzioni(s['testo'], cfg.get('subtitle_replace')).split()
        sp.append(ps); parole += ps
    if not parole:
        return None
    tempi = tempi_parole(voce, parole, [a for a, b in tempi_scene], [b for a, b in tempi_scene], sp)
    righe = ['[Script Info]', 'ScriptType: v4.00+', f'PlayResX: {W}', f'PlayResY: {H}', 'WrapStyle: 2', '',
             '[V4+ Styles]',
             'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding',
             f'Style: S,{fam},{size},{riga_c},{riga_c},{bordo_c},&H80000000,0,0,0,0,100,100,0,0,1,{bordo:g},4,2,80,80,110,1', '',
             '[Events]', 'Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text']
    pulisci = lambda x: x.replace('{', '(').replace('}', ')').upper()
    # righe da max N parole, mai a cavallo di due scene; una riga resta a schermo fino alla riga successiva (max 0,6 s di vuoto)
    k = 0
    gruppi = []
    for ps in sp:
        idx = list(range(k, k + len(ps)))
        k += len(ps)
        while idx:
            g = idx[:max_p]
            idx = idx[max_p:]
            # una frase che finisce (punto) chiude la riga
            for j, ii in enumerate(g[:-1]):
                if re.search(r'[.!?]$', parole[ii]):
                    idx = g[j + 1:] + idx; g = g[:j + 1]; break
            gruppi.append(g)
    for n, g in enumerate(gruppi):
        fine_g = tempi[g[-1]][1]
        if n + 1 < len(gruppi):
            fine_g = min(max(fine_g, tempi[gruppi[n + 1][0]][0]), fine_g + 0.6)
        for j, ii in enumerate(g):
            a = tempi[ii][0]
            b = tempi[g[j + 1]][0] if j + 1 < len(g) else fine_g
            if b <= a:
                continue
            testo = ' '.join((('{\\c' + parola_c + '}' + pulisci(parole[x]) + '{\\c' + riga_c + '}') if x == ii else pulisci(parole[x])) for x in g)
            righe.append(f'Dialogue: 0,{tempo_ass(a)},{tempo_ass(b)},S,,0,0,0,,{testo}')
    p = os.path.join(cartella, 'sottotitoli.ass')
    open(p, 'w', encoding='utf-8').write('\n'.join(righe) + '\n')
    log(f'sottotitoli: {len(gruppi)} righe, font {fam} {size}px')
    return p


# ============================================================ IMMAGINI (pezzi di video)
def vf_cover():
    return f'scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},setsar=1,format=yuv420p'


def pezzo_video(src, nf, out, inizio=0.0):
    run(['ffmpeg', '-y', '-v', 'error', '-ss', f'{max(0.0, inizio):.2f}', '-stream_loop', '-1', '-i', src, '-frames:v', str(nf), '-vf', vf_cover()] + ENC + [out])


def pezzo_foto(src, nf, out, verso=1):
    z = f"min(1+0.0009*on,1.25)" if verso > 0 else f"max(1.25-0.0009*on,1)"
    vf = (f'scale={W * 2}:{H * 2}:force_original_aspect_ratio=increase,crop={W * 2}:{H * 2},'
          f"zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={nf}:s={W}x{H}:fps={FPS},setsar=1,format=yuv420p")
    run(['ffmpeg', '-y', '-v', 'error', '-loop', '1', '-i', src, '-frames:v', str(nf), '-vf', vf] + ENC + [out])


def pezzo_png(png, nf, out):
    run(['ffmpeg', '-y', '-v', 'error', '-loop', '1', '-i', png, '-frames:v', str(nf), '-vf', vf_cover()] + ENC + [out])


def testo_grande(img, testo, cfg, box=(160, 0, 1760, 1080), colore=None, dim_max=190):
    """Scritta tipografica (scene typo / chiusura): font del canale, maiuscolo, centrata, il piu' grande possibile, contorno."""
    from PIL import ImageDraw, ImageFont
    stile = {}
    try:
        stile = json.loads(str(cfg.get('typo_text_style') or '').strip() or '{}')
    except Exception:
        pass
    fam = stile.get('font-family') or cfg.get('thumbnail_font_url') or cfg.get('brand_font_family') or 'Anton'
    ttf = font(fam)
    col = colore or stile.get('color') or cfg.get('thumbnail_highlight_text_color') or '#FEF302'
    sw = int(num(cfg.get('typo_stroke_width'), round(num(cfg.get('thumbnail_highlight_stroke_width'), 12) / 2)))
    stroke = cfg.get('thumbnail_highlight_stroke_color') or '#000000'
    x0, y0, x1, y1 = box
    parole = str(testo).upper().split()
    best = None
    for n_righe in range(1, min(5, len(parole)) + 1):
        per = math.ceil(len(parole) / n_righe)
        righe = [' '.join(parole[i:i + per]) for i in range(0, len(parole), per)]
        lo, hi = 20, dim_max
        while lo < hi:
            k = (lo + hi + 1) // 2
            f = ImageFont.truetype(ttf, k)
            if max(f.getlength(r) for r in righe) + 2 * sw <= x1 - x0 and len(righe) * k * 1.0 <= y1 - y0:
                lo = k
            else:
                hi = k - 1
        if not best or lo > best[0]:
            best = (lo, righe)
    k, righe = best
    f = ImageFont.truetype(ttf, k)
    d = ImageDraw.Draw(img)
    y = y0 + ((y1 - y0) - len(righe) * k) / 2
    for r in righe:
        d.text(((x0 + x1) / 2, y), r, font=f, fill=col, anchor='ma', stroke_width=sw, stroke_fill=stroke)
        y += k
    return img


def immagine_typo(s, cfg, texture, out):
    from PIL import Image, ImageDraw, ImageFont
    try:
        img = Image.open(texture).convert('RGB').resize((W, H)) if texture else Image.new('RGB', (W, H), (20, 18, 24))
    except Exception:
        img = Image.new('RGB', (W, H), (20, 18, 24))
    dati = s.get('dati') or {}
    valori = dati.get('valori') if isinstance(dati, dict) else None
    titolo = re.sub(r'\s*[→➔➜⟶⇒➝]\s*', ' » ', str(s.get('etichetta') or '')).strip()
    if dati.get('tipo') in ('numero', 'quota') and valori and len(valori) == 1:   # grafico semplice: valore grande + etichetta
        v = valori[0]
        val = str(v.get('valore'))
        val = ((val.replace('.', ',') if os.environ.get('LINGUA', 'it')[:2] == 'it' else val) + '%') if dati.get('tipo') == 'quota' else (val + (' ' + str(dati.get('unita')) if dati.get('unita') else ''))
        if titolo:
            testo_grande(img, re.sub(r'[\d][\d.,]*\s*(%|x|mln|mld|anni)?', '', titolo, flags=re.I).strip() or titolo, cfg, (160, 60, 1760, 300), dim_max=110)
        testo_grande(img, val, cfg, (160, 330, 1760, 760), colore=cfg.get('chart_value_color') or cfg.get('chart_bar_color'), dim_max=260)
        if v.get('etichetta'):
            testo_grande(img, str(v['etichetta']), cfg, (160, 790, 1760, 900), colore='#FFFFFF', dim_max=60)
    elif titolo:
        testo_grande(img, titolo, cfg)
    img.save(out, quality=92)
    return out


# ============================================================ MUSICA, SUONI, ISCRIZIONE
def musica_rotazione(urls, totale, volume, seme, cartella):
    """Si parte da un brano a caso, poi seguono gli altri in ordine (a giro), con dissolvenze: copre tutto il video."""
    file_b = []
    for n, u in enumerate(urls):
        try:
            f = scarica(u, os.path.join(cartella, f'musica_{n}.mp3'))
            if durata(f) > 20:
                file_b.append(f)
        except Exception as e:
            log('brano saltato:', str(e)[:80])
    if not file_b:
        return None
    rnd = random.Random(seme)
    inizio = rnd.randrange(len(file_b))
    ordine = file_b[inizio:] + file_b[:inizio]
    seq, somma, k = [], 0.0, 0
    while somma < totale + 5 and len(seq) < 80:
        f = ordine[k % len(ordine)]; k += 1
        seq.append(f); somma += durata(f) - (3 if len(seq) > 1 else 0)
    unita = os.path.join(cartella, 'musica_unita.m4a')
    if len(seq) == 1:
        run(['ffmpeg', '-y', '-v', 'error', '-i', seq[0], '-c:a', 'aac', '-b:a', '192k', unita])
    else:
        ins = sum((['-i', f] for f in seq), [])
        fl, prev = [], '[0:a]'
        for n in range(1, len(seq)):
            o = f'[m{n}]' if n < len(seq) - 1 else '[mus]'
            fl.append(f'{prev}[{n}:a]acrossfade=d=3:c1=tri:c2=tri{o}'); prev = o
        run(['ffmpeg', '-y', '-v', 'error'] + ins + ['-filter_complex', ';'.join(fl), '-map', '[mus]', '-c:a', 'aac', '-b:a', '192k', unita])
    log(f'musica: {len(seq)} brani in fila (parte da "{os.path.basename(ordine[0])}"), volume {volume}')
    return unita


def audio_finale(voce, totale, musica, volume, swoosh, momenti, vol_swoosh, cartella, extra=None):
    """Voce + musica (in loop, volume basso, dissolvenze) + suono di transizione a inizio scena."""
    ins = ['-i', voce]
    fl = [f'[0:a]apad=whole_dur={totale:.3f}[v]']
    mix = ['[v]']
    k = 1
    if musica:
        ins += ['-stream_loop', '-1', '-i', musica]
        fl.append(f'[{k}:a]atrim=0:{totale:.3f},volume={volume},afade=t=in:d=2,afade=t=out:st={max(0, totale - 3):.2f}:d=3[m]')
        mix.append('[m]'); k += 1
    if swoosh and momenti:
        ins += ['-i', swoosh]
        n = len(momenti)
        fl.append(f'[{k}:a]volume={vol_swoosh},asplit={n}' + ''.join(f'[w{j}]' for j in range(n)))
        for j, t in enumerate(momenti):
            ms = int(t * 1000)
            fl.append(f'[w{j}]adelay={ms}|{ms}[d{j}]')
        fl.append(''.join(f'[d{j}]' for j in range(n)) + f'amix=inputs={n}:duration=longest:normalize=0[sw]')
        mix.append('[sw]'); k += 1
    for f, t, v, dd in (extra or []):   # suoni delle scene (cornice, cassa, ...): come json2video
        ins += ['-i', f]; ms = int(max(0.0, t) * 1000)
        fl.append(f'[{k}:a]' + (f'atrim=0:{dd:.3f},' if dd and dd > 0 else '') + f'volume={v},adelay={ms}|{ms}[x{k}]')
        mix.append(f'[x{k}]'); k += 1
    fl.append(''.join(mix) + f'amix=inputs={len(mix)}:duration=first:normalize=0,atrim=0:{totale:.3f}[a]')
    out = os.path.join(cartella, 'audio_finale.m4a')
    run(['ffmpeg', '-y', '-v', 'error'] + ins + ['-filter_complex', ';'.join(fl), '-map', '[a]', '-c:a', 'aac', '-b:a', '192k', out])
    return out


def componi(base, audio, ass, isc, totale, cartella, out):
    """Video base + sottotitoli + invito iscrizione (immagine al secondo N per 4 s, clic e campana) + audio."""
    ins = ['-i', base, '-i', audio]
    fl = '[0:v]' + (f"ass='{ass}':fontsdir='{FONT_DIR}'" if ass else 'null') + '[v0]'
    amap, vmap, k = '1:a', '[v0]', 2
    img = str((isc or {}).get('img') or '').strip()
    if img:
        try:
            sec = num(isc.get('sec'), 10.0)
            png = scarica(img, os.path.join(cartella, 'iscriviti.png'))
            ins += ['-loop', '1', '-t', f'{totale:.3f}', '-i', png]
            fl += (f";[{k}:v]scale=900:-1,format=rgba,fade=t=in:st={sec}:d=0.3:alpha=1,fade=t=out:st={sec + 3.6}:d=0.4:alpha=1[isc];"
                   f"[v0][isc]overlay=x=(W-w)/2:y=640:enable='between(t,{sec},{sec + 4})'[v1]")
            vmap = '[v1]'; k += 1
            suoni = []
            clic = num(isc.get('clic_ritardo'), 0.6)
            for url, quando, nome in ((isc.get('clic'), sec + clic, 'clic'), (isc.get('campana'), sec + clic + num(isc.get('campana_ritardo'), 1.0), 'campana')):
                if not str(url or '').strip():
                    continue
                try:
                    f = scarica(str(url).strip(), os.path.join(cartella, nome + '.mp3'))
                except Exception as e:
                    log(nome + ' non disponibile:', str(e)[:80]); continue
                ins += ['-i', f]; ms = int(quando * 1000)
                fl += f";[{k}:a]adelay={ms}|{ms},volume=0.5[s{k}]"; suoni.append(f'[s{k}]'); k += 1
            if suoni:
                fl += f";[1:a]{''.join(suoni)}amix=inputs={len(suoni) + 1}:duration=first:normalize=0[ai]"; amap = '[ai]'
            log(f'invito iscrizione al secondo {sec}')
        except Exception as e:
            log('invito iscrizione saltato:', str(e)[:120])
    run(['ffmpeg', '-y', '-v', 'error'] + ins + ['-filter_complex', fl, '-map', vmap, '-map', amap,
         '-c:v', 'libx264', '-preset', 'fast', '-crf', '18', '-s', '2560x1440', '-sws_flags', 'lanczos', '-pix_fmt', 'yuv420p', '-r', str(FPS),
         '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', '-t', f'{totale:.3f}', out])


# ============================================================ CARICAMENTO E RISPOSTA A n8n
def carica_file(path, tipo='video/mp4'):
    h = {'Authorization': 'Key ' + E('FAL_KEY', '')}
    dim = os.path.getsize(path)
    base = 'https://rest.alpha.fal.ai/storage/upload/'
    corpo = {'content_type': tipo, 'file_name': os.path.basename(path)}
    if dim <= 90 * 1024 * 1024:
        ini = http(base + 'initiate?storage_type=fal-cdn-v3', corpo, h)
        with open(path, 'rb') as f:
            req = urllib.request.Request(ini['upload_url'], data=f.read(), method='PUT', headers={'Content-Type': tipo})
        with urllib.request.urlopen(req, timeout=1800):
            pass
        return ini['file_url']
    ini = http(base + 'initiate-multipart?storage_type=fal-cdn-v3', corpo, h)
    u = urllib.parse.urlsplit(ini['upload_url'])
    radice, coda = f'{u.scheme}://{u.netloc}{u.path}', ('?' + u.query) if u.query else ''
    pezzo, parti = 10 * 1024 * 1024, []
    with open(path, 'rb') as f:
        n = 0
        while True:
            dati = f.read(pezzo)
            if not dati:
                break
            n += 1
            for tent in range(4):
                try:
                    req = urllib.request.Request(f'{radice}/{n}{coda}', data=dati, method='PUT')
                    with urllib.request.urlopen(req, timeout=600) as r:
                        testo = r.read().decode() or '{}'
                        try:
                            etag = json.loads(testo).get('etag')
                        except Exception:
                            etag = None
                        etag = etag or r.headers.get('ETag') or r.headers.get('etag')
                    if not etag:
                        raise RuntimeError('nessun etag')
                    parti.append({'partNumber': n, 'etag': etag}); break
                except Exception as e:
                    if tent == 3:
                        raise
                    log(f'pezzo {n} non caricato ({str(e)[:80]}), riprovo'); time.sleep(5 * (tent + 1))
    http(f'{radice}/complete{coda}', {'parts': parti})
    return ini['file_url']


def rispondi(url, corpo):
    if not url:
        log('nessun resume_url:', json.dumps(corpo)[:300]); return
    for k in range(5):
        try:
            http(url, corpo, raw=True); log('risposta a n8n inviata'); return
        except Exception as e:
            log('risposta a n8n non riuscita (' + str(e)[:120] + '), riprovo'); time.sleep(10 * (k + 1))


# ============================================================ MONTAGGIO
def monta(dati, cartella, out):
    cfg = dati.get('config') or {}
    Regole.testo = str(cfg.get('regole_immagini') or '').strip()
    Regole.escludi = [w.strip().lower() for w in str(cfg.get('stock_exclude_words') or '').split(',') if w.strip()]
    Regole.suffisso = str(cfg.get('stock_query_suffix') or '').strip()
    Regole.pubblico = {'it': 'italiano', 'en': 'americano/inglese'}.get(str(cfg.get('language') or 'it')[:2], str(cfg.get('language') or ''))
    if str(cfg.get('language') or '').strip():   # lingua della voce per whisper (prima era sempre 'it')
        os.environ['LINGUA'] = str(cfg['language']).strip().lower()[:2]
    EFF = str(cfg.get('effetti_github') or '').strip().upper() == 'SI'   # effetti di json2video disegnati qui (grafici, cornici, cifre, suoni)
    scene = [s for s in dati.get('scene', []) if str(s.get('audio') or '').strip()]
    if not scene:
        raise RuntimeError('nessuna scena con audio nel file dati')
    os.makedirs(cartella, exist_ok=True)
    # 1) voce
    def prendi_voce(x):
        i, s = x
        a = scarica(s['audio'], os.path.join(cartella, f'voce_{i:03d}.mp3'))
        return a, durata(a)
    with ThreadPoolExecutor(6) as ex:
        voci = list(ex.map(prendi_voce, enumerate(scene)))
    tempi, t = [], 0.0
    for a, d in voci:
        tempi.append((t, t + d)); t += d
    totale_voce = t
    lista = os.path.join(cartella, 'voci.txt')
    open(lista, 'w').write(''.join(f"file '{os.path.abspath(a)}'\n" for a, d in voci))
    voce = os.path.join(cartella, 'voce.m4a')
    run(['ffmpeg', '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', lista, '-c:a', 'aac', '-b:a', '192k', voce])
    totale_voce = durata(voce)
    log(f'{len(scene)} scene, {totale_voce / 60:.1f} minuti di voce')
    # 2) piano dei pezzi: una clip nuova ogni N secondi (stock_clip_duration), pezzi uguali dentro la scena
    passo = max(2.0, num(cfg.get('stock_clip_duration'), 4.0))
    tipo_pref = {'video': 'video', 'photo': 'photo', 'image': 'photo'}.get(str(cfg.get('stock_media_type') or 'mixed').lower(), 'mixed')
    texture = [u.strip() for u in str(cfg.get('scene_bg_textures') or '').split(',') if u.strip()]
    piano = []   # (scena, inizio, fine)
    for i, (s, (a, b)) in enumerate(zip(scene, tempi)):
        n = 1 if (s.get('typo') or (EFF and (s.get('effetti') or {}).get('cornice'))) else max(1, math.ceil((b - a) / passo - 0.05))
        for k in range(n):
            piano.append((i, a + (b - a) * k / n, a + (b - a) * (k + 1) / n))
    # 3) ricerche e scelta delle clip (4 controlli)
    if OFFLINE:
        media_scena = {i: [{'tipo': s.get('media_tipo_locale', 'video'), 'url': s['media_locale']}] if s.get('media_locale') else []
                       for i, s in enumerate(scene)}
    else:
        ricerche = scrivi_ricerche(scene, dati.get('titolo') or '')
        def per_scena(i):
            s = scene[i]
            if s.get('typo') or (EFF and (s.get('effetti') or {}).get('cornice')):
                return i, []
            quanti = sum(1 for x in piano if x[0] == i)
            contesto = ' '.join(scene[j]['testo'] for j in (i - 1, i) if 0 <= j < len(scene))[-600:]
            m = scegli_media(ricerche.get(i) or [], contesto, quanti, tipo_pref)
            log(f'scena {i + 1}: {len(m)}/{quanti} clip ({", ".join(ricerche.get(i) or [])[:90]})')
            return i, m
        with ThreadPoolExecutor(3) as ex:
            media_scena = dict(ex.map(per_scena, range(len(scene))))
    # 4) i pezzi di video, tagliati a fotogrammi esatti sulla voce (niente sfasamenti)
    pezzi, scaricati, ultimo = [], {}, None
    contatore, liste_eff = {}, {}
    for n, (i, a, b) in enumerate(piano):
        nf = int(round(b * FPS)) - int(round(a * FPS))
        if nf <= 0:
            continue
        o = os.path.join(cartella, f'pezzo_{n:04d}.mp4')
        s = scene[i]
        eff = (s.get('effetti') or {}) if EFF else {}
        try:
            if eff.get('cornice'):   # foto in cornice su fondo colorato (stessa pagina HTML di json2video), con zoom lento
                png = EF.foto_cornice(eff['cornice'], eff.get('sfondo'), cartella, f'cornice_{i:03d}')
                pezzo_foto(png, nf, o, 1)
                ultimo = None
            elif s.get('typo'):
                tex = None
                if texture:
                    u = texture[i % len(texture)]
                    tex = scaricati.get(u) or scarica(u, os.path.join(cartella, f'texture_{i % len(texture)}.jpg'))
                    scaricati[u] = tex
                s_typo = dict(s, etichetta='', dati={}) if any(l.get('type') == 'text' for l in eff.get('livelli') or []) else s   # il titolo lo disegna il livello di json2video
                pezzo_png(immagine_typo(s_typo, cfg, tex, os.path.join(cartella, f'typo_{i:03d}.jpg')), nf, o)
                ultimo = None
            else:
                k = contatore.get(i, 0); contatore[i] = k + 1
                lista_m = media_scena.get(i) or []
                if k >= len(lista_m):
                    raise LookupError('nessuna clip controllata per questo pezzo')
                m = lista_m[k]
                foto = m['tipo'] == 'foto'
                if m['url'] not in scaricati:
                    scaricati[m['url']] = scarica(m['url'], os.path.join(cartella, f'media_{len(scaricati):04d}' + ('.jpg' if foto else '.mp4')))
                src = scaricati[m['url']]
                if foto:
                    pezzo_foto(src, nf, o, 1 if n % 2 == 0 else -1)
                    ultimo = ('foto', src, 0.0)
                else:
                    pezzo_video(src, nf, o)
                    ultimo = ('video', src, nf / FPS)
        except Exception as e:
            # riserva: si continua la clip precedente (mai un'immagine a caso)
            if not isinstance(e, LookupError):
                log(f'pezzo {n} (scena {i + 1}) non riuscito: {str(e)[:120]}')
            if ultimo and ultimo[0] == 'video':
                pezzo_video(ultimo[1], nf, o, ultimo[2]); ultimo = ('video', ultimo[1], ultimo[2] + nf / FPS)
            elif ultimo:
                pezzo_foto(ultimo[1], nf, o, -1)
            elif pezzi:
                run(['ffmpeg', '-y', '-v', 'error', '-sseof', '-0.1', '-i', pezzi[-1], '-frames:v', '1', o + '.png'])
                pezzo_png(o + '.png', nf, o)
            else:
                run(['ffmpeg', '-y', '-v', 'error', '-f', 'lavfi', '-i', f'color=c=0x15121a:s={W}x{H}:r={FPS}', '-frames:v', str(nf)] + ENC + [o])
        if eff.get('livelli'):   # grafici animati, titoli, cifre in dollari, clip typo_fast_cut sopra il pezzo
            try:
                a_sc, b_sc = tempi[i]
                if i not in liste_eff:
                    liste_eff[i] = EF.sovrimpressione(eff['livelli'], b_sc - a_sc, cartella, f'eff_{i:03d}')
                    for v in eff['livelli']:
                        if v.get('type') == 'video' and v.get('src') and not v.get('locale'):
                            try:
                                v['locale'] = scaricati.get(v['src']) or scarica(v['src'], os.path.join(cartella, f'sopra_{len(scaricati):04d}.mp4'))
                                scaricati[v['src']] = v['locale']
                            except Exception as e:
                                log('clip sopra la scena non scaricata:', str(e)[:80])
                video_sopra = [v for v in eff['livelli'] if v.get('type') == 'video' and v.get('locale')]
                o2 = o[:-4] + '_eff.mp4'
                o = EF.applica(o, o2, liste_eff[i], video_sopra, a - a_sc, nf / FPS, cartella, ENC, vf_cover())
            except Exception as e:
                log(f'effetti della scena {i + 1} non applicati: {str(e)[:150]}')
        pezzi.append(o)
    if EFF:
        EF.chiudi()
    # 5) nessuna schermata finale (decisione di Giorgio, 31 ott 2026: mai su nessun canale)
    totale = totale_voce
    lista_p = os.path.join(cartella, 'pezzi.txt')
    open(lista_p, 'w').write(''.join(f"file '{os.path.abspath(p)}'\n" for p in pezzi))
    base = os.path.join(cartella, 'base.mp4')
    run(['ffmpeg', '-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', lista_p, '-c', 'copy', base])
    # 6) sottotitoli
    ass = None
    if str(cfg.get('show_subtitles', True)).strip().lower() not in ('false', 'no', '0'):
        ass = sottotitoli(scene, tempi, voce, cfg, cartella)
    # 7) audio: voce + musica a rotazione + transizioni
    musica = None
    urls = [u.strip() for u in re.split(r'\|\||\n', str(cfg.get('musica_rotazione') or cfg.get('musica') or '')) if u.strip()]   # colonna musica_rotazione
    vol = num(cfg.get('musica_volume'), 0.03)
    vol = vol / 100 if vol > 1 else vol
    if not urls and str(dati.get('musica') or '').strip():   # musica del canale di json2video (brand_music_url)
        urls = [str(dati['musica']).strip()]
        vol = num(dati.get('volume_musica'), vol)
    if urls:
        try:
            musica = musica_rotazione(urls, totale, vol, str(dati.get('id') or dati.get('titolo') or ''), cartella)
        except Exception as e:
            log('musica saltata:', str(e)[:150])
    swoosh, momenti = None, []
    if str(cfg.get('transition_sound_url') or '').strip():
        try:
            swoosh = scarica(cfg['transition_sound_url'], os.path.join(cartella, 'swoosh.mp3'))
            perc = num(cfg.get('transition_sound_percentage'), 100)
            momenti = [a for k, (a, b) in enumerate(tempi) if k > 0 and math.floor(k * perc / 100) > math.floor((k - 1) * perc / 100)]
        except Exception as e:
            log('suono di transizione saltato:', str(e)[:80])
    extra = []
    if EFF:
        file_suoni = {}
        for i, s in enumerate(scene):
            for x in (s.get('effetti') or {}).get('suoni') or []:
                u = str(x.get('src') or '').strip()
                if not u:
                    continue
                try:
                    if u not in file_suoni:
                        file_suoni[u] = scarica(u, os.path.join(cartella, f'suono_{len(file_suoni):03d}.mp3'))
                    extra.append((file_suoni[u], tempi[i][0] + num(x.get('start'), 0), num(x.get('volume'), 1), num(x.get('durata'), 0)))
                except Exception as e:
                    log('suono saltato:', str(e)[:80])
        log(f'effetti json2video: {sum(1 for s in scene if (s.get("effetti") or {}).get("livelli"))} scene con livelli, '
            f'{sum(1 for s in scene if (s.get("effetti") or {}).get("cornice"))} foto in cornice, {len(extra)} suoni')
    audio = audio_finale(voce, totale, musica, vol, swoosh, momenti, num(cfg.get('transition_sound_volume'), 0.7), cartella, extra)
    # 8) composizione finale
    componi(base, audio, ass, dati.get('iscrizione') or {}, totale, cartella, out)
    log(f'video pronto: {durata(out) / 60:.1f} minuti, {len(pezzi)} pezzi, ricerche Pexels {_conti["pexels"]}')
    return durata(out)


def main():
    p = json.loads(E('PAYLOAD') or '{}')
    os.makedirs(LAVORO, exist_ok=True)
    t0 = time.time()
    try:
        if p.get('dati'):
            dati = p['dati']
        else:
            dati = json.loads(http(url_drive(p['dati_url']), raw=True).decode('utf-8-sig'))
        dati.setdefault('id', p.get('id'))
        out = os.path.join(LAVORO, 'video_finale.mp4')
        dur = monta(dati, LAVORO, out)
        if E('DRY_RUN', '0') == '1':
            log('prova: video NON caricato (artifact)'); return
        url = carica_file(out)
        log('video caricato:', url, f'| {round((time.time() - t0) / 60, 1)} minuti di lavoro')
        rispondi(p.get('resume_url'), {'movie': {'status': 'done', 'url': url, 'duration': round(dur, 2)}})
    except Exception as e:
        traceback.print_exc()
        rispondi(p.get('resume_url'), {'movie': {'status': 'failed', 'message': str(e)[:500]}})
        sys.exit(1)


if __name__ == '__main__':
    main()
