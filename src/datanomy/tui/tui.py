"""Terminal UI for exploring data files."""

from textual.app import App, ComposeResult
from textual.containers import ScrollableContainer
from textual.widgets import Footer, Header, TabbedContent, TabPane

from datanomy.reader.ipc import IPCReader
from datanomy.reader.parquet import ParquetReader
from datanomy.tui.arrow import BuffersTab as IPCBuffersTab
from datanomy.tui.arrow import DataTab as IPCDataTab
from datanomy.tui.arrow import MetadataTab as IPCMetadataTab
from datanomy.tui.arrow import SchemaTab as IPCSchemaTab
from datanomy.tui.arrow import StructureTab as IPCStructureTab
from datanomy.tui.parquet import DataTab, MetadataTab, SchemaTab, StatsTab, StructureTab


class DatanomyApp(App):
    """A Textual app to explore data file anatomy."""

    CSS = """
    TabbedContent {
        height: 1fr;
    }

    TabPane {
        padding: 1;
    }

    #structure-content, #schema-content, #stats-content, #data-content, #buffers-content {
        padding: 1;
    }
    """

    BINDINGS = [("q", "quit", "Quit")]

    def __init__(self, reader: ParquetReader | IPCReader) -> None:
        """
        Initialize the app.

        Parameters
        ----------
            reader: ParquetReader or IPCReader instance
        """
        super().__init__()
        self.reader = reader

    def compose(self) -> ComposeResult:
        """
        Create child widgets for the app.

        Yields
        ------
            ComposeResult: Child widgets
        """
        yield Header()
        with TabbedContent():
            if isinstance(self.reader, ParquetReader):
                yield from self._parquet_tabs()
            else:
                yield from self._ipc_tabs()
        yield Footer()

    def _parquet_tabs(self) -> ComposeResult:
        """
        Create Parquet-specific tabs.

        Yields
        ------
            ComposeResult: Parquet tab panes
        """
        assert isinstance(self.reader, ParquetReader)
        with TabPane("Structure", id="tab-structure"):
            yield ScrollableContainer(StructureTab(self.reader))
        with TabPane("Schema", id="tab-schema"):
            yield ScrollableContainer(SchemaTab(self.reader))
        with TabPane("Data", id="tab-data"):
            yield ScrollableContainer(DataTab(self.reader))
        with TabPane("Metadata", id="tab-metadata"):
            yield ScrollableContainer(MetadataTab(self.reader))
        with TabPane("Stats", id="tab-stats"):
            yield ScrollableContainer(StatsTab(self.reader))

    def _ipc_tabs(self) -> ComposeResult:
        """
        Create Arrow IPC-specific tabs.

        Yields
        ------
            ComposeResult: IPC tab panes
        """
        assert isinstance(self.reader, IPCReader)
        with TabPane("Structure", id="tab-structure"):
            yield ScrollableContainer(IPCStructureTab(self.reader))
        with TabPane("Schema", id="tab-schema"):
            yield ScrollableContainer(IPCSchemaTab(self.reader))
        with TabPane("Data", id="tab-data"):
            yield ScrollableContainer(IPCDataTab(self.reader))
        with TabPane("Metadata", id="tab-metadata"):
            yield ScrollableContainer(IPCMetadataTab(self.reader))
        with TabPane("Buffers", id="tab-buffers"):
            yield ScrollableContainer(IPCBuffersTab(self.reader))
