from __future__ import annotations

import sys
import threading
import tkinter as tk
import tkinter.font as tkfont
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

from converter import __version__
from converter.engine import process_all
from converter.settings import (
    Settings,
    assets_dir,
    default_config_path,
    default_settings,
    ensure_default_config,
    is_path_set,
    load_settings,
    path_display,
    save_settings,
)

_INFO_LANGUAGE_LABELS: dict[str, str] = {
    "en": "English",
    "ru": "Русский",
    "uk": "Українська",
    "kk": "Қазақша",
    "fr": "Français",
    "es": "Español",
    "pl": "Polski",
}
_INFO_CLOSE_LABELS: dict[str, str] = {
    "en": "Close",
    "ru": "Закрыть",
    "uk": "Закрити",
    "kk": "Жабу",
    "fr": "Fermer",
    "es": "Cerrar",
    "pl": "Zamknij",
}
_INFO_TITLE_LABELS: dict[str, str] = {
    "en": "Instructions",
    "ru": "Инструкция",
    "uk": "Інструкція",
    "kk": "Нұсқаулық",
    "fr": "Instructions",
    "es": "Instrucciones",
    "pl": "Instrukcja",
}
_INFO_TEXTS: dict[str, str] = {
    "en": """\
Hand History Converter

1. Open Settings (gear icon) to configure:
   • Import folder — raw hand history .txt / .zip files (default: import/)
   • Export folder — converted output (default: export/)
   • Clear Import folder after converting — removes source .txt/.zip files when done (after Dropbox copy, if enabled)
   • Coin hands as PS - export CoinPoker as PokerStars (for Hand2Note without Pro/Asia subscription)
   • Copy to Dropbox — mirrors raw hands to Dropbox; shows Dropbox and optional Chico folders
   • Import from folders — also watch PokerPlanets and Downloads folders for new files only
   • Clear folders after import — with "Copy to Dropbox" on, delete only processed files from watched folders after copy (never deletes Chico originals, unprocessed or pre–first-run Downloads files)
   • Nickname — hero name in converted GG / UP / Coin hands (default: Hero)

2. Put .txt hand histories (or GG/UP .zip archives) in the Import folder. Rooms: PokerPlanets, GGPokerOK, UPpoker, CoinPoker (tournaments + cash).

3. Click Convert.
   • Converted files are written to Export.
   • .zip hand histories are unpacked and converted; with Copy to Dropbox, tournament summaries from separate zips go to Dropbox …/year/summaries.
   • With Copy to Dropbox: PP / GG / UP raw files go to Dropbox.
   • Chico .txt files copy unchanged to Dropbox (if set); originals in the Chico folder are kept.
   • Import from folders: only new files since the last run are processed. Downloads files older than the app's first-run date are ignored to avoid duplicates already in the Hand2Note database. Import those via the Import folder manually if needed.
   • If you don't want your cash hands to get into the Dropbox do not use H2N3's auto import!

""",
    "ru": """\
Конвертер истории раздач

1. Откройте Настройки (иконка шестерёнки) для настройки:
   • Папка Import — исходные .txt / .zip файлы истории раздач (по умолчанию: import/)
   • Папка Export — сконвертированные файлы (по умолчанию: export/)
   • Очистить папку Import после конвертации — удаляет исходные .txt/.zip после завершения (после копирования в Dropbox, если включено)
   • Coin hands as PS — экспорт CoinPoker в формате PokerStars (для Hand2Note без подписки Pro/Asia)
   • Копировать в Dropbox — копирует исходные файлы в Dropbox; открывает поля Dropbox и Chico (необязательно)
   • Импорт из папок — также следит за папками PokerPlanets и Downloads (только новые файлы)
   • Очистить папки после импорта — при включённом Dropbox удаляет только обработанные файлы из доп. папок (не удаляет оригиналы Chico, необработанные и файлы Downloads старше даты первого запуска)
   • Никнейм — имя героя в конвертированных раздачах GG / UP / Coin (по умолчанию: Hero)

2. Положите .txt (или .zip GG/UP) в папку Import. Румы: PokerPlanets, GGPokerOK, UPpoker, CoinPoker (турниры и кэш).

3. Нажмите Convert.
   • Сконвертированные файлы сохраняются в Export.
   • Архивы .zip с раздачами распаковываются; при копировании в Dropbox саммари из отдельных zip попадают в …/year/summaries.
   • При копировании в Dropbox: исходные PP / GG / UP копируются в Dropbox.
   • Файлы Chico копируются в Dropbox без изменений (если указана папка); оригиналы в папке Chico не удаляются.
   • Импорт из папок обрабатывает только новые файлы с прошлого запуска. Файлы в Downloads старше даты первого запуска приложения игнорируются, чтобы не дублировать раздачи уже в базе Hand2Note. При необходимости импортируйте их вручную через папку Import.
   • Если не хотите, чтобы кэш-раздачи попадали в Dropbox, не используйте автоимпорт H2N3!

""",
    "uk": """\
Конвертер історії роздач

1. Відкрийте Налаштування (іконка шестерні) для налаштування:
   • Папка Import — вихідні .txt / .zip файли історії роздач (за замовчуванням: import/)
   • Папка Export — сконвертовані файли (за замовчуванням: export/)
   • Очистити папку Import після конвертації — видаляє вихідні .txt/.zip після завершення (після копіювання в Dropbox, якщо увімкнено)
   • Coin hands as PS — експорт CoinPoker у форматі PokerStars (для Hand2Note без підписки Pro/Asia)
   • Копіювати в Dropbox — копіює вихідні файли в Dropbox; показує поля Dropbox і Chico (необов'язково)
   • Імпорт з папок — також стежить за папками PokerPlanets і Downloads (лише нові файли)
   • Очистити папки після імпорту — з увімкненим Dropbox видаляє лише оброблені файли з додаткових папок (не видаляє оригінали Chico, необроблені та файли Downloads старші за дату першого запуску)
   • Нікнейм — ім'я героя в сконвертованих роздачах GG / UP / Coin (за замовчуванням: Hero)

2. Покладіть .txt (або .zip GG/UP) у папку Import. Руми: PokerPlanets, GGPokerOK, UPpoker, CoinPoker (турніри та кеш).

3. Натисніть Convert.
   • Сконвертовані файли зберігаються в Export.
   • Архіви .zip з роздачами розпаковуються; з Copy to Dropbox самарі з окремих zip потрапляють у …/year/summaries.
   • Якщо увімкнено копіювання в Dropbox: вихідні PP / GG / UP копіюються в Dropbox.
   • Файли Chico копіюються в Dropbox без змін (якщо вказано папку); оригінали в папці Chico не видаляються.
   • Імпорт з папок обробляє лише нові файли з попереднього запуску. Файли в Downloads старші за дату першого запуску програми ігноруються, щоб уникнути дублікатів уже в базі Hand2Note. За потреби імпортуйте їх вручну через папку Import.
   • Якщо не хочете, щоб кеш-роздачі потрапляли в Dropbox, не використовуйте автоімпорт H2N3!

""",
    "kk": """\
Раздаға тарихы конвертері

1. Баптау үшін Параметрлерді (тісті белгіше) ашыңыз:
   • Import қалтасы — бастапқы .txt / .zip раздаға тарихы файлдары (әдепкі: import/)
   • Export қалтасы — түрлендірілген шығыс (әдепкі: export/)
   • Түрлендіргеннен кейін Import қалтасын тазарту — аяқталғаннан кейін бастапқы .txt/.zip файлдарын жояды (Dropbox көшіруінен кейін, егер қосулы болса)
   • Coin hands as PS — CoinPoker-ді PokerStars форматында экспорттау (Pro/Asia жазылымы жоқ Hand2Note үшін)
   • Dropbox-қа көшіру — бастапқы файлдарды Dropbox-қа көшіреді; Dropbox және Chico өрістерін көрсетеді
   • Қалталардан импорт — PokerPlanets және Downloads қалталарын қадағалайды (тек жаңа файлдар)
   • Импорттан кейін қалталарды тазарту — Dropbox қосулы болса, тек өңделген файлдарды қосымша қалталардан жояды (Chico түпнұсқаларын, өңделмеген және бірінші іске қосу күнінен бұрынғы Downloads файлдарын жоймайды)
   • Лақап аты — түрлендірілген GG / UP / Coin раздачаларындағы кейіпкер аты (әдепкі: Hero)

2. Import қалтасына .txt (немесе GG/UP .zip) салыңыз. Үйлер: PokerPlanets, GGPokerOK, UPpoker, CoinPoker (турнирлер + кэш).

3. Convert түймесін басыңыз.
   • Түрлендірілген файлдар Export-қа жазылады.
   • .zip раздачалар шығарылады; Dropbox-қа көшіру қосулы болса summary zip-тер …/year/summaries-қа түседі.
   • Dropbox-қа көшіру қосулы болса: PP / GG / UP бастапқы файлдары көшіріледі.
   • Chico .txt файлдары Dropbox-қа өзгеріссіз көшіріледі (егер орнатылса); Chico қалтасындағы түпнұсқалар сақталады.
   • Қалталардан импорт тек соңғы іске қосудан бергі жаңа файлдарды өңдейді. Downloads-тағы қолданбаның бірінші іске қосу күнінен бұрынғы файлдар елемейді (Hand2Note дерекқорындағы қайталауларды болдырмау үшін). Қажет болса, оларды Import қалтасы арқылы қолмен импорттаңыз.
   • Кэш раздачалардың Dropbox-қа түсуін қаламасаңыз, H2N3 автоимпортын пайдаланбаңыз!

""",
    "fr": """\
Convertisseur d'historiques de mains

1. Ouvrez Paramètres (icône engrenage) pour configurer :
   • Dossier Import — fichiers .txt / .zip d'historiques bruts (par défaut : import/)
   • Dossier Export — fichiers convertis (par défaut : export/)
   • Vider le dossier Import après conversion — supprime les .txt/.zip sources une fois terminé (après copie Dropbox, si activée)
   • Coin hands as PS — export CoinPoker en PokerStars (pour Hand2Note sans abonnement Pro/Asia)
   • Copier vers Dropbox — copie les mains brutes vers Dropbox ; affiche les dossiers Dropbox et Chico (optionnel)
   • Importer depuis des dossiers — surveille aussi PokerPlanets et Downloads (nouveaux fichiers seulement)
   • Vider les dossiers après import — avec Dropbox, supprime uniquement les fichiers traités des dossiers surveillés (ne supprime jamais les originaux Chico, ni les fichiers Downloads non traités / antérieurs à la date de première exécution)
   • Pseudo — nom du héros dans les mains GG / UP / Coin converties (par défaut : Hero)

2. Placez les fichiers .txt (ou .zip GG/UP) dans Import. Salles : PokerPlanets, GGPokerOK, UPpoker, CoinPoker (tournois + cash).

3. Cliquez sur Convert.
   • Les fichiers convertis sont écrits dans Export.
   • Les .zip de mains sont décompressés ; avec Dropbox, les résumés vont dans …/year/summaries.
   • Avec Copier vers Dropbox : les fichiers bruts PP / GG / UP vont dans Dropbox.
   • Les .txt Chico sont copiés vers Dropbox tels quels (si défini) ; les originaux du dossier Chico sont conservés.
   • Import depuis dossiers : seuls les nouveaux fichiers depuis la dernière exécution sont traités. Les fichiers Downloads antérieurs à la date de première exécution de l'appli sont ignorés pour éviter les doublons déjà dans Hand2Note. Importez-les via Import manuellement si besoin.
   • Si vous ne voulez pas que vos mains cash aillent dans Dropbox, n'utilisez pas l'import auto de H2N3 !

""",
    "es": """\
Convertidor de historiales de manos

1. Abra Ajustes (icono de engranaje) para configurar:
   • Carpeta Import — archivos .txt / .zip de historiales (predeterminado: import/)
   • Carpeta Export — archivos convertidos (predeterminado: export/)
   • Vaciar carpeta Import tras convertir — elimina los .txt/.zip originales al terminar (tras la copia a Dropbox, si está activa)
   • Coin hands as PS — exportar CoinPoker como PokerStars (para Hand2Note sin suscripción Pro/Asia)
   • Copiar a Dropbox — copia las manos sin convertir a Dropbox; muestra carpetas Dropbox y Chico (opcional)
   • Importar desde carpetas — también vigila PokerPlanets y Downloads (solo archivos nuevos)
   • Vaciar carpetas tras importar — con Dropbox, borra solo archivos procesados de carpetas vigiladas (no borra originales de Chico, ni archivos de Downloads no procesados / anteriores a la fecha del primer uso)
   • Apodo — nombre del héroe en manos GG / UP / Coin convertidas (predeterminado: Hero)

2. Coloque archivos .txt (o .zip GG/UP) en Import. Salas: PokerPlanets, GGPokerOK, UPpoker, CoinPoker (torneos + cash).

3. Haga clic en Convert.
   • Los archivos convertidos se guardan en Export.
   • Los .zip de manos se descomprimen; con Dropbox, los summaries van a …/year/summaries.
   • Con Copiar a Dropbox: los archivos PP / GG / UP sin convertir van a Dropbox.
   • Los .txt de Chico se copian a Dropbox sin cambios (si está configurado); los originales en la carpeta Chico se conservan.
   • Importar desde carpetas solo procesa archivos nuevos desde la última ejecución. Los archivos de Downloads anteriores a la fecha del primer uso de la app se ignoran para evitar duplicados ya en Hand2Note. Impórtelos manualmente por Import si hace falta.
   • Si no quiere que sus manos de cash lleguen a Dropbox, no use la importación automática de H2N3.

""",
    "pl": """\
Konwerter historii rozdań

1. Otwórz Ustawienia (ikona koła zębatego), aby skonfigurować:
   • Folder Import — surowe pliki .txt / .zip historii rozdań (domyślnie: import/)
   • Folder Export — przekonwertowane pliki (domyślnie: export/)
   • Wyczyść folder Import po konwersji — usuwa źródłowe .txt/.zip po zakończeniu (po kopii do Dropbox, jeśli włączona)
   • Coin hands as PS — eksport CoinPoker jako PokerStars (dla Hand2Note bez subskrypcji Pro/Asia)
   • Kopiuj do Dropbox — kopiuje surowe ręce do Dropbox; pokazuje foldery Dropbox i Chico (opcjonalnie)
   • Import z folderów — także obserwuje PokerPlanets i Downloads (tylko nowe pliki)
   • Wyczyść foldery po imporcie — przy Dropbox usuwa tylko przetworzone pliki z obserwowanych folderów (nie usuwa oryginałów Chico, nieprzetworzonych ani plików Downloads starszych niż data pierwszego uruchomienia)
   • Pseudonim — nazwa bohatera w przekonwertowanych rozdanach GG / UP / Coin (domyślnie: Hero)

2. Umieść pliki .txt (lub .zip GG/UP) w folderze Import. Pokoje: PokerPlanets, GGPokerOK, UPpoker, CoinPoker (turnieje + cash).

3. Kliknij Convert.
   • Przekonwertowane pliki są zapisywane w Export.
   • Archiwa .zip z rozdaniami są rozpakowywane; przy Dropbox summary trafiają do …/year/summaries.
   • Przy Kopiuj do Dropbox: surowe PP / GG / UP trafiają do Dropbox.
   • Pliki Chico .txt kopiowane do Dropbox bez zmian (jeśli ustawione); oryginały w folderze Chico pozostają.
   • Import z folderów przetwarza tylko nowe pliki od ostatniego uruchomienia. Pliki w Downloads starsze niż data pierwszego uruchomienia aplikacji są ignorowane, aby uniknąć duplikatów już w bazie Hand2Note. W razie potrzeby zaimportuj je ręcznie przez folder Import.
   • Jeśli nie chcesz, żeby rozdania cash trafiały do Dropbox, nie używaj autoimportu H2N3!

""",
}
_LABEL_TO_INFO_LANG = {label: code for code, label in _INFO_LANGUAGE_LABELS.items()}


