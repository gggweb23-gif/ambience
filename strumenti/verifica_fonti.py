#!/usr/bin/env python3
"""Verifica GRATUITA delle fonti libere per un argomento: quante immagini di pubblico dominio / CC0 ci sono
per ogni ricerca (Met Museum Open Access, Wikimedia Commons). Uso: QUERY="a;b;c" python3 strumenti/verifica_fonti.py"""
import json, os, urllib.parse, urllib.request, concurrent.futures as cf

def get(u):
    req = urllib.request.Request(u, headers={'User-Agent': 'ambience-verifica/1.0 (gggweb23@gmail.com)'})
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.loads(r.read().decode())

def met(q):
    try:
        ids = (get('https://collectionapi.metmuseum.org/public/collection/v1/search?hasImages=true&q=' + urllib.parse.quote(q)).get('objectIDs') or [])
        buoni, esempi = 0, []
        for i in ids[:25]:
            try:
                o = get(f'https://collectionapi.metmuseum.org/public/collection/v1/objects/{i}')
            except Exception:
                continue
            if o.get('isPublicDomain') and o.get('primaryImage') and ('Roman' in (o.get('culture') or '') + (o.get('period') or '') + (o.get('title') or '') or 'Roman' in (o.get('department') or '')):
                buoni += 1
                if len(esempi) < 2:
                    esempi.append(o.get('title', '')[:50])
        return len(ids), buoni, esempi
    except Exception as e:
        return 0, 0, [str(e)[:60]]

def commons(q):
    try:
        j = get('https://commons.wikimedia.org/w/api.php?action=query&format=json&list=search&srnamespace=6&srlimit=50&srsearch=' + urllib.parse.quote(q + ' painting'))
        return j.get('query', {}).get('searchinfo', {}).get('totalhits', 0), [x['title'][5:60] for x in j.get('query', {}).get('search', [])[:2]]
    except Exception as e:
        return 0, [str(e)[:60]]

qs = [q.strip() for q in os.environ.get('QUERY', '').split(';') if q.strip()]
with cf.ThreadPoolExecutor(6) as ex:
    ris = list(ex.map(lambda q: (q, met(q), commons(q)), qs))
for q, (tot, buoni, es), (ch, ces) in ris:
    print(f'{q:32s} | Met: {tot:5d} risultati, {buoni:2d}/25 romani di pubblico dominio {es} | Commons dipinti: {ch} {ces}')
