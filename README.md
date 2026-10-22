# incremental_line_reader

Reads lines from a file starting at a byte offset and returns the new lines appended since the last read.

```python
from incremental_line_reader import IncrementalLineReader

reader = IncrementalLineReader("/var/log/app.log")
result = reader.read_lines(offset=0)
print(result.lines)              # list of bytes, each including trailing \n
# Persist result.offset_exclusive somewhere. Next call:
result = reader.read_lines(offset=result.offset_exclusive)
```

`read_lines(offset)` returns a `LineReaderResult` — a tuple-subclass with
`.lines`, `.offset` (where the read started), and `.offset_exclusive` (where to
resume next time). It unpacks like a tuple: `lines, _, next_offset = result`.

## Why this exists

For tailing a log or append-only file from where you left off. The key
trade-off: the file is opened and closed on every `read_lines` call. This costs
a little performance but guarantees you always see the current on-disk state —
including truncation or rotation — instead of holding a stale descriptor.

## Awkward edge

A line is only returned once a `\n` terminator is present. If the file ends
mid-write (no `\n`), that partial data is held back and returned on a
subsequent call once the `\n` appears. Only `\n` is treated as a line
terminator; `\r\n` and bare `\r` are not split. If the file is truncated to a
size below your stored offset, `offset_exclusive` is reset to the file's new
size so the next call starts cleanly from the new end.
