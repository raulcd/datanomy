"""Tests for the TUI module.

These are smoke tests to ensure the UI doesn't crash.
We don't test specific text/formatting as that's brittle and changes often.
"""

from pathlib import Path

import pytest

from datanomy.reader.ipc import IPCReader
from datanomy.reader.parquet import ParquetReader
from datanomy.tui.tui import DatanomyApp


@pytest.mark.asyncio
async def test_app_launches_without_crash(simple_parquet: Path) -> None:
    """Test that app launches and runs without crashing."""
    reader = ParquetReader(simple_parquet)
    app = DatanomyApp(reader)

    async with app.run_test():
        # If we get here, app launched successfully
        assert app is not None


@pytest.mark.asyncio
async def test_app_has_required_tabs(simple_parquet: Path) -> None:
    """Test that all expected tabs are present."""
    reader = ParquetReader(simple_parquet)
    app = DatanomyApp(reader)

    async with app.run_test():
        # Verify all tabs exist
        assert app.query_one("#tab-structure") is not None
        assert app.query_one("#tab-schema") is not None
        assert app.query_one("#tab-data") is not None
        assert app.query_one("#tab-metadata") is not None
        assert app.query_one("#tab-stats") is not None


@pytest.mark.asyncio
async def test_tabs_render_without_error(simple_parquet: Path) -> None:
    """Test that tab content renders without throwing exceptions."""
    reader = ParquetReader(simple_parquet)
    app = DatanomyApp(reader)

    async with app.run_test():
        # Verify structure and schema tabs render
        # (other tabs are placeholders for now)
        structure_content = app.query_one("#structure-content")
        structure_content.render()

        schema_content = app.query_one("#schema-content")
        schema_content.render()


@pytest.mark.asyncio
async def test_app_with_empty_file(empty_parquet: Path) -> None:
    """Test that app handles empty Parquet files."""
    reader = ParquetReader(empty_parquet)
    app = DatanomyApp(reader)

    async with app.run_test():
        # Should not crash with empty file
        app.query_one("#structure-content").render()
        app.query_one("#schema-content").render()


@pytest.mark.asyncio
async def test_app_with_complex_schema(complex_schema_parquet: Path) -> None:
    """Test that app handles complex nested schemas."""
    reader = ParquetReader(complex_schema_parquet)
    app = DatanomyApp(reader)

    async with app.run_test():
        # Should handle nested types without crashing
        app.query_one("#structure-content").render()
        app.query_one("#schema-content").render()


@pytest.mark.asyncio
async def test_app_with_many_columns(large_schema_parquet: Path) -> None:
    """Test that app handles files with many columns."""
    reader = ParquetReader(large_schema_parquet)
    app = DatanomyApp(reader)

    async with app.run_test():
        # Should handle large schema without crashing
        app.query_one("#structure-content").render()
        app.query_one("#schema-content").render()


@pytest.mark.asyncio
async def test_app_with_multiple_row_groups(multi_row_group_parquet: Path) -> None:
    """Test that app handles multiple row groups."""
    reader = ParquetReader(multi_row_group_parquet)
    app = DatanomyApp(reader)

    async with app.run_test():
        # Should handle multiple row groups without crashing
        app.query_one("#structure-content").render()


# --- Arrow IPC TUI tests ---


@pytest.mark.asyncio
async def test_ipc_app_launches_without_crash(simple_ipc: Path) -> None:
    """Test that app launches with an IPC file without crashing."""
    reader = IPCReader(simple_ipc)
    app = DatanomyApp(reader)

    async with app.run_test():
        assert app is not None


@pytest.mark.asyncio
async def test_ipc_app_has_required_tabs(simple_ipc: Path) -> None:
    """Test that all expected IPC tabs are present (no Stats tab)."""
    reader = IPCReader(simple_ipc)
    app = DatanomyApp(reader)

    async with app.run_test():
        assert app.query_one("#tab-structure") is not None
        assert app.query_one("#tab-schema") is not None
        assert app.query_one("#tab-data") is not None
        assert app.query_one("#tab-metadata") is not None


@pytest.mark.asyncio
async def test_ipc_tabs_render_without_error(simple_ipc: Path) -> None:
    """Test that IPC tab content renders without throwing exceptions."""
    reader = IPCReader(simple_ipc)
    app = DatanomyApp(reader)

    async with app.run_test():
        app.query_one("#structure-content").render()
        app.query_one("#schema-content").render()


@pytest.mark.asyncio
async def test_ipc_app_with_empty_file(empty_ipc: Path) -> None:
    """Test that app handles empty Arrow IPC files."""
    reader = IPCReader(empty_ipc)
    app = DatanomyApp(reader)

    async with app.run_test():
        app.query_one("#structure-content").render()
        app.query_one("#schema-content").render()


@pytest.mark.asyncio
async def test_ipc_app_with_multiple_batches(multi_batch_ipc: Path) -> None:
    """Test that app handles multiple record batches."""
    reader = IPCReader(multi_batch_ipc)
    app = DatanomyApp(reader)

    async with app.run_test():
        app.query_one("#structure-content").render()


# --- Buffers tab TUI tests ---


@pytest.mark.asyncio
async def test_ipc_buffers_tab_present(simple_ipc: Path) -> None:
    """Test that the Buffers tab is present in the IPC app."""
    reader = IPCReader(simple_ipc)
    app = DatanomyApp(reader)

    async with app.run_test():
        assert app.query_one("#tab-buffers") is not None


@pytest.mark.asyncio
async def test_ipc_buffers_tab_renders_simple(simple_ipc: Path) -> None:
    """Test that the Buffers tab renders without error for a simple IPC file."""
    reader = IPCReader(simple_ipc)
    app = DatanomyApp(reader)

    async with app.run_test():
        app.query_one("#buffers-content").render()


@pytest.mark.asyncio
async def test_ipc_buffers_tab_renders_complex(complex_ipc: Path) -> None:
    """Test that the Buffers tab handles complex types (string_view, list, struct, large_string, nulls)."""
    reader = IPCReader(complex_ipc)
    app = DatanomyApp(reader)

    async with app.run_test():
        app.query_one("#buffers-content").render()


@pytest.mark.asyncio
async def test_ipc_buffers_tab_renders_multi_batch(multi_batch_ipc: Path) -> None:
    """Test that the Buffers tab renders two batches side by side."""
    reader = IPCReader(multi_batch_ipc)
    app = DatanomyApp(reader)

    async with app.run_test():
        app.query_one("#buffers-content").render()


@pytest.mark.asyncio
async def test_ipc_buffers_tab_renders_empty(empty_ipc: Path) -> None:
    """Test that the Buffers tab handles an IPC file with no record batches."""
    reader = IPCReader(empty_ipc)
    app = DatanomyApp(reader)

    async with app.run_test():
        app.query_one("#buffers-content").render()
