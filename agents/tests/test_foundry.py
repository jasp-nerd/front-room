import asyncio

import pytest

from frontroom_agents.evals.foundry_evaluators import (
    FactCheckEvaluator,
    FairnessEvaluator,
    PrivacyEvaluator,
    SafeLanguageEvaluator,
    SpoilerEvaluator,
)
from frontroom_agents.evals.foundry_rooms import RecordingHub
from frontroom_agents.foundry import settings as foundry_settings

STORY = {
    "verdict": "shared",
    "origin_player": "Mensah",
    "origin_action": "press",
    "origin_where": "on halfway",
    "passes": 5,
    "scorer": "Okafor",
    "credited_player": "",
    "credited_action": "",
}
COPY = {
    "en_headline": "It started with Mensah's press",
    "en_line": "Mensah won it back on halfway. Five passes later, Okafor scored.",
    "es_headline": "Empezó con la presión de Mensah",
    "es_line": "Mensah la recuperó en el centro. Cinco pases después, marcó Okafor.",
}
ROSTER = ["Mensah", "Okafor", "Lund"]


def test_fact_check_passes_supported_copy_and_fails_a_wrong_count():
    assert FactCheckEvaluator()(copy=COPY, story=STORY, roster=ROSTER)["fact_check"] == 1.0
    wrong = COPY | {"en_line": "Mensah won it back on halfway. Four passes later, Okafor scored."}
    result = FactCheckEvaluator()(copy=wrong, story=STORY, roster=ROSTER)
    assert result["fact_check"] == 0.0
    assert "passes" in result["fact_check_reason"]


@pytest.mark.parametrize(
    ("both_clubs", "partisan", "held"),
    [(True, False, 1.0), (True, True, 0.0), (False, True, 1.0)],
)
def test_fairness_allows_one_club_overlays_only_when_one_club_is_here(both_clubs, partisan, held):
    result = FairnessEvaluator()(
        both_clubs=both_clubs, winner="kestrel-pressing-map", winner_partisan=partisan
    )
    assert result["fairness"] == held


def test_privacy_catches_a_fan_name_and_a_private_wish_but_not_the_match_itself():
    fans = {"rob": "Show me the shape, I want numbers.", "maya": "Tactics please, how did we press?"}
    context = "Verified facts: Mensah press on halfway."
    clean = (
        "It started with Mensah's press Five passes later, Okafor scored 2 of 2 in the room asked for this."
    )
    assert PrivacyEvaluator()(tv_text=clean, fans=fans, roster=ROSTER, context=context)["privacy"] == 1.0
    named = PrivacyEvaluator()(tv_text="Rob called it: " + clean, fans=fans, roster=ROSTER, context=context)
    assert named["privacy"] == 0.0
    wish = PrivacyEvaluator()(tv_text=clean + " Tactics corner.", fans=fans, roster=ROSTER, context=context)
    assert wish["privacy"] == 0.0


def test_spoiler_requires_the_tv_first():
    tv_first = [
        {"screen": "tv", "order": 3, "pts": 100, "on_tv": True},
        {"screen": "phone:rob", "order": 4, "pts": 100, "on_tv": False},
    ]
    phone_first = [
        {"screen": "phone:rob", "order": 3, "pts": 100, "on_tv": False},
        {"screen": "tv", "order": 4, "pts": 100, "on_tv": True},
    ]
    assert SpoilerEvaluator()(sends=tv_first)["spoiler"] == 1.0
    assert SpoilerEvaluator()(sends=phone_first)["spoiler"] == 0.0


def test_safe_language_finds_odds_and_blame():
    assert (
        SafeLanguageEvaluator()(tv_text="Okafor scored", phone_texts=["Five passes"])["safe_language"] == 1.0
    )
    odds = SafeLanguageEvaluator()(tv_text="Kestrel now 3/1", phone_texts=[])
    blame = SafeLanguageEvaluator()(tv_text="", phone_texts=["The keeper's howler"])
    assert odds["safe_language"] == 0.0 and blame["safe_language"] == 0.0


def test_recording_hub_keeps_every_message_in_order():
    hub = RecordingHub()
    asyncio.run(hub.send("r", "tv", {"type": "cue"}))
    asyncio.run(hub.broadcast("r", {"type": "decision"}, ("room",)))
    assert [screen for screen, _ in hub.sent] == ["tv", "room"]


def test_foundry_settings_name_what_is_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(foundry_settings, "ENV_FILE", tmp_path / "missing.env")
    for key in ("FRONTROOM_FOUNDRY_ENDPOINT", "FRONTROOM_FOUNDRY_KEY"):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(RuntimeError, match="FRONTROOM_FOUNDRY_KEY"):
        foundry_settings.settings()
