from datetime import UTC, datetime, timedelta, timezone

import pytest
from sqlalchemy.dialects import sqlite

from backend.models import UTCDateTime

DIALECT = sqlite.dialect()


def test_utc_datetime_stores_aware_datetime_as_naive_utc() -> None:
    paris_summer = timezone(timedelta(hours=2))
    value = datetime(2026, 10, 9, 16, 0, tzinfo=paris_summer)

    stored = UTCDateTime().process_bind_param(value, DIALECT)

    assert stored == datetime(2026, 10, 9, 14, 0)


def test_utc_datetime_rejects_naive_datetime() -> None:
    with pytest.raises(ValueError, match="naive datetime"):
        UTCDateTime().process_bind_param(datetime(2026, 10, 9, 14, 0), DIALECT)


def test_utc_datetime_reads_naive_value_as_utc() -> None:
    loaded = UTCDateTime().process_result_value(datetime(2026, 10, 9, 14, 0), DIALECT)

    assert loaded == datetime(2026, 10, 9, 14, 0, tzinfo=UTC)


def test_utc_datetime_passes_none_through() -> None:
    assert UTCDateTime().process_bind_param(None, DIALECT) is None
    assert UTCDateTime().process_result_value(None, DIALECT) is None
