"""
Heel dun laagje bovenop Hyperliquid's publieke /info-API.

Documentatie: https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api
Geen API-key nodig, geen login nodig -- het is puur het uitlezen van
publieke, on-chain positie-informatie van een wallet-adres.

We gebruiken hier ALLEEN het "clearinghouseState"-request-type: dat geeft de
huidige open posities van een account terug. We plaatsen zelf geen orders,
we schrijven niks -- alleen lezen.
"""

import time
import requests
from config import HYPERLIQUID_INFO_URL


def get_clearinghouse_state(address: str) -> dict:
    """
    Haalt de huidige open posities + accountinfo op voor 1 wallet-adres.

    Geeft de ruwe JSON-response terug (dict). Belangrijkste veld:
    response["assetPositions"] -- lijst van open posities, elk met een
    "position"-dict met o.a. "coin", "szi" (grootte; positief = long,
    negatief = short), "entryPx", "positionValue".

    Gooit een requests.exceptions.RequestException als het misgaat (geen
    internet, Hyperliquid down, etc.) -- vang dit af in de aanroepende code
    zodat 1 kapotte request niet de hele ronde langs alle wallets stopt.
    """
    payload = {"type": "clearinghouseState", "user": address}
    resp = requests.post(HYPERLIQUID_INFO_URL, json=payload, timeout=15)
    resp.raise_for_status()
    return resp.json()


def extract_positions(raw_state: dict) -> dict:
    """
    Zet de ruwe API-response om naar een simpel dict: {coin: {...}}.

    We doen dit defensief (met .get()) omdat we de exacte schema-details
    niet 100% kunnen verifiëren zonder de API zelf te kunnen aanroepen
    vanuit deze omgeving -- als Hyperliquid ooit een veldnaam verandert,
    crasht dit niet keihard maar geeft het gewoon minder info terug.

    Controleer bij de EERSTE keer draaien altijd even de ruwe output (zie
    debug_dump.py) om te checken dat de veldnamen nog kloppen.
    """
    positions = {}
    for entry in raw_state.get("assetPositions", []):
        pos = entry.get("position", {})
        coin = pos.get("coin")
        szi_raw = pos.get("szi")
        if coin is None or szi_raw is None:
            continue
        try:
            szi = float(szi_raw)
        except (TypeError, ValueError):
            continue
        if szi == 0:
            continue  # geen open positie (meer)
        entry_px = pos.get("entryPx")
        position_value = pos.get("positionValue")
        positions[coin] = {
            "szi": szi,
            "entry_px": float(entry_px) if entry_px is not None else None,
            "position_value_usd": abs(float(position_value)) if position_value is not None else None,
        }
    return positions


def get_positions(address: str) -> dict:
    """Gemak-functie: direct van wallet-adres naar {coin: {...}}-dict."""
    raw = get_clearinghouse_state(address)
    return extract_positions(raw)


def get_all_mids() -> dict:
    """
    Haalt de actuele (midden-)marktprijs op voor ALLE coins tegelijk, in 1
    request. Gebruikt door de paper-portfolio: wij "kopen" op de huidige
    marktprijs op het moment dat we het signaal zien (niet op de -- vaak
    alweer verouderde -- instapprijs van de trader die we volgen), en
    controleren elke run of een open paper-trade de stop-loss of take-profit
    geraakt heeft.

    Geeft een dict terug: {coin: prijs (float)}.
    """
    payload = {"type": "allMids"}
    resp = requests.post(HYPERLIQUID_INFO_URL, json=payload, timeout=15)
    resp.raise_for_status()
    raw = resp.json()
    prices = {}
    for coin, price_raw in raw.items():
        try:
            prices[coin] = float(price_raw)
        except (TypeError, ValueError):
            continue
    return prices


def polite_sleep(seconds: float):
    time.sleep(seconds)
