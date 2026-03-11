from pyparse.base         import BinaryPacket
from pyparse.binary_types import IntegerBinaryType, BytesBinaryType, ArrayBinaryType


b_int: type[IntegerBinaryType] = IntegerBinaryType
b_uint8: type[int]   = IntegerBinaryType[8, False]
b_int8: type[int]    = IntegerBinaryType[8, True]
b_uint16: type[int]  = IntegerBinaryType[16, False]
b_int16: type[int]   = IntegerBinaryType[16, True]
b_uint32: type[int]  = IntegerBinaryType[32, False]
b_int32: type[int]   = IntegerBinaryType[32, True]
b_uint64: type[int]  = IntegerBinaryType[64, False]
b_int64: type[int]   = IntegerBinaryType[64, True]
b_bytes: type[BytesBinaryType] = BytesBinaryType
b_array: type[ArrayBinaryType] = ArrayBinaryType
