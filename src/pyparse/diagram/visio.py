""" Thin wrapper around Microsoft Visio's COM automation API for diagram drawing.
"""
MM_TO_IN = 1 / 25.4


def mm(value: float):
    """ Convert millimetres to inches (Visio's native unit).

    :param value: Length in millimetres.
    :returns:     Length in inches.
    """
    return MM_TO_IN * value


def mm_to_string(value: float):
    """ Format a millimetre length as a Visio ShapeSheet formula string.

    :param value: Length in millimetres.
    :returns:     ``"<value> mm"``.
    """
    return f"{value} mm"


def hex_to_rgb(hex_color: str) -> str:
    """ Convert a ``#RRGGBB`` hex color to a Visio ``RGB(r,g,b)`` formula string.

    :param hex_color: Color in ``#RRGGBB`` form (with or without the leading ``#``).
    :returns:         Visio-compatible ``RGB(r,g,b)`` literal.
    """
    h                = hex_color.lstrip('#')
    red, green, blue = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"RGB({red},{green},{blue})"


class VisioContext:
    """ Context manager that launches Visio, holds a document, and exposes drawing helpers.

    :param editable: If ``True``, leave the Visio document open after exit for interactive editing.
    """
    def __init__(self, editable: bool = False):
        self._visio = None
        self._doc   = None
        self._pages = {}
        self._edit  = editable


    def __enter__(self):
        # Defer COM import: lets non-Windows machines import pyparse.diagram for static inspection.
        try:
            from win32com.client import Dispatch
        except ImportError as exc:
            raise ImportError("pyparse.diagram requires pywin32 on Windows; install with pyparse[diagram].") from exc

        self._visio = Dispatch("Visio.Application")
        self._visio.Visible = True

        self._doc = self._visio.Documents.Add("")

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._edit:
            return

        self._doc.Close()
        self._visio.Quit()

    def create_page(self, page_name: str, page: int = None, width: int = 210, height: int = 297):
        """ Rename a page and set its dimensions; defaults to A4 portrait.

        :param page_name: Name to assign to the page; used as a key by other helpers.
        :param page:      1-based page index; if omitted, picks the next unused page.
        :param width:     Page width in millimetres.
        :param height:    Page height in millimetres.
        :returns:         The Visio page COM object.
        """
        page = self._doc.Pages(page if page else len(self._pages) + 1)

        page.Name = page_name
        page.PageSheet.CellsU("PageWidth").FormulaU  = mm_to_string(width)
        page.PageSheet.CellsU("PageHeight").FormulaU = mm_to_string(height)

        self._pages[page_name] = page
        return page

    def draw_line(self,
                  page_name: str,
                  x_start: float,
                  y_start: float,
                  x_end: float,
                  y_end: float):
        """ Draw a line between two points (millimetre coordinates).

        :param page_name: Name of a page previously registered via :meth:`create_page`.
        :param x_start:   Start x coordinate in mm.
        :param y_start:   Start y coordinate in mm.
        :param x_end:     End x coordinate in mm.
        :param y_end:     End y coordinate in mm.
        :returns:         The Visio line shape.
        """
        page = self._pages[page_name]

        line = page.DrawLine(mm(x_start), mm(y_start), mm(x_end), mm(y_end))
        return line

    @staticmethod
    def style_line(line, stroke: str, stroke_width: str, arrow_begin: str = "0", arrow_end: str = "4"):
        """ Apply stroke color, weight and arrowhead style to a line shape.

        :param line:         Visio line shape returned by :meth:`draw_line`.
        :param stroke:       Stroke color as ``#RRGGBB``.
        :param stroke_width: ShapeSheet length (e.g. ``"0.75pt"``).
        :param arrow_begin:  Visio arrow style code for the start of the line.
        :param arrow_end:    Visio arrow style code for the end of the line.
        :returns:            The same line shape, for chaining.
        """
        line.CellsU("LineColor").FormulaU  = hex_to_rgb(stroke)
        line.CellsU("LineWeight").FormulaU = stroke_width
        line.CellsU("EndArrow").FormulaU   = arrow_begin
        line.CellsU("BeginArrow").FormulaU = arrow_end
        return line

    def draw_rectangle(self,
                       page_name: str,
                       x_left: float,
                       y_left: float,
                       x_right: float,
                       y_right: float):
        """ Draw a rectangle defined by two opposite corners (millimetre coordinates).

        :param page_name: Name of a page previously registered via :meth:`create_page`.
        :param x_left:    Left edge x coordinate in mm.
        :param y_left:    Bottom edge y coordinate in mm.
        :param x_right:   Right edge x coordinate in mm.
        :param y_right:   Top edge y coordinate in mm.
        :returns:         The Visio rectangle shape.
        """
        page = self._pages[page_name]

        rect = page.DrawRectangle(mm(x_left), mm(y_left), mm(x_right), mm(y_right))
        return rect

    @staticmethod
    def style_rectangle(rect,
                        stroke: str,
                        foreground_fill: str,
                        stroke_width: str = '0.75pt',
                        stroke_pattern: str = '1',
                        fill_pattern: str = None,
                        background_fill: str = "#FFFFFF"):
        """ Apply stroke and fill styling to a rectangle shape.

        :param rect:            Visio rectangle shape returned by :meth:`draw_rectangle`.
        :param stroke:          Stroke color as ``#RRGGBB``.
        :param foreground_fill: Foreground fill color as ``#RRGGBB``.
        :param stroke_width:    ShapeSheet length such as ``"0.75pt"``.
        :param stroke_pattern:  Visio line-pattern code (``"1"`` solid, ``"2"`` dashed, ...).
        :param fill_pattern:    Optional Visio fill-pattern code.
        :param background_fill: Background fill color as ``#RRGGBB`` (used by hatched patterns).
        """
        rect.CellsU("LineColor").FormulaU = hex_to_rgb(stroke)
        rect.CellsU("LineWeight").FormulaU = stroke_width

        rect.CellsU("FillForegnd").FormulaU = hex_to_rgb(foreground_fill)
        rect.CellsU("FILLBkgnd").FormulaU   = hex_to_rgb(background_fill)

        if fill_pattern:
            rect.CellsU("FillPattern").FormulaU = fill_pattern

        rect.CellsU("LinePattern").FormulaU = stroke_pattern

    def rectangle_text(self,
                       rect,
                       text: str,
                       subtext: str = "",
                       font: str = "Verdana",
                       size: str = "9pt",
                       color: str = "#000000",
                       hor_align: str = "1",
                       vert_align: str = "1"):
        """ Overlay a text label (optionally with smaller subtext below) on a rectangle and group them.

        :param rect:       Backing rectangle returned by :meth:`draw_rectangle`.
        :param text:       Primary label drawn inside the rectangle.
        :param subtext:    Optional smaller secondary label drawn bottom-aligned.
        :param font:       Font family name.
        :param size:       Primary text size as a ShapeSheet length (e.g. ``"9pt"``).
        :param color:      Primary text color as ``#RRGGBB``.
        :param hor_align:  Visio horizontal alignment code (``"0"`` left, ``"1"`` center, ``"2"`` right).
        :param vert_align: Visio vertical alignment code; overridden to top when subtext is present.
        """
        page = rect.ContainingPage

        # Derive bounds from PinX/PinY (shape center) and Width/Height; Visio's y-axis points up.
        x = rect.CellsU("PinX").Result("in") - rect.CellsU("Width").Result("in") / 2
        y_top = rect.CellsU("PinY").Result("in") + rect.CellsU("Height").Result("in") / 2
        y_bot = rect.CellsU("PinY").Result("in") - rect.CellsU("Height").Result("in") / 2
        w = rect.CellsU("Width").Result("in")

        main = page.DrawRectangle(x, y_top, x + w, y_bot)
        main.Text = text
        main.CellsU("Char.Font").FormulaU      = "\"" + font + "\""
        main.CellsU("LinePattern").FormulaU = "0"
        main.CellsU("FillPattern").FormulaU = "0"
        main.CellsU("Char.Size").FormulaU = size
        main.CellsU("Char.Color").FormulaU = hex_to_rgb(color)
        main.CellsU("Para.HorzAlign").FormulaU = hor_align
        main.CellsU("VerticalAlign").FormulaU = "0" if subtext else vert_align  # top aligned within its box

        if subtext:
            sub = page.DrawRectangle(x, y_top, x + w, y_bot)
            sub.Text = subtext
            sub.CellsU("Char.Font").FormulaU      = "\"" + font + "\""
            sub.CellsU("LinePattern").FormulaU = "0"
            sub.CellsU("FillPattern").FormulaU = "0"
            sub.CellsU("Char.Size").FormulaU = "6pt"
            sub.CellsU("Char.Color").FormulaU = hex_to_rgb("#ADADAD")
            sub.CellsU("Para.HorzAlign").FormulaU = hor_align
            sub.CellsU("VerticalAlign").FormulaU = "2"  # bottom aligned within its box

            self.group([rect, main, sub])
            return

        self.group([rect, main])

    def draw_label(self, page_name: str, text: str, x_left: float, y_left: float, font_size: int = 9):
        """ Draw a borderless text label anchored to a point.

        :param page_name: Name of a page previously registered via :meth:`create_page`.
        :param text:      Label text.
        :param x_left:    Left edge x coordinate in mm.
        :param y_left:    Bottom edge y coordinate in mm.
        :param font_size: Font size in points; also sets the label's vertical extent in mm.
        :returns:         The Visio rectangle shape backing the label.
        """
        page = self._pages[page_name]

        label = page.DrawRectangle(mm(x_left), mm(y_left), mm(x_left + 10), mm(y_left + font_size))
        label.Text = text
        label.CellsU("LinePattern").FormulaU = "0"
        label.CellsU("FillPattern").FormulaU = "0"
        label.CellsU("Char.Size").FormulaU = "9pt"
        label.CellsU("Para.HorzAlign").FormulaU = "1"
        label.CellsU("VerticalAlign").FormulaU = "1"

        return label

    def group(self, shapes: list):
        """ Group several shapes into a single composite via the active window selection.

        :param shapes: Shapes to group.
        :returns:      The new group shape.
        """
        selection = self._visio.ActiveWindow.Selection
        selection.DeselectAll()

        for shape in shapes:
            selection.Select(shape, 2)
        return selection.Group()
