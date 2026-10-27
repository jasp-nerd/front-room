import json
from pathlib import Path

import jsonschema
import pytest
from referencing import Registry, Resource

from frontroom_engine.demo import demo_match
from frontroom_engine.io import MatchFiles, write_match
from frontroom_engine.league import League, build_league
from frontroom_engine.sim.match import MatchResult, simulate_match

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "packages" / "protocol" / "schema"


@pytest.fixture(scope="session")
def league() -> League:
    return build_league()


@pytest.fixture(scope="session")
def match(league: League) -> MatchResult:
    return simulate_match(league, "KES", "ASH", 11)


@pytest.fixture(scope="session")
def match_files(match: MatchResult, tmp_path_factory: pytest.TempPathFactory) -> MatchFiles:
    return write_match(match, tmp_path_factory.mktemp("match"))


@pytest.fixture(scope="session")
def demo(league: League, tmp_path_factory: pytest.TempPathFactory) -> MatchFiles:
    result, steering = demo_match(league)
    return write_match(result, tmp_path_factory.mktemp("demo"), steering)


def _validator(name: str) -> jsonschema.Draft202012Validator:
    resources = [
        (p.name, Resource.from_contents(json.loads(p.read_text()))) for p in SCHEMA_DIR.glob("*.json")
    ]
    schema = json.loads((SCHEMA_DIR / name).read_text())
    return jsonschema.Draft202012Validator(schema, registry=Registry().with_resources(resources))


@pytest.fixture(scope="session")
def event_validator() -> jsonschema.Draft202012Validator:
    return _validator("match-event.schema.json")


@pytest.fixture(scope="session")
def frame_validator() -> jsonschema.Draft202012Validator:
    return _validator("tracking-frame.schema.json")
