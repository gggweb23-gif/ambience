#!/usr/bin/env python3
"""RIFORNIMENTO AUTOMATICO DEI TITOLI (9 nov 2026, Giorgio: "quando finiscono i video nel file di produzione, aggiungili coerenti con il canale").
Per i canali con titoli_auto = SI in Channel Configs: se nel file di produzione restano meno di titoli_auto_minimo righe "Pronto" (vuota = 3),
Claude propone 10 titoli nuovi sullo STESSO filone del canale (colonne niche / scout_filone), mai uguali o quasi uguali a quelli gia' nel file,
con lo stesso schema dei titoli che ci sono, e li aggiunge in fondo come "Pronto" (codice, playlist, testo copertina e, se il file le ha,
le colonne oggetto e voci_costo). Una chiamata Claude ogni 10 titoli (circa 0,03 $), registrata nei costi.
Uso: lo chiama strumenti/avvio_canali.py ogni notte prima di scegliere la riga; a mano: python3 strumenti/rifornisci_titoli.py "Costo Vero"."""
import json, os, re, sys, time, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

E = os.environ.get


def num(x, d=0.0):
    try:
        return float(str(x).replace(',', '.'))
    except Exception:
        return d


def claude(prompt):
    req = urllib.request.Request('https://api.anthropic.com/v1/messages', method='POST', data=json.dumps({
        'model': 'claude-sonnet-5-5', 'max_tokens': 8000, 'thinking': {'type': 'between_tools'}, 'output_config': {'effort': 'low'},
        'messages': [{'role': 'user', 'content': prompt}]}).encode(),
        headers={'x-api-key': E('ANTHROPIC_API_KEY', ''), 'anthropic-version': '2023-06-01', 'content-type': 'application/json'})
    j = json.loads(urllib.request.urlopen(req, timeout=300).read())
    u = j.get('usage') or {}
    print(f"  titoli: Claude {u.get('input_tokens', 0) * 3e-6 + u.get('output_tokens', 0) * 15e-6:.3f} $")
    return ''.join(b.get('text', '') for b in j['content'] if b.get('type') == 'text')


