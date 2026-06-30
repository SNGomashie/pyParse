""" Render a :class:`BinaryPacket` as an RFC-style bit/byte row diagram on a Visio page.
"""
from pyparse import BinaryPacket
from pyparse.diagram.layout import _display_fields, _layout_rows
from pyparse.diagram.visio  import VisioContext

_PAGE_WIDTH = 210  # mm
_PAGE_HEIGHT = 297  # mm
_DIAGRAM_X_MARGIN = 20  # mm
_DIAGRAM_Y_MARGIN = 40  # mm
_CELL_H = 10  # mm

_DIAGRAM_WIDTH = _PAGE_WIDTH - (_DIAGRAM_X_MARGIN * 2)  # mm
_DIAGRAM_X_LEFT = _DIAGRAM_X_MARGIN  # mm
_DIAGRAM_X_RIGHT = _PAGE_WIDTH - _DIAGRAM_X_MARGIN  # mm
_DIAGRAM_Y_START = _PAGE_HEIGHT - _DIAGRAM_Y_MARGIN

_TICK_H = 1  # mm


def draw_field_cell(visio: VisioContext,
                    page: str,
                    field_name: str,
                    label: str,
                    bit_width: int,
                    row: int,
                    position: int,
                    cell_bit_w: float,
                    style: str = 'normal',
                    fill: str = None,
                    continuation: bool = False):
    """ Draw a single field cell at a given row/bit position on the diagram grid.

    :param visio:        Active :class:`VisioContext`.
    :param page:         Name of the target page.
    :param field_name:   Primary text shown in the cell.
    :param label:        Type label shown as subtext (suppressed for continuation cells).
    :param bit_width:    Cell width in bits.
    :param row:          Row index, ``0`` being the topmost row.
    :param position:     Starting bit offset within the row.
    :param cell_bit_w:   Horizontal width of one bit in millimetres.
    :param style:        ``'normal'``, ``'bitfield'``, ``'nested'``, ``'variable'``, or ``'remaining'``.
    :param fill:         Optional hex fill color; defaults to white.
    :param continuation: ``True`` if this cell continues a field from the previous row.
    """
    x_start = _DIAGRAM_X_LEFT + (position * cell_bit_w)
    rect = visio.draw_rectangle(page,
                                x_start,
                                _DIAGRAM_Y_START - (row * _CELL_H),
                                x_start + (bit_width * cell_bit_w),
                                _DIAGRAM_Y_START + _CELL_H - (row * _CELL_H))

    fill = fill if fill else "#FFFFFF"

    visio.style_rectangle(rect, '#000000', fill)

    if style == 'variable':
        visio.style_rectangle(rect,
                              '#000000',
                              fill,
                              stroke_pattern='2')

    elif style == 'remaining':
        # Gray hatched fill marks padding bits at the end of a row (no real field there).
        visio.style_rectangle(rect,
                              '#000000',
                              '#ADADAD',
                              "0.75pt",
                              "2",
                              "#FFFFFF")

    visio.rectangle_text(rect, field_name, label if not continuation else "")


def draw_bit_byte_ticks(visio: VisioContext, page: str, row_bits: int, cell_bit_w: float):
    """ Draw the bit/byte ruler above the diagram with numeric labels every 8 bits.

    :param visio:      Active :class:`VisioContext`.
    :param page:       Name of the target page.
    :param row_bits:   Row width in bits.
    :param cell_bit_w: Horizontal width of one bit in millimetres.
    """
    shapes = []
    for bit in range(row_bits + 1):
        byte = (bit % 8) == 0
        tick_height = _TICK_H * 2 if byte else _TICK_H

        line = visio.draw_line(page,
                               _DIAGRAM_X_LEFT + (bit * cell_bit_w),
                               _DIAGRAM_Y_START + _CELL_H,
                               _DIAGRAM_X_LEFT + (bit * cell_bit_w),
                               _DIAGRAM_Y_START + _CELL_H + tick_height)
        shapes.append(line)

        if byte:
            label = visio.draw_label(page,
                                     str(bit),
                                     _DIAGRAM_X_LEFT + (bit * cell_bit_w) - (10 / 2),
                                     _DIAGRAM_Y_START + _CELL_H + _TICK_H)
            shapes.append(label)

    visio.group(shapes)


def draw_rfc_diagram(packet: type[BinaryPacket],
                     expand_nested: bool = True,
                     editable: bool = True,
                     row_bits: int = 32):
    """ Render a packet definition as an RFC-style diagram in a new Visio document.

    :param packet:        :class:`BinaryPacket` subclass to render.
    :param expand_nested: If ``True``, inline nested packets and tint them with a stable color.
    :param editable:      If ``True``, leave the Visio document open for interactive editing.
    :param row_bits:      Row width in bits (default 32, matching RFC convention).
    """
    if row_bits <= 0:
        raise ValueError("row_bits must be a positive integer")

    fields     = _display_fields(packet, expand_nested)
    rows       = _layout_rows(fields, row_bits)
    cell_bit_w = _DIAGRAM_WIDTH / row_bits

    with VisioContext(editable) as v:
        v.create_page("Test", width=_PAGE_WIDTH, height=_PAGE_HEIGHT)

        draw_bit_byte_ticks(v, "Test", row_bits, cell_bit_w)

        for row, cells in enumerate(rows):
            position = 0
            for cell in cells:
                draw_field_cell(v, "Test",
                                cell.name,
                                cell.label,
                                bit_width=cell.width,
                                row=row,
                                position=position,
                                cell_bit_w=cell_bit_w,
                                style=cell.style,
                                fill=cell.fill,
                                continuation=cell.continuation)
                position += cell.width


def main():
    """ CLI entry point: import a packet class by dotted path and render its diagram.
    """
    from argparse import ArgumentParser
    from pyparse import BinaryPacket

    parser = ArgumentParser(description="Render a pyparse BinaryPacket as an RFC-style Visio diagram.")
    parser.add_argument('class_type',
                        type=str,
                        help="Dotted path to a BinaryPacket subclass, e.g. mypkg.mod.MyPacket")
    parser.add_argument('--expand-nested',
                        action='store_true',
                        help="Inline nested packets and tint them by type")
    parser.add_argument('--row-bits',
                        type=int,
                        default=32,
                        help="Row width in bits (default: 32)")
    parser.add_argument('--keep-open',
                        action='store_true',
                        help="Leave the Visio document open after generation for interactive editing")

    args = parser.parse_args()

    def path_to_class(path: str) -> type[BinaryPacket]:
        import importlib

        module_name, class_name = path.rsplit('.', 1)
        module = importlib.import_module(module_name)
        class_type = getattr(module, class_name)

        if not issubclass(class_type, BinaryPacket):
            raise ValueError(f"{path} is not a BinaryPacket subclass")

        return class_type

    draw_rfc_diagram(path_to_class(args.class_type),
                     expand_nested=args.expand_nested,
                     editable=args.keep_open,
                     row_bits=args.row_bits)


if __name__ == '__main__':
    main()
