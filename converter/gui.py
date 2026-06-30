from __future__ import annotations

import sys
import threading
import tkinter as tk
import tkinter.font as tkfont
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

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
   • Import folder — raw hand history .txt files (default: import/)
   • Export folder — converted output (default: export/)
   • Clear Import folder after converting — removes source .txt files when done (after Dropbox copy, if enabled)
   • Coin hands as PS - export CoinPoker as PokerStars (for Hand2Note without Pro/Asia subscription)
   • Copy to Dropbox — mirrors raw hands to Dropbox; shows Dropbox and optional Chico folders
   • Nickname — hero name in converted GG / UP / Coin hands (default: Hero)

2. Put .txt hand histories in the Import folder. Rooms: PokerPlanets, GGPokerOK, UPoker, CoinPoker.

3. Click Convert.
   • Converted files are written to Export.
   • With Copy to Dropbox: PP / GG / UP raw files and Coin converted files go to Dropbox.
   • Chico .txt files copy unchanged (if set).
   • With Clear Import: all .txt files under Import are deleted last.

Import, Export, and Dropbox folder (when Copy to Dropbox is on) must be set before converting.
You will be prompted to open Settings if any are missing.
""",
    "ru": """\
Конвертер истории раздач

1. Откройте Настройки (иконка шестерёнки) для настройки:
   • Папка Import — исходные .txt файлы истории раздач (по умолчанию: import/)
   • Папка Export — сконвертированные файлы (по умолчанию: export/)
   • Очистить папку Import после конвертации — удаляет исходные .txt после завершения (после копирования в Dropbox, если включено)
   • Coin hands as PS — экспорт CoinPoker в формате PokerStars (для Hand2Note без подписки Pro/Asia)
   • Копировать в Dropbox — копирует исходные файлы в Dropbox; открывает поля Dropbox и Chico (необязательно)
   • Никнейм — имя героя в конвертированных раздачах GG / UP / Coin (по умолчанию: Hero)

2. Положите .txt файлы истории раздач в папку Import. Румы: PokerPlanets, GGPokerOK, UPoker, CoinPoker.

3. Нажмите Convert.
   • Сконвертированные файлы сохраняются в Export.
   • При включённом копировании в Dropbox: исходные файлы PP / GG / UP и сконвертированные Coin копируются в Dropbox.
   • Файлы Chico копируются без изменений (если указана папка).
   • При включённой очистке Import: все .txt в папке Import удаляются в конце.

Перед конвертацией должны быть указаны папки Import, Export и Dropbox (если включено копирование в Dropbox).
При отсутствии любой из них откроется окно Настроек.
""",
    "uk": """\
Конвертер історії роздач

