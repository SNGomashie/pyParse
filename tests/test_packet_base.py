import pytest

from construct import BytesInteger, Struct

from pyparse        import b_uint8, b_uint16
from pyparse.base   import FieldInfo, PacketMeta, BinaryPacket
from pyparse.errors import InvalidBinaryFieldType


def test_field_info_is_not_nested():
    info = FieldInfo('test', b_uint8)
    assert not info.is_nested


def test_field_info_is_not_nested():
    class TestPacket(BinaryPacket):
        a: b_uint16
    
    info = FieldInfo('test', TestPacket)
    assert info.is_nested


def test_packet_meta_build_construct():
    PacketMeta._build_construct({'field0': b_uint8,
                                 'field1': b_uint16})


def test_packet_metaclass_field_to_subcon():
    field = FieldInfo('field0', b_uint8)
    
    struct = PacketMeta._field_to_subcon(field)
    assert struct.name is 'field0'
    assert struct.sizeof() == 1


def test_packet_metaclass_build_construct():
    annotations = {'field0': b_uint8,
                   'field1': b_uint16}
    
    struct = PacketMeta._build_construct(annotations)
    
    assert struct.subcons[0].name == 'field0'
    assert struct.subcons[0].sizeof() == 1
    assert struct.subcons[1].name == 'field1'
    assert struct.subcons[1].sizeof() == 2
    
    assert struct.sizeof() == 3


def test_packet_metaclass_is_not_binary_packet():
    annotation = b_uint16
    
    assert PacketMeta._is_binary_packet(annotation) is False


def test_packet_metaclass_is_binary_packet():
    class TestPacket(BinaryPacket):
        a: b_uint8
    
    assert PacketMeta._is_binary_packet(TestPacket) is True


def test_binary_packet_invalid_type():
    with pytest.raises(InvalidBinaryFieldType):
        class TestPacket(BinaryPacket):
            a: int


def test_binary_packet_to_dict_not_nested():
    class TestPacket(BinaryPacket):
        a: b_uint8
        
    packet_dict = TestPacket(a=10)._to_dict()
    assert 'a' in packet_dict
    assert packet_dict['a'] == 10


def test_binary_packet_to_dict_nested():
    class Nested(BinaryPacket):
        a: b_uint8
        
    class TestPacket(BinaryPacket):
        a: Nested
    
    packet_dict = TestPacket(a=Nested(a=10))._to_dict()
    assert 'a' in packet_dict
    assert packet_dict['a'] == {'a': 10}


def test_binary_packet_serialize_not_nested():
    class TestPacket(BinaryPacket):
        a: b_uint8   
    
    packet = TestPacket(a=10)
    b_packet = packet.serialize()
    
    assert b_packet == b'\x0A'


def test_binary_packet_serialize_nested():
    class Nested(BinaryPacket):
        a: b_uint8
    
    class TestPacket(BinaryPacket):
        a: Nested  
    
    packet = TestPacket(a=Nested(a=10))
    b_packet = packet.serialize()
    
    assert b_packet == b'\x0A'


def test_binary_packet_from_container_not_nested():
    class TestPacket(BinaryPacket):
        a: b_uint8
    
    struct = Struct('a' / BytesInteger(1, False))
    parsed = struct.parse(b'\x0A')
    
    packet = TestPacket._from_container(parsed)
    assert packet.a == 10


def test_binary_packet_from_container_nested():
    class Nested(BinaryPacket):
        a: b_uint8
    
    class TestPacket(BinaryPacket):
        a: Nested
    
    struct = Struct('a' / Struct('a' / BytesInteger(1, False)))
    parsed = struct.parse(b'\x0A')
    
    packet = TestPacket._from_container(parsed)
    assert packet.a.a == 10


def test_binary_packet_parse_not_nested():
    class TestPacket(BinaryPacket):
        a: b_uint16
        
    packet = TestPacket.parse(b'\x0A')
    assert packet.a == 10
