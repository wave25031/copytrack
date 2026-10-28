"""
Draai dit ALS EERSTE, één keer, voordat je track_positions.py gebruikt.

Dit haalt de ruwe API-response op voor de eerste wallet uit de lijst en
print 'm helemaal uit. Zo kun je met eigen ogen checken dat de veldnamen
("coin", "szi", "entryPx", "positionValue", ...) nog kloppen met wat
hyperliquid_client.py verwacht -- ik kan deze API namelijk niet zelf
live testen vanuit mijn eigen omgeving (geen internettoegang daar naartoe),
dus dit is de controle-stap om zeker te weten dat alles klopt voor je het
script op de automatische piloot laat draaien.

Draaien:
    python debug_dump.py
"""

import json
import truststore
truststore.inject_into_ssl()

from wallets import WALLETS
from hyperliquid_client import get_clearinghouse_state, extract_positions

if __name__ == "__main__":
    test_wallet = WALLETS[0]
    print(f"Test-aanroep voor {test_wallet['label']} ({test_wallet['address']}) ...\n")

    raw = get_clearinghouse_state(test_wallet["address"])
    print("=== RUWE API-RESPONSE ===")
    print(json.dumps(raw, indent=2)[:4000])  # eerste 4000 tekens, anders kan het heel lang worden
    print("\n=== UITGELEZEN POSITIES (wat het script hieruit haalt) ===")
    positions = extract_positions(raw)
    if not positions:
        print("Geen open posities op dit moment voor deze wallet (kan gewoon kloppen).")
    for coin, info in positions.items():
        richting = "LONG" if info["szi"] > 0 else "SHORT"
        print(f"  {coin}: {richting}, grootte={info['szi']}, entry={info['entry_px']}, "
              f"waarde=${info['position_value_usd']}")

    print("\nKlopt dit ongeveer met wat je op de Hyperliquid-website ziet voor dit "
          "adres? Zo ja: track_positions.py kan aan de slag. Zo nee: laat het weten, "
          "dan passen we de veldnamen in hyperliquid_client.py aan.")