1. Відкрийте Налаштування (іконка шестерні) для налаштування:
   • Папка Import — вихідні .txt файли історії роздач (за замовчуванням: import/)
   • Папка Export — сконвертовані файли (за замовчуванням: export/)
   • Очистити папку Import після конвертації — видаляє вихідні .txt після завершення (після копіювання в Dropbox, якщо увімкнено)
   • Coin hands as PS — експорт CoinPoker у форматі PokerStars (для Hand2Note без підписки Pro/Asia)
   • Копіювати в Dropbox — копіює вихідні файли в Dropbox; показує поля Dropbox і Chico (необов'язково)
   • Нікнейм — ім'я героя в сконвертованих роздачах GG / UP / Coin (за замовчуванням: Hero)

2. Покладіть .txt файли історії роздач у папку Import. Руми: PokerPlanets, GGPokerOK, UPoker, CoinPoker.

3. Натисніть Convert.
   • Сконвертовані файли зберігаються в Export.
   • Якщо увімкнено копіювання в Dropbox: вихідні PP / GG / UP і сконвертовані Coin копіюються в Dropbox.
   • Файли Chico копіюються без змін (якщо вказано папку).
   • Якщо увімкнено очищення Import: усі .txt у папці Import видаляються наприкінці.

Перед конвертацією мають бути вказані папки Import, Export і Dropbox (якщо увімкнено копіювання в Dropbox).
Якщо якоїсь немає, відкриється вікно Налаштувань.
""",
    "kk": """\
Раздаға тарихы конвертері

1. Баптау үшін Параметрлерді (бісікелей белгіше) ашыңыз:
   • Import қалтасы — бастапқы .txt раздаға тарихы файлдары (әдепкі: import/)
   • Export қалтасы — түрлендірілген шығыс (әдепкі: export/)
   • Түрлендіргеннен кейін Import қалтасын тазарту — аяқталғаннан кейін бастапқы .txt файлдарын жояды (қосулы болса, Dropbox көшіруінен кейін)
   • Coin hands as PS — CoinPoker-ді PokerStars форматында экспорттау (Hand2Note Pro/Asia жазылымысыз)
   • Dropbox-қа көшіру — бастапқы файлдарды Dropbox-қа көшіреді; Dropbox және Chico қалталарын көрсетеді (міндетті емес)
   • Лақап аты — түрлендірілген GG / UP / Coin раздачаларындағы кейіпкер аты (әдепкі: Hero)

2. Import қалтасына .txt раздаға тарихы файлдарын салыңыз. Үйлер: PokerPlanets, GGPokerOK, UPoker, CoinPoker.

3. Convert түймесін басыңыз.
   • Түрлендірілген файлдар Export-қа жазылады.
   • Dropbox-қа көшіру қосулы болса: PP / GG / UP бастапқы файлдары және Coin түрлендірілген файлдары Dropbox-қа түседі.
   • Chico .txt файлдары өзгеріссіз көшіріледі (орнатылған болса).
   • Import-ты тазарту қосулы болса: Import-тегі барлық .txt файлдары соңында жойылады.

Түрлендірмес бұрын Import, Export және Dropbox қалталары (Dropbox-қа көшіру қосулы болса) орнатылуы керек.
Егер біреуі жоқ болса, Параметрлер терезесі ашылады.
""",
    "fr": """\
Convertisseur d'historiques de mains

1. Ouvrez Paramètres (icône engrenage) pour configurer :
   • Dossier Import — fichiers .txt d'historiques bruts (par défaut : import/)
   • Dossier Export — fichiers convertis (par défaut : export/)
   • Vider le dossier Import après conversion — supprime les .txt sources une fois terminé (après la copie Dropbox, si activé)
   • Coin hands as PS — export CoinPoker en PokerStars (Hand2Note sans abonnement Pro/Asia)
   • Copier vers Dropbox — copie les mains brutes vers Dropbox ; affiche les dossiers Dropbox et Chico (facultatif)
   • Pseudo — nom du héros dans les mains GG / UP / Coin converties (par défaut : Hero)

2. Placez les fichiers .txt d'historiques dans le dossier Import. Salles : PokerPlanets, GGPokerOK, UPoker, CoinPoker.

3. Cliquez sur Convert.
   • Les fichiers convertis sont écrits dans Export.
   • Avec Copier vers Dropbox : les fichiers bruts PP / GG / UP et les fichiers Coin convertis vont dans Dropbox.
   • Les fichiers Chico .txt sont copiés sans modification (si défini).
   • Avec Vider Import : tous les .txt du dossier Import sont supprimés en dernier.

Les dossiers Import, Export et Dropbox (si Copier vers Dropbox est activé) doivent être définis avant la conversion.
Vous serez invité à ouvrir Paramètres si l'un d'eux manque.
""",
    "es": """\
Convertidor de historiales de manos

1. Abra Ajustes (icono de engranaje) para configurar:
   • Carpeta Import — archivos .txt de historiales sin convertir (predeterminado: import/)
   • Carpeta Export — archivos convertidos (predeterminado: export/)
   • Vaciar carpeta Import tras convertir — elimina los .txt originales al terminar (después de copiar a Dropbox, si está activado)
   • Coin hands as PS — exportar CoinPoker como PokerStars (Hand2Note sin suscripción Pro/Asia)
   • Copiar a Dropbox — copia las manos sin convertir a Dropbox; muestra las carpetas Dropbox y Chico (opcional)
   • Apodo — nombre del héroe en manos GG / UP / Coin convertidas (predeterminado: Hero)

2. Coloque archivos .txt de historiales en la carpeta Import. Salas: PokerPlanets, GGPokerOK, UPoker, CoinPoker.

3. Haga clic en Convert.
   • Los archivos convertidos se guardan en Export.
   • Con Copiar a Dropbox: los archivos PP / GG / UP sin convertir y los Coin convertidos van a Dropbox.
   • Los archivos Chico .txt se copian sin cambios (si está configurado).
   • Con Vaciar Import: todos los .txt de Import se eliminan al final.

Las carpetas Import, Export y Dropbox (si Copiar a Dropbox está activado) deben estar configuradas antes de convertir.
Se le pedirá abrir Ajustes si falta alguna.
""",
    "pl": """\
Konwerter historii rozdań

1. Otwórz Ustawienia (ikona koła zębatego), aby skonfigurować:
   • Folder Import — surowe pliki .txt historii rozdań (domyślnie: import/)
   • Folder Export — przekonwertowane pliki (domyślnie: export/)
   • Wyczyść folder Import po konwersji — usuwa źródłowe .txt po zakończeniu (po kopiowaniu do Dropbox, jeśli włączone)
   • Coin hands as PS — eksport CoinPoker jako PokerStars (Hand2Note bez subskrypcji Pro/Asia)
   • Kopiuj do Dropbox — kopiuje surowe ręce do Dropbox; pokazuje foldery Dropbox i Chico (opcjonalnie)
   • Pseudonim — nazwa bohatera w przekonwertowanych rozdanach GG / UP / Coin (domyślnie: Hero)

2. Umieść pliki .txt historii rozdań w folderze Import. Pokoje: PokerPlanets, GGPokerOK, UPoker, CoinPoker.

3. Kliknij Convert.
   • Przekonwertowane pliki są zapisywane w Export.
   • Przy Kopiuj do Dropbox: surowe pliki PP / GG / UP i przekonwertowane Coin trafiają do Dropbox.
   • Pliki Chico .txt są kopiowane bez zmian (jeśli ustawione).
   • Przy Wyczyść Import: wszystkie .txt w Import są usuwane na końcu.

Foldery Import, Export i Dropbox (gdy Kopiuj do Dropbox jest włączone) muszą być ustawione przed konwersją.
Zostaniesz poproszony o otwarcie Ustawień, jeśli któregoś brakuje.
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
            command=self._toggle_dropbox_fields,
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
        self.update_idletasks()
        self._center_over(parent)

    def _toggle_dropbox_fields(self) -> None:
        if self._vars["copy_to_dropbox"].get():
            self._dropbox_section.grid()
        else:
            self._dropbox_section.grid_remove()

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
        alias = self._vars["player_alias"].get().strip()
        copy_to_dropbox = self._vars["copy_to_dropbox"].get()

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
    _MIN_WIDTH = 480
    _MIN_HEIGHT = 360
    _MAX_WIDTH = 960
    _MAX_HEIGHT = 720

    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent)
        self._lang_code = "en"
        self._parent = parent
        self.title(_INFO_TITLE_LABELS[self._lang_code])
        apply_window_icon(self)
        self.resizable(True, True)
        self.transient(parent)

        frame = ttk.Frame(self, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)

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

        self._close_btn = ttk.Button(footer, command=self.destroy)
        self._close_btn.pack(side=tk.RIGHT)

        self._set_language(self._lang_code)

        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.bind("<Escape>", lambda _e: self.destroy())

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

        cap_w = min(int(self.winfo_screenwidth() * 0.9), self._MAX_WIDTH)
        cap_h = min(int(self.winfo_screenheight() * 0.85), self._MAX_HEIGHT)
        width = max(self._MIN_WIDTH, min(720, cap_w))

        self.geometry(f"{width}x{self._MIN_HEIGHT}")
        self.update_idletasks()
        display_lines = int(self._text.index("end-1c").split(".")[0])
        content_h = line_height * display_lines + 24
        height = max(
            self._MIN_HEIGHT,
            min(content_h + frame_pad + footer_height, cap_h),
        )

        self.minsize(self._MIN_WIDTH, self._MIN_HEIGHT)
        self.geometry(f"{width}x{height}")

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

        root.title("HH Converter")
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
                error = f"Error: {exc}"

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

        self._set_convert_label("Done!")
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
