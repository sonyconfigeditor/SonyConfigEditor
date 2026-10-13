"""Sony Config Editor - reads, converts and writes Sony Cinecam configuration files.

Currently supported: PXW-FS7 / PXW-FS7M2 SCENE files (*.SCENE) and ALL files (*.ALL).

Requirements: Python 3.10 or newer with Tkinter (Windows/macOS: included in the python.org installer;
Debian/Ubuntu: sudo apt install python3-tk; Fedora: sudo dnf install python3-tkinter) and one extra library:

    pip install customtkinter

Only to build an executable (see build_exe.bat for Windows, build_app.sh for Linux/macOS):

    pip install pyinstaller
"""

import argparse
import colorsys
import contextlib
import functools
import hashlib
import locale
import os
import re
import json
import sys
import time
import tkinter as tk
import tkinter.font as tkfont
from dataclasses import dataclass, field
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk
from customtkinter.windows.widgets.appearance_mode import AppearanceModeTracker

_version = "0.1.0"
_date = "2026-10-07"

APP_NAME = "Sony Config Editor"
CONTACT_EMAIL = "sonyconfigeditor@gmail.com"
SCENE_MAGIC = "V01.00^^^^^^^^^"
SCENE_NAME_WIDTH = 17  # name field incl. '^' padding
SCENE_FOOTER = "%%%%"
CHANGED_COLOR = "#f0ad4e"
WARNING_COLOR = "#e57373"
# collapsible blocks of the parameter table; the block of a parameter comes from "group" in the parameter database
GROUPS = [("video", "Video"), ("audio", "Audio"), ("misc", "Miscellaneous"), ("unknown", "Unknown")]
GROUP_ICONS = {"video": "🎬", "audio": "🔊", "misc": "⚙", "unknown": "❓"}     # Unicode symbols (no image files needed), shown in the block header and the jump buttons
DEFAULT_COLLAPSED = {"unknown"}
# order of the camera-menu sub-groups inside a block (parameters get "subgroup" in the databases; others: "Other")
SUBGROUP_ORDER = [
    "System › Base Setting", "System › Codec / Rec Format", "System › Rec Format (companion values)",
    "Camera › ISO/Gain/EI", "Camera › ND Filter", "Camera › Auto Exposure", "Paint › Black", "Paint › Gamma", "Paint › Black Gamma", "Paint › Knee / White Clip", "Paint › White Clip", "Paint › Detail", "Paint › Skin Detail", "Paint › Detail / Aperture", "Paint › Matrix", "Paint › Offset White",
    "White", "Recording › S&Q Motion", "Audio › Input", "VF › Zebra / Marker", "File › Clip",
]
CATEGORIES = ("System", "Camera", "Paint")      # main menus of the camera with their own collapsible heading above their sub-groups ("Paint › Gamma", "Camera › ND Filter", ...)
FILTER_DELAY_MS = 150
BASE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))  # _MEIPASS: bundled by PyInstaller
# SCENE and ALL files share the container format but use different parameter IDs -> one database per file type
PARAM_DB_FILES = {"scene": BASE_DIR / "scene_parameters.json", "all": BASE_DIR / "all_parameters.json"}
PARAM_DB_FILE = PARAM_DB_FILES["scene"]
TEMPLATE_DIR = BASE_DIR / "templates"
DEFAULTS_FILE = BASE_DIR / "defaults.json"   # neutral values for "Neu" (documented defaults of the manual, no factory dump)
ID_MAP_FILE = BASE_DIR / "id_map.json"   # SCENE id -> ALL id per model, for switching between the two file types
MODELS = ("PXW-FS7", "PXW-FS7M2")
# Supported file types by extension.
FILE_TYPES = {".scene": "Sony SCENE File", ".all": "Sony ALL File"}
# ALL files use the same container (MD5 line, V01.00, name, model, ID=value, %%%%) as SCENE files
LOADERS = {".scene": lambda path: SceneFile.load(path), ".all": lambda path: SceneFile.load(path)}
HISTORY_LIMIT = 200
COALESCE_SECONDS = 1.0  # consecutive edits of the same field within this time form one undo step


PARAM_DB_ERRORS: dict[str, str] = {}   # kind -> reason, while a parameter database could not be read (shown to the user)


def _read_param_file(kind: str) -> dict:
    """Read a parameter database. A file that is just being written is retried; a real failure is remembered, never silent."""
    error = ""
    for _attempt in range(6):
        try:
            data = json.loads(PARAM_DB_FILES[kind].read_text(encoding="utf-8"))
            PARAM_DB_ERRORS.pop(kind, None)
            return data
        except (OSError, ValueError) as exc:
            error = f"{PARAM_DB_FILES[kind].name}: {exc}"
            time.sleep(0.25)
    PARAM_DB_ERRORS[kind] = error
    return {}


def load_param_db(kind: str = "scene") -> dict:
    return translate_db({k: v for k, v in _read_param_file(kind).items() if not k.startswith("_")})


def load_param_locks(kind: str) -> list:
    """Sub-groups that are greyed out while a condition holds (see _locks in the database)."""
    return translate_db(_read_param_file(kind).get("_locks", []))


def param_db_models(kind: str) -> list | None:
    """Models a parameter database was derived for (None = no restriction)."""
    return _read_param_file(kind).get("_models")


def new_scene_params(model: str) -> dict | None:
    """Parameters of a new SCENE file: the model's template plus the neutral values of defaults.json (None without template)."""
    params = SceneSession._template(model, "scene")
    if params is None:
        return None
    params = dict(params)
    try:
        neutral = json.loads(DEFAULTS_FILE.read_text(encoding="utf-8")).get("scene", {})
    except (OSError, ValueError):
        neutral = {}
    for pid, how in neutral.items():
        if pid.startswith("_") or pid not in params:
            continue
        parts = params[pid].split(",")
        if how == "zeros":
            params[pid] = ",".join("0" for _ in parts)
        elif how == "zeros_keep_first":
            params[pid] = ",".join([parts[0]] + ["0"] * (len(parts) - 1))
        else:
            params[pid] = how
    return params


SETTINGS_NAME = "settings.json"
MAX_SETTINGS_BYTES = 16 * 1024
SOURCE_LANGUAGE = "en"      # the English texts in the code are the keys of the catalogs in translations/<code>.json
LANG = SOURCE_LANGUAGE      # active language
TRANSLATIONS: dict[str, dict[str, str]] = {}
DEFAULT_LANGUAGE = SOURCE_LANGUAGE      # used when neither a saved choice nor the operating-system language has a catalog
USE_SAVED_LANGUAGE = True   # the tests switch it off and run in the source language


def load_translations() -> None:
    TRANSLATIONS.clear()
    folder = BASE_DIR / "translations"
    for path in sorted(folder.glob("*.json")):
        try:
            TRANSLATIONS[path.stem] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass


def available_languages() -> dict[str, str]:
    """{code: name} of English (source) and every catalog in translations/."""
    names = {SOURCE_LANGUAGE: "English"}
    for code, catalog in TRANSLATIONS.items():
        names[code] = catalog.get("_name", code)
    return names


def tr(text: str) -> str:
    """Text in the active language (unknown texts and the source language stay as they are)."""
    if LANG == SOURCE_LANGUAGE or not text:
        return text
    return TRANSLATIONS.get(LANG, {}).get(text, text)


def tr_all(text: str) -> list[str]:
    """The text in every language (to size widgets for the longest one)."""
    return [text] + [catalog.get(text, text) for catalog in TRANSLATIONS.values()]


_LAZY = {"depth": 0, "real": None}


@contextlib.contextmanager
def lazy_layout():
    """Within the block, update_idletasks does nothing. Every customtkinter widget calls it when it redraws, and it flushes ALL pending
    layout work of the window: with ~1000 rows each configure() would lay out the whole table. The layout happens once, when Tk is idle
    (or at the next explicit update). Can be nested."""
    if _LAZY["depth"] == 0:
        _LAZY["real"] = tk.Misc.update_idletasks
        tk.Misc.update_idletasks = lambda _self: None
    _LAZY["depth"] += 1
    try:
        yield
    finally:
        _LAZY["depth"] -= 1
        if _LAZY["depth"] == 0:
            tk.Misc.update_idletasks = _LAZY["real"]


def lazy(method):
    """Decorator: run a method that changes many widgets with lazy_layout()."""
    @functools.wraps(method)
    def wrapper(*args, **kwargs):
        with lazy_layout():
            return method(*args, **kwargs)
    return wrapper


def quiet_scrollbar(scrollbar) -> None:
    """customtkinter's scrollbar flushes ALL pending layout work (canvas.update_idletasks) at every redraw, and Tk redraws it at
    every change of the scroll region: with ~1000 rows that is a full layout of the window per change. Draw without the flush;
    the layout still happens, once, when Tk is idle."""
    original = scrollbar._draw

    def draw(no_color_updates=False):
        canvas = scrollbar._canvas
        canvas.update_idletasks = lambda: None       # instance attribute shadows the method for the duration of the draw
        try:
            original(no_color_updates)
        finally:
            del canvas.update_idletasks

    scrollbar._draw = draw


def tr_status(status: str) -> str:
    """Decoding status (likely / hypothesis) in the active language."""
    return {"likely": tr("likely"), "hypothesis": tr("hypothesis")}.get(status, status)


def tr_label(text: str) -> str:
    """Translate a label; a trailing ' – assumption' is translated separately (the label itself is mostly a format name)."""
    suffix = " – assumption"
    if text.endswith(suffix):
        return tr_label(text[:-len(suffix)]) + tr(suffix)
    out = tr(text)
    if out == text and LANG != SOURCE_LANGUAGE:      # generated format labels: replace single words (catalog entry "_label_words")
        for word, replacement in TRANSLATIONS.get(LANG, {}).get("_label_words", {}).items():
            out = re.sub(r"\b" + re.escape(word) + r"\b", replacement, out)
    return out


def translate_db(node):
    """Copy of a parameter database with the texts a user reads (notes, reasons, messages, labels, choices) in the active language."""
    if LANG == SOURCE_LANGUAGE:
        return node
    if isinstance(node, dict):
        out = {}
        for key, value in node.items():
            if key in ("note", "reason", "text", "message", "message_4k", "message_2k") and isinstance(value, str):
                out[key] = tr(value)
            elif key == "label" and isinstance(value, str):
                out[key] = tr_label(value)
            elif key == "choices" and isinstance(value, dict):
                out[key] = {k: tr_label(v) if isinstance(v, str) else v for k, v in value.items()}
            elif key in ("evidence", "values", "match", "set", "when", "requires") or not isinstance(value, (dict, list)):
                out[key] = value
            else:
                out[key] = translate_db(value)
        return out
    if isinstance(node, list):
        return [translate_db(v) for v in node]
    return node


WINDOWS_LANGUAGE_NAMES = {"german": "de", "english": "en", "spanish": "es", "italian": "it", "french": "fr", "portuguese": "pt"}


def match_language(name: str, available) -> str | None:
    """Catalog code for an operating-system locale name such as 'pt_BR', 'fr_CA', 'de-DE' or 'Portuguese_Brazil' (None if there is none).
    Portuguese: Brazil (pt_BR) has its own catalog, every other region and the bare 'pt' use the European one ('pt') if it exists
    (the bare 'pt' without a region goes to Brazil, which has far more speakers)."""
    if not name:
        return None
    name = name.replace("-", "_")
    base, _sep, region = name.partition("_")
    base = WINDOWS_LANGUAGE_NAMES.get(base.lower(), base.lower())
    region = region.split(".")[0].upper()
    if region in ("BRAZIL", "BRASIL"):
        region = "BR"
    if base == "pt":
        if region == "BR" or not region:
            return "pt_BR" if "pt_BR" in available else ("pt" if "pt" in available else None)
        return "pt" if "pt" in available else ("pt_BR" if "pt_BR" in available else None)
    if name in available:
        return name
    return base if base in available else None


def initial_language() -> str:
    """Saved choice, else the language of the operating system if there is a catalog for it, else English."""
    code = None
    if USE_SAVED_LANGUAGE:
        try:
            code = load_settings().get("language")
        except (AttributeError, TypeError):
            code = None
        code = code if isinstance(code, str) else None
        if code is None:
            try:
                code = match_language(locale.getlocale()[0] or "", available_languages())
            except (ValueError, TypeError):
                code = None
    return code if code in available_languages() else DEFAULT_LANGUAGE if DEFAULT_LANGUAGE in available_languages() else SOURCE_LANGUAGE


def init_language() -> None:
    """Load the catalogs and choose the language (idempotent)."""
    global LANG
    load_translations()
    LANG = initial_language() if USE_SAVED_LANGUAGE else LANG


def settings_path() -> Path:
    """Per-user settings file in the usual place of the operating system (no registry, always writable):
    Windows %APPDATA%, macOS ~/Library/Application Support, Linux $XDG_CONFIG_HOME or ~/.config.
    Portable mode: a settings.json next to the program (or the EXE) is used instead."""
    program_dir = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
    if (program_dir / SETTINGS_NAME).is_file():
        return program_dir / SETTINGS_NAME
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "SonyConfigEditor" / SETTINGS_NAME


def load_settings() -> dict:
    """Saved settings; anything unreadable, oversized or of the wrong type is ignored (the file is user-editable input)."""
    if not USE_SAVED_LANGUAGE:
        return {}
    try:
        path = settings_path()
        if path.stat().st_size > MAX_SETTINGS_BYTES:
            return {}
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError):      # RecursionError: deeply nested brackets in a small file
        return {}
    return data if isinstance(data, dict) else {}


def is_safe_dir(text: str) -> bool:
    """Folder from the settings file: plain local path, no control characters, must exist."""
    if len(text) >= 1024 or any(ord(c) < 32 for c in text) or text.startswith((chr(92) * 2, "//")):
        return False
    try:
        return Path(text).is_dir()
    except (OSError, ValueError):
        return False


def save_settings(**changes) -> None:
    """Merge the changes into the settings file (atomic write); failures are ignored, the program works without persistence."""
    if not USE_SAVED_LANGUAGE:
        return
    data = load_settings()
    data.update(changes)
    try:
        path = settings_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(temp, path)
    except OSError:
        pass


def save_language(code: str) -> None:
    save_settings(language=code)


APPEARANCES = ("system", "light", "dark")      # customtkinter appearance modes: follow Windows / day / night
DEFAULT_APPEARANCE = "dark"


def initial_appearance() -> str:
    """Saved choice (the settings file is user-editable input: anything else is ignored), else night mode."""
    mode = load_settings().get("appearance")
    return mode if isinstance(mode, str) and mode in APPEARANCES else DEFAULT_APPEARANCE


SHOW_RAW_VALUES = True      # IDs and raw values in brackets behind the decoded text (the tests switch it off to keep their texts short)
RAW_COLOR = "#8a8a8a"


def with_raw(label: str, raw) -> str:
    """Decoded text plus the raw value in brackets: 'HG2 4600G30 (1)'."""
    return f"{label} ({raw})" if SHOW_RAW_VALUES else label   # (the labels of the databases are translated when the database is loaded)


def index_label(label: str) -> str:
    """Format list entries start with their index ('9 – 1920×1080 59.94p'): shown as '1920×1080 59.94p (9)'."""
    if SHOW_RAW_VALUES:
        m = re.match(r"^(\d+) – (.*)$", label)
        if m:
            return f"{m.group(2)} ({m.group(1)})"
    return label


def load_id_map() -> dict:
    """{model: {scene id: all id}}"""
    try:
        data = json.loads(ID_MAP_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {m: v["scene_to_all"] for m, v in data.items() if not m.startswith("_")}


def load_transfer_rules() -> dict:
    try:
        rules = json.loads(PARAM_DB_FILE.read_text(encoding="utf-8")).get("_transfer", {})
    except (OSError, ValueError):
        rules = {}
    return {"none": set(rules.get("none", [])), "first": set(rules.get("first", [])), "maps": rules.get("value_maps", {})}


# --------------------------------------------------------------------------- #
# SCENE file model
# --------------------------------------------------------------------------- #
class SceneFileError(Exception):
    pass


# Limits for files from outside: real camera files are below 4 KB, 420 lines, 56 values per ID and 153 characters per value.
MAX_FILE_BYTES = 64 * 1024
MAX_LINES = 2000
MAX_VALUE_CHARS = 512
MAX_VALUE_FIELDS = 128
MAX_NAME_CHARS = 64
ID_PATTERN = re.compile(r"\d{5}")
MAGIC_PATTERN = re.compile(r"V\d{2}\.\d{2}\^*")
MODEL_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._ -]{0,31}")
VALUE_PATTERN = re.compile(r"[ -~ -ÿ]*")      # printable latin-1, no control characters


@dataclass
class SceneFile:
    name: str = ""
    model: str = ""
    params: dict = field(default_factory=dict)  # id (str, 5 digits) -> raw value
    checksum_ok: bool = True
    path: Path | None = None
    number: str = ""   # file number 000-999 (the file name NNN.SCENE / NNN.ALL), empty if the file name is not a number

    @staticmethod
    def _checksum(body: str) -> str:
        return hashlib.md5(body.encode("latin-1")).hexdigest()

    @classmethod
    def parse(cls, text: str, path: Path | None = None) -> "SceneFile":
        if len(text) > MAX_FILE_BYTES:
            raise SceneFileError(tr("File too large for a SCENE file."))
        text = text.replace("\r\n", "\n")
        lines = text.split("\n")
        if len(lines) < 5:
            raise SceneFileError(tr("File too short for a SCENE file."))
        if len(lines) > MAX_LINES:
            raise SceneFileError(tr("File has too many lines for a SCENE file."))
        stored_sum, magic, name_line, model = lines[0], lines[1], lines[2], lines[3]
        if not MAGIC_PATTERN.fullmatch(magic):
            raise SceneFileError(tr("Unknown format: {magic}").format(magic=repr(magic[:40])))
        if len(name_line) > MAX_NAME_CHARS or not VALUE_PATTERN.fullmatch(name_line):
            raise SceneFileError(tr("Invalid name in the file."))
        if not MODEL_PATTERN.fullmatch(model.strip()):
            raise SceneFileError(tr("Invalid model entry in the file."))
        body = text.split("\n", 1)[1]
        scene = cls(
            name=name_line.rstrip("^"),
            model=model.strip(),
            checksum_ok=stored_sum.strip().lower() == cls._checksum(body),
            path=path,
        )
        for line in lines[4:]:
            if line.startswith("%%%%") or not line.strip():
                continue
            key, sep, value = line.partition("=")
            key = key.strip()
            if not sep or not ID_PATTERN.fullmatch(key):
                raise SceneFileError(tr("Invalid line: {line}").format(line=repr(line[:40])))
            if key in scene.params:
                raise SceneFileError(tr("ID {id} occurs more than once.").format(id=key))
            if len(value) > MAX_VALUE_CHARS or value.count(",") >= MAX_VALUE_FIELDS or not VALUE_PATTERN.fullmatch(value):
                raise SceneFileError(tr("Invalid value for ID {id}.").format(id=key))
            scene.params[key] = value
        return scene

    @classmethod
    def load(cls, path: Path) -> "SceneFile":
        with open(path, "rb") as handle:
            data = handle.read(MAX_FILE_BYTES + 1)      # never read more than the limit, whatever the file claims
        if len(data) > MAX_FILE_BYTES:
            raise SceneFileError(tr("File too large for a SCENE file."))
        return cls.parse(data.decode("latin-1"), Path(path))

    def serialize(self) -> str:
        body_lines = [
            SCENE_MAGIC,
            self.name[: SCENE_NAME_WIDTH - 1].ljust(SCENE_NAME_WIDTH, "^"),
            self.model,
            *(f"{k}={v}" for k, v in sorted(self.params.items())),
            SCENE_FOOTER,
        ]
        body = "\n".join(body_lines) + "\n"
        return f"{self._checksum(body)}\n{body}"

    def save(self, path: Path | None = None) -> None:
        target = Path(path or self.path)
        target.write_bytes(self.serialize().encode("latin-1"))
        self.path = target
        self.checksum_ok = True


