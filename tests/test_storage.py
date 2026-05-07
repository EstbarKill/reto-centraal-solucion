from datetime import date

from src.storage import _blob_path_for_date



def test_blob_path_for_date():
    result = _blob_path_for_date(
        "PUMP-1001",
        date(2026, 5, 7),
    )

    assert result == (
        "machine_id=PUMP-1001/year=2026/month=05/day=07/events.ndjson"
    )