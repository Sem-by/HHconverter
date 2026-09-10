from __future__ import annotations

LANGUAGE_LABELS: dict[str, str] = {
    "en": "English",
    "ru": "Русский",
    "uk": "Українська",
    "kk": "Қазақша",
    "fr": "Français",
    "es": "Español",
    "pl": "Polski",
    "de": "Deutsch",
}

LANGUAGE_CODES: tuple[str, ...] = tuple(LANGUAGE_LABELS)
_LABEL_TO_CODE = {label: code for code, label in LANGUAGE_LABELS.items()}

DEFAULT_LANGUAGE = "en"


def normalize_language(code: str | None) -> str:
    if not code:
        return DEFAULT_LANGUAGE
    key = str(code).strip().lower()
    return key if key in LANGUAGE_LABELS else DEFAULT_LANGUAGE


def language_from_label(label: str) -> str:
    return _LABEL_TO_CODE.get(label, DEFAULT_LANGUAGE)


def t(lang: str, key: str, **kwargs: object) -> str:
    """Look up a UI string; fall back to English, then the key."""
    code = normalize_language(lang)
    table = UI.get(code) or UI[DEFAULT_LANGUAGE]
    text = table.get(key) or UI[DEFAULT_LANGUAGE].get(key) or key
    if kwargs:
        return text.format(**kwargs)
    return text


