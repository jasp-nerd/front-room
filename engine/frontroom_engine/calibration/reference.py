"""The cached reference statistics that the realism scorecard compares against.

The raw open data is gigabytes and git-ignored, so the aggregate numbers are computed once and
committed as `reference_stats.json`. Tests and the scorecard only ever read that file.
"""

import json
from pathlib import Path
from typing import Any

from frontroom_engine.calibration.idsse import idsse_reference
from frontroom_engine.calibration.wyscout import wyscout_reference

REFERENCE_PATH = Path(__file__).with_name("reference_stats.json")

ATTRIBUTION = (
    "Contains information derived from the Wyscout public dataset (Pappalardo et al., 2019, "
    "Scientific Data 6, 236, doi:10.1038/s41597-019-0247-7, CC BY 4.0) and the IDSSE dataset "
    "(Bassek et al., 2025, Scientific Data 12, 195, doi:10.1038/s41597-025-04505-y, CC BY 4.0; official "
    "match data provided by DFL / Sportec Solutions). "
    "Only aggregate statistics are stored; changes were made."
)


def build_reference(raw_dir: Path) -> dict[str, Any]:
    """Recompute every reference statistic from `data/raw` (wyscout/ and idsse/ subfolders)."""
    wyscout = raw_dir / "wyscout"
    return {
        "attribution": ATTRIBUTION,
        "events": wyscout_reference(
            wyscout / "events" / "events_England.json", wyscout / "matches" / "matches_England.json"
        ),
        "tracking": idsse_reference(raw_dir / "idsse"),
    }


def _rounded(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 4)
    if isinstance(value, dict):
        return {key: _rounded(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_rounded(item) for item in value]
    return value


def write_reference(raw_dir: Path, path: Path = REFERENCE_PATH) -> dict[str, Any]:
    reference = _rounded(build_reference(raw_dir))
    path.write_text(json.dumps(reference, indent=2) + "\n")
    return reference


def load_reference(path: Path = REFERENCE_PATH) -> dict[str, Any]:
    return json.loads(path.read_text())
