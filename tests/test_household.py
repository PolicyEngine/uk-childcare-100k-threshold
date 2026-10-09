"""The cliff example runs through policyengine.py and reproduces the published family."""

import pytest

from childcare_100k.household import _run

# Net income after the family's own childcare spending, 2027-28 (see docs/METHOD.md, "Cliff example").
# Exactly £100,000 still qualifies (SI 2022/1134 reg 14(3)(c)(i): excluded only above £100,000).
EXPECTED = {
    (99_000, False): 101_619,
    (100_000, False): 102_199,
    (100_001, False): 84_331,
    (100_001, True): 102_200,
}


@pytest.mark.parametrize(("earnings", "reform"), list(EXPECTED))
def test_cliff_points(earnings, reform):
    r = _run(earnings, 2027, reform)
    assert round(r["net_income"] - r["childcare_spend"]) == EXPECTED[(earnings, reform)]


def test_cliff_uses_policyengine_py_not_policyengine_uk():
    import inspect

    from childcare_100k import household

    source = inspect.getsource(household)
    assert "policyengine.tax_benefit_models.uk import calculate_household" in source
    assert "from policyengine_uk" not in source