def _info_lang_from_label(label: str) -> str:
    return _LABEL_TO_INFO_LANG.get(label, "en")


_ASSETS_DIR = assets_dir()
_APP_ICON = _ASSETS_DIR / "app.ico"
_APP_ICON_PNG = _ASSETS_DIR / "app.png"
_SETTINGS_ICON = _ASSETS_DIR / "settings_16.png"
_HELP_ICON = _ASSETS_DIR / "help_16.png"
_INFO_DIAGRAM = _ASSETS_DIR / "intended_way_to_use.png"
_DISCORD_ICON = _ASSETS_DIR / "discord_24.png"
_DISCORD_URL = "https://discord.gg/AKRS7YFaw"


def _pixel_lum(rgb: tuple[int, int, int]) -> float:
    r, g, b = rgb
    return 0.299 * r + 0.587 * g + 0.114 * b


def _load_toolbar_icon(path: Path, master: tk.Misc) -> tk.PhotoImage | None:
    if not path.is_file():
        return None
    try:
        src = tk.PhotoImage(file=str(path), master=master)
        width, height = src.width(), src.height()
        rows: list[str] = []
        transparent: list[tuple[int, int]] = []
        for y in range(height):
            pixels: list[str] = []
            for x in range(width):
                red, green, blue = src.get(x, y)
                if _pixel_lum((red, green, blue)) < 128:
                    pixels.append("#000000")
                else:
                    pixels.append("#000001")
                    transparent.append((x, y))
            rows.append("{" + " ".join(pixels) + "}")
        icon = tk.PhotoImage(master=master, width=width, height=height)
        icon.put(" ".join(rows), to=(0, 0))
        for x, y in transparent:
            icon.transparency_set(x, y, True)
        return icon
    except (OSError, tk.TclError):
        return None


