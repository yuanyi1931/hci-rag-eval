from __future__ import annotations

from collections import Counter
from typing import Sequence


def _as_2d_matrix(data: Sequence[Sequence[object]]) -> list[list[object]]:
    if not data:
        return []
    matrix = [list(row) for row in data]
    if not matrix[0]:
        return []
    width = len(matrix[0])
    if any(len(row) != width for row in matrix):
        raise ValueError("Each row in the ratings matrix must have the same length.")
    return matrix


def _validate_matrix_shape(matrix: Sequence[Sequence[object]]) -> tuple[int, int]:
    if not matrix or not matrix[0]:
        raise ValueError("Ratings matrix must be non-empty and rectangular.")
    n_items = len(matrix)
    n_raters = len(matrix[0])
    if n_items < 2 or n_raters < 2:
        raise ValueError("Ratings matrix must contain at least 2 items and 2 raters.")
    if any(len(row) != n_raters for row in matrix):
        raise ValueError("Ratings matrix must be rectangular: rows = items, columns = raters.")
    return n_items, n_raters


def icc_2_1(ratings: Sequence[Sequence[float]]) -> float:
    """Compute ICC(2,1) for a matrix with rows = items/targets and columns = raters.

    This follows the standard Shrout & Fleiss (1979) definition for two-way random-effects,
    single-measure reliability:
        ICC(2,1) = (MSR - MSE) / (MSR + (k - 1) * MSE + k * (MSC - MSE) / n)
    where n is the number of items/targets, k is the number of raters, MSR is the row mean
    square, MSC is the column mean square, and MSE is the residual mean square.
    """
    matrix = _as_2d_matrix(ratings)
    if not matrix:
        return 0.0
    n_items, n_raters = _validate_matrix_shape(matrix)
    numeric_matrix = [[float(value) for value in row] for row in matrix]

    row_means = [sum(row) / n_raters for row in numeric_matrix]
    col_means = [sum(numeric_matrix[i][j] for i in range(n_items)) / n_items for j in range(n_raters)]
    grand_mean = sum(sum(row) for row in numeric_matrix) / (n_items * n_raters)

    ss_rows = sum(n_raters * (row_mean - grand_mean) ** 2 for row_mean in row_means)
    ss_cols = sum(n_items * (col_mean - grand_mean) ** 2 for col_mean in col_means)
    ss_total = sum((value - grand_mean) ** 2 for row in numeric_matrix for value in row)
    ss_error = ss_total - ss_rows - ss_cols

    df_rows = n_items - 1
    df_cols = n_raters - 1
    df_error = df_rows * df_cols

    msr = ss_rows / df_rows if df_rows else 0.0
    msc = ss_cols / df_cols if df_cols else 0.0
    mse = ss_error / df_error if df_error else 0.0

    denominator = msr + (n_raters - 1) * mse + n_raters * (msc - mse) / n_items
    if abs(denominator) < 1e-12:
        return 1.0 if abs(msr - mse) < 1e-12 else 0.0
    return (msr - mse) / denominator


def icc2_1(ratings: Sequence[Sequence[float]]) -> float:
    return icc_2_1(ratings)


def jaccard_similarity(left: Sequence[object], right: Sequence[object]) -> float:
    """Return the Jaccard similarity for two sets of claim labels."""
    left_set = set(left)
    right_set = set(right)
    if not left_set and not right_set:
        return 1.0
    if not left_set or not right_set:
        return 0.0
    union = left_set | right_set
    if not union:
        return 1.0
    return len(left_set & right_set) / len(union)


def krippendorff_alpha(ratings: Sequence[Sequence[object]], level: str = "nominal") -> float:
    """Compute Krippendorff's alpha for nominal judgments.

    This implementation follows the finite-sample corrected disagreement form from Krippendorff (2004):
        D_e = (n^2 - sum_j n_j^2) / (n * (n - 1))
    where n is the total number of judgments and n_j is the count of each nominal category.
    Nominal level is currently implemented; ordinal and interval variants are intentionally not supported.
    """
    if level != "nominal":
        raise NotImplementedError("Only nominal Krippendorff's alpha is implemented in this project.")
    if not ratings:
        return 0.0
    matrix = _as_2d_matrix(ratings)
    if not matrix:
        return 0.0
    n_items, n_raters = _validate_matrix_shape(matrix)

    label_counts = Counter(value for row in matrix for value in row)
    total = sum(label_counts.values())
    if total <= 1:
        return 0.0

    expected_disagreement = (total**2 - sum(count**2 for count in label_counts.values())) / (total * (total - 1))
    if abs(expected_disagreement) < 1e-12:
        return 1.0

    mismatches = 0
    pair_count = 0
    for row in matrix:
        for i in range(len(row)):
            for j in range(i + 1, len(row)):
                pair_count += 1
                if row[i] != row[j]:
                    mismatches += 1
    observed_disagreement = mismatches / pair_count if pair_count else 0.0
    return 1.0 - (observed_disagreement / expected_disagreement)


def cohen_kappa(rater_1: Sequence[object], rater_2: Sequence[object]) -> float:
    """Compute Cohen's kappa coefficient for two raters.

    The usual formula is:
        kappa = (p_o - p_e) / (1 - p_e)
    where p_o is observed agreement and p_e is agreement expected by chance.
    """
    if len(rater_1) != len(rater_2):
        raise ValueError("Both rating sequences must have the same length.")
    if not rater_1:
        return 0.0
    labels = list(dict.fromkeys(list(rater_1) + list(rater_2)))
    if len(labels) == 1:
        return 1.0

    confusion = {label: {inner: 0 for inner in labels} for label in labels}
    row_totals = {label: 0 for label in labels}
    col_totals = {label: 0 for label in labels}
    for a, b in zip(rater_1, rater_2):
        confusion[a][b] += 1
        row_totals[a] += 1
        col_totals[b] += 1

    total = len(rater_1)
    observed_agreement = sum(confusion[label][label] for label in labels) / total
    expected_agreement = sum((row_totals[label] / total) * (col_totals[label] / total) for label in labels)
    if abs(expected_agreement - 1.0) < 1e-12:
        return 1.0 if abs(observed_agreement - 1.0) < 1e-12 else 0.0
    if expected_agreement == 0.0:
        return 0.0
    return (observed_agreement - expected_agreement) / (1.0 - expected_agreement)
