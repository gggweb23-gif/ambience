#!/usr/bin/env python3
"""17 nov (Giorgio: "anticipo l'uscita"): rende PUBBLICO subito un video programmato. Env: VIDEO_ID, YT_REFRESH_TOKEN, YT_CLIENT_ID, YT_CLIENT_SECRET"""
import json, os, urllib.parse, urllib.request
E = os.environ.get
d = urllib.parse.urlencode({'client_id': E('YT_CLIENT_ID'), 'client_secret': E('YT_CLIENT_SECRET'), 'refresh_token': E('YT_REFRESH_TOKEN'), 'grant_type': 'refresh_token'}).encode()
tk = json.loads(urllib.request.urlopen(urllib.request.Request('https://oauth2.googleapis.com/token', data=d)).read())['access_token']
H = {'Authorization': 'Bearer ' + tk, 'Content-Type': 'application/json'}
for vid in [v.strip() for v in E('VIDEO_ID', '').split(',') if v.strip()]:
    st = json.loads(urllib.request.urlopen(urllib.request.Request(f'https://www.googleapis.com/youtube/v3/videos?part=status&id={vid}', headers=H)).read())['items'][0]['status']
    nuovo = {'privacyStatus': 'public', 'selfDeclaredMadeForKids': st.get('selfDeclaredMadeForKids', False), 'embeddable': st.get('embeddable', True),
             'publicStatsViewable': st.get('publicStatsViewable', True), 'license': st.get('license', 'youtube')}
    if 'containsSyntheticMedia' in st:
        nuovo['containsSyntheticMedia'] = st['containsSyntheticMedia']
    urllib.request.urlopen(urllib.request.Request('https://www.googleapis.com/youtube/v3/videos?part=status', data=json.dumps({'id': vid, 'status': nuovo}).encode(), headers=H, method='PUT')).read()
    print('PUBBLICO', vid, '(era', st.get('privacyStatus'), st.get('publishAt', ''), ')')
