# pyparse

A declarative binary packet parsing and serialization library for Python.

Define binary protocol structures using plain type annotations. pyparse compiles them into efficient serializers/deserializers at class-creation time, so you write a schema once and get both directions for free.

```python
from pyparse import BinaryPacket, b_uint8, b_uint16, b_array

class Frame(BinaryPacket):
    count:   b_uint8
    payload: b_array['count', b_uint8]

raw = Frame(count=3, payload=[10, 20, 30]).serialize()  # → bytes
frame = Frame.parse(raw)                                # → Frame(count=3, payload=[10, 20, 30])
```

---

## Quickstart

```python
from pyparse import BinaryPacket, b_uint8, b_uint16, b_bytes

class Header(BinaryPacket):
    version:  b_uint8
    msg_type: b_uint8
    length:   b_uint16

header = Header(version=1, msg_type=2, length=256)

raw     = header.serialize()          # pack to bytes
decoded = Header.parse(raw)           # unpack from bytes

assert decoded.version == 1
assert decoded.length  == 256
```

---

## Field Types

### Integers

| Type | Size | Notes |
|------|------|-------|
| `b_uint8` | 1 byte | unsigned |
| `b_int8` | 1 byte | signed |
| `b_uint16` | 2 bytes | unsigned |
| `b_int16` | 2 bytes | signed |
| `b_uint32` | 4 bytes | unsigned |
| `b_int32` | 4 bytes | signed |
| `b_uint64` | 8 bytes | unsigned |
| `b_int64` | 8 bytes | signed |
| `b_int[N]` | N bits | unsigned, arbitrary bit width |
| `b_int[N, True]` | N bits | signed, arbitrary bit width |

Use the `b_int[N]` factory for any bit width, including sub-byte fields:

```python
class Flags(BinaryPacket):
    priority: b_int[3]   # 3 bits
    reserved: b_int[1]   # 1 bit
    type_id:  b_int[4]   # 4 bits
    # Total: 8 bits → packed into one byte automatically
```

Consecutive sub-byte fields are automatically packed together into a `BitStruct`. The total must be byte-aligned (by default the class raises an error if it is not — see [Alignment Policy](#alignment-policy)).

### Raw Bytes

```python
from pyparse import BinaryPacket, b_bytes

class Packet(BinaryPacket):
    magic:    b_bytes[4]   # exactly 4 bytes
    checksum: b_bytes[2]   # exactly 2 bytes
```

There is also a pre-defined `b_byte` alias for a single byte field.

### Arrays

```python
from pyparse import BinaryPacket, b_array, b_uint8, b_uint16

# Fixed-length array
class Fixed(BinaryPacket):
    data: b_array[8, b_uint8]   # always 8 elements

# Dynamic-length array (size taken from another field)
class Dynamic(BinaryPacket):
    count:   b_uint16
    payload: b_array['count', b_uint8]  # 'count' refers to the field above
```

Use `b_greedy` to consume all remaining bytes as an array:

```python
from pyparse import BinaryPacket, b_greedy, b_uint8

class Stream(BinaryPacket):
    header: b_uint8
    rest:   b_greedy[b_uint8]   # reads until end of data
```

### Enums and Flags

```python
from enum import IntEnum, IntFlag
from pyparse import BinaryPacket, b_enum, b_flag

class Color(IntEnum):
    RED   = 0
    GREEN = 1
    BLUE  = 2

class Permission(IntFlag):
    READ    = 1
    WRITE   = 2
    EXECUTE = 4

class Packet(BinaryPacket):
    color: b_enum[8, Color, False]         # 8-bit unsigned enum
    perms: b_flag[8, Permission, False]    # 8-bit unsigned flag
```

### Nested Packets

Any `BinaryPacket` subclass can be used as a field type:

```python
from pyparse import BinaryPacket, b_uint8, b_uint16, b_array

class Header(BinaryPacket):
    version: b_uint8
    length:  b_uint16

class Message(BinaryPacket):
    header:  Header              # nested packet
    payload: b_array['header.length', b_uint8]
```

---

## Serialization and Parsing

```python
# Serialize an instance to bytes
raw: bytes = my_packet.serialize()

# Parse bytes back into an instance
my_packet = MyPacket.parse(raw)
```

Both methods raise descriptive errors on failure:

- `PacketParseError` — raised by `.parse()`, includes the field path and reason (e.g. "not enough data (expected 4 bytes, got 2)")
- `PacketBuildError` — raised by `.serialize()`, includes the field path and reason (e.g. "value 300 overflows a 8-bit unsigned integer")

---

## Alignment Policy

When sub-byte fields are used, their total bit count inside a consecutive group must be a multiple of 8. The default policy is `STRICT`, which raises a `FieldAlignmentError` at class-creation time if this rule is violated.

```python
from pyparse import BinaryPacket, AlignmentPolicy, b_int

# STRICT (default): misaligned groups raise FieldAlignmentError
class GoodPacket(BinaryPacket):
    a: b_int[6]
    b: b_int[2]   # 6 + 2 = 8 ✓

# Pass policy= to change the behavior (PAD/IGNORE are planned but not yet implemented)
class StrictPacket(BinaryPacket, policy=AlignmentPolicy.STRICT):
    ...
```

---

## Architecture Overview

```
BinaryPacket subclass definition
    └─ __init_subclass__ hook fires at class-creation time
        ├─ Extracts type annotations
        ├─ Groups consecutive sub-byte fields into BitStructs
        ├─ Compiles the full schema to a construct.Struct
        └─ Wraps the class as a keyword-only dataclass

instance.serialize()
    └─ _to_dict() flattens nested objects → construct.Struct.build() → bytes

MyPacket.parse(raw)
    └─ construct.Struct.parse(raw) → Container → _from_container() → instance
```

pyparse is built on top of the [`construct`](https://github.com/construct/construct) library, which handles the low-level binary I/O. The declarative API removes all boilerplate.