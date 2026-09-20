"""HTML escaping for data-derived values interpolated into dashboard markup.

Every value that originates from the database, a connector or a catalog row is
untrusted with respect to HTML: a catalog name containing ``<script>`` or an
error message containing ``"`` must not be able to break out of its element or
attribute. The dashboard's HTML components call :func:`escape_html` on every
data-derived string before interpolation.

Only presentation-layer *chrome* (the static markup a component builds itself)
is interpolated unescaped; it never contains data.
"""

from html import escape

__all__ = ["escape_html"]


def escape_html(value: object) -> str:
    """Escape a data-derived value for HTML text content or a quoted attribute.

    Quotes are escaped as well as ``&``/``<``/``>``. Escaping ``"`` and ``'`` in
    text content is redundant but harmless (the browser renders the original
    character), and it means one function is safe in **both** contexts — so a
    value can never be rendered differently depending on where a component puts
    it. The input is coerced with ``str`` so a non-string data value (a number, a
    ``Timestamp``) is escaped rather than raising.

    Args:
        value: Any data-derived value about to be interpolated into markup

    Returns:
        The value with ``&``, ``<``, ``>``, ``"`` and ``'`` escaped
    """
    return escape(str(value), quote=True)
