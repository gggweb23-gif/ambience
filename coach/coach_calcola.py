#!/usr/bin/env python3
"""COACH AUTOMATICO - calcolo (gratis, nessuna chiamata a pagamento).
Legge Channel Configs (xlsx) + file di produzione del canale (xlsx, schede Foglio1 e Performance) + ricetta del canale
e dice, per la versione attiva, se i parametri del canale sono rispettati e quale leva toccare.

Uso: python3 coach/coach_calcola.py <channel_configs.xlsx> <produzione.xlsx> "<channel_id>"
Uscita: JSON su stdout (e coach/canali/<slug>/ultimo_calcolo.json).

Regole (decise con Giorgio il 30 ott 2026, valgono per tutti i canali con coach_auto = SI):
- finestra = ultimi N video della versione attiva (colonna coach_finestra_video, default 3), solo video con almeno 72 ore
- CTR = clic totali / impression totali della finestra (media pesata) >= coach_obiettivo_ctr (default 3,5)
- 6 nov 2026, Giorgio: regola unica per tutti i canali = 3 video con almeno 72 ore nella versione attiva E almeno
  coach_min_impression (default 1000) impression sommando QUEGLI STESSI 3 video della versione attiva (stato ATTESA_IMPRESSION);
  prima (5 nov) si sommavano gli ultimi 5 video di qualsiasi versione
- retention 30 s e 60 s = media pesata sulle views, solo video con almeno 30 views (se non bastano si allarga a 5 video)
  >= coach_obiettivo_ret30 (default 65) e coach_obiettivo_ret60 (default 50)
- ordine fisso delle leve: CTR -> retention 30 s -> retention 60 s
- 5 nov 2026, Giorgio: esito['retention'] = decisione PARALLELA sulla retention, attiva da coach_min_views_retention (default 50)
  views totali del canale (tutti i video sommati), anche quando la copertina e' ancora in ATTESA o in LEVA_CTR
- STABILE quando i parametri tengono per 2 controlli di fila
- 5 nov 2026, Giorgio (studio impression): impression e CTR si valutano SOLO sui video con almeno 3 giorni di report YouTube
  completi (colonne giorni_report / copertura_report della scheda Performance); gli altri sono "in attesa di report"
  (esito['in_attesa_report']) e non contano, perche' i report arrivano 2-5 giorni dopo. La retention resta come prima."""
import datetime as dt, json, os, re, sys, unicodedata
import openpyxl

ADESSO = dt.datetime.now()


def slug(s):
    s = unicodedata.normalize('NFD', str(s)).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '_', s).strip('_')


def num(v, d=None):
    try:
        return float(str(v).replace('%', '').replace(',', '.'))
    except Exception:
        return d


def data(v):
    if isinstance(v, dt.datetime):
        return v.replace(tzinfo=None)
    m = re.match(r'(\d{4})-(\d{2})-(\d{2})[ T](\d{1,2}):(\d{2})', str(v or ''))
    return dt.datetime(*map(int, m.groups())) if m else None


def righe(ws):
    r = list(ws.iter_rows(values_only=True))
    h = [str(x or '').strip() for x in r[0]]
    return [dict(zip(h, x)) for x in r[1:] if any(c not in (None, '') for c in x)]


