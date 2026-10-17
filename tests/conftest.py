import numpy as np
import pandas as pd
import pytest

from driftradar.datasets import make_demo


@pytest.fixture(scope="session")
def demo():
    return make_demo(n=3000, seed=7)


@pytest.fixture(scope="session")
def demo_stable():
    return make_demo(n=3000, seed=7, drift=False)


@pytest.fixture
def rng():
    return np.random.default_rng(0)


@pytest.fixture
def simple_frames(rng):
    ref = pd.DataFrame({"x": rng.normal(0, 1, 2000), "cat": rng.choice(list("abc"), 2000)})
    cur = pd.DataFrame({"x": rng.normal(0, 1, 2000), "cat": rng.choice(list("abc"), 2000)})
    return ref, cur
