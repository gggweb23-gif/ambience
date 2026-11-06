#!/usr/bin/env python3
"""SHORTS DAI NOSTRI VIDEO LUNGHI (6 nov 2026, Giorgio: 4 Short al giorno per canale, KAO compreso, caricati in automatico).
Per ogni canale con shorts_al_giorno > 0 e shorts_budget_giorno compilato (Channel Configs):
1. prende l'ultimo video lungo gia' su YouTube (riga Completato con youtube_video_id e colonna shorts vuota nel file di produzione)
   e il suo file dall'artifact "shorts-<canale>-riga<N>" salvato dal motore (3 giorni);
2. trascrive l'audio gratis (faster-whisper sul server GitHub);
3. Claude sceglie i momenti piu' forti (35-55 s, frase d'aggancio all'inizio, senso compiuto) -> spesa entro shorts_budget_giorno;
4. formato verticale 1080x1920: video al centro, lo stesso video sfocato dietro, gancio scritto in alto, sottotitoli grandi parola per parola;
5. controlli (durata, niente nero, niente silenzio), poi caricamento programmato negli orari di shorts_orari DOPO l'uscita del video lungo,
   con il link al video completo nella descrizione. Gli id e gli orari finiscono nella colonna shorts del file di produzione.
PROVA = SI: fa gli Short ma NON li carica (cartella shorts_prova/ -> artifact da guardare)."""
import datetime as dt, glob, json, os, re, shutil, subprocess, sys, time, urllib.parse, urllib.request, zipfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import avvio_canali as A
import performance as PF

E = os.environ.get
ROMA = A.ZoneInfo('Europe/Rome')
SOLO = E('SOLO_CANALE', '').strip()
PROVA = E('PROVA', 'NO').strip().upper() == 'SI'
RIGA = E('RIGA', '').strip()
REPO = E('GITHUB_REPOSITORY', 'gggweb23-gif/ambience')
FONT = os.path.abspath('ctr_test/Anton.ttf')
LAV = os.path.abspath('lavoro_shorts')
OUT_PROVA = os.path.abspath('shorts_prova')
MODELLO = 'claude-haiku-4-5-20251001'
DUR_MIN, DUR_MAX = 30, 58


def log(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)


def num(v, d=0.0):
    try:
        return float(str(v).replace(',', '.').replace('$', '').strip())
    except Exception:
        return d


def run(cmd, **k):
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **k)


