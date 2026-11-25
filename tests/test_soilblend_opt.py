"""Tests for soilblend-opt."""

from __future__ import annotations

import json

import pytest

from soilblend_opt import SoilTest, compute_lime_requirement, optimize_fertilizer_blend
from soilblend_opt.cli import main as cli_main


def test_kamprath_lime_requirement_and_acidity_warning() -> None:
    acidic = SoilTest(soil_ph=4.8, texture="clay", exchangeable_acidity_cmol_kg=1.5)
    lime = compute_lime_requirement(acidic, target_ph=6.0, lime_ecce_pct=80.0, kamprath_factor=1.6)
    # 1.6 * 1.5 * (100/80) = 3.0 t/ha CaCO3
    assert lime.lime_required_t_ha == pytest.approx(3.0)
    assert lime.method_used == "kamprath_exchangeable_acidity"
    assert lime.phosphorus_fixation_warning is not None

    neutral = SoilTest(soil_ph=6.4, texture="loam")
    no_lime = compute_lime_requirement(neutral, target_ph=6.0)
    assert no_lime.lime_required_t_ha == 0.0
    assert no_lime.phosphorus_fixation_warning is None


def test_lp_blend_meets_all_npk_requirements_at_minimum_cost() -> None:
    soil = SoilTest(soil_ph=5.2, texture="loam", available_n_kg_ha=25.0, olsen_p_mg_kg=6.0, exchangeable_k_cmol_kg=0.12)
    rec = optimize_fertilizer_blend(soil, "maize", target_yield_t_ha=6.0)
    assert rec.supplied_n_kg_ha >= rec.required_n_kg_ha - 0.5
    assert rec.supplied_p2o5_kg_ha >= rec.required_p2o5_kg_ha - 0.5
    assert rec.supplied_k2o_kg_ha >= rec.required_k2o_kg_ha - 0.5
    assert rec.total_fertilizer_cost_usd_ha > 0.0
    # Urea is cheaper per kg N than CAN; LP selects DAP + Urea + MOP!
    assert "urea" in rec.blend_kg_per_ha
    assert "basal" not in rec.blend_kg_per_ha
    assert len(rec.topdress_application_kg_ha) >= 1


def test_cli_runs(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli_main(["--crop", "irish_potato", "--ph", "5.0", "--yield-t-ha", "22"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["lime"]["lime_required_t_ha"] > 0.0
    assert out["total_fertilizer_cost_usd_ha"] > 0.0
