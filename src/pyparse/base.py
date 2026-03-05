import dataclasses

from enum import StrEnum
from typing import dataclass_transform

from construct import Construct, BitStruct, Struct

from pyparse.binary_types import AbstractBinaryType
from pyparse.errors import InvalidBinaryFieldType, FieldAlignmentError


class AlignmentPolicy(StrEnum):
    """ Enumeration of the alignment policies.
    """
    STRICT = "strict"
    PAD    = "pad"
    IGNORE = "ignore"


@dataclasses.dataclass
class FieldInfo:
    """ Represents metadata for a single field within a ``BinaryPacket``.

    Stores the field name and its associated type annotation, which must be
    either a concrete ``AbstractBinaryType`` subclass or a nested ``BinaryPacket``
    subclass. Instantiation will fail if neither condition is met.

    :param name:       The field's attribute name as declared in the packet.
    :param annotation: The field's type, must be a subclass of either ``AbstractBinaryType`` or ``BinaryPacket``.

    :raises InvalidBinaryFieldType: If ``annotation`` is neither a subclass of ``AbstractBinaryType`` nor
                                    ``BinaryPacket``.
    """
    name:       str
    annotation: "type[AbstractBinaryType | BinaryPacket]"

    def __post_init__(cls) -> None:
        """ Check whether the annotation field is either a binary type, or a binary packet.
        """
        if not issubclass(cls.annotation, AbstractBinaryType) and not issubclass(cls.annotation, BinaryPacket):
            raise InvalidBinaryFieldType("Invalid binary field type provided. Must be either a nested binary type, "
                                         "or a provided binary type")

    @property
    def is_nested(self) -> bool:
        """ Returns whether the field is a nested ``BinaryPacket`` type.
        
        :returns: ``True`` if a nested packet, ``False`` otherwise.
        """
        return isinstance(self.annotation, type) and issubclass(self.annotation, BinaryPacket)

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
        return self.annotation.__meta__['bits']


@dataclasses.dataclass
class BitFieldInfo:
    """Groups a collection of bit fields that collectively occupy a byte alligned space.

    A ``BitFieldInfo`` aggregates multiple :class:`FieldInfo` entries whose
    total bit width is expected to sum to a byte-aligned boundary. It serves
    as an intermediate representation used during packet construction to
    handle fields that do not individually align to byte boundaries.

    :param name:   Identifier for the bit field group.
    :param fields: Ordered list of :class:`FieldInfo` entries comprising the group.
    """
    name:  str
    fields: list[FieldInfo]