def http(url, corpo=None, h=None, timeout=120, metodo=None):
    dati = json.dumps(corpo).encode() if corpo is not None else None
    req = urllib.request.Request(url, data=dati, method=metodo, headers={**({'Content-Type': 'application/json'} if dati else {}), **(h or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        t = r.read().decode()
        return json.loads(t) if t.strip() else {}


def gh_json(percorso):
    return json.loads(run(['gh', 'api', percorso]).stdout)


def durata(f):
    return float(run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f]).stdout.strip())


# ---------------------------------------------------------------- sorgente
def data_ini(r):
    try:
        ini = dt.datetime.fromisoformat(str(r.get('data_inizio_produzione')).strip().replace('Z', '+00:00').replace(' ', 'T'))
        return ini if ini.tzinfo else ini.replace(tzinfo=ROMA)
    except Exception:
        return None


def scarica_sorgente(cid, riga, r, dur_yt, cfg_corrente=None):
    cfg_corrente = cfg_corrente or {}
    """Il file del video lungo: prima l'artifact con il suo nome (shorts-<canale>-riga<N>, poi DA CARICARE <canale>);
    per i video fatti prima degli Short, gli artifact dei motori (video-storia, video-mappe, video-archivio) dei giorni del video.
    Si usa solo se la durata coincide con quella del video su YouTube (cosi' non si prende mai il video sbagliato)."""
    slug = re.sub(r'[^a-z0-9]+', '_', cid.lower()).strip('_')
    def giusto(v, generico=False):
        if not v:
            return False
        if generico and '/archivio/' in v and '/archivio/' + slug + '_' not in v:   # video-archivio contiene i video di piu' canali
            return False
        d = durata(v)
        ok = d >= 180 and (not dur_yt or abs(d - dur_yt) <= 1.5)
        if not ok:
            log(f'  file scartato: dura {d / 60:.1f} min' + (f', su YouTube {dur_yt / 60:.1f} min' if dur_yt else ''))
        return ok
    for nome in (f'shorts-{cid}-riga{riga}', f'DA CARICARE {cid}'):
        arts = elenco(nome)[-1:]
        for a in arts:
            v = _scarica(a)
            if giusto(v):
                return v
    ini = data_ini(r)
    if not ini:
        return None
    motore = str(cfg_corrente.get('render_workflow') or cfg_corrente.get('github_workflow') or '').strip()
    generici = {'video_storia.yml': 'video-storia', 'video_mappe.yml': 'video-mappe', 'video_archivio.yml': 'video-archivio'}
    for nome in [generici[motore]] if motore in generici else []:   # solo i file del motore di QUESTO canale (mai il video di un altro canale)
        for a in reversed(elenco(nome)):
            c = dt.datetime.fromisoformat(a['created_at'].replace('Z', '+00:00'))
            if ini - dt.timedelta(hours=1) <= c <= ini + dt.timedelta(hours=36):
                for v in _scarica(a, tutti=True):
                    if giusto(v, True):
                        return v
    return None


def elenco(nome):
    arts = gh_json(f'repos/{REPO}/actions/artifacts?name={urllib.parse.quote(nome)}&per_page=100').get('artifacts', [])
    return sorted([a for a in arts if not a.get('expired')], key=lambda x: x['created_at'])


def _scarica(a, tutti=False):
    d = os.path.join(LAV, 'sorgente'); shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
    z = os.path.join(LAV, 'sorgente.zip')
    with open(z, 'wb') as f:
        subprocess.run(['gh', 'api', f'repos/{REPO}/actions/artifacts/{a["id"]}/zip'], stdout=f, check=True)
    zipfile.ZipFile(z).extractall(d); os.remove(z)
    mp4 = sorted(glob.glob(os.path.join(d, '**', '*.mp4'), recursive=True), key=os.path.getsize, reverse=True)
    return mp4 if tutti else (mp4[0] if mp4 else None)


def durata_yt(vid, tk):
    try:
        it = http('https://www.googleapis.com/youtube/v3/videos?part=contentDetails&id=' + vid, h={'Authorization': 'Bearer ' + tk})['items'][0]
        m = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', it['contentDetails']['duration'])
        return int(m.group(1) or 0) * 3600 + int(m.group(2) or 0) * 60 + int(m.group(3) or 0)
    except Exception:
        return None


# ---------------------------------------------------------------- trascrizione (gratis)
def trascrivi(video, lingua):
    from faster_whisper import WhisperModel
    wav = os.path.join(LAV, 'audio.wav')
    run(['ffmpeg', '-y', '-v', 'error', '-i', video, '-ac', '1', '-ar', '16000', wav])
    import numpy as np, wave
    with wave.open(wav) as w:   # audio letto senza PyAV (la versione nuova di av non accetta piu' metadata_errors)
        audio = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768.0
    m = WhisperModel(E('WHISPER_MODEL', 'small'), device='cpu', compute_type='int8')
    segs, _ = m.transcribe(audio, language=(lingua or 'en')[:2], word_timestamps=True, vad_filter=True)
    frasi, parole = [], []
    for s in segs:
        ws = [{'w': w.word.strip(), 's': w.start, 'e': w.end} for w in (s.words or []) if w.word.strip()]
        parole += ws
        frasi.append({'s': s.start, 'e': s.end, 't': s.text.strip()})
    log('trascrizione:', len(frasi), 'frasi,', len(parole), 'parole')
    return frasi, parole


# ---------------------------------------------------------------- scelta dei momenti (Claude, entro il budget)
def scegli(frasi, n, titolo, lingua, budget):
    testo = '\n'.join(f"[{f['s']:.1f}-{f['e']:.1f}] {f['t']}" for f in frasi)
    lingua_nome = {'it': 'Italian', 'en': 'English'}.get((lingua or 'en')[:2], 'the language of the transcript')
    domanda = (f'This is the timed transcript of our YouTube video "{titolo}".\n\n{testo}\n\n'
               f'Pick the {n} best moments to cut as YouTube Shorts. Rules:\n'
               f'- each moment lasts between 35 and 55 seconds, starts exactly at the start of a line and ends exactly at the end of a line;\n'
               '- the FIRST sentence must hook a stranger scrolling (a surprising fact, a question, a strong claim), never a greeting, never "in this video";\n'
               '- the moment must make sense on its own, without the rest of the video, and end on a complete thought (ideally a payoff or a twist);\n'
               '- no overlaps between moments; skip the subscribe request and the outro;\n'
               f'- for each moment write in {lingua_nome}: "gancio" = on-screen hook, max 6 words, punchy, in CAPITAL letters; '
               '"titolo" = Short title, max 70 characters, curiosity-driven, no hashtags; '
               '"frase" = one sentence for the description.\n'
               'Answer ONLY with JSON: [{"inizio": seconds, "fine": seconds, "gancio": "...", "titolo": "...", "frase": "..."}]\n'
               'IMPORTANT: if the transcript is clearly NOT about the video title (wrong video), answer only the word DIVERSO.')
    r = http('https://api.anthropic.com/v1/messages', {'model': MODELLO, 'max_tokens': 2000, 'messages': [{'role': 'user', 'content': domanda}]},
             {'x-api-key': E('ANTHROPIC_API_KEY', ''), 'anthropic-version': '2023-06-01'}, timeout=300)
    u = r.get('usage', {})
    costo = (u.get('input_tokens', 0) * 1.0 + u.get('output_tokens', 0) * 5.0) / 1e6
    log(f'scelta dei momenti: {costo:.4f} $ (budget {budget:.2f} $)')
    if costo > budget:
        raise RuntimeError(f'spesa {costo:.4f} $ oltre shorts_budget_giorno {budget} $: Short non fatti')
    t = ''.join(b.get('text', '') for b in r.get('content', []))
    if t.strip().upper().startswith('DIVERSO'):
        raise RuntimeError('il file non corrisponde al titolo del video: Short non fatti')
    m = re.search(r'\[.*\]', t, re.S)
    scelte = json.loads(m.group(0)) if m else []
    # aggancio ai confini delle frasi e controllo delle durate
    inizi, fini = [f['s'] for f in frasi], [f['e'] for f in frasi]
    out = []
    for x in scelte:
        try:
            a = min(inizi, key=lambda v: abs(v - float(x['inizio'])))
            b = min(fini, key=lambda v: abs(v - float(x['fine'])))
        except Exception:
            continue
        if b - a > DUR_MAX:   # troppo lungo: si chiude all'ultima frase che sta dentro
            b = max([v for v in fini if a + DUR_MIN <= v <= a + DUR_MAX] or [a + DUR_MAX])
        if b - a < DUR_MIN or any(not (b <= o['a'] or a >= o['b']) for o in out):
            log('momento scartato:', x.get('titolo'), f'{a:.0f}-{b:.0f}'); continue
        out.append({'a': a, 'b': b, 'gancio': str(x.get('gancio') or '').strip()[:60], 'titolo': str(x.get('titolo') or '').strip()[:90],
                    'frase': str(x.get('frase') or '').strip()[:300]})
    testo_tutto = ' '.join(f['t'] for f in frasi).lower()
    for x in out[:n]:   # gancio con parole sbagliate o tagliate (es. "CAD"): meglio senza gancio che con un errore
        sbagliate = [w for w in errori_ortografia(x['gancio'], lingua) if w.lower() not in testo_tutto]
        if sbagliate:
            log(f"  gancio scartato per parole sbagliate {sbagliate}: {x['gancio']}"); x['gancio'] = ''
    return out[:n], costo


def errori_ortografia(testo, lingua):
    if not testo:
        return []
    diz = {'it': 'it_IT', 'en': 'en_US'}.get((lingua or 'en')[:2], 'en_US')
    try:
        r = subprocess.run(['hunspell', '-d', diz, '-l'], input=testo.lower(), capture_output=True, text=True, timeout=30)
        return [w for w in r.stdout.split() if not w.isdigit()]
    except Exception as e:
        log('  controllo ortografia non disponibile:', str(e)[:80]); return []


# ---------------------------------------------------------------- montaggio verticale
def ass_tempo(t):
    t = max(0, t); h = int(t // 3600); m = int(t % 3600 // 60); s = t % 60
    return f'{h}:{m:02d}:{s:05.2f}'


def sottotitoli(parole, a, b, gancio, file):
    pz = [w for w in parole if w['s'] >= a - 0.05 and w['e'] <= b + 0.3]
    righe = ['[Script Info]', 'ScriptType: v4.00+', 'PlayResX: 1080', 'PlayResY: 1920', '',
             '[V4+ Styles]',
             'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding',
             'Style: Gancio,Anton,124,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,0,0,0,0,100,100,1,0,1,8,3,8,70,70,250,1',
             'Style: Sotto,Anton,92,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,0,0,0,0,100,100,1,0,1,7,3,2,60,60,520,1', '',
             '[Events]', 'Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text']
    if gancio:
        righe.append(f'Dialogue: 1,{ass_tempo(0)},{ass_tempo(b - a)},Gancio,,0,0,0,,{gancio.upper()}')
    gruppo = []
    for i, w in enumerate(pz):   # gruppi di 3 parole; la parola detta in quel momento in giallo
        gruppo.append(w)
        if len(gruppo) == 3 or i == len(pz) - 1 or re.search(r'[.!?,;:]$', w['w']):
            for j, g in enumerate(gruppo):
                fine = gruppo[j + 1]['s'] if j + 1 < len(gruppo) else g['e']
                testo = ' '.join(('{\\c&H00F2FF&}' + x['w'].upper() + '{\\c&HFFFFFF&}') if k == j else x['w'].upper() for k, x in enumerate(gruppo))
                righe.append(f"Dialogue: 0,{ass_tempo(g['s'] - a)},{ass_tempo(max(fine, g['s'] + 0.08) - a)},Sotto,,0,0,0,,{testo}")
            gruppo = []
    open(file, 'w', encoding='utf-8').write('\n'.join(righe) + '\n')


def monta(video, x, parole, out, con_sottotitoli=True):
    ass = out[:-4] + '.ass'
    sottotitoli(parole if con_sottotitoli else [], x['a'], x['b'], x['gancio'], ass)
    d = x['b'] - x['a'] + 0.25
    fd = os.path.dirname(FONT)
    fl = ('[0:v]split[s1][s2];[s1]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=24:2,eq=brightness=-0.18[bg];'
          '[s2]scale=1080:-2[fg];[bg][fg]overlay=0:(H-h)/2,'
          f"ass='{ass}':fontsdir='{fd}',fade=t=out:st={d - 0.35:.2f}:d=0.35,fps=30[v];"
          f'[0:a]afade=t=out:st={d - 0.35:.2f}:d=0.35[au]')
    run(['ffmpeg', '-y', '-v', 'error', '-ss', f"{x['a']:.2f}", '-t', f'{d:.2f}', '-i', video, '-filter_complex', fl, '-map', '[v]', '-map', '[au]',
         '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', out])
    return out


def controlla(f):
    """Mai caricare uno Short sbagliato: durata, nero, silenzio."""
    dur = durata(f)
    if not DUR_MIN - 1 <= dur <= 62:
        return f'durata {dur:.0f} s'
    err = subprocess.run(['ffmpeg', '-v', 'info', '-i', f, '-vf', 'blackdetect=d=1.5:pix_th=0.08', '-af', 'silencedetect=n=-45dB:d=3', '-f', 'null', '-'],
                         capture_output=True, text=True).stderr
    if 'black_start' in err:
        return 'tratto nero'
    if 'silence_start' in err:
        return 'silenzio di oltre 3 secondi'
    return ''


# ---------------------------------------------------------------- caricamento programmato
def orari_liberi(cfg, prod, dopo, n):
    orari = sorted({(int(m[0]), int(m[1])) for m in re.findall(r'(\d{1,2})[:.](\d{2})', str(cfg.get('shorts_orari') or '09:00, 13:00, 19:00, 21:30'))})
    presi = set(re.findall(r'@(\d{4}-\d\d-\d\d \d\d:\d\d)', ' '.join(str(r.get('shorts') or '') for r in prod)))
    out, giorno = [], dopo.date()
    while len(out) < n and giorno <= dopo.date() + dt.timedelta(days=4):
        for h, m in orari:
            q = dt.datetime(giorno.year, giorno.month, giorno.day, h, m, tzinfo=ROMA)
            if q > dopo and q.strftime('%Y-%m-%d %H:%M') not in presi and len(out) < n:
                out.append(q)
        giorno += dt.timedelta(days=1)
    return out


def carica(tk, f, x, cfg, riga, vid_lungo, quando):
    lingua = str(cfg.get('language') or 'en')[:2]
    link = 'Video completo' if lingua == 'it' else 'Full video'
    tag = [t.strip() for t in str(riga.get('tag_seo') or '').split(',') if t.strip()][:8]
    meta = {'snippet': {'title': (x['titolo'] or riga.get('titolo_italiano') or '')[:90].strip() + ' #shorts',
                        'description': f"{x['frase']}\n\n▶ {link}: https://youtu.be/{vid_lungo}\n\n#shorts",
                        'tags': tag, 'categoryId': str(cfg.get('youtube_category_id') or 27), 'defaultLanguage': lingua, 'defaultAudioLanguage': lingua},
            'status': {'privacyStatus': 'private', 'publishAt': quando.astimezone(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'selfDeclaredMadeForKids': False}}
    req = urllib.request.Request('https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status', data=json.dumps(meta).encode(),
                                 headers={'Authorization': 'Bearer ' + tk, 'Content-Type': 'application/json', 'X-Upload-Content-Type': 'video/mp4'})
    up = urllib.request.urlopen(req, timeout=60).headers['Location']
    req = urllib.request.Request(up, data=open(f, 'rb').read(), method='PUT', headers={'Authorization': 'Bearer ' + tk, 'Content-Type': 'video/mp4'})
    return json.loads(urllib.request.urlopen(req, timeout=900).read())['id']


def scrivi(fid, sch, h, n, colonna, valore):
    if colonna not in h:
        pr = next(x['properties'] for x in A.api(fid, 'GET', '?fields=sheets.properties')['sheets'] if x['properties']['title'] == sch)
        manca = len(h) + 1 - pr['gridProperties']['columnCount']
        if manca > 0:   # il foglio non ha abbastanza colonne: se ne aggiungono (altrimenti Google risponde 400)
            A.api(fid, 'POST', ':batchUpdate', {'requests': [{'appendDimension': {'sheetId': pr['sheetId'], 'dimension': 'COLUMNS', 'length': manca + 2}}]})
        A.api(fid, 'POST', '/values:batchUpdate', {'valueInputOption': 'RAW', 'data': [{'range': f"'{sch}'!{A.lettera(len(h) + 1)}1", 'values': [[colonna]]}]})
        h.append(colonna)
    A.api(fid, 'POST', '/values:batchUpdate', {'valueInputOption': 'RAW', 'data': [{'range': f"'{sch}'!{A.lettera(h.index(colonna) + 1)}{n}", 'values': [[valore]]}]})


def costo_registro(cid, costo, nota):
    os.makedirs('coach/costi', exist_ok=True)
    f = 'coach/costi/shorts.tsv'; nuovo = not os.path.exists(f)
    with open(f, 'a') as o:
        if nuovo:
            o.write('data\tcanale\tcosto_dollari\tnota\n')
        o.write(f"{time.strftime('%Y-%m-%d %H:%M')}\t{cid}\t{costo:.4f}\t{nota}\n")


# ---------------------------------------------------------------- canale
def canale(cfg):
    cid = str(cfg.get('channel_id') or '').strip()
    n_giorno = int(num(cfg.get('shorts_al_giorno')))
    budget = num(cfg.get('shorts_budget_giorno'))
    fid = str(cfg.get('scout_production_sheet_id') or '').strip()
    if not cid or n_giorno < 1 or not fid or (SOLO and cid != SOLO):
        return
    log('===', cid, f"| shorts_al_giorno={cfg.get('shorts_al_giorno')!r} shorts_orari={cfg.get('shorts_orari')!r} shorts_budget_giorno={cfg.get('shorts_budget_giorno')!r}")
    if budget <= 0:
        log('  shorts_budget_giorno vuota: niente Short (nessuna spesa senza il tuo ok)'); return
    sch, h, prod = A.righe(fid)
    oggi = dt.datetime.now(ROMA)
    chiave = str(cfg.get('chiave_youtube') or '').strip() or {'Storia in Minuti': 'YT_REFRESH_TOKEN_STORIA', 'KAO PSICOLOGIA': 'YT_REFRESH_TOKEN_KAO'}.get(cid, '') \
        or 'YT_REFRESH_TOKEN_' + re.sub(r'[^A-Z0-9]+', '_', cid.upper()).strip('_')
    rt = PF.SEGRETI.get(chiave) or E(chiave)
    if not rt:
        raise RuntimeError('manca il segreto ' + chiave)
    tk = PF.token(rt)[0]
    # gia' in coda: se ci sono abbastanza Short programmati nei prossimi giorni non se ne fanno altri (ritmo = shorts_al_giorno)
    futuri = [q for q in re.findall(r'@(\d{4}-\d\d-\d\d \d\d:\d\d)', ' '.join(str(r.get('shorts') or '') for r in prod)) if q > oggi.strftime('%Y-%m-%d %H:%M')]
    if not PROVA and not RIGA and len(futuri) >= 2 * n_giorno:
        log(f'  {len(futuri)} Short gia\' programmati: per ora basta'); return
    if RIGA:
        cand = [(int(RIGA), prod[int(RIGA) - 2])]
    else:
        cand = [(i + 2, r) for i, r in enumerate(prod) if (str(r.get('status')).strip() == 'Completato' and str(r.get('youtube_video_id') or '').strip()
                or PROVA and str(r.get('status')).strip() == 'Da caricare a mano') and not str(r.get('shorts') or '').strip()]   # in prova anche i video ancora da caricare a mano
        # i file dei video restano su GitHub 7 giorni: si parte dal video piu' recente e, se manca il file, si passa ai giorni prima
        cand = [x for x in cand if data_ini(x[1]) and (oggi - data_ini(x[1])).days < 7][::-1][:4]
    if not cand:
        log('  nessun video lungo da cui fare gli Short'); return
    video = None
    for n, riga in cand:
        vid = str(riga.get('youtube_video_id') or '').strip()
        video = scarica_sorgente(cid, n, riga, durata_yt(vid, tk) if vid else None, cfg)
        if video:
            break
        log(f'  riga {n}: file del video non trovato su GitHub')
        if not PROVA and not RIGA:
            scrivi(fid, sch, h, n, 'shorts', 'saltato: file del video non disponibile')
    if not video:
        return
    titolo = str(riga.get('titolo_italiano') or riga.get('titolo_originale') or '')
    log(f'  riga {n}: {titolo} | {durata(video) / 60:.1f} min')
    frasi, parole = trascrivi(video, str(cfg.get('language') or 'en'))
    momenti, costo = scegli(frasi, n_giorno, titolo, str(cfg.get('language') or 'en'), budget)
    if not momenti:
        raise RuntimeError('nessun momento valido scelto')
    fatti = []
    for k, x in enumerate(momenti, 1):
        f = monta(video, x, parole, os.path.join(LAV, f'short_{k}.mp4'), str(cfg.get('shorts_sottotitoli') or '').strip().upper() == 'SI')
        prob = controlla(f)
        log(f"  Short {k}: {x['a']:.0f}-{x['b']:.0f} s | {x['gancio']} | {x['titolo']}" + (f' | SCARTATO: {prob}' if prob else ''))
        if not prob:
            fatti.append((f, x))
    if PROVA:
        os.makedirs(OUT_PROVA, exist_ok=True)
        slug = re.sub(r'[^A-Za-z0-9]+', '_', cid).strip('_')
        fot = os.path.join('prove_video', 'shorts', slug); os.makedirs(fot, exist_ok=True)   # fotogrammi nel repository, da mostrare in chat
        for k, (f, x) in enumerate(fatti, 1):
            shutil.copy(f, os.path.join(OUT_PROVA, f'{slug}_{k}.mp4'))
            run(['ffmpeg', '-y', '-v', 'error', '-ss', '2.5', '-i', f, '-frames:v', '1', '-vf', 'scale=540:-2', os.path.join(fot, f'short_{k}.jpg')])
        for dove in (OUT_PROVA, fot):
          open(os.path.join(dove, f'{slug}_testi.txt'), 'w', encoding='utf-8').write(
            '\n\n'.join(f"Short {k}: {x['a']:.0f}-{x['b']:.0f} s\nGANCIO: {x['gancio']}\nTITOLO: {x['titolo']} #shorts\nDESCRIZIONE: {x['frase']}" for k, (f, x) in enumerate(fatti, 1)))
        costo_registro(cid, costo, f'prova, {len(fatti)} Short')
        return
    # uscita: dopo il video lungo (mai prima: il link porterebbe a un video non ancora pubblico)
    try:
        uscita_lungo = dt.datetime.strptime(str(riga.get('data_pubblicazione') or '')[:16], '%Y-%m-%d %H:%M').replace(tzinfo=ROMA)
    except Exception:
        uscita_lungo = oggi
    slot = orari_liberi(cfg, prod, max(oggi + dt.timedelta(minutes=45), uscita_lungo + dt.timedelta(minutes=30)), len(fatti))
    caricati = []
    for (f, x), q in zip(fatti, slot):
        sid = carica(tk, f, x, cfg, riga, str(riga.get('youtube_video_id')).strip(), q)
        caricati.append(f"{sid}@{q.strftime('%Y-%m-%d %H:%M')}")
        log('  caricato', sid, '| esce', q.strftime('%d/%m %H:%M'))
    scrivi(fid, sch, h, n, 'shorts', ' | '.join(caricati) or 'nessuno Short superato i controlli')
    costo_registro(cid, costo, f'{len(caricati)} Short caricati')


def main():
    os.makedirs(LAV, exist_ok=True)
    _, _, canali = A.righe(A.CONFIGS)
    if E('REGISTRA', '').strip():   # correzione a mano della colonna shorts: {"canale": {"riga": "valore"}}
        for cfg in canali:
            for n, v in json.loads(E('REGISTRA')).get(str(cfg.get('channel_id')), {}).items():
                fid = str(cfg.get('scout_production_sheet_id')).strip(); sch, h, _ = A.righe(fid)
                scrivi(fid, sch, h, int(n), 'shorts', v); log(cfg.get('channel_id'), 'riga', n, 'shorts =', v or '(vuota)')
        return
    errori = []
    for cfg in canali:
        try:
            canale(cfg)
        except Exception as e:
            log('  ERRORE', cfg.get('channel_id'), str(e)[:300]); errori.append(str(cfg.get('channel_id')))
        finally:
            shutil.rmtree(os.path.join(LAV, 'sorgente'), ignore_errors=True)
    if errori:
        sys.exit('Short non riusciti per: ' + ', '.join(errori))


if __name__ == '__main__':
    main()
