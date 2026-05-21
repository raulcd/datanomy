"""Arrow buffer display using PyArrow buffers."""

from __future__ import annotations

import struct as _struct
from collections.abc import Callable

import numpy as np
import pyarrow as pa
from rich.console import Group
from rich.panel import Panel
from rich.text import Text

_MAX_ROWS = 10
_ORANGE = "orange1"


# ---------------------------------------------------------------------------
# Buffer decoders — all read from pa.Buffer via np.frombuffer
# ---------------------------------------------------------------------------


def _bitmap_text(buf: pa.Buffer, n: int) -> Text:
    """
    Render a packed bitmap buffer as colored bit text (no spaces).

    Shows all bits in the buffer: the first n in element order (white 1s,
    violet 0s), and any trailing padding bits as dim 0s. Arrow packs bitmaps
    into bytes LSB-first, so bits are unpacked with bitorder='little' to
    restore logical element order.

    Parameters
    ----------
        buf: Packed bitmap buffer
        n: Number of meaningful elements (remaining bits are padding)

    Returns
    -------
        Text: Rich Text with white 1s, violet 0s, and dim 0s for padding
    """
    all_bits = np.unpackbits(np.frombuffer(buf, dtype="uint8"), bitorder="little")
    t = Text()
    for i, b in enumerate(all_bits):
        if i < n:
            t.append("1", style="white") if b else t.append("0", style="violet")
        else:
            t.append("0", style="dim")
    return t


def _numeric_text(buf: pa.Buffer, dtype: str, count: int) -> Text:
    """
    Render a fixed-width numeric buffer as space-separated values.

    Parameters
    ----------
        buf: Raw numeric buffer
        dtype: NumPy dtype string (e.g. 'int32', 'int64', 'float64')
        count: Number of elements to read

    Returns
    -------
        Text: Rich Text with values separated by two spaces
    """
    values = np.frombuffer(buf, dtype=dtype)[:count]
    t = Text()
    for i, v in enumerate(values):
        if i > 0:
            t.append("  ")
        t.append(str(v))
    return t


def _numeric_values_text(
    buf: pa.Buffer,
    validity_buf: pa.Buffer | None,
    n: int,
    dtype: str,
) -> Text:
    """
    Render a values buffer with null masking applied from the validity bitmap.

    Parameters
    ----------
        buf: Raw values buffer
        validity_buf: Validity bitmap buffer (None means all values are valid)
        n: Number of elements
        dtype: NumPy dtype string matching the Arrow type's storage format

    Returns
    -------
        Text: Rich Text with values separated by two spaces; nulls shown as dim '-'
    """
    values = np.frombuffer(buf, dtype=dtype)[:n]
    if validity_buf is not None and len(validity_buf) > 0:
        valid = np.unpackbits(
            np.frombuffer(validity_buf, dtype="uint8"), bitorder="little"
        )[:n]
    else:
        valid = np.ones(n, dtype="uint8")
    t = Text()
    for i, (v, is_valid) in enumerate(zip(values, valid)):
        if i > 0:
            t.append("  ")
        t.append("-", style="dim") if not is_valid else t.append(str(v))
    return t


def _bool_values_text(
    buf: pa.Buffer,
    validity_buf: pa.Buffer | None,
    n: int,
) -> Text:
    """
    Render a boolean values buffer showing both raw bits and decoded True/False values.

    Boolean arrays store one bit per value (same packed-bitmap format as validity),
    so both representations are shown.

    Parameters
    ----------
        buf: Raw boolean values bitmap buffer
        validity_buf: Validity bitmap buffer (None means all values are valid)
        n: Number of elements

    Returns
    -------
        Text: Two-line Rich Text — raw bits on the first line, decoded values on the second
    """
    all_bits = np.unpackbits(np.frombuffer(buf, dtype="uint8"), bitorder="little")
    bits = all_bits[:n]
    if validity_buf is not None and len(validity_buf) > 0:
        valid = np.unpackbits(
            np.frombuffer(validity_buf, dtype="uint8"), bitorder="little"
        )[:n]
    else:
        valid = np.ones(n, dtype="uint8")
    t = Text()
    t.append("bits:   ", style="dim")
    for i, b in enumerate(all_bits):
        if i < n:
            t.append("1", style="white") if b else t.append("0", style="violet")
        else:
            t.append("0", style="dim")
    t.append("\n")
    t.append("values: ", style="dim")
    for i, (b, is_valid) in enumerate(zip(bits, valid)):
        if i > 0:
            t.append("  ")
        t.append("-", style="dim") if not is_valid else t.append(
            "True" if b else "False"
        )
    return t


