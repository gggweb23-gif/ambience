#!/usr/bin/env python3
"""MOTORE "COSTO VERO" (9 nov 2026, canale Costo Vero): quanto costa DAVVERO possedere qualcosa (auto, casa, cane, barca...), 9-10 minuti.
Stile approvato con la prova possesso v6: illustrazioni dipinte (FLUX.2 Klein), sempre lo stesso protagonista (la prima immagine fa da
riferimento), un'immagine nuova circa ogni 5 secondi (a ogni passo della grafica), grafica che spiega disegnata e animata in codice.
Regole di Giorgio: classe media italiana; SUV medio da circa 45.000 euro, mai l'auto in casa; benzina e carburante MAI nei costi;
i numeri a schermo li calcola il codice (totale = somma delle voci, costo vero = totale - rivendita, al mese, al giorno) e il copione
viene controllato PRIMA di spendere (prezzo = primo valore, rate >= prezzo, costo vero realistico, niente carburante, parole sufficienti).
Budget: colonna coach_budget_video / budget_video (euro). Se le immagini non ci stanno, l'intervallo tra le immagini si allunga (mai superato).
Copertina stile 3 "scontrino" con la scritta fissa QUANTO COSTA?, posizione che cambia da un video all'altro (MANO LIBERA).
SECCO=SI: prova a secco GRATIS (copione finto, niente Claude, niente voce, niente immagini AI)."""
import io, json, math, multiprocessing as mp, os, random, re, shutil, subprocess, sys, time
from PIL import Image, ImageDraw

ROOT = os.getcwd()
QUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, QUI); sys.path.insert(0, os.path.join(QUI, 'strumenti'))
LAV = os.path.join(ROOT, 'lavoro_possesso'); os.makedirs(LAV, exist_ok=True)
os.environ.setdefault('COSTI_FILE', os.path.join(LAV, 'costi_video.jsonl'))
import costi as CO
import iscrizione as ISC
import motore_yt as YT
import prova_possesso6 as PV

E = os.environ.get
P = json.loads(E('PAYLOAD') or '{}') or {}
RIGA = P.get('riga') or {}
SECCO = str(E('SECCO') or 'NO').upper() == 'SI'
PROVA = SECCO or str(E('PROVA') or P.get('prova') or 'NO').upper() == 'SI'
CARICA = str(E('CARICA') or 'NO').upper() == 'SI'
VOCE = str(E('VOCE') or P.get('voice_id') or 'glnsgBC77wt5zOYU0szz').strip()   # voce di Quanto Ti Resta (scelta da Giorgio)
VOCE_MOD = str(P.get('voice_model_id') or 'eleven_multilingual_v2')
LINGUA = str(P.get('language') or 'it')[:2]
TITOLO = str(E('TEMA') or RIGA.get('titolo_italiano') or RIGA.get('titolo_originale') or '').strip()
OGGETTO = str(RIGA.get('oggetto') or '').strip()
VOCI_COSTO = str(RIGA.get('voci_costo') or '').strip()
W, H, FPS = PV.W, PV.H, PV.FPS
log = YT.log
MODELLO = 'claude-sonnet-5-5'
SEC_IMG = 4.0   # 9 nov sera (Giorgio: "il ritmo e' lento"): un'immagine nuova ogni 4 secondi (se il budget lo permette)
MIN_PAROLE, MAX_PAROLE = 1500, 1650   # 9-10 minuti con la voce accelerata come Quanto Ti Resta


def num(x, d=0.0):
    try:
        return float(str(x).replace(',', '.'))
    except Exception:
        return d


BUDGET_USD = (num(P.get('coach_budget_video')) or num(P.get('budget_video')) or 1.5) * 1.08
AUTO = bool(re.search(r'\b(suv|auto|macchina|utilitaria|berlina|station wagon)\b', (TITOLO + ' ' + OGGETTO).lower()))


def durata(f):
    return float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f]).decode().strip())


def claude(prompt, sforzo='medium', max_tokens=32000):
    dati = {'model': MODELLO, 'max_tokens': max_tokens, 'thinking': {'type': 'between_tools'}, 'output_config': {'effort': sforzo},
            'messages': [{'role': 'user', 'content': prompt}]}
    for k in range(4):
        try:
            j = YT.http('https://api.anthropic.com/v1/messages', dati, {'x-api-key': E('ANTHROPIC_API_KEY', ''), 'anthropic-version': '2023-06-01'}, timeout=900)
            CO.registra('claude', MODELLO, usage=j.get('usage'))
            t = ''.join(b.get('text', '') for b in j['content'] if b.get('type') == 'text')
            if '{' in t:
                return t
        except Exception as e:
            log('Claude non risponde, riprovo:', str(e)[:150])
        time.sleep(10 * (k + 1))
    raise RuntimeError('Claude non risponde')


def leggi_json(t):
    m = re.search(r'\{.*\}', t, re.S).group(0)
    try:
        return json.loads(m)
    except Exception:
        from json_repair import repair_json
        return json.loads(repair_json(m))


