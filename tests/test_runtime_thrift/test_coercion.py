import pytest

from src.openrouter_mcp.runtime_thrift import _coercion, metrics, summary

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, 0),
        ("", 0),
        (False, 0),
        ("7", 7),
        (2.9, 2),
        ("invalid", 0),
    ],
)
def test_as_int_preserves_forgiving_conversion(value, expected):
    assert _coercion._as_int(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, 0.0),
        ("", 0.0),
        (False, 0.0),
        ("7.25", 7.25),
        (3, 3.0),
        ("invalid", 0.0),
    ],
)
def test_as_float_preserves_forgiving_conversion(value, expected):
    assert _coercion._as_float(value) == expected


def test_coercion_does_not_absorb_truthiness_errors():
    class BrokenTruthiness:
        def __bool__(self):
            raise RuntimeError("truthiness failed")

    value = BrokenTruthiness()

    with pytest.raises(RuntimeError, match="truthiness failed"):
        _coercion._as_int(value)

    with pytest.raises(RuntimeError, match="truthiness failed"):
        _coercion._as_float(value)


def test_coercion_does_not_absorb_overflow_errors():
    class IntOverflow:
        def __bool__(self):
            return True

        def __int__(self):
            raise OverflowError("int overflow")

    class FloatOverflow:
        def __bool__(self):
            return True

        def __float__(self):
            raise OverflowError("float overflow")

    with pytest.raises(OverflowError, match="int overflow"):
        _coercion._as_int(IntOverflow())

    with pytest.raises(OverflowError, match="float overflow"):
        _coercion._as_float(FloatOverflow())


def test_runtime_thrift_consumers_share_coercion_functions():
    assert metrics._as_int is summary._as_int is _coercion._as_int
    assert metrics._as_float is summary._as_float is _coercion._as_float
