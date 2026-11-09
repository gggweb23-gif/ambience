#!/usr/bin/env python3
"""Controlla se le @handle YouTube sono libere (API YouTube channels?forHandle, chiave YT_API_KEY_RADAR). Input: NOMI separati da virgola."""
import json, os, urllib.parse, urllib.request
for n in [x.strip() for x in os.environ.get('NOMI', '').split(',') if x.strip()]:
    h = n.replace(' ', '')
    u = 'https://www.googleapis.com/youtube/v3/channels?' + urllib.parse.urlencode({'part': 'snippet,statistics', 'forHandle': '@' + h, 'key': os.environ['YT_API_KEY_RADAR']})
    j = json.load(urllib.request.urlopen(u))
    it = j.get('items') or []
    print(f'{n:22s} @{h:22s} ->', 'LIBERA' if not it else f"OCCUPATA ({it[0]['snippet']['title']}, {it[0]['statistics'].get('subscriberCount', '?')} iscritti)")
