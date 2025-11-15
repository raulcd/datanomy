from typing import Any

from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import HorizontalScroll, Vertical
from textual.widgets import DataTable, Static

from datanomy.reader.parquet import ParquetReader
from datanomy.tui.common import create_column_grid
from datanomy.utils import format_size


class BaseParquetTab(Static):
    """Base class for Parquet-specific tab widgets."""

    def __init__(self, reader: ParquetReader) -> None:
        """
        Initialize the tab view.

        Parameters
        ----------
            reader: ParquetReader instance
        """
        super().__init__()
        self.reader = reader

    def compose(self) -> ComposeResult:
        """Render the tab view."""
        content_id = f"{self.__class__.__name__.lower().replace('tab', '')}-content"
        yield Static(self.render_tab_content(), id=content_id)

    def render_tab_content(self) -> Group:
        """
        Render the tab content. Must be implemented by subclasses.

        Returns
        -------
            Group: Rich renderable content
        """
        raise NotImplementedError("Subclasses must implement render_tab_content()")


class StructureTab(BaseParquetTab):
    """Widget displaying Parquet file structure."""

    def _header(self) -> Panel:
        """
        Create Text for Parquet Header information.

        Returns
        -------
            Panel: Rich Panel with Parquet Header representation
        """
        header_text = Text()
        header_text.append("Magic Number: PAR1\n", style="yellow")
        header_text.append("Size: 4 bytes")
        return Panel(
            header_text,
            title="Header",
            border_style="yellow",
        )

    def _file_info(self) -> Text:
        """
        Create Text for Parquet File information.

        Returns
        -------
            Text: Rich Text with File Information representation
        """
        file_size_str = format_size(self.reader.file_size)

        # File info panel
        file_info = Text()
        file_info.append("File: ", style="bold")
        file_info.append(f"{self.reader.file_path.name}\n")
        file_info.append("Size: ", style="bold")
        file_info.append(file_size_str)
        return file_info

    def _row_groups(self) -> list[Panel]:
        """
        Create Panels for each Row Group.

        Returns
        -------
            list[Panel]: List of Rich Panels for Row Groups
        """
        # Row groups
        row_group_panels: list[Panel] = []
        for i in range(self.reader.num_row_groups):
            rg = self.reader.get_row_group_info(i)

            # Calculate compressed and uncompressed sizes
            compressed_sum = sum(
                rg.column(j).total_compressed_size for j in range(rg.num_columns)
            )
            uncompressed_sum = rg.total_byte_size  # This is the uncompressed size

            # Check if any column is compressed
            has_compression = any(
                rg.column(j).compression != "UNCOMPRESSED"
                for j in range(rg.num_columns)
            )

            compressed_str = format_size(compressed_sum)
            uncompressed_str = format_size(uncompressed_sum)

            # Summary info
            rg_summary = Text()
            rg_summary.append(f"Rows: {rg.num_rows:,}\n")
            if has_compression:
                rg_summary.append(f"Compressed: {compressed_str}\n")
                rg_summary.append(f"Uncompressed: {uncompressed_str}\n")
                # Calculate compression ratio
                if uncompressed_sum > 0:
                    compression_pct = (1 - compressed_sum / uncompressed_sum) * 100
                    rg_summary.append(
                        f"Compression: {compression_pct:.1f}%\n",
                        style="green" if compression_pct > 0 else "yellow",
                    )
            else:
                rg_summary.append(f"Size: {compressed_str}\n")
            rg_summary.append(f"Columns: {rg.num_columns}\n")

            # Create column chunk table
            max_cols_to_show = 20  # Limit display for files with many columns
            cols_to_display = min(rg.num_columns, max_cols_to_show)

            # Create a table with 3 columns
            col_table = create_column_grid(num_columns=3)

            # Build rows of column panels
            cols_per_row = 3
            for row_idx in range(0, cols_to_display, cols_per_row):
                row_panels: list[Panel | Text] = []
                for col_offset in range(cols_per_row):
                    col_idx = row_idx + col_offset
                    if col_idx < cols_to_display:
                        col = rg.column(col_idx)
                        col_compressed_str = format_size(col.total_compressed_size)
                        col_name = col.path_in_schema
                        is_compressed = col.compression != "UNCOMPRESSED"

                        col_text = Text()
                        if is_compressed:
                            col_uncompressed_str = format_size(
                                col.total_uncompressed_size
                            )
                            col_text.append(
                                f"Compressed: {col_compressed_str}\n", style="dim"
                            )
                            col_text.append(
                                f"Uncompressed: {col_uncompressed_str}\n", style="dim"
                            )
                            # Calculate compression ratio for this column
                            if col.total_uncompressed_size > 0:
                                col_compression_pct = (
                                    1
                                    - col.total_compressed_size
                                    / col.total_uncompressed_size
                                ) * 100
                                ratio_style = (
                                    "green" if col_compression_pct > 0 else "yellow"
                                )
                                col_text.append(
                                    f"Ratio: {col_compression_pct:.1f}%\n",
                                    style=ratio_style,
                                )
                        else:
                            col_text.append(
                                f"Size: {col_compressed_str}\n", style="dim"
                            )
                        col_text.append(f"Codec: {col.compression}\n", style="dim")
                        col_text.append(f"Type: {col.physical_type}", style="dim")

                        col_panel = Panel(
                            col_text,
                            title=f"[cyan]{col_name}[/cyan]",
                            border_style="dim",
                            padding=(0, 1),
                        )
                        row_panels.append(col_panel)
                    else:
                        # Empty space for alignment (no visible border)
                        row_panels.append(Text(""))

                col_table.add_row(*row_panels)

            # If too many columns, add note
            if rg.num_columns > max_cols_to_show:
                remaining_text = Text()
                remaining_text.append(
                    f"... and {rg.num_columns - max_cols_to_show} more columns",
                    style="dim italic",
                )
                col_table.add_row(Panel(remaining_text, border_style="dim"), "", "")

            # Combine summary and column table
            rg_content = Group(rg_summary, Text(), col_table)

            panel = Panel(
                rg_content, title=f"[green]Row Group {i}[/green]", border_style="green"
            )
            row_group_panels.append(panel)
        return row_group_panels

    def _index_pages(self) -> list[Panel]:
        """
        Create Panels for Page Indexes if present.

        Returns
        -------
            list[Panel]: List of Rich Panels for Page Indexes
        """
        page_index_size = self.reader.page_index_size
        page_index_panels: list[Panel] = []
        if page_index_size > 0:
            page_index_size_str = format_size(page_index_size)

            # Check what indexes and statistics are actually present
            has_col_index = False
            has_off_index = False
            has_min_max = False
            has_null_count = False
            has_distinct_count = False

            for i in range(self.reader.num_row_groups):
                rg = self.reader.get_row_group_info(i)
                for j in range(rg.num_columns):
                    col = rg.column(j)
                    if col.has_column_index:
                        has_col_index = True
                    if col.has_offset_index:
                        has_off_index = True

                    # Check what statistics are actually present
                    if col.is_stats_set:
                        stats = col.statistics
                        if stats.has_min_max:
                            has_min_max = True
                        if stats.has_null_count:
                            has_null_count = True
                        if stats.has_distinct_count:
                            has_distinct_count = True

            # Create a single parent panel if any indexes exist
            if has_col_index or has_off_index:
                page_index_content: list[Text | Table] = []

                # Total size at the top
                size_text = Text()
                size_text.append(f"Total Size: {page_index_size_str}", style="bold")
                page_index_content.append(size_text)
                page_index_content.append(Text())  # Blank line

                # Create a table for the index sub-panels (2 columns for indexes)
                index_table = Table.grid(padding=(0, 1), expand=True)
                index_table.add_column(ratio=1)
                index_table.add_column(ratio=1)

                index_panels: list[Panel | Text] = []

                # Column Index sub-panel
                if has_col_index:
                    col_index_text = Text()
                    col_index_text.append(
                        "Per-page statistics for filtering\n\n", style="cyan"
                    )
                    col_index_text.append("Contains:\n", style="bold")

                    # Only list statistics that are actually present
                    if has_min_max:
                        col_index_text.append(
                            "• min/max values per page\n", style="dim"
                        )
                    if has_null_count:
                        col_index_text.append("• null_count per page\n", style="dim")
                    if has_distinct_count:
                        col_index_text.append(
                            "• distinct_count per page\n", style="dim"
                        )

                    col_index_text.append("• Enables page-level pruning", style="dim")
                    col_index_panel = Panel(
                        col_index_text,
                        title="[cyan]Column Index[/cyan]",
                        border_style="dim",
                        padding=(0, 1),
                    )
                    index_panels.append(col_index_panel)
                else:
                    index_panels.append(Text(""))

                # Offset Index sub-panel
                if has_off_index:
                    offset_index_text = Text()
                    offset_index_text.append(
                        "Page locations for random access\n\n", style="cyan"
                    )
                    offset_index_text.append("Contains:\n", style="bold")
                    offset_index_text.append("• Page file offsets\n", style="dim")
                    offset_index_text.append("• compressed_page_size\n", style="dim")
                    offset_index_text.append("• first_row_index per page", style="dim")
                    offset_index_panel = Panel(
                        offset_index_text,
                        title="[cyan]Offset Index[/cyan]",
                        border_style="dim",
                        padding=(0, 1),
                    )
                    index_panels.append(offset_index_panel)
                else:
                    index_panels.append(Text(""))

                index_table.add_row(*index_panels)
                page_index_content.append(index_table)

                # Create the parent panel
                page_index_panel = Panel(
                    Group(*page_index_content),
                    title="[magenta]Page Indexes[/magenta]",
                    border_style="magenta",
                )
                page_index_panels.append(page_index_panel)
        return page_index_panels

    def _footer(self) -> Panel:
        """
        Create Text for Parquet Footer information.

        Returns
        -------
            Panel: Rich Panel with Parquet Footer representation
        """
        metadata_size_str = format_size(self.reader.metadata_size)

        footer_text = Text()
        footer_text.append(f"Total Rows: {self.reader.num_rows:,}\n")
        footer_text.append(f"Row Groups: {self.reader.num_row_groups}\n")
        footer_text.append(f"Metadata: {metadata_size_str}\n")
        footer_text.append("Footer Size Field: 4 bytes\n")
        footer_text.append("Magic Number: PAR1", style="yellow")
        footer_text.append(" (4 bytes)")

        return Panel(footer_text, title="[blue]Footer[/blue]", border_style="blue")

    def render_tab_content(self) -> Group:
        """
        Render the Parquet file structure diagram.

        Returns
        -------
            Group: Rich renderable showing file structure
        """
        sections: list[Text | Panel] = [
            self._file_info(),
            Text(),
            self._header(),
            Text(),
        ]
        sections.extend(self._row_groups())
        page_index_panels = self._index_pages()
        if page_index_panels:
            sections.append(Text())
            sections.extend(page_index_panels)
        sections.extend([Text(), self._footer()])

        return Group(*sections)


