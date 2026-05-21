"""Tests for the buffers display module."""

import pyarrow as pa
from rich.panel import Panel
from rich.text import Text

from datanomy.buffers.core import (
    _bitmap_text,
    _bool_values_text,
    _data_text,
    _numeric_text,
    _numeric_values_text,
    _offsets_text,
    _string_view_text,
    _validity_text,
    column_panel,
)


# --- _validity_text ---


def test_validity_text_none_buffer() -> None:
    """None buffer means no nulls; returns a dim 'None' message."""
    result = _validity_text(None, 5)
    assert isinstance(result, Text)
    assert "None" in result.plain


def test_validity_text_no_nulls() -> None:
    """PyArrow omits the validity buffer when all values are valid."""
    arr = pa.array([1, 2, 3, 4, 5], type=pa.int32())
    buf = arr.buffers()[0]
    result = _validity_text(buf, 5)
    assert isinstance(result, Text)
    if buf is None:
        assert "None" in result.plain
    else:
        assert "1" in result.plain


def test_validity_text_with_nulls() -> None:
    """Array with some nulls produces text containing both 1s and 0s."""
    arr = pa.array([1, None, 3], type=pa.int32())
    buf = arr.buffers()[0]
    assert buf is not None
    result = _validity_text(buf, 3)
    assert isinstance(result, Text)
    assert "1" in result.plain
    assert "0" in result.plain


def test_validity_text_all_nulls() -> None:
    """Array with all nulls produces text containing only 0s."""
    arr = pa.array([None, None, None], type=pa.int32())
    buf = arr.buffers()[0]
    assert buf is not None
    result = _validity_text(buf, 3)
    assert isinstance(result, Text)
    assert "0" in result.plain


# --- _bitmap_text ---


def test_bitmap_text_basic() -> None:
    """Bitmap text returns a Text with only '1' and '0' characters."""
    arr = pa.array([1, None, 3], type=pa.int32())
    buf = arr.buffers()[0]
    assert buf is not None
    result = _bitmap_text(buf, 3)
    assert isinstance(result, Text)
    for ch in result.plain:
        assert ch in ("0", "1")


def test_bitmap_text_length() -> None:
    """Bitmap text has ceil(n/8)*8 characters: n meaningful bits plus padding."""
    arr = pa.array([1, None, 3, None, 5], type=pa.int32())
    buf = arr.buffers()[0]
    assert buf is not None
    result = _bitmap_text(buf, 5)
    # 5 elements → 1 byte → 8 bits (5 meaningful + 3 dim padding)
    assert len(result.plain) == 8


# --- _numeric_text ---


def test_numeric_text_int32() -> None:
    """Offsets buffer reads correct int32 values."""
    arr = pa.array(["hello", "world"], type=pa.string())
    buf = arr.buffers()[1]
    assert buf is not None
    result = _numeric_text(buf, "int32", 3)
    assert isinstance(result, Text)
    assert "0" in result.plain
    assert "5" in result.plain
    assert "10" in result.plain


def test_numeric_text_int64() -> None:
    """Large-string offsets read correct int64 values."""
    arr = pa.array(["foo", "bar"], type=pa.large_string())
    buf = arr.buffers()[1]
    assert buf is not None
    result = _numeric_text(buf, "int64", 3)
    assert isinstance(result, Text)
    assert "0" in result.plain
    assert "3" in result.plain
    assert "6" in result.plain


# --- _numeric_values_text ---


def test_numeric_values_text_no_nulls() -> None:
    """All values rendered as plain strings when validity is None."""
    arr = pa.array([10, 20, 30], type=pa.int32())
    buf = arr.buffers()[1]
    assert buf is not None
    result = _numeric_values_text(buf, None, 3, "int32")
    assert isinstance(result, Text)
    assert "10" in result.plain
    assert "20" in result.plain
    assert "30" in result.plain


def test_numeric_values_text_with_nulls() -> None:
    """Null values rendered as dim '-' character."""
    arr = pa.array([10, None, 30], type=pa.int32())
    validity_buf = arr.buffers()[0]
    values_buf = arr.buffers()[1]
    assert values_buf is not None
    result = _numeric_values_text(values_buf, validity_buf, 3, "int32")
    assert isinstance(result, Text)
    assert "-" in result.plain
    assert "10" in result.plain
    assert "30" in result.plain


