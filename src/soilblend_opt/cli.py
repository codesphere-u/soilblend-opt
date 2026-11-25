"""CLI entrypoint for soilblend-opt."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from .fertility import SoilTest, optimize_fertilizer_blend


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="soilblend-opt",
        description="Compute acidic soil lime requirement and exact least-cost NPK fertilizer blend.",
    )
    parser.add_argument(
        "--crop",
        default="maize",
        help="Crop key (maize, beans, irish_potato, rice, arabica_coffee, banana_matooke).",
    )
    parser.add_argument("--yield-t-ha", type=float, default=None, help="Target yield in tonnes/ha.")
    parser.add_argument("--ph", type=float, default=5.1, help="Soil pH.")
    parser.add_argument("--texture", default="loam", help="Soil texture (sandy, loam, clay, volcanic_ando).")
    parser.add_argument("--avail-n", type=float, default=30.0, help="Available soil N (kg/ha).")
    parser.add_argument("--olsen-p", type=float, default=8.0, help="Olsen P (mg/kg).")
    parser.add_argument("--exch-k", type=float, default=0.25, help="Exchangeable K (cmol/kg).")
    parser.add_argument("--exch-acidity", type=float, default=None, help="Exchangeable acidity Al3+ (cmol/kg).")
    args = parser.parse_args(argv)

    rec = optimize_fertilizer_blend(
        SoilTest(
            soil_ph=args.ph,
            texture=args.texture,
            available_n_kg_ha=args.avail_n,
            olsen_p_mg_kg=args.olsen_p,
            exchangeable_k_cmol_kg=args.exch_k,
            exchangeable_acidity_cmol_kg=args.exch_acidity,
        ),
        args.crop,
        target_yield_t_ha=args.yield_t_ha,
    )
    print(json.dumps(asdict(rec), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
