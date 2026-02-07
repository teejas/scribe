from datetime import datetime, timezone

from scribe.db import APPLE_EPOCH_OFFSET, _apple_timestamp_to_datetime


def test_apple_epoch_conversion():
    # Jan 1, 2025 00:00:00 UTC in Apple epoch
    apple_ts = datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp() - APPLE_EPOCH_OFFSET
    result = _apple_timestamp_to_datetime(apple_ts)
    assert result.year == 2025
    assert result.month == 1
    assert result.day == 1


def test_apple_epoch_offset_value():
    # The offset is the number of seconds between Unix epoch and Apple epoch
    # Unix epoch: Jan 1, 1970. Apple epoch: Jan 1, 2001. Difference: 31 years.
    assert APPLE_EPOCH_OFFSET == 978307200
