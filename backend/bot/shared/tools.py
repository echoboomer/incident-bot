import datetime
import ipaddress
import json
import logging
import random
import string

from typing import Any, List

logger = logging.getLogger(__name__)

random_suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
timestamp_fmt = "%Y-%m-%dT%H:%M:%S %Z"
timestamp_fmt_short = "%d/%m/%Y %H:%M:%S"


def fetch_timestamp(short: bool = False):
    if short:
        return datetime.datetime.now().astimezone().strftime(timestamp_fmt_short)
    return datetime.datetime.now().astimezone().strftime(timestamp_fmt)


def find_index_in_list(lst: List, key: Any, value: Any):
    """Takes a list of dictionaries and returns
    the index value if key matches.
    """
    for i, dic in enumerate(lst):
        if dic[key] == value:
            return i
    return -1


def read_json_from_file(file_path: str) -> Any:
    """
    Opens a json file in the filesystem and returns its data as a dictionary.
    """
    file = open(file_path)
    json_data = json.load(file)
    file.close()
    return json_data


def render_html(file, variables: dict) -> dict:
    """Reads a template file as HTML, replaces vars using a dict,
    and returns HTML
    """
    try:
        with open(file, "r") as f:
            html_data = f.read()
            for k, v in variables.items():
                html_data = html_data.replace(f"{{{k}}}", v)
    except:
        print(f"error when interpolating variables on file {file}: ")
        print(variables)
    return html_data


def render_json(file, variables: dict) -> Any:
    """Reads a template file as JSON, replaces vars using a dict,
    and returns JSON
    """
    try:
        with open(file, "r") as f:
            json_data = f.read()
            for k, v in variables.items():
                json_data = json_data.replace(f"{{{k}}}", v)
    except:
        print(f"error when interpolating variables on file {file}: ")
        print(variables)
    return json.loads(json_data)


def validate_ip_address(address):
    try:
        ipaddress.ip_network(address)
        return True
    except ValueError as error:
        logger.error(error)
        return False
