"""
i18n — Internationalization for MikroBot.

Supported languages: en, ru, de, am
Usage:
    from ui.i18n import t
    text = t("system.info", lang="ru")
"""

from typing import Optional

_STRINGS: dict[str, dict[str, str]] = {
    # ── Generic ────────────────────────────────────────────────────────────────
    "btn.back":         {"en": "⬅️ Back",    "ru": "⬅️ Назад",    "de": "⬅️ Zurück",   "am": "⬅️ Վերադառնալ"},
    "btn.refresh":      {"en": "🔄 Refresh", "ru": "🔄 Обновить", "de": "🔄 Aktualisieren", "am": "🔄 Թարմացնել"},
    "btn.cancel":       {"en": "❌ Cancel",  "ru": "❌ Отмена",   "de": "❌ Abbrechen", "am": "❌ Չեղարկել"},
    "btn.add":          {"en": "➕ Add",     "ru": "➕ Добавить", "de": "➕ Hinzufügen","am": "➕ Ավելացնել"},
    "btn.remove":       {"en": "🗑 Remove",  "ru": "🗑 Удалить",  "de": "🗑 Entfernen", "am": "🗑 Հեռացնել"},
    "btn.confirm":      {"en": "✅ Confirm", "ru": "✅ Подтвердить","de": "✅ Bestätigen","am": "✅ Հաստատել"},
    "btn.enable":       {"en": "✅ Enable",  "ru": "✅ Включить", "de": "✅ Aktivieren","am": "✅ Ակտիվացնել"},
    "btn.disable":      {"en": "⛔ Disable", "ru": "⛔ Выключить","de": "⛔ Deaktivieren","am": "⛔ Անջատել"},

    # ── Errors / Alerts ────────────────────────────────────────────────────────
    "err.no_router":    {
        "en": "❌ No router connected.\nUse /add\\_router to connect your MikroTik device.",
        "ru": "❌ Роутер не подключён.\nИспользуйте /add\\_router для подключения.",
        "de": "❌ Kein Router verbunden.\nNutze /add\\_router um deinen MikroTik zu verbinden.",
        "am": "❌ Երթուղիչ չի միացված։\nՕգտագործեք /add\\_router՝ MikroTik-ը միացնելու համար:",
    },
    "err.no_permission": {
        "en": "🚫 Insufficient permissions.",
        "ru": "🚫 Недостаточно прав.",
        "de": "🚫 Unzureichende Berechtigungen.",
        "am": "🚫 Անբավարար թույլտվություններ:",
    },
    "err.not_authorized": {
        "en": "🚫 You are not authorized. Contact the bot owner.",
        "ru": "🚫 Нет доступа. Обратитесь к владельцу бота.",
        "de": "🚫 Nicht autorisiert. Kontaktiere den Bot-Eigentümer.",
        "am": "🚫 Դուք թույлատրված չեք: Կապվեք բոտի սեփականատիրոջ հետ:",
    },
    "err.connection_lost": {
        "en": "🔌 Router connection lost. Try again or reconnect.",
        "ru": "🔌 Соединение с роутером потеряно. Попробуйте снова.",
        "de": "🔌 Verbindung zum Router getrennt. Erneut versuchen.",
        "am": "🔌 Կորցրեց կապը երթուղիչի հետ: Կրկին փորձեք:",
    },
    "err.timeout": {
        "en": "⏱ Router is not responding. Check if it's online.",
        "ru": "⏱ Роутер не отвечает. Проверьте, доступен ли он.",
        "de": "⏱ Router antwortet nicht. Prüfe ob er online ist.",
        "am": "⏱ Երթուղիչը չի պատասխանում: Ստուգեք արդյոք այն առցանց է:",
    },
    "err.generic": {
        "en": "❌ Unexpected error: `{type}`\n`{msg}`",
        "ru": "❌ Непредвиденная ошибка: `{type}`\n`{msg}`",
        "de": "❌ Unerwarteter Fehler: `{type}`\n`{msg}`",
        "am": "❌ Անկանխատեսելի սխալ: `{type}`\n`{msg}`",
    },

    # ── System ─────────────────────────────────────────────────────────────────
    "menu.system":      {"en": "📊 System",      "ru": "📊 Система",     "de": "📊 System",      "am": "📊 Համակարգ"},
    "sys.reboot_confirm": {
        "en": "⚠️ *Reboot router now?*\n\nThe router will be offline for ~30 seconds.",
        "ru": "⚠️ *Перезагрузить роутер?*\n\nРоутер будет недоступен ~30 секунд.",
        "de": "⚠️ *Router jetzt neu starten?*\n\nDer Router wird ca. 30 Sekunden offline sein.",
        "am": "⚠️ *Վերաբեռնե՞լ երթուղիչը։*\n\nԵրթուղիչը ~30 վայրկյան անհասանելի կլինի:",
    },
    "sys.rebooting": {
        "en": "🔁 *Reboot command sent.*\n\nRouter will be back in ~30 seconds.",
        "ru": "🔁 *Команда перезагрузки отправлена.*\n\nРоутер вернётся через ~30 секунд.",
        "de": "🔁 *Neustart-Befehl gesendet.*\n\nRouter kommt in ~30 Sekunden zurück.",
        "am": "🔁 *Վերաբեռնման հրամանն ուղարկված է:*\n\nԵրթուղիչը կվերադառնա ~30 վայրկյանից:",
    },

    # ── Interfaces ─────────────────────────────────────────────────────────────
    "menu.interfaces":  {"en": "🔌 Interfaces",  "ru": "🔌 Интерфейсы",  "de": "🔌 Schnittstellen","am": "🔌 Ինտերֆեյսներ"},

    # ── Firewall ───────────────────────────────────────────────────────────────
    "menu.firewall":    {"en": "🛡 Firewall",     "ru": "🛡 Файрвол",     "de": "🛡 Firewall",    "am": "🛡 Firewall"},
    "fw.blocked":       {
        "en": "🚫 `{ip}` added to blacklist.",
        "ru": "🚫 `{ip}` добавлен в чёрный список.",
        "de": "🚫 `{ip}` zur Blacklist hinzugefügt.",
        "am": "🚫 `{ip}` ավելացված է սև ցուցակում:",
    },

    # ── DHCP ───────────────────────────────────────────────────────────────────
    "menu.dhcp":        {"en": "📡 DHCP",         "ru": "📡 DHCP",        "de": "📡 DHCP",        "am": "📡 DHCP"},

    # ── Wireless ───────────────────────────────────────────────────────────────
    "menu.wireless":    {"en": "📶 Wireless",     "ru": "📶 Wi-Fi",       "de": "📶 Wireless",    "am": "📶 Wireless"},
    "wifi.pass_short":  {
        "en": "❌ WiFi password must be at least 8 characters.",
        "ru": "❌ Пароль Wi-Fi должен быть минимум 8 символов.",
        "de": "❌ WLAN-Passwort muss mindestens 8 Zeichen haben.",
        "am": "❌ Wi-Fi գաղտնաբառը պետք է ունենա առնվազն 8 նիշ:",
    },

    # ── VPN ────────────────────────────────────────────────────────────────────
    "menu.vpn":         {"en": "🔒 VPN",          "ru": "🔒 VPN",         "de": "🔒 VPN",         "am": "🔒 VPN"},

    # ── Network ────────────────────────────────────────────────────────────────
    "menu.network":     {"en": "🌐 Network",      "ru": "🌐 Сеть",        "de": "🌐 Netzwerk",    "am": "🌐 Ցանց"},
    "menu.routes":      {"en": "🗺 Routes",       "ru": "🗺 Маршруты",    "de": "🗺 Routen",      "am": "🗺 Երթուղիներ"},
    "menu.dns":         {"en": "🌐 DNS",          "ru": "🌐 DNS",         "de": "🌐 DNS",         "am": "🌐 DNS"},

    # ── Logs ───────────────────────────────────────────────────────────────────
    "menu.logs":        {"en": "📋 Logs",         "ru": "📋 Логи",        "de": "📋 Logs",        "am": "📋 Գրանցամատյաններ"},
    "log.stream_start": {
        "en": "📡 *Log stream started.*\nTap 🔴 Stop to end. Or use /stop\\_logs.",
        "ru": "📡 *Стриминг логов запущен.*\nНажмите 🔴 Стоп для остановки. Или /stop\\_logs.",
        "de": "📡 *Log-Stream gestartet.*\nTippe 🔴 Stop zum Beenden. Oder /stop\\_logs.",
        "am": "📡 *Մատյանի հոսքը սկսված է:*\nSentinel 🔴 Stop-ին՝ ավարտելու համար: Կամ /stop\\_logs:",
    },

    # ── Tools ──────────────────────────────────────────────────────────────────
    "menu.tools":       {"en": "🔧 Tools",        "ru": "🔧 Инструменты", "de": "🔧 Tools",       "am": "🔧 Գործիքներ"},

    # ── Backup ─────────────────────────────────────────────────────────────────
    "menu.backup":      {"en": "📦 Backup",       "ru": "📦 Резервная копия","de": "📦 Sicherung", "am": "📦 Կրկնօրինակ"},
    "backup.created":   {
        "en": "✅ *Backup created!*\nFile: `{filename}`",
        "ru": "✅ *Резервная копия создана!*\nФайл: `{filename}`",
        "de": "✅ *Sicherung erstellt!*\nDatei: `{filename}`",
        "am": "✅ *Կրկնօրինակը ստեղծվեց!*\nՖայլ: `{filename}`",
    },

    # ── Extras ─────────────────────────────────────────────────────────────────
    "menu.extras":      {"en": "🌉 Extras",       "ru": "🌉 Прочее",      "de": "🌉 Extras",      "am": "🌉 Լրացուցիչ"},
    "menu.hotspot":     {"en": "🔥 Hotspot",      "ru": "🔥 Хотспот",     "de": "🔥 Hotspot",     "am": "🔥 Hotspot"},
    "menu.queues":      {"en": "📊 QoS / Queues", "ru": "📊 КоС / Очереди","de": "📊 QoS / Warteschlangen","am": "📊 QoS / Հերթեր"},

    # ── Settings ───────────────────────────────────────────────────────────────
    "menu.settings":    {"en": "⚙️ Settings",     "ru": "⚙️ Настройки",   "de": "⚙️ Einstellungen","am": "⚙️ Պարամետրեր"},
    "settings.lang_set": {
        "en": "🌐 Language set to English.",
        "ru": "🌐 Язык изменён на Русский.",
        "de": "🌐 Sprache auf Deutsch gesetzt.",
        "am": "🌐 Լեզուն փոխվել է հայերենի:",
    },
    "settings.lang_prompt": {
        "en": "🌐 *Select your language:*",
        "ru": "🌐 *Выберите язык:*",
        "de": "🌐 *Sprache auswählen:*",
        "am": "🌐 *Ընտրեք լեզուն:*",
    },

    # ── Add Router FSM ─────────────────────────────────────────────────────────
    "fsm.router.alias": {
        "en": "➕ *Add Router*\n\nStep 1/5: Enter a name (alias) for this router:\nExample: `home`, `office`, `vps`",
        "ru": "➕ *Добавить роутер*\n\nШаг 1/5: Введите псевдоним (название) роутера:\nПример: `дом`, `офис`, `vps`",
        "de": "➕ *Router hinzufügen*\n\nSchritt 1/5: Gib einen Namen (Alias) für den Router ein:\nBeispiel: `home`, `buero`, `vps`",
        "am": "➕ *Ավելացնել երթուղիչ*\n\nՔայլ 1/5: Մուտքագրեք անուն (alias) երթուղիչի համար:\nՕրինակ: `տուն`, `գրասենյակ`, `vps`",
    },
    "fsm.router.host": {
        "en": "Step 2/5: Enter router IP address:\nExample: `192.168.88.1`",
        "ru": "Шаг 2/5: Введите IP-адрес роутера:\nПример: `192.168.88.1`",
        "de": "Schritt 2/5: Router-IP-Adresse eingeben:\nBeispiel: `192.168.88.1`",
        "am": "Քայլ 2/5: Մուտքագրեք երթուղիչի IP-հասցեն:\nՕրինակ: `192.168.88.1`",
    },
    "fsm.router.user": {
        "en": "Step 3/5: Enter username:\nExample: `admin`",
        "ru": "Шаг 3/5: Введите имя пользователя:\nПример: `admin`",
        "de": "Schritt 3/5: Benutzernamen eingeben:\nBeispiel: `admin`",
        "am": "Քայլ 3/5: Մուտքագրեք օգտվողի անունը:\nՕրինակ: `admin`",
    },
    "fsm.router.pass": {
        "en": "Step 4/5: Enter password (send `-` for empty password):",
        "ru": "Шаг 4/5: Введите пароль (отправьте `-` если пустой):",
        "de": "Schritt 4/5: Passwort eingeben (sende `-` für kein Passwort):",
        "am": "Քայլ 4/5: Մուտքագրեք գաղտնաբառ (ուղարկեք `-` եթե դատարկ է):",
    },
    "fsm.router.pass_received": {
        "en": "🔒 Password received.\n\nStep 5/5: Enter API port (default: `8728`, SSL: `8729`, or send `-` for default):",
        "ru": "🔒 Пароль получен.\n\nШаг 5/5: Введите API порт (стандарт: `8728`, SSL: `8729`, или отправьте `-`):",
        "de": "🔒 Passwort erhalten.\n\nSchritt 5/5: API-Port eingeben (Standard: `8728`, SSL: `8729`, oder `-`):",
        "am": "🔒 Գաղտնաբառ ստացված է:\n\nՔայլ 5/5: Մուտքագրեք API պորտ (կանխ.: `8728`, SSL: `8729`, կամ ուղարկեք `-`):",
    },
    "fsm.router.connecting": {
        "en": "⏳ Connecting to router… please wait.",
        "ru": "⏳ Подключаюсь к роутеру… пожалуйста, подождите.",
        "de": "⏳ Verbinde mit Router… bitte warten.",
        "am": "⏳ Միանում եմ երթուղիչին… Խնդրում ենք սպասել:",
    },

    # ── Start / Welcome ────────────────────────────────────────────────────────
    "start.welcome": {
        "en": "👋 *Welcome, {name}!*{role}\n\n🖥 *MikroBot — WinBox in Telegram*\n\nFull RouterOS management from your phone.\nUse /add\\_router to connect your first MikroTik device,\nor tap the menu below.",
        "ru": "👋 *Добро пожаловать, {name}!*{role}\n\n🖥 *MikroBot — WinBox в Telegram*\n\nПолное управление RouterOS с телефона.\nИспользуйте /add\\_router для подключения,\nили нажмите на меню ниже.",
        "de": "👋 *Willkommen, {name}!*{role}\n\n🖥 *MikroBot — WinBox in Telegram*\n\nVollständige RouterOS-Verwaltung vom Smartphone.\nNutze /add\\_router um deinen ersten Router zu verbinden,\noder tippe auf das Menü.",
        "am": "👋 *Բարի գալուստ, {name}!*{role}\n\n🖥 *MikroBot — WinBox Telegram-ում*\n\nRouterOS-ի ամբողջական կառավարում ձեր հեռախոսից:\nՕգտագործեք /add\\_router ձեր առաջին MikroTik-ը միացնելու,\nկամ ընտրեք ստորև գտնվող ընտրացանկից:",
    },

    # ── Owner Bootstrap ────────────────────────────────────────────────────────
    "auth.owner_bootstrap": {
        "en": "👑 You are now the owner of this bot!",
        "ru": "👑 Вы теперь владелец этого бота!",
        "de": "👑 Du bist jetzt der Eigentümer dieses Bots!",
        "am": "👑 Դուք այժմ այս բոտի սեփականատերն եք:",
    },

    # ── Ping ──────────────────────────────────────────────────────────────────
    "tool.ping_prompt": {
        "en": "🏓 Enter hostname or IP to ping:",
        "ru": "🏓 Введите хостнейм или IP для пинга:",
        "de": "🏓 Hostnamen oder IP zum Pingen eingeben:",
        "am": "🏓 Մուտքագրեք hostname կամ IP-ն ping անելու համար:",
    },
    "tool.pinging": {
        "en": "🏓 Pinging `{target}`…",
        "ru": "🏓 Пингую `{target}`…",
        "de": "🏓 Pinge `{target}`…",
        "am": "🏓 Ping `{target}`…",
    },

    # ── Search ────────────────────────────────────────────────────────────────
    "tool.search_prompt": {
        "en": "🔍 *Global Search*\n\nEnter search term (IP, MAC, hostname, interface name):\nExample: `192.168.88` or `AA:BB` or `ether1`",
        "ru": "🔍 *Глобальный поиск*\n\nВведите запрос (IP, MAC, имя хоста, интерфейс):\nПример: `192.168.88` или `AA:BB` или `ether1`",
        "de": "🔍 *Globale Suche*\n\nSuchbegriff eingeben (IP, MAC, Hostname, Interface):\nBeispiel: `192.168.88` oder `AA:BB` oder `ether1`",
        "am": "🔍 *Գլոբալ որոնում*\n\nՄուտքագրեք որոնման հարցում (IP, MAC, hostname, interface):\nՕրինակ: `192.168.88` կամ `AA:BB` կամ `ether1`",
    },
    "tool.search_no_results": {
        "en": "🔍 No results for `{query}`",
        "ru": "🔍 Ничего не найдено для `{query}`",
        "de": "🔍 Keine Ergebnisse für `{query}`",
        "am": "🔍 Արդյունքներ չկան `{query}`-ի համար",
    },

    # ── Common words ──────────────────────────────────────────────────────────
    "word.or":          {"en": "or",    "ru": "или",    "de": "oder",   "am": "կամ"},
    "word.skip":        {"en": "skip",  "ru": "пропустить","de": "überspringen","am": "բաց թողնել"},
    "word.yes":         {"en": "Yes",   "ru": "Да",      "de": "Ja",     "am": "Այո"},
    "word.no":          {"en": "No",    "ru": "Нет",     "de": "Nein",   "am": "Ոչ"},
    "word.error":       {"en": "Error", "ru": "Ошибка",  "de": "Fehler", "am": "Սխալ"},
}

_FALLBACK = "en"


def t(key: str, lang: Optional[str] = None, **kwargs) -> str:
    """
    Get a translated string.

    Args:
        key: Translation key, e.g. "err.no_router"
        lang: Language code (en/ru/de/am). Falls back to "en".
        **kwargs: Format variables, e.g. t("fw.blocked", lang="ru", ip="1.2.3.4")
    """
    lang = lang or _FALLBACK
    entry = _STRINGS.get(key)
    if entry is None:
        return f"[missing:{key}]"
    text = entry.get(lang) or entry.get(_FALLBACK) or f"[missing:{key}:{lang}]"
    if kwargs:
        try:
            text = text.format(**kwargs)
        except KeyError:
            pass
    return text


def get_lang(user_id: int, sessions=None) -> str:
    """
    Get the user's configured language from session manager.
    Returns "en" if not set.
    """
    if sessions is None:
        return _FALLBACK
    try:
        return sessions.get_language(user_id) or _FALLBACK
    except Exception:
        return _FALLBACK
