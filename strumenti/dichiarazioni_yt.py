"""Dichiarazioni YouTube dopo il caricamento (6 nov 2026, Giorgio): "Promozione a pagamento" = No su tutti i video e gli Short.
Mai bloccante: se YouTube rifiuta, il video resta caricato e si scrive solo un avviso nel registro."""
import json, urllib.request


def nessuna_promozione(video_id, token):
    try:
        req = urllib.request.Request('https://www.googleapis.com/youtube/v3/videos?part=paidProductPlacementDetails', method='PUT',
                                     data=json.dumps({'id': video_id, 'paidProductPlacementDetails': {'hasPaidProductPlacement': False}}).encode(),
                                     headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
        urllib.request.urlopen(req, timeout=60).read()
        print('promozione a pagamento: No', flush=True)
    except Exception as e:
        print('promozione a pagamento non impostata:', str(e)[:150], flush=True)
