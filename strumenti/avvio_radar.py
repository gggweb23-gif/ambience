#!/usr/bin/env python3
"""25 nov 2026 (Giorgio): Lost Decades e The Dollar Years ogni 2 giorni, in automatico (prima i video RADAR si lanciavano a mano).
Per ogni canale di strumenti/shorts_radar.json con video_attivo = SI:
  - se l'ultimo video lungo (prove_video/radar/<cartella>/produzione.json) e' di meno di ogni_quanti_giorni giorni fa -> niente;
  - se oggi e' gia' partito (segno prove_video/radar/<cartella>/avviato_<data>.txt) -> niente (GitHub a volte fa partire 2 giri);
  - altrimenti Claude sceglie il titolo nuovo dal filone del competitor (modelli + titoli gia' fatti, mai ripetuti),
    con contesto/riserva per le immagini e la playlist, e lancia canale_radar.yml (uscita oggi alle ora_uscita italiane).
Costo: quello di un video RADAR (~1-1,7 $), deciso da Giorgio il 25 nov."""
import datetime as dt, json, os, subprocess, urllib.request
from zoneinfo import ZoneInfo

E = os.environ.get
ROMA = ZoneInfo('Europe/Rome')
oggi = dt.datetime.now(ROMA).date()
cfg = json.load(open('strumenti/shorts_radar.json'))
canali = json.load(open('strumenti/prova_radar_canali.json'))


def claude(prompt):
    req = urllib.request.Request('https://api.anthropic.com/v1/messages', method='POST', data=json.dumps({
        'model': 'claude-sonnet-5-5', 'max_tokens': 600, 'messages': [{'role': 'user', 'content': prompt}]}).encode(),
        headers={'x-api-key': E('ANTHROPIC_API_KEY', ''), 'anthropic-version': '2023-06-01', 'content-type': 'application/json'})
    t = ''.join(b.get('text', '') for b in json.load(urllib.request.urlopen(req, timeout=120)).get('content', []))
    return json.loads(t[t.find('{'): t.rfind('}') + 1])


da_lanciare = []
for nome, c in cfg.items():
    if not isinstance(c, dict) or str(c.get('video_attivo', 'NO')).upper() != 'SI':
        continue
    cart = c['cartella']; d = os.path.join('prove_video', 'radar', cart)
    if E('SOLO') and E('SOLO') not in (nome, cart):
        continue
    righe = json.load(open(os.path.join(d, 'produzione.json'))) if os.path.exists(os.path.join(d, 'produzione.json')) else []
    ultimo = None
    for r in righe:
        try:
            x = dt.datetime.fromisoformat(str(r.get('data_inizio_produzione')).replace('Z', '+00:00'))
            x = (x if x.tzinfo else x.replace(tzinfo=ROMA)).astimezone(ROMA).date()
            ultimo = max(ultimo, x) if ultimo else x
        except Exception:
            pass
    ogni = int(c.get('ogni_quanti_giorni') or 2)
    segno = os.path.join(d, f'avviato_{oggi.isoformat()}.txt')
    if os.path.exists(segno):
        print(nome, ': oggi gia\' lanciato'); continue
    if ultimo and (oggi - ultimo).days < ogni and E('FORZA', '').upper() != 'SI':
        print(nome, f': oggi niente video (uno ogni {ogni} giorni, ultimo il {ultimo})'); continue
    k = canali[cart]
    fatti = [r.get('titolo_originale', '') for r in righe if r.get('titolo_originale')]
    z = claude(f"""You plan the next long video (10 minutes) of an English YouTube channel for a US audience.
Channel niche: {k['descrizione']}
Competitor we follow: {k['competitor']}. Its winning titles: {k['modelli']}
Titles we ALREADY published (never repeat them or their exact topic): {json.dumps(fatti, ensure_ascii=False)}
Write ONE new title in the same winning pattern and niche as the competitor (same structure, new angle/topic, clickable for the home page, never clickbait lies).
Return ONLY JSON: {{"titolo": "...", "contesto": "one line: what the images must show (era, place, people) so every image is coherent with this video",
"riserva": "2-4 word archive search for fallback images", "playlist": "short playlist name for this topic (2-4 words)"}}""")
    k['titolo'], k['contesto'], k['riserva'] = z['titolo'], z.get('contesto') or k.get('contesto'), z.get('riserva') or k.get('riserva')
    open(segno, 'w').write(z['titolo'])
    print(nome, ': nuovo video ->', z)
    da_lanciare.append({'canale': cart, 'chiave': c['chiave_youtube'], 'titolo': z['titolo'], 'playlist': z.get('playlist') or ''})

if da_lanciare:
    json.dump(canali, open('strumenti/prova_radar_canali.json', 'w'), ensure_ascii=False, indent=1)
    ora = E('ORA_USCITA', '17:00')
    uscita = dt.datetime.combine(oggi, dt.time(*map(int, ora.split(':'))), ROMA).astimezone(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    subprocess.run('git config user.name render-bot; git config user.email render-bot@users.noreply.github.com; '
                   'git add strumenti/prova_radar_canali.json prove_video/radar && git commit -qm "RADAR: titoli del giorno" && '
                   'for i in 1 2 3 4 5; do git pull --rebase -q && git push -q && break; sleep 7; done', shell=True, check=True)
    subprocess.run(['gh', 'workflow', 'run', 'canale_radar.yml', '-f', 'canali=' + json.dumps(da_lanciare, ensure_ascii=False),
                    '-f', 'pubblica_il=' + uscita, '-f', 'secondi=600'], check=True)
    print('lanciato canale_radar.yml per', [x['canale'] for x in da_lanciare], '| esce', uscita)
else:
    print('nessun video RADAR da lanciare oggi')
