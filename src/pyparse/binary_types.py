""" Module contains the parameterized binary types, to be used in the DSL of pyparsing. These types contain metadata
which is used to create appropriate concrete binary types.
"""
from dataclasses import dataclass
from enum import Enum, Flag, EnumType
from typing import Any, Annotated, Union, get_origin, get_args, Callable

from construct import Array, BytesInteger, BitsInteger, Bytes, this, Adapter, GreedyRange, Struct, Switch

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

    @property
    def bit_width(self) -> int:
        return self.bits

    def description(self) -> str:
        return f"{'int' if self.signed else 'uint'}{self.bits}"


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
class EnumBinaryMeta:
    """ Metadata for an enum-valued integer field of arbitrary bit width.

    Wraps a ``BytesInteger`` or ``BitsInteger`` with an adapter that converts
    raw integers to/from the given ``IntEnum`` subclass on parse/build.
    """

    bits: int
    type: EnumType
    signed: bool = False

    def to_construct(self) -> Adapter:
        if self.bits % 8 == 0:
            base = BytesInteger(self.bits // 8, signed=self.signed)
        else:
            base = BitsInteger(self.bits, signed=self.signed)

        enumType = self.type

        class EnumAdapter(Adapter):
            def _decode(self, obj, context, path):
                return enumType(obj)

            def _encode(self, obj, context, path):
                return obj.value if isinstance(obj, enumType) else int(obj)

        return EnumAdapter(base)

    @property
    def bit_width(self) -> int:
        return self.bits

    def description(self) -> str:
        return f"{self.type.__name__}[{'int' if self.signed else 'uint'}{self.bits}]"


class b_enum:
    """ Factory for enum-valued field annotations.

    Use ``b_enum[bits, EnumType, signed]``.  All three arguments are required.

    :param bits:     Width of the field in bits (positive integer).
    :param EnumType: An ``IntEnum`` subclass whose values map to the raw integer.
    :param signed:   ``True`` for a signed field, ``False`` for unsigned.
    """
    @classmethod
    def __class_getitem__(cls, args) -> type[Enum]:
        if not isinstance(args, tuple) or len(args) not in (2, 3):
            raise BinaryTypeError("Use b_enum[bits, enumType] or b_enum[bits, enumType, signed]")

        bits, enumType, *remaining = args
        signed = remaining[0] if remaining else False

        if not isinstance(bits, int) or bits <= 0:
            raise BinaryDefinitionError("Width in bits must be a positive integer")
        if not isinstance(signed, bool):
            raise BinaryDefinitionError("Signed must be a boolean")
        if not isinstance(enumType, EnumType):
            raise BinaryDefinitionError("enumType must be an Enum")

        return Annotated[enumType, EnumBinaryMeta(bits, enumType, signed)]


@dataclass(frozen=True)
class FlagBinaryMeta:
    """ Metadata for a bitmask/flag field of arbitrary bit width.

    Wraps a ``BytesInteger`` or ``BitsInteger`` with an adapter that converts
    raw integers to/from the given ``IntFlag`` subclass on parse/build.
    """
    bits: int
    type: EnumType
    signed: bool = False

    def to_construct(self) -> Adapter:
        if self.bits % 8 == 0:
            base = BytesInteger(self.bits // 8, signed=self.signed)
        else:
            base = BitsInteger(self.bits, signed=self.signed)

        flagType = self.type

        class FlagAdapter(Adapter):
            def _decode(self, obj, context, path):
                return flagType(obj)

            def _encode(self, obj, context, path):
                return obj.value if isinstance(obj, flagType) else int(obj)

        return FlagAdapter(base)

    @property
    def bit_width(self) -> int:
        return self.bits

    def description(self) -> str:
        return f"{self.type.__name__}[{'int' if self.signed else 'uint'}{self.bits}]"


class b_flag:
    """ Factory for bitmask/flag field annotations.

    Use ``b_flag[bits, FlagType, signed]``.  All three arguments are required.

    :param bits:     Width of the field in bits (positive integer).
    :param FlagType: An ``IntFlag`` subclass whose members represent individual bits.
    :param signed:   ``True`` for a signed field, ``False`` for unsigned.
    """
    @classmethod
    def __class_getitem__(cls, args) -> type[Flag]:
        if not isinstance(args, tuple) or len(args) not in (2, 3):
            raise BinaryTypeError("Use b_flag[bits, enumType] or b_flag[bits, enumType, signed]")

        bits, flagType, *remaining = args
        signed = remaining[0] if remaining else False

        if not isinstance(bits, int) or bits <= 0:
            raise BinaryDefinitionError("Width in bits must be a positive integer")
        if not isinstance(signed, bool):
            raise BinaryDefinitionError("Signed must be a boolean")
        if not isinstance(flagType, EnumType):
            raise BinaryDefinitionError("flagType must be an Flag")

        return Annotated[flagType, FlagBinaryMeta(bits, flagType, signed)]


@dataclass(frozen=True)
class BytesBinaryMeta:
    """ Metadata for a fixed-width raw bytes field.
    """
    width: int

    def to_construct(self) -> Bytes:
        return Bytes(self.width)

    @property
    def bit_width(self) -> int:
        return self.width * 8

    def description(self) -> str:
        return "byte" if self.width == 1 else f"bytes[{self.width}]"


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

    @property
    def bit_width(self) -> int | None:
        if isinstance(self.width, str):
            return None  # dynamic size — resolved at parse time
        if hasattr(self.element, "__construct__"):
            return self.width * self.element.__construct__.sizeof() * 8
        return self.width * get_binary_meta(self.element).bit_width

    def description(self) -> str:
        size = f"'{self.width}'" if isinstance(self.width, str) else str(self.width)
        return f"{_element_label(self.element)}[{size}]"


class b_array:
    """Factory for array field annotations. Use ``b_array[width, element_type]``.

    ``width`` may be a fixed integer or a field name string (e.g. ``'count'``).
    """
    @classmethod
    def __class_getitem__(cls, args) -> type[list]:
        """ Return an ``Annotated[list, ArrayBinaryMeta]`` type.
        """
        width, element = args
        return Annotated[list[element], ArrayBinaryMeta(width, element)]  # type: ignore[return-value]


@dataclass(frozen=True)
class GreedyBinaryMeta:
    """ Metadata for a variable-length array field that consumes all remaining bytes.

    Produces a ``GreedyRange`` over the element type's construct.
    """
    element: Any

    def to_construct(self) -> GreedyRange:
        return GreedyRange(get_binary_meta(self.element).to_construct())

    @property
    def bit_width(self) -> None:
        return None  # consumes to end of input

    def description(self) -> str:
        return f"{_element_label(self.element)}[...]"


class b_greedy:
    """ Factory for greedy array field annotations.

    Use ``b_greedy[element_type]``.  The field reads elements until the input
    is exhausted, so it must be the last field in a packet.
    """
    @classmethod
    def __class_getitem__(cls, args) -> type[list]:
        element = args
        return Annotated[list[element], GreedyBinaryMeta(element)]


@dataclass(frozen=True)
class SwitchBinaryMeta:
    """ Metadata for a switch field that selects a sub-structure based on a key value.

    ``key`` is either a field name string or a callable ``(context) -> value`` for
    cases where the selection depends on more than one field.  ``cases`` maps key
    values to the corresponding type (a ``BinaryPacket`` subclass or ``b_*`` type).
    If ``default`` is set it is used when no case matches; otherwise a missing key
    raises a construct ``MappingError``.
    """
    key:   str | Callable
    cases: dict[Any, Struct]
    default: Any = None

    def to_construct(self):
        key     = self.key
        key_f   = this[key] if isinstance(key, str) else key
        cases   = self.cases
        default = self.default

        def _subcon(annotation):
            if hasattr(annotation, '__construct__'):
                return annotation.__construct__
            meta = get_binary_meta(annotation)
            if meta is not None:
                return meta.to_construct()
            raise BinaryDefinitionError(f"Unsupported type in b_switch cases: {annotation!r}")

        construct_cases = {case: _subcon(element) for case, element in cases.items()}
        switch_kwargs   = {'default': _subcon(default)} if default is not None else {}
        switch_subcon   = Switch(key_f, construct_cases, **switch_kwargs)

        class SwitchAdapter(Adapter):
            def _decode(self, obj, context, path):
                key_value  = context[key] if isinstance(key, str) else key(context)
                annotation = cases.get(key_value, default)
                if annotation is not None and hasattr(annotation, '_from_container'):
                    return annotation._from_container(obj)
                return obj

            def _encode(self, obj, context, path):
                # _to_dict already converted any BinaryPacket to a dict
                return obj

        return SwitchAdapter(switch_subcon)

    @property
    def bit_width(self) -> None:
        return None  # case-dependent

    def description(self) -> str:
        return f"switch[{self.key}]" if isinstance(self.key, str) else "switch"


class b_switch:
    """ Factory for switch field annotations.

    Selects which sub-structure to parse/build based on the value of another field.
    Use ``b_switch[key, cases]`` or ``b_switch[key, cases, default]``.

    :param key:     A field name string, or a callable ``(context) -> value`` when
                    the selection depends on more than one field.
    :param cases:   A dict mapping key values to types (``BinaryPacket`` subclasses
                    or ``b_*`` annotations).
    :param default: Fallback type when no case matches.  If omitted, an unmatched
                    key raises a ``MappingError`` at parse/build time.
    """
    @classmethod
    def __class_getitem__(cls, args) -> Any:
        if not isinstance(args, tuple) or len(args) not in (2, 3):
            raise BinaryTypeError("Use b_switch[key, cases] or b_switch[key, cases, default]")

        key, cases, *remaining = args
        default = remaining[0] if remaining else None

        if not isinstance(key, (str, Callable)):
            raise BinaryDefinitionError("key must be a field name string or callable")
        if not isinstance(cases, dict):
            raise BinaryDefinitionError("cases must be a dict")

        # Build a Union of the case types (plus default) so static checkers can narrow on the result.
        case_types = tuple(cases.values())
        if default is not None:
            case_types = case_types + (default,)
        union = Union[case_types] if case_types else Any

        return Annotated[union, SwitchBinaryMeta(key, cases, default)]


def get_binary_meta(annotation: Any) -> IntegerBinaryMeta | BytesBinaryMeta | ArrayBinaryMeta | None:
    """ Extract binary metadata from an ``Annotated`` type hint.

    Scans the metadata arguments of an ``Annotated[T, ...]`` type and returns
    the first recognized binary metadata object, or ``None`` if the annotation
    carries no binary metadata.

    :param annotation: A type hint, typically produced by one of the ``b_*`` factories.
    :returns:          The binary metadata instance, or ``None``.
    """
    if get_origin(annotation) is Annotated:
        for arg in get_args(annotation)[1:]:
            if isinstance(arg, (IntegerBinaryMeta, BytesBinaryMeta, ArrayBinaryMeta, EnumBinaryMeta, FlagBinaryMeta,
                                GreedyBinaryMeta, SwitchBinaryMeta)):
                return arg
    return None


def _element_label(element: Any) -> str:
    """ Return a short type label for an array/greedy element (packet class or ``b_*`` annotation).
    """
    if hasattr(element, "__groups__"):
        return element.__name__
    meta = get_binary_meta(element)
    return meta.description() if meta else ""
