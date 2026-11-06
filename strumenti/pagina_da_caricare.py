#!/usr/bin/env python3
"""Pagina unica "Video da caricare" (Release da-caricare): solo i video ancora "Da caricare a mano" nei file di produzione,
anche piu' di uno per canale (es. video fatti in anticipo per sabato e domenica), in ordine di uscita.
Video = titolo (YouTube lo usa come titolo provvisorio), copertina = CANALE + giorno di uscita."""
import glob, json, os, re, shutil, subprocess, sys, zipfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import avvio_canali as A
import manuale as M

R = os.environ.get('GITHUB_REPOSITORY', 'gggweb23-gif/ambience')
OUT = 'f'


def gh(p):
    return json.loads(subprocess.run(['gh', 'api', p], check=True, capture_output=True, text=True).stdout)


def slug(t):
    return re.sub(r'[^A-Za-z0-9]+', '_', str(t or 'video')).strip('_')[:70] or 'video'


os.makedirs(OUT, exist_ok=True)
attesa = []   # (uscita, canale, titolo, slug)
_, _, canali = A.righe(A.CONFIGS)
for cfg in canali:
    if not M.attivo(cfg):
        continue
    cid = str(cfg.get('channel_id')).strip(); fid = str(cfg.get('scout_production_sheet_id') or '').strip()
    try:
        _, _, prod = A.righe(fid)
    except Exception as e:
        print(cid, 'file di produzione non leggibile', e); continue
    for r in prod:
        if str(r.get('status')).strip() == M.STATO:
            t = str(r.get('titolo_italiano') or '').strip()
            attesa.append((str(r.get('data_pubblicazione') or '')[:16], cid, t, slug(t)))
print('da caricare:', attesa)
arts = [a for a in gh(f'repos/{R}/actions/artifacts?per_page=100')['artifacts'] if not a.get('expired') and a['name'].startswith('DA CARICARE ')]
trovati = {}
for a in sorted(arts, key=lambda x: x['created_at'], reverse=True):
    cid = a['name'][len('DA CARICARE '):]
    if not any(c == cid and s not in trovati for _, c, _, s in attesa):
        continue
    d = f"z/{a['id']}"; os.makedirs(d, exist_ok=True)
    with open('z.zip', 'wb') as f:
        subprocess.run(['gh', 'api', f"repos/{R}/actions/artifacts/{a['id']}/zip"], stdout=f, check=True)
    zipfile.ZipFile('z.zip').extractall(d); os.remove('z.zip')
    for usc, c, t, s in attesa:
        if c != cid or s in trovati:
            continue
        v = glob.glob(f'{d}/{s}.mp4'); cop = glob.glob(f'{d}/{s}_COPERTINA.*')
        if v:
            shutil.move(v[0], f'{OUT}/{s}.mp4')
            nome_cop = ''
            if cop:
                nome_cop = f"{slug(c)}__{usc[:10]}__COPERTINA{os.path.splitext(cop[0])[1]}"
                shutil.move(cop[0], f'{OUT}/{nome_cop}')
            trovati[s] = (usc, c, t, f'{s}.mp4', nome_cop)
    shutil.rmtree(d, ignore_errors=True)
righe = ['PRIMA di caricare controlla in alto a sinistra in YouTube Studio di essere sul CANALE giusto.',
         'Il titolo va sempre INCOLLATO dal file di produzione (colonna titolo_italiano, o la prima riga della descrizione), insieme a descrizione, tag, playlist e orario.', '',
         '| Uscita | Canale | Titolo | Video | Copertina |', '|---|---|---|---|---|']
for usc, c, t, s in sorted(attesa):
    if s in trovati:
        _, _, _, fv, fc = trovati[s]
        righe.append(f'| {usc} | **{c}** | {t} | `{fv}` | `{fc}` |')
    else:
        righe.append(f'| {usc} | **{c}** | {t} | (file non trovato) | |')
open('note.md', 'w').write('\n'.join(righe) + '\n')
print('\n'.join(righe))
