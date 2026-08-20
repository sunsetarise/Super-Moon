from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from supermoon32.qualified import managers
from supermoon34 import endurance


def fake_psutil(rss_bytes: int):
    process = mock.Mock()
    process.memory_info.return_value = SimpleNamespace(rss=rss_bytes)
    return SimpleNamespace(Process=mock.Mock(return_value=process))


def test_sm34_memory_telemetry_without_unix_resource_module():
    fallback = fake_psutil(64 * 1024)
    with mock.patch.object(endurance, "_resource", None), mock.patch.object(
        endurance, "_psutil", fallback
    ):
        assert endurance._max_rss_kib() == 64


def test_sm34_windows_directory_sync_is_safely_skipped(tmp_path: Path):
    with mock.patch.object(endurance.os, "name", "nt"), mock.patch.object(
        endurance.os, "open", side_effect=AssertionError("directory open is invalid on Windows")
    ):
        endurance._fsync_directory(tmp_path)


def test_sm32_memory_telemetry_without_proc_or_unix_resource_module():
    fallback = fake_psutil(96 * 1024)
    with mock.patch("builtins.open", side_effect=OSError("no /proc on Windows")), mock.patch.object(
        managers, "_resource", None
    ), mock.patch.object(managers, "_psutil", fallback):
        assert managers.current_rss_bytes() == 96 * 1024