class SchemaTab(BaseParquetTab):
    """Widget displaying schema information."""

    def _schema_structure(self) -> Panel:
        """
        Create Panel for Parquet schema structure (Thrift-like representation).

        Returns
        -------
            Panel: Rich Panel with schema structure
        """
        parquet_schema = self.reader.schema_parquet
        schema_str = str(parquet_schema)

        # Remove the first line (Python object repr)
        schema_lines = schema_str.split("\n")
        clean_schema = (
            "\n".join(schema_lines[1:]) if len(schema_lines) > 1 else schema_str
        )

        # Remove noisy field_id=-1 annotations
        clean_schema = clean_schema.replace(" field_id=-1", "")

        # Remove trailing empty lines
        clean_schema = clean_schema.rstrip()

        return Panel(
            Text(clean_schema, style="dim"),
            title="[yellow]Parquet Schema Structure[/yellow]",
            border_style="yellow",
        )

    def _calculate_column_sizes(self) -> dict[int, tuple[int, int]]:
        """
        Calculate total compressed and uncompressed sizes per column.

        Returns
        -------
            dict[int, tuple[int, int]]: Mapping of column index to (compressed, uncompressed) sizes
        """
        column_sizes: dict[int, tuple[int, int]] = {}
        for rg_idx in range(self.reader.num_row_groups):
            rg = self.reader.get_row_group_info(rg_idx)
            for col_idx in range(rg.num_columns):
                col_chunk = rg.column(col_idx)
                if col_idx not in column_sizes:
                    column_sizes[col_idx] = (0, 0)
                compressed, uncompressed = column_sizes[col_idx]
                column_sizes[col_idx] = (
                    compressed + col_chunk.total_compressed_size,
                    uncompressed + col_chunk.total_uncompressed_size,
                )
        return column_sizes

    def _build_column_info(
        self, col: Any, col_idx: int, column_sizes: dict[int, tuple[int, int]]
    ) -> Text:
        """
        Build text content for a single column's information.

        Parameters
        ----------
            col: Parquet column schema object
            col_idx: Column index
            column_sizes: Dictionary mapping column index to sizes

        Returns
        -------
            Text: Rich Text with column information
        """
        col_text = Text()

        # Show total size
        if col_idx in column_sizes:
            compressed, uncompressed = column_sizes[col_idx]
            if compressed != uncompressed:
                col_text.append("Compressed: ", style="bold")
                col_text.append(f"{format_size(compressed)}\n", style="dim")
                col_text.append("Uncompressed: ", style="bold")
                col_text.append(f"{format_size(uncompressed)}\n", style="dim")

                # Calculate compression ratio
                if uncompressed > 0:
                    compression_pct = (1 - compressed / uncompressed) * 100
                    ratio_style = "green" if compression_pct > 0 else "yellow"
                    col_text.append("Compression: ", style="bold")
                    col_text.append(f"{compression_pct:.1f}%\n", style=ratio_style)
            else:
                col_text.append("Size: ", style="bold")
                col_text.append(f"{format_size(compressed)}\n", style="dim")
            col_text.append("\n")

        # Physical type
        col_text.append("Physical Type: ", style="bold")
        col_text.append(f"{col.physical_type}\n", style="yellow")

        # Logical type (if present and meaningful)
        if col.logical_type is not None and str(col.logical_type) != "None":
            col_text.append("Logical Type: ", style="bold")
            col_text.append(f"{col.logical_type}\n", style="cyan")
        else:
            # Add blank line for alignment
            col_text.append("\n")

        col_text.append("\n")

        # Repetition level
        col_text.append("Max Repetition Level: ", style="bold")
        col_text.append(f"{col.max_repetition_level}\n", style="dim")
        if col.max_repetition_level == 0:
            col_text.append("  → Not repeated (flat value)\n", style="dim italic")
        else:
            col_text.append("  → Repeated (list/nested lists)\n", style="dim italic")

        # Definition level
        col_text.append("Max Definition Level: ", style="bold")
        col_text.append(f"{col.max_definition_level}\n", style="dim")

        # Explain what definition level means
        if col.max_definition_level == 0:
            col_text.append("  → REQUIRED (no nulls allowed)\n", style="dim italic")
        else:
            col_text.append("  → OPTIONAL (value can be null)\n", style="dim italic")

        return col_text

    def _column_details(self) -> Panel:
        """
        Create Panel with column details grid.

        Returns
        -------
            Panel: Rich Panel containing column information in a 3-column grid
        """
        parquet_schema = self.reader.schema_parquet
        num_columns = len(parquet_schema.names)
        column_sizes = self._calculate_column_sizes()

        # Create a table grid for column panels (3 columns wide)
        schema_table = create_column_grid(num_columns=3)

        # Build column panels
        cols_per_row = 3
        for row_idx in range(0, num_columns, cols_per_row):
            row_panels: list[Panel | Text] = []

            for col_offset in range(cols_per_row):
                col_idx = row_idx + col_offset
                if col_idx < num_columns:
                    col = parquet_schema.column(col_idx)
                    name = parquet_schema.names[col_idx]

                    # Build column info using helper
                    col_text = self._build_column_info(col, col_idx, column_sizes)

                    col_panel = Panel(
                        col_text,
                        title=f"[green]{name}[/green]",
                        border_style="cyan",
                        padding=(0, 1),
                    )
                    row_panels.append(col_panel)
                else:
                    # Empty space for alignment
                    row_panels.append(Text(""))

            schema_table.add_row(*row_panels)

        return Panel(
            schema_table,
            title="[cyan]Column Details[/cyan]",
            border_style="cyan",
        )

    def render_tab_content(self) -> Group:
        """
        Render schema information.

        Returns
        -------
            Group: Rich renderable showing Parquet schema as column panels and structure
        """
        return Group(self._schema_structure(), Text(), self._column_details())


