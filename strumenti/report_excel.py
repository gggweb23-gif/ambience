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
SOTT = Border(bottom=Side(style='thin', color='BBBBBB'))


def num(v):
    try:
        return float(str(v).replace('%', '').replace(',', '.'))
    except Exception:
        return None


def main():
    dati = json.load(open(sys.argv[1] if len(sys.argv) > 1 else 'coach/performance_dati.json'))
    oggi = dt.date.today().isoformat()
    wb = Workbook(); ws = wb.active; ws.title = 'Performance'
    ws.column_dimensions['A'].width = 18; ws.column_dimensions['B'].width = 58
    for c in 'CDEF':
        ws.column_dimensions[c].width = 15
    ws['A1'] = f'PERFORMANCE CANALI - {oggi}'; ws['A1'].font = Font(bold=True, size=16)
    ws['A2'] = 'OBIETTIVI DA SUPERARE:'; ws['A2'].font = Font(bold=True)
    ws['B2'] = f"CTR copertina > {OBIETTIVI['ctr']:.1f}%   |   Ritenzione 30 s > {OBIETTIVI['ritenzione_30s']:.0f}%   |   Ritenzione 60 s > {OBIETTIVI['ritenzione_60s']:.0f}%"
    ws['B2'].font = Font(bold=True, color='B91C1C')
    ws['A3'] = 'Dati totali da quando il video e\' uscito. Verde = sopra obiettivo, rosso = sotto, grigio = dato non ancora arrivato (YouTube li da\' con 2-3 giorni di ritardo) o troppe poche visualizzazioni per calcolare la ritenzione.'
    ws['A3'].font = Font(italic=True, color='666666', size=9)
    r = 5
    for nome in sorted(dati):
        video = sorted(dati[nome], key=lambda x: str(x.get('data_pubblicazione') or ''))[-N:]
        if not video:
            continue
        ws.cell(r, 1, nome.upper()).font = Font(bold=True, size=13)
        for c in range(1, 7):
            ws.cell(r, c).fill = CANALE
        r += 1
        for c, t in enumerate(['Pubblicato', 'Titolo', 'Impression', 'CTR %', 'Ritenzione 30 s %', 'Ritenzione 60 s %'], 1):
            x = ws.cell(r, c, t); x.font = Font(bold=True, color='FFFFFF'); x.fill = TESTA; x.alignment = Alignment(horizontal='center', wrap_text=True)
        r += 1
        for v in video:
            imp, ctr, r30, r60 = (num(v.get(k)) for k in ('impression', 'ctr', 'ritenzione_30s', 'ritenzione_60s'))
            ws.cell(r, 1, str(v.get('data_pubblicazione') or '')[:16])
            ws.cell(r, 2, str(v.get('titolo') or ''))
            ws.cell(r, 3, int(imp) if imp is not None else 'in arrivo')
            for c, (val, ob) in zip((4, 5, 6), ((ctr, OBIETTIVI['ctr']), (r30, OBIETTIVI['ritenzione_30s']), (r60, OBIETTIVI['ritenzione_60s']))):
                vuoto = 'in arrivo' if (c == 4 or not imp or num(v.get('giorni_dalla_pubblicazione')) is None or num(v.get('giorni_dalla_pubblicazione')) < 3) else 'poche views'
                x = ws.cell(r, c, round(val, 1) if val is not None else vuoto)
                x.fill = GRIGIO if val is None or (c == 4 and not imp) else (VERDE if val >= ob else ROSSO)
                x.alignment = Alignment(horizontal='center')
            ws.cell(r, 3).alignment = Alignment(horizontal='center')
            for c in range(1, 7):
                ws.cell(r, c).border = SOTT
            r += 1
        r += 2   # spazio tra un canale e l'altro
    ws.freeze_panes = 'A5'
    os.makedirs('report', exist_ok=True)
    out = f'report/Performance_{oggi}.xlsx'
    wb.save(out); print(out)


if __name__ == '__main__':
    main()
