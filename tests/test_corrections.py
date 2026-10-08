"""The model corrections (corrections.py): the 2029 salary-sacrifice fix, the three 30-hours entitlement fixes and Tax-Free Childcare reg 13."""

import pytest

from childcare_100k import corrections


def _situation(year):
    """One parent on £97,000 after £10,000 of pension salary sacrifice, with a two-year-old."""
    return {
        "people": {
            "parent": {
                "age": {year: 35},
                "employment_income_before_lsr": {year: 97_000},
                "pension_contributions_via_salary_sacrifice": {year: 10_000},
            },
            "child": {"age": {year: 2}},
        },
        "benunits": {"bu": {"members": ["parent", "child"]}},
        "households": {
            "hh": {"members": ["parent", "child"], "region": {year: "SOUTH_EAST"}}
        },
    }


def _sim(year, corrected):
    from policyengine_uk import Simulation
    from policyengine_uk.utils.scenario import Scenario

    kwargs = (
        {
            "scenario": Scenario(
                simulation_modifier=corrections.apply_corrections,
                applied_before_data_load=True,
            )
        }
        if corrected
        else {}
    )
    return Simulation(situation=_situation(year), **kwargs)


def _value(sim, variable, year):
    return sim.calculate(variable, year)[0]


def test_income_tests_ignore_salary_sacrifice_returned_to_pay_in_2029():
    uncorrected, corrected = _sim(2029, False), _sim(2029, True)
    assert _value(
        corrected, "salary_sacrifice_returned_to_income", 2029
    ) == pytest.approx(8_000)
    # The model's own adjusted net income crosses £100,000 and fails both tests...
    assert _value(uncorrected, "adjusted_net_income", 2029) > 100_000
    assert not _value(uncorrected, corrections.THIRTY_HOURS_INCOME_TEST, 2029)
    assert not _value(uncorrected, corrections.TFC_INCOME_TEST, 2029)
    # ...the corrected tests pass, and nothing else moves.
    assert _value(corrected, corrections.THIRTY_HOURS_INCOME_TEST, 2029)
    assert _value(corrected, corrections.TFC_INCOME_TEST, 2029)
    for variable in ("adjusted_net_income", "income_tax", "ni_employee"):
        assert _value(corrected, variable, 2029) == pytest.approx(
            _value(uncorrected, variable, 2029)
        )


def test_correction_is_a_no_op_before_the_cap():
    uncorrected, corrected = _sim(2028, False), _sim(2028, True)
    for variable in (
        corrections.THIRTY_HOURS_INCOME_TEST,
        corrections.TFC_INCOME_TEST,
        "income_tax",
    ):
        assert _value(corrected, variable, 2028) == _value(uncorrected, variable, 2028)


def test_correction_refuses_a_changed_model_formula(monkeypatch):
    monkeypatch.setitem(
        corrections.EXPECTED_FORMULA_SHA256, corrections.TFC_INCOME_TEST, "0" * 64
    )
    from policyengine_uk import CountryTaxBenefitSystem

    with pytest.raises(RuntimeError, match="changed upstream"):
        corrections.apply_to_system(CountryTaxBenefitSystem())


# ── Entitlement corrections (C1-C3 of the program review of #4) ─────────────────

Y = 2027


def _family(a_income, b_income, child_age, usage=30, b_extra=None, reform=False, corrected=True):
    from policyengine_uk import Simulation
    from policyengine_uk.utils.scenario import Scenario

    from childcare_100k import config

    people = {
        "a": {"age": {Y: 35}, "employment_income": {Y: a_income}, "is_parent": {Y: True}},
        "b": {"age": {Y: 34}, "employment_income": {Y: b_income}, "is_parent": {Y: True}, **(b_extra or {})},
        "c": {"age": {Y: child_age}},
    }
    situation = {
        "people": people,
        "benunits": {"bu": {"members": list(people), "maximum_extended_childcare_hours_usage": {Y: usage}}},
        "households": {"hh": {"members": list(people), "region": {Y: "SOUTH_EAST"}}},
    }
    scenario = Scenario(
        parameter_changes=config.parameter_changes(config.REFORM_PARAMETERS) if reform else None,
        simulation_modifier=corrections.apply_corrections if corrected else None,
        applied_before_data_load=True,
    )
    return Simulation(situation=situation, scenario=scenario)


def _funded(sim):
    return {
        v: float(sim.calculate(f"{v}_childcare_entitlement", Y).sum())
        for v in ("extended", "universal", "targeted")
    }


def test_exactly_100000_qualifies_for_the_30_hours():
    """C3: reg 14(3)(c)(i) excludes only income that exceeds £100,000."""
    assert _funded(_family(100_000, 40_000, 2))["extended"] > 0
    assert _funded(_family(100_000, 40_000, 2, corrected=False))["extended"] == 0
    assert _funded(_family(100_001, 40_000, 2))["extended"] == 0