# ============================================================ 1) COPIONE (controllato prima di spendere)
STRUTTURA = """Scene in quest'ordine (tipo e dati):
1. "cartellino": GANCIO FORTE nei primi 15 secondi (circa 35 parole): prima LA FINE, poi si spiega come ci si arriva. Il prezzo sul cartellino,
   SUBITO il costo vero e quanto costa al mese, poi la promessa ("ti mostro voce per voce da dove esce questo numero"). Niente introduzioni lente.
   dati {"prezzo": <prezzo>, "costo_vero": <costo vero = somma delle voci dei dettagli - rivendita>, "al_mese": <costo vero / mesi, arrotondato>, "domanda": "MA QUANTO COSTA DAVVERO?"}
2. "racconto": max 40 parole, veloce: il protagonista e la sua scelta (la trappola in cui cadono tutti).
3-8. "dettaglio" (una scena per OGNI voce di spesa, 4-6 scene): dati {"nome": "Assicurazione", "per_anno": <euro all'anno>, "anni": <anni>, "nota": "max 6 parole"}
   (per le rate: "per_anno" = rata annua, il totale rate + interessi e' SEMPRE piu' del prezzo per un acquisto a rate). Spiega bene perche' costa cosi'.
9. "scontrini": il riepilogo di tutte le voci. dati {"anni": <anni>} (le voci le prende il programma dalle scene "dettaglio")
10. "valore": quanto vale la cosa anno per anno. dati {"valori": [<prezzo>, <valore dopo 1 anno>, ...]} (da oggi all'ultimo anno; l'ultimo e' la rivendita)
11. "calcolo": costo vero = totale pagato - rivendita; poi al mese e al giorno. dati {} (i numeri li calcola il programma)
12. "confronto": un'alternativa concreta (es. usato vs nuovo, leasing vs acquisto, adozione vs allevamento). dati {"titolo": "max 5 parole", "a": ["nome", "<euro>"], "b": ["nome", "<euro>"]}
13. "consigli": 5 trucchi concreti per spendere meno. dati {"voci": ["max 5 parole", ...]}
14. "prossimo": gancio alla prossima puntata e invito a iscriversi. dati {"testo": "PROSSIMA PUNTATA: ..."}"""


def controlla(c):
    """Controllo dei numeri e delle regole PRIMA di spendere in immagini e voce. Ritorna la lista dei problemi (vuota = ok)."""
    prob = []
    try:
        S_ = {}
        for x in c['scene']:
            S_.setdefault(x['tipo'], []).append(x.get('dati') or {})
        prezzo = num(S_['cartellino'][0].get('prezzo')); val = [num(v) for v in S_['valore'][0]['valori']]
        cv_g = num(S_['cartellino'][0].get('costo_vero'))
        det = [(str(d.get('nome') or ''), num(d.get('per_anno')) * num(d.get('anni'))) for d in S_['dettaglio']]
        tot = sum(v for _, v in det); rate = sum(v for n, v in det if re.search(r'rat|finanz|mutuo', n.lower()))
        if len(det) < 4:
            prob.append(f'servono almeno 4 scene "dettaglio" (una per voce di spesa), ce ne sono {len(det)}')
        if abs(prezzo - val[0]) > 1:
            prob.append(f'il prezzo del cartellino ({prezzo:.0f}) deve essere uguale al primo valore ({val[0]:.0f})')
        if rate and rate < prezzo * .95 and not re.search(r'mutuo', TITOLO.lower()):
            prob.append(f'rate + interessi ({rate:.0f}) non possono essere meno del prezzo ({prezzo:.0f})')
        if tot - val[-1] < prezzo * .3:
            prob.append(f'costo vero ({tot - val[-1]:.0f}) irrealistico rispetto al prezzo ({prezzo:.0f})')
        if any(re.search(r'benzin|carbur|gasolio|ricaric|pieno', n.lower()) for n, _ in det):
            prob.append('la benzina / il carburante / la ricarica NON vanno mai nei costi (regola di Giorgio)')
        anni = {num(d.get('anni')) for d in S_['dettaglio']}
        if len(anni) > 1:
            prob.append(f'tutte le voci devono usare lo stesso numero di anni ({sorted(anni)})')
        if anni and len(val) - 1 != int(list(anni)[0]):
            prob.append(f'i valori anno per anno ({len(val)}) devono essere anni + 1 ({int(list(anni)[0]) + 1})')
        if abs(cv_g - (tot - val[-1])) > max(50, (tot - val[-1]) * .01):   # il gancio dice la fine: deve essere il numero giusto
            prob.append(f'il costo vero del gancio ({cv_g:.0f}) deve essere uguale a somma delle voci - rivendita ({tot - val[-1]:.0f})')
        parole = sum(len(str(x.get('voce') or '').split()) for x in c['scene'])
        if parole < MIN_PAROLE - 60:
            prob.append(f'il copione ha {parole} parole: ne servono {MIN_PAROLE}-{MAX_PAROLE} (video di 9-10 minuti)')
    except Exception as e:
        prob.append(f'struttura dati non valida: {e}')
    return prob


