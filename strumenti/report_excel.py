#!/usr/bin/env python3
"""FOGLIO EXCEL DEL MATTINO (9 nov 2026, richiesta di Giorgio: "poche informazioni chiare e ben ordinate, divise per canale").
Per ogni canale attivo: gli ultimi 10 video pubblicati, dal piu' vecchio al piu' nuovo, con data di pubblicazione, impression, CTR,
ritenzione a 30 s e a 60 s (totali da quando il video e' uscito, ad oggi). In alto gli obiettivi: CTR 3,5% - 30 s 65% - 60 s 50%.
Verde = sopra l'obiettivo, rosso = sotto, grigio = dato non ancora arrivato.
Legge coach/performance_dati.json (lo scrive strumenti/performance.py ogni mattina). Scrive report/Performance_AAAA-MM-GG.xlsx."""
import datetime as dt, json, os, sys
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

OBIETTIVI = {'ctr': 3.5, 'ritenzione_30s': 65.0, 'ritenzione_60s': 50.0}
N = 10
VERDE, ROSSO, GRIGIO = PatternFill('solid', fgColor='C6EFCE'), PatternFill('solid', fgColor='FFC7CE'), PatternFill('solid', fgColor='EDEDED')
TESTA = PatternFill('solid', fgColor='1F2937'); CANALE = PatternFill('solid', fgColor='DBEAFE')
AZZURRO = PatternFill('solid', fgColor='67E8F9')   # 15 nov (Giorgio): video VINCENTE, deve saltare all'occhio (diverso dal celeste dei titoli canale)
SOTT = Border(bottom=Side(style='thin', color='BBBBBB'))


def num(v):
    try:
        return float(str(v).replace('%', '').replace(',', '.'))
    except Exception:
        return None


def fonti_txt(f):
    """Percentuali per fonte e DOVE AGIRE (11 nov sera, Giorgio)."""
    tot = sum(f.values()) if f else 0
    if not tot:
        return ['-'] * 4 + ['dati in arrivo']
    pc = {k: round(f.get(k, 0) / tot * 100) for k in ('home', 'consigliati', 'ricerca', 'shorts')}
    if tot < 20:
        cons = 'troppe poche visualizzazioni: dato non ancora affidabile'
    else:
        top = max(pc, key=pc.get)
        cons = {'home': 'HOME: agire sulla COPERTINA (CTR) - il video viene proposto a chi non lo cerca',
                'consigliati': 'CONSIGLIATI: agire su ARGOMENTO e TITOLO agganciati ai video grandi del filone (stesse figure/eventi, tag simili)',
                'ricerca': 'RICERCA: agire su TITOLO, DESCRIZIONE e TAG con le parole che la gente cerca',
                'shorts': 'SHORT: le visite arrivano dagli Short - collegare gli Short al video lungo'}[top]
        if pc[top] < 40:
            cons = 'misto (nessuna fonte sopra il 40%): copertina e titolo insieme'
    return [pc['home'], pc['consigliati'], pc['ricerca'], pc['shorts'], cons]


def vincente(g, mediana):
    """15 nov (Giorgio): un video "funziona" se CTR >= 4% con almeno 500 impression, oppure fa almeno 3 volte le views medie del canale (min 100)."""
    v, ctr, imp = g.get('views') or 0, g.get('ctr'), g.get('impression') or 0
    if v < 50000:   # 21 nov (Giorgio): sotto le 50.000 views non e' un vincente da cui fare gemelli
        return False
    return bool((ctr is not None and ctr >= 4.0 and imp >= 500) or (mediana and v >= 100 and v >= 3 * mediana))


