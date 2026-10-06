"""Unit tests for the aggregation: microdf weighting, disclosure control and the sensitivities.

These run on small synthetic runs, so they need no population data.
"""

import numpy as np
import pytest

from childcare_100k import aggregate as A


class FakeRun:
    """A run's arrays for one year, keyed like ``engine.extract``'s output."""

    def __init__(self, year, **arrays):
        self.year = year
        self.arrays = arrays

    def __call__(self, year, name):
        assert year == self.year
        return self.arrays[name]


def _pair(year=2026, n=4, d_free=None, d_tfc=None, over_law=None, newly=None, n_age0=None, **extra):
    """A baseline and reform run over ``n`` one-family households (household = family = one adult)."""
    w = np.arange(1.0, n + 1)
    zero = np.zeros(n)
    d_free = zero if d_free is None else np.asarray(d_free, float)
    d_tfc = zero if d_tfc is None else np.asarray(d_tfc, float)
    over_law = np.ones(n, bool) if over_law is None else np.asarray(over_law, bool)
    newly = np.zeros(n, bool) if newly is None else np.asarray(newly, bool)
    n_age0 = zero if n_age0 is None else np.asarray(n_age0, float)
    common = dict(
        hh_weight=w, bu_weight=w, p_weight=w,
        hh_gov_balance=zero, hh_net_income=np.full(n, 50_000.0), hh_decile=np.arange(1, n + 1),
        hh_country=np.array(["ENGLAND"] * n), bu_country=np.zeros(n, int),
        bu_any_over_law=over_law, bu_n_age0=n_age0, rate_by_age=np.array([11.0, 11.0, 8.0, 6.0, 6.0]),
        p_age=np.full(n, 3.0), p_is_child=np.ones(n, bool),
        **extra,
    )
    base = FakeRun(year, **common, hh_free=zero, hh_tfc=zero, bu_free=zero, bu_tfc=zero,
                   p_bu_free=zero, p_bu_tfc=zero, p_extended=np.zeros(n, bool), p_tfc=np.zeros(n, bool),
                   p_free_value=zero, p_tfc_value=zero,
                   bu_ext_eligible=np.zeros(n, bool))
    ref = FakeRun(year, **{**common, "hh_gov_balance": -(d_free + d_tfc),
                           "hh_net_income": 50_000.0 + d_free + d_tfc},
                  hh_free=d_free, hh_tfc=d_tfc, bu_free=d_free, bu_tfc=d_tfc,
                  p_bu_free=d_free, p_bu_tfc=d_tfc, p_extended=d_free > 0, p_tfc=d_tfc > 0,
                  p_free_value=d_free, p_tfc_value=d_tfc,
                  bu_ext_eligible=newly)
    return base, ref


def test_gross_is_the_weighted_change():
    base, ref = _pair(d_free=[100, 0, 0, 0], d_tfc=[0, 0, 50, 0])
    free, tfc, net = A.gross(base, ref, 2026)
    assert free == pytest.approx(1 * 100)
    assert tfc == pytest.approx(3 * 50)
    assert net == pytest.approx(100 + 150)


def test_differing_weights_between_runs_raise():
    base, ref = _pair()
    ref.arrays["hh_weight"] = ref.arrays["hh_weight"] * 2
    with pytest.raises(ValueError):
        A.gross(base, ref, 2026)


def test_mean_gain_is_null_when_nobody_gains():
    base, ref = _pair()
    out = A.recipients({"baseline": base, "reform": ref}, years=[2026])["2026"]
    assert out["mean_gain_gbp"] is None and out["mean_gain_suppressed"] is True
    assert out["families_gaining"] == 0


def test_mean_gain_is_the_weighted_mean_over_gainers():
    base, ref = _pair(d_free=[0, 100, 400, 0])
    out = A.recipients({"baseline": base, "reform": ref}, years=[2026])["2026"]
    assert out["mean_gain_gbp"] == round((2 * 100 + 3 * 400) / (2 + 3))
    assert out["mean_gain_suppressed"] is False


def test_cell_with_no_gainers_but_one_loser_is_suppressed():
    assert A._cell_ok(0, 0)
    assert A._cell_ok(12, 15)
    assert not A._cell_ok(0, 1)
    assert not A._cell_ok(3, 12)


def test_lone_suppressed_cell_with_no_complement_suppresses_the_breakdown():
    cells = [
        {"country": "England", "total_change_bn": 0.5, "families_gaining": 150_000, "suppressed": False},
        {"country": "Wales", "total_change_bn": None, "families_gaining": None, "suppressed": True},
        {"country": "Scotland", "total_change_bn": 0.0, "families_gaining": 0, "suppressed": False},
    ]
    # England would be the only candidate, but it has changed records; drop it to leave none.
    out = A._complement([dict(c) for c in cells], [0, 5, 0])
    assert all(c["suppressed"] for c in out)
    assert all(c["total_change_bn"] is None and c["families_gaining"] is None for c in out)
    assert [c["country"] for c in out] == ["England", "Wales", "Scotland"]