def copione():
    if SECCO:
        return copione_finto()
    f = os.path.join(LAV, 'copione.json')
    if os.path.exists(f):
        log('copione ripreso'); return json.load(open(f))
    regole_auto = (' Per l\'auto: un SUV medio nuovo da circa 45.000 euro (salvo diverso titolo), comprato a rate.' if AUTO else '')
    prompt = f"""Scrivi il copione di un video YouTube italiano di 9-10 minuti ({MIN_PAROLE}-{MAX_PAROLE} parole parlate in tutto) per il canale "Costo Vero"
("Quanto costa DAVVERO possedere le cose?"). Titolo (tienilo): "{TITOLO}". Cosa: {OGGETTO or TITOLO}. Voci di spesa da coprire: {VOCI_COSTO or 'quelle realistiche'}.
Numeri realistici italiani 2026, arrotondati, per un italiano di classe media.{regole_auto} Un protagonista con nome italiano che torna in tutto il video.
NON includere MAI benzina, carburante, ricarica o consumi d'uso (regola di Giorgio): solo i costi di possesso. Mai cifre troppo basse.
Tono: chiaro, curioso, mai noioso; frasi brevi; numeri scritti in lettere nella voce; mai correzioni a voce. Fai TUTTI i conti prima di scrivere e ricontrollali.
{STRUTTURA}
Per OGNI scena: "tipo", "capitolo" (max 4 parole, per i capitoli della descrizione), "voce" (testo parlato), "dati", "sfondi".
"sfondi" = lista di immagini in INGLESE, UNA ogni 12 parole circa della voce (un'immagine nuova ogni 5 secondi), nell'ordine in cui la voce ne parla.
Ogni immagine: {{"persone": true/false, "descr": "...", "frase": "max 5 parole in italiano MAIUSCOLE che riassumono quel momento"}}.
persone=true solo con il protagonista (stesso viso e vestiti); persone=false = oggetti e luoghi SENZA persone{' e SENZA automobili' if AUTO else ''}
(es. polizza e chiavi su un tavolo, bollettino e penna, salvadanaio, calcolatrice, attrezzi in officina, ciotola e guinzaglio, documenti del notaio).
{'Il SUV compare SOLO nelle immagini con persone=true, sempre all aperto, in salone o in officina, mai in casa, sempre di lato o di tre quarti da dietro.' if AUTO else ''}
Almeno 75% delle immagini con persone=false. Mai immagini di fogli scritti, scontrini, banconote, schermi o cartelli (le scritte escono illeggibili): oggetti semplici (chiavi, salvadanaio, monete, calcolatrice, gomme, attrezzi, garage, strade). Tutto da classe media italiana.
Aggiungi: "titolo", "descrizione" (2 brevi paragrafi per YouTube, in italiano), "tag" (12-15 tag in italiano), "protagonista" (descrizione fisica in inglese: eta', capelli, vestiti),
"riferimento" (in inglese: il protagonista accanto alla cosa, all'aperto o nel posto giusto), "copertina": {{"oggetto": "in inglese: la cosa grande e ben visibile, sfondo semplice"}}.
Rispondi SOLO con JSON: {{"titolo": "...", "descrizione": "...", "tag": [...], "protagonista": "...", "riferimento": "...", "copertina": {{...}}, "scene": [...]}}"""
    errore = ''
    for tentativo in range(3):
        c = leggi_json(claude(prompt + errore, sforzo='low'))   # 9 nov: sforzo basso (i conti li controlla il programma): Claude costava 0,46 $
        prob = controlla(c)
        if not prob:
            break
        log('copione scartato:', prob); errore = '\n\nATTENZIONE, il tentativo precedente era sbagliato: ' + '; '.join(prob) + '. Rifai tutti i conti e correggi.'
    else:
        raise RuntimeError('copione con numeri non coerenti dopo 3 tentativi: ' + '; '.join(prob))
    json.dump(c, open(f, 'w'), ensure_ascii=False, indent=1)
    return c


def copione_finto():
    v = 'Questa e una frase di prova per controllare i tempi del montaggio del video. '
    sf = lambda n, p=False: [{'persone': p, 'descr': 'test', 'frase': f'FRASE DI PROVA {k + 1}'} for k in range(n)]
    det = [('Rate + interessi', 9800, 5), ('Assicurazione', 900, 5), ('Bollo', 420, 5), ('Tagliandi e gomme', 650, 5)]
    S = [{'tipo': 'cartellino', 'capitolo': 'Il prezzo', 'voce': v * 2, 'dati': {'prezzo': 45000, 'costo_vero': 37850}, 'sfondi': sf(4, True)},
         {'tipo': 'racconto', 'capitolo': 'La scelta', 'voce': v * 3, 'dati': {}, 'sfondi': sf(6)}]
    S += [{'tipo': 'dettaglio', 'capitolo': n, 'voce': v * 2, 'dati': {'nome': n, 'per_anno': a, 'anni': y, 'nota': 'nota di prova'}, 'sfondi': sf(4)} for n, a, y in det]
    S += [{'tipo': 'scontrini', 'capitolo': 'Riepilogo', 'voce': v * 2, 'dati': {'anni': 5}, 'sfondi': sf(4)},
          {'tipo': 'valore', 'capitolo': 'Il valore', 'voce': v * 2, 'dati': {'valori': [45000, 37000, 31000, 27000, 24000, 21000]}, 'sfondi': sf(4)},
          {'tipo': 'calcolo', 'capitolo': 'Il costo vero', 'voce': v * 2, 'dati': {}, 'sfondi': sf(4)},
          {'tipo': 'confronto', 'capitolo': 'Alternativa', 'voce': v * 2, 'dati': {'titolo': 'Usato contro nuovo', 'a': ['Nuovo', '45.000'], 'b': ['Usato 3 anni', '29.000']}, 'sfondi': sf(4)},
          {'tipo': 'consigli', 'capitolo': 'Come risparmiare', 'voce': v * 3, 'dati': {'voci': ['Confronta le assicurazioni', 'Anticipo piu alto', 'Tagliando fuori rete', 'Gomme quattro stagioni', 'Tienila piu anni']}, 'sfondi': sf(6)},
          {'tipo': 'prossimo', 'capitolo': 'Prossima puntata', 'voce': v, 'dati': {'testo': 'PROSSIMA PUNTATA: IL CANE'}, 'sfondi': sf(2)}]
    return {'titolo': TITOLO or 'Prova a secco', 'descrizione': 'Prova.', 'tag': ['prova'], 'protagonista': 'test', 'riferimento': 'test', 'copertina': {'oggetto': 'test'}, 'scene': S}


