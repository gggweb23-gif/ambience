"""Regola di Giorgio (tutti i canali): la prima frase della descrizione YouTube e' sempre il titolo del video."""


def con_titolo(titolo, descr):
    t, d = str(titolo or '').strip(), str(descr or '').strip()
    if not t or d.lower().startswith(t.lower()):
        return d
    return t + '\n\n' + d
