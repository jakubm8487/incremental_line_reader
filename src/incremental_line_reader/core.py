"""Core implementation of the incremental line reader."""

from __future__ import annotations

import os


class LineReaderResult(tuple):
    """An immutable, tuple-like result holding (lines, offset, offset_exclusive).

    Why a namedtuple-style class instead of a plain tuple or a dict?
    We need three things back from read_lines: the lines themselves, the
    byte offset where reading started (so callers can persist a stable
    resumption point), and the byte offset just past the final line break
    of the last yielded line (so callers can persist where to resume).
    A plain tuple obscures field meaning; a dict is more awkward to unpack.
    This class supports both attribute access and tuple unpacking, which
    keeps callers concise without sacrificing clarity.
    """

    __slots__ = ()

    def __new__(cls, lines, offset, offset_exclusive):
        return super().__new__(cls, (lines, offset, offset_exclusive))

    @property
    def lines(self):
        return self[0]

    @property
    def offset(self):
        """Byte offset where this read started."""
        return self[1]

    @property
    def offset_exclusive(self):
        """Byte offset to resume from next time (just past the last line break)."""
        return self[2]

    def __repr__(self):
        return (
            f"LineReaderResult(lines={self.lines!r}, "
            f"offset={self.offset!r}, offset_exclusive={self.offset_exclusive!r})"
        )


class IncrementalLineReader:
    """Read lines from a file starting at a byte offset.

    Each call to read_lines returns the new lines that have been appended
    since the last read, along with the offset to use for the next call.

    Design decisions (stated plainly so the behaviour is unambiguous):

    1. A "line" ends with \n. If the file ends without a trailing \n, that
       final data is treated as an incomplete line and is NOT returned
       until a \n appears. This prevents returning a half-written line
       that is still being appended.

    2. \r\n and bare \r are NOT treated as line terminators. Only \n is
       recognised. This matches the most common append-to-file scenario
       (Unix-style logging) and keeps the implementation simple.

    3. The reader never moves backwards. If the file is truncated to a
       size smaller than the stored offset, read_lines returns an empty
       list and sets the next offset to the file's current size, so a
       subsequent call starts fresh from the new end.

    4. The file is opened and closed on every read call. This is the
       trade-off: we sacrifice the performance of a kept-open file
       descriptor for the robustness of always seeing the current file
       state (including rotation or truncation that happened between
       calls). For a tailing / polling use case this is the safer choice.
    """

    def __init__(self, file_path):
        """Initialise the reader for the given file path.

        Args:
            file_path: Path to the file to read. The file need not exist
                yet; read_lines will simply return an empty result.
        """
        self._file_path = os.fspath(file_path)

    @staticmethod
    def _split_lines(data):
        """Split bytes into complete lines ending with \n.

        Returns (lines, remaining) where *lines* is a list of bytes objects
        each including its trailing \n, and *remaining* is the trailing data
        after the last \n (may be empty, or a partial line still being
        written).

        We keep the \n on each returned line because callers may want to
        write the bytes verbatim without re-adding separators. Stripping
        is the caller's responsibility.
        """
        if not data:
            return [], b""
        lines = data.split(b"\n")
        # split always yields at least one element; the last element is
        # the data after the final \n (or the whole input if no \n).
        remaining = lines.pop()
        # Re-attach \n to each complete line so callers get full records.
        complete = [segment + b"\n" for segment in lines]
        return complete, remaining

    def read_lines(self, offset=0):
        """Read new lines from the file starting at *offset*.

        Args:
            offset: Byte offset to resume reading from. Defaults to 0
                (read from the start).

        Returns:
            A LineReaderResult with three fields:
                - lines: list of bytes objects, each including its
                  trailing \n. Empty if no complete new lines exist.
                - offset: the byte offset where this read started
                  (echoed for record-keeping).
                - offset_exclusive: the byte offset to resume from on
                  the next call (just past the last \n that was read).

        If the file does not exist, returns no lines and the offset is
        unchanged (so the caller can retry later). If the file was
        truncated to a size below *offset*, the next offset is reset to
        the file's current size.
        """
        if not os.path.isfile(self._file_path):
            return LineReaderResult([], offset, offset)

        file_size = os.path.getsize(self._file_path)

        # If the file shrank (e.g. rotation/truncation), reset to the new
        # end so the next call starts cleanly.
        if file_size < offset:
            return LineReaderResult([], offset, file_size)

        if file_size == offset:
            return LineReaderResult([], offset, offset)

        with open(self._file_path, "rb") as f:
            f.seek(offset)
            data = f.read()

        lines, remaining = self._split_lines(data)
        new_offset = offset + len(data) - len(remaining)
        return LineReaderResult(lines, offset, new_offset)
