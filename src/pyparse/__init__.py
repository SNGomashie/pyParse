from typing import Annotated, TypeAlias

from pyparse.base         import BinaryPacket
from pyparse.binary_types import (b_array, b_bytes, b_enum, b_flag, b_greedy, b_int, BytesBinaryMeta, IntegerBinaryMeta,
                                  b_switch)
from pyparse._builder     import AlignmentPolicy


b_uint8:  TypeAlias = Annotated[int, IntegerBinaryMeta(8, False)]
b_int8:   TypeAlias = Annotated[int, IntegerBinaryMeta(8, True)]
b_uint16: TypeAlias = Annotated[int, IntegerBinaryMeta(16, False)]
b_int16:  TypeAlias = Annotated[int, IntegerBinaryMeta(16, True)]
b_uint32: TypeAlias = Annotated[int, IntegerBinaryMeta(32, False)]
b_int32:  TypeAlias = Annotated[int, IntegerBinaryMeta(32, True)]
b_uint64: TypeAlias = Annotated[int, IntegerBinaryMeta(64, False)]
b_int64:  TypeAlias = Annotated[int, IntegerBinaryMeta(64, True)]

b_byte:   TypeAlias = Annotated[bytes, BytesBinaryMeta(1)]