class StatsTab(BaseParquetTab):
    """Widget displaying column statistics."""

    def _has_any_stats(self) -> bool:
        """
        Check if any statistics exist in the file.

        Returns
        -------
            bool: True if at least one column has statistics
        """
        for rg_idx in range(self.reader.num_row_groups):
            rg = self.reader.get_row_group_info(rg_idx)
            for col_idx in range(rg.num_columns):
                col = rg.column(col_idx)
                if col.is_stats_set:
                    return True
        return False

    def _no_stats_message(self) -> Group:
        """
        Create message panel when no statistics are available.

        Returns
        -------
            Group: Rich Group with "no statistics" message
        """
        no_stats_text = Text()
        no_stats_text.append(
            "No statistics found in this Parquet file.\n\n", style="yellow"
        )
        no_stats_text.append(
            "Statistics can be written during file creation using write options.",
            style="dim",
        )
        return Group(Panel(no_stats_text, title="[yellow]Statistics[/yellow]"))

    def _build_column_stats_text(self, col_idx: int) -> Text:
        """
        Build statistics text for a single column across all row groups.

        Parameters
        ----------
            col_idx: Column index

        Returns
        -------
            Text: Rich Text with column statistics
        """
        col_text = Text()
        has_stats_for_col = False

        for rg_idx in range(self.reader.num_row_groups):
            rg = self.reader.get_row_group_info(rg_idx)
            col_chunk = rg.column(col_idx)

            if col_chunk.is_stats_set:
                has_stats_for_col = True
                stats = col_chunk.statistics

                # Row group header
                if self.reader.num_row_groups > 1:
                    col_text.append(f"Row Group {rg_idx}:\n", style="bold cyan")

                # Number of values (always present when stats are set)
                col_text.append("  num_values: ", style="bold")
                col_text.append(f"{stats.num_values:,}\n", style="cyan")

                # Min/Max
                if stats.has_min_max:
                    col_text.append("  min: ", style="bold")
                    col_text.append(f"{stats.min}\n", style="green")
                    col_text.append("  max: ", style="bold")
                    col_text.append(f"{stats.max}\n", style="green")

                # Null count
                if stats.has_null_count:
                    col_text.append("  null_count: ", style="bold")
                    col_text.append(f"{stats.null_count:,}\n", style="yellow")

                # Distinct count
                if stats.has_distinct_count:
                    col_text.append("  distinct_count: ", style="bold")
                    col_text.append(f"{stats.distinct_count:,}\n", style="magenta")

                # Add spacing between row groups
                if rg_idx < self.reader.num_row_groups - 1:
                    col_text.append("\n")

        # If no statistics for this column, show message
        if not has_stats_for_col:
            col_text.append("No statistics available", style="dim yellow")

        return col_text

    def _build_stats_grid(self) -> Table:
        """
        Build the statistics grid with equal-height panels.

        Returns
        -------
            Table: Rich Table grid with column statistics
        """
        num_columns = self.reader.metadata.num_columns
        stats_table = create_column_grid(num_columns=3)

        # Build statistics panels per column
        cols_per_row = 3
        for row_idx in range(0, num_columns, cols_per_row):
            row_texts: list[Text] = []

            # First pass: build all text content
            for col_offset in range(cols_per_row):
                col_idx = row_idx + col_offset
                if col_idx < num_columns:
                    row_texts.append(self._build_column_stats_text(col_idx))
                else:
                    row_texts.append(Text(""))

            # Calculate max height (number of lines) in this row
            max_lines = max(
                len(str(t).split("\n")) for t in row_texts if str(t).strip()
            )

            # Second pass: pad texts to equal height and create panels
            row_panels: list[Panel | Text] = []
            for col_offset in range(cols_per_row):
                col_idx = row_idx + col_offset
                if col_idx < num_columns:
                    col_name = self.reader.schema_parquet.names[col_idx]
                    col_text = row_texts[col_offset]

                    # Pad with empty lines to match max_lines
                    current_lines = len(str(col_text).split("\n"))
                    for _ in range(max_lines - current_lines):
                        col_text.append("\n")

                    col_panel = Panel(
                        col_text,
                        title=f"[green]{col_name}[/green]",
                        border_style="cyan",
                        padding=(0, 1),
                        expand=True,
                    )
                    row_panels.append(col_panel)
                else:
                    # Empty space for alignment
                    row_panels.append(Text(""))

            stats_table.add_row(*row_panels)

        return stats_table

    def render_tab_content(self) -> Group:
        """
        Render column statistics.

        Returns
        -------
            Group: Rich renderable showing statistics per column
        """
        if not self._has_any_stats():
            return self._no_stats_message()

        return Group(self._build_stats_grid())


