#!/usr/bin/env python3
"""CONTROLLO DI GESTIONE PER CANALE (deciso con Giorgio il 31 ott 2026). Gratis: nessuna chiamata a pagamento.
Ogni giorno aggiorna il foglio Google "Controllo di Gestione Canali" (ID in CONTROLLO_GESTIONE_ID) con:
- scheda Riepilogo: una riga per canale (costi reali, video, views, iscritti, CTR, ricavi, margine, giorni della prova di 60 giorni);
- scheda Costi: ogni giro video con il costo reale (anche i giri bloccati, che sono soldi spesi);
- scheda Ricavi: la compila Giorgio (mese, canale, ricavi in euro) finche' YouTube non da' i ricavi in automatico;
- scheda Regole: i parametri (cambio, giorni di prova, canali massimi) che Giorgio puo' cambiare.
Le colonne manuali del Riepilogo (data_avvio, decisione, note) non vengono mai sovrascritte.
Fonti: Channel Configs, file di produzione di ogni canale (Foglio1 + Performance), coach/costi/<slug>.tsv.
Segreto: GOOGLE_SA_KEY (fogli condivisi in modifica con coach-164@multichannel-coach.iam.gserviceaccount.com)."""
import datetime as dt, json, os, re, sys, unicodedata, urllib.parse, urllib.request

CONFIGS = os.environ.get('FOGLIO_CONFIGS', '1COMpgHJshcmz_a9s-WsjCO5xbhwxBazt-ZB0G_C7Rb0')
GESTIONE = os.environ.get('CONTROLLO_GESTIONE_ID', '')
OGGI = dt.datetime.now()
QUI = os.path.dirname(os.path.abspath(__file__))

RIEPILOGO = ['canale', 'nome_youtube', 'attivo', 'data_avvio', 'giorno_prova', 'giorni_al_giudizio', 'data_giudizio',
             'video_pubblicati', 'video_ultimi_30gg', 'costo_totale_eur', 'costo_medio_video_eur', 'budget_video_eur',
             'video_fuori_budget', 'costo_giri_bloccati_eur', 'costo_ultimi_30gg_eur', 'views_totali', 'views_ultimi_30gg',
             'iscritti_guadagnati', 'ctr_medio', 'ricavi_totali_eur', 'margine_eur', 'ricavi_per_1000_views_eur',
             'segnale', 'decisione', 'note', 'aggiornato']
MANUALI = ('data_avvio', 'decisione', 'note')
COSTI = ['data', 'canale', 'costo_usd', 'costo_eur', 'prova', 'esito', 'link', 'dettaglio']
RICAVI = ['mese', 'canale', 'ricavi_eur', 'note']
REGOLE_DEFAULT = [
    ['parametro', 'valore', 'spiegazione'],
    ['cambio_usd_eur', '0,93', 'quanti euro vale 1 dollaro (i costi delle API sono in dollari)'],
    ['giorni_prova', '60', 'giorni di continuita\' per ogni canale prima di decidere se continuare o spegnere'],
    ['canali_attivi_max', '8', 'canali accesi insieme con l\'impostazione attuale (oltre: segnale ATTENZIONE)'],
    ['', '', ''],
    ['REGOLA', '', 'Ogni canale gira per giorni_prova giorni senza cambi di angolo. Al giorno giorni_prova il segnale diventa GIUDIZIO: '
                   'Giorgio decide CONTINUA o SPEGNI (colonna decisione). Se SPEGNI, il budget va su una nuova scommessa (nicchia, trend, formato).'],
    ['SEGNALI', '', 'IN PROVA = dentro i giorni di prova | GIUDIZIO = prova finita, serve la decisione | SOPRA BUDGET = costo medio '
                    'oltre il budget a video | FERMO = nessun video negli ultimi 7 giorni con il canale acceso'],
]


def slug(s):
    s = unicodedata.normalize('NFD', str(s)).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '_', s).strip('_')


def num(v, d=None):
    try:
        s = str(v).replace('%', '').replace('€', '').replace('$', '').strip()
        if re.match(r'^-?\d{1,3}(\.\d{3})+(,\d+)?$', s):   # 1.234,5
            s = s.replace('.', '')
        return float(s.replace(',', '.'))
    except Exception:
        return d


def data(v):
    m = re.match(r'(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{1,2}):(\d{2}))?', str(v or ''))
    if not m:
        return None
    g = [int(x) if x else 0 for x in m.groups()]
    return dt.datetime(*g)


def eur(x):
    return f'{x:.2f}'.replace('.', ',')


def token():
    from google.oauth2 import service_account
    from google.auth.transport.requests import Request
    cr = service_account.Credentials.from_service_account_info(json.loads(os.environ['GOOGLE_SA_KEY']),
                                                               scopes=['https://www.googleapis.com/auth/spreadsheets'])
    cr.refresh(Request())
    return cr.token


