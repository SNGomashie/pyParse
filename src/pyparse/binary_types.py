""" Module contains the parameterized binary types, to be used in the DSL of pyparsing. These types contain metadata
which is used to create appropriate concrete binary types.
"""
from abc import ABC, abstractmethod
from functools import lru_cache
from typing import Any, ClassVar

from construct import Array, BytesInteger, BitsInteger, Struct, Bytes, this

from pyparse.errors import BinaryDefinitionError, BinaryTypeError


class AbstractBinaryType(ABC):
    """ Abstract base class for binary types.

    Subclasses must implement ``__class_getitem__`` and ``to_concrete``, where ``__class_getitem__`` is used to
    parameterize a binary type to create a concrete binary type. Subclasses carry metadata definitions in ``__meta__``.
    ``to_construct`` is used to return the associated struct.
    """
    __meta__: ClassVar[dict[str, Any]]

    def __init_subclass__(cls, **meta: Any) -> None:
        """ Capture keyword metadata declared on subclasses.

        This enables defining concrete types by creating subclasses with keyword arguments, e.g.
        via dynamic class creation.
        """
        super().__init_subclass__()
        cls.__meta__ = dict(meta)

    @classmethod
    @abstractmethod
    def __class_getitem__(cls, args: object) -> type[Any]:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def to_construct(cls) -> Struct:
        raise NotImplementedError


class IntegerBinaryType(AbstractBinaryType):
    """ Parametric integer binary type.

    Use ``IntegerBinaryType[bits, signed]`` (typically exposed as ``bin.int[bits, signed]``)
    to obtain a cached concrete class token that is both an ``int`` subclass and an
    ``IntegerBinaryType`` subclass.

    :note: Only supports byte-aligned integers.
    """
    @classmethod
    def __class_getitem__(cls, args) -> type[int]:
        """ Parameterize the integer type family.

        :param args: Parameter typle of (bits, signed).
        :returns:    A cached concrete integer type class.
        """
        if not isinstance(args, tuple):
            bits   = args
            signed = False
        elif len(args) != 2:
            raise BinaryTypeError("Use bin.int[width, signed]")
        else:
            bits, signed = args

        if not isinstance(bits, int) or bits <= 0:
            raise BinaryDefinitionError("Width in bits must be a positive integer")

        if not isinstance(signed, bool):
            raise BinaryDefinitionError("Signed must be a boolean")

        # return Annotated[int, IntegerMeta(bits, signed)]
        return _build_integer_type(cls, bits, signed)

    @classmethod
    def to_construct(cls) -> BytesInteger | BitsInteger:
        """ Convert this integer definition into a construct parser.

        Only use byte-aligned integers.

        :returns: A construct integer parser.
        """
        meta   = cls.__meta__
        bits   = meta['bits']
        signed = meta['signed']

        if bits % 8 == 0:
            return BytesInteger(bits // 8, signed=signed)
        else:
            return BitsInteger(bits, signed=signed)


@lru_cache(None)
def _build_integer_type(base: type[IntegerBinaryType], bits: int, signed: bool) -> type[int]:
    """ Build a cached concrete integer binary type class.

    The returned class is a subclass of both ``ìnt`` and the provided ``base`` family class,
    and carries ``bits`` and ``signed`` in ``__meta__``.

    :param base:   Integer type family
    :param bits:   Integer width in bits
    :param signed: Integer signedness.
    :returns:      A concrete integer type class.
    """
    prefix = 'int' if signed else 'uint'
    name   = f'{prefix}{bits}'

    namespace = {
        '__module__': base.__module__,
        '__qualname__': name

    }

    metaClass = type(base)

    return metaClass(name,
                     (int, base),
                     namespace,
                     bits=bits,
                     signed=signed)


class BytesBinaryType(AbstractBinaryType):
    """ Parametric bytes binary type.

    Use ``BytesBinaryType[width]`` (typically exposed as ``b_bytes[width]``)
    to obtain a cached concrete class token that is both an ``bytes`` subclass and an
    ``BytesBinaryType`` subclass.
    """
    @classmethod
    def __class_getitem__(cls, args: Any) -> type[bytes]:
        """ Parameterize the integer type family.

        :param args: Parameter tuple of (width,).
        :returns:    A cached concrete bytes type class.
        """
        if isinstance(args, tuple):
            raise BinaryTypeError("Use bin.bytes[width]")

        width = args

        if not isinstance(width, int) or width <= 0:
            raise BinaryDefinitionError("width must be a positive integer")

        return _build_bytes_type(cls, width)

    @classmethod
    def to_construct(cls) -> Bytes:
        """ Convert this bytes definition into a construct parser.

        :returns: A construct integer parser.
        """
        meta = cls.__meta__
        width = meta['width']

        return Bytes(width)


@lru_cache(None)
def _build_bytes_type(base: type[BytesBinaryType], width: int) -> type[bytes]:
    """ Build a cached concrete bytes binary type class.

    The returned class is a subclass of both ``bytes`` and the provided ``base`` family class,
    and carries ``bits`` and ``signed`` in ``__meta__``.

    :param base:  Bytes type family
    :param width: Byte string width in bits
    :returns:     A concrete integer type class.
    """
    namespace = {
        '__module__': base.__module__,
        '__qualname__': 'bytes'

    }

    metaClass = type(base)

    return metaClass('bytes',
                     (bytes, base),
                     namespace,
                     width=width)


class ArrayBinaryType(AbstractBinaryType):
    @classmethod
    def __class_getitem__(cls, args) -> type[list]:
        width, element = args
        return _build_array_type(cls, width, element)

    @classmethod
    def to_construct(cls) -> Array:
        meta    = cls.__meta__
        width   = meta['width']
        element = meta['element']

        expr = this[width] if isinstance(width, str) else width

        if hasattr(element, '__construct__'):
            return Array(expr, element.__construct__)

        return Array(expr, element.to_construct())


@lru_cache(None)
def _build_array_type(base: type[ArrayBinaryType], width: int | str, element: ArrayBinaryType) -> type[list]:
    """ Build a cached concrete array binary type class.

    The returned class is a subclass of both ``array`` and the provided ``base`` family class,
    and carries ``bits`` and ``signed`` in ``__meta__``.

    :param base:    Bytes type family
    :param width:   Byte string width in bits
    :param element:
    :returns:       A concrete integer type class.
    """
    elementName = element.__name__.lower()
    arrayName = f"{elementName}_array_{width}"

    namespace = {
        '__module__': base.__module__,
        '__qualname__': arrayName
    }

    metaClass = type(base)

    return metaClass(arrayName,
                     (list, base),
                     namespace,
                     width=width,
                     element=element)