def test_numeric_values_text_all_nulls() -> None:
    """All-null array renders only '-' entries."""
    arr = pa.array([None, None], type=pa.int32())
    validity_buf = arr.buffers()[0]
    values_buf = arr.buffers()[1]
    assert values_buf is not None
    result = _numeric_values_text(values_buf, validity_buf, 2, "int32")
    assert isinstance(result, Text)
    assert "-" in result.plain


# --- _bool_values_text ---


def test_bool_values_text_basic() -> None:
    """Boolean values text contains a bits line and a values line."""
    arr = pa.array([True, False, None], type=pa.bool_())
    validity_buf = arr.buffers()[0]
    values_buf = arr.buffers()[1]
    assert values_buf is not None
    result = _bool_values_text(values_buf, validity_buf, 3)
    assert isinstance(result, Text)
    assert "bits:" in result.plain
    assert "values:" in result.plain


def test_bool_values_text_null_as_dash() -> None:
    """Null boolean values are rendered as '-'."""
    arr = pa.array([True, None], type=pa.bool_())
    validity_buf = arr.buffers()[0]
    values_buf = arr.buffers()[1]
    assert values_buf is not None
    result = _bool_values_text(values_buf, validity_buf, 2)
    assert "-" in result.plain


def test_bool_values_text_no_nulls() -> None:
    """Without nulls, values show True/False."""
    arr = pa.array([True, False], type=pa.bool_())
    values_buf = arr.buffers()[1]
    assert values_buf is not None
    result = _bool_values_text(values_buf, None, 2)
    assert "True" in result.plain
    assert "False" in result.plain


# --- _offsets_text ---


def test_offsets_text_int32() -> None:
    """String array offsets are rendered with int32 widths."""
    arr = pa.array(["hello", "world"], type=pa.string())
    buf = arr.buffers()[1]
    assert buf is not None
    result = _offsets_text(buf, 2, pa.int32())
    assert isinstance(result, Text)
    assert "0" in result.plain
    assert "5" in result.plain
    assert "10" in result.plain


def test_offsets_text_int64() -> None:
    """Large-string array offsets are rendered with int64 widths."""
    arr = pa.array(["foo", "bar"], type=pa.large_string())
    buf = arr.buffers()[1]
    assert buf is not None
    result = _offsets_text(buf, 2, pa.int64())
    assert isinstance(result, Text)
    assert "0" in result.plain
    assert "3" in result.plain
    assert "6" in result.plain


def test_offsets_text_with_nulls() -> None:
    """Null values do not break offset rendering (offsets still advance by 0)."""
    arr = pa.array(["a", None, "bc"], type=pa.string())
    buf = arr.buffers()[1]
    assert buf is not None
    result = _offsets_text(buf, 3, pa.int32())
    assert isinstance(result, Text)


# --- _data_text ---


def test_data_text_valid_utf8() -> None:
    """Concatenated UTF-8 bytes of the data buffer are decoded correctly."""
    arr = pa.array(["hello", "world"], type=pa.string())
    buf = arr.buffers()[2]
    assert buf is not None
    result = _data_text(buf)
    assert isinstance(result, Text)
    assert "helloworld" in result.plain


def test_data_text_empty_buffer() -> None:
    """An empty buffer decodes to an empty string without error."""
    buf = pa.py_buffer(b"")
    result = _data_text(buf)
    assert isinstance(result, Text)
    assert result.plain == ""


def test_data_text_non_ascii() -> None:
    """Non-ASCII UTF-8 content is decoded without raising."""
    arr = pa.array(["café", "naïve"], type=pa.string())
    buf = arr.buffers()[2]
    assert buf is not None
    result = _data_text(buf)
    assert isinstance(result, Text)


# --- _string_view_text ---


def test_string_view_text_inline() -> None:
    """Short strings (<=12 bytes) are shown inline in quotes."""
    arr = pa.array(["hi", "bye"], type=pa.string_view())
    views_buf = arr.buffers()[1]
    assert views_buf is not None
    result = _string_view_text(views_buf, None, 2)
    assert isinstance(result, Text)
    assert '"hi"' in result.plain
    assert '"bye"' in result.plain


