#!/usr/bin/env python3
"""CARICAMENTO A MANO (colonna carica di Channel Configs = MANUALE; 5 nov, Giorgio).
Il motore fa tutto (copione, voce, montaggio, controlli, copertina, titolo, descrizione, tag, playlist, orario) ma NON carica su YouTube:
- video e copertina finiscono nella cartella da_caricare/ -> il workflow li mette nell'artifact "DA CARICARE ..." (si scarica da GitHub, 7 giorni);
- titolo, descrizione, tag, playlist, testo copertina e orario di uscita vanno nel file di produzione del canale (stato "Da caricare a mano").
Quando Giorgio lo carica, strumenti/trova_caricati.py trova il video sul canale dal titolo e scrive youtube_video_id + stato Completato."""
import datetime as dt, os, re, shutil
from zoneinfo import ZoneInfo

STATO = 'Da caricare a mano'
ROMA = ZoneInfo('Europe/Rome')


def attivo(P):
    return str((P or {}).get('carica') or '').strip().upper() == 'MANUALE'


def orario(P):
    """Data e ora di uscita da programmare in YouTube Studio (ora italiana, 'AAAA-MM-GG HH:MM')."""
    s = str((P or {}).get('pubblica_il') or '').strip()
    if s:
        try:
            return dt.datetime.fromisoformat(s.replace('Z', '+00:00')).astimezone(ROMA).strftime('%Y-%m-%d %H:%M')
        except Exception:
            pass
    m = re.match(r'(\d{1,2})[:.](\d{2})', str((P or {}).get('publish_time') or '17:00'))
    ora = dt.datetime.now(ROMA)
    q = ora.replace(hour=int(m.group(1)) if m else 17, minute=int(m.group(2)) if m else 0, second=0, microsecond=0)
    if q < ora + dt.timedelta(hours=2):   # c'e' bisogno del tempo per scaricarlo e caricarlo a mano
        q += dt.timedelta(days=1)
    return q.strftime('%Y-%m-%d %H:%M')


def prepara(video, copertina, titolo, root='.'):
    """Copia video e copertina in da_caricare/ con il nome del titolo (li prende l'artifact del workflow)."""
    d = os.path.join(root, 'da_caricare')
    os.makedirs(d, exist_ok=True)
    nome = re.sub(r'[^A-Za-z0-9]+', '_', str(titolo or 'video')).strip('_')[:70] or 'video'
    out = []
    if video and os.path.exists(video):
        dst = os.path.join(d, nome + '.mp4')
        shutil.copy(video, dst); out.append(dst)
    if copertina and os.path.exists(copertina):
        dst = os.path.join(d, nome + '_COPERTINA' + (os.path.splitext(copertina)[1] or '.jpg'))
        shutil.copy(copertina, dst); out.append(dst)
    print('DA CARICARE A MANO:', ', '.join(os.path.basename(x) for x in out), flush=True)
    return out
