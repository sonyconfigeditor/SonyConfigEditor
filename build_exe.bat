@echo off
REM Builds a single-file Windows EXE of the Sony Config Editor with PyInstaller.
REM Result: dist\SonyConfigEditor.exe. The version (from _version in SonyConfigEditor.py)
REM is embedded in the file properties (Details tab), not in the file name.
setlocal
cd /d "%~dp0"

REM 1. Is there a usable Python at all? (the Microsoft Store stub "python.exe" counts as missing)
python -c "import sys" >nul 2>&1
if errorlevel 1 (
    echo Python was not found.
    echo   Install Python 3.10 or newer from https://www.python.org/downloads/ ^(tick "Add python.exe to PATH" in the installer^),
    echo   or run:  winget install Python.Python.3.12
    echo   Then open a NEW command prompt and start build_exe.bat again.
    echo   If Python is installed but not on the PATH, start it via the launcher:  py -3 tools\check_build_env.py
    exit /b 1
)

REM 2. Python version, Tkinter, libraries, PyInstaller and the data files: every missing item is listed with the command that fixes it
python tools\check_build_env.py
if errorlevel 1 (
    echo.
    echo The build was not started. Fix the items marked MISSING above, then run build_exe.bat again.
    exit /b 1
)

python tools\make_version_info.py build\version_info.txt
if errorlevel 1 (
    echo Could not create the version file.
    exit /b 1
)

python -m PyInstaller --noconfirm --clean --onefile --windowed ^
    --name SonyConfigEditor ^
    --icon assets\sonyconfigeditor.ico ^
    --version-file build\version_info.txt ^
    --collect-data customtkinter ^
    --add-data "scene_parameters.json;." ^
    --add-data "all_parameters.json;." ^
    --add-data "user_parameters.json;." ^
    --add-data "user_menu_items.json;." ^
    --add-data "id_map.json;." ^
    --add-data "defaults.json;." ^
    --add-data "LICENSE;." ^
    --add-data "THIRD_PARTY_NOTICES.md;." ^
    --add-data "assets;assets" ^
    --add-data "translations;translations" ^
    --add-data "templates;templates" ^
    SonyConfigEditor.py
if errorlevel 1 (
    echo Build failed.
    exit /b 1
)

echo.
echo Done: %~dp0dist\SonyConfigEditor.exe
endlocal