def test_string_view_text_long() -> None:
    """Long strings (>12 bytes) show len/prefix/buf/offset metadata."""
    arr = pa.array(["a-string-longer-than-twelve-bytes"], type=pa.string_view())
    views_buf = arr.buffers()[1]
    assert views_buf is not None
    result = _string_view_text(views_buf, None, 1)
    assert isinstance(result, Text)
    assert "len=" in result.plain


def test_string_view_text_with_nulls() -> None:
    """Null values in string_view arrays are rendered as '-'."""
    arr = pa.array(["hi", None, "bye"], type=pa.string_view())
    views_buf = arr.buffers()[1]
    validity_buf = arr.buffers()[0]
    assert views_buf is not None
    result = _string_view_text(views_buf, validity_buf, 3)
    assert isinstance(result, Text)
    assert "-" in result.plain


# --- column_panel ---


def test_column_panel_returns_panel() -> None:
    """column_panel always returns a Rich Panel."""
    arr = pa.array([1, 2, 3], type=pa.int32())
    assert isinstance(column_panel("col", arr), Panel)


def test_column_panel_title_contains_field_name() -> None:
    """Panel title includes the field name."""
    arr = pa.array([1, 2, 3], type=pa.int32())
    panel = column_panel("my_field", arr)
    assert "my_field" in str(panel.title)


def test_column_panel_title_contains_type() -> None:
    """Panel title includes the Arrow type."""
    arr = pa.array([1, 2, 3], type=pa.int32())
    panel = column_panel("col", arr)
    assert "int32" in str(panel.title)


def test_column_panel_int32_with_nulls() -> None:
    """Primitive int32 column with nulls renders without error."""
    arr = pa.array([1, None, 3], type=pa.int32())
    assert isinstance(column_panel("id", arr), Panel)


def test_column_panel_float64() -> None:
    """Float64 column renders without error."""
    arr = pa.array([1.1, None, 3.3], type=pa.float64())
    assert isinstance(column_panel("score", arr), Panel)


def test_column_panel_bool() -> None:
    """Bool column renders without error."""
    arr = pa.array([True, False, None], type=pa.bool_())
    assert isinstance(column_panel("flag", arr), Panel)


def test_column_panel_string() -> None:
    """String column with nulls renders without error."""
    arr = pa.array(["alice", None, "charlie"], type=pa.string())
    assert isinstance(column_panel("name", arr), Panel)


def test_column_panel_large_string() -> None:
    """Large-string column uses int64 offsets and renders without error."""
    arr = pa.array(["foo", None, "bar"], type=pa.large_string())
    assert isinstance(column_panel("notes", arr), Panel)


def test_column_panel_string_view_inline() -> None:
    """String-view column with short (inline) values renders without error."""
    arr = pa.array(["short", None, "also_short"], type=pa.string_view())
    assert isinstance(column_panel("sv_col", arr), Panel)


def test_column_panel_string_view_variadic() -> None:
    """String-view column with a long value (> 12 bytes) renders variadic buffer."""
    arr = pa.array(
        ["short", None, "a-much-longer-string-exceeding-twelve-bytes"],
        type=pa.string_view(),
    )
    assert isinstance(column_panel("sv_long", arr), Panel)


def test_column_panel_list_of_strings() -> None:
    """List<string> column has offsets and values buffers; renders without error."""
    arr = pa.array([["a", "b"], None, ["c"]], type=pa.list_(pa.string()))
    assert isinstance(column_panel("tags", arr), Panel)


def test_column_panel_list_view() -> None:
    """List-view column has offsets and sizes buffers; renders without error."""
    arr = pa.array(
        [["a", "b"], None, ["c"], [], ["d", "e"]],
        type=pa.list_view(pa.string()),
    )
    assert isinstance(column_panel("labels", arr), Panel)


def test_column_panel_struct() -> None:
    """Struct column renders all child buffers without error."""
    struct_type = pa.struct([pa.field("x", pa.int32()), pa.field("y", pa.int32())])
    arr = pa.array([{"x": 1, "y": 2}, None, {"x": 3, "y": 4}], type=struct_type)
    assert isinstance(column_panel("point", arr), Panel)


