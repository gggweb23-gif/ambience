"""Ricetta del coach automatico per i motori Python: se il canale ha coach_auto = SI e esiste
coach/canali/<slug del channel_id>/ricetta.json, i parametri della versione attiva valgono sopra la riga di Channel Configs."""
import json, os, re, unicodedata


def slug(s):
    s = unicodedata.normalize('NFD', str(s)).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '_', s).strip('_')


def applica(P, log=print):
    try:
        if str(P.get('coach_auto') or '').strip().upper() != 'SI':
            return P
        f = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'canali', slug(P.get('channel_id') or P.get('canale') or ''), 'ricetta.json')
        if not os.path.exists(f):
            return P
        ric = json.load(open(f))
        v = next((x for x in ric.get('versioni', []) if x.get('n') == ric.get('versione_attiva')), None)
        if v and v.get('parametri'):
            P.update(v['parametri'])
            log(f"coach: ricetta versione {v['n']} - {v.get('cosa', '')} | {', '.join(v['parametri'])}")
    except Exception as e:
        log('coach: ricetta non letta (' + str(e)[:100] + '), uso Channel Configs')
    return P