TK = None


def api(foglio, metodo, percorso, corpo=None):
    req = urllib.request.Request('https://sheets.googleapis.com/v4/spreadsheets/' + foglio + percorso,
                                 data=json.dumps(corpo).encode() if corpo is not None else None, method=metodo,
                                 headers={'Authorization': 'Bearer ' + TK, 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode() or '{}')


def schede(foglio):
    return [s['properties']['title'] for s in api(foglio, 'GET', '?fields=sheets.properties')['sheets']]


def leggi(foglio, scheda, area='A1:AZZ5000'):
    v = api(foglio, 'GET', '/values/' + urllib.parse.quote(f"'{scheda}'!{area}")).get('values', [])
    if not v:
        return []
    h = [str(x).strip() for x in v[0]]
    return [dict(zip(h, r + [''] * (len(h) - len(r)))) for r in v[1:] if any(str(c).strip() for c in r)]


def scrivi(foglio, scheda, righe):
    api(foglio, 'POST', '/values/' + urllib.parse.quote(f"'{scheda}'!A1:AZZ5000") + ':clear', {})
    api(foglio, 'PUT', '/values/' + urllib.parse.quote(f"'{scheda}'!A1") + '?valueInputOption=USER_ENTERED', {'values': righe})


def prepara(foglio):
    """Crea le schede mancanti; Ricavi e Regole si creano una volta sola e poi le gestisce Giorgio."""
    gia = schede(foglio)
    nuove = [s for s in ('Riepilogo', 'Costi', 'Ricavi', 'Regole') if s not in gia]
    if nuove:
        api(foglio, 'POST', ':batchUpdate', {'requests': [{'addSheet': {'properties': {'title': s}}} for s in nuove]})
    if 'Ricavi' in nuove:
        scrivi(foglio, 'Ricavi', [RICAVI])
    if 'Regole' in nuove:
        scrivi(foglio, 'Regole', REGOLE_DEFAULT)
    vecchie = [s for s in gia if s not in ('Riepilogo', 'Costi', 'Ricavi', 'Regole')]
    if vecchie and gia == vecchie:   # foglio nuovo: si toglie il "Foglio1" vuoto
        ids = {s['properties']['title']: s['properties']['sheetId'] for s in api(foglio, 'GET', '?fields=sheets.properties')['sheets']}
        api(foglio, 'POST', ':batchUpdate', {'requests': [{'deleteSheet': {'sheetId': ids[s]}} for s in vecchie]})


def costi_canale(canale, cambio):
    f = os.path.join(QUI, 'costi', slug(canale) + '.tsv')
    out = []
    if os.path.exists(f):
        for l in open(f).read().splitlines()[1:]:
            c = l.split('\t') + [''] * 8
            usd = num(c[1], 0)
            out.append({'data': c[0], 'usd': usd, 'eur': usd * cambio, 'prova': (c[3] or 'NO').upper(), 'link': c[4],
                        'dettaglio': c[5][:300], 'esito': (c[6] or 'OK').upper()})
    return out


def main():
    global TK
    if not GESTIONE:
        raise SystemExit('manca CONTROLLO_GESTIONE_ID')
    TK = token()
    prepara(GESTIONE)
    regole = {r.get('parametro', ''): r.get('valore', '') for r in leggi(GESTIONE, 'Regole')}
    cambio = num(regole.get('cambio_usd_eur'), 0.93)
    prova_gg = int(num(regole.get('giorni_prova'), 60))
    max_attivi = int(num(regole.get('canali_attivi_max'), 8))
    vecchio = {r.get('canale', ''): r for r in leggi(GESTIONE, 'Riepilogo')}
    ricavi = {}
    for r in leggi(GESTIONE, 'Ricavi'):
        ricavi[r.get('canale', '').strip()] = ricavi.get(r.get('canale', '').strip(), 0) + (num(r.get('ricavi_eur'), 0) or 0)
    cfg_scheda = schede(CONFIGS)[0]
    canali = [r for r in leggi(CONFIGS, cfg_scheda) if str(r.get('channel_id', '')).strip()]
    riep, log_costi, attivi = [RIEPILOGO], [COSTI], 0
    for cfg in canali:
        can = str(cfg['channel_id']).strip()
        attivo = (num(cfg.get('videos_per_day'), 0) or 0) > 0
        attivi += attivo
        cs = costi_canale(can, cambio)
        for c in cs:
            log_costi.append([c['data'], can, eur(c['usd']), eur(c['eur']), c['prova'], c['esito'], c['link'], c['dettaglio']])
        veri = [c for c in cs if c['prova'] != 'SI' and c['esito'] == 'OK']
        bloccati = [c for c in cs if c['esito'] != 'OK']
        bud = num(cfg.get('coach_budget_video'))
        pubbl, views, views30, iscr, imp, clic, errore = [], 0, 0, 0, 0, 0, ''
        fid = str(cfg.get('scout_production_sheet_id') or '').strip()
        if fid:
            try:
                sch = schede(fid)
                for r in leggi(fid, sch[0]):
                    d = data(r.get('data_pubblicazione'))
                    if str(r.get('status', '')).strip() == 'Completato' and d:
                        pubbl.append(d)
                if 'Performance' in sch:
                    ultimo, vecchi = {}, {}
                    for p in leggi(fid, 'Performance'):
                        v, d = str(p.get('youtube_video_id', '')).strip(), data(p.get('data_rilevazione'))
                        if not v or not d:
                            continue
                        if v not in ultimo or d >= ultimo[v][0]:
                            ultimo[v] = (d, p)
                        if d <= OGGI - dt.timedelta(days=30) and (v not in vecchi or d >= vecchi[v][0]):
                            vecchi[v] = (d, p)
                    for v, (d, p) in ultimo.items():
                        vw = num(p.get('views'), 0) or 0
                        views += vw; views30 += vw - (num(vecchi[v][1].get('views'), 0) or 0 if v in vecchi else 0)
                        iscr += num(p.get('iscritti'), 0) or 0
                        im, ct = num(p.get('impression'), 0) or 0, num(p.get('ctr'))
                        if im and ct is not None:
                            imp += im; clic += im * ct / 100
            except Exception as e:
                errore = 'file di produzione non leggibile: ' + str(e)[:80]
        man = vecchio.get(can, {})
        avvio = data(man.get('data_avvio')) or (min(pubbl) if pubbl else None)
        giorno = (OGGI - avvio).days + 1 if avvio else 0
        giudizio = avvio + dt.timedelta(days=prova_gg) if avvio else None
        costo_tot = sum(c['eur'] for c in cs)
        medio = sum(c['eur'] for c in veri) / len(veri) if veri else 0
        fuori = sum(1 for c in veri if bud and c['eur'] > bud * 1.02)
        c30 = sum(c['eur'] for c in cs if (data(c['data']) or OGGI) >= OGGI - dt.timedelta(days=30))
        ric = ricavi.get(can, 0) + ricavi.get(str(cfg.get('channel_name') or '').strip(), 0)
        segnali = []
        if attivo and giorno and giorno <= prova_gg:
            segnali.append(f'IN PROVA (giorno {giorno} di {prova_gg})')
        if giorno > prova_gg and not str(man.get('decisione', '')).strip():
            segnali.append('GIUDIZIO: decidi CONTINUA o SPEGNI')
        if bud and veri and medio > bud * 1.02:
            segnali.append('SOPRA BUDGET')
        if attivo and pubbl and max(pubbl) < OGGI - dt.timedelta(days=7):
            segnali.append('FERMO')
        if errore:
            segnali.append(errore)
        riep.append([can, cfg.get('channel_name', ''), 'SI' if attivo else 'NO',
                     man.get('data_avvio') or (avvio.strftime('%Y-%m-%d') if avvio else ''),
                     giorno or '', max(0, prova_gg - giorno + 1) if avvio else '', giudizio.strftime('%Y-%m-%d') if giudizio else '',
                     len(pubbl), sum(1 for d in pubbl if d >= OGGI - dt.timedelta(days=30)),
                     eur(costo_tot), eur(medio), eur(bud) if bud else '', fuori, eur(sum(c['eur'] for c in bloccati)), eur(c30),
                     int(views), int(views30), int(iscr), (eur(clic / imp * 100) + '%') if imp else '',
                     eur(ric), eur(ric - costo_tot), eur(ric / views * 1000) if views else '',
                     ' | '.join(segnali), man.get('decisione', ''), man.get('note', ''), OGGI.strftime('%Y-%m-%d %H:%M')])
    if attivi > max_attivi:
        riep.append([f'ATTENZIONE: {attivi} canali accesi, oltre il massimo di {max_attivi} della scheda Regole'])
    tot_costi = sum(num(r[9], 0) for r in riep[1:] if len(r) > 9)
    tot_ricavi = sum(num(r[19], 0) for r in riep[1:] if len(r) > 19)
    riep.append([])
    riep.append(['TOTALE', '', f'{attivi} accesi', '', '', '', '', '', '', eur(tot_costi), '', '', '', '', '', '', '', '', '',
                 eur(tot_ricavi), eur(tot_ricavi - tot_costi)])
    scrivi(GESTIONE, 'Riepilogo', riep)
    scrivi(GESTIONE, 'Costi', log_costi)
    print(f'controllo di gestione aggiornato: {len(canali)} canali, {attivi} accesi, costi {eur(tot_costi)} euro, ricavi {eur(tot_ricavi)} euro')


if __name__ == '__main__':
    main()