class SceneSession:
    """Holds one parameter set per file type (SCENE / ALL) and camera model, so switching back and forth loses nothing.

    store[key]    full parameter set of that profile (key = "<kind>:<model>", incl. values the other profile cannot express)
    baseline[key] state when the profile was last entered; only differences to it are carried over when leaving,
                  so values the other profile cannot express (e.g. BT.2020, ALL-only settings) survive a round trip.
    Between SCENE and ALL only the IDs of id_map.json are carried over (same value shape required).
    """

    def __init__(self, scene: SceneFile, param_db: dict, rules: dict, kind: str = "scene"):
        self.scene = scene
        self.db = param_db
        self.rules = rules
        self.kind = kind
        self.model = scene.model
        self.id_maps = load_id_map()
        self.store = {self.key: scene.params}
        self.baseline = {self.key: dict(scene.params)}

    @property
    def key(self) -> str:
        return f"{self.kind}:{self.model}"

    @staticmethod
    def _template(model: str, kind: str = "scene") -> dict | None:
        path = TEMPLATE_DIR / f"{model}.{kind.upper()}"
        try:
            return SceneFile.load(path).params
        except (OSError, SceneFileError):
            return None

    def can_switch_kind(self) -> bool:
        return self.model in self.id_maps and all(self._template(self.model, k) is not None for k in ("scene", "all"))

    def _valid_for(self, key: str, value: str, model: str) -> bool:
        spec = (self.db.get(key) or {}).get("widget") or {}
        parts = [p.strip() for p in value.split(",")]
        for field in spec.get("fields", []):
            idx = field.get("index")
            if idx is None or idx >= len(parts):
                continue
            allowed = field.get("only_models", {}).get(parts[idx])
            if allowed is not None and model not in allowed:
                return False
        return True

    def _scene_id(self, key: str) -> str:
        """Transfer rules are written with SCENE IDs: translate an ID of an ALL file (IDs without a SCENE equivalent stay as they are)."""
        if self.kind == "scene":
            return key
        reverse = {a: sc for sc, a in self.id_maps.get(self.model, {}).items()}
        return reverse.get(key, key)

    @staticmethod
    def mapped_value(rules: dict, rule_key: str, value: str, src_model: str, dst_model: str) -> str | None:
        """Value of another model for the same menu position (value_maps, e.g. Master Black), None if not known."""
        return rules.get("maps", {}).get(rule_key, {}).get(f"{src_model}>{dst_model}", {}).get(value.strip())

    def _carry(self, key: str, value: str, target: dict, model: str) -> bool:
        """Copy one value into target if the rules allow it. Returns True if copied."""
        rule_key = self._scene_id(key)
        if key in target:
            mapped = self.mapped_value(self.rules, rule_key, value, self.model, model)
            if mapped is not None:
                target[key] = mapped
                return True
        if rule_key in self.rules["none"] or key not in target:
            return False
        src, dst = value.split(","), target[key].split(",")
        if rule_key in self.rules["first"]:
            dst[0] = src[0]
            new = ",".join(dst)
        elif len(src) == len(dst):
            new = value
        else:
            return False
        if not self._valid_for(key, new, model):
            return False
        target[key] = new
        return True

    def _normalize(self, target: dict):
        """Do what the camera does by itself with the carried values: White Clip is switched off with S-Log2/S-Log3 (FS7M2 test, 2026-10-08)."""
        if self.kind == "scene":
            slog = target.get("00022") == "1" or target.get("00143") == "1"
            if slog and "00068" in target:
                target["00068"] = "0"
        else:
            flags = [target.get(k) for k in ("00039", "00041", "00190")]
            slog3 = None not in flags and all(f == "0" for f in flags) and target.get("00044") == "0"
            if (target.get("00044") == "1" or slog3) and "00125" in target:
                target["00125"] = "0"

    def switch(self, target_model: str) -> dict:
        """Switch the camera model (SCENE only). Returns counts for display."""
        source_key, target_key = self.key, f"{self.kind}:{target_model}"
        report = {"copied": 0, "kept": 0, "hidden": 0, "added": 0, "template": False}
        if target_model == self.model:
            return report
        src = self.store[source_key]
        edited = {k: v for k, v in src.items() if self.baseline[source_key].get(k) != v}
        if target_key in self.store:
            target = self.store[target_key]
            candidates = edited
        else:
            tpl = self._template(target_model, self.kind)
            report["template"] = tpl is not None
            target = dict(tpl) if tpl is not None else dict(src)
            candidates = src
        for key, value in candidates.items():
            if key not in target:
                continue
            if self._carry(key, value, target, target_model):
                report["copied"] += 1
            else:
                report["kept"] += 1  # model specific / other shape / invalid: target keeps its own value
        report["hidden"] = sum(1 for k in src if k not in target)
        report["added"] = sum(1 for k in target if k not in src)
        self._normalize(target)
        self.store[target_key] = target
        self.baseline[target_key] = dict(target)
        self.model = target_model
        self.scene.model = target_model
        self.scene.params = target
        return report

    def _kind_map(self, source_kind: str, target_kind: str) -> dict:
        scene_to_all = self.id_maps.get(self.model, {})
        if source_kind == "scene":
            return dict(scene_to_all)
        return {a: s for s, a in scene_to_all.items()}

    def switch_kind(self, target_kind: str) -> dict:
        """Switch between SCENE and ALL. Only mapped IDs are carried over; everything else stays in its own profile."""
        report = {"copied": 0, "unmapped": 0, "template": False}
        if target_kind == self.kind or not self.can_switch_kind():
            return report
        source_key, target_key = self.key, f"{target_kind}:{self.model}"
        src = self.store[source_key]
        mapping = self._kind_map(self.kind, target_kind)
        if target_key in self.store:
            target = self.store[target_key]
            candidates = {k: v for k, v in src.items() if self.baseline[source_key].get(k) != v}
        else:
            target = dict(self._template(self.model, target_kind))
            report["template"] = True
            candidates = src
        for key, value in candidates.items():
            tid = mapping.get(key)
            if tid is not None and tid in target and len(value.split(",")) == len(target[tid].split(",")):
                target[tid] = value
                report["copied"] += 1
            elif tid is None:
                report["unmapped"] += 1
        self.store[target_key] = target
        self.baseline[target_key] = dict(target)
        self.kind = target_kind
        self.scene.params = target
        return report


def import_candidates(src: SceneFile, src_kind: str, dst_params: dict, dst_kind: str, dst_model: str,
                      dst_db: dict, rules: dict) -> tuple[list[dict], str]:
    """Which values of file `src` can be imported into the current file (any combination of SCENE/ALL and Mk1/Mk2).

    Same type and model: IDs are identical. Otherwise the values go through the SCENE ID space (id_map.json for ALL <-> SCENE,
    transfer rules and `only_models` for model differences). Returns (items, reason); reason is set if nothing can be mapped.
    Item: {"tid", "name", "known", "cur", "new", "differs"}; values that need a different shape are left out.
    """
    id_maps = load_id_map()
    same = src_kind == dst_kind and src.model == dst_model
    if same:
        pairs = [(k, k, k) for k in src.params if k in dst_params]
    else:
        if src_kind == "scene":
            to_scene = {k: k for k in src.params}
        elif src.model in id_maps:
            to_scene = {a: sc for sc, a in id_maps[src.model].items()}
        else:
            return [], tr("There is no mapping to SCENE IDs for ALL files of the {model} yet.").format(model=src.model)
        if dst_kind == "scene":
            from_scene = {k: k for k in dst_params}
        elif dst_model in id_maps:
            from_scene = dict(id_maps[dst_model])
        else:
            return [], tr("There is no mapping to SCENE IDs for ALL files of the {model} yet.").format(model=dst_model)
        pairs = [(sid, to_scene[sid], from_scene[to_scene[sid]]) for sid in src.params
                 if sid in to_scene and to_scene[sid] in from_scene and from_scene[to_scene[sid]] in dst_params]
    checker = SceneSession(SceneFile(model=dst_model, params=dict(dst_params)), dst_db, rules, dst_kind)
    items = []
    for sid, scene_id, tid in pairs:
        value, cur = src.params[sid], dst_params[tid]
        src_parts, cur_parts = value.split(","), cur.split(",")
        if not same:
            mapped = SceneSession.mapped_value(rules, scene_id, value, src.model, dst_model) if src.model != dst_model else None
            if mapped is not None:
                info = dst_db.get(tid)
                items.append({"tid": tid, "name": info["name"] if info else "", "known": info is not None, "cur": cur, "new": mapped,
                              "differs": mapped != cur})
                continue
            if scene_id in rules["none"]:
                continue
            if scene_id in rules["first"]:
                cur_parts[0] = src_parts[0]
                src_parts = cur_parts
                value = ",".join(src_parts)
        if len(src_parts) != len(cur_parts):
            continue
        if not same and src.model != dst_model and not checker._valid_for(tid, value, dst_model):
            continue
        info = dst_db.get(tid)
        items.append({"tid": tid, "name": info["name"] if info else "", "known": info is not None, "cur": cur, "new": value,
                      "differs": value != cur})
    items.sort(key=lambda i: i["tid"])
    return items, ""


def raw_to_step(raw: int, unit: float, sign: int = 1, trunc: bool = False) -> int:
    """Menu step of a raw value. With trunc the raw value may lie between two steps (the wheel is finer than the display): the camera then
    shows the step cut towards zero (a small tolerance keeps values we wrote ourselves, step x unit rounded, on their step)."""
    x = sign * raw / unit
    if trunc:
        return int(abs(x) + 0.05) * (1 if x >= 0 else -1)
    return round(x)


def clean_name(name: str) -> str:
    """Menu name without the trailing explanations of the database names ('(menu step -99..+99)', '(?)')."""
    previous = None
    while previous != name:
        previous = name
        name = re.sub(r"\s*\([^()]*\)\s*$", "", name).strip()
    return name or "?"


def diff_path(tid: str, info: dict | None, full_name: bool = False) -> str:
    """Readable path of a parameter in the camera menu, for example 'Paint/White Clip/White Clip Level' (no IDs for known parameters)."""
    if not info:
        return f"{tr('Unknown')}/ID {tid}"
    sub = info.get("subgroup", "Other").replace(" › ", "/")
    return f"{sub}/{info['name'] if full_name else clean_name(info['name'])}"


def describe_value(info: dict | None, raw: str, params: dict) -> str:
    """Readable text of a raw value (choice names, steps, percentages ...); the raw text if the value cannot be decoded."""
    widget = (info or {}).get("widget")
    if not widget:
        return raw
    parts = [x.strip() for x in raw.split(",")]
    kind = widget.get("type")
    try:
        if kind == "choice":
            return widget["choices"].get(parts[0], raw)
        if kind == "checkbox":
            return tr("On") if parts[widget.get("index", 0)] == widget.get("on", "1") else tr("Off")
        if kind == "counter":
            number = int(parts[widget["index"]])
            scale = widget.get("scale")
            text = f"{number * scale:.{widget.get('decimals', 2)}f}" if scale else str(number)
            return f"{text} {widget['unit']}".strip() if widget.get("unit") else text
        if kind == "fields":
            return ", ".join(f["choices"].get(parts[f["index"]], parts[f["index"]]) if "choices" in f else parts[f["index"]] for f in widget["fields"])
        if kind == "stepfields":
            out = []
            for f in widget["fields"]:
                value = parts[f["index"]]
                if "choices" in f:
                    text = f["choices"].get(value, value)
                else:
                    lo, hi = f["range"] if "range" in f else widget["range"]
                    step = max(lo, min(hi, raw_to_step(int(value), f.get("unit", widget["unit"]), f.get("sign", 1), f.get("trunc", False))))
                    text = f"{step:+d}" if lo < 0 else str(step)
                out.append(f"{f['label']} {text}" if len(widget["fields"]) > 1 and "choices" not in f else text)
            return ", ".join(out)
        if kind == "axis_pairs":
            axes, unit = widget["axes"], widget["unit"]
            out = []
            for i, axis in enumerate(axes):
                hue, sat = round(int(parts[widget["hue_start"] + i]) / unit), round(int(parts[widget["sat_start"] + i]) / unit)
                if hue or sat:
                    out.append(f"{axis} {hue:+d}/{sat:+d}")
            return "; ".join(out) or tr("all 0")
        if kind == "derived":
            for option in widget["options"]:
                if all(params.get(pid, "").split(",")[int(field)].strip() == want for pid, fields in option["match"].items() for field, want in fields.items()):
                    return option["label"]
        if kind == "multichoice":
            texts = []
            for selector in widget["selectors"]:
                for option in selector["options"]:
                    if all(parts[int(field)] == want for field, want in option["values"].items()):
                        texts.append(option["label"])
                        break
            if texts:
                return " / ".join(texts)
    except (KeyError, IndexError, ValueError, TypeError):
        pass
    return raw


def build_diff_rows(items: list[dict], cur_params: dict, db: dict) -> list[dict]:
    """Rows of the difference view in camera-menu order: {"path", "left", "right", "differs", "tid"} (parts of combined rows are left out)."""
    new_params = dict(cur_params)
    for item in items:
        new_params[item["tid"]] = item["new"]
    group_rank = {g: i for i, (g, _t) in enumerate(GROUPS)}

    def order(item):
        info = db.get(item["tid"])
        sub = info.get("subgroup", "Other") if info else ""
        return (group_rank.get(info.get("group", "misc") if info else "unknown", 9),
                SUBGROUP_ORDER.index(sub) if sub in SUBGROUP_ORDER else len(SUBGROUP_ORDER), sub, info.get("order", 99) if info else 99, item["tid"])

    rows = []
    for item in sorted(items, key=order):
        info = db.get(item["tid"])
        if info and info.get("covered_by"):
            continue
        rows.append({"path": diff_path(item["tid"], info), "tid": item["tid"], "differs": item["differs"],
                     "left": describe_value(info, item["cur"], cur_params), "right": describe_value(info, item["new"], new_params)})
    seen: set[str] = set()
    for row in rows:          # a second parameter with the same short path: full name first, the ID as the last resort
        if row["path"] in seen:
            row["path"] = diff_path(row["tid"], db.get(row["tid"]), full_name=True)
            if row["path"] in seen:
                row["path"] += f" [ID {row['tid']}]"
        seen.add(row["path"])
    return rows


# --------------------------------------------------------------------------- #
# GUI
# --------------------------------------------------------------------------- #
class ImportDialog(ctk.CTkToplevel):
    """List of importable values with check boxes (select all / none / invert). `result` = chosen items or None."""

    def __init__(self, app, items: list[dict], source_text: str, invisible: bool = False):
        super().__init__(app)
        if invisible:
            self.attributes("-alpha", 0)   # tests: never show a window to the user (set before anything is built)
        self.app, self.items, self.result, self.source_text = app, items, None, source_text
        self.title(tr("Import from {source}").format(source=source_text))
        self.geometry(f"{int(app.winfo_width() * 0.85)}x{int(app.winfo_height() * 0.9)}")
        self.transient(app)
        c = app._c
        self.vars = [tk.BooleanVar(value=i["known"] and i["differs"]) for i in items]
        top = ctk.CTkFrame(self)
        top.pack(fill="x", padx=8, pady=(8, 2))
        self.var_search = tk.StringVar()
        ctk.CTkLabel(top, text=tr("Search")).pack(side="left", padx=(8, 4))
        ctk.CTkEntry(top, textvariable=self.var_search, width=200, height=26).pack(side="left", padx=4)
        self.var_diff = tk.BooleanVar(value=True)
        self.var_known = tk.BooleanVar(value=False)
        for text, var in ((tr("differences only"), self.var_diff), (tr("known only"), self.var_known)):
            ctk.CTkCheckBox(top, text=text, variable=var, command=self._refilter, width=20, checkbox_width=20, checkbox_height=20).pack(side="left", padx=(12, 2))
        self.var_search.trace_add("write", lambda *_a: self._refilter())
        bar = ctk.CTkFrame(self)
        bar.pack(fill="x", padx=8, pady=2)
        for source, cmd in (("All", lambda: self._set_visible(lambda v, _i: True)), ("None", lambda: self._set_visible(lambda v, _i: False)),
                            ("Invert selection", lambda: self._set_visible(lambda v, _i: not v)),
                            ("Known only", lambda: self._set_visible(lambda _v, i: i["known"]))):
            ctk.CTkButton(bar, text=tr(source), width=app._tr_width(source, 110), height=26, command=cmd).pack(side="left", padx=(6, 2), pady=3)
        self.lbl_count = ctk.CTkLabel(bar, text="", text_color="gray")
        self.lbl_count.pack(side="right", padx=10)
        self.list = ctk.CTkScrollableFrame(self)
        self.list.pack(fill="both", expand=True, padx=8, pady=2)
        self.rows = []
        for item, var in zip(items, self.vars):
            new = item["new"] if len(item["new"]) <= 70 else item["new"][:67] + "…"
            cur = item["cur"] if len(item["cur"]) <= 70 else item["cur"][:67] + "…"
            label = item["name"] or tr("(unknown)")
            same_text = tr("(same)")      # no nested quotes inside an f-string (Python < 3.12)
            text = f"{item['tid']}  {label}:   {cur}  →  {new}" if item["differs"] else f"{item['tid']}  {label}:   {cur}  {same_text}"
            cb = tk.Checkbutton(self.list, text=text, variable=var, anchor="w", justify="left", command=self._update_count,
                                bg=c["bg"], fg=c["label"] if item["known"] else "#9a9a9a", selectcolor=c["entry"],
                                activebackground=c["bg"], activeforeground=c["text"], font=app._font)
            self.rows.append(cb)
        foot = ctk.CTkFrame(self, fg_color="transparent")
        foot.pack(fill="x", padx=8, pady=(2, 8))
        ctk.CTkButton(foot, text=tr("Import selection"), width=app._tr_width("Import selection", 150), command=self._ok).pack(side="right", padx=4)
        ctk.CTkButton(foot, text=tr("Import all known"), width=app._tr_width("Import all known", 190), command=self._all_known).pack(side="right", padx=4)
        ctk.CTkButton(foot, text=tr("Cancel"), width=app._tr_width("Cancel", 100), fg_color="gray40", hover_color="gray30", command=self.destroy).pack(side="right", padx=4)
        ctk.CTkButton(foot, text=tr("Show differences"), width=app._tr_width("Show differences", 170), command=self._show_diff).pack(side="left", padx=4)
        self._refilter()

    def _visible(self, idx: int) -> bool:
        item = self.items[idx]
        if self.var_diff.get() and not item["differs"]:
            return False
        if self.var_known.get() and not item["known"]:
            return False
        tokens = self.var_search.get().lower().split()
        hay = f"{item['tid']} {item['name']} {item['cur']} {item['new']}".lower()
        return all(t in hay for t in tokens)

    def _refilter(self):
        for idx, cb in enumerate(self.rows):
            if self._visible(idx):
                cb.pack(fill="x", anchor="w", padx=4)
            else:
                cb.pack_forget()
        self._update_count()

    def _set_visible(self, fn):
        for idx, var in enumerate(self.vars):
            if self._visible(idx):
                var.set(fn(var.get(), self.items[idx]))
        self._update_count()

    def _update_count(self):
        shown = sum(1 for i in range(len(self.items)) if self._visible(i))
        chosen = sum(1 for v in self.vars if v.get())
        self.lbl_count.configure(text=tr("{chosen} selected, {shown} of {total} shown").format(chosen=chosen, shown=shown, total=len(self.items)))

    def _show_diff(self):
        self.app.show_diff(self.items, self.source_text)
        self.after(50, self.grab_set)         # the difference window had the input grab

    def _ok(self):
        self.result = [i for i, v in zip(self.items, self.vars) if v.get()]
        self.destroy()

    def _all_known(self):
        self.result = [i for i in self.items if i["known"] and i["differs"]]
        self.destroy()


