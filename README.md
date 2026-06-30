# HHConverter

Convert tournament hand histories from multiple poker rooms into **PokerStars-style** text for **Hand2Note 3** import.

Supports **PokerPlanets**, **GGPokerOK**, **UPPoker**, and **CoinPoker**, with optional Dropbox mirroring and Chico copy.

## Features

- GUI (`HHConverter.exe` or `python -m converter.gui`) and CLI (`python -m converter`)
- Per-room conversion to Hand2Note-compatible PokerStars format
- **Coin hands as PS** — basic PokerStars export for Hand2Note (no Coin Pro / `CPR_` tables required)
- Legacy Coin Pro layout still available (€, `CPR_` tables, Freeroll on Dropbox) when **Coin hands as PS** is off
- Hand ID namespacing per room to avoid collisions in one database
- Optional Dropbox mirror (raw PP/GG/UP, daily merged Coin files, Chico unchanged)
- Optional clear Import folder after convert
- Instructions in 7 languages (EN, RU, UK, KK, FR, ES, PL)

## Requirements

- **Python 3.11+** (for running from source)
- **Windows** (for the standalone `.exe` build)
- [tzdata](https://pypi.org/project/tzdata/) on Windows (included in build)

## Quick start (from source)

```powershell
cd Converter
python -m pip install -e .
copy config.example.json config.json
# Edit config.json or use the GUI Settings dialog
python -m converter.gui
```

CLI:

```powershell
python -m converter
python -m converter --config config.json -q
```

On first GUI launch, `config.json` is created next to the app if missing.

## Configuration

Copy `config.example.json` to `config.json`:

| Field | Description |
|-------|-------------|
| `import_path` | Folder with raw `.txt` hand histories |
| `export_path` | Converted output folder |
| `dropbox_base_path` | Dropbox root for mirrored hands (empty = off) |
| `dropbox_mode` | `"original"` or `"none"` |
| `chico_import_path` | Chico `.txt` folder to copy unchanged (or `null`) |
| `clear_import_after_convert` | Delete `*.txt` under Import after a successful run |
| `coin_as_ps` | Export Coin as basic PokerStars format (default **true**). Uncheck for legacy H2N Coin Pro layout |
| `player_alias` | Hero nickname in GG / UP / Coin output |

## Supported rooms

| Room | Input header | Export notes |
|------|----------------|--------------|
| PokerPlanets | `PokerPlanets Hand #` | PokerStars-style |
| GGPokerOK | `Poker Hand #TM5730…` | Numeric TM ids |
| UPoker | `Poker Hand #TM0…` | Hex TM ids |
| CoinPoker | `CoinPoker Hand #` | PS-style when `coin_as_ps` is on; legacy Coin module layout when off |

Chico files are copied as-is when `chico_import_path` is set (not converted).

## Build standalone Windows app

```powershell
.\build.ps1
```

Output: `dist\HHConverter\HHConverter.exe` (keep `_internal` beside the exe).

## Hand ID namespacing

- PokerPlanets: `111111` + original id
- GGPoker: `205730…` (from `TM5730…`)
- UPoker: `205872…` band
- Coin (PS mode): `333333` + original id
- Coin (legacy mode): original Coin ids

## Disclaimer

This project is not affiliated with Hand2Note, PokerStars, or any poker room. Use at your own risk. Comply with the terms of service of software and poker sites you use.

## License

MIT — see [LICENSE](LICENSE).
