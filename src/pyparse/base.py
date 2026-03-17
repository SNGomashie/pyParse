import dataclasses

from typing import dataclass_transform, get_type_hints

from construct import ListContainer, Container, ConstructError

from pyparse.binary_types import get_binary_meta, ArrayBinaryMeta
from pyparse.errors import PacketBuildError, PacketParseError
from pyparse._builder import AlignmentPolicy, build_construct, BitFieldInfo


@dataclass_transform(kw_only_default=True)
class BinaryPacket:
    """ Base class for declarative binary packet definitions.

          Subclass ``BinaryPacket`` and annotate fields using the provided ``b_*`` binary types.
          At class-creation time the annotations are compiled into an internal construct
          ``Struct``, and the class is wrapped as a keyword-only dataclass — no ``__init__``
          boilerplate required.

          Supported field types:

          - Integers: ``b_int[bits, signed]``, ``b_uint8``, ``b_int16``
          - Bytes: ``b_bytes[n]`` — fixed-width raw bytes
          - Arrays: ``b_array[count, element]``
          - Nested ``BinaryPacket`` subclasses

          Consecutive sub-byte fields (e.g. ``b_int[6]``) are automatically packed into a
          ``BitStruct``. The alignment policy can be configured per-class via the ``policy``
          keyword argument.

          Example::

              from pyparse import BinaryPacket, b_uint8, b_uint16, b_bytes, b_array

              class Frame(BinaryPacket):
                  count:   b_uint8
                  payload: b_array['count', b_uint8]

              frame   = Frame(count=3, payload=[0, 1, 2])
              raw     = frame.serialize()         # bytes
              p_frame = Frame.parse(raw)          # Frame instance
          """
    def __init_subclass__(cls, policy: AlignmentPolicy = AlignmentPolicy.STRICT, **kwargs):
        """ Process field annotations at class-creation time.

        Builds the internal ``construct`` Struct, groups fields, and wraps the class as a keyword-only dataclass.

        :param policy: Alignment policy applied to bit field groups. Defaults to :attr:`AlignmentPolicy.STRICT`.
        """
        super().__init_subclass__(**kwargs)
        annotations = get_type_hints(cls, include_extras=True)
        cls.__construct__, cls.__groups__ = build_construct(annotations, policy)
        dataclasses.dataclass(cls, kw_only=True)

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

            if isinstance(value, list):
                for index, sub_field in enumerate(value):
                    if isinstance(sub_field, BinaryPacket):
                        value[index] = sub_field._to_dict()

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
        try:
            return self.__construct__.build(self._to_dict())
        except ConstructError as e:
            raise PacketBuildError(self, e) from e

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
            annotation = get_type_hints(cls, include_extras=True).get(group.name)

            # Process array
            if isinstance(get_binary_meta(annotation), ArrayBinaryMeta):
                if isinstance(container[group.name], ListContainer):
                    kwargs[group.name] = cls._parse_list_container(value, annotation)
                continue

            # if the associated annotation is a binary packet, recursively convert the associated container.
            if hasattr(annotation, '__construct__'):
                kwargs[group.name] = annotation._from_container(value)
            else:
                kwargs[group.name] = value

        return cls(**kwargs)

    @staticmethod
    def _parse_list_container(field_list: ListContainer, annotation):
        """ Convert a ListContainer produced by construct into a plain Python list.

        :param field_list: The ``ListContainer`` from a parsed construct result.
        :param annotation: The ``Annotated`` array field type.
        :returns:          A list of element values.
        """

        element = get_binary_meta(annotation).element
        parsed_fields = []

        for field in field_list:
            if isinstance(field, Container):
                field = element._from_container(field)
            parsed_fields.append(field)

        return parsed_fields

    @classmethod
    def parse(cls, data: bytes) -> "BinaryPacket":
        """ Deserializes raw bytes into a packet instance.

        :param data: Raw bytes to parse.
        :returns:    A fully populated instance of ``cls``.
        """
        try:
            parsed = cls.__construct__.parse(data)
        except ConstructError as e:
            raise PacketParseError(cls, e) from e
        return cls._from_container(parsed)
