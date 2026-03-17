
from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated

from construct import BitStruct, Construct, Struct

from pyparse.binary_types import get_binary_meta
from pyparse.errors import FieldAlignmentError, InvalidBinaryFieldType


class AlignmentPolicy(StrEnum):
    """ Enumeration of the alignment policies.
    """
    STRICT = "strict"
    PAD    = "pad"
    IGNORE = "ignore"


@dataclass
class FieldInfo:
    """ Represents metadata for a single field within a ``BinaryPacket``.

    Stores the field name and its associated type annotation, which must be
    either an ``Annotated`` binary type or a nested ``BinaryPacket`` subclass.
    Instantiation will fail if neither condition is met.

    :param name:       The field's attribute name as declared in the packet.
    :param annotation: The field's type.

    :raises InvalidBinaryFieldType: If ``annotation`` carries no binary metadata
                                    and has no ``__construct__`` attribute.
    """

    name:       str
    annotation: "type[BinaryPacket]"

    def __post_init__(self) -> None:
        """ Check whether the annotation field is either a binary type, or a binary packet.
        """
        is_binary_type  = get_binary_meta(self.annotation)
        is_binary_packet = hasattr(self.annotation, '__construct__')
        if not is_binary_type and not is_binary_packet:
            raise InvalidBinaryFieldType("Invalid binary field type provided. Must be either a nested binary type, "
                                         "or a provided binary type")

    @property
    def is_nested(self) -> bool:
        """ Returns whether the field is a nested ``BinaryPacket`` type.

        :returns: ``True`` if a nested packet, ``False`` otherwise.
        """
        return hasattr(self.annotation, '__construct__')

    @property
    def is_bit_field(self) -> bool:
        """ Returns whether the field is a bit field type.

        :returns: ``True`` if a bit field type, ``False`` otherwise.
        """
        return not self.is_nested and self.bits % 8 != 0

    @property
    def bits(self) -> int:
        """ Returns the number of bits of the type in the bit field.

        :returns: number of bits of the type in the bit field.
        """

        return getattr(get_binary_meta(self.annotation), 'bits', 8)


@dataclass
class BitFieldInfo:
    """Groups a collection of bit fields that collectively occupy a byte alligned space.

    A ``BitFieldInfo`` aggregates multiple :class:`FieldInfo` entries whose
    total bit width is expected to sum to a byte-aligned boundary. It serves
    as an intermediate representation used during packet construction to
    handle fields that do not individually align to byte boundaries.

    :param name:   Identifier for the bit field group.
    :param fields: Ordered list of :class:`FieldInfo` entries comprising the group.
    """
    name:   str
    fields: list[FieldInfo]


def apply_alignment(buffer: list[FieldInfo], buf_bits: int, policy: AlignmentPolicy) -> list[FieldInfo]:
    """ Enforces byte-alignment on a buffered bit field group per the given policy.

    :param buffer:   Accumulated bit fields pending flush.
    :param buf_bits: Total bit width of ``buffer``.
    :param policy:   Alignment policy to apply.
    :returns:        The (possibly padded) field list, if policy permits continuation.

    :raises FieldAlignmentError: Under :attr:`AlignmentPolicy.STRICT` if the group is not byte-aligned.
    :raises NotImplementedError: Under :attr:`AlignmentPolicy.PAD` and :attr:`AlignmentPolicy.IGNORE` until
                                     implemented.
    """
    remaining_bits = buf_bits % 8

    if remaining_bits == 0:
        return buffer

    match policy:
        case AlignmentPolicy.STRICT:
            raise FieldAlignmentError(f"Field(s) {[field.name for field in buffer]} sum to {buf_bits} bits, "
                                      f"not byte-aligned. Fields must be byte aligned.")
        case AlignmentPolicy.PAD:
            # TODO: Pad bit group until byte-aligned
            raise NotImplementedError
        case AlignmentPolicy.IGNORE:
            # TODO: Simply ignore, but give some warning??
            raise NotImplementedError


def group_fields(fields: list[FieldInfo], policy: AlignmentPolicy = AlignmentPolicy.STRICT) -> list[FieldInfo]:
    """ Partitions a flat field list into byte-aligned groups.

    Byte-aligned fields and nested packets are emitted as bare :class:`FieldInfo` entries.
    Consecutive bit fields are accumulated and flushed into a :class:`BitFieldInfo`
    once their combined width reaches a byte boundary, or at the end of the field list.
    Alignment of incomplete groups is delegated to :meth:`apply_alignment`.

    :param fields: Ordered list of :class:`FieldInfo` entries to partition.
    :param policy: Determines behavior when a bit group is not byte-aligned on flush.
    :returns:      Ordered list of :class:`FieldInfo` and :class:`BitFieldInfo` groups.
    """
    groups = []
    buffer = []
    bit_count = 0

    def flush():
        """ Flush the bit buffer, create a BitFieldInfo object and append it to the group.
        """
        nonlocal bit_count
        if not buffer:
            return

        name = "_".join(field.name for field in buffer)
        buffer[:] = apply_alignment(buffer, bit_count, policy)
        groups.append(BitFieldInfo(name=name, fields=list(buffer)))
        buffer.clear()
        bit_count = 0

    for field in fields:
        if field.is_nested or not field.is_bit_field:
            flush()
            groups.append(field)
        else:
            buffer.append(field)
            bit_count += field.bits
            if bit_count % 8 == 0:
                flush()

    flush()
    return groups


def field_to_subcon(field: FieldInfo) -> Construct:
    """ Maps a single :class:`FieldInfo` to a named ``construct`` subcon.

    Nested ``BinaryPacket`` fields delegate to the nested class's own ``__construct__``.
    Primitive fields delegate to their type's ``to_construct()`` method.

    :param field: The field to convert.
    :returns:     A renamed ``construct`` subcon.
    """
    if field.is_nested:
        return field.name / field.annotation.__construct__
    return field.name / get_binary_meta(field.annotation).to_construct()


def group_to_subcon(group: FieldInfo | BitFieldInfo) -> Construct:
    """ Maps a group to its ``construct`` subcon.

    Bit field groups are wrapped in a ``BitStruct``; all others are forwarded
    to :meth:`field_to_subcon`.

    :param group: A :class:`FieldInfo` or :class:`BitFieldInfo` to convert.
    :returns:     A named ``construct`` subcon.
    """
    if not isinstance(group, BitFieldInfo) and not group.is_bit_field:
        return field_to_subcon(group)
    return group.name / BitStruct(*[field_to_subcon(field) for field in group.fields])


def build_construct(annotations: dict, policy: AlignmentPolicy = AlignmentPolicy.STRICT) \
        -> tuple[Struct, list[FieldInfo]]:
    """ Build a ``construct`` Struct and ordered group list from a packet's resolved annotations.

    :param annotations: Full type hint dict from ``get_type_hints(cls, include_extras=True)``.
    :param policy:      Bit field alignment policy.
    :returns:           Tuple of the compiled ``Struct`` and the ordered list of field groups.
    """
    fields = [FieldInfo(name, annotation) for name, annotation in annotations.items()]
    groups = group_fields(fields, policy)
    return Struct(*[group_to_subcon(group) for group in groups]), groups
