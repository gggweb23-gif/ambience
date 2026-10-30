#!/usr/bin/env python3
"""COSTI DEL VIDEO (stima, per tutti i motori): ogni chiamata a pagamento scrive una riga in costi_video.jsonl
(variabile COSTI_FILE), alla fine riepilogo() dice quanto e' costato il video e dove.
Prezzi in $ (listino, da aggiornare qui se cambiano). Voce ElevenLabs: crediti (abbonamento, non dollari).
Uso da riga di comando: python3 costi.py [file]  -> stampa il riepilogo."""
import json, os, sys, time

# $ per milione di token: (input, output). cache: lettura 0,1x input, scrittura 1,25x input
PREZZI_TOKEN = {'haiku': (1.0, 5.0), 'sonnet': (3.0, 15.0), 'opus': (5.0, 25.0), 'gpt-4.1-mini': (0.4, 1.6), 'gpt-4.1': (2.0, 8.0),
                'gpt-4o-mini': (0.15, 0.6), 'gpt-4o': (2.5, 10.0)}
FILE = lambda: os.environ.get('COSTI_FILE') or os.path.join(os.getcwd(), 'costi_video.jsonl')


def _prezzo(modello):
    m = str(modello).lower()
    for k in sorted(PREZZI_TOKEN, key=len, reverse=True):
        if k in m:
            return PREZZI_TOKEN[k]
    return (3.0, 15.0)


def dollari_token(modello, usage, batch=False):
    pi, po = _prezzo(modello)
    u = usage or {}
    tin = (u.get('input_tokens') or u.get('prompt_tokens') or 0)
    tout = (u.get('output_tokens') or u.get('completion_tokens') or 0)
    cr, cw = u.get('cache_read_input_tokens') or 0, u.get('cache_creation_input_tokens') or 0
    d = (tin * pi + tout * po + cr * pi * 0.1 + cw * pi * 1.25) / 1e6
    return d * (0.5 if batch else 1.0)


def registra(voce, modello='', usage=None, dollari=None, crediti=None, nota=''):
    """voce: claude | openai | fal | elevenlabs | altro"""
    try:
        if dollari is None and usage is not None:
            dollari = dollari_token(modello, usage)
        r = {'t': round(time.time()), 'voce': voce, 'modello': str(modello), 'dollari': round(float(dollari or 0), 5),
             'crediti': int(crediti or 0), 'nota': str(nota)[:60]}
        if usage:
            r['token'] = {k: v for k, v in usage.items() if isinstance(v, int)}
        with open(FILE(), 'a') as f:
            f.write(json.dumps(r) + '\n')
    except Exception:
        pass


def riepilogo(path=None):
    path = path or FILE()
    righe = []
    if os.path.exists(path):
        for l in open(path):
            try:
                righe.append(json.loads(l))
            except Exception:
                pass
    per = {}
    for r in righe:
        k = r['voce'] + (' ' + r['modello'] if r.get('modello') else '')
        a = per.setdefault(k, {'chiamate': 0, 'dollari': 0.0, 'crediti': 0})
        a['chiamate'] += 1; a['dollari'] += r.get('dollari') or 0; a['crediti'] += r.get('crediti') or 0
    tot = round(sum(a['dollari'] for a in per.values()), 3)
    cred = sum(a['crediti'] for a in per.values())
    return {'totale_dollari': tot, 'crediti_voce': cred,
            'dettaglio': {k: {'chiamate': v['chiamate'], 'dollari': round(v['dollari'], 3), 'crediti': v['crediti']}
                          for k, v in sorted(per.items(), key=lambda x: -x[1]['dollari'])}}


def testo(rp=None):
    rp = rp or riepilogo()
    parti = [f"{k}: {v['dollari']:.3f} $ ({v['chiamate']} chiamate)" + (f", {v['crediti']} crediti" if v['crediti'] else '')
             for k, v in rp['dettaglio'].items()]
    return f"COSTO VIDEO (stima): {rp['totale_dollari']:.2f} $ + {rp['crediti_voce']} crediti voce | " + ' | '.join(parti)


if __name__ == '__main__':
    print(testo(riepilogo(sys.argv[1] if len(sys.argv) > 1 else None)))
