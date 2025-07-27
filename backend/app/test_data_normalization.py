import numpy as np

def test_function():
    assert np.array([1, 2, 3]).sum() == 6

def test_none_to_str():
    value = None
    assert value is None
    value = "valid string"
    assert isinstance(value, str)