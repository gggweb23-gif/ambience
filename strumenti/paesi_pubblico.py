#!/usr/bin/env python3
"""Sola lettura (11 nov): da quali paesi e in quale lingua arrivano le visualizzazioni di un canale (ultimi 28 giorni) e se YouTube
ha attivato il doppiaggio automatico. CHIAVE = nome del segreto YouTube del canale."""
import datetime as dt, json, os, sys, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import performance as PF
E = os.environ.get
tk, scope = PF.token(E(E('CHIAVE')))
h = {'Authorization': 'Bearer ' + tk}
fine = dt.date.today(); ini = fine - dt.timedelta(days=28)
for dim in ('country', 'insightTrafficSourceType'):
    r = PF.analytics(h, {'startDate': ini.isoformat(), 'endDate': fine.isoformat(), 'dimensions': dim, 'metrics': 'views,estimatedMinutesWatched', 'sort': '-views', 'maxResults': 15})
    print('\n===', dim); [print('  ', row) for row in r.get('rows', []) or []]
