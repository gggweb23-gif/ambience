#!/usr/bin/env python3
"""Invia per email l'ultimo foglio Excel del mattino (report/Performance_*.xlsx). Segreti GitHub: GMAIL_UTENTE, GMAIL_PASSWORD_APP, EMAIL_REPORT."""
import datetime as dt, glob, os, smtplib, sys
from email.message import EmailMessage
E = os.environ.get
if not (E('GMAIL_UTENTE') and E('GMAIL_PASSWORD_APP')):
    print('email non configurata: salto'); sys.exit(0)
f = sorted(glob.glob('report/Performance_*.xlsx'))[-1]
m = EmailMessage(); m['Subject'] = 'Performance canali ' + dt.date.today().strftime('%d/%m/%Y')
m['From'] = E('GMAIL_UTENTE'); m['To'] = E('EMAIL_REPORT') or E('GMAIL_UTENTE')
m.set_content('In allegato il foglio delle performance: ultimi 10 video di ogni canale con la riga TOTALE CANALE '
              '(durata media, % vista, visualizzazioni, ore, iscritti, impression, CTR, ritenzione 30 s e 60 s).')
m.add_attachment(open(f, 'rb').read(), maintype='application', subtype='vnd.openxmlformats-officedocument.spreadsheetml.sheet', filename=os.path.basename(f))
with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
    s.login(E('GMAIL_UTENTE'), E('GMAIL_PASSWORD_APP')); s.send_message(m)
print('email inviata:', os.path.basename(f))
