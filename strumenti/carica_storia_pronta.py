#!/usr/bin/env python3
"""CARICA SU YOUTUBE UN VIDEO STORIA GIA' FATTO (senza rifarlo e senza spese).
Serve quando video_storia.py ha creato il video ma non l'ha caricato (es. 5/11: Iraq di 7 min 56 s, sotto la soglia di allora).
Prende l'artifact "video-storia" del run RUN_ID (scaricato da carica_storia_pronta.yml in questa cartella), carica video,
copertina e playlist con le stesse funzioni di video_storia.py, esce alle publish_time del canale (oggi se c'e' tempo, se no domani)
e scrive l'esito nella riga del file di produzione (stato Completato)."""
import datetime as dt, json, os, re, sys
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import avvio_canali as A

CANALE = os.environ.get('CANALE', 'Storia in Minuti').strip()
titolo = open('titolo.txt', encoding='utf-8').read().strip()
c = json.load(open('copione.json', encoding='utf-8'))
cfg = next(x for x in A.righe(A.CONFIGS)[2] if str(x.get('channel_id') or '').strip() == CANALE)
fid = str(cfg.get('scout_production_sheet_id') or '').strip()
_, h, prod = A.righe(fid)
k = next((i for i, r in enumerate(prod) if str(r.get('titolo_italiano') or '').strip() == titolo), None)
if k is None:
    raise SystemExit('riga del file di produzione non trovata per il titolo: ' + titolo)
riga = prod[k]
if str(riga.get('status')).strip() == 'Completato' or str(riga.get('youtube_video_id') or '').strip():
    raise SystemExit('questo video risulta gia\' caricato: ' + str(riga.get('youtube_video_id')))

m = re.match(r'(\d{1,2})[:.](\d{2})', str(cfg.get('publish_time') or '17:00'))
ora = dt.datetime.now(ZoneInfo('Europe/Rome'))
quando = ora.replace(hour=int(m.group(1)) if m else 17, minute=int(m.group(2)) if m else 0, second=0, microsecond=0)
if quando < ora + dt.timedelta(minutes=30):
    quando += dt.timedelta(days=1)
P = {k_: v for k_, v in cfg.items() if not re.search(r'token|secret|password|api_key', k_, re.I)}
P.pop('callback_url', None)
P.update({'canale': CANALE, 'link': str(riga.get('Link video') or '').strip(), 'id': str(riga.get('Link video') or '').strip(),
          'foglio_produzione': fid, 'riga_produzione': k + 2, 'prova': 'NO', 'carica': 'SI',
          'pubblica_il': quando.astimezone(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')})
os.environ['PAYLOAD'] = json.dumps(P, ensure_ascii=False)
sys.path.insert(0, os.getcwd())
import video_storia as V

cop = 'copertina.jpg' if os.path.exists('copertina.jpg') else ''
vid = V.carica_youtube('video_storia.mp4', c, titolo)
note = [x for x in (V.carica_copertina(vid, cop), V.playlist_video(vid, titolo)) if x]
descr, tags = V.dati_youtube(c, titolo)
V.avvisa({'stato': 'PUBBLICATO', 'video_id': vid, 'link': 'https://www.youtube.com/watch?v=' + vid, 'titolo': titolo,
          'testo_copertina': str((c.get('copertina') or {}).get('testo') or ''), 'pubblica_il': P['pubblica_il'],
          'descrizione': descr, 'tag': ', '.join(tags), 'minuti_video': round(V.durata('video_storia.mp4') / 60, 1), 'errore': '; '.join(note)})
print('caricato', vid, '| esce', quando.strftime('%d/%m %H:%M'), '|', '; '.join(note) or 'copertina e playlist ok')
import esito_foglio
esito_foglio.main()
