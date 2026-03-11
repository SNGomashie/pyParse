import pytest
from construct import BytesInteger

from pyparse.errors import BinaryDefinitionError, BinaryTypeError
from pyparse.binary_types import _build_integer_type
from pyparse.binary_types import IntegerBinaryType

from pyparse import b_int


def test_class_get_item_rejects_non_tuple() -> None:
    with pytest.raises(BinaryDefinitionError):
        b_int['nope']


def test_class_get_item_rejects_wrong_arity() -> None:
    with pytest.raises(BinaryTypeError):
        b_int[8, True, 0]


@pytest.mark.parametrize('bits', [0, -1, -8])
def test_class_get_item_rejects_non_positive_bits(bits: int) -> None:
    with pytest.raises(BinaryDefinitionError):
        b_int[bits, True]


def test_class_get_item_rejects_non_int_bits() -> None:
    with pytest.raises(BinaryDefinitionError):
        b_int['8', True]


def test_class_get_item_rejects_non_bool_signed() -> None:
    with pytest.raises(BinaryDefinitionError):
        b_int[8, 1]


def test_build_returns_concrete_subclass() -> None:
    t = b_int[8, True]
    assert isinstance(t, type)
    assert issubclass(t, int)
    assert issubclass(t, b_int)


def test_build_caches_by_family_parameters() -> None:
    a = b_int[8, True]
    b = b_int[8, True]
    c = b_int[8, False]

    assert a is b
    assert a is not c


def test_build_caches_function() -> None:
    a = _build_integer_type(IntegerBinaryType, 8, True)
    b = _build_integer_type(IntegerBinaryType, 8, True)
    assert a is b


def test_metadata_is_attached() -> None:
    t = IntegerBinaryType[24, False]
    assert hasattr(t, '__meta__')
    assert t.__meta__['bits'] == 24
    assert t.__meta__['signed'] is False


def test_to_construct_byte_aligned() -> None:
    t = IntegerBinaryType[24, False]
    c = t.to_construct()
    assert isinstance(c, BytesInteger)
