#!/usr/bin/env python3
"""PULSANTE "MI PIACE / ISCRIVITI + CAMPANELLA" CON I SUONI (6 nov 2026, Giorgio: su tutti i video e gli Short di tutti i canali, presenti e futuri).
Immagine e suoni dalle colonne subscribe_overlay_* di Channel Configs; se sono vuote si usano quelli standard nella lingua del canale
(italiano = ISCRIVITI, altre lingue = SUBSCRIBE), gli stessi dei video lunghi di Storia in Minuti e Agora of Sages.
Il pulsante entra con una dissolvenza, dopo 0,6 s si sente il clic e dopo un altro secondo il "ding" della campanella.
Se qualcosa va storto il video resta com'era (mai un video perso per il pulsante)."""
import os, shutil, subprocess, time, urllib.request

DRIVE = 'https://drive.google.com/uc?export=download&id='
STANDARD = {'img_it': DRIVE + '1xGxzt1tEo-lpVPL0eg0dnSOHJy5NX2Wm',   # MI PIACE / ISCRIVITI + campanella
            'img_en': DRIVE + '10HxGKh0ISy1eGapQwuagJyyVuzUo5qd3',   # LIKE / SUBSCRIBE + campanella
            'clic': DRIVE + '1I-kBzQs0Mz_g3w_FDZsYK6-hdGxbTkjJ',
            'campana': DRIVE + '1xejqUoCdL7fUih6WGuhug5mfinW-91A2'}


def num(v, d):
    try:
        return float(str(v).replace(',', '.')) if str(v if v is not None else '').strip() != '' else d
    except Exception:
        return d


def impostazioni(cfg):
    """Immagine, suoni e tempi del canale (colonne di Channel Configs, altrimenti quelli standard nella lingua del canale)."""
    cfg = cfg or {}
    it = str(cfg.get('language') or '').strip().lower()[:2] == 'it'
    return {'img': str(cfg.get('subscribe_overlay_url') or '').strip() or STANDARD['img_it' if it else 'img_en'],
            'clic': str(cfg.get('subscribe_overlay_sound_url') or '').strip() or STANDARD['clic'],
            'campana': str(cfg.get('subscribe_overlay_bell_url') or '').strip() or STANDARD['campana'],
            'sec': num(cfg.get('subscribe_overlay_second'), 10.0),
            'clic_ritardo': num(cfg.get('subscribe_overlay_sound_delay'), 0.6),
            'campana_ritardo': num(cfg.get('subscribe_overlay_bell_delay'), 1.0)}


def scarica(url, path, tentativi=4):
    if os.path.exists(path) and os.path.getsize(path) > 2000:
        return path
    for k in range(tentativi):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=120) as r, open(path, 'wb') as f:
                shutil.copyfileobj(r, f, 1 << 20)
            if os.path.getsize(path) > 2000:
                return path
        except Exception:
            time.sleep(3 * (k + 1))
    raise RuntimeError('impossibile scaricare ' + url)


def misure(video):
    o = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height:format=duration', '-of', 'default=nw=1', video],
                       capture_output=True, text=True).stdout
    d = dict(x.split('=', 1) for x in o.split() if '=' in x)
    return int(d.get('width', 1920)), int(d.get('height', 1080)), float(d.get('duration', 0) or 0)


def applica(video, uscita, cfg, cartella, short=False, log=print, enc=None):
    """Mette il pulsante con i suoni su video -> uscita. short=True: dal secondo 1 fino alla fine, sopra il video (tra gancio e immagine);
    video lungo: al secondo subscribe_overlay_second per 4 s, nel mezzo dello schermo (come negli altri motori). True se fatto."""
    try:
        s = impostazioni(cfg)
        os.makedirs(cartella, exist_ok=True)
        png = scarica(s['img'], os.path.join(cartella, 'iscriviti_' + s['img'][-12:] + '.png'))
        W, H, dur = misure(video)
        if short:
            sec = 1.0; larg = int(W * 0.63); y = int(H * 0.26)   # 1080x1920: 680 px a y=500, tra il gancio e l'immagine (posizione A scelta da Giorgio):
            # sotto i sottotitoli toccava il nome del canale e i pulsanti di YouTube sul telefono
            vis = f"gte(t,{sec})"; fade = f"fade=t=in:st={sec}:d=0.3:alpha=1"
        else:
            sec = min(s['sec'], max(dur - 5, 0)); larg = int(W * 0.47); y = int(H * 0.593)   # 1920x1080: 900 px a y=640, come Storia in Minuti
            vis = f"between(t,{sec},{sec + 4})"; fade = f"fade=t=in:st={sec}:d=0.3:alpha=1,fade=t=out:st={sec + 3.6}:d=0.4:alpha=1"
        ins = ['-i', video, '-loop', '1', '-t', f'{dur:.3f}', '-i', png]
        fl = (f"[1:v]scale={larg}:-1,format=rgba,{fade}[isc];"
              f"[0:v][isc]overlay=x=(W-w)/2:y={y}:enable='{vis}',format=yuv420p[v]")
        suoni, k = [], 2
        for url, quando, nome in ((s['clic'], sec + s['clic_ritardo'], 'clic'), (s['campana'], sec + s['clic_ritardo'] + s['campana_ritardo'], 'campana')):
            try:
                f = scarica(url, os.path.join(cartella, nome + '_' + url[-12:] + '.mp3'))
            except Exception as e:
                log(nome, 'non disponibile:', str(e)[:80]); continue
            ins += ['-i', f]; ms = int(quando * 1000)
            fl += f";[{k}:a]adelay={ms}|{ms},volume=0.5[s{k}]"; suoni.append(f'[s{k}]'); k += 1
        amap = '0:a'
        if suoni:
            fl += f";[0:a]{''.join(suoni)}amix=inputs={len(suoni) + 1}:duration=first:normalize=0[a]"; amap = '[a]'
        subprocess.run(['ffmpeg', '-y', '-v', 'error', *ins, '-filter_complex', fl, '-map', '[v]', '-map', amap,
                        *(enc or ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20']), '-c:a', 'aac', '-b:a', '192k',
                        '-movflags', '+faststart', '-t', f'{dur:.3f}', uscita], check=True)
        if misure(uscita)[2] < dur - 1:
            raise RuntimeError('video con il pulsante piu\' corto dell\'originale')
        log(f"pulsante iscriviti {'per tutto lo Short' if short else f'al secondo {sec:g}'} con {len(suoni)} suoni")
        return True
    except Exception as e:
        log('pulsante iscriviti saltato:', str(e)[:200])
        return False
