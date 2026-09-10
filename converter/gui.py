from __future__ import annotations

import sys
import threading
import tkinter as tk
import tkinter.font as tkfont
import webbrowser
from collections.abc import Callable
from dataclasses import replace
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

from converter.i18n import (
    DEFAULT_LANGUAGE,
    INFO_TEXTS,
    LANGUAGE_LABELS,
    language_from_label,
    normalize_language,
    t,
)

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


def _center_on_screen(window: tk.Toplevel) -> None:
    window.update_idletasks()
    width = window.winfo_width()
    height = window.winfo_height()
    x = max(0, (window.winfo_screenwidth() - width) // 2)
    y = max(0, (window.winfo_screenheight() - height) // 2)
    window.geometry(f"+{x}+{y}")


def _show_modal(window: tk.Toplevel, parent: tk.Misc) -> None:
    """Show a modal dialog even when the main window is withdrawn."""
    apply_window_icon(window)
    window.resizable(False, False)
    try:
        if bool(parent.winfo_viewable()):
            window.transient(parent)
    except tk.TclError:
        pass
    window.update_idletasks()
    _center_on_screen(window)
    window.deiconify()
    window.lift()
    window.focus_force()
    try:
        window.attributes("-topmost", True)
        window.after(50, lambda: window.attributes("-topmost", False))
    except tk.TclError:
        pass
    window.grab_set()


class SetupWizard:
    """First-run dialogs: language → H2N edition → hero nickname."""

    def __init__(self, parent: tk.Misc, config_path: Path) -> None:
        self._parent = parent
        self._config_path = config_path
        self._lang = DEFAULT_LANGUAGE
        self._coin_as_ps = False
        self._nickname = "Hero"
        self._cancelled = False

    def run(self) -> Settings | None:
        if not self._step_language():
            return None
        if not self._step_h2n():
            return None
        if not self._step_nickname():
            return None

        settings = replace(
            default_settings(),
            ui_language=self._lang,
            coin_as_ps=self._coin_as_ps,
            player_alias=self._nickname,
        )
        save_settings(self._config_path, settings)
        settings.import_path.mkdir(parents=True, exist_ok=True)
        settings.export_path.mkdir(parents=True, exist_ok=True)
        return settings

    def _step_language(self) -> bool:
        win = tk.Toplevel(self._parent)
        win.withdraw()
        self._cancelled = True
        lang_var = tk.StringVar(value=LANGUAGE_LABELS[self._lang])
        title_lbl = ttk.Label(win, anchor=tk.CENTER)
        title_lbl.pack(padx=24, pady=(20, 12))

        combo = ttk.Combobox(
            win,
            textvariable=lang_var,
            values=list(LANGUAGE_LABELS.values()),
            state="readonly",
            width=18,
        )
        combo.pack(padx=24, pady=(0, 16))

        def refresh_title(_event: tk.Event | None = None) -> None:
            code = language_from_label(lang_var.get())
            title_lbl.configure(text=t(code, "wizard_lang_title"))
            win.title(t(code, "wizard_lang_title"))
            ok_btn.configure(text=t(code, "ok"))

        def accept() -> None:
            self._lang = language_from_label(lang_var.get())
            self._cancelled = False
            win.destroy()

        combo.bind("<<ComboboxSelected>>", refresh_title)
        ok_btn = ttk.Button(win, text=t(self._lang, "ok"), command=accept)
        ok_btn.pack(pady=(0, 16))
        refresh_title()
        win.protocol("WM_DELETE_WINDOW", win.destroy)
        win.bind("<Return>", lambda _e: accept())
        win.bind("<Escape>", lambda _e: win.destroy())
        _show_modal(win, self._parent)
        win.wait_window()
        return not self._cancelled

    def _step_h2n(self) -> bool:
        win = tk.Toplevel(self._parent)
        win.withdraw()
        self._cancelled = True
        win.title(t(self._lang, "wizard_h2n_title"))

        ttk.Label(win, text=t(self._lang, "wizard_h2n_title"), anchor=tk.CENTER).pack(
            padx=24, pady=(20, 16)
        )
        buttons = ttk.Frame(win)
        buttons.pack(padx=24, pady=(0, 20))

        def choose_pro() -> None:
            self._coin_as_ps = False
            self._cancelled = False
            win.destroy()

        def choose_basic() -> None:
            self._coin_as_ps = True
            self._cancelled = False
            win.destroy()

        ttk.Button(
            buttons, text=t(self._lang, "wizard_h2n_pro"), width=14, command=choose_pro
        ).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(
            buttons,
            text=t(self._lang, "wizard_h2n_basic"),
            width=14,
            command=choose_basic,
        ).pack(side=tk.LEFT)

        win.protocol("WM_DELETE_WINDOW", win.destroy)
        win.bind("<Escape>", lambda _e: win.destroy())
        _show_modal(win, self._parent)
        win.wait_window()
        return not self._cancelled

    def _step_nickname(self) -> bool:
        win = tk.Toplevel(self._parent)
        win.withdraw()
        self._cancelled = True
        win.title(t(self._lang, "wizard_nick_title"))

        ttk.Label(win, text=t(self._lang, "wizard_nick_title"), anchor=tk.CENTER).pack(
            padx=24, pady=(20, 12)
        )
        nick_var = tk.StringVar(value="Hero")
        entry = ttk.Entry(win, textvariable=nick_var, width=28)
        entry.pack(padx=24, pady=(0, 16))
        entry.select_range(0, tk.END)
        entry.focus_set()

        def accept() -> None:
            nick = nick_var.get().strip() or "Hero"
            self._nickname = nick
            self._cancelled = False
            win.destroy()

        ttk.Button(win, text=t(self._lang, "ok"), command=accept).pack(pady=(0, 16))
        win.protocol("WM_DELETE_WINDOW", win.destroy)
        win.bind("<Return>", lambda _e: accept())
        win.bind("<Escape>", lambda _e: win.destroy())
        _show_modal(win, self._parent)
        win.wait_window()
        return not self._cancelled


class SettingsDialog(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Misc,
        config_path: Path,
        settings: Settings | None,
        lang: str,
        on_language_change: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__(parent)
        apply_window_icon(self)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self._config_path = config_path
        self._result: Settings | None = None
        self._lang = normalize_language(lang)
        self._language_change_cb = on_language_change
        self._path_labels: dict[str, ttk.Label] = {}
        self._browse_buttons: list[ttk.Button] = []

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
            "eight88_folder": tk.StringVar(
                value=path_display(base.eight88_folder) if base.eight88_folder else ""
            ),
            "onewin_folder": tk.StringVar(
                value=path_display(base.onewin_folder) if base.onewin_folder else ""
            ),
            "downloads_folder": tk.StringVar(
                value=path_display(base.downloads_folder) if base.downloads_folder else ""
            ),
            "clear_folders_after_import": tk.BooleanVar(
                value=base.clear_folders_after_import and base.dropbox_mode == "original"
            ),
        }
        self._lang_var = tk.StringVar(value=LANGUAGE_LABELS[self._lang])

        body = ttk.Frame(self, padding=12)
        body.grid(row=0, column=0, sticky="nsew")

        row = 0
        row = self._add_path_row(body, row, "import_folder", "import_path")
        row = self._add_path_row(body, row, "export_folder", "export_path")

        self._cb_clear_import = ttk.Checkbutton(
            body,
            variable=self._vars["clear_import_after_convert"],
        )
        self._cb_clear_import.grid(row=row, column=0, columnspan=2, sticky="w", pady=(8, 4))
        row += 1

        self._cb_coin = ttk.Checkbutton(
            body,
            variable=self._vars["coin_as_ps"],
        )
        self._cb_coin.grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 4))
        row += 1

        self._cb_dropbox = ttk.Checkbutton(
            body,
            variable=self._vars["copy_to_dropbox"],
            command=self._on_dropbox_toggle,
        )
        self._cb_dropbox.grid(row=row, column=0, columnspan=2, sticky="w", pady=(4, 4))
        row += 1

        self._dropbox_section = ttk.Frame(body)
        self._dropbox_section.grid(row=row, column=0, columnspan=2, sticky="ew")
        self._dropbox_section.columnconfigure(0, weight=1)
        section_row = 0
        section_row = self._add_path_row(
            self._dropbox_section,
            section_row,
            "dropbox_folder",
            "dropbox_base_path",
        )
        self._add_path_row(
            self._dropbox_section,
            section_row,
            "chico_folder",
            "chico_import_path",
        )
        row += 1

        self._cb_import_folders = ttk.Checkbutton(
            body,
            variable=self._vars["import_from_folders"],
            command=self._toggle_import_folders,
        )
        self._cb_import_folders.grid(row=row, column=0, columnspan=2, sticky="w", pady=(8, 4))
        row += 1

        self._folders_section = ttk.Frame(body)
        self._folders_section.grid(row=row, column=0, columnspan=2, sticky="ew")
        self._folders_section.columnconfigure(0, weight=1)
        frow = 0
        frow = self._add_path_row(
            self._folders_section,
            frow,
            "poker_planets_folder",
            "poker_planets_folder",
        )
        frow = self._add_path_row(
            self._folders_section,
            frow,
            "eight88_folder",
            "eight88_folder",
        )
        frow = self._add_path_row(
            self._folders_section,
            frow,
            "onewin_folder",
            "onewin_folder",
        )
        frow = self._add_path_row(
            self._folders_section,
            frow,
            "downloads_folder",
            "downloads_folder",
        )
        self._clear_folders_cb = ttk.Checkbutton(
            self._folders_section,
            variable=self._vars["clear_folders_after_import"],
        )
        self._clear_folders_cb.grid(row=frow, column=0, columnspan=2, sticky="w", pady=(4, 0))
        row += 1

        self._nickname_label = ttk.Label(body)
        self._nickname_label.grid(
            row=row, column=0, columnspan=2, sticky="w", pady=(8, 2)
        )
        ttk.Entry(body, textvariable=self._vars["player_alias"], width=48).grid(
            row=row + 1, column=0, columnspan=2, sticky="ew"
        )
        row += 2

        footer = ttk.Frame(body)
        footer.grid(row=row, column=0, columnspan=2, pady=(12, 0), sticky="ew")
        lang_combo = ttk.Combobox(
            footer,
            textvariable=self._lang_var,
            values=list(LANGUAGE_LABELS.values()),
            state="readonly",
            width=14,
        )
        lang_combo.pack(side=tk.LEFT)
        lang_combo.bind("<<ComboboxSelected>>", self._on_language_change)
        self._btn_cancel = ttk.Button(footer, command=self._cancel)
        self._btn_cancel.pack(side=tk.RIGHT, padx=(6, 0))
        self._btn_save = ttk.Button(footer, command=self._save)
        self._btn_save.pack(side=tk.RIGHT)

        body.columnconfigure(0, weight=1)
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.bind("<Escape>", lambda _e: self._cancel())

        self._apply_language()
        self._toggle_dropbox_fields()
        self._toggle_import_folders()
        self._sync_clear_folders_state()
        self.update_idletasks()
        self._center_over(parent)

    def _on_language_change(self, _event: tk.Event | None = None) -> None:
        self._lang = language_from_label(self._lang_var.get())
        self._apply_language()
        if self._language_change_cb is not None:
            self._language_change_cb(self._lang)

    def _apply_language(self) -> None:
        lang = self._lang
        self.title(t(lang, "settings_title"))
        self._lang_var.set(LANGUAGE_LABELS[lang])
        for key, label in self._path_labels.items():
            label.configure(text=t(lang, key))
        for btn in self._browse_buttons:
            btn.configure(text=t(lang, "browse"))
        self._cb_clear_import.configure(text=t(lang, "clear_import"))
        self._cb_coin.configure(text=t(lang, "coin_as_ps"))
        self._cb_dropbox.configure(text=t(lang, "copy_to_dropbox"))
        self._cb_import_folders.configure(text=t(lang, "import_from_folders"))
        self._clear_folders_cb.configure(text=t(lang, "clear_folders"))
        self._nickname_label.configure(text=t(lang, "nickname"))
        self._btn_cancel.configure(text=t(lang, "cancel"))
        self._btn_save.configure(text=t(lang, "save"))

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

    def _add_path_row(self, parent: ttk.Frame, row: int, label_key: str, key: str) -> int:
        label = ttk.Label(parent)
        label.grid(row=row, column=0, columnspan=2, sticky="w", pady=(6, 2))
        self._path_labels[label_key] = label
        entry = ttk.Entry(parent, textvariable=self._vars[key], width=40)
        entry.grid(row=row + 1, column=0, sticky="ew", padx=(0, 6))
        browse = ttk.Button(
            parent,
            command=lambda k=key, e=entry: self._browse(k, e),
        )
        browse.grid(row=row + 1, column=1, sticky="e")
        self._browse_buttons.append(browse)
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
        eight88_folder = self._vars["eight88_folder"].get().strip()
        onewin_folder = self._vars["onewin_folder"].get().strip()
        downloads = self._vars["downloads_folder"].get().strip()
        alias = self._vars["player_alias"].get().strip()
        copy_to_dropbox = self._vars["copy_to_dropbox"].get()
        import_from_folders = self._vars["import_from_folders"].get()
        clear_folders = (
            self._vars["clear_folders_after_import"].get() if copy_to_dropbox else False
        )
        lang = self._lang

        missing = [
            name
            for name, value in (
                (t(lang, "import_folder"), import_path),
                (t(lang, "export_folder"), export_path),
                (t(lang, "nickname_short"), alias),
            )
            if not value
        ]
        if copy_to_dropbox and not dropbox_path:
            missing.append(t(lang, "dropbox_folder"))
        if missing:
            messagebox.showerror(
                t(lang, "settings_title"),
                t(lang, "required", items="\n• ".join(missing)),
                parent=self,
            )
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
            eight88_folder=Path(eight88_folder) if eight88_folder else None,
            onewin_folder=Path(onewin_folder) if onewin_folder else None,
            downloads_folder=Path(downloads) if downloads else None,
            clear_folders_after_import=clear_folders,
            ui_language=lang,
        )
        try:
            save_settings(self._config_path, self._result)
        except OSError as exc:
            messagebox.showerror(
                t(lang, "settings_title"),
                t(lang, "could_not_save", exc=exc),
                parent=self,
            )
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

    def __init__(
        self,
        parent: tk.Misc,
        lang: str = "en",
        on_language_change: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self._lang_code = normalize_language(lang)
        self._parent = parent
        self._on_language_change_cb = on_language_change
        self._diagram_pil: Image.Image | None = None
        self._diagram_image: ImageTk.PhotoImage | None = None
        self._diagram_full_image: ImageTk.PhotoImage | None = None
        self._diagram_full_win: tk.Toplevel | None = None
        self._discord_image: tk.PhotoImage | None = None
        self._resize_after: str | None = None
        self._last_diagram_width = 0
        self._initial_layout_done = False

        self.title(t(self._lang_code, "info_title"))
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

        self._lang_var = tk.StringVar(value=LANGUAGE_LABELS[self._lang_code])
        lang_combo = ttk.Combobox(
            footer,
            textvariable=self._lang_var,
            values=list(LANGUAGE_LABELS.values()),
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
        btn = ttk.Button(
            parent, text=t(self._lang_code, "discord"), width=8, command=self._open_discord
        )
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
        win.title(t(self._lang_code, "info_title"))
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
        self._set_language(language_from_label(self._lang_var.get()))

    def _set_language(self, lang_code: str) -> None:
        lang_code = normalize_language(lang_code)
        prev = self._lang_code
        self._lang_code = lang_code
        self._lang_var.set(LANGUAGE_LABELS[lang_code])
        self.title(t(lang_code, "info_title"))
        self._close_btn.configure(text=t(lang_code, "close"))
        if isinstance(self._discord_btn, ttk.Button):
            self._discord_btn.configure(text=t(lang_code, "discord"))
        content = INFO_TEXTS.get(lang_code) or INFO_TEXTS["en"]
        self._text.configure(state=tk.NORMAL)
        self._text.delete("1.0", tk.END)
        self._text.insert("1.0", content)
        self._text.configure(state=tk.DISABLED)
        self._fit_to_content()
        self._center_over(self._parent)
        if prev != lang_code and self._on_language_change_cb is not None:
            self._on_language_change_cb(lang_code)

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
        self._lang = "en"
        self._convert_idle_key = "convert"

        root.title(f"HH Converter {__version__}")
        root.minsize(320, 140)
        root.resizable(False, False)

        self._build_ui()
        self._reload_settings(silent=True)
        self._apply_language()

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
            text=t(self._lang, "convert"),
            style="Convert.TButton",
            command=self._start_convert,
        )
        self._btn_convert.pack(fill=tk.X, pady=(12, 8))

        self._status = ttk.Label(outer, text=t(self._lang, "ready"), anchor=tk.W)
        self._status.pack(fill=tk.X)

    def _apply_language(self) -> None:
        lang = self._lang
        if self._busy:
            self._btn_convert.configure(text=t(lang, "convert"))
            self._status.configure(text=t(lang, "converting"))
        elif self._convert_idle_key == "done_again":
            self._btn_convert.configure(text=t(lang, "done_again"))
            if self._settings:
                self._status.configure(text=self._status_text(self._settings))
        else:
            self._btn_convert.configure(text=t(lang, "convert"))
            if self._settings:
                self._status.configure(text=self._status_text(self._settings))
            else:
                self._status.configure(text=t(lang, "ready"))

    def _set_language(self, lang: str, *, persist: bool = True) -> None:
        lang = normalize_language(lang)
        self._lang = lang
        if persist and self._settings is not None and self._settings.ui_language != lang:
            self._settings = replace(self._settings, ui_language=lang)
            try:
                save_settings(self.config_path, self._settings)
            except OSError:
                pass
        self._apply_language()

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        state = tk.DISABLED if busy else tk.NORMAL
        self._btn_convert.configure(state=state)
        self._btn_settings.configure(state=state)

    def _set_convert_label(self, key: str) -> None:
        self._convert_idle_key = key
        self._btn_convert.configure(text=t(self._lang, key))

    def _reload_settings(self, *, silent: bool) -> None:
        try:
            ensure_default_config(self.config_path)
            self._settings = load_settings(self.config_path)
        except ValueError as exc:
            self._settings = None
            self._status.configure(text=t(self._lang, "invalid_config"))
            if not silent:
                messagebox.showerror(t(self._lang, "settings_title"), str(exc), parent=self.root)
            return
        self._lang = normalize_language(self._settings.ui_language)
        self._status.configure(text=self._status_text(self._settings))

    def _missing_convert_paths(self, settings: Settings) -> list[str]:
        missing: list[str] = []
        if not is_path_set(settings.import_path):
            missing.append(t(self._lang, "import_folder"))
        if not is_path_set(settings.export_path):
            missing.append(t(self._lang, "export_folder"))
        if settings.dropbox_mode == "original" and not is_path_set(settings.dropbox_base_path):
            missing.append(t(self._lang, "dropbox_folder"))
        return missing

    def _prompt_configure_paths(self, missing: list[str]) -> None:
        messagebox.showwarning(
            t(self._lang, "convert"),
            t(self._lang, "set_paths", items="\n• ".join(missing)),
            parent=self.root,
        )
        self._open_settings()

    def _status_text(self, settings: Settings) -> str:
        return t(self._lang, "player_name", alias=settings.player_alias)

    def _open_settings(self) -> None:
        dialog = SettingsDialog(
            self.root,
            self.config_path,
            self._settings,
            self._lang,
            on_language_change=self._on_settings_language,
        )
        updated = dialog.run()
        if updated is not None:
            self._settings = updated
            self._lang = normalize_language(updated.ui_language)
            self._convert_idle_key = "convert"
            self._apply_language()

    def _open_info(self) -> None:
        InfoDialog(self.root, lang=self._lang, on_language_change=self._on_info_language)

    def _on_settings_language(self, lang: str) -> None:
        self._set_language(lang, persist=True)

    def _on_info_language(self, lang: str) -> None:
        self._set_language(lang, persist=True)

    def _start_convert(self) -> None:
        if self._busy:
            return
        if self._settings is None:
            self._reload_settings(silent=True)
        if self._settings is None:
            self._prompt_configure_paths(
                [t(self._lang, "import_folder"), t(self._lang, "export_folder")]
            )
            return

        missing = self._missing_convert_paths(self._settings)
        if missing:
            self._prompt_configure_paths(missing)
            return

        self._set_convert_label("convert")
        self._set_busy(True)
        self._status.configure(text=t(self._lang, "converting"))
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
            self._set_convert_label("convert")
            if self._settings:
                self._status.configure(text=self._status_text(self._settings))
            messagebox.showerror(t(self._lang, "convert"), error, parent=self.root)
            return

        self._set_convert_label("done_again")
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

    if not config_path.is_file():
        root.withdraw()
        if SetupWizard(root, config_path).run() is None:
            root.destroy()
            return 0
        root.deiconify()

    ConverterApp(root, config_path)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