def _fixed_size_binary_text(
    buf: pa.Buffer,
    validity_buf: pa.Buffer | None,
    n: int,
    byte_width: int,
) -> Text:
    """
    Render a fixed-size binary values buffer as hex strings.

    Each value occupies exactly byte_width bytes; null values are shown as dim '-'.

    Parameters
    ----------
        buf: Raw values buffer (n * byte_width bytes)
        validity_buf: Validity bitmap buffer (None means all values are valid)
        n: Number of elements
        byte_width: Fixed byte width per value (from the type)

    Returns
    -------
        Text: Rich Text with hex strings separated by two spaces; nulls as dim '-'
    """
    raw = np.frombuffer(buf, dtype="uint8")
    if validity_buf is not None and len(validity_buf) > 0:
        valid = np.unpackbits(
            np.frombuffer(validity_buf, dtype="uint8"), bitorder="little"
        )[:n]
    else:
        valid = np.ones(n, dtype="uint8")
    t = Text()
    for i in range(n):
        if i > 0:
            t.append("  ")
        if not valid[i]:
            t.append("-", style="dim")
        else:
            t.append(raw[i * byte_width : (i + 1) * byte_width].tobytes().hex())
    return t


def _data_text(buf: pa.Buffer) -> Text:
    """
    Decode a raw data buffer as UTF-8 text via np.frombuffer.

    Parameters
    ----------
        buf: Raw data buffer containing UTF-8 bytes

    Returns
    -------
        Text: Rich Text with the decoded string content
    """
    return Text(
        np.frombuffer(buf, dtype="uint8").tobytes().decode("utf-8", errors="replace")
    )


def _string_view_text(
    views_buf: pa.Buffer,
    validity_buf: pa.Buffer | None,
    n: int,
) -> Text:
    """
    Render the views buffer for string_view / binary_view arrays.

    Each view is 16 bytes read via np.frombuffer. Short strings (len <= 12) are
    stored inline in the view and shown decoded. Longer strings reference a
    variadic buffer: the view stores the total length, the first 4 bytes as a
    prefix, the buffer index, and the byte offset within that buffer.

    Parameters
    ----------
        views_buf: Raw views buffer (16 bytes per element)
        validity_buf: Validity bitmap buffer (None means all values are valid)
        n: Number of elements

    Returns
    -------
        Text: Rich Text with one entry per row
    """
    raw = np.frombuffer(views_buf, dtype="uint8")

    null_mask = None
    if validity_buf is not None and len(validity_buf) > 0:
        null_mask = np.unpackbits(
            np.frombuffer(validity_buf, dtype="uint8"), bitorder="little"
        )[:n]

    t = Text()
    for i in range(n):
        if i > 0:
            t.append("  ")
        if null_mask is not None and not null_mask[i]:
            t.append("-", style="dim")
            continue
        view = raw[i * 16 : (i + 1) * 16].tobytes()
        length = _struct.unpack_from("<i", view, 0)[0]
        if length <= 12:
            data = view[4 : 4 + length]
            t.append(f'"{data.decode("utf-8", errors="replace")}"', style="green")
        else:
            prefix = view[4:8].decode("utf-8", errors="replace")
            buf_index = _struct.unpack_from("<i", view, 8)[0]
            offset = _struct.unpack_from("<i", view, 12)[0]
            t.append(
                f'len={length} prefix="{prefix}" buf={buf_index} off={offset}',
                style="yellow",
            )
    return t