class DiffDialog(ctk.CTkToplevel):
    """Side-by-side difference of the current file and another file (like a file compare tool): menu paths instead of IDs,
    changed rows coloured, next/previous difference, all rows or only the differences."""

    def __init__(self, app, rows: list[dict], other_name: str, invisible: bool = False):
        super().__init__(app)
        if invisible:
            self.attributes("-alpha", 0)
        self.app, self.rows, self.other_name = app, rows, other_name
        self.diff_rows = [i for i, r in enumerate(rows) if r["differs"]]
        self.current = 0 if self.diff_rows else -1       # index into diff_rows
        self.only_diffs = True
        self._lines: list[int] = []                      # row index of every line that is shown
        self.title(tr("Compare with {source}").format(source=other_name))
        self.geometry(f"{int(app.winfo_width() * 0.9)}x{int(app.winfo_height() * 0.9)}")
        self.transient(app)
        dark = ctk.get_appearance_mode() == "Dark"
        self._colors = {"diff": "#4a4220" if dark else "#fff3c4", "cell": "#7a6414" if dark else "#ffe08a", "sel": "#2d4a6d" if dark else "#cfe4ff",
                        "only": "#5a2f2f" if dark else "#ffd6d6"}
        bar = ctk.CTkFrame(self)
        bar.pack(fill="x", padx=8, pady=(8, 2))
        sources = (("Previous difference", "Alt+Up", self.previous_difference), ("Next difference", "Alt+Down", self.next_difference))
        for source, hint, command in sources:
            ctk.CTkButton(bar, text=f"{tr(source)}  ({hint})", width=app._tr_width(source, 150) + 60, height=26, command=command).pack(side="left", padx=(6, 2), pady=3)
        self.seg = ctk.CTkSegmentedButton(bar, values=[tr("Show full files") + "  (Ctrl+1)", tr("Show only differences") + "  (Ctrl+2)"], command=self._segment)
        self.seg.set(tr("Show only differences") + "  (Ctrl+2)")
        self.seg.pack(side="left", padx=(16, 2), pady=3)
        self.lbl_count = ctk.CTkLabel(bar, text="", text_color="gray")
        self.lbl_count.pack(side="right", padx=10)
        font = app._font
        self.head = tk.Text(self, height=1, font=app._font_bold, bg=app._c["bg"], fg=app._c["label"], relief="flat", borderwidth=0, highlightthickness=0, wrap="none")
        self.head.pack(fill="x", padx=(10, 8))
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.text = tk.Text(body, font=font, bg=app._c["entry"], fg=app._c["text"], relief="flat", borderwidth=0, highlightthickness=0, wrap="none",
                            cursor="arrow", spacing1=app._sc(2), spacing3=app._sc(2))
        scroll = ctk.CTkScrollbar(body, command=self.text.yview)
        self.text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.text.pack(side="left", fill="both", expand=True)
        for name, color in (("diff", "diff"), ("current", "sel"), ("only", "only")):
            self.text.tag_configure(name, background=self._colors[color])
        self.text.tag_configure("cell", background=self._colors["cell"])
        self.text.tag_raise("cell", "diff")
        self._job = None
        self.text.bind("<Configure>", lambda _e: self._schedule_render())
        self.text.bind("<Button-1>", self._click)
        for seq, command in (("<Alt-Down>", self.next_difference), ("<F8>", self.next_difference), ("<Alt-Up>", self.previous_difference),
                             ("<Shift-F8>", self.previous_difference), ("<Control-Key-1>", self.show_full), ("<Control-Key-2>", self.show_differences),
                             ("<Escape>", self.destroy)):
            self.bind(seq, lambda _e, c=command: (c(), "break")[1])
        self.after(50, self._render)

    # -- content ----------------------------------------------------------- #
    def _clip(self, text: str, width: int) -> str:
        font = self.app._font
        if font.measure(text) <= width:
            return text
        while text and font.measure(text + "…") > width:
            text = text[:-1]
        return text + "…"

    def _schedule_render(self):
        if self._job is not None:
            self.after_cancel(self._job)
        self._job = self.after(120, self._render)

    def _render(self):
        self._job = None
        width = max(self.text.winfo_width(), self.app._sc(600)) - self.app._sc(24)
        col_path, col_left = int(width * 0.42), int(width * 0.29)
        col_right = width - col_path - col_left
        tabs = (col_path, col_path + col_left)
        self.text.configure(tabs=tabs)
        self.head.configure(tabs=tabs, state="normal")
        self.head.delete("1.0", "end")
        self.head.insert("1.0", f"{tr('Path')}\t{tr('Current file')}\t{self.other_name}")
        self.head.configure(state="disabled")
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self._lines = []
        shown_diff_line = {}
        for idx, row in enumerate(self.rows):
            if self.only_diffs and not row["differs"]:
                continue
            line = len(self._lines) + 1
            self._lines.append(idx)
            left = self._clip(row["left"], col_left - self.app._sc(12))
            right = self._clip(row["right"], col_right - self.app._sc(12))
            path = self._clip(row["path"], col_path - self.app._sc(12))
            start = self.text.index("end-1c")
            self.text.insert("end", f"{path}\t{left}\t{right}\n")
            if row["differs"]:
                self.text.tag_add("diff", f"{line}.0", f"{line + 1}.0")          # up to the next line: the colour reaches the window edge
                self.text.tag_add("cell", f"{line}.{len(path) + 1}", f"{line + 1}.0")
            shown_diff_line[idx] = line
        self.text.configure(state="disabled")
        self._mark_current()
        self._update_count()

    def _mark_current(self):
        self.text.tag_remove("current", "1.0", "end")
        if self.current < 0:
            return
        idx = self.diff_rows[self.current]
        if idx in self._lines:
            line = self._lines.index(idx) + 1
            self.text.tag_add("current", f"{line}.0", f"{line + 1}.0")
            self.text.tag_raise("current")
            self.text.see(f"{line}.0")

    def _update_count(self):
        if not self.diff_rows:
            self.lbl_count.configure(text=tr("No differences"))
        else:
            self.lbl_count.configure(text=tr("Difference {n} of {total}").format(n=self.current + 1, total=len(self.diff_rows)))

    # -- commands ---------------------------------------------------------- #
    def next_difference(self):
        if self.diff_rows:
            self.current = (self.current + 1) % len(self.diff_rows)
            self._mark_current()
            self._update_count()

    def previous_difference(self):
        if self.diff_rows:
            self.current = (self.current - 1) % len(self.diff_rows)
            self._mark_current()
            self._update_count()

    def show_full(self):
        self.only_diffs = False
        self.seg.set(tr("Show full files") + "  (Ctrl+1)")
        self._render()

    def show_differences(self):
        self.only_diffs = True
        self.seg.set(tr("Show only differences") + "  (Ctrl+2)")
        self._render()

    def _segment(self, value: str):
        (self.show_differences if tr("Show only differences") in value else self.show_full)()

    def _click(self, event):
        """A click on a changed row makes it the current difference."""
        line = int(self.text.index(f"@{event.x},{event.y}").split(".")[0])
        if 1 <= line <= len(self._lines):
            idx = self._lines[line - 1]
            if idx in self.diff_rows:
                self.current = self.diff_rows.index(idx)
                self._mark_current()
                self._update_count()


def hue_hex(degrees: int) -> str:
    """Fully saturated colour of a hue angle (0 to 359 degrees) for the small colour field next to hue values."""
    r, g, b = colorsys.hsv_to_rgb((degrees % 360) / 360, 1.0, 1.0)
    return f"#{round(r * 255):02x}{round(g * 255):02x}{round(b * 255):02x}"


class MenuItem:
    """Stands in for a former toolbar button: configure(state=...) / cget("state") act on the menu entry."""

    def __init__(self, app, key: str):
        self.app, self.key = app, key

    def configure(self, **kw):
        if "state" in kw:
            self.app._set_menu_state(self.key, kw["state"])

    def cget(self, name):
        return self.app._menu_state.get(self.key) if name == "state" else None


MENU_TEXTS = ["New…", "Open…", "Save", "Save As…", "Import…", "Exit", "Undo", "Redo", "Find", "File", "Edit",
              "Language", "View", "Help", "About {app}…", "All", "None", "Invert selection", "Known only", "Miscellaneous", "Unknown", "Compare…", "Previous difference", "Next difference", "Expand all", "Collapse all"]   # texts that tr() gets through variables
ABOUT_TEXTS = [
    "Reads, converts and writes configuration files (SCENE and ALL files) of the Sony PXW-FS7 and PXW-FS7M2 cameras.",
    "Copyright (c) 2026 Lukas Himmelswanderer. Published under the MIT License.",
    "Unofficial, independent project: it is not affiliated with Sony and is neither supported nor reviewed by Sony. Sony, PXW-FS7 and PXW-FS7M2 and other product and brand names mentioned are the property of their respective owners and are used here only to name the compatible devices.",
    "The file formats were researched by comparing the author's own files in order to achieve interoperability. The program contains neither Sony software nor Sony material.",
    "Use at your own risk: the software is provided without any warranty (see license text). Files created with this program change settings of your camera. Before loading them, back up the current state (save an All File to the SD card). Flawless operation with every camera and every firmware cannot be guaranteed.",
    "Uses: customtkinter (MIT License) and the Python standard library (Tkinter).",
]


class LicenseDialog(ctk.CTkToplevel):
    """Shows the text of the LICENSE file."""

    def __init__(self, app, invisible: bool = False):
        super().__init__(app)
        if invisible:
            self.attributes("-alpha", 0)
        self.title(tr("License text"))
        self.transient(app)
        self.geometry(f"{app._sc(640)}x{app._sc(480)}")
        box = ctk.CTkTextbox(self, wrap="word")
        box.pack(fill="both", expand=True, padx=12, pady=(12, 6))
        try:
            text = (BASE_DIR / "LICENSE").read_text(encoding="utf-8")
        except OSError:
            text = "MIT License (LICENSE file not found)"
        box.insert("1.0", text)
        box.configure(state="disabled")
        ctk.CTkButton(self, text=tr("Close"), width=app._tr_width("Close", 100), command=self.destroy).pack(pady=(0, 12))


def open_mail_client() -> bool:
    """Open the default mail program with a new message to the project address (Windows, macOS, Linux). Returns False on failure."""
    import subprocess
    import urllib.parse
    url = f"mailto:{CONTACT_EMAIL}?subject=" + urllib.parse.quote(f"{APP_NAME} {_version}")
    try:
        if sys.platform == "win32":
            os.startfile(url)                                  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", url])
        else:
            subprocess.Popen(["xdg-open", url])
        return True
    except (OSError, ValueError):
        try:
            import webbrowser
            return bool(webbrowser.open(url))
        except Exception:
            return False


LOGO_FILE = BASE_DIR / "assets" / "sonyconfigeditor.png"


def load_logo(size: int):
    """The program logo as a CTkImage of size x size logical pixels (None if the file is missing or unreadable)."""
    try:
        from PIL import Image
        with Image.open(LOGO_FILE) as img:
            img = img.convert("RGBA")
            box = img.getchannel("A").getbbox()      # the icon has a wide transparent margin: crop it, so the logo uses its full size
            if box:
                img = img.crop(box)
            img.thumbnail((512, 512))      # the original is larger than any display size; keep the scaled copy small
            return ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))
    except (OSError, ImportError, ValueError):
        return None


