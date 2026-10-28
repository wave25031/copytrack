"""Stuurt 1 testmail. Gebruik: Actions -> copytrack -> Run workflow -> vink 'testmail' aan."""
import sys
from datetime import datetime, timezone

from notifier import send_email_notification

ok = send_email_notification(
    subject="Copy-tracker: testmail",
    body=f"Als je dit leest, werken de meldingen weer.\nVerstuurd: {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC",
)
sys.exit(0 if ok else 1)
