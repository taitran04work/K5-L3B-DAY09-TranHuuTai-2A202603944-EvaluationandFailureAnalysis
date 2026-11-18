"""Statistics students implement (M2 judge calibration, M4 paired bootstrap).

Rules: a judge is a classifier -- measure it like one. A higher mean is not
"better" until the paired CI of the difference excludes 0.
Reference values to self-check are in tests/test_lab9_stats.py.
"""

from __future__ import annotations

from collections.abc import Sequence
import math

import numpy as np
from scipy.stats import bootstrap

POS = "FAIL"   # the judge's job is to FIND failures, so FAIL is the positive class


def confusion(human: Sequence[str], judge: Sequence[str]) -> dict[str, int]:
    """tp/fp/fn/tn with FAIL as positive."""
    if len(human) != len(judge):
        raise ValueError("human and judge must have the same length")
    pairs = [(str(h).strip().upper(), str(j).strip().upper()) for h, j in zip(human, judge)]
    return {
        "tp": sum(h == POS and j == POS for h, j in pairs),
        "fp": sum(h == "PASS" and j == POS for h, j in pairs),
        "fn": sum(h == POS and j == "PASS" for h, j in pairs),
        "tn": sum(h == "PASS" and j == "PASS" for h, j in pairs),
    }


def precision_recall(human: Sequence[str], judge: Sequence[str]) -> tuple[float, float]:
    # TODO M2: precision = tp/(tp+fp), recall = tp/(tp+fn); return 0.0 when the denominator is 0
    cm = confusion(human, judge)
    precision = cm["tp"] / (cm["tp"] + cm["fp"]) if cm["tp"] + cm["fp"] else 0.0
    recall = cm["tp"] / (cm["tp"] + cm["fn"]) if cm["tp"] + cm["fn"] else 0.0
    return precision, recall


def cohen_kappa(human: Sequence[str], judge: Sequence[str]) -> float:
    """kappa = (p_o - p_e) / (1 - p_e). Raise ValueError when undefined (p_e == 1):
    a constant judge has no signal and must FAIL calibration, not pass on a technicality."""
    if len(human) != len(judge):
        raise ValueError("human and judge must have the same length")
    cm = confusion(human, judge)
    n = sum(cm.values())
    if n == 0:
        raise ValueError("kappa is undefined")
    p_observed = (cm["tp"] + cm["tn"]) / n
    human_fail = cm["tp"] + cm["fn"]
    human_pass = cm["fp"] + cm["tn"]
    judge_fail = cm["tp"] + cm["fp"]
    judge_pass = cm["fn"] + cm["tn"]
    p_expected = ((human_fail * judge_fail) + (human_pass * judge_pass)) / (n * n)
    if p_expected == 1:
        raise ValueError("kappa is undefined for a constant judge")
    return (p_observed - p_expected) / (1 - p_expected)


def rogan_gladen(observed_rate: float, sensitivity: float, specificity: float) -> float:
    """Correct an observed failure rate for judge error; clip to [0, 1]."""
    # TODO M2: (p_obs + spec - 1) / (sens + spec - 1)
    denominator = sensitivity + specificity - 1
    if denominator == 0:
        return 0.0
    corrected = (observed_rate + specificity - 1) / denominator
    return min(1.0, max(0.0, corrected))


def paired_bootstrap(a: Sequence[float], b: Sequence[float], *, n_resamples: int = 1000,
                     rng: int = 2027, confidence: float = 0.95) -> tuple[float, float, float]:
    """a[i], b[i] = per-item mean over seeds, SAME items, SAME order.
    Return (mean(a)-mean(b), lo, hi) with scipy.stats.bootstrap(paired=True, method="percentile",
    rng=numpy.random.default_rng(rng)). If a == b everywhere return (0.0, 0.0, 0.0)."""
    if len(a) != len(b):
        raise ValueError("paired samples must have the same length")
    values_a = [float(x) for x in a]
    values_b = [float(x) for x in b]
    if not values_a:
        raise ValueError("paired samples must not be empty")
    difference = float(np.mean(values_a) - np.mean(values_b))
    if all(abs(x - y) < 1e-12 for x, y in zip(values_a, values_b)):
        return 0.0, 0.0, 0.0
    result = bootstrap(
        (np.asarray(values_a), np.asarray(values_b)),
        statistic=lambda x, y: float(np.mean(x) - np.mean(y)),
        n_resamples=n_resamples,
        method="percentile",
        paired=True,
        rng=np.random.default_rng(rng),
        confidence_level=confidence,
    )
    alpha = (1.0 - confidence) / 2
    lo = float(result.confidence_interval.low)
    hi = float(result.confidence_interval.high)
    if alpha == 0:
        lo = hi = difference
    return difference, lo, hi


def pass_at_k(n: int, c: int, k: int) -> float:
    """Probability that AT LEAST ONE of k trials drawn from n (c of them passing) passes.
    Unbiased estimator (Chen et al. 2021): 1 - C(n-c, k) / C(n, k). Raise ValueError if k > n."""
    if n < 0 or c < 0 or k < 0:
        raise ValueError("n, c and k must be non-negative")
    if c > n:
        raise ValueError("c cannot exceed n")
    if k < 1:
        raise ValueError("k must be positive")
    if k > n:
        raise ValueError("k cannot exceed n")
    return 1.0 - math.comb(n - c, k) / math.comb(n, k)


def pass_hat_k(n: int, c: int, k: int) -> float:
    """pass^k (tau-bench, Yao et al. 2024): probability that ALL k trials drawn from n pass.
    Unbiased estimator: C(c, k) / C(n, k). Raise ValueError if k > n.
    pass^k <= pass@1 <= pass@k; a reliable agent keeps pass^k close to pass@1."""
    if n < 0 or c < 0 or k < 0:
        raise ValueError("n, c and k must be non-negative")
    if c > n:
        raise ValueError("c cannot exceed n")
    if k < 1:
        raise ValueError("k must be positive")
    if k > n:
        raise ValueError("k cannot exceed n")
    return math.comb(c, k) / math.comb(n, k)
