# Datanomy

> Explore the anatomy of your columnar data files

**Datanomy** is a terminal-based tool for inspecting and understanding data files.
It provides an interactive view of your data's structure, metadata, and internal organization.

Currently only Parquet available:

![Parquet demo](https://github.com/user-attachments/assets/87f2f0ad-2eec-480d-b461-370ac3af6122)

## Features for Parquet view

### General Structure

![General Structure](https://github.com/user-attachments/assets/eee4ea85-e5c8-4661-a2e2-0321b26076f1)

### Schema

![Schema](https://github.com/user-attachments/assets/e66087ce-f8b4-439d-b7fe-78da5f5d8a48)

### Data

![Data](https://github.com/user-attachments/assets/cbe278af-0240-4ded-9b0e-704ddb489e71)

### Metadata

![Metadata](https://github.com/user-attachments/assets/a71cf396-8c00-40e2-94de-da38ce4af745)

### Stats

![Stats](https://github.com/user-attachments/assets/f437a6a8-be71-413b-b15f-10b4376df981)

## Installation

```bash
# From PyPI
uv tool install datanomy
## with pip
pip install datanomy

# From source
uv tool install "datanomy @ git+https://github.com/raulcd/datanomy.git"
## cloning the repo 
git clone https://github.com/raulcd/datanomy.git
cd datanomy
uv sync
```

## Usage

```bash
# Run without installing using uvx
uvx datanomy data.parquet

# Inspect a Parquet file
datanomy data.parquet
```

## Keyboard Shortcuts

- `q` - Quit the application

## Development

```bash
# Install dependencies
uv sync

# Run from source
uv run datanomy path/to/file.parquet
```

```bash
# Install dev dependencies
uv sync --extra dev

# Run tests
uv run pytest

# Format code
uv run ruff format .

# Lint
uv run ruff check .

# Lint
uv run mypy .
```

## License

Apache License 2.0

## Contributing

Contributions welcome! Please open an issue or PR.

---

Built with [Textual](https://textual.textualize.io/) and [PyArrow](https://arrow.apache.org/docs/python/)