class DataTab(BaseParquetTab):
    """Widget displaying data preview."""

    def __init__(self, reader: ParquetReader, num_rows: int = 50) -> None:
        """
        Initialize the data view.

        Parameters
        ----------
            reader: ParquetReader instance
            num_rows: Number of rows to display (default: 50)
        """
        super().__init__(reader)
        self.num_rows = num_rows
        self.id = "data-content"

    @staticmethod
    def _format_value(value: Any, max_length: int = 50) -> str:
        """
        Format a value for display.

        Parameters
        ----------
            value: The value to format
            max_length: Maximum string length before truncation

        Returns
        -------
            str: Formatted value string
        """
        if value is None:
            return "NULL"

        value_str = str(value)
        if len(value_str) > max_length:
            return f"{value_str[: max_length - 3]}..."
        return value_str

    def _read_data(self) -> tuple[Any, int, int]:
        """
        Read and slice data from Parquet file.

        Returns
        -------
            tuple[Any, int, int]: (table, num_rows_display, total_rows)

        Raises
        ------
            Exception: If reading data fails
        """
        table = self.reader.parquet_file.read(columns=None, use_threads=True)

        # Limit to requested number of rows
        if len(table) > self.num_rows:
            table = table.slice(0, self.num_rows)

        num_rows_display = len(table)
        total_rows = self.reader.num_rows

        return table, num_rows_display, total_rows

    def _create_data_table(self, table: Any, num_rows_display: int) -> DataTable:
        """
        Create a Textual ``DataTable`` widget populated with preview rows.

        Parameters
        ----------
            table: PyArrow table slice for preview rendering
            num_rows_display: Number of rows to include in the table

        Returns
        -------
            DataTable: Configured widget ready for display
        """

        data_table: DataTable = DataTable(id="data-preview-table", zebra_stripes=True)
        data_table.border_title = "Data Preview"
        data_table.styles.border = ("round", "cyan")
        data_table.styles.width = "auto"

        columns = list(table.schema.names)
        if not columns:
            return data_table

        min_width = max(80, sum(max(12, len(name) + 2) for name in columns))
        data_table.styles.min_width = min_width

        data_table.add_columns(*columns)

        for row_idx in range(num_rows_display):
            row_values: list[str | Text] = []
            for name in columns:
                value = table[name][row_idx].as_py()
                formatted_value = self._format_value(value)
                if value is None:
                    row_values.append(Text(formatted_value, style="dim yellow"))
                else:
                    row_values.append(formatted_value)
            data_table.add_row(*row_values)

        return data_table

    def compose(self) -> ComposeResult:
        """
        Compose widgets for the data preview tab.

        Yields
        ------
            ComposeResult: Child widgets making up the tab content
        """

        try:
            table, num_rows_display, total_rows = self._read_data()
        except Exception as e:
            error_text = Text()
            error_text.append(f"Error reading data: {e}", style="red")
            yield Static(Panel(error_text, title="[red]Error[/red]"), id="data-content")
            return

        columns = list(table.schema.names)
        data_widget: DataTable | None = None
        empty_panel: Panel | None = None

        if columns:
            data_widget = self._create_data_table(table, num_rows_display)
        else:
            empty_text = Text("Parquet table has no columns", style="yellow")
            empty_panel = Panel(
                empty_text,
                title="[cyan]Data Preview[/cyan]",
                border_style="cyan",
            )

        header_text = Text()
        header_text.append(
            f"Showing {num_rows_display:,} of {total_rows:,} rows", style="cyan bold"
        )

        with Vertical(id="data-content"):
            yield Static(header_text)

            if data_widget is not None:
                with HorizontalScroll():
                    yield data_widget
            elif empty_panel is not None:
                yield Static(empty_panel)


