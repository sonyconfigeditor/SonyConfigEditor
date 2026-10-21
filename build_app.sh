#!/usr/bin/env bash
# Builds the Sony Config Editor with PyInstaller on Linux and macOS (counterpart of build_exe.bat for Windows).
#
#   Linux : dist/SonyConfigEditor            (one single executable)
#   macOS : dist/SonyConfigEditor.app        (app bundle, "onedir" inside; a onefile app bundle would unpack on every start)
#
# PyInstaller cannot cross-compile: run this script on the system you build for (Linux build on Linux, macOS build on a Mac).
# Prerequisites:
#   Python 3.10+ WITH Tkinter   Debian/Ubuntu: sudo apt install python3-tk python3-venv   |   Fedora: sudo dnf install python3-tkinter
#                               macOS: python.org installer (includes Tk) or  brew install python-tk
#   Linux: build on the OLDEST distribution you want to support (the executable needs at least the glibc of the build machine).
#
# Usage:  ./build_app.sh            (creates and uses a virtual environment in build/venv)
#         NO_VENV=1 ./build_app.sh  (uses the current Python environment)
set -euo pipefail
cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"
OS="$(uname -s)"
case "$OS" in
    Linux)  PLATFORM=linux ;;
    Darwin) PLATFORM=macos ;;
    *) echo "Unsupported system: $OS (Windows: use build_exe.bat)"; exit 1 ;;
esac

if ! command -v "$PYTHON" >/dev/null 2>&1; then
    echo "Python was not found ($PYTHON). Install Python 3.10 or newer first (Debian/Ubuntu: sudo apt install python3 python3-venv python3-tk, macOS: python.org installer or: brew install python)."
    exit 1
fi

# Python version, Tkinter and the data files; missing pip packages are fine here: they are installed into the virtual environment below
"$PYTHON" tools/check_build_env.py --install-ok || { echo; echo "The build was not started. Fix the items marked MISSING above, then run ./build_app.sh again."; exit 1; }
if [ -z "${NO_VENV:-}" ] && ! "$PYTHON" -c "import venv, ensurepip" 2>/dev/null; then
    echo "The venv module of Python is missing. Debian/Ubuntu: sudo apt install python3-venv   |   or use NO_VENV=1 ./build_app.sh with your own environment."
    exit 1
fi

if [ -z "${NO_VENV:-}" ]; then
    "$PYTHON" -m venv build/venv
    # shellcheck disable=SC1091
    source build/venv/bin/activate
    PYTHON=python
fi
"$PYTHON" -m pip install --quiet --upgrade pip
"$PYTHON" -m pip install --quiet --upgrade pyinstaller customtkinter

# --add-data uses ":" between source and target on Linux/macOS (";" on Windows)
COMMON=(
    --noconfirm --clean --windowed
    --name SonyConfigEditor
    --collect-data customtkinter
    --add-data "scene_parameters.json:."
    --add-data "all_parameters.json:."
    --add-data "user_parameters.json:."
    --add-data "user_menu_items.json:."
    --add-data "id_map.json:."
    --add-data "defaults.json:."
    --add-data "LICENSE:."
    --add-data "THIRD_PARTY_NOTICES.md:."
    --add-data "assets:assets"
    --add-data "translations:translations"
    --add-data "templates:templates"
)

if [ "$PLATFORM" = "macos" ]; then
    VERSION="$("$PYTHON" -c "import SonyConfigEditor as a; print(a._version)")"
    # --target-architecture universal2 only works if Python and all binary packages are universal2; the default is the architecture of this Mac
    "$PYTHON" -m PyInstaller "${COMMON[@]}" --onedir \
        --osx-bundle-identifier "org.sonyconfigeditor.app" \
        SonyConfigEditor.py
    /usr/libexec/PlistBuddy -c "Add :CFBundleShortVersionString string $VERSION" dist/SonyConfigEditor.app/Contents/Info.plist 2>/dev/null \
        || /usr/libexec/PlistBuddy -c "Set :CFBundleShortVersionString $VERSION" dist/SonyConfigEditor.app/Contents/Info.plist || true
    echo
    echo "Done: $(pwd)/dist/SonyConfigEditor.app"
    echo "Not signed: on first start use right-click > Open (Gatekeeper). Signing/notarization needs an Apple developer account."
else
    "$PYTHON" -m PyInstaller "${COMMON[@]}" --onefile SonyConfigEditor.py
    echo
    echo "Done: $(pwd)/dist/SonyConfigEditor"
fi
