import tempfile
from pathlib import Path

from scribe.ledger import Ledger


def _make_ledger(tmp_path: Path) -> Ledger:
    return Ledger(db_path=tmp_path / "test.db")


def test_new_file_is_not_known(tmp_path):
    ledger = _make_ledger(tmp_path)
    assert not ledger.is_known("/fake/file.m4a")
    assert not ledger.is_processed("/fake/file.m4a")


def test_mark_pending_makes_known(tmp_path):
    ledger = _make_ledger(tmp_path)
    ledger.mark_pending("/fake/file.m4a")
    assert ledger.is_known("/fake/file.m4a")
    assert not ledger.is_processed("/fake/file.m4a")


def test_mark_done(tmp_path):
    ledger = _make_ledger(tmp_path)
    ledger.mark_pending("/fake/file.m4a")
    ledger.mark_processing("/fake/file.m4a")
    ledger.mark_done("/fake/file.m4a")
    assert ledger.is_processed("/fake/file.m4a")


def test_mark_failed_and_retry(tmp_path):
    ledger = _make_ledger(tmp_path)
    ledger.mark_pending("/fake/file.m4a")
    ledger.mark_processing("/fake/file.m4a")
    ledger.mark_failed("/fake/file.m4a", "some error")

    assert not ledger.is_processed("/fake/file.m4a")
    assert ledger.get_failed() == ["/fake/file.m4a"]

    count = ledger.reset_failed()
    assert count == 1
    assert ledger.get_pending() == ["/fake/file.m4a"]


def test_duplicate_pending_is_ignored(tmp_path):
    ledger = _make_ledger(tmp_path)
    ledger.mark_pending("/fake/file.m4a")
    ledger.mark_pending("/fake/file.m4a")  # should not raise
    assert ledger.get_pending() == ["/fake/file.m4a"]


def test_get_pending_returns_multiple(tmp_path):
    ledger = _make_ledger(tmp_path)
    ledger.mark_pending("/fake/a.m4a")
    ledger.mark_pending("/fake/b.m4a")
    pending = ledger.get_pending()
    assert set(pending) == {"/fake/a.m4a", "/fake/b.m4a"}


def test_db_permissions(tmp_path):
    ledger = _make_ledger(tmp_path)
    db_path = tmp_path / "test.db"
    mode = db_path.stat().st_mode & 0o777
    assert mode == 0o600