class MetadataTab(BaseParquetTab):
    """Display Parquet file metadata."""

    def _calculate_total_sizes(self) -> tuple[int, int]:
        """
        Calculate total compressed and uncompressed sizes across all row groups.

        Returns
        -------
            tuple[int, int]: (total_compressed, total_uncompressed)
        """
        total_compressed = 0
        total_uncompressed = 0
        metadata = self.reader.metadata

        for rg_idx in range(metadata.num_row_groups):
            rg = metadata.row_group(rg_idx)
            for col_idx in range(rg.num_columns):
                col = rg.column(col_idx)
                total_compressed += col.total_compressed_size
                total_uncompressed += col.total_uncompressed_size

        return total_compressed, total_uncompressed

    def _file_info(self) -> Panel:
        """
        Create Panel with file information.

        Returns
        -------
            Panel: Rich Panel with file metadata information
        """
        metadata = self.reader.metadata
        file_info = Text()

        # Basic metadata
        file_info.append("Created by: ", style="bold")
        file_info.append(f"{metadata.created_by}\n", style="cyan")
        file_info.append("Format version: ", style="bold")
        file_info.append(f"{metadata.format_version}\n", style="cyan")
        file_info.append("Metadata size: ", style="bold")
        file_info.append(f"{format_size(metadata.serialized_size)}\n", style="cyan")
        file_info.append("\n")

        # Data statistics
        file_info.append("Total rows: ", style="bold")
        file_info.append(f"{metadata.num_rows:,}\n", style="green")
        file_info.append("Total columns: ", style="bold")
        file_info.append(f"{metadata.num_columns}\n", style="green")
        file_info.append("Row groups: ", style="bold")
        file_info.append(f"{metadata.num_row_groups}\n", style="green")

        # Size information
        total_compressed, total_uncompressed = self._calculate_total_sizes()
        file_info.append("\n")
        file_info.append("Total compressed size: ", style="bold")
        file_info.append(f"{format_size(total_compressed)}\n", style="cyan")
        file_info.append("Total uncompressed size: ", style="bold")
        file_info.append(f"{format_size(total_uncompressed)}\n", style="cyan")

        if total_uncompressed > 0:
            compression_pct = (1 - total_compressed / total_uncompressed) * 100
            ratio_style = "green" if compression_pct > 0 else "yellow"
            file_info.append("Compression ratio: ", style="bold")
            file_info.append(f"{compression_pct:.1f}%\n", style=ratio_style)

        return Panel(
            file_info,
            title="[cyan]File Information[/cyan]",
            border_style="cyan",
        )

    def _custom_metadata(self) -> Panel:
        """
        Create Panel with custom metadata.

        Returns
        -------
            Panel: Rich Panel with custom metadata key-value pairs
        """
        metadata = self.reader.metadata
        custom_metadata = Text()

        if metadata.metadata:
            for key, value in metadata.metadata.items():
                # Keys and values are bytes
                key_str = key.decode("utf-8") if isinstance(key, bytes) else key
                value_str = value.decode("utf-8") if isinstance(value, bytes) else value

                custom_metadata.append(f"{key_str}:\n", style="bold yellow")
                # For long values like ARROW:schema, just show truncated
                if len(value_str) > 200:
                    custom_metadata.append(
                        f"  {value_str[:200]}...\n", style="dim white"
                    )
                    custom_metadata.append(
                        f"  (truncated, {len(value_str)} bytes total)\n",
                        style="italic magenta",
                    )
                else:
                    custom_metadata.append(f"  {value_str}\n", style="white")
                custom_metadata.append("\n")
        else:
            custom_metadata.append("No custom metadata found", style="dim yellow")

        return Panel(
            custom_metadata,
            title="[cyan]Custom Metadata[/cyan]",
            border_style="cyan",
        )

    def render_tab_content(self) -> Group:
        """
        Render file metadata.

        Returns
        -------
            Group: Rich renderable showing file and custom metadata
        """
        return Group(self._file_info(), Text(), self._custom_metadata())
