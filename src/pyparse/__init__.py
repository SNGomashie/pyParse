
from pyparse.binary_types import IntegerBinaryType


b_int    = IntegerBinaryType
b_uint8  = IntegerBinaryType[8, False]
b_int8   = IntegerBinaryType[8, True]
b_uint16 = IntegerBinaryType[16, False]
b_int16  = IntegerBinaryType[16, True]
b_uint32 = IntegerBinaryType[32, False]
b_int32  = IntegerBinaryType[32, True]
b_uint64 = IntegerBinaryType[64, False]
b_int64  = IntegerBinaryType[64, True]