def test_lone_suppressed_cell_gets_the_smallest_changed_complement():
    cells = [
        {"country": "England", "total_change_bn": 0.5, "families_gaining": 150_000, "suppressed": False},
        {"country": "Scotland", "total_change_bn": 0.02, "families_gaining": 9_000, "suppressed": False},
        {"country": "Wales", "total_change_bn": None, "families_gaining": None, "suppressed": True},
        {"country": "Northern Ireland", "total_change_bn": 0.0, "families_gaining": 0, "suppressed": False},
    ]
    out = A._complement(cells, [900, 40, 5, 0])
    assert [c["suppressed"] for c in out] == [False, True, True, False]


def _sensitivity_runs(base, ref, d_routed_extra):
    """Hours30 runs identical to central; routed runs change TFC gains by ``d_routed_extra``."""
    rb = FakeRun(2026, **base.arrays)
    rr = FakeRun(2026, **{**ref.arrays, "bu_tfc": ref.arrays["bu_tfc"] + np.asarray(d_routed_extra, float)})
    return {"baseline": base, "reform": ref, "baseline_hours30": base, "reform_hours30": ref,
            "baseline_routed": rb, "reform_routed": rr}


def test_joint_low_end_does_not_double_count():
    # Family 0 already qualifies in law (not over £100k net of pension contributions): its whole
    # gain is removed, so its routed-share change must not be removed a second time.
    base, ref = _pair(d_tfc=[1000, 1000, 0, 0], over_law=[False, True, True, True])
    runs = _sensitivity_runs(base, ref, [-400, -400, 0, 0])
    out = A.sensitivities(runs, years=[2026])
    joint = out["effects_bn"][A.JOINT_LOW]["2026"]
    # Pension removes family 0's gain (w=1 x 1000); routed counts family 1 only (w=2 x -400).
    assert joint == round((-1 * 1000 + 2 * -400) / 1e9, 3)
    rng = out["range_bn"]
    assert rng["low"]["2026"] == round(rng["central"]["2026"] + joint, 3)


def test_under_ones_use_the_term_delayed_share_of_the_year():
    base, ref = _pair(newly=[True, False, False, False], n_age0=[1, 1, 0, 0])
    runs = _sensitivity_runs(base, ref, [0, 0, 0, 0])
    out = A.sensitivities(runs, years=[2026])
    expected = 1 * 1 * (1.125 / 12) * 30 * 38 * 11.0
    assert out["effects_bn"]["under_ones"]["2026"] == round(expected / 1e9, 3)
    assert A.UNDER_ONE_SHARE_OF_YEAR == pytest.approx(0.09375)


def test_routed_runs_with_different_weights_raise():
    base, ref = _pair(d_tfc=[1000, 0, 0, 0])
    runs = _sensitivity_runs(base, ref, [0, 0, 0, 0])
    runs["reform_routed"].arrays["bu_weight"] = runs["reform_routed"].arrays["bu_weight"] * 2
    with pytest.raises(ValueError):
        A.sensitivities(runs, years=[2026])


def test_a_child_counts_as_gaining_only_from_their_own_entitlement():
    """One family, two children: the three-year-old moves from universal to extended hours
    with the same value; only the two-year-old's hours rise. Only the two-year-old gains."""
    year = 2026
    fam = dict(  # noqa: C408 - keyword arrays read like engine.extract's output
        hh_weight=np.full(1, 1_000.0), bu_weight=np.full(1, 1_000.0), p_weight=np.full(2, 1_000.0),
        hh_gov_balance=np.zeros(1), hh_net_income=np.full(1, 50_000.0), hh_decile=np.array([10]),
        hh_country=np.array(["ENGLAND"]), bu_country=np.zeros(1, int),
        bu_any_over_law=np.ones(1, bool), bu_n_age0=np.zeros(1),
        rate_by_age=np.array([11.0, 11.0, 8.0, 6.0, 6.0]),
        p_age=np.array([3.0, 2.0]), p_is_child=np.ones(2, bool),
        bu_ext_eligible=np.zeros(1, bool),
    )
    zero2 = np.zeros(2)
    base = FakeRun(year, **fam, hh_free=np.array([3_000.0]), hh_tfc=np.zeros(1), bu_free=np.array([3_000.0]),
                   bu_tfc=np.zeros(1), p_bu_free=np.full(2, 3_000.0), p_bu_tfc=zero2,
                   p_extended=np.array([False, False]), p_tfc=np.array([False, False]),
                   p_free_value=np.array([3_000.0, 0.0]), p_tfc_value=zero2)
    ref = FakeRun(year, **{**fam, "hh_gov_balance": np.array([-2_000.0]), "hh_net_income": np.full(1, 52_000.0),
                           "bu_ext_eligible": np.ones(1, bool)},
                  hh_free=np.array([5_000.0]), hh_tfc=np.zeros(1), bu_free=np.array([5_000.0]), bu_tfc=np.zeros(1),
                  p_bu_free=np.full(2, 5_000.0), p_bu_tfc=zero2,
                  p_extended=np.array([True, True]), p_tfc=np.array([False, False]),
                  p_free_value=np.array([3_000.0, 2_000.0]), p_tfc_value=zero2)
    out = A.recipients({"baseline": base, "reform": ref}, years=[year])[str(year)]
    assert out["families_gaining"] == 1_000
    assert out["children_gaining"] == 1_000  # the two-year-old only; projecting the family change gave 2,000
    assert out["children_by_scheme"]["thirty_hours"] == 1_000
    assert out["children_gaining_by_age"]["2"] == 1_000
    assert out["children_gaining_by_age"]["3-4"] == 0
