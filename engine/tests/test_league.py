from frontroom_engine.league import League, Role, build_league


def test_same_seed_builds_the_same_league() -> None:
    assert build_league(2026) == build_league(2026)


def test_different_seed_changes_the_drawn_clubs_but_not_the_demo_clubs() -> None:
    first, second = build_league(1), build_league(2)
    assert first.club("BRA").squad != second.club("BRA").squad
    assert first.club("KES").style == second.club("KES").style


def test_twenty_clubs_with_squads_of_twenty_three(league: League) -> None:
    assert len(league.clubs) == 20
    assert len({club.short for club in league.clubs}) == 20
    for club in league.clubs:
        assert len(club.squad) == 23
        assert len({p.number for p in club.squad}) == 23
        assert len(club.starting_eleven()) == 11
        assert sum(p.role == Role.GK for p in club.squad) == 3


def test_demo_cast_is_in_place(league: League) -> None:
    kestrel, ashvale = league.club("KES"), league.club("ASH")
    assert (kestrel.name, ashvale.name) == ("Kestrel FC", "Ashvale Athletic")
    expected = {
        (kestrel, 6): ("Mensah", Role.DM),
        (kestrel, 10): ("Diallo", Role.AM),
        (kestrel, 9): ("Okafor", Role.ST),
        (ashvale, 4): ("Lund", Role.CM),
    }
    for (club, number), (surname, role) in expected.items():
        player = club.by_number(number)
        assert (player.last_name, player.role) == (surname, role)
        assert player in club.starting_eleven()


def test_traits_stay_within_physical_bounds(league: League) -> None:
    for club in league.clubs:
        for player in club.squad:
            if player.role != Role.GK:
                assert 8.0 <= player.traits.top_speed <= 9.5
            assert 3.0 <= player.traits.acceleration <= 4.0
            assert 0.18 <= player.traits.reaction_time <= 0.32
