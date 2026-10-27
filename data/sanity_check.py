#!/usr/bin/env python3
"""Quick sanity load of the downloaded calibration datasets (stdlib only).

Run from the repo root:  python3 -I data/sanity_check.py [--skip-tracking]

Prints row counts for the Wyscout public dataset (per competition) and the
DFL/IDSSE matches (events, 25 Hz frames, tracked objects). Parsing the seven
~370 MB tracking XMLs takes a few minutes; --skip-tracking skips them.
"""
from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

RAW = Path(__file__).resolve().parent / "raw"


def wyscout() -> None:
    d = RAW / "wyscout"
    print("== Wyscout public dataset (Pappalardo et al. 2019, CC BY 4.0)")
    for name in ("competitions", "teams", "players", "coaches", "referees", "playerank"):
        text = (d / f"{name}.json").read_text(encoding="utf-8")
        try:
            print(f"  {name}.json: {len(json.loads(text)):,} rows")
        except json.JSONDecodeError as exc:
            # referees.json on figshare (v1, md5 6b5b5612...) is truncated upstream mid-record.
            print(f"  {name}.json: MALFORMED upstream ({exc.msg} at char {exc.pos} of {len(text)}); "
                  f"~{text.count('{\"wyId\"')} records present")
    tot_e = tot_m = 0
    for ef in sorted((d / "events").glob("events_*.json")):
        comp = ef.stem.removeprefix("events_")
        ev = json.loads(ef.read_text(encoding="utf-8"))
        ma = json.loads((d / "matches" / f"matches_{comp}.json").read_text(encoding="utf-8"))
        n_ev_matches = len({e["matchId"] for e in ev})
        tot_e += len(ev)
        tot_m += len(ma)
        extra = ""
        if comp == "England":
            types = Counter(e["eventName"] for e in ev)
            goals = sum(
                t["score"] for m in ma for t in m["teamsData"].values()
            )
            extra = (f"  | seasonId {sorted({m['seasonId'] for m in ma})}, passes {types['Pass']:,}, "
                     f"shots {types['Shot']:,}, goals {goals} ({goals / len(ma):.2f}/match), "
                     f"events/match {len(ev) / n_ev_matches:.0f}")
        print(f"  {comp:24s} matches {len(ma):4d}  events {len(ev):9,d}  (matches with events {n_ev_matches}){extra}")
    print(f"  TOTAL                    matches {tot_m:4d}  events {tot_e:9,d}")


def idsse(skip_tracking: bool) -> None:
    d = RAW / "idsse"
    print("== DFL/IDSSE open dataset (Bassek et al. 2025, CC BY 4.0)")
    infos = sorted(d.glob("DFL_02_01_matchinformation_*.xml"))
    tot_ev = tot_fr = 0
    for info in infos:
        mid = info.stem.rsplit("_", 1)[-1]
        g = ET.parse(info).getroot().find("./MatchInformation/General")
        title = f"{g.get('CompetitionName')} {g.get('Season')} MD{g.get('MatchDay')}: {g.get('HomeTeamName')} {g.get('Result')} {g.get('GuestTeamName')}"
        evf = next(d.glob(f"DFL_03_02_events_raw_*_{mid}.xml"))
        n_ev = sum(1 for _, el in ET.iterparse(evf) if el.tag == "Event")
        tot_ev += n_ev
        line = f"  {mid}  {title}\n      events {n_ev:,}"
        posf = next(d.glob(f"DFL_04_03_positions_raw_observed_*_{mid}.xml"), None)
        if posf and not skip_tracking:
            ball_frames = 0
            objects = Counter()
            cur_team = None
            for ev, el in ET.iterparse(posf, events=("start", "end")):
                if ev == "start" and el.tag == "FrameSet":
                    cur_team = el.get("TeamId")
                    objects["ball" if cur_team == "BALL" else "referee" if cur_team == "referee" else "player"] += 1
                elif ev == "end" and el.tag == "Frame":
                    if cur_team == "BALL":
                        ball_frames += 1
                    el.clear()
                elif ev == "end" and el.tag == "FrameSet":
                    el.clear()
            tot_fr += ball_frames
            line += (f"  | 25 Hz ball frames {ball_frames:,} (= {ball_frames / 25 / 60:.1f} min)"
                     f"  | FrameSets (object x half): players {objects['player']}, referees {objects['referee']}, ball {objects['ball']}")
        print(line, flush=True)
    print(f"  TOTAL matches {len(infos)}, events {tot_ev:,}" + ("" if skip_tracking else f", ball frames {tot_fr:,}"))


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--skip-tracking", action="store_true")
    a = p.parse_args()
    wyscout()
    idsse(a.skip_tracking)
    return 0


if __name__ == "__main__":
    sys.exit(main())