def numeri(c):
    """Tutti i numeri a schermo calcolati dal programma (mai incoerenti)."""
    S = c['scene']
    det = [x['dati'] for x in S if x['tipo'] == 'dettaglio']
    voci = [(str(d.get('nome') or ''), num(d.get('per_anno')) * num(d.get('anni'))) for d in det]
    anni = int(num(det[0].get('anni'), 5)) if det else 5
    valori = [num(v) for v in next(x for x in S if x['tipo'] == 'valore')['dati']['valori']]
    tot = sum(v for _, v in voci); cv = tot - valori[-1]
    prezzo = num(next(x for x in S if x['tipo'] == 'cartellino')['dati'].get('prezzo')) or valori[0]
    return {'prezzo': prezzo, 'voci': voci, 'anni': anni, 'valori': valori, 'totale': tot, 'rivendita': valori[-1], 'costo_vero': cv,
            'mese': cv / (anni * 12), 'giorno': cv / (anni * 365)}


# ============================================================ 2) IMMAGINI
STILE_GEN = ('DIGITAL PAINTED ILLUSTRATION, NOT a photograph: warm editorial illustration style with soft painted shading, consistent in every image. '
             'Everything is ORDINARY ITALIAN MIDDLE CLASS: modest apartments and kitchens, ordinary neighbourhoods, normal clothes. '
             'Premium editorial illustration for an Italian personal-finance YouTube explainer, semi-realistic 2.5D style, warm cinematic light, Italian setting. '
             'Keep the LEFT 50% of the frame calm and uncluttered (soft background only) because graphics go there; main subject on the RIGHT half. '
             'Absolutely no text, no letters, no numbers, no logos, no brand, no shop signs, no license plates. ')
STILE_OGG = PV.STILE_OGGETTI if AUTO else PV.STILE_OGGETTI.replace('NO people, NO cars, NO vehicles anywhere in the image', 'NO people anywhere in the image')
SPESA = [0.0]


def fal(endpoint, dati):
    hd = {'Authorization': 'Key ' + E('FAL_KEY', '')}
    inv = YT.http('https://queue.fal.run/' + endpoint, dati, hd, timeout=120)
    for _ in range(150):
        time.sleep(2)
        if YT.http(inv['status_url'], headers=hd, timeout=60).get('status') == 'COMPLETED':
            break
    return YT.http(inv['response_url'], headers=hd, timeout=60)['images'][0]['url']


def immagine(f, prompt, rif=None):
    """Una illustrazione 1280x720 (testo-immagine circa 0,009 $; con il protagonista, partendo dal riferimento, circa 0,017 $)."""
    if os.path.exists(f):
        return f
    if SECCO:
        random.seed(f); im = Image.new('RGB', (W, H), tuple(random.randint(90, 200) for _ in range(3)))
        ImageDraw.Draw(im).ellipse((1150, 250, 1650, 750), fill=(240, 240, 240)); im.save(f, quality=90); return f
    for k in range(3):
        try:
            if rif:
                url = fal(PV.KLEIN_EDIT, {'prompt': prompt, 'image_urls': [rif], 'image_size': {'width': 1280, 'height': 720}, 'num_images': 1, 'output_format': 'jpeg'})
                CO.registra('fal', 'flux-2-klein-4b-edit', dollari=PV.PREZZO['edit'])
            else:
                url = fal(PV.KLEIN_T2I, {'prompt': prompt, 'image_size': {'width': 1280, 'height': 720}, 'num_images': 1, 'output_format': 'jpeg'})
                CO.registra('fal', 'flux-2-klein-4b', dollari=PV.PREZZO['t2i'])
            im = Image.open(io.BytesIO(YT.http(url, raw=True, timeout=120))).convert('RGB')
            from PIL import ImageStat
            if max(ImageStat.Stat(im.resize((64, 36))).mean) < 18:   # immagine nera (filtro di sicurezza del fornitore): si rifa', mai uno sfondo nero nel video
                log('immagine nera scartata, la rifaccio'); prompt = prompt + ' Bright, warm daylight scene.'; continue
            from PIL import ImageFilter
            im.resize((W, H), Image.LANCZOS).filter(ImageFilter.UnsharpMask(radius=2, percent=70, threshold=2)).save(f, quality=95)   # ingrandita e resa nitida
            return f, url
        except Exception as e:
            log('immagine non riuscita, riprovo:', str(e)[:150]); time.sleep(5)
    return None


def piano_immagini(c, durate):
    """Quante immagini per scena: una ogni 5 s; se il budget non basta, l'intervallo si allunga (mai oltre il budget)."""
    tutte = [x for s in c['scene'] for x in (s.get('sfondi') or [])]
    p_cop = 0.009; claude_usd = CO.totale()
    quota_persone = sum(1 for x in tutte if x.get('persone')) / max(1, len(tutte))
    medio = quota_persone * PV.PREZZO['edit'] + (1 - quota_persone) * PV.PREZZO['t2i']
    sec = SEC_IMG
    while True:
        n = sum(max(1, math.ceil(d / sec)) for d in durate)
        if claude_usd + p_cop + PV.PREZZO['t2i'] + n * medio <= BUDGET_USD or sec >= 9:
            break
        sec += .5
    if sec > SEC_IMG:
        log(f'budget: un\'immagine ogni {sec:.1f} s (invece di {SEC_IMG:.0f}) per restare sotto {BUDGET_USD / 1.08:.2f} euro')
    return sec