class AboutDialog(ctk.CTkToplevel):
    """Name, version, licence, disclaimer."""

    def __init__(self, app, invisible: bool = False):
        super().__init__(app)
        if invisible:
            self.attributes("-alpha", 0)
        self.app, self.invisible = app, invisible
        self.title(tr("About {app}").format(app=APP_NAME))
        self.transient(app)
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(padx=24, pady=(18, 8))
        head = ctk.CTkFrame(frame, fg_color="transparent")
        head.pack(anchor="w", pady=(0, 10))
        logo = load_logo(112)
        if logo is not None:
            ctk.CTkLabel(head, text="", image=logo).pack(side="left", padx=(0, 16))      # CTkImage scales with the Windows display scaling
        titles = ctk.CTkFrame(head, fg_color="transparent")
        titles.pack(side="left")
        ctk.CTkLabel(titles, text=APP_NAME, font=ctk.CTkFont(size=22, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(titles, text=tr("Version {version} ({date})").format(version=_version, date=_date), text_color="gray").pack(anchor="w")
        wrap = app._sc(560)
        self.texts = []
        for source in ABOUT_TEXTS:
            label = ctk.CTkLabel(frame, text=tr(source), wraplength=wrap, justify="left", anchor="w")
            label.pack(anchor="w", pady=(0, 8))
            self.texts.append(label)
        link = ctk.CTkLabel(frame, text=CONTACT_EMAIL, text_color=app._c["accent"], anchor="w", cursor="hand2",
                            font=ctk.CTkFont(underline=True))
        link.pack(anchor="w")
        link.bind("<Button-1>", lambda _e: open_mail_client())
        self.link = link
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(pady=(0, 16))
        ctk.CTkButton(row, text=tr("License text…"), width=app._tr_width("License text…", 130), command=self.show_license).pack(side="left", padx=6)
        ctk.CTkButton(row, text=tr("Close"), width=app._tr_width("Close", 100), command=self.destroy).pack(side="left", padx=6)

    def show_license(self):
        dialog = LicenseDialog(self.app, invisible=self.invisible)
        if not self.invisible:
            dialog.after(50, dialog.grab_set)
            self.wait_window(dialog)


class RowLabel(tk.Frame):
    """Name of a parameter row: the decoded text and, in grey and in brackets behind it, the ID."""

    def __init__(self, master, name: str, ident: str, bg: str, fg: str, font, wraplength: int):
        super().__init__(master, bg=bg)
        self.name = tk.Label(self, text=name, anchor="w", justify="left", wraplength=wraplength, bg=bg, fg=fg, font=font)
        self.name.pack(side="left")
        self.ident = tk.Label(self, text=ident, bg=bg, fg=RAW_COLOR, font=font)
        if ident:
            self.ident.pack(side="left", padx=(6, 0))

    def configure(self, cnf=None, **kw):
        if "fg" in kw:
            self.name.configure(fg=kw.pop("fg"))
        if kw:
            super().configure(**kw)

    config = configure

    def cget(self, key):
        if key == "text":
            return (self.name.cget("text") + " " + self.ident.cget("text")).strip()
        return super().cget(key)


class ModelDialog(ctk.CTkToplevel):
    """Asks which camera a new file is for. `result` = model name or None."""

    def __init__(self, app, invisible: bool = False):
        super().__init__(app)
        if invisible:
            self.attributes("-alpha", 0)
        self.result = None
        self.title(tr("New"))
        self.transient(app)
        ctk.CTkLabel(self, text=tr("Which camera is the new file for?")).pack(padx=24, pady=(18, 10))
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(padx=24, pady=(0, 6))
        for label, model in (("FS7 (Mk1)", "PXW-FS7"), ("FS7 Mk2", "PXW-FS7M2")):
            ctk.CTkButton(row, text=label, width=130, command=lambda m=model: self._pick(m)).pack(side="left", padx=6)
        ctk.CTkLabel(self, text=tr("Neutral values from the templates; not a factory state."), text_color="gray").pack(padx=24, pady=(0, 6))
        ctk.CTkButton(self, text=tr("Cancel"), width=app._tr_width("Cancel", 100), fg_color="gray40", hover_color="gray30", command=self.destroy).pack(pady=(0, 16))

    def _pick(self, model: str):
        self.result = model
        self.destroy()


class Tooltip:
    """Small text window shown while the mouse is over a widget."""

    def __init__(self, widget, text: str = ""):
        self.widget, self.text, self._tip = widget, text, None
        widget.bind("<Enter>", self._show, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<Destroy>", self._hide, add="+")

    def _show(self, _e=None):
        if self._tip or not self.text:
            return
        self._tip = tk.Toplevel(self.widget)
        self._tip.wm_overrideredirect(True)
        self._tip.wm_geometry(f"+{self.widget.winfo_rootx() + 16}+{self.widget.winfo_rooty() + self.widget.winfo_height() + 4}")
        app = self.widget.nametowidget(".")   # the App: its font and _sc() follow the Windows scaling
        sc = getattr(app, "_sc", lambda px: px)
        tk.Label(self._tip, text=self.text, justify="left", wraplength=sc(520), bg="#ffffe0", fg="#202020",
                 font=getattr(app, "_font", None), relief="solid", borderwidth=1, padx=sc(8), pady=sc(5)).pack()

    def _hide(self, _e=None):
        if self._tip:
            self._tip.destroy()
            self._tip = None


INFO_SYMBOL = "ⓘ"


class InfoLabel(ctk.CTkLabel):
    """Info symbol whose text is shown as a tooltip; it takes no room while there is no text."""

    def __init__(self, master, **kwargs):
        kwargs.pop("text", None)
        super().__init__(master, text=INFO_SYMBOL, text_color="gray", cursor="hand2", font=ctk.CTkFont(size=18), **kwargs)
        self.info = ""
        self.on_change = None   # called after the symbol was shown or hidden
        self._tooltip = Tooltip(self)

    def set_info(self, text: str):
        self.info = self._tooltip.text = text

    def cget(self, attribute_name):
        return self.info if attribute_name == "text" else super().cget(attribute_name)


class AutoHideInfo(InfoLabel):
    """InfoLabel for the header messages: `configure(text=...)` sets the tooltip and shows or hides the symbol."""

    def grid(self, **kwargs):
        self._grid_kwargs = kwargs
        super().grid(**kwargs)

    def configure(self, require_redraw=False, **kwargs):
        if "text" in kwargs:
            self.set_info(kwargs.pop("text"))
            if hasattr(self, "_grid_kwargs"):
                super().grid(**self._grid_kwargs) if self.info else self.grid_remove()
                if self.on_change:
                    self.on_change()
        if kwargs:
            super().configure(require_redraw=require_redraw, **kwargs)


class AutoHideLabel(ctk.CTkLabel):
    """Label that takes no room while its text is empty (keeps the header compact)."""

    def grid(self, **kwargs):
        self._grid_kwargs = kwargs
        super().grid(**kwargs)

    def configure(self, require_redraw=False, **kwargs):
        super().configure(require_redraw=require_redraw, **kwargs)
        if "text" in kwargs and hasattr(self, "_grid_kwargs"):
            if kwargs["text"]:
                super().grid(**self._grid_kwargs)
            else:
                self.grid_remove()
            if getattr(self, "on_change", None):
                self.on_change()


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        init_language()
        self.appearance = initial_appearance()
        self._apply_appearance(self.appearance)
        ctk.set_default_color_theme("blue")
        self.title(f"{APP_NAME} v{_version}")
        scale = ctk.ScalingTracker.get_window_scaling(self)
        screen_w, screen_h = self.winfo_screenwidth() / scale, self.winfo_screenheight() / scale
        self.geometry(f"{int(min(1150, screen_w * 0.9))}x{int(min(700, screen_h * 0.85))}")   # the Multi Matrix row (axis, hue, saturation) needs about 1050
        self.minsize(int(min(900, screen_w * 0.6)), int(min(500, screen_h * 0.5)))

        self.scene: SceneFile | None = None
        self.original: dict = {}
        self.entries: dict[str, ctk.CTkBaseClass] = {}
        self.vars: dict[str, tk.StringVar] = {}
        self.kind = "scene"
        self.param_db = load_param_db("scene")
        self.locks: list = []
        self.rules = load_transfer_rules()
        self.session: SceneSession | None = None
        self._hist: list[dict] = []
        self._hpos = -1
        self._last_key: str | None = None
        self._last_t = 0.0
        self._busy = False
        self._built_model: str | None = None
        self._built_kind: str | None = None
        self._built_db: dict = {}
        self._built_look: tuple = ()
        self._last_dir: Path | None = None   # folder of the last opened/saved file (remembered in the settings file)
        saved_dir = load_settings().get("last_dir")
        if isinstance(saved_dir, str) and is_safe_dir(saved_dir):      # no network (UNC) paths from the file: checking them would contact a foreign server
            self._last_dir = Path(saved_dir)
        self._collapsed: dict[str, bool] = {}   # block -> collapsed (kept while the app runs)
        self._sub_collapsed: set[str] = set()   # collapsed sub-groups (by title, kept while the app runs)
        self._cat_collapsed: set[str] = set()   # collapsed categories ("Paint")
        self._groups: dict[str, dict] = {}
        self._lazy_groups: set[str] = set()   # blocks whose rows are not built yet
        self._reflow: list = []               # widgets whose fields wrap to the width of the window (see _reflow_all)
        self._reflow_job = None
        self._rows: dict[str, dict] = {}      # parameter id -> {"label", "widget", "sub"} (for the filter)
        self._subheads: list[dict] = []
        self._filter_job = None
        self._stash: dict[tuple, dict[str, str]] = {}   # (parameter, choice that was left) -> values the choice replaced
        self._saved: tuple | None = None  # state key of the last loaded/saved version (for the "*" marker)

        self._scale = scale
        self._font = tkfont.Font(family="Segoe UI", size=-max(1, round(13 * scale)))  # pixel size follows the Windows scaling
        self._font_bold = tkfont.Font(family="Segoe UI", size=-max(1, round(13 * scale)), weight="bold")
        self._build()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self._row_parent = self.table   # parent of the widgets of the current block while the table is built
        self._c = self._theme_colors()
        self._window_mode = ctk.get_appearance_mode()        # the colours the window was built with
        AppearanceModeTracker.add(lambda _mode: self.after_idle(self._follow_system))
        # customtkinter scales its own widgets (and follows monitor changes); the plain tk widgets of the parameter
        # table are scaled here
        ctk.ScalingTracker.add_widget(self._on_scaling_changed, self)
        self._bind_shortcuts()
        for seq in ("<Control-f>", "<Control-F>"):
            self.bind(seq, lambda _e: (self.entry_search.focus_set(), "break")[1])
        for seq in ("<Control-z>", "<Control-Z>"):
            self.bind(seq, lambda _e: self.undo() or "break")
        for seq in ("<Control-y>", "<Control-Y>", "<Control-Shift-z>", "<Control-Shift-Z>"):
            self.bind(seq, lambda _e: self.redo() or "break")

    def _sync_messages(self):
        """The message area takes no room at all while there is nothing to say."""
        shown = any(label.winfo_manager() for label in (self.lbl_scene_hint, self.lbl_switch, self.lbl_warn))
        if shown and not self.messages.winfo_manager():
            self.messages.pack(fill="x", padx=8, before=self._filt)
        elif not shown and self.messages.winfo_manager():
            self.messages.pack_forget()

    def _update_clip_row(self):
        """Show the clip name row for ALL files and link it with the parameter row 00285 (title prefix)."""
        show = self.kind == "all" and "00285" in self.vars
        if show and not self.clipbar.winfo_manager():
            self.clipbar.pack(fill="x", padx=8, pady=2, before=self._head)
        elif not show and self.clipbar.winfo_manager():
            self.clipbar.pack_forget()
        if not show:
            return
        table_var = self.vars["00285"]
        self._clip_sync = True
        self.var_clip_name.set(table_var.get())
        self._clip_sync = False

        def table_changed(*_a):
            if not self._clip_sync:
                self._clip_sync = True
                self.var_clip_name.set(table_var.get())
                self._clip_sync = False

        if not getattr(table_var, "_clip_traced", False):      # one trace per variable, however often the row is updated
            table_var._clip_traced = True
            table_var.trace_add("write", table_changed)

    def _on_clip_name(self, *_a):
        if self._clip_sync or "00285" not in self.vars:
            return
        self._clip_sync = True
        self.vars["00285"].set(self.var_clip_name.get())
        self._clip_sync = False

    def _sc(self, px: int) -> int:
        """Scale a pixel value for the plain tk widgets (Windows display scaling / High DPI)."""
        return max(1, round(px * self._scale))

    def _on_scaling_changed(self, _widget_scaling: float, window_scaling: float):
        if abs(window_scaling - self._scale) < 0.01:
            return
        self._scale = window_scaling
        self._font.configure(size=-max(1, round(13 * window_scaling)))
        self._font_bold.configure(size=-max(1, round(13 * window_scaling)))
        if self.scene:
            self.after_idle(lambda: self._populate(reset_original=False))

    def _blend(self, color: str, target: str, amount: float) -> str:
        """`color` moved by `amount` (0..1) towards `target`, both any Tk colour; result as #rrggbb."""
        (r1, g1, b1), (r2, g2, b2) = self.winfo_rgb(color), self.winfo_rgb(target)
        mix = lambda a, b: round((a + (b - a) * amount) / 257)
        return f"#{mix(r1, r2):02x}{mix(g1, g2):02x}{mix(b1, b2):02x}"

    def _separator(self, parent, kind: str, **grid):
        """Thin horizontal line: "main" = dark and thick (between blocks and categories), "sub" = light and thin (between sub-groups)."""
        line = tk.Frame(parent, bg=self._c["sep_" + kind], height=self._sc(2 if kind == "main" else 1))
        line.grid(sticky="ew", **grid)
        return line

    def _theme_colors(self) -> dict:
        """Colours for the plain tk widgets of the parameter table (far faster than customtkinter widgets)."""
        theme = ctk.ThemeManager.theme
        mode = 1 if ctk.get_appearance_mode() == "Dark" else 0
        pick = lambda v: v[mode] if isinstance(v, (list, tuple)) else v
        bg = self.table._apply_appearance_mode(self.table.cget("fg_color"))
        # structure: sub-group cards are a little lighter (dark mode) / darker (light mode) than the table, main separators clearly darker,
        # sub-group separators a little lighter than the table
        dark = mode == 1
        return {
            "bg": bg,
            "card": self._blend(bg, "#ffffff" if dark else "#000000", 0.06),
            "card_border": self._blend(bg, "#ffffff" if dark else "#000000", 0.14),
            "sep_main": self._blend(bg, "#000000", 0.75 if dark else 0.45),
            "sep_sub": self._blend(bg, "#ffffff" if dark else "#000000", 0.16),
            "entry": pick(theme["CTkEntry"]["fg_color"]),
            "text": pick(theme["CTkEntry"]["text_color"]),
            "border": pick(theme["CTkEntry"]["border_color"]),
            "focus": pick(theme["CTkButton"]["fg_color"]),
            "label": pick(theme["CTkLabel"]["text_color"]),
            "accent": "#6cb6ff" if mode == 1 else "#1f6aa5",
            "font": self._font,
        }

    # -- menu bar ------------------------------------------------------------ #
    def _build_menu(self):
        """Menu bar (File, Edit, View, Help) with the usual shortcuts; replaces the former toolbar buttons."""
        self._menu_entries = {}
        self._menu_state = getattr(self, "_menu_state", None) or {k: "disabled" for k in ("save", "save_as", "import", "compare", "undo", "redo")}
        bar = ctk.CTkFrame(self, corner_radius=0, height=30)     # own menu bar: the native one can neither be scaled nor coloured
        bar.pack(side="top", fill="x")
        theme, mode = ctk.ThemeManager.theme, (1 if ctk.get_appearance_mode() == "Dark" else 0)
        pick = lambda v: v[mode] if isinstance(v, (list, tuple)) else v
        colors = {"entry": pick(theme["CTkEntry"]["fg_color"]), "text": pick(theme["CTkEntry"]["text_color"]), "border": pick(theme["CTkEntry"]["border_color"]),
                  "focus": pick(theme["CTkButton"]["fg_color"]), "label": pick(theme["CTkLabel"]["text_color"])}

        def new_menu(parent):
            return tk.Menu(parent, tearoff=False, font=self._font, bg=colors["entry"], fg=colors["text"], activebackground=colors["focus"],
                           activeforeground="#ffffff", selectcolor=colors["text"], borderwidth=1, relief="solid", activeborderwidth=0)

        def cascade(label, menu):
            button = ctk.CTkButton(bar, text=label, width=10, height=26, corner_radius=4, fg_color="transparent", text_color=colors["label"],
                                   hover_color=colors["border"], command=lambda: popup(button, menu))
            button.pack(side="left", padx=(4, 0), pady=2)

        def popup(button, menu):
            menu.tk_popup(button.winfo_rootx(), button.winfo_rooty() + button.winfo_height())
            menu.grab_release()

        def add(menu, key, source, command, accel=None):
            menu.add_command(label=tr(source), command=command, accelerator=accel)
            self._menu_entries[key] = (menu, menu.index("end"))

        file_menu = new_menu(bar)
        add(file_menu, "new", "New…", self.new_file, "Ctrl+N")
        add(file_menu, "open", "Open…", self.open_file, "Ctrl+O")
        add(file_menu, "save", "Save", self.save, "Ctrl+S")
        add(file_menu, "save_as", "Save As…", self.save_as, "Ctrl+Shift+S")
        file_menu.add_separator()
        add(file_menu, "import", "Import…", self.import_file, "Ctrl+I")
        add(file_menu, "compare", "Compare…", self.compare_file, "Ctrl+D")
        file_menu.add_separator()
        add(file_menu, "exit", "Exit", self.on_close, "Alt+F4")
        cascade(tr("File"), file_menu)

        edit_menu = new_menu(bar)
        add(edit_menu, "undo", "Undo", self.undo, "Ctrl+Z")
        add(edit_menu, "redo", "Redo", self.redo, "Ctrl+Y")
        edit_menu.add_separator()
        add(edit_menu, "search", "Find", lambda: self.entry_search.focus_set(), "Ctrl+F")
        cascade(tr("Edit"), edit_menu)

        view_menu = new_menu(bar)
        lang_menu = new_menu(view_menu)
        self.var_lang = tk.StringVar(value=LANG)
        for code, name in available_languages().items():
            lang_menu.add_radiobutton(label=name, value=code, variable=self.var_lang, command=lambda c=code: self.set_language(c))
        add(view_menu, "expand_all", "Expand all", self.expand_all, "Ctrl+Shift+Down")
        add(view_menu, "collapse_all", "Collapse all", self.collapse_all, "Ctrl+Shift+Up")
        view_menu.add_separator()
        view_menu.add_cascade(label=tr("Language"), menu=lang_menu)
        look_menu = new_menu(view_menu)
        self.var_appearance = tk.StringVar(value=self.appearance)
        for mode, label in (("system", tr("System")), ("light", tr("Day")), ("dark", tr("Night"))):
            look_menu.add_radiobutton(label=label, value=mode, variable=self.var_appearance, command=lambda m=mode: self.set_appearance(m))
        view_menu.add_cascade(label=tr("Appearance"), menu=look_menu)
        cascade(tr("View"), view_menu)

        help_menu = new_menu(bar)
        help_menu.add_command(label=tr("About {app}…").format(app=APP_NAME), command=self.show_about, accelerator="F1")
        cascade(tr("Help"), help_menu)

        self._menu_bar = bar
        self._menu_commands = {"new": self.new_file, "open": self.open_file, "save": self.save, "save_as": self.save_as, "import": self.import_file, "compare": self.compare_file,
                               "exit": self.on_close, "undo": self.undo, "redo": self.redo, "about": self.show_about,
                               "expand_all": self.expand_all, "collapse_all": self.collapse_all}
        for key, state in self._menu_state.items():
            self._set_menu_state(key, state)
        # the former toolbar buttons: the code (and the tests) still enable / disable them by name
        for name, key in (("btn_save", "save"), ("btn_save_as", "save_as"), ("btn_undo", "undo"), ("btn_redo", "redo"), ("btn_import", "import"), ("btn_compare", "compare")):
            setattr(self, name, MenuItem(self, key))

    def _set_menu_state(self, key: str, state: str):
        self._menu_state[key] = state
        entry = self._menu_entries.get(key)
        if entry:
            entry[0].entryconfigure(entry[1], state=state)

    def _shortcut(self, key: str):
        """Keyboard shortcut of a menu entry (ignored while the entry is disabled)."""
        if self._menu_state.get(key, "normal") != "disabled":
            self._menu_commands[key]()
        return "break"

    def _bind_shortcuts(self):
        for seq, key in (("<Control-n>", "new"), ("<Control-N>", "new"), ("<Control-o>", "open"), ("<Control-O>", "open"), ("<Control-s>", "save"),
                         ("<Control-S>", "save_as"), ("<Control-Shift-s>", "save_as"), ("<Control-Shift-S>", "save_as"), ("<Control-i>", "import"),
                         ("<Control-I>", "import"), ("<Control-d>", "compare"), ("<Control-D>", "compare"), ("<Control-Shift-Down>", "expand_all"), ("<Control-Shift-Up>", "collapse_all"), ("<Control-q>", "exit"), ("<Control-Q>", "exit"), ("<F1>", "about")):
            self.bind(seq, lambda _e, k=key: self._shortcut(k))

    def show_about(self, invisible: bool = False):
        dialog = AboutDialog(self, invisible=invisible)
        if not invisible:
            dialog.after(50, dialog.grab_set)
            self.wait_window(dialog)
        return dialog

    def set_language(self, code: str):
        """Switch the language at run time: the whole window (menus, labels, notes, dropdowns) is rebuilt in the new language."""
        global LANG
        if code == LANG or code not in available_languages():
            return
        LANG = code
        save_language(code)
        self._rebuild_window()

    def set_appearance(self, mode: str):
        """Switch between system setting, day and night mode: the plain tk widgets and menus do not follow by themselves, so the window is rebuilt."""
        if mode not in APPEARANCES or mode == self.appearance:
            return
        self.appearance = mode
        save_settings(appearance=mode)
        self._apply_appearance(mode)
        self._rebuild_window()

    @staticmethod
    def _apply_appearance(mode: str):
        """Set the customtkinter mode. "system" only marks the mode as system-controlled, the tracker looks at the system a moment later
        (polling): detect it now, otherwise the window would be built with the colours of the previous mode."""
        ctk.set_appearance_mode(mode)
        if mode == "system":
            AppearanceModeTracker.init_appearance_mode()

    def _follow_system(self, *_args):
        """The system switched between light and dark while the mode is "system": build the window again with the new colours."""
        if self.appearance == "system" and self._window_mode != ctk.get_appearance_mode():
            self._rebuild_window()

    def _rebuild_window(self):
        """Build all widgets again (new language or colours) and show the current file in them."""
        keep = (self.var_search.get(), self.var_changed.get(), self.var_known.get())
        for widget in self.winfo_children():
            widget.destroy()
        self._build()
        self._c = self._theme_colors()
        self._window_mode = ctk.get_appearance_mode()
        self._row_parent = self.table
        self.var_search.set(keep[0])
        self.var_changed.set(keep[1])
        self.var_known.set(keep[2])
        if self.scene:
            self._apply_kind(self.kind)         # databases in the new language
            self._populate(reset_original=False)
            self._update_title()
            self._update_history_buttons()
        else:
            self.param_db = load_param_db(self.kind)
            self.locks = load_param_locks(self.kind)
            self.title(f"{APP_NAME} v{_version}")
        self.lbl_switch.configure(text="")

    def _tr_width(self, source: str, minimum: int) -> int:
        """Width (unscaled pixels) of a button or dropdown for the longest translation of a text."""
        return max(minimum, max(round(self._font.measure(t) / self._scale) for t in tr_all(source)) + 40)

    def _build(self):
        self._build_menu()

        self.clipbar = ctk.CTkFrame(self)      # ALL files only: clip name and start number (packed by _update_clip_row)
        ctk.CTkLabel(self.clipbar, text=tr("Clip name")).pack(side="left", padx=(10, 4), pady=3)
        self.var_clip_name = tk.StringVar()
        self.entry_clip = ctk.CTkEntry(self.clipbar, textvariable=self.var_clip_name, width=260, height=26)
        self.entry_clip.pack(side="left", padx=4)
        self.lbl_clip_hint = InfoLabel(self.clipbar)
        self.lbl_clip_hint.set_info(tr("Clip name = title prefix (00285). The running clip number (Number Set) is not stored in the ALL file: the camera counts it internally."))
        self.lbl_clip_hint.pack(side="left", padx=12)
        self._clip_sync = False

        head = ctk.CTkFrame(self)
        head.pack(fill="x", padx=8, pady=2)
        self._head = head
        self.lbl_kind = ctk.CTkLabel(head, text=tr("Type"))
        self.lbl_kind.grid(row=0, column=0, padx=(8, 4), pady=3, sticky="w")
        self.var_kind = tk.StringVar(value="SCENE")
        self.seg_kind = ctk.CTkSegmentedButton(
            head, values=["SCENE", "ALL"], variable=self.var_kind, command=self._switch_kind, state="disabled", height=26
        )
        self.seg_kind.grid(row=0, column=1, padx=4, sticky="w")
        ctk.CTkLabel(head, text=tr("File ID")).grid(row=0, column=2, padx=(14, 4), sticky="w")
        self.var_name = tk.StringVar()
        ctk.CTkEntry(head, textvariable=self.var_name, width=170, height=26).grid(row=0, column=3, padx=4)
        self.var_name.trace_add("write", lambda *_a: self._record("__name__"))
        ctk.CTkLabel(head, text=tr("File no.")).grid(row=0, column=4, padx=(14, 4), sticky="w")
        self.var_number = tk.StringVar()
        self.entry_number = ctk.CTkEntry(head, textvariable=self.var_number, width=54, height=26, justify="center")
        self.entry_number.grid(row=0, column=5, padx=4)
        self.entry_number.bind("<FocusOut>", lambda _e: self._pad_number())
        self.var_number.trace_add("write", self._on_number)
        self.var_clip_name.trace_add("write", self._on_clip_name)
        self.lbl_model = ctk.CTkLabel(head, text=tr("Model"))
        self.lbl_model.grid(row=0, column=6, padx=(14, 4), sticky="w")
        self.var_model = tk.StringVar()
        self.menu_model = ctk.CTkOptionMenu(
            head, values=list(MODELS), variable=self.var_model, width=118, height=26, command=self._switch_model, state="disabled"
        )
        self.menu_model.grid(row=0, column=7, padx=(4, 8), sticky="w")
        head.grid_columnconfigure(8, weight=1)
        info = ctk.CTkFrame(head, fg_color="transparent")   # checksum and file, right-aligned in the control row
        info.grid(row=0, column=8, sticky="e", padx=(8, 8))
        self.lbl_status = ctk.CTkLabel(info, text=tr("No file loaded"), anchor="e")
        self.lbl_status.pack(side="right", padx=(6, 0))
        self.lbl_sum = ctk.CTkLabel(info, text="")
        self.lbl_sum.pack(side="right", padx=(6, 10))


        self.messages = messages = ctk.CTkFrame(self, fg_color="transparent", height=0)
        self.lbl_scene_hint = AutoHideInfo(messages)
        self.lbl_scene_hint.grid(row=0, column=0, padx=8, sticky="w")
        self.lbl_scene_hint.grid_remove()
        self.lbl_switch = AutoHideInfo(messages)
        self.lbl_switch.grid(row=1, column=0, padx=8, sticky="w")
        self.lbl_switch.grid_remove()
        self.lbl_warn = AutoHideLabel(messages, text="", text_color=WARNING_COLOR, anchor="w", justify="left", wraplength=840)
        self.lbl_warn.grid(row=2, column=0, padx=8, sticky="w")
        self.lbl_warn.grid_remove()   # only shown while there are plausibility warnings

        for label in (self.lbl_scene_hint, self.lbl_switch, self.lbl_warn):
            label.on_change = self._sync_messages
        filt = ctk.CTkFrame(self)
        self._filt = filt
        filt.pack(fill="x", padx=8, pady=(2, 2))
        ctk.CTkLabel(filt, text=tr("Search")).pack(side="left", padx=(10, 6), pady=3)
        self.var_search = tk.StringVar()
        self.entry_search = ctk.CTkEntry(filt, textvariable=self.var_search, width=240, height=26)
        self.entry_search.pack(side="left", padx=4)
        self.entry_search.bind("<Escape>", lambda _e: self._clear_filter())
        self.var_search.trace_add("write", lambda *_a: self._schedule_filter())
        self.var_changed = tk.BooleanVar(value=False)
        self.var_known = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(filt, text=tr("changed only"), variable=self.var_changed, command=self._schedule_filter, width=20, checkbox_width=20, checkbox_height=20).pack(side="left", padx=(12, 4))
        ctk.CTkCheckBox(filt, text=tr("known only"), variable=self.var_known, command=self._schedule_filter, width=20, checkbox_width=20, checkbox_height=20).pack(side="left", padx=(8, 4))
        ctk.CTkButton(filt, text="✕", width=30, height=26, command=self._clear_filter).pack(side="left", padx=(8, 4))
        ctk.CTkButton(filt, text=tr("Expand all"), width=self._tr_width("Expand all", 100), height=26, command=self.expand_all).pack(side="left", padx=(20, 2))
        ctk.CTkButton(filt, text=tr("Collapse all"), width=self._tr_width("Collapse all", 100), height=26, command=self.collapse_all).pack(side="left", padx=2)
        self.lbl_filter = ctk.CTkLabel(filt, text="", text_color="gray")
        self.lbl_filter.pack(side="right", padx=12)
        jump = ctk.CTkFrame(self, fg_color="transparent")      # jump buttons: no long scrolling between the blocks
        jump.pack(fill="x", padx=8, pady=(0, 2))
        ctk.CTkLabel(jump, text=tr("Go to"), text_color="gray").pack(side="left", padx=(10, 6))
        self.jump_buttons = {}
        jump_width = max(self._tr_width(title, 90) for _g, title in GROUPS) + 24      # all buttons as wide as the longest one
        for group, title in GROUPS:
            label = f"{GROUP_ICONS[group]}  {tr(title)}"
            self.jump_buttons[group] = ctk.CTkButton(jump, text=label, width=jump_width, height=26, command=lambda g=group: self.jump_to(g))
            self.jump_buttons[group].pack(side="left", padx=2)
            self.jump_buttons[group].configure(state="disabled")      # enabled once the shown file has such a block

        self._tables: dict[tuple, dict] = {}     # built tables of the profiles (type, model) that are not shown at the moment
        self._active_key: tuple | None = None
        self.table = self._new_table()
        self.table.pack(fill="both", expand=True, padx=8, pady=(2, 8))

    def _new_table(self):
        table = ctk.CTkScrollableFrame(self)
        quiet_scrollbar(table._scrollbar)
        table._parent_canvas.bind("<Configure>", lambda e: self._schedule_reflow(), add="+")
        table.grid_columnconfigure(0, weight=1)
        return table

    # -- actions ----------------------------------------------------------- #
    def open_file(self):
        path = filedialog.askopenfilename(
            title=tr("Open file"),
            initialdir=str(self._last_dir) if self._last_dir else None,
            filetypes=[
                ("Sony SCENE/ALL File", "*.SCENE *.ALL"),
                ("Sony SCENE File", "*.SCENE"),
                ("Sony ALL File", "*.ALL"),
                (tr("All files"), "*.*"),
            ],
        )
        if path and self._confirm_discard(tr("Open")):
            self.open_path(Path(path))

    def new_file(self):
        """Ask for the camera (FS7 / FS7M2) and start a new file from its templates (SCENE and ALL profile, switchable)."""
        if not self._confirm_discard(tr("New")):
            return
        dialog = ModelDialog(self)
        dialog.after(50, dialog.grab_set)
        self.wait_window(dialog)
        if dialog.result:
            self.new_for_model(dialog.result)

    def new_for_model(self, model: str) -> bool:
        params = new_scene_params(model)
        if params is None:
            messagebox.showwarning(APP_NAME, tr("There is no template for {model}.").format(model=model))
            return False
        self.scene = SceneFile(name="NEW", model=model, params=params)
        self._adopt("scene")
        self.lbl_status.configure(text=tr("New (neutral values, not a factory state)"))
        return True

    def open_path(self, path: Path) -> bool:
        """Load a file by extension (also used for the command line). Shows an error dialog on failure."""
        ext = path.suffix.lower()
        loader = LOADERS.get(ext)
        if loader is None:
            if ext in FILE_TYPES:
                msg = tr("{type} ({name}) is not supported yet (no sample files).").format(type=FILE_TYPES[ext], name=path.name)
            else:
                msg = tr("Unknown file type {ext}. Supported: {types}").format(ext=repr(path.suffix), types=", ".join(sorted(FILE_TYPES)))
            messagebox.showwarning(APP_NAME, msg)
            return False
        try:
            self.scene = loader(path)
        except (SceneFileError, OSError) as exc:
            messagebox.showerror(APP_NAME, tr("The file could not be read:\n{error}").format(error=exc))
            return False
        self._last_dir = path.parent
        save_settings(last_dir=str(path.parent))
        self.scene.number = path.stem if len(path.stem) == 3 and path.stem.isdigit() else ""
        return self._adopt("all" if ext == ".all" else "scene")

    def _adopt(self, kind: str) -> bool:
        """Make self.scene the current file of the given type (session, parameter database, table)."""
        self.kind = kind
        self._stash = {}
        self.param_db = load_param_db(kind)
        self.locks = load_param_locks(kind)
        models = param_db_models(kind)
        db_applies = models is None or self.scene.model in models
        if not db_applies:
            self.param_db = {}  # IDs of another model would be labelled wrongly
            self.locks = []
        can_models = self.scene.model in MODELS and db_applies
        can_kind = self.scene.model in load_id_map() and db_applies
        self.session = SceneSession(self.scene, self.param_db, self.rules, kind) if (can_models or can_kind) else None
        if self.session and kind == "scene" and can_kind:
            self.lbl_switch.configure(text="")
        elif self.session and kind == "scene":
            self.lbl_switch.configure(text=tr("Switching between SCENE and ALL exists only for {models} so far (no mapping for {model}).").format(
                models=", ".join(load_id_map()), model=self.scene.model))
        elif self.session:
            self.lbl_switch.configure(text="")   # nothing to report: the disabled model menu already shows that
        elif kind == "all" and not db_applies:
            self.lbl_switch.configure(text=tr("ALL file for {model}: the parameter mapping applies to {models} only so far; only raw values are shown.").format(
                model=self.scene.model, models=", ".join(models)))
        else:
            self.lbl_switch.configure(text=tr("The model {model} does not support a model switch.").format(model=repr(self.scene.model)))
        if not self.scene.checksum_ok:      # a file edited by hand: say so, saving with the program repairs it
            note = tr("Checksum wrong: the file was probably edited by hand. It is repaired when you save.")
            current = self.lbl_switch.cget("text")
            self.lbl_switch.configure(text=f"{note}\n{current}" if current else note)
        self._saved = None
        if self._can_refresh_in_place():
            self._refresh_in_place(reset_original=True)
        else:
            self._populate()
        self._history_reset()
        if PARAM_DB_ERRORS.get(kind):
            messagebox.showerror(APP_NAME, tr("The parameter database could not be read, only raw values are shown:\n{error}\n\nCheck the file and open it again.").format(
                error=PARAM_DB_ERRORS[kind]))
        return True

    TABLE_STATE = ("table", "entries", "vars", "_groups", "_rows", "_subheads", "_cats", "_lazy_groups", "_reflow",
                   "_built_model", "_built_kind", "_built_db", "_built_look")

    def _look(self) -> tuple:
        """What the built widgets depend on besides the values: a table built for another look must be rebuilt."""
        return (SHOW_RAW_VALUES, LANG, self._scale, ctk.get_appearance_mode())

    def _table_key(self) -> tuple:
        return (self.kind, self.scene.model)

    def _table_valid(self, state: dict) -> bool:
        return state["_built_db"] == self.param_db and state["_built_look"] == self._look() and set(state["vars"]) == set(self.scene.params)

    def _swap_table(self, key: tuple, state: dict):
        """Show the table that was built earlier for the profile `key`; the table shown so far is kept for the way back."""
        if self._active_key is not None:
            self._tables[self._active_key] = {a: getattr(self, a) for a in self.TABLE_STATE}
        self.table.pack_forget()
        for attr, value in state.items():
            setattr(self, attr, value)
        self._row_parent = self.table
        self._active_key = key

    def _drop_tables(self):
        for state in self._tables.values():
            state["table"].destroy()
        self._tables = {}

    def _populate(self, reset_original: bool = True):
        """Show the parameter table of the current profile (type, model): a table built before is reused (only its values are
        updated), otherwise it is built. Building takes seconds for an ALL file (about 1000 widgets), so every profile keeps its
        table while it is not shown; the table is taken off the screen while it is built: every new widget otherwise triggers
        a layout of the whole window."""
        key = self._table_key()
        state = self._tables.pop(key, None)
        if state is not None and (key == self._active_key or not self._table_valid(state)):
            state["table"].destroy()
            state = None
        if state is not None:
            self._swap_table(key, state)         # not shown yet: its values are updated before it is laid out
            self._table_header()
            self._refresh_in_place(reset_original)
            self._table_footer()
            self.table.pack(fill="both", expand=True, padx=8, pady=(2, 8))
            self.update_idletasks()
            self._reflow_all()
            return
        if key != self._active_key and self._active_key is not None and self.vars:
            self._tables[self._active_key] = {a: getattr(self, a) for a in self.TABLE_STATE}      # keep the table we leave
            self.table.pack_forget()
            self.table = self._new_table()
            self.entries, self.vars = {}, {}
        else:
            self._drop_tables()      # rebuilt for a new look (language, scale, raw values) or database: the others are stale
        scroll = self.table._parent_canvas.yview()[0]
        self._scroll_hint = scroll
        canvas = self.table._parent_canvas
        scroll_command = canvas.cget("yscrollcommand")
        canvas.configure(yscrollcommand="")   # the scrollbar redraw after every new row is the slowest part
        self.table.pack_forget()
        try:
            with lazy_layout():
                self._populate_rows(reset_original)
        finally:
            self.table.pack(fill="both", expand=True, padx=8, pady=(2, 8))
            canvas.configure(yscrollcommand=scroll_command)
        self._active_key = key
        self.update_idletasks()
        self._reflow_all()
        self.table._parent_canvas.yview_moveto(scroll)

    def _reflow_all(self):
        """Lay out the wrapped fields of step widgets for the current width of the table."""
        self._reflow_job = None
        available = self.table._parent_canvas.winfo_width() - self._sc(330)    # minus label column, margins and scroll bar
        if available <= 0:
            return
        for widget in self._reflow:
            try:
                widget._relayout(available)
            except tk.TclError:
                pass

    def _schedule_reflow(self, _event=None):
        if self._reflow_job is not None:
            self.after_cancel(self._reflow_job)
        self._reflow_job = self.after(120, self._reflow_all)

    def _populate_rows(self, reset_original: bool = True):
        s = self.scene
        self._busy = True
        scroll = self._scroll_hint
        for w in self.table.winfo_children():
            w.destroy()
        self.entries.clear()
        self.vars.clear()
        if reset_original:
            self.original = dict(s.params)
        self.var_name.set(s.name)
        self.var_number.set(s.number)
        self._table_header()
        self._built_model = s.model
        self._built_kind = self.kind
        self._built_db = self.param_db
        self._built_look = self._look()
        self._groups = {}
        self._rows = {}
        self._subheads = []
        self._cats = []
        self._lazy_groups = set()
        self._reflow = []
        by_group = {g: [] for g, _title in GROUPS}
        for key, value in s.params.items():
            info = self.param_db.get(key)
            by_group[info.get("group", "misc") if info else "unknown"].append((key, value, info))

        def sort_key(item):
            key, _value, info = item
            sub = info.get("subgroup", "Other") if info else ""
            order = info.get("order", 99) if info else 99
            return (SUBGROUP_ORDER.index(sub) if sub in SUBGROUP_ORDER else len(SUBGROUP_ORDER), sub, order, key)

        table_row = 0
        for group, title in GROUPS:
            items = sorted(by_group[group], key=sort_key)
            if not items:
                continue
            sep = self._separator(self.table, "main", row=table_row, column=0, pady=(self._sc(10), 0)) if table_row else None
            header = ctk.CTkButton(
                self.table, text="", anchor="w", height=32, corner_radius=6,
                fg_color=("gray75", "gray25"), hover_color=("gray70", "gray30"), text_color=("gray10", "gray90"),
                command=lambda g=group: self._toggle_group(g),
            )
            header.grid(row=table_row + 1, column=0, sticky="ew", padx=self._sc(2), pady=(self._sc(6), self._sc(2)))
            container = tk.Frame(self.table, bg=self._c["bg"])
            container.grid(row=table_row + 2, column=0, sticky="ew")
            container.grid_columnconfigure(0, minsize=self._sc(310))
            container.grid_columnconfigure(1, weight=1)
            self._groups[group] = {"title": tr(title), "header": header, "container": container, "count": len(items),
                                   "keys": [k for k, _v, _i in items], "visible": len(items), "sep": sep}
            self._row_parent = container
            row, current_sub, sub_info = 0, None, None
            if group == "unknown" and self._collapsed.get(group, group in DEFAULT_COLLAPSED):
                # the collapsed block of unknown parameters (about 250 rows of an ALL file) is built when it is opened
                for key, value, _info in items:
                    var = tk.StringVar(value=value)
                    var.trace_add("write", lambda *_a, k=key: self._on_edit(k))
                    self.vars[key] = var
                    self._rows[key] = {"label": None, "widget": None, "sub": None, "info": None, "lazy": True}
                self._lazy_groups.add(group)
                self._apply_group_state(group)
                table_row += 3
                continue
            card, card_row, first_sub = container, 0, True
            for key, value, info in items:
                sub = (info.get("subgroup", "Other") if info else None)
                if sub is not None and sub != current_sub:
                    category = sub.split(" › ")[0] if " › " in sub and sub.split(" › ")[0] in CATEGORIES else None
                    if category and not any(c["title"] == category for c in self._cats):
                        cat_sep = self._separator(container, "main", row=row, column=0, columnspan=2, pady=(self._sc(12), 0))
                        cat_label = tk.Label(container, text="", anchor="w", bg=self._c["bg"], fg=self._c["label"], font=self._font_bold, cursor="hand2")
                        cat_label.grid(row=row + 1, column=0, columnspan=2, sticky="w", padx=self._sc(5), pady=(self._sc(6), self._sc(2)))
                        cat_info = {"label": cat_label, "sep": cat_sep, "title": category, "subs": []}
                        cat_label.bind("<Button-1>", lambda _e, ci=cat_info: self._toggle_cat(ci))
                        self._set_cat_text(cat_info)
                        self._cats.append(cat_info)
                        row += 2
                        first_sub = True
                    # every sub-group is a rounded card (slightly different fill); a thin light line separates it from the previous one
                    wrap = tk.Frame(container, bg=self._c["bg"])
                    wrap.grid(row=row, column=0, columnspan=2, sticky="ew", padx=(self._sc(24 if category else 5), self._sc(5)))
                    wrap.grid_columnconfigure(0, weight=1)
                    if not first_sub:
                        self._separator(wrap, "sub", row=0, column=0, pady=(self._sc(5), self._sc(5)))
                    first_sub = False
                    card = ctk.CTkFrame(wrap, corner_radius=10, fg_color=self._c["card"], border_width=1, border_color=self._c["card_border"])
                    card.grid(row=1, column=0, sticky="ew", ipady=self._sc(3))
                    card.grid_columnconfigure(0, minsize=self._sc(300))
                    card.grid_columnconfigure(1, weight=1)
                    heading = tk.Label(card, text=sub, anchor="w", bg=self._c["card"], fg=self._c["accent"], font=self._font_bold, cursor="hand2")
                    heading.grid(row=0, column=0, columnspan=2, sticky="w", padx=self._sc(10), pady=(self._sc(6), self._sc(2)))
                    sub_info = {"label": heading, "outer": wrap, "keys": [], "title": sub, "suffix": "", "category": category,
                                "display": sub.split(" › ", 1)[1] if category else sub}
                    if category:
                        next(c for c in self._cats if c["title"] == category)["subs"].append(sub_info)
                    heading.bind("<Button-1>", lambda _e, si=sub_info: self._toggle_sub(si))
                    self._set_sub_text(sub_info)
                    self._subheads.append(sub_info)
                    current_sub, row, card_row = sub, row + 1, 1
                parent, prow = (card, card_row) if sub is not None else (container, row)
                self._row_parent = parent
                name_label = self._row_label(parent, key, info, self._c["card"] if sub is not None else None)
                name_label.grid(row=prow, column=0, padx=self._sc(10 if sub is not None else 5), pady=self._sc(1), sticky="w")
                var = tk.StringVar(value=value)
                var.trace_add("write", lambda *_a, k=key: self._on_edit(k))
                widget = self._build_choice_widget(key, var, info.get("widget") if info else None)
                if widget is None:
                    widget = tk.Entry(
                        parent, textvariable=var, bg=self._c["entry"], fg=self._c["text"], insertbackground=self._c["text"],
                        relief="flat", highlightthickness=self._sc(1), highlightbackground=self._c["border"],
                        highlightcolor=self._c["focus"], font=self._c["font"],
                    )
                    widget.grid(row=prow, column=1, padx=self._sc(5), pady=self._sc(2), sticky="ew", ipady=self._sc(2))
                    outer = None
                elif hasattr(widget, "_mark"):
                    widget.grid(row=prow, column=1, padx=5, pady=2, sticky="w")
                    outer = None
                else:
                    # widgets whose children fill the whole frame (step fields, multi-choice) get an outer frame for the yellow "changed" border:
                    # a border on the widget itself would be covered by its own children
                    outer = ctk.CTkFrame(parent, fg_color="transparent", border_width=2, border_color=self._c["card"], corner_radius=4)
                    outer.grid(row=prow, column=1, padx=3, pady=2, sticky="w")
                    widget.grid(in_=outer, row=0, column=0, padx=5, pady=5, sticky="w")
                    widget.lift()
                    widget._mark = outer
                self.vars[key], self.entries[key] = var, widget
                self._rows[key] = {"label": name_label, "widget": widget, "outer": outer, "sub": sub_info if sub is not None else None, "info": info}
                if sub is not None:
                    sub_info["keys"].append(key)
                    card_row += 1
                else:
                    row += 1
            self._apply_group_state(group)
            table_row += 3
        self._row_parent = self.table
        for wkey, widget in self.entries.items():
            deps = getattr(widget, "_derived_deps", None)
            if deps:
                for pid in deps:
                    if pid in self.vars:
                        self.vars[pid].trace_add("write", lambda *_a, w=widget, k=wkey: (w._refresh(), self._paint_mark(k)))
                widget._refresh()
        self._table_footer()
        self.update_idletasks()
        self.table._parent_canvas.yview_moveto(scroll)

    def _table_header(self):
        """Header controls for the profile that is shown (type, model, locks)."""
        self.var_kind.set(self.kind.upper())
        self.var_model.set(self.scene.model)
        self.menu_model.configure(state="normal" if self.session and self.scene.model in MODELS else "disabled")
        self.seg_kind.configure(state="normal" if self.session and self.session.can_switch_kind() else "disabled")
        self._update_lock_marks()

    def _table_footer(self):
        """Everything around the table that depends on the file: clip row, filter, buttons, checksum, status line."""
        s = self.scene
        self._busy = True
        self._update_clip_row()
        self._apply_filter()
        for group, button in self.jump_buttons.items():       # SCENE files have no Audio / Miscellaneous parameters: their buttons are greyed out
            button.configure(state="normal" if group in self._groups else "disabled")
        self.btn_save.configure(state="normal")
        self.btn_save_as.configure(state="normal")
        self.btn_import.configure(state="normal")
        self.btn_compare.configure(state="normal")
        self.lbl_sum.configure(
            text=tr("Checksum OK") if s.checksum_ok else tr("Checksum WRONG"),
            text_color="#4caf50" if s.checksum_ok else "#e57373",
        )
        self.lbl_status.configure(text=f"…\\{s.path.parent.name}\\{self._file_label()}" if s.path else "")
        self._busy = False
        self._update_history_buttons()

    def _menu_width(self, labels: list[str], minimum: int) -> int:
        """Width of a dropdown (unscaled pixels) that shows the longest of the labels completely."""
        if not labels:
            return minimum
        return max(minimum, round(self._font.measure(max(labels, key=len)) / self._scale) + 56)

    def _row_label(self, container, key: str, info: dict | None, bg: str | None = None) -> "RowLabel":
        """Name of a row: decoded text (with status) and the ID in grey brackets behind it; rows without a name show the ID."""
        if info and SHOW_RAW_VALUES:
            text = info["name"] + (f" [{tr_status(info.get('status'))}]" if info.get("status") != "confirmed" else "")
            ident = f"({key})"
        elif info:
            text = f"{key}  {info['name']}" + (f" [{tr_status(info.get('status'))}]" if info.get("status") != "confirmed" else "")
            ident = ""
        else:
            text, ident = key, ""
        return RowLabel(container, text, ident, bg or self._c["bg"], self._c["label"], self._c["font"], self._sc(235 if ident else 300))

    def _ensure_built(self, group: str):
        """Build the rows of a block that was left unbuilt while it was collapsed."""
        if group not in self._lazy_groups:
            return
        self._lazy_groups.discard(group)
        container = self._groups[group]["container"]
        row = 0
        for key in self._groups[group]["keys"]:
            var = self.vars[key]
            name_label = self._row_label(container, key, None)
            name_label.grid(row=row, column=0, padx=self._sc(5), pady=self._sc(1), sticky="w")
            changed = var.get() != self.original.get(key)
            widget = tk.Entry(
                container, textvariable=var, bg=self._c["entry"], fg=self._c["text"], insertbackground=self._c["text"],
                relief="flat", highlightthickness=self._sc(1), highlightbackground=CHANGED_COLOR if changed else self._c["border"],
                highlightcolor=self._c["focus"], font=self._c["font"],
            )
            widget.grid(row=row, column=1, padx=self._sc(5), pady=self._sc(2), sticky="ew", ipady=self._sc(2))
            self.entries[key] = widget
            self._rows[key].update({"label": name_label, "widget": widget, "lazy": False})
            row += 1

    def _apply_group_state(self, group: str):
        info = self._groups[group]
        collapsed = self._collapsed.get(group, group in DEFAULT_COLLAPSED)
        info["header"].configure(text=f"{'▶' if collapsed else '▼'}   {GROUP_ICONS[group]}  {info['title']}   ({info['count']})")
        if collapsed:
            info["container"].grid_remove()
        else:
            info["container"].grid()

    # -- search and filter ------------------------------------------------------ #
    def _filter_active(self) -> bool:
        return bool(self.var_search.get().strip() or self.var_changed.get() or self.var_known.get())

    def _schedule_filter(self):
        if self._filter_job is not None:
            self.after_cancel(self._filter_job)
        self._filter_job = self.after(FILTER_DELAY_MS, self._apply_filter)

    def _clear_filter(self):
        self.var_search.set("")
        self.var_changed.set(False)
        self.var_known.set(False)
        self._apply_filter()

    def _row_matches(self, key: str, tokens: list[str], changed_only: bool, known_only: bool) -> bool:
        info = self._rows[key]["info"]
        if known_only and info is None:
            return False
        if changed_only and self.vars[key].get() == self.original.get(key):
            return False
        if tokens:
            sub = info.get("subgroup", "") if info else ""
            haystack = f"{key} {info['name'] if info else ''} {info.get('status', '') if info else ''} {sub} {self.vars[key].get()}".lower()
            return all(t in haystack for t in tokens)
        return True

    def _apply_filter(self):
        """Show only the matching parameters (blocks with matches are opened while a filter is active)."""
        if self._filter_job is not None:
            try:
                self.after_cancel(self._filter_job)
            except ValueError:
                pass
            self._filter_job = None
        if not self.scene:
            return
        tokens = self.var_search.get().strip().lower().split()
        changed_only, known_only = self.var_changed.get(), self.var_known.get()
        active = bool(tokens or changed_only or known_only)
        if active:
            for group in list(self._lazy_groups):
                self._ensure_built(group)
        shown_keys: set[str] = set()
        for group, info in self._groups.items():
            visible = 0
            for key in info["keys"]:
                row = self._rows[key]
                if row.get("lazy"):
                    visible += 1       # not built yet (collapsed block, no filter): nothing to show or hide
                    continue
                sub = row["sub"]
                show = self._row_matches(key, tokens, changed_only, known_only) if active else not (sub and (sub["title"] in self._sub_collapsed or sub.get("category") in self._cat_collapsed))
                if row["info"] and row["info"].get("covered_by") and not (tokens and show):
                    show = False   # part of a combined dropdown (e.g. Gamma Category): visible only when searched for explicitly
                for widget in (row["label"], row.get("outer") or row["widget"]):
                    widget.grid() if show else widget.grid_remove()
                if show:
                    visible += 1
                    shown_keys.add(key)
            info["visible"] = visible
            if active:
                count_text = tr("{n} of {total}").format(n=visible, total=info["count"])      # no nested quotes in the f-string (Python < 3.12)
                info["header"].configure(text=f"▼   {GROUP_ICONS[group]}  {info['title']}   ({count_text})")
                for part in (info["sep"], info["header"], info["container"]):
                    if part is not None:
                        part.grid() if visible else part.grid_remove()
            else:
                if info["sep"] is not None:
                    info["sep"].grid()
                info["header"].grid()
                self._apply_group_state(group)
        for sub in self._subheads:
            hidden = (active and not any(k in shown_keys for k in sub["keys"])) or (not active and sub.get("category") in self._cat_collapsed)
            sub["outer"].grid_remove() if hidden else sub["outer"].grid()
        for cat in self._cats:
            shown = any(k in shown_keys for sub in cat["subs"] for k in sub["keys"]) if active else True
            for part in (cat["sep"], cat["label"]):
                part.grid() if shown else part.grid_remove()
            self._set_cat_text(cat)
        total = sum(1 for row in self._rows.values() if not (row["info"] and row["info"].get("covered_by")))   # rows of combined dropdowns are not listed
        self.lbl_filter.configure(text=tr("{n} of {total}").format(n=len(shown_keys) if active else total, total=total))

    def _set_sub_text(self, sub: dict):
        arrow = "▶" if sub["title"] in self._sub_collapsed else "▼"
        sub["label"].configure(text=f"{arrow}  {sub.get('display', sub['title'])}{sub['suffix']}")

    def _set_cat_text(self, cat: dict):
        arrow = "▶" if cat["title"] in self._cat_collapsed and not self._filter_active() else "▼"
        cat["label"].configure(text=f"{arrow}  {cat['title']}")

    def _toggle_cat(self, cat: dict):
        if self._filter_active():
            return   # matches stay visible while a filter is active
        self._cat_collapsed ^= {cat["title"]}
        self._apply_filter()

    def _toggle_sub(self, sub: dict):
        if self._filter_active():
            return   # matches stay visible while a filter is active
        self._sub_collapsed ^= {sub["title"]}
        for sinfo in self._subheads:
            if sinfo["title"] == sub["title"]:
                self._set_sub_text(sinfo)
        self._apply_filter()

    def expand_all(self):
        """Open every block, category and sub-group (the collapsed block of unknown parameters is built now)."""
        if not self.scene:
            return
        self._cat_collapsed.clear()
        self._sub_collapsed.clear()
        for group in self._groups:
            self._collapsed[group] = False
            self._ensure_built(group)
        self._after_fold_change()

    def collapse_all(self):
        """Close every block, category and sub-group."""
        if not self.scene:
            return
        self._cat_collapsed |= {cat["title"] for cat in self._cats}
        self._sub_collapsed |= {sub["title"] for sub in self._subheads}
        for group in self._groups:
            self._collapsed[group] = True
        self._after_fold_change()

    def _after_fold_change(self):
        for cat in self._cats:
            self._set_cat_text(cat)
        for sub in self._subheads:
            self._set_sub_text(sub)
        self._apply_filter()

    def jump_to(self, group: str):
        """Open a block (if it is closed) and scroll the table so that its header is at the top."""
        if not self.scene or group not in self._groups:
            return
        if not self._filter_active() and self._collapsed.get(group, group in DEFAULT_COLLAPSED):
            self._collapsed[group] = False
            self._ensure_built(group)
            self._apply_group_state(group)
        header = self._groups[group]["header"]
        if not header.winfo_manager():
            return      # the block has no match for the current filter
        self.update_idletasks()
        total = max(1, self.table.winfo_height())
        self.table._parent_canvas.yview_moveto(max(0.0, (header.winfo_y() - self._sc(4)) / total))

    def _toggle_group(self, group: str):
        if self._filter_active():
            return   # blocks with matches stay open while a filter is active
        self._collapsed[group] = not self._collapsed.get(group, group in DEFAULT_COLLAPSED)
        if not self._collapsed[group]:
            self._ensure_built(group)
        self._apply_group_state(group)

    def _build_choice_widget(self, key: str, var: tk.StringVar, spec: dict | None):
        """Dropdown row for enumerable parameters; None if the value does not fit the spec."""
        if not spec:
            return None
        if spec["type"] == "stepfields":
            return self._build_step_widget(var, spec)
        if spec["type"] == "multichoice":
            return self._build_multichoice_widget(key, var, spec)
        if spec["type"] == "counter":
            return self._build_counter_widget(var, spec)
        if spec["type"] == "derived":
            return self._build_derived_widget(key, var, spec)
        if spec["type"] == "checkbox":
            return self._build_checkbox_widget(var, spec)
        if spec["type"] == "axis_pairs":
            return self._build_axis_widget(var, spec)
        fields = spec["fields"] if spec["type"] == "fields" else [{"index": None, "choices": spec["choices"]}]
        parts = var.get().split(",")
        if any(f["index"] is not None and f["index"] >= len(parts) for f in fields) or len(parts) < spec.get("min_fields", 0):
            return None       # another camera model stores a different shape: the plain text field is shown

        frame = ctk.CTkFrame(self._row_parent, fg_color="transparent", border_width=0, border_color=CHANGED_COLOR)
        menu_row = self._marked_row(frame)   # the "changed" frame goes around the controls only, not around the notes below
        menus: list = []

        def current(idx):
            raw = var.get()
            return (raw.split(",")[idx] if idx is not None else raw).strip()

        def make_menu(f):
            idx = f["index"]
            only = f.get("only_models", {})
            choices = {k: with_raw(v, k) for k, v in f["choices"].items() if self.scene.model in only.get(k, [self.scene.model])}
            labels = list(choices.values())
            cur = current(idx)
            if cur not in choices:
                labels.append(tr("{value} (unknown)").format(value=cur))
            readonly = spec.get("readonly", False)
            menu = ctk.CTkOptionMenu(menu_row, values=labels, width=self._menu_width(list(f["choices"].values()) + labels, 190), dynamic_resizing=False,
                                     state="disabled" if readonly else "normal")
            menu.set(choices.get(cur, tr("{value} (unknown)").format(value=cur)))

            def pick(label):
                new = next((k for k, v in choices.items() if v == label), None)
                if new is None:
                    return
                self._last_key = None   # every dropdown choice is its own undo step (only typing is merged)
                old = current(idx)
                # values this choice is going to replace belong to the choice that is left: remember them
                remembered = (spec.get("remember") or {}).get(new)
                if remembered and old != new:
                    self._stash[(key, old)] = {pid: self.vars[pid].get() for pid in remembered if pid in self.vars}
                if idx is None:
                    var.set(new)
                else:
                    items = var.get().split(",")
                    lead = items[idx][: len(items[idx]) - len(items[idx].lstrip())]
                    items[idx] = lead + new
                    var.set(",".join(items))
                # values the camera changes by itself with this choice (taken from sample files) ...
                self._apply_companions(key, spec.get("companions", {}).get(new))
                # ... and the values of the last time this choice was active come back
                if old != new and (key, new) in self._stash:
                    self._set_values(key, self._stash[(key, new)])

            menu.configure(command=pick)
            menu.pack(side="left", padx=(0, 6))
            menu._enabled_when = f.get("enabled_when")   # e.g. the preset is only selectable while the preset matrix is On
            menus.append((menu, idx, choices))

        for f in fields:
            make_menu(f)

        def availability():
            for menu, idx, choices in menus:
                cur = current(idx)
                labels = list(choices.values()) + ([] if cur in choices else [tr("{value} (unknown)").format(value=cur)])
                disabled = {}
                for k, v in choices.items():
                    ok, reason = self._option_state(spec.get("requires", {}).get(k))
                    if not ok:
                        disabled[v] = reason
                self._fill_menu(menu, labels, disabled)
                rule = getattr(menu, "_enabled_when", None)
                if rule and not hasattr(menu, "_state_before_lock"):      # a row lock (greyed row) has priority
                    menu.configure(state="normal" if current(rule["field"]) in rule["in"] else "disabled")

        def refresh():
            for menu, idx, choices in menus:
                cur = current(idx)
                menu.set(choices.get(cur, tr("{value} (unknown)").format(value=cur)))
            availability()

        def warning() -> str:
            for _menu, idx, choices in menus:
                cur = current(idx)
                ok, reason = self._option_state(spec.get("requires", {}).get(cur))
                if not ok:
                    return f"{choices.get(cur, cur)}: {reason}"
            return ""

        frame._refresh = refresh
        frame._availability = availability
        frame._warning = warning
        raw = ctk.CTkLabel(menu_row, text=tr("Raw value: {value}").format(value=var.get()), text_color="gray")
        raw.pack(side="left", padx=4)
        var.trace_add("write", lambda *_a: raw.configure(text=tr("Raw value: {value}").format(value=var.get())))
        if spec.get("note"):
            note = InfoLabel(frame)
            note.set_info(spec["note"])
            note.pack(anchor="w", padx=4)
        return frame

    def _build_derived_widget(self, key: str, var: tk.StringVar, spec: dict):
        """Dropdown whose choice is a combination of values in several parameters (e.g. Gamma Category = a set of flags).

        option["match"]  {id: {field: value}}: the option is shown while all of these values are set
        option["set"]    {id: {field: value}}: written when the option is picked (plus set_models[model] and the "set_if" rules)
        """
        options = spec["options"]
        selects = {label: dict(sel, choices={k: with_raw(v, k) for k, v in sel["choices"].items()})
                   for label, sel in spec.get("selects", {}).items()}     # option label -> {"id", "field", "choices"}: the second dropdown follows the first
        frame = ctk.CTkFrame(self._row_parent, fg_color="transparent", border_width=0, border_color=CHANGED_COLOR)
        row = self._marked_row(frame)
        ctk.CTkLabel(row, text=spec.get("label", ""), text_color="gray").pack(side="left", padx=(0, 6)) if spec.get("label") else None
        menu = ctk.CTkOptionMenu(row, values=[o["label"] for o in options], width=self._menu_width([o["label"] for o in options], 150), dynamic_resizing=False)
        menu.pack(side="left")
        select_menu = None
        if selects:
            ctk.CTkLabel(row, text=spec.get("select_label", "Select"), text_color="gray").pack(side="left", padx=(14, 6))
            select_menu = ctk.CTkOptionMenu(row, values=["–"], width=self._menu_width([v for sel in selects.values() for v in sel["choices"].values()], 210), dynamic_resizing=False)
            select_menu.pack(side="left")

        def holds(option) -> bool:
            return all(self._field_value(pid, int(f)) == v for pid, fields in option["match"].items() for f, v in fields.items())

        def current_label() -> str:
            return next((o["label"] for o in options if holds(o)), tr("unknown combination"))

        def pick(label):
            option = next((o for o in options if o["label"] == label), None)
            if option is None:
                return
            self._last_key = None   # every dropdown choice is its own undo step
            values = {pid: dict(fields) for pid, fields in option["set"].items()}
            for pid, fields in option.get("set_models", {}).get(self.scene.model, {}).items():
                values.setdefault(pid, {}).update(fields)
            for rule in option.get("set_if", []):
                if self._cond_holds(rule["cond"]):
                    for pid, fields in rule["set"].items():
                        values.setdefault(pid, {}).update(fields)
            keep = spec.get("remember")     # settings that only exist in one option (Knee, Black Gamma in STD): off outside, the old state comes back in it
            if keep:
                old_label = current_label()
                if old_label == keep["option"] and label != old_label:
                    self._stash[(key, old_label)] = {pid: self._field_value(pid, 0) for pid in keep["ids"] if pid in self.vars}
                    for pid in keep["ids"]:
                        values.setdefault(pid, {})["0"] = "0"
                elif label == keep["option"] and old_label != label:
                    for pid, value in self._stash.get((key, label), {}).items():
                        if value is not None:
                            values.setdefault(pid, {})["0"] = value
            self._apply_companions(key, values)
            refresh()

        def refresh_select(label):
            if select_menu is None:
                return
            sel = selects.get(label)
            if sel is None:        # categories without sub-options (S-Log2, S-Log3): select = category
                select_menu.configure(values=["–"], state="disabled")
                select_menu.set("–" if label in {o["label"] for o in options} else "")
                return
            now = self._field_value(sel["id"], int(sel.get("field", 0)))
            labels = list(sel["choices"].values()) + ([] if now in sel["choices"] else [tr("{value} (unknown)").format(value=now)])
            select_menu.configure(values=labels, state="normal")
            select_menu.set(sel["choices"].get(now, tr("{value} (unknown)").format(value=now)))

        def pick_select(label):
            sel = selects.get(current_label())
            if sel is None:
                return
            value = next((k for k, v in sel["choices"].items() if v == label), None)
            if value is None:
                return
            self._last_key = None   # every dropdown choice is its own undo step
            self._apply_companions(key, {sel["id"]: {str(sel.get("field", 0)): value}})
            refresh()

        def refresh():
            label = current_label()
            labels = [o["label"] for o in options] + ([] if any(o["label"] == label for o in options) else [label])
            disabled = {o["label"]: reason for o in options for ok, reason in [self._option_state(o.get("requires"))] if not ok}
            self._fill_menu(menu, labels, disabled)
            menu.set(label)
            refresh_select(label)

        menu.configure(command=pick)
        if select_menu is not None:
            select_menu.configure(command=pick_select)
        frame._refresh = refresh
        frame._availability = refresh
        frame._derived_deps = ({pid for o in options for pid in o["match"]} | {x["id"] for x in selects.values()}) - {key}
        raw = ctk.CTkLabel(row, text=tr("Raw value: {value}").format(value=var.get()), text_color="gray")
        raw.pack(side="left", padx=8)
        var.trace_add("write", lambda *_a: raw.configure(text=tr("Raw value: {value}").format(value=var.get())))
        if spec.get("note"):
            note = InfoLabel(frame)
            note.set_info(spec["note"])
            note.pack(anchor="w", padx=4)
        return frame

    def _build_axis_widget(self, var: tk.StringVar, spec: dict):
        """Multi Matrix: choose an axis, then edit its hue and saturation (like the camera menu). Axes with a value are marked."""
        axes, hue0, sat0, unit = spec["axes"], spec["hue_start"], spec["sat_start"], spec["unit"]
        lo, hi = spec["range"]
        max_raw, min_raw = spec.get("max_raw"), spec.get("min_raw")
        parts = var.get().split(",")
        if len(parts) < max(hue0, sat0) + len(axes):
            return None
        try:
            [int(x) for x in parts]
        except ValueError:
            return None
        frame = ctk.CTkFrame(self._row_parent, fg_color="transparent", border_width=0, border_color=CHANGED_COLOR)
        row = self._marked_row(frame)
        current_axis = tk.IntVar(value=0)

        def raw_of(start):
            return int(var.get().split(",")[start + current_axis.get()])

        def shown(start) -> int:
            return max(lo, min(hi, round(raw_of(start) / unit)))

        def write(start, new):
            new = max(lo, min(hi, new))
            if new != shown(start):
                raw = round(new * unit)
                if max_raw and abs(new) == hi:
                    raw = max_raw if new > 0 else min_raw
                items = var.get().split(",")
                items[start + current_axis.get()] = str(raw)
                var.set(",".join(items))

        def label_of(i):
            changed = int(var.get().split(",")[hue0 + i]) != 0 or int(var.get().split(",")[sat0 + i]) != 0
            return ("● " if changed else "   ") + axes[i]

        axis_cell = ctk.CTkFrame(row, fg_color="transparent")      # label above the dropdown like above the hue and saturation fields
        axis_cell.pack(side="left", padx=(0, 10))
        ctk.CTkLabel(axis_cell, text="Axis", text_color="gray").pack()
        menu = ctk.CTkOptionMenu(axis_cell, values=[label_of(i) for i in range(len(axes))], width=120, dynamic_resizing=False)
        menu.pack()
        controls = {}
        for start, name in ((hue0, "Hue"), (sat0, "Saturation")):
            cell = ctk.CTkFrame(row, fg_color="transparent")
            cell.pack(side="left", padx=4)
            ctk.CTkLabel(cell, text=name, text_color="gray").pack()
            line = ctk.CTkFrame(cell, fg_color="transparent")
            line.pack()
            entry = ctk.CTkEntry(line, width=52, justify="center")

            def bump(delta, start=start):
                self._last_key = None   # every click is its own undo step
                write(start, shown(start) + delta)
                refresh()

            def commit(_e=None, start=start, entry=entry):
                try:
                    write(start, int(entry.get().strip()))
                except ValueError:
                    pass
                refresh()

            for text, delta in (("−10", -10), ("−1", -1)):
                ctk.CTkButton(line, text=text, width=38, height=26, command=lambda d=delta, b=bump: b(d)).pack(side="left", padx=(0, 2))
            entry.pack(side="left", padx=2)
            for text, delta in (("+1", 1), ("+10", 10)):
                ctk.CTkButton(line, text=text, width=38, height=26, command=lambda d=delta, b=bump: b(d)).pack(side="left", padx=(2, 0))
            entry.bind("<Return>", commit)
            entry.bind("<FocusOut>", commit)
            controls[start] = entry

        def refresh():
            labels = [label_of(i) for i in range(len(axes))]
            menu.configure(values=labels)
            menu.set(labels[current_axis.get()])
            for start, entry in controls.items():
                entry.delete(0, "end")
                entry.insert(0, str(shown(start)))

        def pick(label):
            current_axis.set(next(i for i in range(len(axes)) if label.endswith(axes[i]) and label.strip(" ●") == axes[i]))
            refresh()

        menu.configure(command=pick)
        frame._refresh = refresh
        frame._controls = controls
        raw = ctk.CTkLabel(frame, text=tr("Raw value: {value}").format(value=var.get()), text_color="gray", wraplength=430, justify="left")
        raw.pack(anchor="w", padx=4)
        var.trace_add("write", lambda *_a: raw.configure(text=tr("Raw value: {value}").format(value=var.get())))
        if spec.get("note"):
            note = InfoLabel(frame)
            note.set_info(spec["note"])
            note.pack(anchor="w", padx=4)
        refresh()
        return frame

    def _build_checkbox_widget(self, var: tk.StringVar, spec: dict):
        """Check box for an on/off field of a value (the other fields stay untouched)."""
        idx, on, off = spec.get("index", 0), spec.get("on", "1"), spec.get("off", "0")
        parts = var.get().split(",")
        if idx >= len(parts) or parts[idx].strip() not in (on, off):
            return None
        frame = ctk.CTkFrame(self._row_parent, fg_color="transparent", border_width=0, border_color=CHANGED_COLOR)
        row = self._marked_row(frame)
        state = tk.BooleanVar(value=parts[idx].strip() == on)

        def toggled():
            self._last_key = None   # every click is its own undo step
            items = var.get().split(",")
            items[idx] = on if state.get() else off
            var.set(",".join(items))

        box = ctk.CTkCheckBox(row, text=spec.get("text", "an"), variable=state, command=toggled, width=20, checkbox_width=22, checkbox_height=22)
        box.pack(side="left")

        def refresh():
            state.set(var.get().split(",")[idx].strip() == on)

        frame._refresh = refresh
        raw = ctk.CTkLabel(row, text=tr("Raw value: {value}").format(value=var.get()), text_color="gray")
        raw.pack(side="left", padx=12)
        var.trace_add("write", lambda *_a: (raw.configure(text=tr("Raw value: {value}").format(value=var.get())), refresh()))
        if spec.get("note"):
            note = InfoLabel(frame)
            note.set_info(spec["note"])
            note.pack(anchor="w", padx=4)
        return frame

    def _marked_row(self, frame) -> ctk.CTkFrame:
        """Row for the controls of a parameter inside `frame`; its surrounding border turns yellow when the value is changed.

        The border is always 2 px wide (only its colour changes) and the controls are padded so they do not cover it.
        """
        mark = ctk.CTkFrame(frame, fg_color="transparent", border_width=2, border_color=self._c["card"], corner_radius=4)
        mark.pack(anchor="w")
        frame._mark = mark
        row = ctk.CTkFrame(mark, fg_color="transparent")
        row.pack(padx=4, pady=4)
        return row

    def _build_counter_widget(self, var: tk.StringVar, spec: dict):
        """Number entry with -10/-1/+1/+10 buttons for one field of a value (the other fields stay untouched)."""
        idx, lo, hi, unit = spec["index"], spec["min"], spec["max"], spec.get("unit", "")
        scale, decimals = spec.get("scale"), spec.get("decimals", 2)   # optional display scale (raw 45 shown as 0.45)
        small, large, snap = spec.get("small", 1), spec.get("large", 10), spec.get("snap")   # button steps and grid of allowed values
        parts = var.get().split(",")
        if idx >= len(parts):
            return None
        try:
            int(parts[idx])
        except ValueError:
            return None
        frame = ctk.CTkFrame(self._row_parent, fg_color="transparent", border_width=0, border_color=CHANGED_COLOR)
        row = self._marked_row(frame)

        def current() -> int:
            return int(var.get().split(",")[idx])

        def set_number(new: int):
            if snap:
                new = lo + round((new - lo) / snap) * snap
            new = max(lo, min(hi, new))
            if new != current():
                items = var.get().split(",")
                items[idx] = str(new)
                var.set(",".join(items))

        entry = ctk.CTkEntry(row, width=64, justify="center")

        def show():
            entry.delete(0, "end")
            entry.insert(0, f"{current() * scale:.{decimals}f}" if scale else str(current()))

        def commit(_event=None):
            try:
                text = entry.get().strip().replace(",", ".")
                set_number(round(float(text) / scale) if scale else int(text))
            except ValueError:
                pass
            show()

        def bump(delta: int):
            self._last_key = None   # every click is its own undo step
            set_number(current() + delta)
            show()

        def button(text, delta):
            ctk.CTkButton(row, text=text, width=(54 if scale else 40), height=26, command=lambda: bump(delta)).pack(side="left", padx=(0, 2))

        def caption(step: int) -> str:
            return f"{step * scale:.{decimals}f}".replace(".", ",") if scale else str(step)

        button(f"−{caption(large)}", -large)
        button(f"−{caption(small)}", -small)
        entry.pack(side="left", padx=4)
        button(f"+{caption(small)}", small)
        button(f"+{caption(large)}", large)
        if unit:
            ctk.CTkLabel(row, text=unit, text_color="gray").pack(side="left", padx=(4, 0))
        entry.bind("<Return>", commit)
        entry.bind("<FocusOut>", commit)
        show()
        frame._refresh = show
        raw = ctk.CTkLabel(frame, text=tr("Raw value: {value}").format(value=var.get()), text_color="gray", wraplength=430, justify="left")
        raw.pack(anchor="w", padx=4)
        var.trace_add("write", lambda *_a: raw.configure(text=tr("Raw value: {value}").format(value=var.get())))
        if spec.get("note"):
            note = InfoLabel(frame)
            note.set_info(spec["note"])
            note.pack(anchor="w", padx=4)
        return frame

    def _build_step_widget(self, var: tk.StringVar, spec: dict):
        """Menu-step editor (-99..+99) for scaled raw values; unchanged fields keep their exact raw value."""
        fields, unit = spec["fields"], spec["unit"]
        lo, hi = spec["range"]
        max_raw = spec.get("max_raw")
        min_raw = spec.get("min_raw", -max_raw if max_raw else None)   # the limit step can be stored asymmetrically (B Gamma -99 = -32768)
        parts = var.get().split(",")
        if len(parts) <= max(f["index"] for f in fields):
            return None
        try:
            for f in fields:
                if "choices" not in f:
                    int(parts[f["index"]])
        except ValueError:
            return None

        frame = ctk.CTkFrame(self._row_parent, fg_color="transparent", border_width=0, border_color=CHANGED_COLOR)
        per_row = 2
        refreshers: list = []
        frame._refresh = lambda: [r() for r in refreshers]

        def set_item(idx, text):
            items = var.get().split(",")
            lead = items[idx][: len(items[idx]) - len(items[idx].lstrip())]
            items[idx] = lead + text
            var.set(",".join(items))

        def make_choice(cell, f):
            idx, choices = f["index"], {k: with_raw(v, k) for k, v in f["choices"].items()}
            cur = var.get().split(",")[idx].strip()
            labels = list(choices.values())
            if cur not in choices:
                labels.append(tr("{value} (unknown)").format(value=cur))
            menu = ctk.CTkOptionMenu(cell, values=labels, width=self._menu_width(labels, 100), dynamic_resizing=False)
            menu.set(choices.get(cur, tr("{value} (unknown)").format(value=cur)))
            def choose(lab):
                self._last_key = None   # every dropdown choice is its own undo step
                next((set_item(idx, k) for k, v in choices.items() if v == lab), None)

            menu.configure(command=choose)
            menu.pack()

            def refresh_choice():
                now = var.get().split(",")[idx].strip()
                menu.configure(values=list(choices.values()) + ([] if now in choices else [tr("{value} (unknown)").format(value=now)]))
                menu.set(choices.get(now, tr("{value} (unknown)").format(value=now)))

            refreshers.append(refresh_choice)

        def make_step(cell, f):
            idx = f["index"]
            own_range = "range" in f      # fields can have their own unit, range and sign (e.g. hue 0..359 degrees)
            flo, fhi = f["range"] if own_range else (lo, hi)
            funit, fsign = f.get("unit", unit), f.get("sign", 1)
            shown = lambda: str(max(flo, min(fhi, raw_to_step(int(var.get().split(",")[idx]), funit, fsign, f.get("trunc", False)))))
            row = ctk.CTkFrame(cell, fg_color="transparent")
            row.pack()
            entry = ctk.CTkEntry(row, width=52, justify="center")
            entry.insert(0, shown())
            swatch = None
            if f.get("swatch") == "hue":
                swatch = ctk.CTkFrame(row, width=26, height=26, corner_radius=4, fg_color=hue_hex(int(shown())))

            def apply(new: int):
                new = max(flo, min(fhi, new))
                if new != int(shown()):
                    raw = round(fsign * new * funit)
                    if max_raw and not own_range and abs(new) == hi:
                        raw = max_raw if new > 0 else min_raw  # camera stores the limit steps as +-32767 (or the spec's min_raw)
                    set_item(idx, str(raw))
                show_all()

            def show_all():
                entry.delete(0, "end")
                entry.insert(0, shown())
                if swatch is not None:
                    swatch.configure(fg_color=hue_hex(int(shown())))
                if hint_label is not None:
                    clicks = int(shown())
                    menu_step = (abs(clicks) // hint["per"]) * (1 if clicks >= 0 else -1)
                    hint_label.configure(text=tr("Camera menu shows: {value}").format(value=f"{menu_step:+d}" if menu_step else "0"))

            def commit(_event=None):
                try:
                    apply(int(entry.get().strip()))
                except ValueError:
                    apply(int(shown()))

            def bump(delta: int):
                self._last_key = None   # every click is its own undo step
                apply(int(shown()) + delta)

            def button(text, delta):
                return ctk.CTkButton(row, text=text, width=38, height=26, command=lambda: bump(delta))

            big = f.get("big", 10)      # the large buttons: Master Black moves a whole menu step (8 wheel clicks)
            button(f"−{big}", -big).pack(side="left", padx=(0, 2))
            button("−1", -1).pack(side="left", padx=(0, 2))
            entry.pack(side="left", padx=2)
            button("+1", 1).pack(side="left", padx=(2, 0))
            button(f"+{big}", big).pack(side="left", padx=(2, 0))
            hint = f.get("hint")      # what the camera menu shows for this fine value (Master Black: 8 wheel clicks = one menu step, cut towards zero)
            hint_label = None
            if hint and self.scene.model in hint.get("models", [self.scene.model]):
                hint_label = ctk.CTkLabel(row, text="", text_color="gray")
                hint_label.pack(side="left", padx=(14, 0))
                explain = InfoLabel(row)
                explain.set_info(tr("The small buttons move the wheel by one click, the large buttons by a whole menu step ({n} clicks). The camera menu shows the number of clicks divided by {n}, cut towards zero: around zero {zero} clicks all show 0.").format(n=hint["per"], zero=2 * hint["per"] - 1))
                explain.pack(side="left", padx=(6, 0))
            if swatch is not None:
                swatch.pack(side="left", padx=(8, 0))
            entry.bind("<Return>", commit)
            entry.bind("<FocusOut>", commit)
            entry.commit = commit       # the tests commit directly (a synthetic focus event is not reliably delivered)

            show_all()
            refreshers.append(show_all)

        cells = []
        for n, f in enumerate(fields):
            cell = ctk.CTkFrame(frame, fg_color="transparent")
            cell.grid(row=n // per_row, column=n % per_row, padx=4, pady=2)
            ctk.CTkLabel(cell, text=f["label"], text_color="gray").pack()
            (make_choice if "choices" in f else make_step)(cell, f)
            cells.append(cell)
        raw = ctk.CTkLabel(frame, text=tr("Raw value: {value}").format(value=var.get()), text_color="gray", wraplength=430, justify="left")
        raw.grid(row=(len(fields) - 1) // per_row + 1, column=0, columnspan=per_row, sticky="w", padx=4)
        var.trace_add("write", lambda *_a: raw.configure(text=tr("Raw value: {value}").format(value=var.get())))

        def relayout(available: int):
            """Put as many cells in a line as fit into the available width (physical pixels): fields wrap only when the window is narrow."""
            width = max(c.winfo_reqwidth() for c in cells) + 8
            per = max(1, min(len(cells), available // width))
            for n, cell in enumerate(cells):
                cell.grid(row=n // per, column=n % per, padx=4, pady=2)
            raw.grid(row=(len(cells) - 1) // per + 1, column=0, columnspan=per, sticky="w", padx=4)

        frame._relayout = relayout
        self._reflow.append(frame)
        return frame

    # -- undo / redo ------------------------------------------------------- #
    def _snapshot(self) -> dict:
        self._collect()
        s = self.scene
        if self.session:
            store = {m: dict(p) for m, p in self.session.store.items()}
            baseline = {m: dict(p) for m, p in self.session.baseline.items()}
        else:
            store, baseline = {f"{self.kind}:{s.model}": dict(s.params)}, None
        stash = {k: dict(v) for k, v in self._stash.items()}
        return {"name": s.name, "model": s.model, "kind": self.kind, "number": s.number, "store": store, "baseline": baseline, "stash": stash}

    def _can_refresh_in_place(self) -> bool:
        """True if the table already shows the same parameters of the same type and model: then only the values change."""
        return (bool(self.vars) and set(self.vars) == set(self.scene.params) and self._built_model == self.scene.model
                and self._built_kind == self.kind and self._built_db == self.param_db and self._built_look == self._look())

    @lazy
    def _refresh_in_place(self, reset_original: bool = False):
        """Update the widgets to the values of self.scene (a full rebuild takes seconds for ALL files)."""
        s = self.scene
        if reset_original:
            self.original = dict(s.params)
        self._busy = True
        self.var_name.set(s.name)
        self.var_number.set(s.number)
        changed = []
        for key, var in self.vars.items():
            if var.get() != s.params[key]:
                var.set(s.params[key])
                changed.append(key)
        for key in self.vars:
            self._on_edit(key)
        self._unlock_all_rows()               # a greyed-out entry ignores new text: unlock every row first, lock again afterwards
        for key in changed:
            refresh = getattr(self.entries.get(key), "_refresh", None)
            if refresh:
                refresh()
        self._refresh_availability()      # and lock again what the new values lock
        self._busy = False

    def _restore(self, snap: dict):
        s = self.scene
        s.name, s.model, s.number = snap["name"], snap["model"], snap["number"]
        self._stash = {k: dict(v) for k, v in snap["stash"].items()}
        if snap["kind"] != self.kind:
            self._apply_kind(snap["kind"])
        if self.session:
            self.session.store = {m: dict(p) for m, p in snap["store"].items()}
            self.session.baseline = {m: dict(p) for m, p in snap["baseline"].items()}
            self.session.model = s.model
            self.session.kind = self.kind
            s.params = self.session.store[self.session.key]
        else:
            s.params = dict(snap["store"][f"{self.kind}:{s.model}"])
        if self._can_refresh_in_place():
            self._refresh_in_place()
            self._update_history_buttons()
        else:
            self._populate(reset_original=False)
            self._busy = True  # refresh change markers without creating history entries
            for key in self.vars:
                self._on_edit(key)
            self._busy = False

    def _state_key(self) -> tuple:
        snap = self._snapshot()
        # only what would be saved: the profile that is currently shown (the other profile is kept in the session)
        return (snap["name"], snap["model"], snap["kind"], snap["number"], snap["store"][f"{snap['kind']}:{snap['model']}"])

    def _is_dirty(self) -> bool:
        return bool(self.scene) and self._saved is not None and self._state_key() != self._saved

    def _confirm_discard(self, action: str) -> bool:
        """True if the action may go on: no unsaved changes, or they were saved / may be dropped."""
        if not self._is_dirty():
            return True
        answer = messagebox.askyesnocancel(
            APP_NAME, tr("{file} has unsaved changes.\n\nSave before {action}?").format(file=self._file_label() or tr("The file"), action=action)
        )
        if answer is None:
            return False
        if answer:
            self.save()
            return not self._is_dirty()   # saving was cancelled or failed: do not go on
        return True

    def on_close(self):
        """Ask whether to save unsaved changes before the window closes."""
        if self._confirm_discard("Exit"):
            self.destroy()

    def _update_title(self):
        s = self.scene
        if not s or not self._file_label():
            self.title(f"{APP_NAME} v{_version}")
            return
        dirty = self._saved is not None and self._state_key() != self._saved
        self.title(f"{APP_NAME} v{_version} - {self._file_label()}{'*' if dirty else ''}")

    def _history_reset(self):
        self._saved = self._state_key()
        self._hist = [self._snapshot()]
        self._hpos = 0
        self._last_key = None
        self._update_history_buttons()

    def _record(self, key: str, force_new: bool = False, merge: bool = False):
        if self._busy or not self.scene or not self._hist:
            return
        snap = self._snapshot()
        if snap == self._hist[self._hpos]:
            return
        now = time.monotonic()
        if not force_new and key == self._last_key and (merge or now - self._last_t < COALESCE_SECONDS):
            self._hist[self._hpos] = snap
        else:
            del self._hist[self._hpos + 1 :]
            self._hist.append(snap)
            if len(self._hist) > HISTORY_LIMIT:
                del self._hist[0]
            self._hpos = len(self._hist) - 1
        self._last_key, self._last_t = key, now
        self._update_history_buttons()

    def _apply_companions(self, key: str, companions: dict | None):
        """Set dependent values in other parameters (e.g. 00175, 00454) that must follow a format choice.

        Done as one history step together with the choice itself.
        """
        if not companions:
            return
        busy = self._busy
        self._busy = True
        try:
            for other, fields in companions.items():
                var = self.vars.get(other)
                if var is None:
                    continue
                items = var.get().split(",")
                for i, v in fields.items():
                    i = int(i)
                    if i < len(items):
                        lead = items[i][: len(items[i]) - len(items[i].lstrip())]
                        items[i] = lead + v
                var.set(",".join(items))
                refresh = getattr(self.entries.get(other), "_refresh", None)
                if refresh:
                    refresh()
        finally:
            self._busy = busy
        self._record(key, merge=True)  # belongs to the step of the choice, however long the choice took on a slow machine
        self._update_warnings()

    # -- options that are not possible in the current state: greyed out and not selectable ------ #
    def _field_value(self, pid: str, field: int) -> str | None:
        var = self.vars.get(pid)
        if var is None:
            return None
        parts = [x.strip() for x in var.get().split(",")]
        return parts[field] if field < len(parts) else None

    def _cond_holds(self, cond: dict) -> bool:
        """Condition on one field of a parameter: in / not_in / max / min (unknown parameters never restrict)."""
        value = self._field_value(cond["id"], cond.get("field", 0))
        if value is None:
            return True
        if "in" in cond and value not in cond["in"]:
            return False
        if "not_in" in cond and value in cond["not_in"]:
            return False
        if "max" in cond or "min" in cond:
            try:
                number = float(value)
            except ValueError:
                return True
            if "max" in cond and number > cond["max"]:
                return False
            if "min" in cond and number < cond["min"]:
                return False
        return True

    def _option_state(self, requires: list | None) -> tuple[bool, str]:
        """(available, reason). A requirement only counts when all its "when" conditions hold."""
        for req in requires or []:
            if all(self._cond_holds(g) for g in req.get("when", [])) and not self._cond_holds(req):
                return False, tr(req.get("reason", "not possible"))
        return True, ""

    @staticmethod
    def _fill_menu(menu, labels: list[str], disabled: dict[str, str]):
        """Put the labels into a dropdown; entries in `disabled` stay visible but cannot be selected (with the reason)."""
        menu.configure(values=labels)
        dropdown = menu._dropdown_menu
        tk.Menu.configure(dropdown, disabledforeground="#8a8a8a")
        for i, label in enumerate(labels):
            if label in disabled:
                dropdown.entryconfigure(i, label=f"  {label}   –   {disabled[label]}  ", state="disabled")
            else:
                dropdown.entryconfigure(i, state="normal")

    @lazy
    def _refresh_availability(self):
        for widget in self.entries.values():
            fn = getattr(widget, "_availability", None)
            if fn:
                fn()
        self._apply_locks()
        self._update_kind_switch()

    def _scene_possible(self) -> bool:
        """SCENE files exist only in Custom mode (manual: not configurable in Cine EI)."""
        return not (self.kind == "all" and self._field_value("00418", 0) == "1")

    def _update_lock_marks(self):
        """Mark the type switch and the model menu with a lock symbol and a tooltip reason while a choice is locked."""
        if not self.session:
            return
        kind_reason = "" if self.session.can_switch_kind() else tr("Switching SCENE/ALL does not exist for {model}.").format(model=self.scene.model)
        if not kind_reason and not self._scene_possible():
            kind_reason = tr("SCENE not possible: SCENE files exist in Custom mode only.")
        model_reason = "" if self.session and self.scene.model in MODELS else tr("There is no model switch for this model.")
        for label, widgets, reason, text in (
            (self.lbl_kind, tuple(self.seg_kind._buttons_dict.values()), kind_reason, tr("Type")),
            (self.lbl_model, (self.menu_model,), model_reason, tr("Model")),
        ):
            label.configure(text=f"{text} 🔒" if reason else text, text_color=WARNING_COLOR if reason else ("gray10", "gray90"))
            for widget in (label, *widgets):
                if not hasattr(widget, "_lock_tip"):
                    widget._lock_tip = Tooltip(widget)
                widget._lock_tip.text = reason

    def _update_kind_switch(self):
        """Grey out the SCENE segment while the ALL file is in Cine EI mode."""
        possible = self._scene_possible()
        try:
            self.seg_kind._buttons_dict["SCENE"].configure(state="normal" if possible else "disabled")
        except (AttributeError, KeyError, tk.TclError):
            return
        self.lbl_scene_hint.configure(text="" if possible else tr("SCENE not possible: SCENE files exist in Custom mode only"))
        self._update_lock_marks()

    def _set_enabled(self, widget, enabled: bool):
        """Enable/disable all input widgets inside a row; widgets that are read-only by design stay read-only."""
        stack = [widget]
        while stack:
            w = stack.pop()
            stack.extend(w.winfo_children())
            if not isinstance(w, (tk.Entry, ctk.CTkEntry, ctk.CTkOptionMenu, ctk.CTkCheckBox, ctk.CTkButton)):
                continue
            if isinstance(w, tk.Entry) and isinstance(w.master, ctk.CTkEntry):
                continue     # the inner entry follows its CTkEntry; handling it too stored the already disabled state and left it disabled after the unlock
            try:
                state = str(w.cget("state"))
            except tk.TclError:
                continue
            if not enabled:
                if not hasattr(w, "_state_before_lock"):
                    w._state_before_lock = state
                if isinstance(w, tk.Entry):
                    w.configure(disabledforeground="#8a8a8a", disabledbackground=self._c["entry"])
                w.configure(state="disabled")
            elif hasattr(w, "_state_before_lock"):
                w.configure(state=w._state_before_lock)
                del w._state_before_lock

    @staticmethod
    def _lock_matches(lock: dict, subgroup: str) -> bool:
        """A group lock names a sub-group exactly ("subgroup") or by its beginning ("subgroup_prefix", e.g. the whole Paint menu)."""
        if "subgroup" in lock:
            return subgroup == lock["subgroup"]
        return subgroup.startswith(lock["subgroup_prefix"])

    def _unlock_all_rows(self):
        """Make every locked row usable again (the next _apply_locks locks what the current values lock)."""
        for row in self._rows.values():
            if row.get("locked"):
                row["locked"] = False
                self._set_enabled(row["widget"], True)
                row["label"].configure(fg=self._c["label"])

    def _apply_locks(self):
        """Grey out whole sub-groups while a lock condition holds (e.g. the Paint menu in Cine EI mode, Gamma while it is Off).

        Locks can overlap: a row stays locked while any of them applies. "except" lists rows that stay usable (the switch itself).
        """
        row_reason: dict[str, str] = {}
        sub_reason: dict[str, str] = {}
        for lock in self.locks:
            value = self._field_value(lock["when"]["id"], lock["when"].get("field", 0))
            if value is None or value not in lock["when"]["in"]:
                continue
            if "ids" in lock:        # lock of single rows (e.g. a level that depends on its own On/Off switch)
                for key in lock["ids"]:
                    if key in self._rows:
                        row_reason.setdefault(key, lock["reason"])
                continue
            exempt = set(lock.get("except", []))
            for key, row in self._rows.items():
                info = row["info"]
                if info and self._lock_matches(lock, info.get("subgroup", "")) and key not in exempt:
                    row_reason.setdefault(key, lock["reason"])
            for sub in self._subheads:
                if self._lock_matches(lock, sub["title"]):
                    sub_reason.setdefault(sub["title"], lock["reason"])
        group_locks = [lock for lock in self.locks if "subgroup_prefix" in lock or "subgroup" in lock]
        lock_ids = {key for lock in self.locks for key in lock.get("ids", [])}
        for key, row in self._rows.items():
            locked = key in row_reason
            info = row["info"]
            if not info or not (key in lock_ids or any(self._lock_matches(lock, info.get("subgroup", "")) for lock in group_locks)) or bool(row.get("locked")) == locked:
                continue
            row["locked"] = locked
            self._set_enabled(row["widget"], not locked)
            row["label"].configure(fg="#7a7a7a" if locked else self._c["label"])
        for sub in self._subheads:
            if any(self._lock_matches(lock, sub["title"]) for lock in group_locks):
                reason = sub_reason.get(sub["title"])
                sub["suffix"] = f"   –   {reason}" if reason else ""
                self._set_sub_text(sub)
                sub["label"].configure(fg="#7a7a7a" if reason else self._c["accent"])

    def _set_values(self, key: str, values: dict[str, str]):
        """Set complete values of other parameters (used to bring remembered values back) as part of the current history step."""
        busy = self._busy
        self._busy = True
        try:
            for other, value in values.items():
                var = self.vars.get(other)
                if var is None or var.get() == value:
                    continue
                var.set(value)
                refresh = getattr(self.entries.get(other), "_refresh", None)
                if refresh:
                    refresh()
        finally:
            self._busy = busy
        self._record(key, merge=True)
        self._update_warnings()

    def _warnings(self) -> list[str]:
        out = []
        for key, widget in self.entries.items():
            fn = getattr(widget, "_warning", None)
            if fn:
                msg = fn()
                if msg:
                    out.append(f"{key}: {msg}")
        return out

    @lazy
    def _update_warnings(self):
        self._refresh_availability()   # the options that are possible depend on the other values
        warnings = self._warnings()
        self.lbl_warn.configure(text=("⚠ " + "\n⚠ ".join(warnings)) if warnings else "")
        if warnings:
            self.lbl_warn.grid()
        else:
            self.lbl_warn.grid_remove()
        self._sync_messages()

    @lazy
    def _update_history_buttons(self):
        self.btn_undo.configure(state="normal" if self._hpos > 0 else "disabled")
        self.btn_redo.configure(state="normal" if 0 <= self._hpos < len(self._hist) - 1 else "disabled")
        self._update_title()
        self._update_warnings()

    def _step_history(self, delta: int):
        target = self._hpos + delta
        if not self.scene or not 0 <= target < len(self._hist):
            return
        self._hpos = target
        self._last_key = None
        self._restore(self._hist[target])
        self._update_history_buttons()

    def undo(self):
        self._step_history(-1)

    def redo(self):
        self._step_history(+1)

    # -- file type (SCENE / ALL), number and file name --------------------------- #
    def _ext(self) -> str:
        return ".ALL" if self.kind == "all" else ".SCENE"

    def _file_label(self) -> str:
        """File name shown in the title: NNN.ALL / NNN.SCENE from the number, else the loaded file name."""
        s = self.scene
        if not s:
            return ""
        if len(s.number) == 3:
            return f"{s.number}{self._ext()}"
        if s.path and s.path.suffix.lower() == self._ext().lower():
            return s.path.name
        return f"new{self._ext()}"

    def _target_path(self) -> Path | None:
        """Where Save writes to: folder of the loaded/saved file + number + extension of the current file type."""
        s = self.scene
        folder = s.path.parent if s.path else self._last_dir
        if folder is None:
            return None
        if len(s.number) == 3:
            return folder / f"{s.number}{self._ext()}"
        if s.path and s.path.suffix.lower() == self._ext().lower():
            return s.path
        return None

    def _on_number(self, *_a):
        value = self.var_number.get()
        clean = "".join(ch for ch in value if ch.isdigit())[:3]
        if clean != value:
            self.var_number.set(clean)
            return
        if self._busy or self.scene is None:
            return
        self._record("__number__")

    def _pad_number(self):
        value = self.var_number.get()
        if value:
            self.var_number.set(value.zfill(3))

    def _apply_kind(self, kind: str):
        """Make SCENE or ALL the current file type (parameter database and header state)."""
        self.kind = kind
        self.param_db = load_param_db(kind)
        self.locks = load_param_locks(kind)
        models = param_db_models(kind)
        if models is not None and self.scene.model not in models:
            self.param_db = {}
            self.locks = []
        if self.session:
            self.session.db = self.param_db

    def _switch_kind(self, label: str):
        target = label.lower()
        if not self.session or target == self.kind:
            return
        if not self.session.can_switch_kind() or (target == "scene" and not self._scene_possible()):
            self.var_kind.set(self.kind.upper())
            return
        self._collect()
        r = self.session.switch_kind(target)
        self._apply_kind(target)
        self._populate()
        self._record("__kind__", force_new=True)
        parts = [tr("{n} values taken over").format(n=r["copied"])]
        if r["unmapped"]:
            parts.append(tr("{n} parameters without a counterpart in the other type (kept stored)").format(n=r["unmapped"]))
        if r["template"]:
            parts.append(tr("remaining values from the template"))
        self.lbl_switch.configure(text=tr("Type {type}: {parts}. Switching back restores the original values. Saving writes {file}.").format(
            type=target.upper(), parts="; ".join(parts), file=self._file_label()))

    def import_plan(self, path: Path) -> tuple[list[dict], str, str]:
        """Read a SCENE/ALL file (any model) and list what can go into the current file. Returns (items, reason, source text)."""
        ext = Path(path).suffix.lower()
        if ext not in LOADERS:
            return [], tr("Unknown file type {ext}.").format(ext=repr(Path(path).suffix)), ""
        try:
            src = LOADERS[ext](Path(path))
        except (SceneFileError, OSError) as exc:
            return [], tr("The file could not be read:\n{error}").format(error=exc), ""
        self._collect()
        items, reason = import_candidates(
            src, "all" if ext == ".all" else "scene", self.scene.params, self.kind, self.scene.model, self.param_db, self.rules
        )
        return items, reason, f"{Path(path).name} ({'ALL' if ext == '.all' else 'SCENE'}, {src.model})"

    def show_diff(self, items: list[dict], source_text: str, invisible: bool = False):
        """Difference view of the current file against another file (the items come from import_plan)."""
        self._collect()
        rows = build_diff_rows(items, self.scene.params, self.param_db)
        dialog = DiffDialog(self, rows, source_text, invisible=invisible)
        if not invisible:
            dialog.after(50, dialog.grab_set)
            self.wait_window(dialog)
        return dialog

    def compare_file(self):
        if not self.scene:
            return
        path = filedialog.askopenfilename(
            title=tr("Compare with…"), initialdir=self._last_dir,
            filetypes=[("Sony SCENE/ALL File", "*.SCENE *.ALL"), (tr("All files"), "*.*")],
        )
        if not path:
            return
        items, reason, source = self.import_plan(Path(path))
        if not items:
            messagebox.showinfo(APP_NAME, reason or tr("Nothing can be imported from this file."))
            return
        self.show_diff(items, source)

    def import_file(self):
        if not self.scene:
            return
        path = filedialog.askopenfilename(
            title=tr("Import from…"), initialdir=self._last_dir,
            filetypes=[("Sony SCENE/ALL File", "*.SCENE *.ALL"), (tr("All files"), "*.*")],
        )
        if not path:
            return
        items, reason, source = self.import_plan(Path(path))
        if not items:
            messagebox.showinfo(APP_NAME, reason or tr("Nothing can be imported from this file."))
            return
        dialog = ImportDialog(self, items, source)
        dialog.after(50, dialog.grab_set)
        self.wait_window(dialog)
        if dialog.result:
            self.apply_import(dialog.result)

    def apply_import(self, items: list[dict]) -> int:
        """Write the chosen values into the current file as one undo step. Returns how many values changed."""
        values = {i["tid"]: i["new"] for i in items if i["tid"] in self.vars and self.vars[i["tid"]].get() != i["new"]}
        if values:
            self._set_values("__import__", values)
            self._last_key = None   # own undo step
        self.lbl_switch.configure(text=tr("Import: {n} values taken over ({same} were already equal). Undo reverts the whole import.").format(n=len(values), same=len(items) - len(values)))
        return len(values)

    def _switch_model(self, target: str):
        if not self.session or target == self.scene.model:
            return
        self._collect()
        r = self.session.switch(target)
        self._populate()
        self._record("__switch__", force_new=True)
        parts = [tr("{n} values taken over").format(n=r["copied"])]
        if r["kept"]:
            parts.append(tr("{n} model specific or not transferable (the value of the target model stays)").format(n=r["kept"]))
        if r["hidden"]:
            parts.append(tr("{n} parameters do not exist on the {model} (kept stored)").format(n=r["hidden"], model=target))
        if r["added"]:
            parts.append(tr("{n} new parameters (default values)").format(n=r["added"]))
        if not r["template"] and not self.session.store.get(f"{self.kind}:{target}"):
            parts.append(tr("no template found"))
        self.lbl_switch.configure(text=tr("Switch to {model}: {parts}. Switching back restores the original values.").format(model=target, parts="; ".join(parts)))

    def _build_multichoice_widget(self, key: str, var: tk.StringVar, spec: dict):
        """Dropdowns that each set several fields of one value (e.g. resolution = width + height).

        Known combinations are shown as text, anything else as the raw numbers. "autoset" rules fill dependent fields
        for combinations that are known from sample files.
        """
        selectors, autoset = spec["selectors"], spec.get("autoset", [])
        if SHOW_RAW_VALUES:        # display copies: index (or raw value) in brackets behind the text; the database stays as it is
            selectors = [dict(sel, options=[dict(o, label=index_label(o["label"]) + (f" ({o['values'][sel['raw_field']]})" if sel.get("raw_field") else ""))
                                            for o in sel["options"]]) for sel in selectors]
        needed = max(int(i) for sel in selectors for o in sel["options"] for i in o["values"])
        if len(var.get().split(",")) <= needed:
            return None

        def parts():
            return [p.strip() for p in var.get().split(",")]

        def matches(values, cur):
            return all(cur[int(i)] == v for i, v in values.items())

        def current_label(sel, cur):
            gate = sel.get("only_when")
            if gate and cur[int(gate["field"])] not in gate["values"]:
                return gate.get("label", "–")
            for o in sel["options"]:
                if matches(o["values"], cur):
                    return o["label"]
            idx = sorted({int(i) for o in sel["options"] for i in o["values"]})
            return tr("unknown: ") + "/".join(cur[i] for i in idx)

        def listed(sel, cur):
            """Options shown in the dropdown of a selector (a selector with filter_field lists only the options of the current value)."""
            field = sel.get("filter_field")
            if field is None:
                return sel["options"]
            return [o for o in sel["options"] if o["values"][field] == cur[int(field)]]

        def write(new_parts):
            items = var.get().split(",")
            for i, v in enumerate(new_parts):
                lead = items[i][: len(items[i]) - len(items[i].lstrip())]
                items[i] = lead + v
            var.set(",".join(items))

        frame = ctk.CTkFrame(self._row_parent, fg_color="transparent", border_width=0, border_color=CHANGED_COLOR)
        menus: list = []
        hint = ctk.CTkLabel(frame, text="", text_color="gray", wraplength=430, justify="left")

        def warning() -> str:
            """Plausibility checks from the spec; returns a message or an empty string."""
            cur = parts()
            for check in spec.get("checks", []):
                if check["type"] == "interlaced_max_fps":
                    try:
                        fps = int(cur[check["num_field"]]) / int(cur[check["den_field"]])
                    except (ValueError, ZeroDivisionError, IndexError):
                        continue
                    if cur[check["scan_field"]] == check["interlaced_value"] and fps <= check["fps"] + 0.001:
                        return check["message"]
                elif check["type"] == "raw_output_needs_scan":
                    scan_var = self.vars.get(check["scan_id"])
                    if scan_var is None or cur[check["codec_field"]] not in check["raw_codecs"]:
                        continue
                    scan_mode = scan_var.get().split(",")[0].strip()
                    out = cur[check["raw_field"]]
                    if out in check["k4_values"] and scan_mode != check["normal"]:
                        return check["message_4k"]
                    if out in check["k2_values"] and scan_mode == check["normal"]:
                        return check["message_2k"]
            for sel in selectors:       # the chosen option must be possible in the current state
                for o in sel["options"]:
                    if matches(o["values"], cur):
                        ok, reason = self._option_state(o.get("requires"))
                        if not ok:
                            return f"{o['label']}: {reason}"
                        break
            return ""

        def availability():
            cur = parts()
            for sel, menu in menus:
                label = current_label(sel, cur)
                shown = listed(sel, cur)
                labels = [o["label"] for o in shown]
                labels += [] if label in labels else [label]
                disabled = {}
                for o in shown:
                    ok, reason = self._option_state(o.get("requires"))
                    if not ok:
                        disabled[o["label"]] = reason
                self._fill_menu(menu, labels, disabled)

        def refresh():
            cur = parts()
            for sel, menu in menus:
                menu.set(current_label(sel, cur))
            availability()
            rule_hit = next((r for r in autoset if matches(r["when"], cur)), None)
            warn = warning()
            if warn:
                hint.configure(text=warn, text_color=WARNING_COLOR)
            elif rule_hit and all(cur[int(i)] == v for i, v in rule_hit["set"].items()):
                hint.configure(text=tr("Combination known from files."), text_color="gray")
            elif rule_hit:
                hint.configure(text=tr("The format index does not match the known combination."), text_color="gray")
            else:
                hint.configure(
                    text=tr("Combination not known from files; format index and codec fields unchecked."), text_color="gray"
                )

        def make(sel, cell):
            def pick(label):
                option = next((o for o in listed(sel, parts()) if o["label"] == label), None)
                if option is None:
                    return
                if sel.get("on_pick") == "format_for_codec":
                    # a codec choice means: take a format of that codec, preferably the same resolution and frame rate
                    cur = parts()
                    formats = next(x for x in selectors if x.get("filter_field"))
                    field = formats["filter_field"]
                    candidates = [o for o in formats["options"] if o["values"][field] == option["values"][field]]
                    if not candidates:
                        return
                    option = next((o for o in candidates if all(o["values"].get(i) == cur[int(i)] for i in "01234")), candidates[0])
                self._last_key = None   # every dropdown choice is its own undo step
                new = parts()
                for i, v in option["values"].items():
                    new[int(i)] = v
                rule_hit = next((r for r in autoset if matches(r["when"], new)), None)
                if rule_hit:
                    for i, v in rule_hit["set"].items():
                        new[int(i)] = v
                write(new)
                self._apply_companions(key, option.get("companions"))
                refresh()

            readonly = sel.get("readonly", False)  # read-only selectors only display what follows from the other fields
            menu = ctk.CTkOptionMenu(
                cell, values=[o["label"] for o in listed(sel, parts())], width=self._menu_width([o["label"] for o in sel["options"]], sel.get("width", 230)),
                dynamic_resizing=False,
                command=None if readonly else pick, state="disabled" if readonly else "normal",
            )
            menu.pack()
            menus.append((sel, menu))

        per_row = spec.get("per_row", 2)
        for n, sel in enumerate(selectors):
            cell = ctk.CTkFrame(frame, fg_color="transparent")
            cell.grid(row=n // per_row, column=n % per_row, padx=4, pady=2, sticky="w")
            ctk.CTkLabel(cell, text=sel["label"], text_color="gray").pack(anchor="w")
            make(sel, cell)
        last = (len(selectors) - 1) // per_row + 1
        hint.grid(row=last, column=0, columnspan=per_row, sticky="w", padx=4)
        raw = ctk.CTkLabel(frame, text=tr("Raw value: {value}").format(value=var.get()), text_color="gray", wraplength=430, justify="left")
        raw.grid(row=last + 1, column=0, columnspan=per_row, sticky="w", padx=4)
        if spec.get("note"):
            note = InfoLabel(frame)
            note.set_info(spec["note"])
            note.grid(row=last + 2, column=0, columnspan=per_row, sticky="w", padx=4)

        def on_write(*_a):
            raw.configure(text=tr("Raw value: {value}").format(value=var.get()))

        var.trace_add("write", on_write)
        frame._refresh = refresh
        frame._availability = availability
        frame._warning = warning
        refresh()
        return frame

    def _on_edit(self, key: str):
        if not self._busy:
            self._record(key)
            self._update_warnings()
        if self.var_changed.get() and not self._busy:
            self._schedule_filter()
        self._paint_mark(key)

    def _paint_mark(self, key: str):
        """Yellow frame of a row while its value differs from the loaded file. A dropdown that is a combination of several parameters
        (Gamma Category with its select) counts as changed when any of them is."""
        widget = self.entries.get(key)
        if widget is None:      # row of a collapsed block that is not built yet (marked when it is built)
            return
        ids = {key} | set(getattr(widget, "_derived_deps", ()))
        changed = any(self.vars[pid].get() != self.original.get(pid) for pid in ids if pid in self.vars)
        if isinstance(widget, ctk.CTkFrame) and hasattr(widget, "_mark"):
            widget._mark.configure(border_color=CHANGED_COLOR if changed else self._c["card"])
        elif isinstance(widget, ctk.CTkFrame):
            widget.configure(border_width=2 if changed else 0)
        else:
            widget.configure(highlightbackground=CHANGED_COLOR if changed else self._c["border"])

    def _collect(self):
        self.scene.name = self.var_name.get()
        self.scene.number = self.var_number.get()
        for key, var in self.vars.items():
            self.scene.params[key] = var.get()

    def save(self):
        if not self.scene:
            return
        self._collect()
        target = self._target_path()
        if target is None:
            self.save_as()
        else:
            self._write(target)

    def save_as(self):
        if not self.scene:
            return
        self._collect()
        folder = self.scene.path.parent if self.scene.path else self._last_dir
        path = filedialog.asksaveasfilename(
            title=tr("Save file"),
            defaultextension=self._ext(),
            initialfile=self._file_label(),
            initialdir=str(folder) if folder else None,
            filetypes=[("Sony ALL File", "*.ALL")] if self.kind == "all" else [("Sony SCENE File", "*.SCENE")],
        )
        if path:
            self._write(Path(path))

    def _write(self, path: Path):
        self._collect()
        warnings = self._warnings()
        if warnings and not messagebox.askyesno(
            APP_NAME, tr("The file contains implausible values:\n\n{warnings}\n\nSave anyway?").format(warnings="\n".join(warnings))
        ):
            return
        loaded = self.scene.path
        if path.exists() and not (loaded and path.resolve() == loaded.resolve()) and not messagebox.askyesno(
            APP_NAME, tr("{name} already exists in this folder. Overwrite?").format(name=path.name)
        ):
            return
        try:
            self.scene.save(path)
        except OSError as exc:
            messagebox.showerror(APP_NAME, tr("Saving failed:\n{error}").format(error=exc))
            return
        self.scene.number = path.stem if len(path.stem) == 3 and path.stem.isdigit() else self.scene.number
        self._last_dir = path.parent
        save_settings(last_dir=str(path.parent))
        self._populate()
        self.lbl_status.configure(text=tr("Saved: {path}").format(path=path))
        self._saved = self._state_key()
        self._update_title()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="SonyConfigEditor",
        description=tr("Reads, converts and writes configuration files of Sony cinema cameras (.SCENE; .ALL prepared)."),
    )
    parser.add_argument("file", nargs="?", type=Path, help=tr("File to open at start-up (*.SCENE)"))
    parser.add_argument("--version", action="version", version=f"{APP_NAME} {_version} ({_date})")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    init_language()
    args = parse_args(argv)
    if args.file is not None and not args.file.is_file():
        print(tr("File not found: {file}").format(file=args.file), file=sys.stderr)
        return 2
    app = App()
    if args.file is not None:
        app.after(100, lambda: app.open_path(args.file))
    app.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
