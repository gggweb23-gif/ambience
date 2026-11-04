#!/usr/bin/env python3
"""ANALISI DELLE PERFORMANCE (sola lettura, gratis): per ogni canale legge Channel Configs, file di produzione e scheda Performance,
li mette in xlsx temporanei e lancia il calcolo del Coach (coach/coach_calcola.py) per i canali con ricetta.
Per i canali senza ricetta (es. KAO) calcola le stesse medie sugli ultimi video con almeno 72 ore. Non cambia niente."""
import json, os, subprocess, sys, tempfile, urllib.parse
import openpyxl
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import avvio_canali as A
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'coach'))
import coach_calcola as C


def valori(fid, scheda=None):
    pr = A.api(fid, 'GET', '?fields=sheets.properties')['sheets']
    nomi = [s['properties']['title'] for s in pr]
    t = scheda or next((n for n in nomi if not n.startswith('Performance')), nomi[0])
    if t not in nomi:
        return None
    return A.api(fid, 'GET', '/values/' + urllib.parse.quote(f"'{t}'!A1:AZZ3000")).get('values', [])


def xlsx(fogli, path):
    wb = openpyxl.Workbook(); wb.remove(wb.active)
    for nome, v in fogli.items():
        ws = wb.create_sheet(nome)
        for r in v or []:
            ws.append(r)
    wb.save(path)


d = tempfile.mkdtemp()
TAB = []   # riepilogo giornaliero per Giorgio (coach/riepilogo_performance.md)
cfgv = valori(A.CONFIGS); fcfg = os.path.join(d, 'cfg.xlsx'); xlsx({'Configs': cfgv}, fcfg)
h = cfgv[0]
for r in cfgv[1:]:
    cfg = dict(zip(h, r + [''] * (len(h) - len(r))))
    cid = str(cfg.get('channel_id') or '').strip(); fid = str(cfg.get('scout_production_sheet_id') or '').strip()
    if not cid or not fid or A.num(cfg.get('videos_per_day')) < 1:
        continue
    print('=' * 60); print(cid, '| coach_auto', cfg.get('coach_auto') or '-')
    try:
        prod = valori(fid); perf = valori(fid, 'Performance')
    except Exception as e:
        print('  file non leggibile', str(e)[:100]); continue
    stato_coach = 'escluso dal Coach (regola di Giorgio)' if cid == 'KAO PSICOLOGIA' else 'ricetta non ancora presente'
    fp = os.path.join(d, C.slug(cid) + '.xlsx'); xlsx({'Foglio1': prod, 'Performance': perf or [[]]}, fp)
    if os.path.exists(os.path.join('coach', 'canali', C.slug(cid), 'ricetta.json')):
        try:
            e, _ = C.main(fcfg, fp, cid)
            stato_coach = f"{e.get('stato')}: {e.get('motivo')}"
            for v in e.get('tutti_i_video', [])[-6:]:
                print('    video', v['pubblicato'][:16], 'versione', v['versione'], 'ore', v['ore'], '|', v['titolo'][:40])
            print(json.dumps({k: v for k, v in e.items() if k in ('stato', 'motivo', 'misure', 'versione_attiva', 'video_maturi', 'costo_medio_ultimi', 'budget_video')},
                             ensure_ascii=False, default=str))
            for v in e.get('video_finestra', []):
                print('   ', v['pubblicato'][:16], '|', v['titolo'][:50], '| imp', v['impression'], '| ctr', v['ctr'], '| ret30', v['ret30'], '| ret60', v['ret60'], '| views', v['views'])
        except Exception as ex:
            print('  calcolo coach non riuscito:', str(ex)[:200])
    if perf and len(perf) > 1:   # medie semplici sugli ultimi 5 video con almeno 3 giorni
        ph = perf[0]; rows = [dict(zip(ph, x + [''] * (len(ph) - len(x)))) for x in perf[1:]]
        mat = [x for x in rows if C.num(x.get('giorni_dalla_pubblicazione')) >= 3][-5:]
        imp = sum(C.num(x.get('impression'), 0) for x in mat); clic = sum(C.num(x.get('impression'), 0) * C.num(x.get('ctr'), 0) / 100 for x in mat)
        vw = [x for x in mat if C.num(x.get('views'), 0) >= 30]
        pv = sum(C.num(x.get('views'), 0) for x in vw)
        r30 = sum(C.num(x.get('ritenzione_30s'), 0) * C.num(x.get('views'), 0) for x in vw if C.num(x.get('ritenzione_30s')) is not None) / pv if pv else None
        r60 = sum(C.num(x.get('ritenzione_60s'), 0) * C.num(x.get('views'), 0) for x in vw if C.num(x.get('ritenzione_60s')) is not None) / pv if pv else None
        print(f"  ultimi {len(mat)} video (>=3 giorni): impression {imp:.0f} | CTR {clic / imp * 100 if imp else 0:.2f}% (obiettivo {cfg.get('coach_obiettivo_ctr') or 3.5}) | "
              f"ret30 {r30 if r30 is None else round(r30, 1)} (obiettivo {cfg.get('coach_obiettivo_ret30') or 65}) | ret60 {r60 if r60 is None else round(r60, 1)} "
              f"(obiettivo {cfg.get('coach_obiettivo_ret60') or 50}) | video con >=30 views: {len(vw)} | pubblici in tutto: {len(rows)}")
        oc, o30, o60 = (C.num(cfg.get(k), dflt) for k, dflt in (('coach_obiettivo_ctr', 3.5), ('coach_obiettivo_ret30', 65), ('coach_obiettivo_ret60', 50)))
        ok = lambda v, o: '—' if v is None else (f"{v:.1f}%".replace('.', ',') + (' ✅' if v >= o else ' ❌'))
        ctr = clic / imp * 100 if imp else None
        nome = str(cfg.get('channel_name') or cid).strip()
        TAB.append(f"| **{nome}** | {len(mat)} video, " + f"{imp:,.0f}".replace(',', '.') + f" impression | {ok(ctr, oc) if imp >= 100 else '— (poche impression)'} | "
                   f"{ok(r30, o30)} / {ok(r60, o60)} | {stato_coach} |")
    else:
        TAB.append(f"| **{str(cfg.get('channel_name') or cid).strip()}** | nessun dato | — | — | {stato_coach} |")

os.makedirs('coach', exist_ok=True)
import datetime as _dt
open('coach/riepilogo_performance.md', 'w').write(
    f"Riepilogo performance del {_dt.datetime.now(A.ZoneInfo('Europe/Rome')).strftime('%d/%m/%Y %H:%M')} (ultimi 5 video con almeno 3 giorni; obiettivi CTR 3,5% · ret30 65% · ret60 50%)\n\n"
    "| Canale | Ultimi video | CTR | Ritenzione 30 s / 60 s | Decisione del Coach |\n|---|---|---|---|---|\n" + "\n".join(TAB) + "\n")
print(open('coach/riepilogo_performance.md').read())