# Main window + Settings + shared dialog chrome.
UI: dict[str, dict[str, str]] = {
    "en": {
        "settings_title": "Settings",
        "language": "Language",
        "import_folder": "Import folder",
        "export_folder": "Export folder",
        "clear_import": "Clear Import folder after converting",
        "coin_as_ps": "Coin hands as PokerStars (for non-PRO H2N)",
        "copy_to_dropbox": "Copy to Dropbox",
        "dropbox_folder": "Dropbox folder",
        "chico_folder": "Chico folder (optional)",
        "import_from_folders": "Import from folders",
        "poker_planets_folder": "PokerPlanets folder",
        "eight88_folder": "888poker folder",
        "onewin_folder": "1Win folder",
        "downloads_folder": "Downloads folder",
        "clear_folders": "Clear folders after import",
        "nickname": "Nickname",
        "browse": "Browse…",
        "cancel": "Cancel",
        "save": "Save",
        "required": "Required:\n• {items}",
        "could_not_save": "Could not save config:\n{exc}",
        "convert": "Convert",
        "done_again": "Done! Again?",
        "ready": "Ready",
        "converting": "Converting…",
        "player_name": "Player name: {alias}",
        "invalid_config": "Invalid config",
        "set_paths": "Please set the required paths in Settings:\n• {items}",
        "nickname_short": "Nickname",
        "info_title": "Instructions",
        "close": "Close",
        "discord": "Discord",
        "ok": "OK",
        "wizard_lang_title": "Choose your language",
        "wizard_h2n_title": "Which H2N3 do you use?",
        "wizard_h2n_pro": "PRO / ASIA",
        "wizard_h2n_basic": "BASIC",
        "wizard_nick_title": "Hero nickname",
    },
    "ru": {
        "settings_title": "Настройки",
        "language": "Язык",
        "import_folder": "Папка Import",
        "export_folder": "Папка Export",
        "clear_import": "Очистить папку Import после конвертации",
        "coin_as_ps": "Coin как PokerStars (для H2N без Pro/Asia)",
        "copy_to_dropbox": "Копировать в Dropbox",
        "dropbox_folder": "Папка Dropbox",
        "chico_folder": "Папка Chico (необязательно)",
        "import_from_folders": "Импорт из папок",
        "poker_planets_folder": "Папка PokerPlanets",
        "eight88_folder": "Папка 888poker",
        "onewin_folder": "Папка 1Win",
        "downloads_folder": "Папка Downloads",
        "clear_folders": "Очистить папки после импорта",
        "nickname": "Никнейм",
        "browse": "Обзор…",
        "cancel": "Отмена",
        "save": "Сохранить",
        "required": "Обязательно:\n• {items}",
        "could_not_save": "Не удалось сохранить конфиг:\n{exc}",
        "convert": "Конвертировать",
        "done_again": "Готово! Ещё раз?",
        "ready": "Готово",
        "converting": "Конвертация…",
        "player_name": "Игрок: {alias}",
        "invalid_config": "Неверный конфиг",
        "set_paths": "Укажите обязательные пути в Настройках:\n• {items}",
        "nickname_short": "Никнейм",
        "info_title": "Инструкция",
        "close": "Закрыть",
        "discord": "Discord",
        "ok": "OK",
        "wizard_lang_title": "Выберите язык",
        "wizard_h2n_title": "Какой H2N3 вы используете?",
        "wizard_h2n_pro": "PRO / ASIA",
        "wizard_h2n_basic": "BASIC",
        "wizard_nick_title": "Никнейм Hero",
    },
    "uk": {
        "settings_title": "Налаштування",
        "language": "Мова",
        "import_folder": "Папка Import",
        "export_folder": "Папка Export",
        "clear_import": "Очистити папку Import після конвертації",
        "coin_as_ps": "Coin як PokerStars (для H2N без Pro/Asia)",
        "copy_to_dropbox": "Копіювати в Dropbox",
        "dropbox_folder": "Папка Dropbox",
        "chico_folder": "Папка Chico (необов'язково)",
        "import_from_folders": "Імпорт з папок",
        "poker_planets_folder": "Папка PokerPlanets",
        "eight88_folder": "Папка 888poker",
        "onewin_folder": "Папка 1Win",
        "downloads_folder": "Папка Downloads",
        "clear_folders": "Очистити папки після імпорту",
        "nickname": "Нікнейм",
        "browse": "Огляд…",
        "cancel": "Скасувати",
        "save": "Зберегти",
        "required": "Обов'язково:\n• {items}",
        "could_not_save": "Не вдалося зберегти конфіг:\n{exc}",
        "convert": "Конвертувати",
        "done_again": "Готово! Ще раз?",
        "ready": "Готово",
        "converting": "Конвертація…",
        "player_name": "Гравець: {alias}",
        "invalid_config": "Невірний конфіг",
        "set_paths": "Вкажіть обов'язкові шляхи в Налаштуваннях:\n• {items}",
        "nickname_short": "Нікнейм",
        "info_title": "Інструкція",
        "close": "Закрити",
        "discord": "Discord",
        "ok": "OK",
        "wizard_lang_title": "Оберіть мову",
        "wizard_h2n_title": "Який H2N3 ви використовуєте?",
        "wizard_h2n_pro": "PRO / ASIA",
        "wizard_h2n_basic": "BASIC",
        "wizard_nick_title": "Нікнейм Hero",
    },
    "kk": {
        "settings_title": "Параметрлер",
        "language": "Тіл",
        "import_folder": "Import қалтасы",
        "export_folder": "Export қалтасы",
        "clear_import": "Түрлендіргеннен кейін Import қалтасын тазарту",
        "coin_as_ps": "Coin — PokerStars (Pro/Asia жоқ H2N)",
        "copy_to_dropbox": "Dropbox-қа көшіру",
        "dropbox_folder": "Dropbox қалтасы",
        "chico_folder": "Chico қалтасы (міндетті емес)",
        "import_from_folders": "Қалталардан импорт",
        "poker_planets_folder": "PokerPlanets қалтасы",
        "eight88_folder": "888poker қалтасы",
        "onewin_folder": "1Win қалтасы",
        "downloads_folder": "Downloads қалтасы",
        "clear_folders": "Импорттан кейін қалталарды тазарту",
        "nickname": "Лақап ат",
        "browse": "Шолу…",
        "cancel": "Болдырмау",
        "save": "Сақтау",
        "required": "Міндетті:\n• {items}",
        "could_not_save": "Конфиг сақталмады:\n{exc}",
        "convert": "Түрлендіру",
        "done_again": "Дайын! Тағы ма?",
        "ready": "Дайын",
        "converting": "Түрлендіру…",
        "player_name": "Ойыншы: {alias}",
        "invalid_config": "Жарамсыз конфиг",
        "set_paths": "Параметрлерде міндетті жолдарды орнатыңыз:\n• {items}",
        "nickname_short": "Лақап ат",
        "info_title": "Нұсқаулық",
        "close": "Жабу",
        "discord": "Discord",
        "ok": "OK",
        "wizard_lang_title": "Тілді таңдаңыз",
        "wizard_h2n_title": "Қай H2N3 қолданасыз?",
        "wizard_h2n_pro": "PRO / ASIA",
        "wizard_h2n_basic": "BASIC",
        "wizard_nick_title": "Hero лақап аты",
    },
    "fr": {
        "settings_title": "Paramètres",
        "language": "Langue",
        "import_folder": "Dossier Import",
        "export_folder": "Dossier Export",
        "clear_import": "Vider le dossier Import après conversion",
        "coin_as_ps": "Coin en PokerStars (H2N sans Pro/Asia)",
        "copy_to_dropbox": "Copier vers Dropbox",
        "dropbox_folder": "Dossier Dropbox",
        "chico_folder": "Dossier Chico (optionnel)",
        "import_from_folders": "Importer depuis des dossiers",
        "poker_planets_folder": "Dossier PokerPlanets",
        "eight88_folder": "Dossier 888poker",
        "onewin_folder": "Dossier 1Win",
        "downloads_folder": "Dossier Downloads",
        "clear_folders": "Vider les dossiers après import",
        "nickname": "Pseudo",
        "browse": "Parcourir…",
        "cancel": "Annuler",
        "save": "Enregistrer",
        "required": "Obligatoire :\n• {items}",
        "could_not_save": "Impossible d'enregistrer la config :\n{exc}",
        "convert": "Convertir",
        "done_again": "Terminé ! Encore ?",
        "ready": "Prêt",
        "converting": "Conversion…",
        "player_name": "Joueur : {alias}",
        "invalid_config": "Config invalide",
        "set_paths": "Définissez les chemins requis dans Paramètres :\n• {items}",
        "nickname_short": "Pseudo",
        "info_title": "Instructions",
        "close": "Fermer",
        "discord": "Discord",
        "ok": "OK",
        "wizard_lang_title": "Choisissez votre langue",
        "wizard_h2n_title": "Quel H2N3 utilisez-vous ?",
        "wizard_h2n_pro": "PRO / ASIA",
        "wizard_h2n_basic": "BASIC",
        "wizard_nick_title": "Pseudo Hero",
    },
    "es": {
        "settings_title": "Ajustes",
        "language": "Idioma",
        "import_folder": "Carpeta Import",
        "export_folder": "Carpeta Export",
        "clear_import": "Vaciar carpeta Import tras convertir",
        "coin_as_ps": "Coin como PokerStars (H2N sin Pro/Asia)",
        "copy_to_dropbox": "Copiar a Dropbox",
        "dropbox_folder": "Carpeta Dropbox",
        "chico_folder": "Carpeta Chico (opcional)",
        "import_from_folders": "Importar desde carpetas",
        "poker_planets_folder": "Carpeta PokerPlanets",
        "eight88_folder": "Carpeta 888poker",
        "onewin_folder": "Carpeta 1Win",
        "downloads_folder": "Carpeta Downloads",
        "clear_folders": "Vaciar carpetas tras importar",
        "nickname": "Apodo",
        "browse": "Examinar…",
        "cancel": "Cancelar",
        "save": "Guardar",
        "required": "Obligatorio:\n• {items}",
        "could_not_save": "No se pudo guardar la config:\n{exc}",
        "convert": "Convertir",
        "done_again": "¡Listo! ¿Otra vez?",
        "ready": "Listo",
        "converting": "Convirtiendo…",
        "player_name": "Jugador: {alias}",
        "invalid_config": "Config inválida",
        "set_paths": "Configure las rutas obligatorias en Ajustes:\n• {items}",
        "nickname_short": "Apodo",
        "info_title": "Instrucciones",
        "close": "Cerrar",
        "discord": "Discord",
        "ok": "OK",
        "wizard_lang_title": "Elija su idioma",
        "wizard_h2n_title": "¿Qué H2N3 usa?",
        "wizard_h2n_pro": "PRO / ASIA",
        "wizard_h2n_basic": "BASIC",
        "wizard_nick_title": "Apodo Hero",
    },
    "pl": {
        "settings_title": "Ustawienia",
        "language": "Język",
        "import_folder": "Folder Import",
        "export_folder": "Folder Export",
        "clear_import": "Wyczyść folder Import po konwersji",
        "coin_as_ps": "Coin jako PokerStars (H2N bez Pro/Asia)",
        "copy_to_dropbox": "Kopiuj do Dropbox",
        "dropbox_folder": "Folder Dropbox",
        "chico_folder": "Folder Chico (opcjonalnie)",
        "import_from_folders": "Import z folderów",
        "poker_planets_folder": "Folder PokerPlanets",
        "eight88_folder": "Folder 888poker",
        "onewin_folder": "Folder 1Win",
        "downloads_folder": "Folder Downloads",
        "clear_folders": "Wyczyść foldery po imporcie",
        "nickname": "Pseudonim",
        "browse": "Przeglądaj…",
        "cancel": "Anuluj",
        "save": "Zapisz",
        "required": "Wymagane:\n• {items}",
        "could_not_save": "Nie udało się zapisać konfiguracji:\n{exc}",
        "convert": "Konwertuj",
        "done_again": "Gotowe! Jeszcze raz?",
        "ready": "Gotowe",
        "converting": "Konwersja…",
        "player_name": "Gracz: {alias}",
        "invalid_config": "Nieprawidłowa konfiguracja",
        "set_paths": "Ustaw wymagane ścieżki w Ustawieniach:\n• {items}",
        "nickname_short": "Pseudonim",
        "info_title": "Instrukcja",
        "close": "Zamknij",
        "discord": "Discord",
        "ok": "OK",
        "wizard_lang_title": "Wybierz język",
        "wizard_h2n_title": "Którego H2N3 używasz?",
        "wizard_h2n_pro": "PRO / ASIA",
        "wizard_h2n_basic": "BASIC",
        "wizard_nick_title": "Pseudonim Hero",
    },
    "de": {
        "settings_title": "Einstellungen",
        "language": "Sprache",
        "import_folder": "Import-Ordner",
        "export_folder": "Export-Ordner",
        "clear_import": "Import-Ordner nach dem Konvertieren leeren",
        "coin_as_ps": "Coin als PokerStars (H2N ohne Pro/Asia)",
        "copy_to_dropbox": "Nach Dropbox kopieren",
        "dropbox_folder": "Dropbox-Ordner",
        "chico_folder": "Chico-Ordner (optional)",
        "import_from_folders": "Aus Ordnern importieren",
        "poker_planets_folder": "PokerPlanets-Ordner",
        "eight88_folder": "888poker-Ordner",
        "onewin_folder": "1Win-Ordner",
        "downloads_folder": "Downloads-Ordner",
        "clear_folders": "Ordner nach dem Import leeren",
        "nickname": "Nickname",
        "browse": "Durchsuchen…",
        "cancel": "Abbrechen",
        "save": "Speichern",
        "required": "Erforderlich:\n• {items}",
        "could_not_save": "Konfiguration konnte nicht gespeichert werden:\n{exc}",
        "convert": "Konvertieren",
        "done_again": "Fertig! Nochmal?",
        "ready": "Bereit",
        "converting": "Konvertierung…",
        "player_name": "Spielername: {alias}",
        "invalid_config": "Ungültige Konfiguration",
        "set_paths": "Bitte legen Sie die erforderlichen Pfade in den Einstellungen fest:\n• {items}",
        "nickname_short": "Nickname",
        "info_title": "Anleitung",
        "close": "Schließen",
        "discord": "Discord",
        "ok": "OK",
        "wizard_lang_title": "Wählen Sie Ihre Sprache",
        "wizard_h2n_title": "Welches H2N3 nutzen Sie?",
        "wizard_h2n_pro": "PRO / ASIA",
        "wizard_h2n_basic": "BASIC",
        "wizard_nick_title": "Hero-Nickname",
    },
}