def test_partner_on_a_specified_benefit_does_not_need_the_minimum_earnings():
    """C1: reg 14(4)/15(4); a partner on contributory ESA earning £5,000 alongside a £120,000 earner."""
    esa = {"esa_contrib_reported": {Y: 5_000}}
    assert _funded(_family(120_000, 5_000, 2, b_extra=esa))["extended"] == 0  # over the limit today
    assert _funded(_family(120_000, 5_000, 2, b_extra=esa, reform=True))["extended"] > 0
    assert _funded(_family(120_000, 5_000, 2, b_extra=esa, reform=True, corrected=False))["extended"] == 0
    # Without the benefit the low earner still fails the minimum earnings test.
    assert _funded(_family(120_000, 5_000, 2, reform=True))["extended"] == 0


def test_universal_hours_are_kept_when_the_family_becomes_eligible():
    """C2: a three-year-old whose drawn extended use is 5 hours keeps the universal 15."""
    base, reform = _family(120_000, 40_000, 3, usage=5), _family(120_000, 40_000, 3, usage=5, reform=True)
    assert sum(_funded(reform).values()) == pytest.approx(sum(_funded(base).values()))
    assert _funded(reform)["universal"] == pytest.approx(_funded(base)["universal"])
    raw = _family(120_000, 40_000, 3, usage=5, reform=True, corrected=False)
    assert sum(_funded(raw).values()) < sum(_funded(base).values())  # the model's own loss


def test_extended_hours_above_the_universal_are_added_once():
    """C2: with 30 hours used, a three-year-old gets 30 hours in total, not 45."""
    reform = _funded(_family(120_000, 40_000, 3, usage=30, reform=True))
    raw = _funded(_family(120_000, 40_000, 3, usage=30, reform=True, corrected=False))
    assert reform["universal"] > 0
    assert sum(reform.values()) == pytest.approx(sum(raw.values()))


# ── Tax-Free Childcare: reg 13 (C1 of the rereview of #6) ────────────────────────


def _tfc_family(b_extra, a_income=120_000, b_income=0, reform=True, corrected=True, couple=True):
    """A 2027 England family: a £120,000 earner, a partner with ``b_extra``, a three-year-old in £10,000 of paid care."""
    from policyengine_uk import Simulation
    from policyengine_uk.utils.scenario import Scenario

    from childcare_100k import config

    people = {"a": {"age": {Y: 35}, "employment_income": {Y: a_income}, "is_parent": {Y: True}}}
    if couple:
        people["b"] = {"age": {Y: 34}, "employment_income": {Y: b_income}, "is_parent": {Y: True}, **b_extra}
    people["c"] = {"age": {Y: 3}, "childcare_expenses": {Y: 10_000}}
    situation = {
        "people": people,
        "benunits": {"bu": {"members": list(people), "would_claim_tfc": {Y: True},
                            "would_claim_extended_childcare": {Y: True},
                            "maximum_extended_childcare_hours_usage": {Y: 30}}},
        "households": {"hh": {"members": list(people), "region": {Y: "SOUTH_EAST"}}},
    }
    scenario = Scenario(
        parameter_changes=config.parameter_changes(config.REFORM_PARAMETERS) if reform else None,
        simulation_modifier=corrections.apply_corrections if corrected else None,
        applied_before_data_load=True,
    )
    return Simulation(situation=situation, scenario=scenario)


def _tfc(sim):
    return float(sim.calculate("tax_free_childcare", Y).sum())


ESA = {"esa_contrib_reported": {Y: 5_000}}
CARERS_ALLOWANCE = {"carers_allowance": {Y: 4_000}}


@pytest.mark.parametrize("benefit", [ESA, CARERS_ALLOWANCE], ids=["contributory ESA", "carer's allowance"])
def test_partner_on_a_caring_or_incapacity_benefit_is_regarded_as_in_paid_work(benefit):
    """SI 2015/448 reg 13(1)-(2): the reform pays the £2,000 cap on £10,000 of care; the uncorrected model pays nothing."""
    assert _tfc(_tfc_family(benefit, reform=False)) == 0  # over £100,000 today
    assert _tfc(_tfc_family(benefit)) == pytest.approx(2_000)
    assert _tfc(_tfc_family(benefit, corrected=False)) == 0
    # Below the limit the same family qualifies today, too.
    assert _tfc(_tfc_family(benefit, a_income=40_000, reform=False)) == pytest.approx(2_000)


def test_disability_benefits_are_not_a_reg_13_benefit():
    """DLA is not on the reg 13(1)(b) list (the old Pension Credit route is gone, as upstream)."""
    assert _tfc(_tfc_family({"dla": {Y: 4_000}}, a_income=40_000, reform=False)) == 0


