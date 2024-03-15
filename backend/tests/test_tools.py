import datetime

from bot.shared.tools import (
    fetch_timestamp,
    fetch_timestamp_from_time_obj,
    timestamp_fmt,
    timestamp_fmt_short,
)


class TestTimeHelpers:
    def test_fetch_timestamp_generates_the_correct_timestamp(self):
        utc_timestamp = fetch_timestamp(timezone="UTC")
        melbourne_timestamp = fetch_timestamp(timezone="Australia/Melbourne")

        parsed_melbourne = datetime.datetime.strptime(
            utc_timestamp[:13], "%Y-%m-%dT%H"
        )
        parsed_utc = datetime.datetime.strptime(
            melbourne_timestamp[:13], "%Y-%m-%dT%H"
        )

        assert (
            parsed_melbourne.hour != parsed_utc.hour
        ), "The timestamps should have different hours when using differnt timezones"

    def test_fetch_timestamp_short(self):
        short_timestamp = fetch_timestamp(short=True, timezone="UTC")

        assert datetime.datetime.strptime(
            short_timestamp, timestamp_fmt_short
        ), "Should be able to reparse the short format"

    def test_fetch_timestamp_from_time_obj(self):
        now = datetime.datetime.now(datetime.UTC)

        now_as_est = fetch_timestamp_from_time_obj(
            now, timezone="Australia/Melbourne"
        )

        now_as_melbourne_datetime = datetime.datetime.strptime(
            now_as_est, timestamp_fmt
        )
        assert now_as_melbourne_datetime.hour != now.hour
