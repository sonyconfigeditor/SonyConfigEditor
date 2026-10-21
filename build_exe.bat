@echo off
REM Builds a single-file Windows EXE of the Sony Config Editor with PyInstaller.
REM Result: dist\SonyConfigEditor.exe. The version (from _version in SonyConfigEditor.py)
REM is embedded in the file properties (Details tab), not in the file name.
setlocal
cd /d "%~dp0"

python -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo PyInstaller not found. Install it with:  python -m pip install pyinstaller
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
