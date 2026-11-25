"""Acidic soil lime neutralization, crop nutrient gap analysis & least-cost NPK blend LP."""

from .fertility import (
    CROP_NUTRIENT_TARGETS,
    EAST_AFRICA_FERTILIZERS,
    CropTarget,
    FertilizerProduct,
    FertilizerRecommendation,
    LimePrescription,
    SoilTest,
    compute_lime_requirement,
    optimize_fertilizer_blend,
)

__all__ = [
    "CROP_NUTRIENT_TARGETS",
    "EAST_AFRICA_FERTILIZERS",
    "CropTarget",
    "FertilizerProduct",
    "FertilizerRecommendation",
    "LimePrescription",
    "SoilTest",
    "compute_lime_requirement",
    "optimize_fertilizer_blend",
]
__version__ = "0.1.0"