@dataclass_transform()
class PacketMeta(type):
    """Metaclass that transforms user-defined packet classes into structured binary descriptors.

    On class creation, resolves all field annotations across the MRO, groups them
    into byte-aligned constructs (or bit-grouped constructs where applicable), and
    attaches a ``construct`` ``Struct`` and a ``__groups__`` list to the class.
    All produced classes are wrapped as keyword-only dataclasses.

    :param name:      Name of the class being created.
    :param bases:     Base classes of the new class.
    :param namespace: Attribute dictionary of the class body.
    :param policy:    Alignment policy applied to bit fields that do not sum to a
                      byte boundary. Defaults to :attr:`AlignmentPolicy.STRICT`.
    :returns:         A keyword-only dataclass with ``__construct__`` and ``__groups__`` attached.
    """
    def __new__(cls, name: str, bases, namespace, policy=AlignmentPolicy.STRICT):
        # Create raw class object without modifications
        raw = super().__new__(cls, name, bases, namespace)

        annotations: dict[str, AbstractBinaryType | BinaryPacket] = {}
        for base in reversed(raw.__mro__):
            annotations.update(getattr(base, "__annotations__", {}))

        annotations.update(namespace.get('__annotations__', {}))

        raw.__construct__, raw.__groups__ = cls._build_construct(annotations, policy)
        # Turn it into a keyword only dataclass.
        return dataclasses.dataclass(raw, kw_only=True)

    @staticmethod
    def _is_binary_packet(annotation) -> bool:
        """ Returns whether an annotation is a subclass of ``BinaryPacket``.

        :param annotation: The annotation to check.
        :returns: ``True`` if ``annotation`` is a ``BinaryPacket`` subclass, ``False`` otherwise.
        """
        return isinstance(annotation, type) and issubclass(annotation, BinaryPacket)

    @staticmethod
    def _build_construct(annotations: dict, policy: AlignmentPolicy = AlignmentPolicy.STRICT):
        """ Builds a ``Struct`` and grouped field list from a resolved annotation mapping.

        Instantiates a :class:`FieldInfo` for each annotation, groups them via
        :meth:`_group_fields`, then maps each group to its corresponding ``construct``
        subcon.

        :param annotations: Fully resolved annotation dict, including inherited fields.
        :param policy:      Alignment policy forwarded to :meth:`_group_fields`.
        :returns:           A tuple of ``(Struct, list[FieldInfo | BitFieldInfo])``.
        """
        fields  = [FieldInfo(name, anno) for name, anno in annotations.items()]
        groups  = PacketMeta._group_fields(fields, policy)
        return Struct(*[PacketMeta._group_to_subcon(group) for group in groups]), groups

    @staticmethod
    def _group_fields(fields: list[FieldInfo],
                      policy: AlignmentPolicy = AlignmentPolicy.STRICT) -> list[list[FieldInfo]]:
        """ Partitions a flat field list into byte-aligned groups.

        Byte-aligned fields and nested packets are emitted as bare :class:`FieldInfo` entries.
        Consecutive bit fields are accumulated and flushed into a :class:`BitFieldInfo`
        once their combined width reaches a byte boundary, or at the end of the field list.
        Alignment of incomplete groups is delegated to :meth:`_apply_alignment`.

        :param fields: Ordered list of :class:`FieldInfo` entries to partition.
        :param policy: Determines behavior when a bit group is not byte-aligned on flush.
        :returns:      Ordered list of :class:`FieldInfo` and :class:`BitFieldInfo` groups.
        """
        groups    = []
        buffer    = []
        bit_count = 0

        def flush():
            nonlocal bit_count
            if not buffer:
                return

            name = "_".join(field.name for field in buffer)
            buffer[:] = PacketMeta._apply_alignment(buffer, bit_count, policy)
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

    @staticmethod
    def _apply_alignment(buffer: list[FieldInfo], buf_bits: int, policy: AlignmentPolicy) -> list[FieldInfo]:
        """Enforces byte-alignment on a buffered bit field group per the given policy.

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

    @staticmethod
    def _field_to_subcon(field: FieldInfo) -> Construct:
        """ Maps a single :class:`FieldInfo` to a named ``construct`` subcon.

        Nested ``BinaryPacket`` fields delegate to the nested class's own ``__construct__``.
        Primitive fields delegate to their type's ``to_construct()`` method.

        :param field: The field to convert.
        :returns:     A renamed ``construct`` subcon.
        """
        if field.is_nested:
            return field.name / field.annotation.__construct__
        return field.name / field.annotation.to_construct()

    @staticmethod
    def _group_to_subcon(group: FieldInfo | BitFieldInfo) -> Construct:
        """ Maps a group to its ``construct`` subcon.

        Bit field groups are wrapped in a ``BitStruct``; all others are forwarded
        to :meth:`_field_to_subcon`.

        :param group: A :class:`FieldInfo` or :class:`BitFieldInfo` to convert.
        :returns:     A named ``construct`` subcon.
        """
        if not isinstance(group, BitFieldInfo) and not group.is_bit_field:
            return PacketMeta._field_to_subcon(group)

        return group.name / BitStruct(*[PacketMeta._field_to_subcon(field) for field in group.fields])


class BinaryPacket(metaclass=PacketMeta):
    """ Base class for all binary packet definitions.

    Subclasses declare fields as class-level annotations with types derived from
    ``AbstractBinaryType`` or nested ``BinaryPacket`` subclasses. The metaclass
    :class:`PacketMeta` handles struct construction, grouping, and dataclass wrapping
    at class-creation time, so subclasses require no boilerplate beyond their annotations.

    Example::

        class MyPacket(BinaryPacket):
            field_a: UInt8
            field_b: UInt16

        packet = MyPacket(field_a=1, field_b=256)
        raw = pkt.serialize()
        restored_packet = MyPacket.parse(raw)
    """
    def _to_dict(self) -> dict:
        """Recursively converts the packet's fields into a plain dictionary.

        Bit field groups are nested under a sub-dictionary keyed by the group name.
        Nested ``BinaryPacket`` instances are recursed into. Intended for internal
        use as input to ``construct``'s ``build()``.

        :returns: Dictionary representation of the packet suitable for serialization.
        """
        result = {}

        for group in self.__groups__:
            if isinstance(group, BitFieldInfo):
                bit_group = {}
                for bit_field in group.fields:
                    bit_group[bit_field.name] = getattr(self, bit_field.name)
                result[group.name] = bit_group
                continue

            value = getattr(self, group.name)

            # If the value is another BinaryPacket, recursively generate the dict for this binary packet.
            if isinstance(value, BinaryPacket):
                result[group.name] = value._to_dict()
            else:
                result[group.name] = value
        return result
    
    def serialize(self) -> bytes:
        """ Serializes the packet to its binary byte representation.

        :returns: Raw bytes encoding of the packet.
        """
        return self.__construct__.build(self._to_dict())

    @classmethod
    def _from_container(cls, container) -> "BinaryPacket":
        """ Reconstructs a packet instance from a ``construct`` parsed container.

        Bit field values are extracted from their sub-container and mapped back to
        flat kwargs. Nested ``BinaryPacket`` fields are recursively reconstructed.

        :param container: A ``construct`` ``Container`` produced by parsing.
        :returns:         A fully populated instance of ``cls``.
        """
        kwargs = {}
        for group in cls.__groups__:
            if isinstance(group, BitFieldInfo):
                for bitfield in group.fields:
                    kwargs[bitfield.name] = container.get(group.name).get(bitfield.name)
                continue

            value = container.get(group.name)
            annotation = cls.__annotations__.get(group.name)

            # if the associated annotation is a binary packet, recursively convert the associated container.
            if PacketMeta._is_binary_packet(annotation):
                kwargs[group.name] = annotation._from_container(value)
            else:
                kwargs[group.name] = value

        return cls(**kwargs)

    @classmethod
    def parse(cls, data: bytes) -> "BinaryPacket":
        """ Deserializes raw bytes into a packet instance.

        :param data: Raw bytes to parse.
        :returns:    A fully populated instance of ``cls``.
        """
        parsed = cls.__construct__.parse(data)
        return cls._from_container(parsed)
