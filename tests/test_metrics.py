import numpy as np
import pandas as pd
import pytest

from driftradar import metrics


def test_psi_identical_is_zero(rng):
    x = rng.normal(size=5000)
    assert metrics.psi_numeric(x, x) == pytest.approx(0, abs=1e-9)


def test_psi_grows_with_shift(rng):
    ref = rng.normal(size=5000)
    small = metrics.psi_numeric(ref, rng.normal(0.1, 1, 5000))
    big = metrics.psi_numeric(ref, rng.normal(1.0, 1, 5000))
    assert small < 0.1 < 0.25 < big


def test_psi_is_non_negative_and_handles_empty(rng):
    assert metrics.psi_numeric(rng.normal(size=100), rng.normal(size=100)) >= 0
    assert np.isnan(metrics.psi_numeric(np.array([]), np.array([1.0])))
    assert np.isnan(metrics.psi_categorical(pd.Series([], dtype=str), pd.Series(["a"])))


def test_psi_constant_reference():
    ref = np.ones(100)
    assert metrics.psi_numeric(ref, ref) == pytest.approx(0, abs=1e-9)
    assert metrics.psi_numeric(ref, ref + 5) > 0.25


def test_quantile_edges_open_ended(rng):
    edges = metrics.quantile_edges(rng.normal(size=1000), 10)
    assert edges[0] == -np.inf and edges[-1] == np.inf
    assert len(edges) == 13


def test_psi_categorical_new_category():
    ref = pd.Series(["a"] * 50 + ["b"] * 50)
    cur = pd.Series(["a"] * 40 + ["b"] * 30 + ["c"] * 30)
    assert metrics.psi_categorical(ref, cur) > 0.25


def test_category_frequencies_groups_tail():
    ref = pd.Series([f"c{i}" for i in range(100)])
    cats, rf, cf = metrics.category_frequencies(ref, ref, max_categories=5)
    assert metrics.OTHER in cats
    assert rf.sum() == pytest.approx(1) and cf.sum() == pytest.approx(1)


def test_ks_and_chi2(rng):
    stat, p = metrics.ks_test(rng.normal(size=1000), rng.normal(2, 1, 1000))
    assert p < 0.001 and 0 < stat <= 1
    assert all(np.isnan(v) for v in metrics.ks_test(np.array([1.0]), np.array([1.0, 2.0])))
    _, p2 = metrics.chi2_test(pd.Series(list("ab" * 100)), pd.Series(list("ab" * 100)))
    assert p2 > 0.5
    assert metrics.chi2_test(pd.Series(["a"] * 10), pd.Series(["a"] * 10)) == (0.0, 1.0)
    assert np.isnan(metrics.chi2_test(pd.Series([], dtype=str), pd.Series(["a"]))[0])


def test_wasserstein_normalized(rng):
    ref = rng.normal(0, 2, 5000)
    assert metrics.wasserstein_normalized(ref, ref + 2) == pytest.approx(1.0, rel=0.05)
    assert np.isnan(metrics.wasserstein_normalized(np.array([]), ref))