_ROOMS = (
    "PokerPlanets, GGPokerOK (tournaments + cash), UPpoker, CoinPoker "
    "(tournaments + cash), 888poker, 1Win (tournaments + cash)"
)
_DROPBOX = "PP / GG / UP / 888 / Chico / CoinPoker / 1Win"

INFO_TEXTS: dict[str, str] = {
    "en": f"""\
Hand History Converter

1. Open Settings (gear icon) to configure:
   • Import folder — raw hand history .txt / .zip files (default: import/)
   • Export folder — converted output (default: export/)
   • Clear Import folder after converting — removes source .txt/.zip files when done (after Dropbox copy, if enabled)
   • Coin hands as PS — export CoinPoker as PokerStars (for Hand2Note without Pro/Asia).
   • Copy to Dropbox — mirrors raw {_DROPBOX} hands to Dropbox; shows Dropbox and optional Chico folders
   • Import from folders — also watch PokerPlanets, 888poker, 1Win, and Downloads folders for new files only
   • Clear folders after import — with "Copy to Dropbox" on, delete only processed files from watched folders after copy (never deletes Chico originals, unprocessed or pre–first-run Downloads files)
   • Nickname — hero name in converted GG / UP / Coin hands (default: Hero)
   • Language — UI language (bottom of Settings / Info)

2. Put .txt hand histories (or GG/UP .zip archives) in the Import folder. Rooms: {_ROOMS}.

3. Click Convert.
   • Converted files are written to Export.
   • .zip hand histories are unpacked and converted; with Copy to Dropbox, tournament summaries from separate zips go to Dropbox …/year/summaries.
   • With Copy to Dropbox: {_DROPBOX} raw files go to Dropbox (1Win under 1Win/year/month/).
   • Chico .txt files copy unchanged to Dropbox (if set); originals in the Chico folder are kept.
   • Import from folders: only new files since the last run are processed. Downloads files older than the app's first-run date are ignored to avoid duplicates already in the Hand2Note database. Import those via the Import folder manually if needed.
   • If you don't want your cash hands to get into the Dropbox do not use H2N3's auto import!

""",
    "ru": f"""\
Конвертер истории раздач

1. Откройте Настройки (иконка шестерёнки) для настройки:
   • Папка Import — исходные .txt / .zip файлы истории раздач (по умолчанию: import/)
   • Папка Export — сконвертированные файлы (по умолчанию: export/)
   • Очистить папку Import после конвертации — удаляет исходные .txt/.zip после завершения (после копирования в Dropbox, если включено)
   • Coin hands as PS — экспорт CoinPoker в формате PokerStars (для Hand2Note без Pro/Asia).
   • Копировать в Dropbox — копирует исходные {_DROPBOX} в Dropbox; открывает поля Dropbox и Chico (необязательно)
   • Импорт из папок — также следит за папками PokerPlanets, 888poker, 1Win и Downloads (только новые файлы)
   • Очистить папки после импорта — при включённом Dropbox удаляет только обработанные файлы из доп. папок (не удаляет оригиналы Chico, необработанные и файлы Downloads старше даты первого запуска)
   • Никнейм — имя героя в конвертированных раздачах GG / UP / Coin (по умолчанию: Hero).
   • Язык — язык интерфейса (внизу Настроек / Инструкции)

2. Положите .txt (или .zip GG/UP) в папку Import. Румы: {_ROOMS}.

3. Нажмите Convert.
   • Сконвертированные файлы сохраняются в Export.
   • Архивы .zip с раздачами распаковываются; при копировании в Dropbox саммари из отдельных zip попадают в …/year/summaries.
   • При копировании в Dropbox: исходные {_DROPBOX} копируются в Dropbox (1Win в 1Win/год/месяц/).
   • Файлы Chico копируются в Dropbox без изменений (если указана папка); оригиналы в папке Chico не удаляются.
   • Импорт из папок обрабатывает только новые файлы с прошлого запуска. Файлы в Downloads старше даты первого запуска приложения игнорируются, чтобы не дублировать раздачи уже в базе Hand2Note. При необходимости импортируйте их вручную через папку Import.
   • Если не хотите, чтобы кэш-раздачи попадали в Dropbox, не используйте автоимпорт H2N3!

""",
    "uk": f"""\
Конвертер історії роздач

1. Відкрийте Налаштування (іконка шестерні) для налаштування:
   • Папка Import — вихідні .txt / .zip файли історії роздач (за замовчуванням: import/)
   • Папка Export — сконвертовані файли (за замовчуванням: export/)
   • Очистити папку Import після конвертації — видаляє вихідні .txt/.zip після завершення (після копіювання в Dropbox, якщо увімкнено)
   • Coin hands as PS — експорт CoinPoker у форматі PokerStars (для Hand2Note без Pro/Asia).
   • Копіювати в Dropbox — копіює вихідні {_DROPBOX} у Dropbox; показує поля Dropbox і Chico (необов'язково)
   • Імпорт з папок — також стежить за папками PokerPlanets, 888poker, 1Win і Downloads (лише нові файли)
   • Очистити папки після імпорту — з увімкненим Dropbox видаляє лише оброблені файли з додаткових папок (не видаляє оригінали Chico, необроблені та файли Downloads старші за дату першого запуску)
   • Нікнейм — ім'я героя в сконвертованих роздачах GG / UP / Coin (за замовчуванням: Hero).
   • Мова — мова інтерфейсу (внизу Налаштувань / Інструкції)

2. Покладіть .txt (або .zip GG/UP) у папку Import. Руми: {_ROOMS}.

3. Натисніть Convert.
   • Сконвертовані файли зберігаються в Export.
   • Архіви .zip з роздачами розпаковуються; з Copy to Dropbox самарі з окремих zip потрапляють у …/year/summaries.
   • Якщо увімкнено копіювання в Dropbox: вихідні {_DROPBOX} копіюються в Dropbox (1Win у 1Win/рік/місяць/).
   • Файли Chico копіюються в Dropbox без змін (якщо вказано папку); оригінали в папці Chico не видаляються.
   • Імпорт з папок обробляє лише нові файли з попереднього запуску. Файли в Downloads старші за дату першого запуску програми ігноруються, щоб уникнути дублікатів уже в базі Hand2Note. За потреби імпортуйте їх вручну через папку Import.
   • Якщо не хочете, щоб кеш-роздачі потрапляли в Dropbox, не використовуйте автоімпорт H2N3!

""",
    "kk": f"""\
Раздаға тарихы конвертері

1. Баптау үшін Параметрлерді (тісті белгіше) ашыңыз:
   • Import қалтасы — бастапқы .txt / .zip раздаға тарихы файлдары (әдепкі: import/)
   • Export қалтасы — түрлендірілген шығыс (әдепкі: export/)
   • Түрлендіргеннен кейін Import қалтасын тазарту — аяқталғаннан кейін бастапқы .txt/.zip файлдарын жояды (Dropbox көшіруінен кейін, егер қосулы болса)
   • Coin hands as PS — CoinPoker-ді PokerStars форматында экспорттау (Pro/Asia жоқ Hand2Note үшін).
   • Dropbox-қа көшіру — {_DROPBOX} бастапқы файлдарын Dropbox-қа көшіреді; Dropbox және Chico өрістерін көрсетеді
   • Қалталардан импорт — PokerPlanets, 888poker, 1Win және Downloads қалталарын қадағалайды (тек жаңа файлдар)
   • Импорттан кейін қалталарды тазарту — Dropbox қосулы болса, тек өңделген файлдарды қосымша қалталардан жояды (Chico түпнұсқаларын, өңделмеген және бірінші іске қосу күнінен бұрынғы Downloads файлдарын жоймайды)
   • Лақап аты — түрлендірілген GG / UP / Coin раздачаларындағы кейіпкер аты (әдепкі: Hero).
   • Тіл — интерфейс тілі (Параметрлер / Нұсқаулық төменгі жағы)

2. Import қалтасына .txt (немесе GG/UP .zip) салыңыз. Үйлер: {_ROOMS}.

3. Convert түймесін басыңыз.
   • Түрлендірілген файлдар Export-қа жазылады.
   • .zip раздачалар шығарылады; Dropbox-қа көшіру қосулы болса summary zip-тер …/year/summaries-қа түседі.
   • Dropbox-қа көшіру қосулы болса: {_DROPBOX} бастапқы файлдары Dropbox-қа көшіріледі (1Win — 1Win/жыл/ай/).
   • Chico .txt файлдары Dropbox-қа өзгеріссіз көшіріледі (егер орнатылса); Chico қалтасындағы түпнұсқалар сақталады.
   • Қалталардан импорт тек соңғы іске қосудан бергі жаңа файлдарды өңдейді. Downloads-тағы қолданбаның бірінші іске қосу күнінен бұрынғы файлдар елемейді (Hand2Note дерекқорындағы қайталауларды болдырмау үшін). Қажет болса, оларды Import қалтасы арқылы қолмен импорттаңыз.
   • Кэш раздачалардың Dropbox-қа түсуін қаламасаңыз, H2N3 автоимпортын пайдаланбаңыз!

""",
    "fr": f"""\
Convertisseur d'historiques de mains

1. Ouvrez Paramètres (icône engrenage) pour configurer :
   • Dossier Import — fichiers .txt / .zip d'historiques bruts (par défaut : import/)
   • Dossier Export — fichiers convertis (par défaut : export/)
   • Vider le dossier Import après conversion — supprime les .txt/.zip sources une fois terminé (après copie Dropbox, si activée)
   • Coin hands as PS — export CoinPoker en PokerStars (Hand2Note sans Pro/Asia).
   • Copier vers Dropbox — copie les mains brutes {_DROPBOX} vers Dropbox ; affiche les dossiers Dropbox et Chico (optionnel)
   • Importer depuis des dossiers — surveille aussi PokerPlanets, 888poker, 1Win et Downloads (nouveaux fichiers seulement)
   • Vider les dossiers après import — avec Dropbox, supprime uniquement les fichiers traités des dossiers surveillés (ne supprime jamais les originaux Chico, ni les fichiers Downloads non traités / antérieurs à la date de première exécution)
   • Pseudo — nom du héros dans les mains GG / UP / Coin converties (par défaut : Hero).
   • Langue — langue de l'interface (bas de Paramètres / Instructions)

2. Placez les fichiers .txt (ou .zip GG/UP) dans Import. Salles : {_ROOMS}.

3. Cliquez sur Convert.
   • Les fichiers convertis sont écrits dans Export.
   • Les .zip de mains sont décompressés ; avec Dropbox, les résumés vont dans …/year/summaries.
   • Avec Copier vers Dropbox : les fichiers bruts {_DROPBOX} vont dans Dropbox (1Win sous 1Win/année/mois/).
   • Les .txt Chico sont copiés vers Dropbox tels quels (si défini) ; les originaux du dossier Chico sont conservés.
   • Import depuis dossiers : seuls les nouveaux fichiers depuis la dernière exécution sont traités. Les fichiers Downloads antérieurs à la date de première exécution de l'appli sont ignorés pour éviter les doublons déjà dans Hand2Note. Importez-les via Import manuellement si besoin.
   • Si vous ne voulez pas que vos mains cash aillent dans Dropbox, n'utilisez pas l'import auto de H2N3 !

""",
    "es": f"""\
Convertidor de historiales de manos

1. Abra Ajustes (icono de engranaje) para configurar:
   • Carpeta Import — archivos .txt / .zip de historiales (predeterminado: import/)
   • Carpeta Export — archivos convertidos (predeterminado: export/)
   • Vaciar carpeta Import tras convertir — elimina los .txt/.zip originales al terminar (tras la copia a Dropbox, si está activa)
   • Coin hands as PS — exportar CoinPoker como PokerStars (Hand2Note sin Pro/Asia).
   • Copiar a Dropbox — copia las manos {_DROPBOX} sin convertir a Dropbox; muestra carpetas Dropbox y Chico (opcional)
   • Importar desde carpetas — también vigila PokerPlanets, 888poker, 1Win y Downloads (solo archivos nuevos)
   • Vaciar carpetas tras importar — con Dropbox, borra solo archivos procesados de carpetas vigiladas (no borra originales de Chico, ni archivos de Downloads no procesados / anteriores a la fecha del primer uso)
   • Apodo — nombre del héroe en manos GG / UP / Coin convertidas (predeterminado: Hero).
   • Idioma — idioma de la interfaz (abajo de Ajustes / Instrucciones)

2. Coloque archivos .txt (o .zip GG/UP) en Import. Salas: {_ROOMS}.

3. Haga clic en Convert.
   • Los archivos convertidos se guardan en Export.
   • Los .zip de manos se descomprimen; con Dropbox, los summaries van a …/year/summaries.
   • Con Copiar a Dropbox: los archivos {_DROPBOX} sin convertir van a Dropbox (1Win en 1Win/año/mes/).
   • Los .txt de Chico se copian a Dropbox sin cambios (si está configurado); los originales en la carpeta Chico se conservan.
   • Importar desde carpetas solo procesa archivos nuevos desde la última ejecución. Los archivos de Downloads anteriores a la fecha del primer uso de la app se ignoran para evitar duplicados ya en Hand2Note. Impórtelos manualmente por Import si hace falta.
   • Si no quiere que sus manos de cash lleguen a Dropbox, no use la importación automática de H2N3.

""",
    "pl": f"""\
Konwerter historii rozdań

1. Otwórz Ustawienia (ikona koła zębatego), aby skonfigurować:
   • Folder Import — surowe pliki .txt / .zip historii rozdań (domyślnie: import/)
   • Folder Export — przekonwertowane pliki (domyślnie: export/)
   • Wyczyść folder Import po konwersji — usuwa źródłowe .txt/.zip po zakończeniu (po kopii do Dropbox, jeśli włączona)
   • Coin hands as PS — eksport CoinPoker jako PokerStars (Hand2Note bez Pro/Asia).
   • Kopiuj do Dropbox — kopiuje surowe {_DROPBOX} do Dropbox; pokazuje foldery Dropbox i Chico (opcjonalnie)
   • Import z folderów — także obserwuje PokerPlanets, 888poker, 1Win i Downloads (tylko nowe pliki)
   • Wyczyść foldery po imporcie — przy Dropbox usuwa tylko przetworzone pliki z obserwowanych folderów (nie usuwa oryginałów Chico, nieprzetworzonych ani plików Downloads starszych niż data pierwszego uruchomienia)
   • Pseudonim — nazwa bohatera w przekonwertowanych rozdanach GG / UP / Coin (domyślnie: Hero).
   • Język — język interfejsu (dół Ustawień / Instrukcji)

2. Umieść pliki .txt (lub .zip GG/UP) w folderze Import. Pokoje: {_ROOMS}.

3. Kliknij Convert.
   • Przekonwertowane pliki są zapisywane w Export.
   • Archiwa .zip z rozdaniami są rozpakowywane; przy Dropbox summary trafiają do …/year/summaries.
   • Przy Kopiuj do Dropbox: surowe {_DROPBOX} trafiają do Dropbox (1Win w 1Win/rok/miesiąc/).
   • Pliki Chico .txt kopiowane do Dropbox bez zmian (jeśli ustawione); oryginały w folderze Chico pozostają.
   • Import z folderów przetwarza tylko nowe pliki od ostatniego uruchomienia. Pliki w Downloads starsze niż data pierwszego uruchomienia aplikacji są ignorowane, aby uniknąć duplikatów już w bazie Hand2Note. W razie potrzeby zaimportuj je ręcznie przez folder Import.
   • Jeśli nie chcesz, żeby rozdania cash trafiały do Dropbox, nie używaj autoimportu H2N3!

""",
    "de": f"""\
Hand-History-Konverter

1. Öffnen Sie die Einstellungen (Zahnrad-Symbol) zur Konfiguration:
   • Import-Ordner — rohe Hand-History-.txt / -.zip-Dateien (Standard: import/)
   • Export-Ordner — konvertierte Ausgabe (Standard: export/)
   • Import-Ordner nach dem Konvertieren leeren — löscht Quell-.txt/.zip-Dateien nach Abschluss (nach Dropbox-Kopie, falls aktiviert)
   • Coin hands as PS — CoinPoker als PokerStars exportieren (für Hand2Note ohne Pro/Asia).
   • Nach Dropbox kopieren — spiegelt rohe {_DROPBOX}-Hände nach Dropbox; zeigt Dropbox- und optionalen Chico-Ordner
   • Aus Ordnern importieren — überwacht auch PokerPlanets-, 888poker-, 1Win- und Downloads-Ordner (nur neue Dateien)
   • Ordner nach dem Import leeren — bei aktiviertem Dropbox nur verarbeitete Dateien aus überwachten Ordnern löschen (löscht nie Chico-Originale, unverarbeitete oder Downloads-Dateien vor dem ersten Start)
   • Nickname — Hero-Name in konvertierten GG- / UP- / Coin-Händen (Standard: Hero).
   • Sprache — Sprache der Benutzeroberfläche (unten in Einstellungen / Anleitung)

2. Legen Sie .txt-Hand-Histories (oder GG/UP-.zip-Archive) in den Import-Ordner. Räume: {_ROOMS}.

3. Klicken Sie auf Konvertieren.
   • Konvertierte Dateien werden nach Export geschrieben.
   • .zip-Hand-Histories werden entpackt und konvertiert; mit Dropbox gehen Turnier-Summaries aus separaten Zips nach Dropbox …/year/summaries.
   • Mit Nach Dropbox kopieren: rohe {_DROPBOX}-Dateien gehen nach Dropbox (1Win unter 1Win/Jahr/Monat/).
   • Chico-.txt-Dateien werden unverändert nach Dropbox kopiert (falls gesetzt); Originale im Chico-Ordner bleiben erhalten.
   • Aus Ordnern importieren: nur neue Dateien seit dem letzten Lauf werden verarbeitet. Downloads-Dateien älter als das Erststart-Datum der App werden ignoriert, um Duplikate bereits in der Hand2Note-Datenbank zu vermeiden. Importieren Sie diese bei Bedarf manuell über den Import-Ordner.
   • Wenn Ihre Cash-Hände nicht in Dropbox landen sollen, verwenden Sie nicht den Auto-Import von H2N3!

""",
}
