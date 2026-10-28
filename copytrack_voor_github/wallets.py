"""
De wallets die we volgen omdat ze zowel op de 30-dagen- als de all-time-
ranglijst van Hyperliquid (https://app.hyperliquid.xyz/leaderboard) hoog
genoeg stonden op winst (PNL). Dat is het "niet toevallig deze week
geluk"-filter: consistent over twee verschillende tijdsvensters, niet een
gokje dat net die week raak was.

Eerste ronde (trader_01 t/m trader_11, naked_shorts_only, thank_you_jeff):
top-100 op beide ranglijsten. Tweede ronde (trader_13 e.v., wanyekest,
season_3_or_the_rope): zelfde filter, maar dieper doorzocht -- top-200 op
beide ranglijsten, om dichter bij de 20-30 wallets te komen die oorspronkelijk
het idee was.

Adressen zijn met de hand, 1-op-1 overgenomen van de Hyperliquid-explorer-
pagina (dus geen risico op een afgekapt/verkeerd karakter).

Voeg je later zelf een wallet toe (bijv. eentje die je apart hebt gevonden)?
Zet 'm gewoon in dezelfde vorm hieronder bij.
"""

WALLETS = [
    {"address": "0x2ee6bef5b7b63aeefc9059f1436dabe259c34d1c", "label": "trader_01"},
    {"address": "0x856c35038594767646266bc7fd68dc26480e910d", "label": "trader_02"},
    {"address": "0xb83de012dba672c76a7dbbbf3e459cb59d7d6e36", "label": "trader_03"},
    {"address": "0x45d26f28196d226497130c4bac709d808fed4029", "label": "trader_04"},
    {"address": "0xd47587702a91731dc1089b5db0932cf820151a91", "label": "trader_05"},
    {"address": "0x4f7634c03ec4e87e14725c84913ade523c6fad5a", "label": "trader_06"},
    {"address": "0xa312114b5795dff9b8db50474dd57701aa78ad1e", "label": "naked_shorts_only"},
    {"address": "0x939f95036d2e7b6d7419ec072bf9d967352204d2", "label": "trader_08"},
    {"address": "0x5b5d51203a0f9079f8aeb098a6523a13f298c060", "label": "trader_09"},
    {"address": "0xcac19662ec88d23fa1c81ac0e8570b0cf2ff26b3", "label": "trader_10"},
    {"address": "0xa87a233e8a7d8951ff790a2e39738086cb5f71b7", "label": "trader_11"},
    # trader_12 (0x7717a7a245d9f950e586822b8c9b46863ed7bd7e) is verwijderd: bij
    # het eerste testen bleek deze wallet tientallen coins tegelijk te shorten
    # (SPX, STABLE, TAO, VIRTUAL, kBONK, kSHIB, ...) -- typisch market-making-
    # /hedgingbot-gedrag, geen menselijke richting-beslissingen om te volgen.
    # Blijft bewust uitgesloten, ook nu hij bij de top-200-uitbreiding weer
    # in de consistente lijst opdook.
    {"address": "0x2d23b731e5f04996a2dfdbe434c7d922afdb5e00", "label": "thank_you_jeff"},

    # --- Tweede ronde: top-200 op beide ranglijsten (i.p.v. top-100) ---
    {"address": "0x8af700ba841f30e0a3fcb0ee4c4a9d223e1efa05", "label": "trader_13"},
    {"address": "0x5d2f4460ac3514ada79f5d9838916e508ab39bb7", "label": "trader_14"},
    {"address": "0x0d446c3372a9ba9cddef0eef7a1afab6dc0e8c0b", "label": "trader_15"},
    {"address": "0x77375a8c9d13bf79afb2a87f1b0ac1dfd5f5bf66", "label": "trader_16"},
    {"address": "0xc59498175d6d317642aeb97f895a7ce1aa992191", "label": "trader_17"},
    {"address": "0xff4cd3826ecee12acd4329aada4a2d3419fc463c", "label": "trader_18"},
    {"address": "0x6859da14835424957a1e6b397d8026b1d9ff7e1e", "label": "trader_19"},
    {"address": "0x8607a7d180de23645db594d90621d837749408d5", "label": "wanyekest"},
    {"address": "0x7839e2f2c375dd2935193f2736167514efff9916", "label": "trader_20"},
    {"address": "0x9cd0a696c7cbb9d44de99268194cb08e5684e5fe", "label": "trader_21"},
    {"address": "0x4e23288cee4960f9f962195c22948e4bc7ae20c3", "label": "trader_22"},
    {"address": "0x350e33a777d510616fbdb483d1de3b50d1edfcfb", "label": "trader_23"},
    {"address": "0x519c721de735f7c9e6146d167852e60d60496a47", "label": "trader_24"},
    {"address": "0xc926ddba8b7617dbc65712f20cf8e1b58b8598d3", "label": "trader_25"},
    {"address": "0x49e96e255ba418d08e66c35b588e2f2f3766e1d0", "label": "season_3_or_the_rope"},
]