def rifornisci(cfg, fid, A, forza=False):
    """A = modulo avvio_canali (api, righe, lettera). Ritorna quante righe ha aggiunto."""
    cid = str(cfg.get('channel_id') or '').strip()
    if str(cfg.get('titoli_auto') or '').strip().upper() != 'SI' and not forza:
        return 0
    sch, h, prod = A.righe(fid)
    pronte = [r for r in prod if str(r.get('status')).strip() == 'Pronto']
    minimo = int(num(cfg.get('titoli_auto_minimo'), 3) or 3)
    if len(pronte) >= minimo and not forza:
        return 0
    tit = lambda r: str(r.get('titolo_italiano') or r.get('titolo_originale') or '').strip()
    esistenti = [tit(r) for r in prod if tit(r)]
    lingua = str(cfg.get('language') or 'en')[:2]
    extra = [c for c in ('oggetto', 'voci_costo') if c in h]
    esempi = [{k: r.get(k) for k in ['titolo_italiano', 'playlist', 'titolo_thumbnail'] + extra} for r in prod[:5]]
    playlist = sorted({str(r.get('playlist') or '').strip() for r in prod if str(r.get('playlist') or '').strip()}
                      | {x.split(':')[0].strip() for x in str(cfg.get('playlist') or '').split('||') if x.strip()}
                      | {x.strip() for x in str(cfg.get('playlist_previste') or '').split(',') if x.strip()})
    p = f"""YouTube channel "{cfg.get('channel_name') or cid}" (language: {lingua}). Topic (filone, NEVER go outside it): {cfg.get('scout_filone') or cfg.get('niche')}.
Titles already in the production file (do NOT repeat them or make near-duplicates): {json.dumps(esistenti, ensure_ascii=False)}.
Examples of rows (same title pattern, same style): {json.dumps(esempi, ensure_ascii=False)}.
Playlists of the channel (use ONLY these names, exactly as written; a new one only if none fits at all): {json.dumps(playlist, ensure_ascii=False)}.
Propose 10 NEW videos on the same filone, with real proven demand (topics people already search and watch), each one a strong hook, same title pattern as the examples,
correct facts and numbers only (no invented events), title max 70 characters, in the channel language.
Fields per video: "titolo", "playlist", "titolo_thumbnail" (short text for the thumbnail, as in the examples){''.join(f', "{c}"' for c in extra)}.
{'For "voci_costo": the real ownership costs to cover; never fuel/petrol/charging (rule of the channel owner). Every video is about OWNING one thing that you BUY (it has a purchase price and a resale value at the end): never renting, subscriptions or services. Every title STARTS with the thing written ALL IN CAPITALS (the keyword: on mobile only the beginning is visible and it must stand out), then the rest, e.g. "PLAYSTATION 5: quanto costa DAVVERO in 7 anni?".' if 'voci_costo' in extra else ''}
Reply ONLY with JSON: {{"video": [{{...}}]}}"""
    if E('RIGHE'):   # titoli gia' decisi (es. scritti da Claude in chat e approvati): niente chiamata
        nuovi = json.loads(E('RIGHE'))
    else:
        t = claude(p)
        m = re.search(r'\{.*\}', t, re.S)
        try:
            nuovi = json.loads(m.group(0))['video']
        except Exception:
            from json_repair import repair_json
            nuovi = json.loads(repair_json(m.group(0)))['video']
    vis = {re.sub(r'\W+', '', x.lower()) for x in esistenti}
    pref = re.sub(r'[^A-Z]', '', ''.join(w[0] for w in str(cid).upper().split()))[:3] or 'VID'
    n0 = max([int(x) for x in re.findall(rf'{pref}-(\d+)', ' '.join(str(r.get('Link video') or '') for r in prod))] + [len(prod)])
    righe, k = [], n0
    for v in nuovi:
        t_ = str(v.get('titolo') or '').strip()
        if not t_ or re.sub(r'\W+', '', t_.lower()) in vis:
            continue
        if re.search(r'benzin|carburant|fuel|petrol', str(v.get('voci_costo') or ''), re.I):
            v['voci_costo'] = re.sub(r',?\s*[^,]*(benzin|carburant|fuel|petrol)[^,]*', '', str(v['voci_costo']), flags=re.I)
        k += 1; vis.add(re.sub(r'\W+', '', t_.lower()))
        r = {c: '' for c in h}
        r.update({'titolo_originale': t_, 'titolo_italiano': t_, 'Link video': f'{pref}-{k:02d}', 'status': 'Pronto', 'playlist': str(v.get('playlist') or ''),
                  'nome_canale': str(cfg.get('channel_name') or cid), 'titolo_thumbnail': str(v.get('titolo_thumbnail') or ''), 'target_durata': '9-10'})
        for c in extra:
            r[c] = str(v.get(c) or '')
        righe.append([r.get(c, '') for c in h])
    if righe:
        A.api(fid, 'POST', f"/values/{urllib.parse.quote(chr(39) + sch + chr(39) + '!A1')}:append?valueInputOption=RAW&insertDataOption=INSERT_ROWS", {'values': righe})
    print(f'  {cid}: {len(righe)} titoli nuovi aggiunti nel file di produzione (Pronto)')
    return len(righe)


import urllib.parse

if __name__ == '__main__':
    import avvio_canali as A
    _, _, canali = A.righe(A.CONFIGS)
    for cfg in canali:
        if str(cfg.get('channel_id') or '').strip() == sys.argv[1]:
            rifornisci(cfg, str(cfg.get('scout_production_sheet_id') or '').strip(), A, forza=len(sys.argv) > 2 and sys.argv[2] == 'forza')