def _arrow_to_numpy_dtype(t: pa.DataType) -> str:
    """
    Map an Arrow primitive type to its NumPy dtype string for buffer decoding.

    For types without a direct NumPy equivalent (dates, timestamps, durations)
    falls back to an integer dtype matching the storage bit width.

    Parameters
    ----------
        t: Arrow data type

    Returns
    -------
        str: NumPy dtype string suitable for np.frombuffer
    """
    if pa.types.is_int8(t):
        return "int8"
    if pa.types.is_int16(t):
        return "int16"
    if pa.types.is_int32(t):
        return "int32"
    if pa.types.is_int64(t):
        return "int64"
    if pa.types.is_uint8(t):
        return "uint8"
    if pa.types.is_uint16(t):
        return "uint16"
    if pa.types.is_uint32(t):
        return "uint32"
    if pa.types.is_uint64(t):
        return "uint64"
    if pa.types.is_float16(t):
        return "float16"
    if pa.types.is_float32(t):
        return "float32"
    if pa.types.is_float64(t):
        return "float64"
    # Date, time, timestamp, duration, interval — fall back to bit width
    try:
        bw = t.bit_width
        if bw == 8:
            return "int8"
        if bw == 16:
            return "int16"
        if bw == 32:
            return "int32"
        if bw == 64:
            return "int64"
    except AttributeError:
        pass
    return "uint8"


# ---------------------------------------------------------------------------
# Kept for backwards compatibility (used in tests)
# ---------------------------------------------------------------------------


def _validity_text(buf: pa.Buffer | None, num_rows: int) -> Text:
    """
    Render a validity bitmap as packed bit text.
    Returns dim 'None' when the buffer is not allocated.

    Parameters
    ----------
        buf: Validity bitmap buffer, or None if not allocated
        num_rows: Number of elements to unpack

    Returns
    -------
        Text: Rich Text with white 1s and violet 0s, or dim 'None'
    """
    if buf is None or len(buf) == 0:
        return Text("None", style="dim")
    return _bitmap_text(buf, num_rows)


def _offsets_text(buf: pa.Buffer, num_rows: int, offset_type: pa.DataType) -> Text:
    """
    Render an offsets buffer as space-separated integers.
    Reads num_rows + 1 entries (offsets array has one more entry than row count).

    Parameters
    ----------
        buf: Raw offsets buffer
        num_rows: Number of array elements (offsets has num_rows + 1 entries)
        offset_type: PyArrow integer type (int32 or int64)

    Returns
    -------
        Text: Rich Text with offset values separated by two spaces
    """
    dtype = "int32" if offset_type == pa.int32() else "int64"
    return _numeric_text(buf, dtype, num_rows + 1)


# ---------------------------------------------------------------------------
# Display item builders
# ---------------------------------------------------------------------------


def _validity_items(buf: pa.Buffer | None, n: int, label: str) -> list:
    """
    Return display items for a validity bitmap.
    When not allocated (None) there is no box — just 'None' text, because no
    memory was allocated at all for this buffer.

    Parameters
    ----------
        buf: Validity bitmap buffer, or None if not allocated
        n: Number of elements
        label: Label text shown above

    Returns
    -------
        list: [label Text, content (Panel or plain Text), spacer Text]
    """
    label_text = Text(label, style=_ORANGE)
    if buf is None or len(buf) == 0:
        return [label_text, Text("  None", style="dim"), Text()]
    return [
        label_text,
        Panel(_bitmap_text(buf, n), border_style="white", expand=False, padding=(0, 1)),
        Text(),
    ]


