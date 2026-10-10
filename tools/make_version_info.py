"""Writes a PyInstaller version-info file (Windows file properties) from _version in SonyConfigEditor.py.

Usage: python tools/make_version_info.py <output file>
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import SonyConfigEditor as app

version = app._version
numbers = [int(p) for p in version.split(".")][:4]
numbers += [0] * (4 - len(numbers))
tup = tuple(numbers)
dotted = ".".join(map(str, tup))

content = f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={tup}, prodvers={tup}, mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([
      StringTable('040704B0', [
        StringStruct('FileDescription', '{app.APP_NAME}'),
        StringStruct('FileVersion', '{dotted}'),
        StringStruct('InternalName', 'SonyConfigEditor'),
        StringStruct('OriginalFilename', 'SonyConfigEditor.exe'),
        StringStruct('ProductName', '{app.APP_NAME}'),
        StringStruct('ProductVersion', '{version}')])
    ]),
    VarFileInfo([VarStruct('Translation', [0x0407, 1200])])
  ]
)
"""
out = Path(sys.argv[1])
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(content, encoding="utf-8")
print(f"Version {version} -> {out}")
