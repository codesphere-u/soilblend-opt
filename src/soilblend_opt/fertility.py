"""Kamprath lime neutralization, soil-test nutrient balance & exact LP least-cost NPK blending."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from itertools import combinations


@dataclass(frozen=True)
class FertilizerProduct:
    """Commercial fertilizer grade (N-P2O5-K2O %) and local market price."""

    key: str
    display_name: str
    n_pct: float
    p2o5_pct: float
    k2o_pct: float
    price_usd_per_50kg_bag: float
    application_timing: str  # "basal" or "topdress"

    @property
    def price_usd_per_kg(self) -> float:
        return self.price_usd_per_50kg_bag / 50.0


EAST_AFRICA_FERTILIZERS: tuple[FertilizerProduct, ...] = (
    FertilizerProduct("dap", "DAP (18-46-0)", 18.0, 46.0, 0.0, 46.0, "basal"),
    FertilizerProduct("tsp", "TSP (0-46-0)", 0.0, 46.0, 0.0, 42.0, "basal"),
    FertilizerProduct("urea", "Urea (46-0-0)", 46.0, 0.0, 0.0, 38.0, "topdress"),
    FertilizerProduct("can", "CAN (26-0-0)", 26.0, 0.0, 0.0, 34.0, "topdress"),
    FertilizerProduct("mop", "Muriate of Potash (0-0-60)", 0.0, 0.0, 60.0, 44.0, "basal"),
    FertilizerProduct("npk_17_17_17", "NPK (17-17-17)", 17.0, 17.0, 17.0, 45.0, "basal"),
)


@dataclass(frozen=True)
class CropTarget:
    """Nutrient uptake per tonne of harvestable yield and optimal soil pH floor."""

    key: str
    display_name: str
    n_kg_per_tonne: float
    p2o5_kg_per_tonne: float
    k2o_kg_per_tonne: float
    target_soil_ph: float
    default_yield_t_ha: float


CROP_NUTRIENT_TARGETS: dict[str, CropTarget] = {
    "maize": CropTarget("maize", "Maize (grain)", 22.0, 10.0, 20.0, 6.0, 5.0),
    "beans": CropTarget("beans", "Common Beans", 12.0, 11.0, 22.0, 6.0, 2.0),  # Biological N fixation covers ~60% N
    "irish_potato": CropTarget("irish_potato", "Irish Potato", 5.5, 2.5, 8.5, 5.6, 20.0),
    "rice": CropTarget("rice", "Paddy / Upland Rice", 20.0, 9.0, 24.0, 5.8, 4.5),
    "arabica_coffee": CropTarget("arabica_coffee", "Arabica Coffee (parchment)", 45.0, 12.0, 52.0, 5.6, 1.8),
    "banana_matooke": CropTarget("banana_matooke", "East African Highland Banana", 4.5, 1.5, 14.0, 6.0, 25.0),
}

_TEXTURE_LIME_TONNES_PER_PH_UNIT: dict[str, float] = {
    "sandy": 1.8,
    "loam": 3.0,
    "clay": 4.2,
    "volcanic_ando": 5.0,
}


@dataclass(frozen=True)
class SoilTest:
    """Soil laboratory analysis inputs for a smallholder field."""

    soil_ph: float
    texture: str = "loam"
    available_n_kg_ha: float = 30.0
    olsen_p_mg_kg: float = 8.0
    exchangeable_k_cmol_kg: float = 0.25
    exchangeable_acidity_cmol_kg: float | None = None  # Al3+ + H+ for Kamprath formula


@dataclass(frozen=True)
class LimePrescription:
    """Agricultural lime (CaCO3) neutralization prescription for acidic tropical soils."""

    soil_ph: float
    target_ph: float
    lime_required_t_ha: float
    lime_bags_50kg_per_acre: float
    method_used: str
    phosphorus_fixation_warning: str | None


def compute_lime_requirement(
    soil: SoilTest,
    *,
    target_ph: float = 6.0,
    lime_ecce_pct: float = 80.0,
    kamprath_factor: float = 1.6,
) -> LimePrescription:
    """Calculate agricultural lime (t CaCO3/ha) via Kamprath Al3+ neutralization or pH-texture buffer."""
    if not (3.5 <= soil.soil_ph <= 9.0):
        raise ValueError(f"soil_ph out of agronomic range: {soil.soil_ph}")
    if not (40.0 <= lime_ecce_pct <= 105.0):
        raise ValueError("lime_ecce_pct must be in [40, 105]")

    tex = soil.texture.strip().lower()
    if tex not in _TEXTURE_LIME_TONNES_PER_PH_UNIT:
        raise KeyError(f"Unknown texture '{soil.texture}'. Options: {sorted(_TEXTURE_LIME_TONNES_PER_PH_UNIT)}")

    if soil.soil_ph >= target_ph:
        lime_t_ha = 0.0
        method = "no_liming_needed"
    elif soil.exchangeable_acidity_cmol_kg is not None and soil.exchangeable_acidity_cmol_kg > 0.0:
        lime_t_ha = kamprath_factor * soil.exchangeable_acidity_cmol_kg * (100.0 / lime_ecce_pct)
        method = "kamprath_exchangeable_acidity"
    else:
        ph_gap = target_ph - soil.soil_ph
        lime_t_ha = ph_gap * _TEXTURE_LIME_TONNES_PER_PH_UNIT[tex] * (100.0 / lime_ecce_pct)
        method = "texture_ph_buffer_curve"

    # Cap single-season lime incorporation at 6.0 t/ha to avoid micronutrient (Zn/Fe) lockup
    lime_t_ha = min(6.0, max(0.0, lime_t_ha))
    bags_per_acre = (lime_t_ha * 0.404686 * 1000.0) / 50.0

    warn: str | None = None
    if soil.soil_ph < 5.3:
        warn = (
            f"SEVERE SOIL ACIDITY (pH {soil.soil_ph:.1f} < 5.3): Al3+ toxicity will fix applied phosphorus; "
            f"incorporate {lime_t_ha:.2f} t/ha agricultural lime 2-4 weeks before applying NPK/DAP."
        )

    return LimePrescription(
        soil_ph=round(soil.soil_ph, 2),
        target_ph=round(target_ph, 2),
        lime_required_t_ha=round(lime_t_ha, 2),
        lime_bags_50kg_per_acre=round(bags_per_acre, 1),
        method_used=method,
        phosphorus_fixation_warning=warn,
    )


def _solve_linear(a: list[list[float]], b: list[float]) -> list[float] | None:
    """Exact Gaussian elimination with partial pivoting for small 1x1..3x3 basis systems."""
    n = len(b)
    mat = [[*row, b[i]] for i, row in enumerate(a)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(mat[r][col]))
        if abs(mat[pivot][col]) < 1e-10:
            return None
        mat[col], mat[pivot] = mat[pivot], mat[col]
        div = mat[col][col]
        for j in range(col, n + 1):
            mat[col][j] /= div
        for r in range(n):
            if r != col:
                factor = mat[r][col]
                for j in range(col, n + 1):
                    mat[r][j] -= factor * mat[col][j]
    return [mat[i][n] for i in range(n)]


def _solve_least_cost_npk_lp(
    req_n: float,
    req_p: float,
    req_k: float,
    products: Sequence[FertilizerProduct],
) -> dict[str, float]:
    """Solve min sum(c_j * x_j) s.t. A x >= [req_n, req_p, req_k], x >= 0 via exact vertex enumeration."""
    targets = [max(0.0, req_n), max(0.0, req_p), max(0.0, req_k)]
    active_rows = [r for r, val in enumerate(targets) if val > 1e-6]
    if not active_rows:
        return {}

    cols = [[p.n_pct / 100.0, p.p2o5_pct / 100.0, p.k2o_pct / 100.0] for p in products]
    costs = [p.price_usd_per_kg for p in products]
    m = len(products)

    best_cost = float("inf")
    best_x: dict[str, float] = {}

    # Fundamental Theorem of LP: optimum of min c^T x s.t. Ax >= b, x >= 0 lies at a vertex
    # defined by k active nutrient constraints (k in 1..len(active_rows)) and k basic variables.
    for k in range(1, len(active_rows) + 1):
        for row_subset in combinations(active_rows, k):
            rhs = [targets[r] for r in row_subset]
            for prod_subset in combinations(range(m), k):
                sub_a = [[cols[j][r] for j in prod_subset] for r in row_subset]
                sol = _solve_linear(sub_a, rhs)
                if sol is None or any(v < -1e-7 for v in sol):
                    continue
                vals = [max(0.0, v) for v in sol]
                # Verify all 3 nutrient targets satisfied
                sup = [0.0, 0.0, 0.0]
                for idx_local, j in enumerate(prod_subset):
                    for r in range(3):
                        sup[r] += cols[j][r] * vals[idx_local]
                if any(sup[r] < targets[r] - 1e-5 for r in range(3)):
                    continue
                cost = sum(costs[j] * vals[idx_local] for idx_local, j in enumerate(prod_subset))
                if cost < best_cost:
                    best_cost = cost
                    best_x = {
                        products[j].key: vals[idx_local]
                        for idx_local, j in enumerate(prod_subset)
                        if vals[idx_local] > 0.05
                    }

    return best_x


@dataclass(frozen=True)
class FertilizerRecommendation:
    """Integrated liming, N-P-K gap, least-cost fertilizer blend, and split-timing schedule."""

    crop: str
    target_yield_t_ha: float
    lime: LimePrescription
    required_n_kg_ha: float
    required_p2o5_kg_ha: float
    required_k2o_kg_ha: float
    blend_kg_per_ha: dict[str, float]
    blend_50kg_bags_per_acre: dict[str, float]
    supplied_n_kg_ha: float
    supplied_p2o5_kg_ha: float
    supplied_k2o_kg_ha: float
    total_fertilizer_cost_usd_ha: float
    basal_application_kg_ha: dict[str, float]
    topdress_application_kg_ha: dict[str, float]


def optimize_fertilizer_blend(
    soil: SoilTest,
    crop_key: str,
    *,
    target_yield_t_ha: float | None = None,
    products: Sequence[FertilizerProduct] = EAST_AFRICA_FERTILIZERS,
) -> FertilizerRecommendation:
    """Compute lime requirement, soil-adjusted N-P-K gap, and exact least-cost fertilizer blend."""
    c_key = crop_key.strip().lower().replace("-", "_").replace(" ", "_")
    if c_key not in CROP_NUTRIENT_TARGETS:
        raise KeyError(f"Unknown crop '{crop_key}'. Available: {', '.join(sorted(CROP_NUTRIENT_TARGETS))}")
    crop = CROP_NUTRIENT_TARGETS[c_key]
    y_target = target_yield_t_ha if target_yield_t_ha is not None else crop.default_yield_t_ha
    if y_target <= 0.0:
        raise ValueError("target_yield_t_ha must be positive")

    lime = compute_lime_requirement(soil, target_ph=crop.target_soil_ph)

    # Soil lab nutrient supply estimates (0-20 cm plow layer):
    # Olsen P (mg/kg) * 2.0 (kg/ha) * 2.29 (P -> P2O5)
    soil_p2o5_kg_ha = soil.olsen_p_mg_kg * 2.0 * 2.29
    # Exchangeable K (cmol/kg) * 391 (mg/kg) * 2.0 * 1.205 (K -> K2O) * 0.25 availability
    soil_k2o_kg_ha = soil.exchangeable_k_cmol_kg * 391.0 * 2.0 * 1.205 * 0.25

    n_uptake = y_target * crop.n_kg_per_tonne
    p_uptake = y_target * crop.p2o5_kg_per_tonne
    k_uptake = y_target * crop.k2o_kg_per_tonne

    # Recovery efficiencies (P recovery drops severely in unlimed acidic soils)
    p_recovery = 0.40 if (soil.soil_ph >= 5.5 or lime.lime_required_t_ha > 0.0) else 0.25
    req_n = max(0.0, (n_uptake - soil.available_n_kg_ha) / 0.55)
    req_p = max(0.0, (p_uptake - soil_p2o5_kg_ha * 0.35) / p_recovery)
    req_k = max(0.0, (k_uptake - soil_k2o_kg_ha) / 0.60)

    blend_raw = _solve_least_cost_npk_lp(req_n, req_p, req_k, products)
    prod_map = {p.key: p for p in products}

    blend_kg = {k: round(v, 1) for k, v in sorted(blend_raw.items())}
    bags_acre = {k: round((v * 0.404686) / 50.0, 2) for k, v in blend_kg.items()}

    sup_n = sum(v * prod_map[k].n_pct / 100.0 for k, v in blend_raw.items())
    sup_p = sum(v * prod_map[k].p2o5_pct / 100.0 for k, v in blend_raw.items())
    sup_k = sum(v * prod_map[k].k2o_pct / 100.0 for k, v in blend_raw.items())
    tot_cost = sum(v * prod_map[k].price_usd_per_kg for k, v in blend_raw.items())

    basal = {k: v for k, v in blend_kg.items() if prod_map[k].application_timing == "basal"}
    topdress = {k: v for k, v in blend_kg.items() if prod_map[k].application_timing == "topdress"}

    return FertilizerRecommendation(
        crop=crop.key,
        target_yield_t_ha=round(y_target, 2),
        lime=lime,
        required_n_kg_ha=round(req_n, 1),
        required_p2o5_kg_ha=round(req_p, 1),
        required_k2o_kg_ha=round(req_k, 1),
        blend_kg_per_ha=blend_kg,
        blend_50kg_bags_per_acre=bags_acre,
        supplied_n_kg_ha=round(sup_n, 1),
        supplied_p2o5_kg_ha=round(sup_p, 1),
        supplied_k2o_kg_ha=round(sup_k, 1),
        total_fertilizer_cost_usd_ha=round(tot_cost, 2),
        basal_application_kg_ha=basal,
        topdress_application_kg_ha=topdress,
    )
