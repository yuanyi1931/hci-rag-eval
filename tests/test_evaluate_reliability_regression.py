import json
import pytest

from src.evaluate_reliability import evaluate_reliability


# Regression test using the three actual runs from Query 1 in the 2026-08-28 smoke run.
# The expected values were observed during that run and are used to prevent regressions
# in the claim-overlap / confidence-variance calculations.
# Observed pairwise claim jaccards for the three pairs: 0.5, 0.5, 1.0 (mean = 2/3)

FIXTURE_RECORDS = [
    {
        "query_id": 1,
        "run_index": 0,
        "parsed_json": {
            "insights": [
                {"claim": "HCI research increasingly focuses on enriching learning experiences through interactive and intelligent technologies.", "supporting_paper_ids": ["2008.04811v1"], "reasoning": "..."},
                {"claim": "Multisensory and haptic feedback is a growing research priority for conveying information with minimal cognitive disruption.", "supporting_paper_ids": ["2006.00372v2"], "reasoning": "..."},
                {"claim": "Designing for collocated and remote social presence is a recurring challenge across HCI systems.", "supporting_paper_ids": ["2008.02582v1"], "reasoning": "..."},
                {"claim": "Exploratory and user-centered evaluation methods are widely used to surface nuanced insights about emerging interfaces.", "supporting_paper_ids": ["2012.13961v1"], "reasoning": "..."},
                {"claim": "Augmented and mixed reality technologies are being leveraged to blend physical and digital experiences for training and entertainment.", "supporting_paper_ids": ["2007.10897v1"], "reasoning": "..."},
            ],
            "overall_confidence": 0.81,
        },
    },
    {
        "query_id": 1,
        "run_index": 1,
        "parsed_json": {
            "insights": [
                {"claim": "HCI research increasingly focuses on enriching feedback and interaction in skill-learning contexts through technology.", "supporting_paper_ids": ["2008.04811v1"], "reasoning": "..."},
                {"claim": "Multisensory and haptic interfaces are being explored to convey information with lower cognitive burden.", "supporting_paper_ids": ["2006.00372v2"], "reasoning": "..."},
                {"claim": "Bridging the gap between remote or isolated participants and shared social or physical experiences is a recurring design challenge.", "supporting_paper_ids": ["2008.02582v1"], "reasoning": "..."},
                {"claim": "Exploratory and user-centered study designs are predominant, reflecting early-stage investigation of novel interaction paradigms.", "supporting_paper_ids": ["2012.13961v1"], "reasoning": "..."},
            ],
            "overall_confidence": 0.74,
        },
    },
    {
        "query_id": 1,
        "run_index": 2,
        "parsed_json": {
            "insights": [
                {"claim": "HCI research increasingly focuses on enhancing learning through technology-mediated feedback and interaction.", "supporting_paper_ids": ["2008.04811v1"], "reasoning": "..."},
                {"claim": "Embodied and haptic interfaces are emerging as key modalities for conveying information with minimal cognitive disruption.", "supporting_paper_ids": ["2006.00372v2"], "reasoning": "..."},
                {"claim": "Shared and social presence in digital environments is a growing design challenge across HCI contexts.", "supporting_paper_ids": ["2008.02582v1"], "reasoning": "..."},
                {"claim": "Exploratory and mixed-method user studies are the dominant research methodologies across these HCI works.", "supporting_paper_ids": ["2012.13961v1"], "reasoning": "..."},
            ],
            "overall_confidence": 0.78,
        },
    },
]


def test_evaluate_reliability_regression():
    res = evaluate_reliability(FIXTURE_RECORDS, claim_match_threshold=0.6)
    assert res["n_valid_runs"] == 3
    assert res["confidence_sd"] == pytest.approx(0.03511884584284249, rel=1e-2)
    assert res["claim_jaccard"] == pytest.approx(2.0 / 3.0, rel=1e-3)
    assert res["reliability_score"] is not None