def main():
    dati = json.load(open(sys.argv[1] if len(sys.argv) > 1 else 'coach/performance_dati.json'))
    oggi = dt.date.today().isoformat()
    wb = Workbook(); ws = wb.active; ws.title = 'Performance'
    ws.column_dimensions['A'].width = 18; ws.column_dimensions['B'].width = 52
    for c in 'CDEFGHIJKLMNOPQ':
        ws.column_dimensions[c].width = 14
    ws.column_dimensions['R'].width = 70
    try:
        fonti_can = json.load(open('coach/performance_fonti_canale.json'))
    except Exception:
        fonti_can = {}
    ws['A1'] = f'PERFORMANCE CANALI - {oggi}'; ws['A1'].font = Font(bold=True, size=16)
    ws['A2'] = 'OBIETTIVI DA SUPERARE:'; ws['A2'].font = Font(bold=True)
    ws['B2'] = f"CTR copertina > {OBIETTIVI['ctr']:.1f}%   |   Ritenzione 30 s > {OBIETTIVI['ritenzione_30s']:.0f}%   |   Ritenzione 60 s > {OBIETTIVI['ritenzione_60s']:.0f}%"
    ws['B2'].font = Font(bold=True, color='B91C1C')
    ws['A3'] = 'Dati totali da quando il video e\' uscito. Verde = sopra obiettivo, rosso = sotto, grigio = dato non ancora arrivato (YouTube li da\' con 2-3 giorni di ritardo) o troppe poche visualizzazioni per calcolare la ritenzione.'
    ws['A3'].font = Font(italic=True, color='666666', size=9)
    ws['A4'] = ('DA DOVE ARRIVANO LE VISITE -> DOVE AGIRE:  HOME = YouTube lo propone a chi non lo cerca: conta la COPERTINA (CTR).  '
                'CONSIGLIATI = esce accanto/dopo altri video: conta ARGOMENTO e TITOLO agganciati ai video grandi del filone.  '
                'RICERCA = conta il TITOLO con le parole cercate.  SHORT = arrivano dagli Short.')
    ws['A4'].font = Font(italic=True, color='1D4ED8', size=9)
    try:
        quote = json.load(open('coach/performance_quote.json'))
    except Exception:
        quote = {}
    try:   # 15 nov: vincenti degli ultimi 90 giorni calcolati da performance.py (classifica per views al giorno)
        V90 = {n: {w['id']: w for w in x.get('video') or []} for n, x in json.load(open('coach/vincenti.json')).items()}
    except Exception:
        V90 = {}
    ws['A5'] = ('AZZURRO = VIDEO VINCENTE (CTR >= 4% con almeno 500 impression, oppure almeno 3 volte le views medie del canale). '
                'Classifica degli ultimi 90 giorni per views al giorno: i primi 3 sono i modelli dei video GEMELLI (metodo 50-50), circa 50% sul 1°, 30% sul 2°, 20% sul 3°. '
                'Foglio "Vincenti" per l\'elenco completo.')
    ws['A5'].font = Font(bold=True, color='0E7490', size=10)
    r = 7
    COL = ['Pubblicato', 'Titolo', 'Durata media visualizzazione', '% media visualizzata', 'Visualizzazioni', 'Tempo di visualizzazione (ore)',
           'Iscritti', 'Impression miniatura', 'CTR miniatura %', 'Ritenzione 30 s %', 'Ritenzione 60 s %',
           'Da HOME %', 'Da CONSIGLIATI %', 'Da RICERCA %', 'Da SHORT %', 'Entrate stimate €', 'RPM €', 'DOVE AGIRE']   # 22 nov (Giorgio): entrate e RPM per video
    NC = len(COL)
    mmss = lambda x: f'{int(x // 60)}:{int(round(x % 60)):02d}'
    for nome in sorted(dati):
        video = sorted(dati[nome], key=lambda x: str(x.get('data_pubblicazione') or ''))[-N:]
        if not video:
            continue
        ws.cell(r, 1, nome.upper()).font = Font(bold=True, size=13)
        for c in range(1, NC + 1):
            ws.cell(r, c).fill = CANALE
        r += 1
        for c, t in enumerate(COL, 1):
            x = ws.cell(r, c, t); x.font = Font(bold=True, color='FFFFFF'); x.fill = TESTA; x.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        ws.row_dimensions[r].height = 32
        r += 1
        # riga TOTALE del canale (come "Totale" di YouTube Studio, sugli stessi video)
        righe = []
        for v in video:
            g = {k: num(v.get(k)) for k in ('views', 'durata_media_sec', 'perc_media_guardata', 'iscritti', 'impression', 'ctr', 'ritenzione_30s', 'ritenzione_60s', 'giorni_dalla_pubblicazione')}
            g['ore'] = (g['views'] or 0) * (g['durata_media_sec'] or 0) / 3600
            righe.append((v, g))
        vt = sum(g['views'] or 0 for _, g in righe); ore = sum(g['ore'] for _, g in righe)
        imp_t = sum(g['impression'] or 0 for _, g in righe); clic = sum((g['impression'] or 0) * (g['ctr'] or 0) / 100 for _, g in righe)
        perc = sum((g['views'] or 0) * (g['perc_media_guardata'] or 0) for _, g in righe) / vt if vt else None
        tot = ['TOTALE CANALE', f'ultimi {len(video)} video (fonti delle visite: tutto il canale, Short compresi, ultimi 28 giorni)', mmss(ore * 3600 / vt) if vt else '-', round(perc, 1) if perc is not None else '-', int(vt), round(ore, 1),
               int(sum(g['iscritti'] or 0 for _, g in righe)), int(imp_t), round(clic / imp_t * 100, 1) if imp_t else '-', '', '']
        for c, val in enumerate(tot, 1):
            x = ws.cell(r, c, val); x.font = Font(bold=True, size=12); x.fill = PatternFill('solid', fgColor='FEF3C7'); x.alignment = Alignment(horizontal='center' if c > 2 else 'left')
        if imp_t:
            ws.cell(r, 9).fill = VERDE if clic / imp_t * 100 >= OBIETTIVI['ctr'] else ROSSO
        ft = fonti_txt(fonti_can.get(nome) or {})
        ent_t = sum(num(v.get('entrate')) or 0 for v in video); vr_t = sum((g['views'] or 0) for v, g in righe if v.get('entrate') not in (None, ''))
        for c, val in zip((12, 13, 14, 15, 16, 17, NC), ft[:4] + [round(ent_t, 2) if vr_t else '-', round(ent_t / vr_t * 1000, 2) if vr_t else '-', ft[4]]):   # fonti di TUTTO il canale, ultimi 28 giorni (Short compresi)
            x = ws.cell(r, c, val); x.font = Font(bold=True); x.fill = PatternFill('solid', fgColor='FEF3C7')
        r += 1
        vv_ = sorted(g['views'] or 0 for _, g in righe); mediana = vv_[len(vv_) // 2] if vv_ else 0
        q = quote.get(nome) or {}
        for v, g in righe:
            w90 = (V90.get(nome) or {}).get(v.get('youtube_video_id'))
            vince = bool(w90) if V90.get(nome) is not None else vincente(g, mediana)
            ws.cell(r, 1, str(v.get('data_pubblicazione') or '')[:16])
            ws.cell(r, 2, str(v.get('titolo') or ''))
            ws.cell(r, 3, mmss(g['durata_media_sec']) if g['durata_media_sec'] else '-')
            ws.cell(r, 4, round(g['perc_media_guardata'], 1) if g['perc_media_guardata'] is not None else '-')
            ws.cell(r, 5, int(g['views'] or 0)); ws.cell(r, 6, round(g['ore'], 1)); ws.cell(r, 7, int(g['iscritti'] or 0))
            imp = g['impression']
            ws.cell(r, 8, int(imp) if imp is not None else 'in arrivo')
            for c, (val, ob) in zip((9, 10, 11), ((g['ctr'], OBIETTIVI['ctr']), (g['ritenzione_30s'], OBIETTIVI['ritenzione_30s']), (g['ritenzione_60s'], OBIETTIVI['ritenzione_60s']))):
                vuoto = 'in arrivo' if (c == 9 or not imp or g['giorni_dalla_pubblicazione'] is None or g['giorni_dalla_pubblicazione'] < 3) else 'poche views'
                x = ws.cell(r, c, round(val, 1) if val is not None else vuoto)
                x.fill = GRIGIO if val is None or (c == 9 and not imp) else (VERDE if val >= ob else ROSSO)
            ft = fonti_txt(v.get('fonti') or {})
            ent = num(v.get('entrate')); rpm = round(ent / g['views'] * 1000, 2) if ent is not None and g['views'] else None
            for c, val in zip((12, 13, 14, 15, 16, 17, NC), ft[:4] + [round(ent, 2) if ent is not None else '-',
                              (str(rpm) + (' (poche views)' if g['views'] < 500 else '')) if rpm is not None else '-', ft[4]]):
                ws.cell(r, c, val)
            if vince:
                ws.cell(r, 2).fill = AZZURRO; ws.cell(r, 2).font = Font(bold=True)
                posto = (w90 or {}).get('posto')
                ws.cell(r, 2, (f'★ VINCENTE {posto}° ★  ' if posto else '★ VINCENTE ★  ') + str(v.get('titolo') or ''))
                x = ws.cell(r, NC, (('VINCENTE ' + str(posto) + '° - modello dei gemelli (' + str(int(q.get('quota_gemelli') or 0)) + '%)') if posto and posto <= 3 else 'VINCENTE (fuori dai primi 3: non fa da modello)') if (q.get('quota_gemelli') or 0) > 0
                            else 'VINCENTE - VUOI INIZIARE A FARE IL 50-50?')
                x.fill = AZZURRO; x.font = Font(bold=True)
            for c in range(1, NC + 1):
                ws.cell(r, c).border = SOTT
                if 2 < c < NC:
                    ws.cell(r, c).alignment = Alignment(horizontal='center')
            r += 1
        r += 2   # spazio tra un canale e l'altro
    ws.freeze_panes = 'A7'
    # 15 nov (Giorgio): vincenti degli ultimi 90 giorni, anche quelli piu' vecchi degli ultimi 10 video
    wv = wb.create_sheet('Vincenti')
    for c, w_ in zip('ABCDEFGH', (8, 70, 12, 12, 14, 12, 14, 30)):
        wv.column_dimensions[c].width = w_
    wv['A1'] = 'VIDEO VINCENTI (ultimi 90 giorni, o di sempre dove vincenti_giorni = TUTTO) - i vincenti sopra 50.000 views (fino a 3) sono i modelli dei gemelli, a turno'; wv['A1'].font = Font(bold=True, size=14)
    rv = 3
    try:
        tutti_v = json.load(open('coach/vincenti.json'))
    except Exception:
        tutti_v = {}
    for nome in sorted(tutti_v):
        x = tutti_v[nome]; qv = x.get('quota_gemelli') or 0
        wv.cell(rv, 1, nome.upper() + '  [' + str(x.get('periodo') or 'ultimi 90 giorni') + ']' + ('   (50-50 attivo: ' + str(int(qv)) + '% gemelli)' if qv > 0 else '   (50-50 non attivo: canale notizie o quota_gemelli 0)' if x.get('video') else '   (nessun video sopra ' + f"{int(x.get('min_views') or 50000):,}".replace(',', '.') + ' views: niente gemelli, solo video presi dai competitor)')).font = Font(bold=True, size=12)
        rv += 1
        for c, t in enumerate(['Posto', 'Titolo', 'Pubblicato', 'Views', 'Views al giorno', 'CTR %', 'Impression', 'Ruolo'], 1):
            y = wv.cell(rv, c, t); y.font = Font(bold=True, color='FFFFFF'); y.fill = TESTA
        rv += 1
        for w in x.get('video') or []:
            for c, val in enumerate([w['posto'], w['titolo'], w['pubblicato'], w['views'], w['views_giorno'], w['ctr'] if w['ctr'] is not None else '-', w['impression'],
                                     ('MODELLO GEMELLI ' + ('50%' if w['posto'] == 1 else '30%' if w['posto'] == 2 else '20%')) if w['posto'] <= 3 else 'riserva'], 1):
                y = wv.cell(rv, c, val)
                if w['posto'] <= 3:
                    y.fill = AZZURRO
            rv += 1
        rv += 1
    # 11 nov (Giorgio OK, punto 2 dal metodo Reed): quale RAMO del filone (playlist) guardano davvero, per fare piu' video di quel ramo
    wr = wb.create_sheet('Rami del filone')
    for c, w_ in zip('ABCDEFGH', (18, 40, 10, 14, 14, 12, 16, 16)):
        wr.column_dimensions[c].width = w_
    wr['A1'] = 'RAMI DEL FILONE - quale sotto-argomento funziona (tutti i video pubblici letti, non solo gli ultimi 10)'; wr['A1'].font = Font(bold=True, size=14)
    wr['A2'] = 'Il ramo e\' la playlist del video. Fare piu\' video del ramo con CTR e ritenzione piu\' alti.'; wr['A2'].font = Font(italic=True, color='666666', size=9)
    rr_ = 4
    for nome in sorted(dati):
        gruppi = {}
        for v in dati[nome]:
            gruppi.setdefault(str(v.get('playlist') or '').strip() or '(senza playlist)', []).append(v)
        if not gruppi:
            continue
        wr.cell(rr_, 1, nome.upper()).font = Font(bold=True, size=12)
        rr_ += 1
        for c, t in enumerate(['', 'Ramo (playlist)', 'Video', 'Visualizzazioni', 'Impression', 'CTR %', 'Ritenzione 30 s %', 'Ritenzione 60 s %'], 1):
            x = wr.cell(rr_, c, t); x.font = Font(bold=True, color='FFFFFF'); x.fill = TESTA
        rr_ += 1
        stat = []
        for g, vv in gruppi.items():
            imp = sum(num(v.get('impression')) or 0 for v in vv); clic = sum((num(v.get('impression')) or 0) * (num(v.get('ctr')) or 0) / 100 for v in vv)
            r30 = [num(v.get('ritenzione_30s')) for v in vv if num(v.get('ritenzione_30s')) is not None]
            r60 = [num(v.get('ritenzione_60s')) for v in vv if num(v.get('ritenzione_60s')) is not None]
            stat.append((clic / imp * 100 if imp else -1, g, len(vv), int(sum(num(v.get('views')) or 0 for v in vv)), int(imp),
                         round(clic / imp * 100, 1) if imp else '-', round(sum(r30) / len(r30), 1) if r30 else '-', round(sum(r60) / len(r60), 1) if r60 else '-'))
        for st in sorted(stat, reverse=True):
            for c, val in enumerate(['', *st[1:]], 1):
                x = wr.cell(rr_, c, val)
                if c == 6 and isinstance(val, float):
                    x.fill = VERDE if val >= OBIETTIVI['ctr'] else ROSSO
                if c == 7 and isinstance(val, float):
                    x.fill = VERDE if val >= OBIETTIVI['ritenzione_30s'] else ROSSO
                if c == 8 and isinstance(val, float):
                    x.fill = VERDE if val >= OBIETTIVI['ritenzione_60s'] else ROSSO
            rr_ += 1
        rr_ += 1
    os.makedirs('report', exist_ok=True)
    out = f'report/Performance_{oggi}.xlsx'
    wb.save(out); print(out)


if __name__ == '__main__':
    main()