# ============================================================ 3) GRAFICA (tipi nuovi + quelli della prova v6)
INK, Y, R, G, BL, BIANCO, GRIGIO = PV.INK, PV.Y, PV.R, PV.G, PV.BL, PV.BIANCO, PV.GRIGIO
eur, pannello, scritta, ease, cl, pop = PV.eur, PV.pannello, PV.scritta, PV.ease, PV.cl, PV.pop


def frase(im, testo, t, d):
    """La frase del momento in basso a sinistra: entra, si scrive a macchina e si sottolinea (sempre qualcosa che succede)."""
    testo = str(testo or '').upper().strip()
    if not testo:
        return
    a = ease(t / .35); n = int(max(0, t - .2) * 30)
    pannello(im, (90, 880, 90 + 40 + PV.F(64).getlength(testo[:28]) + 40, 990), INK + (235,), alpha=a)
    scritta(im, (130, 896), testo[:n][:28], 64, BIANCO, alpha=a)
    u = ease((t - .25 - len(testo) / 30) / .35)
    if u > 0:
        ImageDraw.Draw(im).line((130, 978, 130 + (PV.F(64).getlength(testo[:28])) * u, 978), fill=Y, width=6)


def grafica(im, sc, t, d, dati, passo_t, passo_d, passo_i):
    tipo = sc['tipo']; dd = sc.get('dati') or {}
    sf = (sc.get('sfondi') or [{}])
    fr_txt = (sf[min(passo_i, len(sf) - 1)] or {}).get('frase') if sf else ''
    sl = lambda a: int(-700 * (1 - ease((t - a) / .45)))
    if tipo == 'cartellino':   # GANCIO: prima la fine (Giorgio, 9 nov sera)
        x = sl(.1)
        pannello(im, (100 + x, 120, 760 + x, 400), (255, 255, 255, 245))
        scritta(im, (140 + x, 150), 'PREZZO SUL CARTELLINO', 44, GRIGIO)
        scritta(im, (140 + x, 215), eur(dati['prezzo']), 130, INK, maxw=580)
        u = ease((t - .9) / .3)
        if u > 0:
            ImageDraw.Draw(im).line((130 + x, 360, 130 + x + 600 * u, 250), fill=R, width=14)
        q = pop((t - 1.3) / .4)
        if q:
            pannello(im, (100, 450, 100 + 860 * min(q, 1.05), 720), R + (255,))
            if q > .9:
                k = ease((t - 1.5) / 1.2)
                scritta(im, (140, 470), 'COSTO VERO', 56, BIANCO)
                scritta(im, (140, 540), eur(dati['costo_vero'] * k), 140, BIANCO, maxw=780)
        if t > 3.2:
            a = ease((t - 3.2) / .3)
            pannello(im, (100, 770, 760, 900), Y + (255,), alpha=a)
            scritta(im, (140, 785), f"{eur(dati['mese'])} AL MESE", 90, INK, alpha=a, maxw=580)
        return
    if tipo == 'racconto':
        frase(im, fr_txt, passo_t, passo_d); return
    if tipo == 'dettaglio':
        x = sl(.2); tot = num(dd.get('per_anno')) * num(dd.get('anni'))
        pannello(im, (100 + x, 150, 960 + x, 640), (255, 255, 255, 245))
        scritta(im, (140 + x, 185), str(dd.get('nome') or '').upper(), 64, INK, maxw=780)
        scritta(im, (140 + x, 290), eur(num(dd.get('per_anno')) * ease((t - .5) / .8)) + ' ALL\'ANNO', 80, GRIGIO, maxw=780)
        k = ease((t - d * .35) / .9)
        if k > 0:
            scritta(im, (140 + x, 400), f"x {int(num(dd.get('anni')))} ANNI =", 60, GRIGIO, alpha=cl(k * 2))
            scritta(im, (140 + x, 470), eur(tot * k), 120, R, alpha=cl(k * 2), maxw=780)
            u = ease((t - d * .35 - .9) / .35)
            if u > 0:
                ImageDraw.Draw(im).line((140 + x, 610, 140 + x + 760 * u, 610), fill=Y, width=8)
        if dd.get('nota') and t > d * .6:
            frase(im, dd['nota'], t - d * .6, d * .4)
        return
    if tipo == 'confronto':
        a_, b_ = (dd.get('a') or ['', '']), (dd.get('b') or ['', ''])
        pannello(im, (90, 140, 1010, 230), INK + (255,), alpha=ease(t / .3))
        scritta(im, (130, 152), str(dd.get('titolo') or 'CONFRONTO').upper(), 60, Y, alpha=ease(t / .3), maxw=840)
        for k, (n_, v_, col, st) in enumerate(((a_[0], a_[1], BL, .5), (b_[0], b_[1], G, d * .4))):
            q = pop((t - st) / .4)
            if not q:
                continue
            x0 = 90 + k * 470
            pannello(im, (x0, 270, x0 + 440 * min(q, 1.05), 640), (255, 255, 255, 245))
            if q > .9:
                scritta(im, (x0 + 30, 300), str(n_).upper(), 50, GRIGIO, maxw=380)
                v = str(v_).replace('€', '').strip()
                v = eur(num(v.replace('.', ''))) if re.fullmatch(r'[\d.]+', v) else (v + ' €')
                scritta(im, (x0 + 30, 400), v, 96, col, maxw=380)
        if t > d * .75:
            frase(im, fr_txt, t - d * .75, d * .25)
        return
    if tipo == 'consigli':
        V = (dd.get('voci') or [])[:5]; x = sl(0)
        pannello(im, (90 + x, 110, 1010 + x, 260 + 112 * len(V)), (255, 255, 255, 245))
        scritta(im, (130 + x, 135), 'COME SPENDERE MENO', 62, INK)
        for i, v in enumerate(V):
            a = pop((t - .5 - i * d * .17) / .35)
            if not a:
                continue
            y = 235 + i * 112
            ImageDraw.Draw(im).ellipse((130 + x, y + 8, 190 + x, y + 68), fill=G)
            ImageDraw.Draw(im).line((145 + x, y + 38, 157 + x, y + 52, 177 + x, y + 24), fill=BIANCO, width=8)
            scritta(im, (215 + x, y + 6), str(v), 56, INK, alpha=cl(a), maxw=760)
        return
    PV.grafica(im, sc, t, d, dati)   # cartellino, scontrini, valore, calcolo, prossimo: come nella prova approvata


