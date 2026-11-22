#!/usr/bin/env python3
"""Mette un video in privato (annulla la programmazione), reversibile. Env: VIDEO_ID, YT_REFRESH_TOKEN, YT_CLIENT_ID, YT_CLIENT_SECRET"""
import json, os, urllib.parse, urllib.request
E = os.environ.get
tk = json.loads(urllib.request.urlopen(urllib.request.Request('https://oauth2.googleapis.com/token', data=urllib.parse.urlencode({
    'client_id': E('YT_CLIENT_ID'), 'client_secret': E('YT_CLIENT_SECRET'), 'refresh_token': E('YT_REFRESH_TOKEN'), 'grant_type': 'refresh_token'}).encode())).read())['access_token']
h = {'Authorization': 'Bearer ' + tk, 'Content-Type': 'application/json'}
v = json.loads(urllib.request.urlopen(urllib.request.Request(f"https://www.googleapis.com/youtube/v3/videos?part=status&id={E('VIDEO_ID')}", headers=h)).read())['items'][0]
st = v['status']; st['privacyStatus'] = 'private'; st.pop('publishAt', None)
r = json.loads(urllib.request.urlopen(urllib.request.Request('https://www.googleapis.com/youtube/v3/videos?part=status', data=json.dumps({'id': E('VIDEO_ID'), 'status': st}).encode(), headers=h, method='PUT')).read())
print(E('VIDEO_ID'), '->', r['status']['privacyStatus'], r['status'].get('publishAt'))
