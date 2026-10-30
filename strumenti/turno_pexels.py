#!/usr/bin/env python3
"""TURNO PEXELS: mai due video che usano Pexels prodotti nello stesso momento (si supererebbe il limite orario di richieste).
Gira come primo job dei workflow che usano Pexels. Se c'e' gia' un altro video Pexels in lavorazione (partito prima),
questo video NON parte: avvisa n8n con stato RIMANDATO (la riga torna a Pronto e riparte al prossimo turno dell'orchestratore).
Elenco dei workflow Pexels: variabile WORKFLOW_PEXELS (nomi dei file separati da virgola)."""
import json, os, sys, urllib.request

REPO, MIO = os.environ['GITHUB_REPOSITORY'], int(os.environ['GITHUB_RUN_ID'])
H = {'Authorization': 'Bearer ' + os.environ['GH_TOKEN'], 'Accept': 'application/vnd.github+json'}
WF = [w.strip() for w in os.environ.get('WORKFLOW_PEXELS', '').split(',') if w.strip()]


def get(url):
    return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=60).read())


io = get(f'https://api.github.com/repos/{REPO}/actions/runs/{MIO}')
chiave_mia = (io.get('run_started_at') or '', MIO)
prima = []
for wf in WF:
    try:
        for r in get(f'https://api.github.com/repos/{REPO}/actions/workflows/{wf}/runs?status=in_progress&per_page=50').get('workflow_runs', []):
            if r['id'] != MIO and ((r.get('run_started_at') or '', r['id']) < chiave_mia):
                prima.append(f"{wf} #{r['run_number']}")
    except Exception as e:
        print('controllo non riuscito su', wf, str(e)[:120])
ok = not prima
print('TURNO PEXELS:', 'via libera' if ok else 'RIMANDATO, in lavorazione: ' + ', '.join(prima))
if not ok:
    try:
        P = json.loads(os.environ.get('PAYLOAD') or '{}')
    except Exception:
        P = {}
    if P.get('callback_url') and str(os.environ.get('PROVA', '')).upper() != 'SI':
        corpo = {'id': P.get('id'), 'foglio': P.get('foglio', ''), 'gid': P.get('gid', ''), 'stato': 'RIMANDATO',
                 'errore': 'Rimandato al prossimo turno: un altro video con Pexels era gia in lavorazione (' + ', '.join(prima) + ')'}
        try:
            urllib.request.urlopen(urllib.request.Request(P['callback_url'], data=json.dumps(corpo).encode(),
                                                          headers={'Content-Type': 'application/json'}), timeout=60).read()
            print('n8n avvisato: RIMANDATO')
        except Exception as e:
            print('avviso a n8n non riuscito:', str(e)[:150])
with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
    f.write(f"ok={'true' if ok else 'false'}\n")
