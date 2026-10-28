"""
Stuurt een e-mail-melding zodra er iets gebeurd is (nieuw copy-signaal,
paper-trade geopend, paper-trade gesloten). Faalt dit (bijv. omdat
EMAIL_APP_PASSWORD nog leeg is), dan crasht het hele script NIET -- je ziet
gewoon een duidelijke melding in het scherm, en de rest (signalen loggen,
paper-portfolio bijhouden) blijft gewoon werken.
"""

import smtplib
from email.mime.text import MIMEText

from config import (
    EMAIL_ENABLED, SMTP_SERVER, SMTP_PORT, EMAIL_FROM, EMAIL_TO,
    EMAIL_APP_PASSWORD,
)


def send_email_notification(subject: str, body: str) -> bool:
    """Geeft True terug bij succes, False als het (om wat voor reden dan ook) niet lukte."""
    if not EMAIL_ENABLED:
        return False
    if not EMAIL_FROM:
        print("  [E-MAIL] Overgeslagen: geen e-mailadres ingesteld (secret EMAIL_ADRES).")
        return False
    if not EMAIL_APP_PASSWORD:
        print("  [E-MAIL] Overgeslagen: EMAIL_APP_PASSWORD is nog leeg in config.py "
              "(zie README.md voor hoe je die zelf aanmaakt).")
        return False

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=20) as server:
            server.starttls()
            server.login(EMAIL_FROM, EMAIL_APP_PASSWORD)
            server.sendmail(EMAIL_FROM, [EMAIL_TO], msg.as_string())
        print(f"  [E-MAIL] Melding verstuurd naar {EMAIL_TO}.")
        return True
    except Exception as e:
        print(f"  [E-MAIL] Versturen mislukt: {e}")
        return False
