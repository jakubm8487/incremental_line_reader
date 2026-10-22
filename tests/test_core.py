import os
import tempfile
import unittest

from incremental_line_reader import IncrementalLineReader, LineReaderResult


class TestIncrementalLineReader(unittest.TestCase):

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.file_path = os.path.join(self._tmpdir.name, "log.txt")

    def _write_bytes(self, data, mode="ab"):
        with open(self.file_path, mode) as f:
            f.write(data)

    def test_read_from_empty_file(self):
        self._write_bytes(b"", mode="wb")
        reader = IncrementalLineReader(self.file_path)
        result = reader.read_lines()
        self.assertEqual(result.lines, [])
        self.assertEqual(result.offset, 0)
        self.assertEqual(result.offset_exclusive, 0)

    def test_read_single_line_with_trailing_newline(self):
        self._write_bytes(b"hello\n", mode="wb")
        reader = IncrementalLineReader(self.file_path)
        result = reader.read_lines()
        self.assertEqual(result.lines, [b"hello\n"])
        self.assertEqual(result.offset, 0)
        self.assertEqual(result.offset_exclusive, 6)

    def test_incomplete_line_without_newline_is_not_returned(self):
        self._write_bytes(b"incomplete", mode="wb")
        reader = IncrementalLineReader(self.file_path)
        result = reader.read_lines()
        self.assertEqual(result.lines, [])
        self.assertEqual(result.offset, 0)
        self.assertEqual(result.offset_exclusive, 0)

    def test_incomplete_line_completed_on_next_read(self):
        self._write_bytes(b"part1", mode="wb")
        reader = IncrementalLineReader(self.file_path)
        result = reader.read_lines()
        self.assertEqual(result.lines, [])

        self._write_bytes(b"part2\n", mode="ab")
        result = reader.read_lines(result.offset_exclusive)
        self.assertEqual(result.lines, [b"part1part2\n"])
        self.assertEqual(result.offset_exclusive, 11)

    def test_incremental_reads_over_multiple_appends(self):
        self._write_bytes(b"a\n", mode="wb")
        reader = IncrementalLineReader(self.file_path)

        r1 = reader.read_lines(0)
        self.assertEqual(r1.lines, [b"a\n"])

        self._write_bytes(b"bb\n", mode="ab")
        r2 = reader.read_lines(r1.offset_exclusive)
        self.assertEqual(r2.lines, [b"bb\n"])

        self._write_bytes(b"ccc\n", mode="ab")
        r3 = reader.read_lines(r2.offset_exclusive)
        self.assertEqual(r3.lines, [b"ccc\n"])

    def test_read_multiple_lines_at_once(self):
        self._write_bytes(b"one\ntwo\nthree\n", mode="wb")
        reader = IncrementalLineReader(self.file_path)
        result = reader.read_lines()
        self.assertEqual(result.lines, [b"one\n", b"two\n", b"three\n"])
        self.assertEqual(result.offset_exclusive, 14)

    def test_no_new_lines_since_last_read(self):
        self._write_bytes(b"line\n", mode="wb")
        reader = IncrementalLineReader(self.file_path)
        r1 = reader.read_lines()
        r2 = reader.read_lines(r1.offset_exclusive)
        self.assertEqual(r2.lines, [])
        self.assertEqual(r2.offset_exclusive, r1.offset_exclusive)

    def test_resume_from_explicit_offset(self):
        self._write_bytes(b"first\nsecond\n", mode="wb")
        reader = IncrementalLineReader(self.file_path)
        result = reader.read_lines(offset=6)
        self.assertEqual(result.lines, [b"second\n"])
        self.assertEqual(result.offset, 6)
        self.assertEqual(result.offset_exclusive, 13)

    def test_file_truncated_resets_offset(self):
        self._write_bytes(b"original content line\n", mode="wb")
        reader = IncrementalLineReader(self.file_path)
        r1 = reader.read_lines()
        self.assertEqual(r1.lines, [b"original content line\n"])

        # Truncate the file to something smaller than the stored offset.
        self._write_bytes(b"new\n", mode="wb")
        result = reader.read_lines(r1.offset_exclusive)
        self.assertEqual(result.lines, [])
        self.assertEqual(result.offset, r1.offset_exclusive)
        self.assertEqual(result.offset_exclusive, 4)

    def test_file_does_not_exist(self):
        reader = IncrementalLineReader(os.path.join(self._tmpdir.name, "nope.txt"))
        result = reader.read_lines()
        self.assertEqual(result.lines, [])
        self.assertEqual(result.offset, 0)
        self.assertEqual(result.offset_exclusive, 0)

    def test_empty_data_between_newlines(self):
        self._write_bytes(b"a\n\nb\n", mode="wb")
        reader = IncrementalLineReader(self.file_path)
        result = reader.read_lines()
        self.assertEqual(result.lines, [b"a\n", b"\n", b"b\n"])

    def test_lines_include_trailing_newline_bytes(self):
        self._write_bytes(b"hello\nworld\n", mode="wb")
        reader = IncrementalLineReader(self.file_path)
        result = reader.read_lines()
        for line in result.lines:
            self.assertTrue(line.endswith(b"\n"))

    def test_result_is_iterable_and_unpackable(self):
        self._write_bytes(b"x\n", mode="wb")
        reader = IncrementalLineReader(self.file_path)
        result = reader.read_lines()
        lines, offset, offset_exclusive = result
        self.assertEqual(lines, [b"x\n"])
        self.assertEqual(offset, 0)
        self.assertEqual(offset_exclusive, 2)

    def test_result_repr_is_informative(self):
        self._write_bytes(b"x\n", mode="wb")
        reader = IncrementalLineReader(self.file_path)
        result = reader.read_lines()
        rep = repr(result)
        self.assertIn("lines", rep)
        self.assertIn("offset", rep)


if __name__ == "__main__":
    unittest.main()
