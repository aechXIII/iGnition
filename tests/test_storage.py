"""Tests for atomic file storage."""
import pathlib

from ignition.core.storage import atomic_write_text


class TestAtomicWriteText:
    def test_creates_file(self, tmp_path: pathlib.Path):
        p = tmp_path / "out.txt"
        atomic_write_text(p, "hello", encoding="utf-8")
        assert p.read_text(encoding="utf-8") == "hello"

    def test_creates_parent_dirs(self, tmp_path: pathlib.Path):
        p = tmp_path / "a" / "b" / "out.txt"
        atomic_write_text(p, "world", encoding="utf-8")
        assert p.exists()

    def test_overwrites_existing(self, tmp_path: pathlib.Path):
        p = tmp_path / "out.txt"
        p.write_text("old", encoding="utf-8")
        atomic_write_text(p, "new", encoding="utf-8")
        assert p.read_text(encoding="utf-8") == "new"

    def test_unicode_content(self, tmp_path: pathlib.Path):
        p = tmp_path / "out.txt"
        content = "zażółć gęślą jaźń 🏁"
        atomic_write_text(p, content, encoding="utf-8")
        assert p.read_text(encoding="utf-8") == content

    def test_no_temp_file_left_on_success(self, tmp_path: pathlib.Path):
        p = tmp_path / "out.txt"
        atomic_write_text(p, "data", encoding="utf-8")
        files = list(tmp_path.iterdir())
        assert files == [p]
