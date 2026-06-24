import pytest
from datetime import date, datetime
from app.utils.helpers import parse_date

def test_parse_date_already_date():
    d = date(2026, 6, 24)
    assert parse_date(d) == d

def test_parse_date_datetime():
    dt = datetime(2026, 6, 24, 12, 34, 56)
    assert parse_date(dt) == date(2026, 6, 24)

def test_parse_date_iso_format():
    assert parse_date("2026-06-24") == date(2026, 6, 24)

def test_parse_date_iso_with_time():
    # ISO with space separator and time
    assert parse_date("2026-06-24 15:30:00") == date(2026, 6, 24)

def test_parse_date_t_separator():
    # ISO with T separator and time
    assert parse_date("2026-06-24T15:30:00") == date(2026, 6, 24)
    # T separator and Z/offset
    assert parse_date("2026-06-24T15:30:00Z") == date(2026, 6, 24)

def test_parse_date_alternative_formats():
    assert parse_date("24-06-2026") == date(2026, 6, 24)
    assert parse_date("2026/06/24") == date(2026, 6, 24)

def test_parse_date_invalid_types():
    with pytest.raises(ValueError, match="Cannot parse date from type"):
        parse_date(12345)
    with pytest.raises(ValueError, match="Cannot parse date from type"):
        parse_date(None)

def test_parse_date_invalid_strings():
    with pytest.raises(ValueError, match="Cannot parse date from string"):
        parse_date("not-a-date")
    with pytest.raises(ValueError, match="Cannot parse date from string"):
        parse_date("2026-13-45")

def test_pagination_params_defaults():
    from app.utils.helpers import pagination_params
    # We can invoke it directly to test logic
    params = pagination_params(0, 50)
    assert params["skip"] == 0
    assert params["limit"] == 50

def test_pagination_params_custom():
    from app.utils.helpers import pagination_params
    params = pagination_params(10, 100)
    assert params["skip"] == 10
    assert params["limit"] == 100
