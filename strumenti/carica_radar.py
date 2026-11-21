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
descr, tags = YT.testi(P, titolo, c.get('descrizione') or '', [], c.get('tag') or [])
descr += '\n\n' + hashtag(tags)
cop = os.path.join(D, 'copertina_1.jpg')
vid, nota = YT.carica_youtube(P, os.path.join(D, 'prova.mp4'), titolo, descr, tags, cop, 'en')
print('CARICATO', vid, '| esce', P['pubblica_il'], '|', nota)
open(os.path.join(D, 'caricato.txt'), 'w').write(f'{vid} {P["pubblica_il"]} {titolo}\n{nota}\n')