def _buffer_items(name: str, content: Text) -> list:
    """
    Return an orange label and a compact white-bordered box for one buffer.

    Parameters
    ----------
        name: Buffer name shown as the label above the box
        content: Rich Text content to display inside the box

    Returns
    -------
        list: [Text label, Panel box, Text spacer]
    """
    label = Text(name, style=_ORANGE)
    box = Panel(content, border_style="white", expand=False, padding=(0, 1))
    return [label, box, Text()]


# ---------------------------------------------------------------------------
# Recursive type walker — consumes from a shared cursor over array.buffers()
# ---------------------------------------------------------------------------


def _is_supported(t: pa.DataType) -> bool:
    """Return True if the type is handled by _walk_and_render."""
    return bool(
        pa.types.is_null(t)
        or pa.types.is_boolean(t)
        or pa.types.is_string(t)
        or pa.types.is_binary(t)
        or pa.types.is_large_string(t)
        or pa.types.is_large_binary(t)
        or pa.types.is_string_view(t)
        or pa.types.is_binary_view(t)
        or pa.types.is_list(t)
        or pa.types.is_large_list(t)
        or pa.types.is_list_view(t)
        or pa.types.is_struct(t)
        or pa.types.is_dictionary(t)
        or pa.types.is_fixed_size_list(t)
        or pa.types.is_map(t)
        or pa.types.is_fixed_size_binary(t)
        or pa.types.is_run_end_encoded(t)
        or pa.types.is_union(t)
        or pa.types.is_primitive(t)
    )


