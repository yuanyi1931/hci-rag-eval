import pytest

from src.stats import cohen_kappa, icc_2_1, jaccard_similarity, krippendorff_alpha


# Source: Shrout & Fleiss (1979), Table 1.
# The convention in this project is rows = items/targets and columns = raters.
# Published ICC(2,1) for this matrix is approximately 0.290.
def test_icc_2_1_shrout_fleiss_1979_table_1():
    ratings = [
        [9, 2, 5, 8],
        [6, 1, 3, 2],
        [8, 4, 6, 8],
        [7, 1, 2, 6],
        [10, 5, 6, 9],
        [6, 2, 4, 7],
    ]
    assert icc_2_1(ratings) == pytest.approx(0.290, rel=1e-2)


# When every item is rated identically across all raters, the ICC formula itself should
# converge to 1.0 without any special-case shortcut. This test verifies the real formula,
# not a guard clause.
def test_icc_2_1_perfect_agreement_formula_converges_to_one():
    ratings = [
        [5, 5, 5],
        [6, 6, 6],
        [7, 7, 7],
    ]
    assert icc_2_1(ratings) == pytest.approx(1.0)


# Random-like sanity check: no systematic agreement beyond chance should keep ICC near 0.
def test_icc_2_1_random_like_data_near_zero():
    ratings = [
        [2, 5, 5, 2],
        [3, 5, 4, 5],
        [1, 5, 1, 4],
        [3, 5, 2, 2],
        [4, 5, 5, 4],
        [4, 2, 2, 2],
    ]
    assert icc_2_1(ratings) == pytest.approx(0.0, abs=0.15)


# Cross-check against pingouin.intraclass_corr for the published benchmark matrix.
# Important naming difference: pingouin follows McGraw & Wong (1996), while this project
# and the published Shrout & Fleiss (1979) table use the older S&F naming convention.
# In the S&F notation, ICC(2,1) is the two-way random-effects, absolute-agreement ICC for
# a single rating. Pingouin encodes that exact model as Type == "ICC(A,1)".
# We therefore match on the exact Type label instead of a brittle "contains" filter.
# Source: independent package output used only for validation, not as the project implementation.
def test_icc_2_1_matches_pingouin_intraclass_corr():
    pingouin = pytest.importorskip("pingouin")
    import pandas as pd

    ratings = [
        [9, 2, 5, 8],
        [6, 1, 3, 2],
        [8, 4, 6, 8],
        [7, 1, 2, 6],
        [10, 5, 6, 9],
        [6, 2, 4, 7],
    ]
    df = []
    for item_idx, row in enumerate(ratings, start=1):
        for rater_idx, score in enumerate(row, start=1):
            df.append({"item": item_idx, "rater": rater_idx, "score": score})
    result = pingouin.intraclass_corr(data=pd.DataFrame(df), targets="item", raters="rater", ratings="score")
    matching_rows = result[result["Type"] == "ICC(A,1)"]
    assert len(matching_rows) == 1, (
        "Expected exactly one pingouin ICC row with Type == 'ICC(A,1)'; "
        f"actual Type values were: {sorted(result['Type'].dropna().unique().tolist())}"
    )
    assert matching_rows.iloc[0]["ICC"] == pytest.approx(icc_2_1(ratings), rel=1e-2)


# When all judgments are identical, the nominal Krippendorff alpha formula should converge
# to 1.0 without any special-case shortcut; this test checks the actual formula at the exact
# agreement boundary.
def test_krippendorff_alpha_perfect_agreement_formula_converges_to_one():
    ratings = [
        ["yes", "yes", "yes"],
        ["yes", "yes", "yes"],
        ["yes", "yes", "yes"],
    ]
    assert krippendorff_alpha(ratings) == pytest.approx(1.0)


# Random-like sanity check: nominal alpha should stay near 0 when agreement is close to chance.
def test_krippendorff_alpha_random_like_data_near_zero():
    ratings = [
        ["B", "B", "A", "B"],
        ["B", "B", "B", "B"],
        ["B", "A", "A", "B"],
        ["A", "A", "B", "A"],
    ]
    alpha = krippendorff_alpha(ratings)
    assert alpha == pytest.approx(0.0, abs=0.2)


# source: hand calculation for sets with intersection 2 and union 4.
def test_jaccard_similarity_hand_calculated():
    assert jaccard_similarity(["a", "b", "c"], ["b", "c", "d"]) == pytest.approx(0.5)


def test_krippendorff_alpha_level_not_nominal_raises():
    ratings = [["A", "B"], ["A", "B"]]
    with pytest.raises(NotImplementedError):
        krippendorff_alpha(ratings, level="ordinal")


def test_krippendorff_alpha_shape_error_message_is_generic():
    with pytest.raises(ValueError, match="at least 2 items and 2 raters"):
        krippendorff_alpha([["A"], ["B"]])


# Hand-calculation example (not a literature citation): a 2x2 confusion matrix with
# counts [[4, 1], [2, 3]], so the four entries are:
#   yes/yes = 4, yes/no = 1, no/yes = 2, no/no = 3.
# This gives p_o = (4 + 3) / 10 = 0.70 and p_e = ( (5/10)*(6/10) + (5/10)*(4/10) ) = 0.50.
# Therefore:
#   kappa = (p_o - p_e) / (1 - p_e)
#         = (0.70 - 0.50) / (1.00 - 0.50)
#         = 0.20 / 0.50
#         = 0.40.
# This is an explicit, checkable worked example; the value is not being claimed as a Cohen (1960)
# page/table citation.
def test_cohens_kappa_hand_calculation_example():
    r1 = ["yes", "yes", "yes", "yes", "yes", "no", "no", "no", "no", "no"]
    r2 = ["yes", "yes", "yes", "yes", "no", "yes", "yes", "no", "no", "no"]
    assert cohen_kappa(r1, r2) == pytest.approx(0.4)