def muovi(bg, t, d, i):
    """Movimento dello sfondo piu' vivo della v6 (9 nov sera, "ritmo lento"): spinta 1,00 -> 1,10 alternata dentro/fuori + scorrimento laterale."""
    k = t / max(d, .1); k = k if i % 2 == 0 else 1 - k
    z = 1 + .10 * k; w, h = int(W / z), int(H / z)
    x0 = int((W - w) * (.5 + (.35 if i % 3 else -.35) * (k - .5))); y0 = int((H - h) * (.5 + .2 * (k - .5)))
    return bg.crop((x0, y0, x0 + w, y0 + h)).resize((W, H), Image.BICUBIC).convert('RGBA')


SCENE, DATI, ATEMPO = [], {}, 1.0


def rendi_scena(i):
    """Una scena in un file mp4: sfondi che cambiano ogni ~5 s con dissolvenza + grafica animata. In parallelo (4 scene alla volta)."""
    s = SCENE[i]; out = s['_out']; d = s['_dur']
    if os.path.exists(out) and os.path.getsize(out) > 1000:
        return out
    bgs = [Image.open(f).convert('RGB') for f in s['_img']]
    n = len(bgs); p = d / n
    enc = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                            '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p', out], stdin=subprocess.PIPE)
    for k in range(int(round(d * FPS))):
        t = k / FPS; j = min(n - 1, int(t / p)); tl = t - j * p
        fr = muovi(bgs[j], tl, p, i + j)
        if j > 0 and tl < .25:
            fr = Image.blend(muovi(bgs[j - 1], p, p, i + j - 1), fr, tl / .25)
        grafica(fr, s, t, d, DATI, tl, p, j)
        enc.stdin.write(fr.convert('RGB').tobytes())
    enc.stdin.close(); enc.wait()
    return out


# ============================================================ 4) VOCE
def voce(i, testo, prima, dopo):
    f = os.path.join(LAV, f'voce_{i:02d}.mp3')
    if os.path.exists(f) and os.path.getsize(f) > 500:
        return f
    if SECCO:
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=mono', '-t', f'{max(3, len(testo.split()) / 2.4):.2f}', f], check=True)
        return f
    for k in range(4):
        try:
            b = YT.http(f'https://api.elevenlabs.io/v1/text-to-speech/{VOCE}?output_format=mp3_44100_128',
                        {'text': testo, 'model_id': VOCE_MOD, 'previous_text': prima[-400:], 'next_text': dopo[:400],
                         'voice_settings': {'stability': .45, 'similarity_boost': .8, 'style': .2}}, {'xi-api-key': E('ELEVENLABS_API_KEY', '')}, timeout=300, raw=True)
            open(f, 'wb').write(b); CO.registra('elevenlabs', VOCE_MOD, crediti=len(testo))
            return f
        except Exception as e:
            log('voce non riuscita, riprovo:', str(e)[:150]); time.sleep(5 * (k + 1))
    raise RuntimeError('ElevenLabs non risponde')