def _walk_and_render(
    t: pa.DataType,
    array: pa.Array,
    n: int,
    prefix: str,
    next_buf: Callable[[], pa.Buffer | None],
    items: list,
) -> None:
    """
    Walk the type tree consuming buffers from a shared cursor and building display items.

    array.buffers() returns ALL buffers in depth-first order (own buffers first,
    then children's).  A single cursor is shared across the whole tree so that
    consuming validity/offsets/values at each level automatically advances past
    the right position for the next level.

    Parameters
    ----------
        t: Arrow type for this level
        array: The array at this level (for computing child sizes / accessing children)
        n: Number of rows at this level
        prefix: Label prefix for nested display (e.g. 'Child array — ')
        next_buf: Callable that returns the next buffer from the shared cursor
        items: Accumulator list — display items are appended in place
    """
    if not _is_supported(t):
        items += [
            Text(f"{prefix}type '{t}' not yet supported in buffers view", style="dim"),
            Text(),
        ]
        return

    if pa.types.is_null(t):
        # Arrow spec: null type has no buffers. PyArrow returns [None] as a cursor
        # placeholder; consume it to keep the cursor aligned with array.buffers().
        next_buf()
        items += [Text(f"{prefix}(null type — no buffers)", style="dim"), Text()]
        return

    if pa.types.is_run_end_encoded(t):
        # REE has no own validity bitmap. Consume the [None] placeholder then
        # recurse into the two children: run_ends and values.
        next_buf()
        _walk_and_render(
            t.run_end_type,
            array.run_ends,
            len(array.run_ends),
            f"{prefix}Run-ends — ",
            next_buf,
            items,
        )
        _walk_and_render(
            t.value_type,
            array.values,
            len(array.values),
            f"{prefix}Values — ",
            next_buf,
            items,
        )
        return

    if pa.types.is_union(t):
        # Union arrays have no validity bitmap. Consume the [None] placeholder,
        # then type_ids, then offsets (dense only), then each child's buffers.
        next_buf()
        type_ids_buf = next_buf()
        if type_ids_buf is not None:
            items += _buffer_items(
                f"{prefix}Type IDs buffer", _numeric_text(type_ids_buf, "int8", n)
            )
        if t.mode == "dense":
            offsets_buf = next_buf()
            if offsets_buf is not None:
                items += _buffer_items(
                    f"{prefix}Offsets buffer", _numeric_text(offsets_buf, "int32", n)
                )
        for i in range(t.num_fields):
            field = t.field(i)
            child = array.field(i)
            child_n = n if t.mode == "sparse" else len(child)
            _walk_and_render(
                field.type,
                child,
                child_n,
                f'{prefix}Child "{field.name}" — ',
                next_buf,
                items,
            )
        return

    # Every other supported type has a validity bitmap as its first buffer
    validity_buf = next_buf()
    items += _validity_items(validity_buf, n, f"{prefix}Validity bitmap buffer")

    if pa.types.is_boolean(t):
        buf = next_buf()
        if buf is not None:
            items += _buffer_items(
                f"{prefix}Values buffer", _bool_values_text(buf, validity_buf, n)
            )

    elif pa.types.is_string(t) or pa.types.is_binary(t):
        offsets_buf = next_buf()
        data_buf = next_buf()
        if offsets_buf is not None:
            items += _buffer_items(
                f"{prefix}Offsets buffer", _numeric_text(offsets_buf, "int32", n + 1)
            )
        if data_buf is not None:
            items += _buffer_items(f"{prefix}Data buffer", _data_text(data_buf))

    elif pa.types.is_large_string(t) or pa.types.is_large_binary(t):
        offsets_buf = next_buf()
        data_buf = next_buf()
        if offsets_buf is not None:
            items += _buffer_items(
                f"{prefix}Offsets buffer", _numeric_text(offsets_buf, "int64", n + 1)
            )
        if data_buf is not None:
            items += _buffer_items(f"{prefix}Data buffer", _data_text(data_buf))

    elif pa.types.is_string_view(t) or pa.types.is_binary_view(t):
        views_buf = next_buf()
        # string_view has no child arrays — remaining buffers in array.buffers() are variadic
        n_variadic = len(array.buffers()) - 2
        if views_buf is not None:
            items += _buffer_items(
                f"{prefix}Views buffer",
                _string_view_text(views_buf, validity_buf, n),
            )
        for i in range(n_variadic):
            var_buf = next_buf()
            if var_buf is not None:
                items += _buffer_items(
                    f"{prefix}Variadic data buffer [{i}]", _data_text(var_buf)
                )

    elif pa.types.is_list(t):
        offsets_buf = next_buf()
        if offsets_buf is not None:
            items += _buffer_items(
                f"{prefix}Offsets buffer", _numeric_text(offsets_buf, "int32", n + 1)
            )
        child_n = array.offsets[n].as_py() if n > 0 else 0
        _walk_and_render(
            t.value_type,
            array.values.slice(0, child_n),
            child_n,
            f"{prefix}Child array — ",
            next_buf,
            items,
        )

    elif pa.types.is_large_list(t):
        offsets_buf = next_buf()
        if offsets_buf is not None:
            items += _buffer_items(
                f"{prefix}Offsets buffer", _numeric_text(offsets_buf, "int64", n + 1)
            )
        child_n = array.offsets[n].as_py() if n > 0 else 0
        _walk_and_render(
            t.value_type,
            array.values.slice(0, child_n),
            child_n,
            f"{prefix}Child array — ",
            next_buf,
            items,
        )

    elif pa.types.is_list_view(t):
        # list_view carries offsets and sizes — each has n entries (not n+1)
        offsets_buf = next_buf()
        sizes_buf = next_buf()
        if offsets_buf is not None:
            items += _buffer_items(
                f"{prefix}Offsets buffer", _numeric_text(offsets_buf, "int32", n)
            )
        if sizes_buf is not None:
            items += _buffer_items(
                f"{prefix}Sizes buffer", _numeric_text(sizes_buf, "int32", n)
            )
        # list_view values can be in any order; cap child display at _MAX_ROWS
        child_vals = array.values
        child_n = min(len(child_vals), _MAX_ROWS)
        _walk_and_render(
            t.value_type,
            child_vals.slice(0, child_n),
            child_n,
            f"{prefix}Child array — ",
            next_buf,
            items,
        )

    elif pa.types.is_struct(t):
        for i in range(t.num_fields):
            field = t.field(i)
            _walk_and_render(
                field.type,
                array.field(field.name),
                n,
                f'{prefix}Child array "{field.name}" — ',
                next_buf,
                items,
            )

    elif pa.types.is_dictionary(t):
        idx_buf = next_buf()
        if idx_buf is not None:
            dtype = _arrow_to_numpy_dtype(t.index_type)
            items += _buffer_items(
                f"{prefix}Indices values buffer",
                _numeric_values_text(idx_buf, validity_buf, n, dtype),
            )
        # The dictionary is a separate Arrow array — it does NOT appear in
        # array.buffers(). Access it via array.dictionary with its own fresh cursor.
        items += _array_items(array.dictionary, f"{prefix}Dictionary — ")

    elif pa.types.is_fixed_size_list(t):
        child_n = n * t.list_size
        _walk_and_render(
            t.value_type,
            array.values.slice(0, child_n),
            child_n,
            f"{prefix}Child array — ",
            next_buf,
            items,
        )

    elif pa.types.is_map(t):
        offsets_buf = next_buf()
        if offsets_buf is not None:
            entries_n = int(np.frombuffer(offsets_buf, dtype="int32")[n])
            items += _buffer_items(
                f"{prefix}Offsets buffer", _numeric_text(offsets_buf, "int32", n + 1)
            )
        else:
            entries_n = 0
        # Entries struct has its own validity slot in the flat buffer list
        entries_validity_buf = next_buf()
        items += _validity_items(
            entries_validity_buf, entries_n, f"{prefix}Entries validity bitmap buffer"
        )
        keys = array.keys.slice(0, entries_n)
        values = array.items.slice(0, entries_n)
        _walk_and_render(
            t.key_type, keys, entries_n, f"{prefix}Key — ", next_buf, items
        )
        _walk_and_render(
            t.item_type, values, entries_n, f"{prefix}Value — ", next_buf, items
        )

    elif pa.types.is_fixed_size_binary(t):
        buf = next_buf()
        if buf is not None:
            items += _buffer_items(
                f"{prefix}Values buffer",
                _fixed_size_binary_text(buf, validity_buf, n, t.byte_width),
            )

    elif pa.types.is_primitive(t):
        buf = next_buf()
        if buf is not None:
            dtype = _arrow_to_numpy_dtype(t)
            items += _buffer_items(
                f"{prefix}Values buffer",
                _numeric_values_text(buf, validity_buf, n, dtype),
            )