def test_reg_13_needs_a_partner_in_qualifying_paid_work():
    """A lone parent on Carer's Allowance; and a couple whose worker is also paid a reg 13(1)(b) benefit (reg 13(3))."""
    lone = _tfc_family({}, a_income=0, reform=False, couple=False)
    lone.set_input("carers_allowance", Y, [4_000, 0])
    assert not lone.calculate("tax_free_childcare_work_condition", Y).any() and _tfc(lone) == 0
    assert _tfc(_tfc_family(ESA, a_income=40_000, reform=False)) == pytest.approx(2_000)
    worker_on_esa = _tfc_family(ESA, a_income=40_000, reform=False)
    worker_on_esa.set_input("esa_contrib", Y, [5_000, 5_000, 0])
    assert _tfc(worker_on_esa) == 0


def test_the_limit_still_applies_to_a_partner_regarded_as_in_paid_work():
    """Reg 13 deems work and the minimum income only; reg 15's £100,000 limit is the reform's to remove."""
    rich_carer = {"carers_allowance": {Y: 4_000}, "savings_interest_income": {Y: 110_000}}
    assert _tfc(_tfc_family(rich_carer, a_income=40_000, reform=False)) == 0
    assert _tfc(_tfc_family(rich_carer, a_income=40_000)) == pytest.approx(2_000)


# ── Claimant and partner, not the is_parent flags (C2 of the rereview of #6) ─────

UNFLAGGED = {"is_parent": {Y: False}}


def test_an_unflagged_nonworking_partner_fails_the_work_condition():
    """C2: a couple whose nonworking partner is not flagged is_parent gets no Tax-Free Childcare (2014 Act s.3(1), reg 9).

    The model's ``is_parent`` gates (and the earlier stand-in) skipped the partner and paid the £2,000 cap.
    """
    assert _tfc(_tfc_family(UNFLAGGED, corrected=False)) == pytest.approx(2_000)  # the model's error
    sim = _tfc_family(UNFLAGGED)
    assert sim.calculate("is_couple", Y).all()
    assert _tfc(sim) == 0
    assert not sim.calculate("tax_free_childcare_eligible", Y).any()
    # The same couple with the partner flagged, as before.
    assert _tfc(_tfc_family({})) == 0
    # The partner earning the minimum: the couple qualifies, flagged or not.
    assert _tfc(_tfc_family(UNFLAGGED, b_income=20_000)) == pytest.approx(2_000)


def test_an_unflagged_partner_faces_the_income_limit():
    """The income test reaches the unflagged partner too: over £100,000 today, both qualify only under the reform."""
    rich = {**UNFLAGGED, "savings_interest_income": {Y: 110_000}}
    assert _tfc(_tfc_family(rich, a_income=40_000, b_income=20_000, reform=False)) == 0
    assert _tfc(_tfc_family(rich, a_income=40_000, b_income=20_000)) == pytest.approx(2_000)


@pytest.mark.parametrize("benefit", [ESA, CARERS_ALLOWANCE], ids=["contributory ESA", "carer's allowance"])
def test_an_unflagged_partner_on_a_reg_13_benefit_is_regarded_as_in_paid_work(benefit):
    assert _tfc(_tfc_family({**UNFLAGGED, **benefit})) == pytest.approx(2_000)


def test_the_30_hours_test_the_claimant_and_partner():
    """Reg 14: the unflagged nonworking partner fails the 30 hours, and an unflagged working partner of a flagged
    parent on Carer's Allowance (reg 14(4)) passes it; the model's is_parent work condition refused that couple."""
    assert _funded(_tfc_family(UNFLAGGED))["extended"] == 0  # the universal 15 hours only
    sim = _tfc_family(UNFLAGGED, a_income=0, b_income=40_000, reform=False)
    sim.set_input("carers_allowance", Y, [4_000, 0, 0])
    assert sim.calculate("extended_childcare_entitlement_eligible", Y).all()
    assert _tfc(sim) == pytest.approx(2_000)


def test_a_lone_parent_with_a_grown_up_child_is_still_single():
    """A dependent 18-year-old (or one 16 or more years younger) is neither claimant nor partner, as upstream."""
    from policyengine_uk import Simulation
    from policyengine_uk.utils.scenario import Scenario

    people = {
        "a": {"age": {Y: 40}, "employment_income": {Y: 40_000}, "is_parent": {Y: True}},
        "b": {"age": {Y: 19}},
        "c": {"age": {Y: 3}, "childcare_expenses": {Y: 10_000}},
    }
    situation = {
        "people": people,
        "benunits": {"bu": {"members": list(people), "would_claim_tfc": {Y: True},
                            "would_claim_extended_childcare": {Y: True},
                            "maximum_extended_childcare_hours_usage": {Y: 30}}},
        "households": {"hh": {"members": list(people), "region": {Y: "SOUTH_EAST"}}},
    }
    scenario = Scenario(simulation_modifier=corrections.apply_corrections, applied_before_data_load=True)
    sim = Simulation(situation=situation, scenario=scenario)
    assert corrections.claimant_or_partner(sim.populations["person"], Y).tolist() == [True, False, False]
    assert _tfc(sim) == pytest.approx(2_000)
    assert sim.calculate("extended_childcare_entitlement_eligible", Y).all()
