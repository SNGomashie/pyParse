"""
"""
import dataclasses

from typing import dataclass_transform

from construct import Construct, Struct

from pyparse.binary_types import AbstractBinaryType
from pyparse.errors import InvalidBinaryFieldType


@dataclasses.dataclass
class FieldInfo:
    """
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


@dataclass_transform()
class PacketMeta(type):
    """ Metaclass that automatically converts created classes into keyword-only dataclasses.
    
    :param cls:       The metaclass itself.
    :param name:      Name of the class being created.
    :param bases:     Base classes of the new class.
    :param namespace: Attribute dictionary defining the class body.
    :returns:         A new class object decorated as a keyword-only dataclass.
    """
    def __new__(cls, name: str, bases, namespace):        
        # Create raw class object without modifications
        raw = super().__new__(cls, name, bases, namespace)

        annotations: dict[str, AbstractBinaryType | BinaryPacket] = {}
        for base in reversed(cls.__mro__):
            annotations.update(getattr(base, "__annotations__", {}))

        annotations.update(namespace.get('__annotations__', {}))

        raw.__construct__ = cls._build_construct(annotations).compile()

        # Turn it into a keyword only dataclass.
        return dataclasses.dataclass(raw, kw_only=True)

    @staticmethod
    def _is_binary_packet(annotation) -> bool:
        """ Returns whether an annotation is a binary packet.
        """
        return isinstance(annotation, type) and issubclass(annotation, BinaryPacket)

    @staticmethod
    def _build_construct(annotations: dict):
        """ Returns a struct based on the fields of the dataclass.
        """
        fields  = [FieldInfo(name, anno) for name, anno in annotations.items()]
        subcons = [PacketMeta._field_to_subcon(field) for field in fields]
        return Struct(*subcons)

    @staticmethod
    def _field_to_subcon(field: FieldInfo) -> Construct:
        """ Returns a renamed struct associated with the field type.
        """
        if field.is_nested:
            return field.name / field.annotation.__construct__
        return field.name / field.annotation.to_construct()


class BinaryPacket(metaclass=PacketMeta):
    def _to_dict(self) -> dict:
        """ Converts the binary packet to a dictionary.

        Recursively traverse the binary packet structure and convert any nested dicts to a dictionary.

        :returns: Dictionary of binary packet data fields.
        """
        result = {}
        for field in dataclasses.fields(self):
            value = getattr(self, field.name)

            # If the value is another BinaryPacket, recursively generate the dict for this binary packet.
            if isinstance(value, BinaryPacket):
                result[field.name] = value._to_dict()
            else:
                result[field.name] = value
        return result
    
    def serialize(self) -> bytes:
        """ Serializes the binary packet into a bytes object.

        :returns: Bytes object representing the binary packet.
        """
        return self.__construct__.build(self._to_dict())

    @classmethod
    def _from_container(cls, container) -> "BinaryPacket":
        """ Converts a construct container into a binary packet object.
        """
        kwargs = {}
        for field in dataclasses.fields(cls):
            value = container.get(field.name)
            annotation = cls.__annotations__.get(field.name)

            # if the associated annotation is a binary packet, recursively convert the associated container.
            if PacketMeta._is_binary_packet(annotation):
                kwargs[field.name] = annotation._from_container(value)
            else:
                kwargs[field.name] = value

        return cls(**kwargs)
    
    @classmethod
    def parse(cls, data: bytes) -> "BinaryPacket":
        """ Parses a bytes object into a binary packet object.
        """
        parsed = cls.__construct__.parse(data)
        return cls._from_container(parsed)