def apply_window_icon(window: tk.Misc) -> None:
    if _APP_ICON.is_file():
        try:
            window.iconbitmap(default=str(_APP_ICON))
            return
        except tk.TclError:
            pass
    if not _APP_ICON_PNG.is_file():
        return
    try:
        photo = tk.PhotoImage(file=str(_APP_ICON_PNG))
    except tk.TclError:
        return
    window.iconphoto(True, photo)
    window._icon_photo_ref = photo  # type: ignore[attr-defined]


class SettingsDialog(tk.Toplevel):
    def __init__(self, parent: tk.Misc, config_path: Path, settings: Settings | None) -> None:
        super().__init__(parent)
        self.title("Settings")
        apply_window_icon(self)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self._config_path = config_path
        self._result: Settings | None = None

        base = settings if settings is not None else default_settings()

        self._vars = {
            "import_path": tk.StringVar(value=path_display(base.import_path)),
            "export_path": tk.StringVar(value=path_display(base.export_path)),
            "copy_to_dropbox": tk.BooleanVar(value=base.dropbox_mode == "original"),
            "clear_import_after_convert": tk.BooleanVar(
                value=base.clear_import_after_convert
            ),
            "coin_as_ps": tk.BooleanVar(value=base.coin_as_ps),
            "dropbox_base_path": tk.StringVar(value=path_display(base.dropbox_base_path)),
            "chico_import_path": tk.StringVar(
                value=path_display(base.chico_import_path) if base.chico_import_path else ""
            ),
            "player_alias": tk.StringVar(value=base.player_alias),
            "import_from_folders": tk.BooleanVar(value=base.import_from_folders),
            "poker_planets_folder": tk.StringVar(
                value=path_display(base.poker_planets_folder) if base.poker_planets_folder else ""
            ),
            "downloads_folder": tk.StringVar(
                value=path_display(base.downloads_folder) if base.downloads_folder else ""
            ),
            "clear_folders_after_import": tk.BooleanVar(
                value=base.clear_folders_after_import and base.dropbox_mode == "original"
            ),
        }

        body = ttk.Frame(self, padding=12)
        body.grid(row=0, column=0, sticky="nsew")

        row = 0
        row = self._add_path_row(body, row, "Import folder", "import_path")
        row = self._add_path_row(body, row, "Export folder", "export_path")

        ttk.Checkbutton(
            body,
            text="Clear Import folder after converting",
            variable=self._vars["clear_import_after_convert"],
        ).grid(row=row, column=0, columnspan=2, sticky="w", pady=(8, 4))
        row += 1

        ttk.Checkbutton(
            body,
            text="Coin hands as PokerStars (for non-PRO H2N)",
            variable=self._vars["coin_as_ps"],
        ).grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 4))
        row += 1

        ttk.Checkbutton(
            body,
            text="Copy to Dropbox",
            variable=self._vars["copy_to_dropbox"],
            command=self._on_dropbox_toggle,
        ).grid(row=row, column=0, columnspan=2, sticky="w", pady=(4, 4))
        row += 1

        self._dropbox_section = ttk.Frame(body)
        self._dropbox_section.grid(row=row, column=0, columnspan=2, sticky="ew")
        self._dropbox_section.columnconfigure(0, weight=1)
        section_row = 0
        section_row = self._add_path_row(
            self._dropbox_section,
            section_row,
            "Dropbox folder",
            "dropbox_base_path",
        )
        self._add_path_row(
            self._dropbox_section,
            section_row,
            "Chico folder (optional)",
            "chico_import_path",
        )
        row += 1

        ttk.Checkbutton(
            body,
            text="Import from folders",
            variable=self._vars["import_from_folders"],
            command=self._toggle_import_folders,
        ).grid(row=row, column=0, columnspan=2, sticky="w", pady=(8, 4))
        row += 1

        self._folders_section = ttk.Frame(body)
        self._folders_section.grid(row=row, column=0, columnspan=2, sticky="ew")
        self._folders_section.columnconfigure(0, weight=1)
        frow = 0
        frow = self._add_path_row(
            self._folders_section,
            frow,
            "PokerPlanets folder",
            "poker_planets_folder",
        )
        frow = self._add_path_row(
            self._folders_section,
            frow,
            "Downloads folder",
            "downloads_folder",
        )
        self._clear_folders_cb = ttk.Checkbutton(
            self._folders_section,
            text="Clear folders after import",
            variable=self._vars["clear_folders_after_import"],
        )
        self._clear_folders_cb.grid(row=frow, column=0, columnspan=2, sticky="w", pady=(4, 0))
        row += 1

        ttk.Label(body, text="Nickname (converted hero)").grid(
            row=row, column=0, columnspan=2, sticky="w", pady=(8, 2)
        )
        ttk.Entry(body, textvariable=self._vars["player_alias"], width=48).grid(
            row=row + 1, column=0, columnspan=2, sticky="ew"
        )
        row += 2

        buttons = ttk.Frame(body)
        buttons.grid(row=row, column=0, columnspan=2, pady=(12, 0), sticky="e")
        ttk.Button(buttons, text="Cancel", command=self._cancel).pack(side=tk.RIGHT, padx=(6, 0))
        ttk.Button(buttons, text="Save", command=self._save).pack(side=tk.RIGHT)

        body.columnconfigure(0, weight=1)
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.bind("<Escape>", lambda _e: self._cancel())

        self._toggle_dropbox_fields()
        self._toggle_import_folders()
        self._sync_clear_folders_state()
        self.update_idletasks()
        self._center_over(parent)

    def _on_dropbox_toggle(self) -> None:
        self._toggle_dropbox_fields()
        self._sync_clear_folders_state()

    def _toggle_dropbox_fields(self) -> None:
        if self._vars["copy_to_dropbox"].get():
            self._dropbox_section.grid()
        else:
            self._dropbox_section.grid_remove()

    def _toggle_import_folders(self) -> None:
        if self._vars["import_from_folders"].get():
            self._folders_section.grid()
        else:
            self._folders_section.grid_remove()
        self._sync_clear_folders_state()

    def _sync_clear_folders_state(self) -> None:
        dropbox_on = self._vars["copy_to_dropbox"].get()
        if not dropbox_on:
            self._vars["clear_folders_after_import"].set(False)
        state = tk.NORMAL if dropbox_on else tk.DISABLED
        self._clear_folders_cb.configure(state=state)

    def _center_over(self, parent: tk.Misc) -> None:
        self.update_idletasks()
        px = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{max(px, 0)}+{max(py, 0)}")

    def _add_path_row(self, parent: ttk.Frame, row: int, label: str, key: str) -> int:
        ttk.Label(parent, text=label).grid(row=row, column=0, columnspan=2, sticky="w", pady=(6, 2))
        entry = ttk.Entry(parent, textvariable=self._vars[key], width=40)
        entry.grid(row=row + 1, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(
            parent,
            text="Browse…",
            command=lambda k=key, e=entry: self._browse(k, e),
        ).grid(row=row + 1, column=1, sticky="e")
        return row + 2

    def _browse(self, key: str, entry: ttk.Entry) -> None:
        initial = self._vars[key].get().strip()
        kwargs: dict = {"parent": self, "mustexist": True}
        if initial:
            p = Path(initial)
            kwargs["initialdir"] = str(p if p.is_dir() else p.parent)
        chosen = filedialog.askdirectory(**kwargs)
        if chosen:
            self._vars[key].set(chosen)
            entry.focus_set()

    def _cancel(self) -> None:
        self._result = None
        self.destroy()

    def _save(self) -> None:
        import_path = self._vars["import_path"].get().strip()
        export_path = self._vars["export_path"].get().strip()
        dropbox_path = self._vars["dropbox_base_path"].get().strip()
        chico_raw = self._vars["chico_import_path"].get().strip()
        pp_folder = self._vars["poker_planets_folder"].get().strip()
        downloads = self._vars["downloads_folder"].get().strip()
        alias = self._vars["player_alias"].get().strip()
        copy_to_dropbox = self._vars["copy_to_dropbox"].get()
        import_from_folders = self._vars["import_from_folders"].get()
        clear_folders = (
            self._vars["clear_folders_after_import"].get() if copy_to_dropbox else False
        )

        missing = [
            name
            for name, value in (
                ("Import folder", import_path),
                ("Export folder", export_path),
                ("Nickname", alias),
            )
            if not value
        ]
        if copy_to_dropbox and not dropbox_path:
            missing.append("Dropbox folder")
        if missing:
            messagebox.showerror("Settings", "Required:\n• " + "\n• ".join(missing), parent=self)
            return

        self._result = Settings(
            import_path=Path(import_path),
            export_path=Path(export_path),
            dropbox_base_path=Path(dropbox_path) if dropbox_path else Path(),
            chico_import_path=Path(chico_raw) if chico_raw else None,
            dropbox_mode="original" if copy_to_dropbox else "none",
            player_alias=alias,
            clear_import_after_convert=self._vars["clear_import_after_convert"].get(),
            coin_as_ps=self._vars["coin_as_ps"].get(),
            import_from_folders=import_from_folders,
            poker_planets_folder=Path(pp_folder) if pp_folder else None,
            downloads_folder=Path(downloads) if downloads else None,
            clear_folders_after_import=clear_folders,
        )
        try:
            save_settings(self._config_path, self._result)
        except OSError as exc:
            messagebox.showerror("Settings", f"Could not save config:\n{exc}", parent=self)
            self._result = None
            return
        self.destroy()

    def run(self) -> Settings | None:
        self.wait_window()
        return self._result


class InfoDialog(tk.Toplevel):
    _MIN_WIDTH = 520
    _MIN_HEIGHT = 420
    _MAX_WIDTH = 1400
    _MAX_HEIGHT = 960
    _DIAGRAM_DEFAULT_SCALE = 0.75  # of native (never default larger than original)
    _PAD = 24

    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent)
        self._lang_code = "en"
        self._parent = parent
        self._diagram_pil: Image.Image | None = None
        self._diagram_image: ImageTk.PhotoImage | None = None
        self._diagram_full_image: ImageTk.PhotoImage | None = None
        self._diagram_full_win: tk.Toplevel | None = None
        self._discord_image: tk.PhotoImage | None = None
        self._resize_after: str | None = None
        self._last_diagram_width = 0
        self._initial_layout_done = False

        self.title(_INFO_TITLE_LABELS[self._lang_code])
        apply_window_icon(self)
        self.resizable(True, True)
        self.transient(parent)

        frame = ttk.Frame(self, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)

        # Diagram above text, centered; click opens full-size view.
        self._diagram_wrap = ttk.Frame(frame)
        self._diagram_wrap.pack(fill=tk.X, pady=(0, 8))
        self._diagram_label = tk.Label(
            self._diagram_wrap,
            cursor="hand2",
            borderwidth=0,
            highlightthickness=0,
        )
        self._diagram_label.pack(anchor=tk.CENTER)
        self._diagram_label.bind("<Button-1>", self._open_diagram_full)

        text_frame = ttk.Frame(frame)
        text_frame.pack(fill=tk.BOTH, expand=True)
        text_frame.rowconfigure(0, weight=1)
        text_frame.columnconfigure(0, weight=1)

        self._text = tk.Text(
            text_frame,
            wrap=tk.WORD,
            relief=tk.FLAT,
            padx=4,
            pady=4,
            borderwidth=0,
            highlightthickness=0,
        )
        self._text.grid(row=0, column=0, sticky="nsew")

        scroll_y = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self._text.yview)
        scroll_y.grid(row=0, column=1, sticky="ns")
        self._text.configure(yscrollcommand=scroll_y.set)

        footer = ttk.Frame(frame)
        footer.pack(fill=tk.X, pady=(8, 0))

        self._discord_btn = self._make_discord_button(footer)
        self._discord_btn.pack(side=tk.LEFT, padx=(0, 8))

        self._lang_var = tk.StringVar(value=_INFO_LANGUAGE_LABELS[self._lang_code])
        lang_combo = ttk.Combobox(
            footer,
            textvariable=self._lang_var,
            values=list(_INFO_LANGUAGE_LABELS.values()),
            state="readonly",
            width=14,
        )
        lang_combo.pack(side=tk.LEFT)
        lang_combo.bind("<<ComboboxSelected>>", self._on_language_change)

        self._close_btn = ttk.Button(footer, command=self._on_close)
        self._close_btn.pack(side=tk.RIGHT)

        self._load_diagram_source()
        self._set_language(self._lang_code)

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind("<Escape>", lambda _e: self._on_close())
        self.bind("<Configure>", self._on_configure)

    def _on_close(self) -> None:
        self._close_diagram_full()
        self.destroy()

    def _make_discord_button(self, parent: tk.Misc) -> ttk.Button | tk.Label:
        if _DISCORD_ICON.is_file():
            try:
                self._discord_image = tk.PhotoImage(file=str(_DISCORD_ICON), master=self)
            except tk.TclError:
                self._discord_image = None
        if self._discord_image is not None:
            btn = tk.Label(
                parent,
                image=self._discord_image,
                cursor="hand2",
                borderwidth=0,
                highlightthickness=0,
            )
            btn.bind("<Button-1>", self._open_discord)
            return btn
        btn = ttk.Button(parent, text="Discord", width=8, command=self._open_discord)
        return btn

    def _open_discord(self, _event: tk.Event | None = None) -> None:
        webbrowser.open(_DISCORD_URL)

    def _load_diagram_source(self) -> None:
        if not _INFO_DIAGRAM.is_file():
            self._diagram_wrap.pack_forget()
            return
        try:
            self._diagram_pil = Image.open(_INFO_DIAGRAM).convert("RGBA")
        except OSError:
            self._diagram_pil = None
            self._diagram_wrap.pack_forget()

    def _default_diagram_width(self) -> int:
        if self._diagram_pil is None:
            return 620
        native_w = self._diagram_pil.width
        target = int(round(native_w * self._DIAGRAM_DEFAULT_SCALE))
        screen_cap = int(self.winfo_screenwidth() * 0.7)
        # Never default larger than the source image.
        return max(320, min(target, native_w, screen_cap, self._MAX_WIDTH - self._PAD))

    def _render_diagram(self, width: int) -> None:
        if self._diagram_pil is None:
            return
        native_w = self._diagram_pil.width
        width = max(160, min(int(width), native_w))
        if width == self._last_diagram_width and self._diagram_image is not None:
            return
        native_h = self._diagram_pil.height
        height = max(1, int(round(native_h * (width / native_w))))
        resized = self._diagram_pil.resize((width, height), Image.Resampling.LANCZOS)
        photo = ImageTk.PhotoImage(resized, master=self)
        self._diagram_image = photo
        self._last_diagram_width = width
        self._diagram_label.configure(image=photo)

    def _on_configure(self, event: tk.Event) -> None:
        if event.widget is not self:
            return
        if not self._initial_layout_done or self._diagram_pil is None:
            return
        if self._resize_after is not None:
            self.after_cancel(self._resize_after)
        self._resize_after = self.after(80, self._resize_diagram_to_window)

    def _resize_diagram_to_window(self) -> None:
        self._resize_after = None
        if self._diagram_pil is None:
            return
        inner = max(160, self.winfo_width() - self._PAD)
        # Grow/shrink with the window but never past the original image width.
        self._render_diagram(min(inner, self._diagram_pil.width))

    def _open_diagram_full(self, _event: tk.Event | None = None) -> None:
        if self._diagram_pil is None:
            return
        if self._diagram_full_win is not None and self._diagram_full_win.winfo_exists():
            self._close_diagram_full()
            return

        win = tk.Toplevel(self)
        self._diagram_full_win = win
        win.title(_INFO_TITLE_LABELS.get(self._lang_code, "Instructions"))
        apply_window_icon(win)
        win.transient(self)
        win.configure(cursor="hand2")

        screen_w = win.winfo_screenwidth()
        screen_h = win.winfo_screenheight()
        native_w, native_h = self._diagram_pil.size
        scale = min(1.0, (screen_w * 0.95) / native_w, (screen_h * 0.92) / native_h)
        show_w = max(1, int(round(native_w * scale)))
        show_h = max(1, int(round(native_h * scale)))
        shown = self._diagram_pil.resize((show_w, show_h), Image.Resampling.LANCZOS)
        photo = ImageTk.PhotoImage(shown, master=win)
        self._diagram_full_image = photo

        label = tk.Label(win, image=photo, cursor="hand2", borderwidth=0)
        label.pack()
        label.bind("<Button-1>", lambda _e: self._close_diagram_full())
        win.bind("<Button-1>", lambda _e: self._close_diagram_full())
        win.bind("<Escape>", lambda _e: self._close_diagram_full())
        win.protocol("WM_DELETE_WINDOW", self._close_diagram_full)

        win.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() - show_w) // 2
        y = self.winfo_rooty() + (self.winfo_height() - show_h) // 2
        win.geometry(f"{show_w}x{show_h}+{max(0, x)}+{max(0, y)}")

    def _close_diagram_full(self) -> None:
        if self._diagram_full_win is not None:
            try:
                self._diagram_full_win.destroy()
            except tk.TclError:
                pass
        self._diagram_full_win = None
        self._diagram_full_image = None

    def _on_language_change(self, _event: tk.Event | None = None) -> None:
        self._set_language(_info_lang_from_label(self._lang_var.get()))

    def _set_language(self, lang_code: str) -> None:
        if lang_code not in _INFO_TEXTS:
            lang_code = "en"
        self._lang_code = lang_code
        self._lang_var.set(_INFO_LANGUAGE_LABELS[lang_code])
        self.title(_INFO_TITLE_LABELS[lang_code])
        self._close_btn.configure(text=_INFO_CLOSE_LABELS[lang_code])
        content = _INFO_TEXTS[lang_code]
        self._text.configure(state=tk.NORMAL)
        self._text.delete("1.0", tk.END)
        self._text.insert("1.0", content)
        self._text.configure(state=tk.DISABLED)
        self._fit_to_content()
        self._center_over(self._parent)

    def _fit_to_content(self) -> None:
        font = tkfont.Font(font=self._text.cget("font"))
        line_height = font.metrics("linespace")
        frame_pad = 48
        footer_height = 48

        diagram_w = self._default_diagram_width()
        self._render_diagram(diagram_w)
        diagram_h = self._diagram_image.height() + 16 if self._diagram_image else 0

        cap_w = min(int(self.winfo_screenwidth() * 0.9), self._MAX_WIDTH)
        cap_h = min(int(self.winfo_screenheight() * 0.85), self._MAX_HEIGHT)
        width = max(self._MIN_WIDTH, min(diagram_w + self._PAD, cap_w))

        self.geometry(f"{width}x{self._MIN_HEIGHT}")
        self.update_idletasks()
        display_lines = int(self._text.index("end-1c").split(".")[0])
        content_h = line_height * display_lines + 24
        height = max(
            self._MIN_HEIGHT,
            min(content_h + frame_pad + footer_height + diagram_h, cap_h),
        )

        self.minsize(self._MIN_WIDTH, self._MIN_HEIGHT)
        self.geometry(f"{width}x{height}")
        self._initial_layout_done = True
        # Match diagram to final window width after geometry settles.
        self.after(50, self._resize_diagram_to_window)

    def _center_over(self, parent: tk.Misc) -> None:
        self.update_idletasks()
        px = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{max(px, 0)}+{max(py, 0)}")


