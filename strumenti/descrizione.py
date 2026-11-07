"""Regola di Giorgio (tutti i canali): la prima frase della descrizione YouTube e' sempre il titolo del video."""


def pulisci_titolo(t):
    """7 nov: via le etichette dei competitor che non sono nostre ([NO AI], (4K), [HD], [FULL DOCUMENTARY]...)."""
    import re
    t = re.sub(r'\s*[\[(]\s*(no\s*ai|4k|hd|full\s*documentary|documentary|documentario( completo)?|animated|animazione)\s*[\])]', '', str(t or ''), flags=re.I)
    return ' '.join(t.split()).strip(' |-')


def con_titolo(titolo, descr):
    t, d = str(titolo or '').strip(), str(descr or '').strip()
    if not t or d.lower().startswith(t.lower()):
        return d
    return t + '\n\n' + d


def tag_con_titolo(titolo, tag):
    """Regola di Giorgio (tutti i canali): il titolo e' sempre anche uno dei tag (il primo). YouTube: max 500 caratteri in tutto."""
    lista = [x.strip() for x in (tag.split(',') if isinstance(tag, str) else (tag or [])) if str(x).strip()]
    t = ' '.join(str(titolo or '').replace(',', ' ').replace('<', ' ').replace('>', ' ').split())
    out, lung = [], 0
    for x in ([t] if t else []) + lista:
        if any(x.lower() == y.lower() for y in out):
            continue
        costo = len(x) + (2 if ' ' in x else 0) + (1 if out else 0)
        if lung + costo > 480:
            continue
        out.append(x); lung += costo
    return out
