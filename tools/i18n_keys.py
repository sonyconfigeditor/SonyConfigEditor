"""List the texts that need a translation (English source texts) and check translations/<code>.json.

    python -X utf8 -I tools/i18n_keys.py            # all keys with their state per language
    python -X utf8 -I tools/i18n_keys.py --missing  # only the keys without translation

Keys are collected from the code (calls of tr(), tr_all(), _tr_width(); the lists ABOUT_TEXTS and MENU_TEXTS) and from the
parameter databases (notes, lock reasons, messages, check box texts). Dropdown labels and choices of the databases are camera menu
names, mostly identical in every language: they count as keys only if some catalog translates them.
"""
import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLACEHOLDER = re.compile(r"\{[a-z_]+\}")


def code_keys() -> list[str]:
    tree = ast.parse((ROOT / "SonyConfigEditor.py").read_text(encoding="utf-8"))
    keys = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
            name = node.func.id if isinstance(node.func, ast.Name) else node.func.attr if isinstance(node.func, ast.Attribute) else ""
            if name in ("tr", "tr_all", "_tr_width"):
                keys.append(node.args[0].value)
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in ("ABOUT_TEXTS", "MENU_TEXTS") for t in node.targets):
            keys.extend(c.value for c in ast.walk(node.value) if isinstance(c, ast.Constant) and isinstance(c.value, str))
    return keys


def db_keys(translated: set[str]) -> list[str]:
    out = []

    def walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if k in ("note", "reason", "message", "message_4k", "message_2k", "help") and isinstance(v, str):
                    out.append(v)
                elif k in ("text", "label") and isinstance(v, str):
                    if v in translated or (k == "text" and v.endswith("active")):
                        out.append(v)
                elif k == "choices" and isinstance(v, dict):
                    out.extend(x for x in v.values() if isinstance(x, str) and x in translated)
                elif k not in ("evidence",):
                    walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    for name in ("scene_parameters.json", "all_parameters.json", "user_menu_items.json"):
        walk(json.loads((ROOT / name).read_text(encoding="utf-8")))
    return out


def catalogs() -> dict[str, dict]:
    out = {}
    for path in sorted((ROOT / "translations").glob("*.json")):
        out[path.stem] = json.loads(path.read_text(encoding="utf-8"))
    return out


def all_keys() -> list[str]:
    translated = {k for cat in catalogs().values() for k in cat if not k.startswith("_")}
    return list(dict.fromkeys(code_keys() + db_keys(translated)))


def placeholder_problems() -> list[str]:
    """Translations whose {placeholders} differ from the source text."""
    bad = []
    for code, cat in catalogs().items():
        for key, value in cat.items():
            if not key.startswith("_") and isinstance(value, str) and sorted(PLACEHOLDER.findall(key)) != sorted(PLACEHOLDER.findall(value)):
                bad.append(f"{code}: {key[:60]!r}")
    return bad


if __name__ == "__main__":
    cats = catalogs()
    keys = all_keys()
    only_missing = "--missing" in sys.argv
    missing_total = 0
    for key in keys:
        state = {code: key in cat for code, cat in cats.items()}
        if not all(state.values()):
            missing_total += 1
        if not only_missing or not all(state.values()):
            print(("  " if all(state.values()) else "!!") + " " + repr(key) + ("" if all(state.values()) else "  missing in: " + ", ".join(c for c, ok in state.items() if not ok)))
    for problem in placeholder_problems():
        print("!! placeholder mismatch", problem)
    print(f"{len(keys)} keys, {missing_total} without translation in at least one language ({', '.join(cats) or 'no catalog'})")
