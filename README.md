# HHConverter

Convert tournament hand histories from multiple poker rooms into **PokerStars-style** text for **Hand2Note 3** import.

Supports **PokerPlanets**, **GGPokerOK**, **UPoker**, and **CoinPoker**, with optional Dropbox backup and **Chico** hands copy.

## Features

- GUI (`HHConverter.exe` or `python -m converter.gui`) and CLI (`python -m converter`)
- Per-room conversion to Hand2Note-compatible PokerStars format
- CoinPoker output matches the legacy Hand2Note Coin module layout (€, `CPR_` tables, UTC, Freeroll header on Dropbox copies)
- Hand ID namespacing per room to avoid collisions in one database
- Optional Dropbox backup (raw PP/GG/UP, daily merged Coin files, Chico unchanged)
- Optional clear Import folder after convert

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
| `player_alias` | Hero nickname in GG / UP / Coin output |

## Supported rooms

| Room | Input header | Notes |
|------|----------------|-------|
| PokerPlanets | `PokerPlanets Hand #` | PokerStars-style export |
| GGPokerOK | `Poker Hand #TM5730…` | Numeric TM ids |
| UPoker | `Poker Hand #TM0…` | Hex TM ids |
| CoinPoker | `CoinPoker Hand #` | H2N Coin module format |

Chico files are copied as-is when `chico_import_path` is set (not converted).

## Disclaimer

This project is not affiliated with Hand2Note, PokerStars, or any poker room. Use at your own risk. Comply with the terms of service of software and poker sites you use.

## License

MIT — see [LICENSE](LICENSE).