class ConverterApp:
    def __init__(self, root: tk.Tk, config_path: Path) -> None:
        self.root = root
        self.config_path = config_path
        self._settings: Settings | None = None
        self._busy = False

        root.title(f"HH Converter {__version__}")
        root.minsize(320, 140)
        root.resizable(False, False)

        self._build_ui()
        self._reload_settings(silent=True)

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=16)
        outer.pack(fill=tk.BOTH, expand=True)

        toolbar = ttk.Frame(outer)
        toolbar.pack(fill=tk.X)

        ttk.Frame(toolbar).pack(side=tk.LEFT, expand=True)
        toolbar_style = ttk.Style()
        toolbar_style.configure("Toolbar.TButton", padding=(8, 4))
        self._settings_icon = _load_toolbar_icon(_SETTINGS_ICON, self.root)
        self._help_icon = _load_toolbar_icon(_HELP_ICON, self.root)
        if self._settings_icon is not None:
            self._btn_settings = ttk.Button(
                toolbar,
                image=self._settings_icon,
                text=" ",
                width=3,
                style="Toolbar.TButton",
                compound=tk.CENTER,
                command=self._open_settings,
            )
        else:
            self._btn_settings = ttk.Button(
                toolbar,
                text="⚙",
                width=3,
                style="Toolbar.TButton",
                command=self._open_settings,
            )
        if self._help_icon is not None:
            self._btn_info = ttk.Button(
                toolbar,
                image=self._help_icon,
                text=" ",
                width=3,
                style="Toolbar.TButton",
                compound=tk.CENTER,
                command=self._open_info,
            )
        else:
            self._btn_info = ttk.Button(
                toolbar,
                text="?",
                width=3,
                style="Toolbar.TButton",
                command=self._open_info,
            )
        self._btn_info.pack(side=tk.RIGHT)
        self._btn_settings.pack(side=tk.RIGHT, padx=(4, 0))

        convert_style = ttk.Style()
        convert_style.configure("Convert.TButton", font=("Segoe UI", 14, "bold"), padding=(24, 16))

        self._btn_convert = ttk.Button(
            outer,
            text="Convert",
            style="Convert.TButton",
            command=self._start_convert,
        )
        self._btn_convert.pack(fill=tk.X, pady=(12, 8))

        self._status = ttk.Label(outer, text="Ready", anchor=tk.W)
        self._status.pack(fill=tk.X)

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        state = tk.DISABLED if busy else tk.NORMAL
        self._btn_convert.configure(state=state)
        self._btn_settings.configure(state=state)

    def _set_convert_label(self, text: str) -> None:
        self._btn_convert.configure(text=text)

    def _reload_settings(self, *, silent: bool) -> None:
        try:
            ensure_default_config(self.config_path)
            self._settings = load_settings(self.config_path)
        except ValueError as exc:
            self._settings = None
            self._status.configure(text="Invalid config")
            if not silent:
                messagebox.showerror("Settings", str(exc), parent=self.root)
            return
        self._status.configure(text=self._status_text(self._settings))

    def _missing_convert_paths(self, settings: Settings) -> list[str]:
        missing: list[str] = []
        if not is_path_set(settings.import_path):
            missing.append("Import folder")
        if not is_path_set(settings.export_path):
            missing.append("Export folder")
        if settings.dropbox_mode == "original" and not is_path_set(settings.dropbox_base_path):
            missing.append("Dropbox folder")
        return missing

    def _prompt_configure_paths(self, missing: list[str]) -> None:
        messagebox.showwarning(
            "Convert",
            "Please set the required paths in Settings:\n• " + "\n• ".join(missing),
            parent=self.root,
        )
        self._open_settings()

    def _status_text(self, settings: Settings) -> str:
        return f"Player name: {settings.player_alias}"

    def _open_settings(self) -> None:
        dialog = SettingsDialog(self.root, self.config_path, self._settings)
        updated = dialog.run()
        if updated is not None:
            self._settings = updated
            self._status.configure(text=self._status_text(self._settings))
            self._set_convert_label("Convert")

    def _open_info(self) -> None:
        InfoDialog(self.root)

    def _start_convert(self) -> None:
        if self._busy:
            return
        if self._settings is None:
            self._reload_settings(silent=True)
        if self._settings is None:
            self._prompt_configure_paths(["Import folder", "Export folder"])
            return

        missing = self._missing_convert_paths(self._settings)
        if missing:
            self._prompt_configure_paths(missing)
            return

        self._set_convert_label("Convert")
        self._set_busy(True)
        self._status.configure(text="Converting…")
        settings = self._settings

        def worker() -> None:
            error: str | None = None
            try:
                process_all(settings, console_print=False)
            except OSError as exc:
                error = f"IO problem: {exc}"
            except Exception as exc:  # noqa: BLE001 — show unexpected errors in the UI
                error = f"Error (v{__version__}): {exc}"

            self.root.after(0, lambda: self._convert_finished(error))

        threading.Thread(target=worker, daemon=True).start()

    def _convert_finished(self, error: str | None) -> None:
        self._set_busy(False)
        if error:
            self._set_convert_label("Convert")
            if self._settings:
                self._status.configure(text=self._status_text(self._settings))
            messagebox.showerror("Convert", error, parent=self.root)
            return

        self._set_convert_label("Done! Again?")
        if self._settings:
            self._status.configure(text=self._status_text(self._settings))


def main(argv: list[str] | None = None) -> int:
    config_path = default_config_path()
    if argv:
        for i, arg in enumerate(argv):
            if arg in ("--config", "-c") and i + 1 < len(argv):
                config_path = Path(argv[i + 1])
                break

    root = tk.Tk()
    apply_window_icon(root)
    try:
        ttk.Style().theme_use("vista")
    except tk.TclError:
        pass

    ConverterApp(root, config_path)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
