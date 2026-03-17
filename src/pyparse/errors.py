from construct import ConstructError, StreamError, IntegerError, RangeError


####################################################
# Binary meta type exceptions
####################################################
class ParsingError(Exception):
    """ Base class for all pyparse runtime exceptions.
    """


class BinaryTypeError(ParsingError):
    """ Raised when a binary type factory receives invalid argument types.
    """


class BinaryDefinitionError(ParsingError):
    """ Raised when a field definition contains invalid parameter values.
    """


class InvalidBinaryFieldType(ParsingError):
    """ Raised when a packet field annotation is neither a binary type nor a nested BinaryPacket.
    """


class FieldAlignmentError(ParsingError):
    """ Raised when a bit field group does not sum to a byte boundary under STRICT alignment.
    """


class PacketParseError(ParsingError):
    """ Raised when deserializing bytes into a packet fails.

    Wraps the underlying construct error with a human-readable field path and reason.
    """
    def __init__(self, packet_type, cause: ConstructError = None) -> None:
        self.packet_type = type(packet_type)
        self.field_path = _path_construct_exception_path(getattr(cause, 'path', None))
        self.cause = _make_reason_readable(cause)
        path_str = " -> ".join(self.field_path) if self.field_path else "<root>"
        super().__init__(
            f"Failed to parse {self.packet_type.__name__} at field '{path_str}': {self.cause}"
        )


class PacketBuildError(ParsingError):
    """ Raised when serializing a packet to bytes fails.

    Wraps the underlying construct error with a human-readable field path and reason.
    """

    def __init__(self, packet_type, cause: ConstructError = None) -> None:

        self.packet_type = type(packet_type)
        self.field_path = _path_construct_exception_path(getattr(cause, 'path', None))
        self.cause = _make_reason_readable(cause)
        path_str = " -> ".join(self.field_path) if self.field_path else "<root>"
        super().__init__(
            f"Failed to parse {self.packet_type.__name__} at field '{path_str}': {self.cause}"
        )


def _path_construct_exception_path(path: str | None) -> list[str]:
    """ Parses a construct exception path string into an ordered list of field names.

    :param path: Raw path string from a construct exception, e.g. ``"(parsing) -> header -> length"``.
    :returns:    Ordered field names, e.g. ``["header", "length"]``. Empty list if path is None.
    """

    # "(parsing) -> header -> b" > ["header", "b"]
    if not path:
        return []

    parts = path.split(" -> ")
    return parts[1:]


def _make_reason_readable(exc: ConstructError) -> str:
    """ Translates a raw construct exception into a human-readable reason string.

    This implementation is SUPER dependent on the message format of construct. I don't like this, but this is the only
    way...

    :param exc: The construct exception to translate.
    :returns:   A concise description of the failure cause.
    """
    message = str(exc)

    # Constructs formats it exceptions such that the real cause is always on the second line
    # "<ExceptionType>\n    <message>"
    cause   = message.split('\n', 1)[1].strip() if '\n' in message else message

    if isinstance(exc, StreamError):
        # Construct formats its StreamError as follows:
        # "stream read less than specified amount, expected 4, found 2"
        # We compare the 4 and the 2, non numerically...
        # (This is super brittle, I know)
        after_expected = cause.split("expected ", 1)[-1]  # "4, found 2"
        expected, found = after_expected.split(", found ")
        if found > expected:
            message = "too much data"
        else:
            message = "not enough data"

        return f"{message} (expected {expected} bytes, got {found})"
    if isinstance(exc, IntegerError):
        # Construct formats it IntegerError as follows:
        # "integer X does not fit into Y bytes, signed Z"
        # We find X, Y and Z by splitting...
        # (This is super brittle, I know)
        parts  = cause.split()
        if len(parts) < 8:
            return cause

        value  = parts[1]
        bits   = int(parts[6].rstrip(",")) * 8
        signed = "signed" if parts[8] == "True" else "unsigned"
        return f"value {value} overflows a {bits}-bit {signed} integer"
    if isinstance(exc, RangeError):
        # Construct formats it RangeError as follows:
        # expected X repetitions, found Y
        # We find X and Y by splitting
        # (This is super brittle, I know)
        parts = cause.split()
        return f"array length mismatch (expected {parts[1]}, got {parts[4]})"
    return cause
