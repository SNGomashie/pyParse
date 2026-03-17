""" Module contains the parameterized binary types, to be used in the DSL of pyparsing. These types contain metadata
which is used to create appropriate concrete binary types.
"""
from dataclasses import dataclass
from typing import Any,  Annotated, get_origin, get_args

from construct import Array, BytesInteger, BitsInteger, Bytes, this

from pyparse.errors import BinaryDefinitionError, BinaryTypeError


@dataclass(frozen=True)
class IntegerBinaryMeta:
    """ Metadata for a signed or unsigned integer field of arbitrary bit width.

    Produces a ``BytesInteger`` for byte-aligned widths, ``BitsInteger`` otherwise.
    """
    bits:   int
    signed: bool = False

    def to_construct(self) -> BytesInteger | BitsInteger:
        if self.bits % 8 == 0:
            return BytesInteger(self.bits // 8, signed=self.signed)
        return BitsInteger(self.bits, signed=self.signed)


class b_int:
    """ Factory for integer binary type annotations.

    Use ``b_int[bits]`` for unsigned or ``b_int[bits, signed]`` for signed integers.
    Supports arbitrary bit widths. Sub-byte widths are intended for use in bit fields.
    """
    @classmethod
    def __class_getitem__(cls, args) -> type[int]:
        """ Return an ``Annotated[int, IntegerBinaryMeta]`` type for the given width and signedness.
        """
        if not isinstance(args, tuple):
            bits, signed = args, False
        elif len(args) != 2:
            raise BinaryTypeError("Use b_int[bits, signed]")
        else:
            bits, signed = args
        if not isinstance(bits, int) or bits <= 0:
            raise BinaryDefinitionError("Width in bits must be a positive integer")
        if not isinstance(signed, bool):
            raise BinaryDefinitionError("Signed must be a boolean")
        return Annotated[int, IntegerBinaryMeta(bits, signed)]  # type: ignore[return-value]


@dataclass(frozen=True)
class BytesBinaryMeta:
    """ Metadata for a fixed-width raw bytes field.
    """
    width: int

    def to_construct(self) -> Bytes:
        return Bytes(self.width)


class b_bytes:
    """ Factory for fixed-width bytes field annotations. Use ``b_bytes[width]``.
    """
    @classmethod
    def __class_getitem__(cls, args) -> type[bytes]:
        """ Return an ``Annotated[bytes, BytesBinaryMeta]`` type for the given byte width.
        """
        if isinstance(args, tuple):
            raise BinaryTypeError("Use b_bytes[width]")
        if not isinstance(args, int) or args <= 0:
            raise BinaryDefinitionError("width must be a positive integer")
        return Annotated[bytes, BytesBinaryMeta(args)]  # type: ignore[return-value]


@dataclass(frozen=True)
class ArrayBinaryMeta:
    """ Metadata for an array field.

    ``width`` may be an integer (fixed count) or a string referencing another field name (dynamic count).
    """
    width: int | str
    element: Any

    def to_construct(self) -> Array:
        expr = this[self.width] if isinstance(self.width, str) else self.width
        if hasattr(self.element, '__construct__'):  # nested BinaryPacket
            return Array(expr, self.element.__construct__)
        return Array(expr, get_binary_meta(self.element).to_construct())


class b_array:
    """Factory for array field annotations. Use ``b_array[width, element_type]``.

    ``width`` may be a fixed integer or a field name string (e.g. ``'count'``).
    """
    @classmethod
    def __class_getitem__(cls, args) -> type[list]:
        """ Return an ``Annotated[list, ArrayBinaryMeta]`` type.
        """
        width, element = args
        return Annotated[list, ArrayBinaryMeta(width, element)]  # type: ignore[return-value]


def get_binary_meta(annotation: Any) -> IntegerBinaryMeta | BytesBinaryMeta | ArrayBinaryMeta | None:
    if get_origin(annotation) is Annotated:
        for arg in get_args(annotation)[1:]:
            if isinstance(arg, (IntegerBinaryMeta, BytesBinaryMeta, ArrayBinaryMeta)):
                return arg
    return None