def _array_items(array: pa.Array, prefix: str = "") -> list:
    """
    Return display items for all buffers of an array and its children.

    Calls array.buffers() once to get the complete flat buffer list (own buffers
    followed by children's buffers in depth-first order), then walks the type
    tree consuming buffers in sequence via a shared cursor.

    Parameters
    ----------
        array: PyArrow array (already sliced to display length)
        prefix: Label prefix for nested display

    Returns
    -------
        list: Flat list of Rich renderables (labels, Panels, spacers)
    """
    buf_iter = iter(array.buffers())

    def next_buf() -> pa.Buffer | None:
        return next(buf_iter, None)

    items: list = []
    _walk_and_render(array.type, array, len(array), prefix, next_buf, items)
    return items


def column_panel(field_name: str, array: pa.Array) -> Panel:
    """
    Render a column's buffer layout as a Rich Panel.

    Parameters
    ----------
        field_name: Column name shown in the panel title
        array: PyArrow array whose buffers are displayed

    Returns
    -------
        Panel: Rich Panel containing labeled buffer boxes for the column
    """
    n = min(len(array), _MAX_ROWS)
    array = array.slice(0, n)
    items = _array_items(array)
    return Panel(
        Group(*items),
        title=f"[green]{field_name}[/green]  [dim]{array.type}[/dim]",
        border_style="cyan",
        padding=(0, 1),
    )
