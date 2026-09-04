import json
import pathlib

# Local cache & session files live next to the project root
CACHE_DIR = pathlib.Path(__file__).resolve().parent

SESSION_FILE = CACHE_DIR / "quiz_master_session.json"
SETTINGS_FILE = CACHE_DIR / "quiz_master_settings.json"


def save_session(refresh_token, uid, email):
    """Persist a refresh token locally so the user stays logged in on this
    device across app restarts."""
    try:
        SESSION_FILE.write_text(
            json.dumps({"refresh_token": refresh_token, "uid": uid, "email": email}),
            encoding="utf-8",
        )
    except Exception as e:
        print("Could not save session:", e)


def load_session():
    try:
        if SESSION_FILE.exists():
            return json.loads(SESSION_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        print("Could not load session:", e)
    return None


def clear_session():
    try:
        if SESSION_FILE.exists():
            SESSION_FILE.unlink()
    except Exception as e:
        print("Could not clear session:", e)


# Aliases with underscore for backward compatibility
_save_session = save_session
_load_session = load_session
_clear_session = clear_session


def load_settings():
    """Local, per-device app preferences (dark mode, question order, etc.)."""
    try:
        if SETTINGS_FILE.exists():
            return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        print("Could not load settings:", e)
    return {}


def save_settings(settings):
    try:
        SETTINGS_FILE.write_text(json.dumps(settings), encoding="utf-8")
    except Exception as e:
        print("Could not save settings:", e)


_load_settings = load_settings
_save_settings = save_settings


def record_quiz_completion_and_get_streak():
    """Calculates dynamic streak based on ISO date (YYYY-MM-DD)."""
    import datetime
    settings = load_settings()
    today = datetime.date.today()
    today_str = today.isoformat()
    last_date_str = settings.get("last_quiz_date")
    current_streak = int(settings.get("current_streak", 0))

    if last_date_str == today_str:
        streak = max(1, current_streak)
    elif last_date_str:
        try:
            last_date = datetime.date.fromisoformat(last_date_str)
            diff = (today - last_date).days
            if diff == 1:
                streak = current_streak + 1
            else:
                streak = 1
        except Exception:
            streak = 1
    else:
        streak = 1

    settings["last_quiz_date"] = today_str
    settings["current_streak"] = streak
    save_settings(settings)
    return streak


def get_current_streak():
    import datetime
    settings = load_settings()
    last_date_str = settings.get("last_quiz_date")
    current_streak = int(settings.get("current_streak", 0))
    if not last_date_str:
        return 0
    try:
        today = datetime.date.today()
        last_date = datetime.date.fromisoformat(last_date_str)
        diff = (today - last_date).days
        if diff in (0, 1):
            return current_streak
    except Exception:
        pass
    return 0

# ══════════════════════════════════════════════════════════════════════════
# Academic Clarity Design System Tokens — Light & Dark
# ══════════════════════════════════════════════════════════════════════════

LIGHT_THEME = {
    "BG_APP": "#f8f9ff", "BG_SURFACE": "#ffffff", "SURFACE_LOW": "#eff4ff",
    "SURFACE_MID": "#e5eeff", "SURFACE_HIGH": "#dce9ff", "PRIMARY": "#00685f",
    "PRIMARY_CONTAINER": "#008378", "PRIMARY_LIGHT": "#e6f5f3",
    "SECONDARY": "#4648d4", "SECONDARY_LIGHT": "#eef0ff",
    "TERTIARY": "#a35532", "TERTIARY_LIGHT": "#fff0eb",
    "TEXT_ON_SURFACE": "#0b1c30", "TEXT_MUTED": "#6d7a77", "TEXT_VARIANT": "#2d3a4b",
    "BORDER_COLOR": "#e2e8f0", "SUCCESS": "#00875a", "SUCCESS_CONTAINER": "#e6f8ef",
    "ERROR": "#ba1a1a", "ERROR_CONTAINER": "#ffdad6", "INPUT_TEXT_COLOR": "black",
}

DARK_THEME = {
    "BG_APP": "#0e1414", "BG_SURFACE": "#161f1f", "SURFACE_LOW": "#1c2727",
    "SURFACE_MID": "#212e2e", "SURFACE_HIGH": "#283939", "PRIMARY": "#4a9c8f",
    "PRIMARY_CONTAINER": "#3a7d72", "PRIMARY_LIGHT": "#1a2b28",
    "SECONDARY": "#9a9cff", "SECONDARY_LIGHT": "#242548",
    "TERTIARY": "#e5966b", "TERTIARY_LIGHT": "#3a2a20",
    "TEXT_ON_SURFACE": "#eef2f2", "TEXT_MUTED": "#9fb0ac", "TEXT_VARIANT": "#c7d0d0",
    "BORDER_COLOR": "#2c3a3a", "SUCCESS": "#5fd39a", "SUCCESS_CONTAINER": "#173229",
    "ERROR": "#ff8b80", "ERROR_CONTAINER": "#3a1613", "INPUT_TEXT_COLOR": "white",
}

BG_APP = LIGHT_THEME["BG_APP"]
BG_SURFACE = LIGHT_THEME["BG_SURFACE"]
SURFACE_LOW = LIGHT_THEME["SURFACE_LOW"]
SURFACE_MID = LIGHT_THEME["SURFACE_MID"]
SURFACE_HIGH = LIGHT_THEME["SURFACE_HIGH"]
PRIMARY = LIGHT_THEME["PRIMARY"]
PRIMARY_CONTAINER = LIGHT_THEME["PRIMARY_CONTAINER"]
PRIMARY_LIGHT = LIGHT_THEME["PRIMARY_LIGHT"]
SECONDARY = LIGHT_THEME["SECONDARY"]
SECONDARY_LIGHT = LIGHT_THEME["SECONDARY_LIGHT"]
TERTIARY = LIGHT_THEME["TERTIARY"]
TERTIARY_LIGHT = LIGHT_THEME["TERTIARY_LIGHT"]
TEXT_ON_SURFACE = LIGHT_THEME["TEXT_ON_SURFACE"]
TEXT_MUTED = LIGHT_THEME["TEXT_MUTED"]
TEXT_VARIANT = LIGHT_THEME["TEXT_VARIANT"]
BORDER_COLOR = LIGHT_THEME["BORDER_COLOR"]
SUCCESS = LIGHT_THEME["SUCCESS"]
SUCCESS_CONTAINER = LIGHT_THEME["SUCCESS_CONTAINER"]
ERROR = LIGHT_THEME["ERROR"]
ERROR_CONTAINER = LIGHT_THEME["ERROR_CONTAINER"]
INPUT_TEXT_COLOR = LIGHT_THEME["INPUT_TEXT_COLOR"]


def apply_theme(dark: bool):
    """Reassigns every color token above, in place, as module globals."""
    globals().update(DARK_THEME if dark else LIGHT_THEME)


_apply_theme = apply_theme

FONT_FAMILY = "Segoe UI"
LETTERS = ["A", "B", "C", "D", "E", "F"]
