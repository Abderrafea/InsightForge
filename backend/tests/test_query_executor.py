from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from uuid import UUID

from app.query.executor import SafeQueryExecutor


def test_json_safe_value_conversion() -> None:
    timestamp = datetime(2026, 8, 11, 12, 30, tzinfo=UTC)

    converted = SafeQueryExecutor._to_json_safe(
        {
            "decimal": Decimal("1234567890.1234"),
            "uuid": UUID("12345678-1234-5678-1234-567812345678"),
            "datetime": timestamp,
            "date": date(2026, 8, 11),
            "time": time(12, 30),
            "duration": timedelta(seconds=90),
            "bytes": b"safe",
            "array": [Decimal("2.50")],
        }
    )

    assert converted == {
        "decimal": "1234567890.1234",
        "uuid": "12345678-1234-5678-1234-567812345678",
        "datetime": "2026-08-11T12:30:00+00:00",
        "date": "2026-08-11",
        "time": "12:30:00",
        "duration": 90.0,
        "bytes": "c2FmZQ==",
        "array": ["2.50"],
    }


def test_duplicate_column_names_are_made_unique() -> None:
    assert SafeQueryExecutor._unique_column_names(["id", "name", "id", "id"]) == [
        "id",
        "name",
        "id_2",
        "id_3",
    ]