def main(f_cfg, f_prod, canale):
    cfg = next((r for r in righe(openpyxl.load_workbook(f_cfg, data_only=True).worksheets[0])
                if str(r.get('channel_id') or '').strip() == canale), None)
    if not cfg:
        raise SystemExit('canale non trovato in Channel Configs: ' + canale)
    O = {'ctr': num(cfg.get('coach_obiettivo_ctr'), 3.5), 'ret30': num(cfg.get('coach_obiettivo_ret30'), 65),
         'ret60': num(cfg.get('coach_obiettivo_ret60'), 50)}
    N = int(num(cfg.get('coach_finestra_video'), 3)); MIN_IMP = num(cfg.get('coach_min_impression'), 1000)   # 6 nov, Giorgio: N video con 72 ore E 1000 impression su quegli N video della versione attiva
    wb = openpyxl.load_workbook(f_prod, data_only=True)
    prod = righe(wb.worksheets[0])
    perf = righe(wb['Performance']) if 'Performance' in wb.sheetnames else []
    ultimo = {}   # ultima rilevazione per video
    for p in perf:
        v = str(p.get('youtube_video_id') or '').strip()
        if v and (v not in ultimo or (data(p.get('data_rilevazione')) or dt.datetime.min) >= (data(ultimo[v].get('data_rilevazione')) or dt.datetime.min)):
            ultimo[v] = p
    nuovo = any('giorni_report' in p for p in perf)   # scheda Performance con la copertura dei report (dal 5 nov)

    def report_ok(p):
        if not nuovo:   # scheda vecchia senza la colonna: come prima
            return True
        return bool(p) and (num(p.get('giorni_report'), 0) or 0) >= 3 and not str(p.get('copertura_report') or '').startswith('incompleto')
    fr = os.path.join(os.path.dirname(__file__), 'canali', slug(canale), 'ricetta.json')
    ric = json.load(open(fr))
    vers = sorted(ric['versioni'], key=lambda x: data(x['dal']) or dt.datetime.min)
    video = []
    for r in prod:
        vid = str(r.get('youtube_video_id') or '').strip()
        ini = data(r.get('data_inizio_produzione')); pub = data(r.get('data_pubblicazione')) or ini
        if not vid or not ini:
            continue
        ver = None
        for x in vers:
            if ini >= (data(x['dal']) or dt.datetime.min):
                ver = x['n']
        p = ultimo.get(vid, {})
        video.append({'id': vid, 'titolo': str(r.get('titolo_italiano') or r.get('titolo_originale') or '')[:70], 'versione': ver,
                      'pubblicato': str(pub), 'ore': round((ADESSO - pub).total_seconds() / 3600, 1) if pub else 0,
                      'impression': num(p.get('impression'), 0), 'ctr': num(p.get('ctr')), 'views': num(p.get('views'), 0),
                      'ret30': num(p.get('ritenzione_30s')), 'ret60': num(p.get('ritenzione_60s')),
                      'report_ok': report_ok(p), 'giorni_report': num(p.get('giorni_report')), 'copertura_report': str(p.get('copertura_report') or ''),
                      'in_performance': bool(p)})
    # costo reale degli ultimi video (coach/costi/<slug>.tsv, scritto dai workflow), prove escluse
    costi = []
    ft = os.path.join(os.path.dirname(__file__), 'costi', slug(canale) + '.tsv')
    if os.path.exists(ft):
        for l in open(ft).read().splitlines()[1:]:
            c = l.split('\t')
            if len(c) > 3 and c[3].upper() != 'SI' and (len(c) < 7 or c[6].upper() in ('', 'OK')):   # giri bloccati esclusi dalla media
                costi.append(num(c[1], 0))
    BUD = num(cfg.get('coach_budget_video'))
    attiva = ric['versione_attiva']
    maturi = sorted([v for v in video if v['versione'] == attiva and v['ore'] >= 72], key=lambda v: v['pubblicato'])
    fin = maturi[-N:]
    fin_imp = [v for v in maturi if v['report_ok']][-N:]   # impression/CTR: solo video con >= 3 giorni di report completi
    attesa_rep = [v for v in video if v['in_performance'] and not v['report_ok']]
    esito = {'canale': canale, 'versione_attiva': attiva, 'obiettivi': O, 'finestra': N, 'video_versione': len([v for v in video if v['versione'] == attiva]),
             'video_maturi': len(maturi), 'video_finestra': fin, 'tutti_i_video': video,
             'budget_video': BUD, 'costo_medio_ultimi': round(sum(costi[-N:]) / len(costi[-N:]), 3) if costi else None,
             'costi_ultimi': costi[-N:], 'in_attesa_report': len(attesa_rep), 'video_in_attesa_report': [v['id'] for v in attesa_rep]}
    if BUD and costi and esito['costo_medio_ultimi'] > BUD * 1.05:   # il budget e' una regola fissa: prima si rientra nel budget
        esito.update({'stato': 'LEVA_COSTO', 'motivo': f"costo medio {esito['costo_medio_ultimi']} $ sopra il budget {BUD} $ a video"})
        return esito, fr
    # 5 nov 2026, Giorgio: da coach_min_views_retention (default 50) views TOTALI del canale (tutti i video sommati) si lavora ANCHE
    # sulla retention, in parallelo alla copertina: YouTube non spinge un video con poco coinvolgimento anche se il CTR e' buono.
    MIN_VR = num(cfg.get('coach_min_views_retention'), 50)
    tot_views = sum(v['views'] for v in video)
    conr = [v for v in video if v['views'] > 0 and (v['ret30'] is not None or v['ret60'] is not None)]
    def ret_tutti(k):
        b = [v for v in conr if v[k] is not None]; pv = sum(v['views'] for v in b)
        return round(sum(v[k] * v['views'] for v in b) / pv, 1) if pv else None
    R30, R60 = ret_tutti('ret30'), ret_tutti('ret60')
    if tot_views < MIN_VR:
        rt = {'stato': 'ATTESA_VIEWS', 'motivo': f'retention: {int(tot_views)} views totali su {int(MIN_VR)} necessarie'}
    elif R30 is None or R30 < O['ret30']:
        rt = {'stato': 'LEVA_RET30', 'motivo': f'retention 30 s {R30}% su {int(tot_views)} views totali (obiettivo {O["ret30"]}%)'}
    elif R60 is None or R60 < O['ret60']:
        rt = {'stato': 'LEVA_RET60', 'motivo': f'retention 60 s {R60}% su {int(tot_views)} views totali (obiettivo {O["ret60"]}%)'}
    else:
        rt = {'stato': 'OK', 'motivo': f'retention 30 s {R30}% / 60 s {R60}% su {int(tot_views)} views totali'}
    rt.update(views_totali=tot_views, ret30=R30, ret60=R60, minimo_views=MIN_VR)
    esito['retention'] = rt
    if len(fin) < N:
        esito.update({'stato': 'ATTESA', 'motivo': f'servono {N} video con almeno 72 ore nella versione {attiva}, ce ne sono {len(fin)}'})
        return esito, fr
    if len(fin_imp) < N:
        esito.update({'stato': 'ATTESA', 'motivo': f'servono {N} video con almeno 3 giorni di report impression nella versione {attiva}, ce ne sono {len(fin_imp)} '
                                                    f'({len(attesa_rep)} video in attesa di report)'})
        return esito, fr
    imp = sum(v['impression'] for v in fin_imp)
    clic = sum(v['impression'] * (v['ctr'] or 0) / 100 for v in fin_imp)
    ctr = round(clic / imp * 100, 2) if imp else 0.0

    def ret(k):
        base = [v for v in fin if v[k] is not None and v['views'] >= 30]
        if len(base) < 2:
            base = [v for v in maturi[-5:] if v[k] is not None and v['views'] >= 30]
        pv = sum(v['views'] for v in base)
        return (round(sum(v[k] * v['views'] for v in base) / pv, 1) if pv else None), len(base)
    r30, n30 = ret('ret30'); r60, n60 = ret('ret60')
    esito['misure'] = {'ctr': ctr, 'impression_totali': imp, 'ret30': r30, 'video_ret30': n30, 'ret60': r60, 'video_ret60': n60}
    esito['misure'].update(in_attesa_report=len(attesa_rep))
    if imp < MIN_IMP:   # 6 nov, Giorgio: poche impression sui video della copertina attuale = dati insufficienti, non si cambia
        esito.update({'stato': 'ATTESA_IMPRESSION', 'motivo': f'copertine ferme: {int(imp)} impression sui {len(fin_imp)} video della versione {attiva} (minimo {int(MIN_IMP)}); se restano basse la leva e\' titolo/argomento, non la copertina'})
    elif ctr < O['ctr']:
        esito.update({'stato': 'LEVA_CTR', 'motivo': f'CTR {ctr}% su {int(imp)} impression (obiettivo {O["ctr"]}%)'})
    elif r30 is None or r30 < O['ret30']:
        esito.update({'stato': 'LEVA_RET30', 'motivo': f'retention 30 s {r30}% (obiettivo {O["ret30"]}%)'})
    elif r60 is None or r60 < O['ret60']:
        esito.update({'stato': 'LEVA_RET60', 'motivo': f'retention 60 s {r60}% (obiettivo {O["ret60"]}%)'})
    else:
        esito.update({'stato': 'OK', 'motivo': 'tutti i parametri rispettati'})
    return esito, fr


if __name__ == '__main__':
    e, fr = main(*sys.argv[1:4])
    json.dump(e, open(os.path.join(os.path.dirname(fr), 'ultimo_calcolo.json'), 'w'), ensure_ascii=False, indent=1, default=str)
    print(json.dumps({k: v for k, v in e.items() if k != 'tutti_i_video'}, ensure_ascii=False, indent=1, default=str))
