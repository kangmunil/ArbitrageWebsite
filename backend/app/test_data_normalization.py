import numpy as np

def test_function():
    """간단한 numpy 배열 합계 테스트 함수입니다.

    numpy 배열의 합계가 올바르게 계산되는지 확인합니다.
    """
    assert np.array([1, 2, 3]).sum() == 6

def test_none_to_str():
    """None 값이 문자열로 변환되지 않고 None으로 유지되는지 테스트합니다.

    변수가 None일 때와 유효한 문자열일 때의 타입을 확인합니다.
    """
    value = None
    assert value is None
    value = "valid string"
    assert isinstance(value, str)