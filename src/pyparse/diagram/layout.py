""" Backend-agnostic layout of a :class:`BinaryPacket` into rows of drawable cells.
"""
from dataclasses import dataclass
from typing      import get_type_hints

from pyparse              import BinaryPacket
from pyparse.binary_types import get_binary_meta, IntegerBinaryMeta
from pyparse._builder     import BitFieldInfo


@dataclass
class Field:
    """ Logical field extracted from a packet definition, prior to row layout.

    :param name:  Field display name.
    :param width: Width in bits, or ``None`` for variable-width fields.
    :param style: Render style hint (``'normal'``, ``'bitfield'``, ``'nested'``, ``'variable'``).
    :param label: Type label shown as subtext (e.g. ``uint16``).
    :param fill:  Optional hex fill color used to tint nested fields.
    """
    name: str
    width: int | None
    style: str
    label: str
    fill: str = None


@dataclass
class Cell:
    """ One drawable cell after a :class:`Field` has been chopped to fit row width.

    :param name:         Cell label (prefixed with ``⬑`` for continuation cells).
    :param width:        Width in bits.
    :param style:        Render style hint inherited from the source field.
    :param label:        Type label shown as subtext.
    :param continuation: ``True`` if this cell continues a field from a previous row.
    :param fill:         Optional hex fill color.
    """
    name: str
    width: int
    style: str
    label: str
    continuation: bool
    fill: str = None


CELL_COLORS = [
    "#FFB3B3", "#FFCBA4", "#FFE5A0", "#D4F0A0", "#A8E6C8",  # rose,     peach,      butter,    lime,   mint
    "#A0D8EF", "#B3C8FF", "#D0B3FF", "#F0B3E8", "#FFB3D4",  # sky,      periwinkle, lavender,  orchid, blush
    "#FFDAB3", "#F5F0A0", "#B8F0B8", "#A0EDE0", "#A0C4FF",  # apricot,  lemon,      sage,      aqua,   cornflower
    "#E8C8FF", "#FFD0E8", "#D4E8C0", "#C0D8F0", "#F0E0B8",  # wisteria, flamingo,   pistachio, powder, vanilla
]


def _display_fields(packet_type: type[BinaryPacket],
                    expand_nested: bool = False,
                    _color_map: dict[str, str] = None,
                    _fill: str = None):
    """ Walk a packet's group list and produce a flat sequence of :class:`Field` objects.

    :param packet_type:   Packet class to flatten.
    :param expand_nested: If ``True``, recurse into nested packets and tint them with a stable color.
    :param _color_map:    Internal accumulator mapping nested packet names to fill colors (recursion only).
    :param _fill:         Internal fill color propagated to nested fields during recursion.
    :returns:             List of :class:`Field` in packet order.
    """
    if _color_map is None:
        _color_map = {}

    fields      = []
    annotations = get_type_hints(packet_type, include_extras=True)

    for group in packet_type.__groups__:

        if isinstance(group, BitFieldInfo):
            for field in group.fields:
                meta = get_binary_meta(field.annotation)
                # Suppress the type label on very narrow integer bit fields where it wouldn't fit visibly.
                if isinstance(meta, IntegerBinaryMeta) and field.bits < 4:
                    label = ""
                elif meta is not None:
                    label = meta.description()
                else:
                    label = f"uint{field.bits}"

                fields.append(Field(field.name.capitalize(),
                                    field.bits,
                                    'bitfield',
                                    label,
                                    fill=_fill))
            continue

        name       = group.name
        annotation = annotations[name]

        # Nested packets aren't tagged with a meta; treat them specially.
        if hasattr(annotation, "__groups__"):
            nested_width = annotation.__construct__.sizeof() * 8
            if expand_nested:
                nested_name = annotation.__name__
                if nested_name not in _color_map:
                    _color_map[nested_name] = CELL_COLORS[len(_color_map) % len(CELL_COLORS)]
                color = _color_map[nested_name]

                nested_fields = _display_fields(annotation,
                                                expand_nested=expand_nested,
                                                _color_map=_color_map,
                                                _fill=color)
                fields.extend(nested_fields)
            else:
                fields.append(Field(name.capitalize(), nested_width, 'nested', annotation.__name__, _fill))
            continue

        meta = get_binary_meta(annotation)
        if meta is None:
            continue

        width = meta.bit_width
        style = 'variable' if width is None else 'normal'
        fields.append(Field(name.capitalize(), width, style, meta.description(), _fill))

    return fields


def _layout_rows(fields: list[Field], row_bits: int = 32):
    """ Pack a flat field list into fixed-width rows, splitting fields that span row boundaries.

    :param fields:   Field sequence from :func:`_display_fields`.
    :param row_bits: Row width in bits (typically 32 for RFC-style diagrams).
    :returns:        List of rows, each a list of :class:`Cell` totalling ``row_bits``.
    """
    rows:     list[list[Cell]] = []
    current:  list[Cell]       = []
    position: int              = 0

    def flush(pad: bool = True):
        nonlocal position
        if pad and position < row_bits:
            current.append(Cell("", row_bits - position, "remaining", '', continuation=True))
        rows.append(list(current))
        current.clear()
        position = 0

    for field in fields:
        # Variable-width fields (width is None) consume only the rest of the current row.
        remaining = field.width if field.width else row_bits - position
        first     = True

        while remaining > 0:
            chunk = min(remaining, row_bits - position)
            label = field.name if first else f"⬑ {field.name}"
            current.append(Cell(label, chunk, field.style, field.label, continuation=not first, fill=field.fill))
            position += chunk
            remaining -= chunk
            first = False

            if position == row_bits:
                flush(pad=False)

    if current:
        flush()

    return rows