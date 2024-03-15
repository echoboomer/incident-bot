import config
import zoneinfo
import ipaddress
import itertools
import random
import string

from datetime import datetime
from iblog import logger
from typing import Any, List


random_suffix = "".join(
    random.choices(string.ascii_lowercase + string.digits, k=6)
)
timestamp_fmt = "%Y-%m-%dT%H:%M:%S %Z"
timestamp_fmt_short = "%d/%m/%Y %H:%M:%S %Z"

application_timezone = config.active.options.get("timezone")


def fetch_timestamp(short: bool = False, timezone: str | None = None) -> str:
    """Return a localized, formatted timestamp using datetime.now()"""
    localized = datetime.now(
        zoneinfo.ZoneInfo(timezone or application_timezone)
    )
    if short:
        return localized.strftime(timestamp_fmt_short)
    return localized.strftime(timestamp_fmt)


def fetch_timestamp_from_time_obj(
    t: datetime, timezone: str | None = None
) -> str:
    """Return a localized, formatted timestamp using datetime.datetime class"""
    return t.astimezone(
        zoneinfo.ZoneInfo(timezone or application_timezone)
    ).strftime(timestamp_fmt)


def find_index_in_list(lst: List, key: Any, value: Any):
    """Takes a list of dictionaries and returns
    the index value if key matches.
    """
    for i, dic in enumerate(lst):
        if dic[key] == value:
            return i
    return -1


def paginate_dictionary(d, per_page):
    """Takes a dictionary and returns per_page items at a time"""
    iterable = iter(d)
    while True:
        p = tuple(itertools.islice(iterable, per_page))
        if not p:
            break
        yield p


def random_string_generator() -> str:
    """Return a random string containing upcase characters and digits"""
    return "".join(
        random.choices(
            string.ascii_uppercase + string.digits,
            k=8,
        )
    )


def validate_date_format_string(fmt: str) -> bool:
    try:
        placeholder_date = datetime.strftime(datetime.now(), fmt)
        datetime.strptime(placeholder_date, fmt)
        return True
    except Exception:
        return False


def validate_ip_address(address: str) -> bool:
    """Validate that a provided string is an IP address"""
    try:
        ipaddress.ip_network(address)
        return True
    except ValueError as error:
        logger.error(error)
        return False


def validate_ip_in_subnet(address: str, subnet: str) -> bool:
    """Return whether or not an IP address is within a subnet"""
    return ipaddress.ip_address(address) in ipaddress.ip_network(subnet)
