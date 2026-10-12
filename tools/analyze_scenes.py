"""Compares SCENE files and reports per-ID value statistics and pairwise diffs."""
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from SonyConfigEditor import SceneFile

root = Path(__file__).resolve().parent.parent
# only the 9 reference files per model (001-009); other files in the folders are user files
sets = {m: [SceneFile.load(p) for p in sorted((root / m).glob("00[1-9].SCENE"))] for m in ("PXW-FS7", "PXW-FS7M2")}

print("# Scene names")
for m, files in sets.items():
    print(m, [f.name for f in files])

print("\n# Per-ID values (file index 1..9 -> value)")
ids = sorted({k for fs in sets.values() for f in fs for k in f.params})
for k in ids:
    for m, fs in sets.items():
        vals = [f.params.get(k) for f in fs]
        if all(v is None for v in vals):
            continue
        uniq = len({v for v in vals})
        tag = "const" if uniq == 1 else f"{uniq} distinct"
        print(f"{k} {m:10} {tag:11} {' | '.join('-' if v is None else v.strip() for v in vals)}")

print("\n# Pairwise diffs within PXW-FS7M2 (known by description)")
fs = sets["PXW-FS7M2"]
pairs = [(0, 1, "HG4 vs HG3 neutral"), (2, 3, "sample look vs 2 (HG7 vs HG8)"), (4, 5, "sample look HG3 vs HG4"), (6, 7, "Kodak 3200 vs 5600")]
for a, b, label in pairs:
    d = [(k, fs[a].params.get(k), fs[b].params.get(k)) for k in ids if fs[a].params.get(k) != fs[b].params.get(k)]
    print(f"\n{fs[a].name} vs {fs[b].name}  [{label}]")
    for k, x, y in d:
        print(f"  {k}: {x} -> {y}")