# ============================================================ 5) COPERTINA (stile 3 scontrino, QUANTO COSTA? fisso)
def scontrino_libero(CP, img, vero, k):
    """Copertina stile 3 "scontrino" a MANO LIBERA (9 nov sera, Giorgio): lato dello scontrino, inclinazione, altezza e posizione/grandezza di
    QUANTO COSTA? cambiano da un video all'altro. Regola per tutti i canali: MAI scritte nell'angolo in basso a destra (lo copre la durata del video)."""
    from PIL import ImageFilter
    W_, H_ = CP.W, CP.H
    im = img.copy().convert('RGBA')
    sx = k % 2 == 0                       # scontrino a sinistra o a destra
    alto = (k // 2) % 2 == 0              # scritta in alto o a meta' altezza
    ang = (5, -7, 4, -5)[k % 4] * (1 if sx else -1); dy = (-10, 30, 0, 50)[(k // 3) % 4]
    sc = Image.new('RGBA', (420, 760), (250, 248, 240, 255)); d = ImageDraw.Draw(sc)
    for i in range(0, 420, 20):
        d.polygon([(i, 0), (i + 10, 14), (i + 20, 0)], fill=(0, 0, 0, 0))
    d.text((210, 70), 'SCONTRINO', font=CP.F(44), fill=CP.NERO, anchor='mm')
    for j in range(5):
        d.line((40, 140 + j * 70, 380, 140 + j * 70), fill=(200, 200, 200), width=4)
        d.rectangle((40, 115 + j * 70, 40 + 120 + (j * 37 + k * 11) % 120, 130 + j * 70), fill=(150, 150, 150))
    d.text((210, 520), 'TOTALE', font=CP.F(54), fill=CP.NERO, anchor='mm')
    s_ = CP.adatta(vero, 90, 380); d.text((210, 610), vero, font=CP.F(s_), fill=CP.ROSSO, anchor='mm')
    sc = sc.rotate(ang, expand=True, resample=Image.BICUBIC)
    ombra = Image.new('RGBA', sc.size, (0, 0, 0, 0)); ombra.putalpha(sc.split()[3].point(lambda a: int(a * .5)))
    x = -30 if sx else W_ - sc.width + 30
    im.alpha_composite(ombra.filter(ImageFilter.GaussianBlur(14)), (x + 14, dy + 10)); im.alpha_composite(sc, (x, dy - 10))
    d = ImageDraw.Draw(im)
    size = (104, 92, 116)[k % 3]
    # la scritta va dal lato opposto allo scontrino, in alto o a meta' altezza: mai sotto H-170 (il timer della copertina)
    y1 = 50 if alto else H_ // 2 - size - 20
    if sx:   # scontrino a sinistra -> scritta a destra, allineata a destra ma lontana dal basso
        tx, anc = W_ - 50, 'ra'
    else:
        tx, anc = 50, 'la'
    CP.scritta_bordo(d, (tx, y1), 'QUANTO', size, CP.BIANCO, anchor=anc)
    CP.scritta_bordo(d, (tx, y1 + size + 10), 'COSTA?', size, CP.GIALLO, anchor=anc)
    assert y1 + 2 * size + 10 < H_ - 170
    return im.convert('RGB')


def copertina(c, rif_url):
    import copertine_possesso as CP
    f = os.path.join(LAV, 'copertina_sfondo.jpg')
    ogg = str((c.get('copertina') or {}).get('oggetto') or OGGETTO or TITOLO)
    immagine(f, CP.STILE + ogg + ', filling the frame, simple warm gradient background')
    if not os.path.exists(f):
        f = os.path.join(LAV, 'riferimento.jpg')
    img = Image.open(f).convert('RGB').resize((CP.W, CP.H))
    k = int(num(P.get('riga_produzione'), 0) or random.randint(0, 9))
    cop = scontrino_libero(CP, img, eur(DATI['costo_vero']), k)
    out = os.path.join(ROOT, 'copertina.jpg'); cop.save(out, quality=92)
    return out


# ============================================================ MAIN
def main():
    global SCENE, DATI, ATEMPO
    if not TITOLO and not SECCO:
        raise RuntimeError('manca il titolo della riga')
    c = copione(); SCENE = c['scene']
    # la scena "scontrini" prende le voci dalle scene "dettaglio" (i conti tornano sempre)
    DATI = numeri(c)
    for s in SCENE:
        if s['tipo'] == 'scontrini':
            s['dati'] = dict(s.get('dati') or {}, voci=[[n, v] for n, v in DATI['voci']], anni=DATI['anni'])
    log('numeri:', {k: (round(v) if isinstance(v, float) else v) for k, v in DATI.items() if k != 'voci'})
    # voce
    for i, s in enumerate(SCENE):
        v = voce(i, str(s['voce']), ' '.join(str(x['voce']) for x in SCENE[:i]), ' '.join(str(x['voce']) for x in SCENE[i + 1:]))
        s['_voce'] = v; s['_nat'] = durata(v); s['_out'] = os.path.join(LAV, f'scena_{i:02d}.mp4')
    # ritmo della voce come Quanto Ti Resta (9 nov sera, Giorgio: "Quanto Ti Resta ha un bel ritmo, Costo Vero e' piu' lento"):
    # stessa velocita' di lettura (colonna voce_ritmo, caratteri al secondo; vuota = 16,5) accelerando la voce fino a +15%
    car = sum(len(str(s['voce'])) for s in SCENE); nat = sum(s['_nat'] for s in SCENE)
    ATEMPO = max(1.0, min(1.15, (num(P.get('voce_ritmo'), 16.5) or 16.5) / max(1.0, car / max(nat, 1))))
    for s in SCENE:
        s['_dur'] = round(s['_nat'] / ATEMPO + .25, 3)
    log(f'voce: {car / max(nat, 1):.1f} caratteri/s naturali -> accelerata x{ATEMPO:.3f}')
    tot_voce = sum(s['_dur'] for s in SCENE)
    log(f'voce: {tot_voce / 60:.1f} minuti')
    if tot_voce < 480 and not SECCO:
        raise RuntimeError(f'video di {tot_voce / 60:.1f} minuti: sotto gli 8 minuti (copione troppo corto)')
    # immagini: una ogni ~5 s (dentro il budget); la prima e' il riferimento del protagonista
    sec = piano_immagini(c, [s['_dur'] for s in SCENE])
    prot = c.get('protagonista') or ''
    stile = STILE_GEN + (PV.STILE[PV.STILE.index('The car is'):PV.STILE.index('modest apartments')] if AUTO else '')
    r = immagine(os.path.join(LAV, 'riferimento.jpg'), stile + f'Main character: {prot}. Scene: {c.get("riferimento") or "the main character with the thing"}')
    rif_url = r[1] if isinstance(r, tuple) else None
    n_img = 0
    for i, s in enumerate(SCENE):
        n = max(1, math.ceil(s['_dur'] / sec)); sf = list(s.get('sfondi') or [])
        while len(sf) < n:   # meno descrizioni del necessario: si chiedono variazioni delle ultime (mai la stessa immagine)
            base = dict(sf[len(sf) % max(1, len(s.get('sfondi') or [1]))] if sf else {'persone': False, 'descr': OGGETTO or TITOLO})
            base['descr'] = str(base.get('descr')) + ', different angle and different composition'; sf.append(base)
        sf = sf[:n]; s['sfondi'] = sf; s['_img'] = []
        for j, x in enumerate(sf):
            f = os.path.join(LAV, f'img_{i:02d}_{j:02d}.jpg')
            con = bool(x.get('persone')) and rif_url
            p = (('Same illustration style, SAME person (same face, hair, clothes)' + (' and SAME SUV' if AUTO else '') + ' as in the reference image. ' + stile +
                  f'Main character (always the same person): {prot}. Scene: {x.get("descr")}') if con else (STILE_OGG + f'Scene (objects and place only): {x.get("descr")}'))
            ok = immagine(f, p, rif_url if con else None)
            if not (ok and os.path.exists(f)):   # immagine non riuscita: la precedente della scena (mai uno sfondo nero), altrimenti il riferimento
                f = s['_img'][-1] if s['_img'] else os.path.join(LAV, 'riferimento.jpg')
            s['_img'].append(f); n_img += 1
    log(f'immagini: {n_img} | spesa finora {CO.totale():.3f} $')
    with mp.get_context('fork').Pool(max(2, os.cpu_count() or 4)) as pool:
        parti = pool.map(rendi_scena, range(len(SCENE)))
    # audio: voci in fila + musica bassa
    audio = []
    for i, s in enumerate(SCENE):
        a = os.path.join(LAV, f'a_{i:02d}.wav')
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', s['_voce'], '-af', f'atempo={ATEMPO:.4f},adelay=100|100,apad,atrim=0:{s["_dur"]:.3f}', '-ar', '44100', '-ac', '2', a], check=True)
        audio.append(a)
    open(os.path.join(LAV, 'v.txt'), 'w').write(''.join(f"file '{p}'\n" for p in parti))
    open(os.path.join(LAV, 'a.txt'), 'w').write(''.join(f"file '{p}'\n" for p in audio))
    video, vocew = os.path.join(LAV, 'video.mp4'), os.path.join(LAV, 'voce.wav')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', os.path.join(LAV, 'v.txt'), '-c', 'copy', video], check=True)
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', os.path.join(LAV, 'a.txt'), vocew], check=True)
    tot = durata(vocew)
    brani = sorted(x for x in os.listdir(os.path.join(QUI, 'libreria_musica')) if re.match(r'(curiosita|epico)_\d+\.mp3$', x))
    musica = os.path.join(QUI, 'libreria_musica', brani[int(num(P.get('riga_produzione'), 0)) % len(brani)])
    base = os.path.join(LAV, 'base.mp4')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', video, '-i', vocew, '-stream_loop', '-1', '-i', musica,
                    '-filter_complex', f'[2:a]volume=0.09,afade=t=out:st={max(0, tot - 3):.2f}:d=3[m];[1:a][m]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95[a]',
                    '-map', '0:v', '-map', '[a]', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-t', f'{tot:.2f}', base], check=True)
    finale = os.path.join(ROOT, 'video_possesso.mp4')
    if not ISC.applica(base, finale, dict(P, subscribe_overlay_second=P.get('subscribe_overlay_second') or 95), os.path.join(LAV, 'isc'), short=False, log=log, enc=['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '19']):
        shutil.copy(base, finale)
    cop = copertina(c, rif_url)
    finale = YT.nitido(finale, os.path.join(ROOT, 'video_possesso_1440.mp4'))
    if finale.endswith('_1440.mp4'):
        shutil.move(finale, os.path.join(ROOT, 'video_possesso.mp4')); finale = os.path.join(ROOT, 'video_possesso.mp4')
    dur_v = durata(finale)
    capitoli, off, visto = [], 0.0, None
    for s in SCENE:
        cap = str(s.get('capitolo') or '').strip()
        if cap and cap != visto:
            visto = cap; capitoli.append(f"{int(off // 60):02d}:{int(off % 60):02d} {cap}")
        off += s['_dur']
    if capitoli:
        capitoli[0] = '00:00 ' + capitoli[0][6:]
    titolo = str(c.get('titolo') or TITOLO)[:100]
    descr, tags = YT.testi(P, titolo, c.get('descrizione'), capitoli, c.get('tag'),
                           'I numeri del video sono stime realistiche per spiegare i conti: ognuno ha i suoi. Benzina e carburante esclusi.')
    log('FATTO:', finale, round(dur_v / 60, 1), 'minuti | immagini', n_img, f'(una ogni {sec:.1f} s) |', CO.testo() if hasattr(CO, 'testo') else '')
    YT.chiudi(P, finale, cop, titolo, descr, tags, {'testo_copertina': 'QUANTO COSTA? ' + eur(DATI['costo_vero'])}, PROVA, CARICA, dur_v, LINGUA, ROOT)


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        import traceback; traceback.print_exc()
        YT.esito({'stato': 'ERRORE', 'errore': str(e)[:400]}, ROOT)
        raise
