from __future__ import annotations

from io import BytesIO, StringIO
import tempfile
from pathlib import Path
import unittest

from supermoon35.contracts import ValidationError
from supermoon35.framing import encode_file, parse_frames, reconstruct, safe_path


class FramingFuzzTests(unittest.TestCase):
    def test_raw_and_binary_roundtrip(self):
        encoded = encode_file("text/a.txt", b"hello") + encode_file("bin/a.bin", bytes(range(256)))
        rows = list(parse_frames(BytesIO(encoded)))
        self.assertEqual([item.data for item in rows], [b"hello", bytes(range(256))])
        self.assertEqual([item.encoding for item in rows], ["raw", "base64"])

    def test_multiline_is_base64(self):
        row = next(iter(parse_frames(BytesIO(encode_file("a.txt", b"a\nb")))))
        self.assertEqual(row.data, b"a\nb")
        self.assertEqual(row.encoding, "base64")

    def test_safe_path_rejects_traversal(self):
        for value in ("", "/absolute", "../escape", "a/../../escape"):
            with self.assertRaises(ValidationError):
                safe_path(value)

    def test_parser_rejects_malformed_corrupt_duplicate(self):
        valid = encode_file("a", b"x")
        malformed = (
            b"garbage\n", valid.replace(b"<<<END_SM35_FILE>>>", b"BAD"),
            valid.replace(b"bytes=1", b"bytes=2"), valid + valid,
            encode_file("a", b"\x00", force_base64=True).replace(b"AA==", b"!!!!"),
        )
        for payload in malformed:
            with self.assertRaises((ValidationError, UnicodeDecodeError)):
                list(parse_frames(BytesIO(payload)))

    def test_reconstruct_confined_no_overwrite(self):
        payload = encode_file("nested/a.txt", b"data")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outputs = reconstruct(BytesIO(payload), root)
            self.assertEqual(outputs[0].read_bytes(), b"data")
            with self.assertRaises(ValidationError):
                reconstruct(BytesIO(payload), root)


if __name__ == "__main__":
    unittest.main()
