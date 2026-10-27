#!/usr/bin/env python3
"""Download the open football datasets used to calibrate/validate the synthetic generator.

These datasets are reference statistics ONLY. They are never runtime match data
and nothing under data/raw/ is ever committed (see data/.gitignore).

Datasets (both CC BY 4.0, figshare):
  wyscout  Pappalardo et al. 2019, Sci Data 6:236. Collection 10.6084/m9.figshare.c.4415000
  idsse    Bassek et al. 2025, Sci Data 12:195.   Article    10.6084/m9.figshare.28196177.v1

Usage (from the repo root):
  python3 -I data/download.py                       # everything
  python3 -I data/download.py --dataset wyscout     # one dataset
  python3 -I data/download.py --dataset idsse --no-tracking   # IDSSE without the 2.6 GB of 25 Hz XML
  python3 -I data/download.py --dry-run             # print the plan and sizes only
  python3 -I data/download.py --verify              # re-hash files already on disk

Idempotent: a file that exists with the expected size and MD5 is skipped. Downloads
go to <name>.part and are renamed only after the MD5 matches figshare's computed_md5.
Zip archives are extracted next to themselves (with a path-traversal guard) into a
folder named after the archive. Stdlib only.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

RAW = Path(__file__).resolve().parent / "raw"
MAX_BYTES = 3 * 1024**3  # skip (and report) any single file larger than 3 GB
UA = "inside-the-game-hackathon-data-download/1.0 (+figshare open data; calibration only)"

# Pinned manifest: (figshare article id, file id, filename, size bytes, md5).
# Taken from https://api.figshare.com/v2/articles/<id> on 2026-10-27.
WYSCOUT = [
    (7770599, 14464685, "events.zip", 77323413, "7c20e8647e7eda58d7838a0c7b1ec6ab"),
    (7770422, 14464622, "matches.zip", 645097, "51d80beb17480919f69a53a0152c2d71"),
    (7765196, 15073721, "players.json", 1737347, "f28ddf6326281efeda6488b2169f5609"),
    (7765310, 15073697, "teams.json", 27404, "1381ff9449f21105090729cf0e086b5b"),
    (7765316, 15073685, "competitions.json", 1209, "3dc210a4805dda5337b0ff9f7eaa407a"),
    (8082650, 15073868, "coaches.json", 70664, "ee8afad14b5be622b1d3560d15248778"),
    (8082665, 15074030, "referees.json", 196709, "6b5b5612e128238f0f28a355cc13796a"),
    (9361148, 16972010, "playerank.json", 6241757, "dbb3671e04eb37f30ef4006986748812"),
    (11743836, 21385245, "eventid2name.csv", 1001, "46daf16100ece0c743eedc9adcfea162"),
    (11743818, 21385239, "tags2name.csv", 1754, "e7acb14918d00e40c80a898b1da8fc39"),
]

_I = 28196177
IDSSE = [
    (_I, 51643475, "DFL_02_01_matchinformation_DFL-COM-000001_DFL-MAT-J03WMX.xml", 11930, "bc5d5b21dbcf36aa30f4cd0428309f6b"),
    (_I, 51643472, "DFL_02_01_matchinformation_DFL-COM-000001_DFL-MAT-J03WN1.xml", 11722, "37b0f85588c0acfb995fe633c7ac2e0d"),
    (_I, 51643478, "DFL_02_01_matchinformation_DFL-COM-000002_DFL-MAT-J03WOH.xml", 11745, "b9710781d400dd812f62b0a6e3d7bce8"),
    (_I, 51643481, "DFL_02_01_matchinformation_DFL-COM-000002_DFL-MAT-J03WOY.xml", 11952, "7b021e577fca917a63111d55cc29ae5b"),
    (_I, 51643487, "DFL_02_01_matchinformation_DFL-COM-000002_DFL-MAT-J03WPY.xml", 11922, "65a4568e4f374af94d3c1015cbc7c4f5"),
    (_I, 51643484, "DFL_02_01_matchinformation_DFL-COM-000002_DFL-MAT-J03WQQ.xml", 11932, "5979209af316a914ce57347d0633df6c"),
    (_I, 51643490, "DFL_02_01_matchinformation_DFL-COM-000002_DFL-MAT-J03WR9.xml", 11823, "5e2d580d3d8ed97e32959de90d04992b"),
    (_I, 51643493, "DFL_03_02_events_raw_DFL-COM-000001_DFL-MAT-J03WMX.xml", 776578, "2d88e180a1f63c7e4157feb980fc7255"),
    (_I, 51643496, "DFL_03_02_events_raw_DFL-COM-000001_DFL-MAT-J03WN1.xml", 612114, "83e8ed7ea8e8ebbbdc61f61ac3534008"),
    (_I, 51643499, "DFL_03_02_events_raw_DFL-COM-000002_DFL-MAT-J03WOH.xml", 635747, "ab66e51512f39d06f49f27dd3b4c2f40"),
    (_I, 51643502, "DFL_03_02_events_raw_DFL-COM-000002_DFL-MAT-J03WOY.xml", 683018, "64b1be01d6ff6848168efebd56f344b9"),
    (_I, 51643505, "DFL_03_02_events_raw_DFL-COM-000002_DFL-MAT-J03WPY.xml", 698898, "f68482441d38723d69f244f896482803"),
    (_I, 51643508, "DFL_03_02_events_raw_DFL-COM-000002_DFL-MAT-J03WQQ.xml", 732186, "b7e9d82af4034539d802319be6c57776"),
    (_I, 51643511, "DFL_03_02_events_raw_DFL-COM-000002_DFL-MAT-J03WR9.xml", 681050, "c13bc5efa5eca4a022cc678210b87d5f"),
    (_I, 51643514, "DFL_04_03_positions_raw_observed_DFL-COM-000001_DFL-MAT-J03WMX.xml", 418524833, "e4273a2adf5dbd9d4ec42def2f01905c"),
    (_I, 51643517, "DFL_04_03_positions_raw_observed_DFL-COM-000001_DFL-MAT-J03WN1.xml", 391722803, "bacb2f609c1d1b0bfc906f6b9d4109f2"),
    (_I, 51643520, "DFL_04_03_positions_raw_observed_DFL-COM-000002_DFL-MAT-J03WOH.xml", 348945715, "3efff25a86a61768e7d253b4bba137a3"),
    (_I, 51643523, "DFL_04_03_positions_raw_observed_DFL-COM-000002_DFL-MAT-J03WOY.xml", 362567859, "4e1063e0a0ae499920cf68ac1aa3ab4e"),
    (_I, 51643526, "DFL_04_03_positions_raw_observed_DFL-COM-000002_DFL-MAT-J03WPY.xml", 371688499, "e56ff1336a334f8da51110fbe7cab764"),
    (_I, 51643529, "DFL_04_03_positions_raw_observed_DFL-COM-000002_DFL-MAT-J03WQQ.xml", 356219423, "9105bad987191d3c3c362c1fce9a4fcd"),
    (_I, 51643532, "DFL_04_03_positions_raw_observed_DFL-COM-000002_DFL-MAT-J03WR9.xml", 372934140, "e060bb7d7a5a3bfbd15bbf9bc631024d"),
]

DATASETS = {"wyscout": WYSCOUT, "idsse": IDSSE}


def human(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024
    return str(n)


def md5_of(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def is_ok(path: Path, size: int, md5: str) -> bool:
    return path.is_file() and path.stat().st_size == size and md5_of(path) == md5


def fetch(file_id: int, dest: Path, size: int, md5: str, retries: int = 3) -> None:
    url = f"https://ndownloader.figshare.com/files/{file_id}"
    tmp = dest.with_name(dest.name + ".part")
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            h = hashlib.md5()
            got = 0
            t0 = time.time()
            with urllib.request.urlopen(req, timeout=60) as r, tmp.open("wb") as out:
                while chunk := r.read(1 << 20):
                    out.write(chunk)
                    h.update(chunk)
                    got += len(chunk)
                    if size > 50 * 1024**2 and got % (100 * 1024**2) < (1 << 20):
                        print(f"      {human(got)} / {human(size)} ({got / max(1e-9, time.time() - t0) / 1e6:.1f} MB/s)", flush=True)
            if got != size or h.hexdigest() != md5:
                raise IOError(f"integrity check failed: got {got} B md5 {h.hexdigest()}, expected {size} B md5 {md5}")
            os.replace(tmp, dest)
            return
        except Exception as exc:  # noqa: BLE001 - retry on any network/integrity error
            print(f"    attempt {attempt}/{retries} failed: {exc}", file=sys.stderr)
            tmp.unlink(missing_ok=True)
            if attempt == retries:
                raise
            time.sleep(5 * attempt)


def safe_extract(zpath: Path) -> Path:
    """Extract <x>.zip into <x>/ (sibling folder), refusing absolute or '..' member paths."""
    target = zpath.with_suffix("")
    marker = target / ".extracted"
    if marker.is_file() and marker.read_text().strip() == md5_of(zpath):
        return target
    target.mkdir(exist_ok=True)
    root = target.resolve()
    with zipfile.ZipFile(zpath) as z:
        for m in z.infolist():
            out = (target / m.filename).resolve()
            if not out.is_relative_to(root):
                raise RuntimeError(f"refusing unsafe zip member path: {m.filename!r}")
            if m.filename.startswith("__MACOSX/"):
                continue
            z.extract(m, target)
    marker.write_text(md5_of(zpath) + "\n")
    return target


def run(name: str, files, args) -> list[str]:
    outdir = RAW / name
    outdir.mkdir(parents=True, exist_ok=True)
    total = sum(f[3] for f in files)
    print(f"[{name}] {len(files)} files, {human(total)} -> {outdir}")
    skipped = []
    for article, file_id, fname, size, md5 in files:
        dest = outdir / fname
        print(f"  {fname}  ({human(size)}, figshare article {article}, file {file_id})")
        if size > MAX_BYTES:
            print(f"    SKIP: larger than {human(MAX_BYTES)}")
            skipped.append(fname)
            continue
        if args.dry_run:
            continue
        if dest.is_file() and dest.stat().st_size == size and (not args.verify or md5_of(dest) == md5):
            print("    ok (already present)")
        elif args.verify and dest.is_file():
            print("    MD5/size mismatch -> re-downloading")
            fetch(file_id, dest, size, md5)
        else:
            fetch(file_id, dest, size, md5)
            print("    downloaded, md5 ok")
        if fname.endswith(".zip"):
            print(f"    extracted -> {safe_extract(dest)}")
    return skipped


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dataset", choices=sorted(DATASETS), action="append", help="repeatable; default: all")
    p.add_argument("--no-tracking", action="store_true", help="IDSSE: skip the 7 x ~370 MB 25 Hz position files")
    p.add_argument("--dry-run", action="store_true", help="print the plan and sizes, download nothing")
    p.add_argument("--verify", action="store_true", help="MD5-check files already on disk (slower)")
    args = p.parse_args()
    skipped = []
    for name in args.dataset or sorted(DATASETS):
        files = DATASETS[name]
        if name == "idsse" and args.no_tracking:
            files = [f for f in files if "_positions_" not in f[2]]
        skipped += run(name, files, args)
    if skipped:
        print("Skipped (> 3 GB):", ", ".join(skipped))
    return 0


if __name__ == "__main__":
    sys.exit(main())
