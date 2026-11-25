#!/usr/bin/env python3
"""CARICA IL VIDEO DI UN CANALE RADAR (21 nov 2026): prende prove_video/radar/<canale>/ (prova.mp4, copertina_1.jpg, copione.json)
e lo carica sul canale (YT_REFRESH_TOKEN), programmato a PUBBLICA_IL (UTC). Descrizione: titolo in prima riga, testo, hashtag in fondo;
tag con il titolo; playlist del canale; AI = No; promozione = No. Env: CANALE, PUBBLICA_IL, PLAYLIST, FOOTER."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import motore_yt as YT
import re


def hashtag(tags, n=4):   # 17 nov (Giorgio): i 3-4 tag piu' popolari come #hashtag in fondo
    out = []
    for t in tags[1:]:
        h = '#' + ''.join(w[:1].upper() + w[1:] for w in re.findall(r"[^\W_]+", t))
        if 2 < len(h) <= 22 and h.lower() not in [x.lower() for x in out]:
            out.append(h)
        if len(out) == n:
            break
    return ' '.join(out)


E = os.environ.get
D = os.path.join('prove_video', 'radar', E('CANALE'))
c = json.load(open(os.path.join(D, 'copione.json')))
titolo = c['titolo'].strip()
P = {'privacy': 'public', 'pubblica_il': E('PUBBLICA_IL') or None, 'youtube_category_id': '27', 'playlist': E('PLAYLIST') or '',
     'youtube_description_footer': E('FOOTER') or ''}
cap = []   # capitoli nella descrizione (regola di sempre): 0:00 obbligatorio, almeno 10 s l'uno
try:
    ult = -99
    for t, n in json.load(open(os.path.join(D, 'capitoli.json'))):
        t = 0 if not cap else t
        if t - ult >= 10:
            cap.append(f"{int(t // 60)}:{int(t % 60):02d} {n}"); ult = t
except Exception:
    pass
if cap and not cap[0].startswith('0:00'):
    cap.insert(0, '0:00 Intro')
descr, tags = YT.testi(P, titolo, c.get('descrizione') or '', cap, c.get('tag') or [])
descr += '\n\n' + hashtag(tags)
cop = os.path.join(D, 'copertina_1.jpg')
import subprocess
dur = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', os.path.join(D, 'prova.mp4')], capture_output=True, text=True).stdout or 0)
if dur < 480:   # regola: video lunghi sempre sopra gli 8 minuti -> non si carica
    raise SystemExit(f'VIDEO TROPPO CORTO ({dur:.0f} s): non caricato')
vid, nota = YT.carica_youtube(P, os.path.join(D, 'prova.mp4'), titolo, descr, tags, cop, 'en')
print('CARICATO', vid, '| esce', P['pubblica_il'], '|', nota)
open(os.path.join(D, 'caricato.txt'), 'w').write(f'{vid} {P["pubblica_il"]} {titolo}\n{nota}\n')

# 25 nov (Giorgio: Lost Decades e The Dollar Years ogni 2 giorni, in automatico): registra il video lungo in produzione.json,
# cosi' shorts.py fa gli Short da questo video e avvio_radar.py sa quando e' uscito l'ultimo.
try:
    import datetime as _dt
    pp = os.path.join(D, 'produzione.json')
    righe = json.load(open(pp)) if os.path.exists(pp) else []
    if not any(r.get('youtube_video_id') == vid for r in righe):
        righe.append({'status': 'Completato', 'youtube_video_id': vid, 'titolo_originale': titolo, 'tag_seo': ', '.join(tags or []),
                      'data_inizio_produzione': _dt.datetime.now(_dt.timezone.utc).isoformat(timespec='seconds'),
                      'data_pubblicazione': P['pubblica_il'] or '', 'file_video': f"radar:video-{E('CANALE')}@{E('GITHUB_RUN_ID', '')}", 'shorts': ''})
        json.dump(righe, open(pp, 'w'), ensure_ascii=False, indent=1)
        print('registrato in', pp)
except Exception as e:
    print('registro produzione non scritto:', str(e)[:120])
