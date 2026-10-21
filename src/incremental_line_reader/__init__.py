"""incremental_line_reader: read lines appended to a file since the last read."""

from .core import IncrementalLineReader, LineReaderResult

__all__ = ["IncrementalLineReader", "LineReaderResult"]