def test_column_panel_empty_array() -> None:
    """Empty array (0 rows) renders without error."""
    arr = pa.array([], type=pa.int32())
    assert isinstance(column_panel("empty", arr), Panel)


def test_column_panel_all_nulls() -> None:
    """All-null column renders without error."""
    arr = pa.array([None, None, None], type=pa.int32())
    assert isinstance(column_panel("all_null", arr), Panel)


def test_column_panel_truncates_long_array() -> None:
    """Arrays longer than _MAX_ROWS (10) are silently truncated."""
    arr = pa.array(list(range(50)), type=pa.int32())
    assert isinstance(column_panel("long_col", arr), Panel)


def test_column_panel_fixed_size_list() -> None:
    """Fixed-size list column renders child buffers without error."""
    arr = pa.array(
        [[1, 2, 3], None, [4, 5, 6]],
        type=pa.list_(pa.int16(), 3),
    )
    assert isinstance(column_panel("coords", arr), Panel)


def test_column_panel_map() -> None:
    """Map column renders offsets, entries validity, key and value buffers without error."""
    arr = pa.array(
        [[("a", 1), ("b", 2)], None, [("c", 3)]],
        type=pa.map_(pa.string(), pa.int32()),
    )
    assert isinstance(column_panel("attrs", arr), Panel)


def test_column_panel_null_type() -> None:
    """Null type column (all values null by definition) renders without error."""
    arr = pa.array([None, None, None], type=pa.null())
    assert isinstance(column_panel("nothing", arr), Panel)


def test_column_panel_dictionary() -> None:
    """Dictionary-encoded column renders indices and dictionary array separately."""
    d = pa.array(["Python", "Data", "Arrow"])
    arr = pa.DictionaryArray.from_arrays(
        pa.array([0, 1, None, 2, 0], type=pa.int16()), d
    )
    panel = column_panel("lang", arr)
    assert isinstance(panel, Panel)


def test_column_panel_run_end_encoded() -> None:
    """Run-end encoded column renders run-ends and values children without error."""
    arr = pa.RunEndEncodedArray.from_arrays(
        run_ends=pa.array([2, 4, 5], type=pa.int32()),
        values=pa.array(["a", "b", "c"]),
    )
    assert isinstance(column_panel("ree_col", arr), Panel)


def test_column_panel_sparse_union() -> None:
    """Sparse union column renders type-ids and child buffers without error."""
    arr = pa.UnionArray.from_sparse(
        pa.array([0, 1, 0, 1], type=pa.int8()),
        [
            pa.array([1, 0, 3, 0], type=pa.int32()),
            pa.array([None, "a", None, "b"], type=pa.utf8()),
        ],
    )
    assert isinstance(column_panel("su_col", arr), Panel)


def test_column_panel_dense_union() -> None:
    """Dense union column renders type-ids, offsets and child buffers without error."""
    arr = pa.UnionArray.from_dense(
        pa.array([0, 1, 0, 1], type=pa.int8()),
        pa.array([0, 0, 1, 1], type=pa.int32()),
        [
            pa.array([1, 3], type=pa.int32()),
            pa.array(["a", "b"], type=pa.utf8()),
        ],
    )
    assert isinstance(column_panel("du_col", arr), Panel)


def test_column_panel_fixed_size_binary() -> None:
    """Fixed-size binary column renders values as hex strings without error."""
    arr = pa.array(
        [b"hello123456789ab", None, b"ABCDEFGHIJKLMNOP"],
        type=pa.binary(16),
    )
    assert isinstance(column_panel("uuid_col", arr), Panel)


def test_column_panel_timestamp() -> None:
    """Timestamp column (primitive type) renders without error."""
    arr = pa.array([1704067200, None, 1717200000], type=pa.timestamp("s"))
    assert isinstance(column_panel("ts_col", arr), Panel)


def test_column_panel_single_row() -> None:
    """Single-element array renders without error."""
    arr = pa.array([42], type=pa.int32())
    assert isinstance(column_panel("one", arr), Panel)
