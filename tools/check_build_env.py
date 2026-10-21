"""Checks that everything is there to run or build the Sony Config Editor and says how to fix what is missing.

    python tools/check_build_env.py              # Python, Tkinter, libraries, then PyInstaller (what build_exe.bat needs)
    python tools/check_build_env.py --install-ok # missing pip packages are fine (build_app.sh installs them into its own virtual environment)

Order of the checks: 1. Python (version, 64 bit), 2. Tkinter, 3. the libraries of the program (customtkinter, Pillow), 4. PyInstaller,
5. the data files the build packs. Every missing item gets a clear message and the command that fixes it. Exit code 0 = ready, 1 = something is missing.
Only the standard library is used, so the script runs even when nothing else is installed.
"""
import importlib.util
import os
import platform
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MIN_PYTHON = (3, 10)
PIP_ALL = "python -m pip install --upgrade customtkinter pillow pyinstaller"
DATA_FILES = ["SonyConfigEditor.py", "scene_parameters.json", "all_parameters.json", "user_parameters.json", "user_menu_items.json", "id_map.json", "defaults.json",
              "LICENSE", "THIRD_PARTY_NOTICES.md", "assets/sonyconfigeditor.ico", "translations/de.json", "templates/PXW-FS7M2.SCENE"]


def has_module(name: str) -> bool:
    """True if the module can be imported (found without importing it, so a broken package does not stop the check)."""
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def tkinter_works() -> bool:
    try:
        import tkinter  # noqa: F401
        return True
    except ImportError:
        return False


def pyinstaller_version() -> str | None:
    """Version text of PyInstaller for this Python, None if it cannot be run."""
    try:
        done = subprocess.run([sys.executable, "-m", "PyInstaller", "--version"], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout.strip() or "?" if done.returncode == 0 else None


def tkinter_hint(system: str) -> str:
    if system == "Windows":
        return ("Python from the python.org installer includes Tkinter. Run the installer again, choose 'Modify' and tick 'tcl/tk and IDLE'\n"
                "      (Python from the Microsoft Store and some other builds come without it: use the python.org installer, https://www.python.org/downloads/).")
    if system == "Darwin":
        return "Install Python from python.org (it includes Tk), or:  brew install python-tk"
    return "Debian/Ubuntu: sudo apt install python3-tk   |   Fedora: sudo dnf install python3-tkinter   |   Arch: sudo pacman -S tk"


def python_hint(system: str) -> str:
    if system == "Windows":
        return ("Install Python 3.10 or newer from https://www.python.org/downloads/ (tick 'Add python.exe to PATH' in the installer), "
                "or:  winget install Python.Python.3.12\n      Then open a new command prompt and start this script again.")
    if system == "Darwin":
        return "Install Python 3.10 or newer from https://www.python.org/downloads/ or:  brew install python"
    return "Install Python 3.10 or newer, e.g.  sudo apt install python3  /  sudo dnf install python3"


def run_checks(install_ok: bool = False, system: str | None = None, module_present=has_module, tk_present=tkinter_works,
               pyinstaller=pyinstaller_version, root: Path = ROOT) -> tuple[list[str], list[str]]:
    """Returns (lines to print, problems). A line starts with 'ok', 'MISSING', 'warning' or a hint indented below it."""
    system = system or platform.system()
    lines: list[str] = []
    problems: list[str] = []

    def report(ok: bool, text: str, fix: str = "", warn_only: bool = False):
        lines.append(("ok       " if ok else ("warning  " if warn_only else "MISSING  ")) + text)
        if not ok:
            if fix:
                lines.append("      -> " + fix)
            if not warn_only:
                problems.append(text)

    # 1. Python
    version = sys.version_info[:3]
    report(version >= MIN_PYTHON, f"Python {'.'.join(map(str, version))} ({sys.executable})",
           f"Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]} or newer is needed.\n      " + python_hint(system))
    if struct.calcsize("P") * 8 != 64:
        report(False, "32-bit Python", "A 64-bit Python is recommended (some libraries have no 32-bit packages).", warn_only=True)
    if version < MIN_PYTHON:
        return lines, problems      # the rest cannot be judged with a Python this old

    # 2. Tkinter
    report(tk_present(), "Tkinter (the window library of Python)", tkinter_hint(system))
    # 3. libraries of the program
    pip_fix = PIP_ALL.replace("python", "python" if system == "Windows" else "python3", 1)
    for name, label, needed in (("customtkinter", "customtkinter (the program's window widgets)", True), ("PIL", "Pillow (only the logo in the About dialog)", False)):
        present = module_present(name)
        report(present or (install_ok and needed), label + (" - will be installed by the build script" if not present and install_ok and needed else ""),
               f"Install it with:  {pip_fix}" + ("" if system == "Windows" else
                                                 "\n      (If pip says 'externally-managed-environment' use a virtual environment: python3 -m venv .venv, activate it, and install again.)")
               if needed else "Optional: the program starts without it (no logo). Install it with:  python -m pip install pillow", warn_only=not needed)
    # 4. PyInstaller
    if install_ok:
        lines.append("ok        PyInstaller: will be installed by the build script")
    else:
        found = pyinstaller()
        report(found is not None, f"PyInstaller {found}" if found else "PyInstaller (builds the executable)",
               "Install it with:  python -m pip install --upgrade pyinstaller\n      (all missing pieces at once:  " + pip_fix + ")")
    # 5. data files of the build
    missing = [name for name in DATA_FILES if not (root / name).exists()]
    report(not missing, "data files of the program" if not missing else f"data files missing: {', '.join(missing)}",
           "Run the script from the project folder of the source code (it was probably not unpacked completely).")
    return lines, problems


def main(argv: list[str]) -> int:
    install_ok = "--install-ok" in argv
    print(f"Checking the environment for building the Sony Config Editor ({platform.system()} {platform.release()}):")
    lines, problems = run_checks(install_ok=install_ok)
    for line in lines:
        print("  " + line)
    if problems:
        print(f"\n{len(problems)} problem(s): fix them (see the lines starting with '->') and start the build again.")
        return 1
    print("\nEverything needed is there.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
