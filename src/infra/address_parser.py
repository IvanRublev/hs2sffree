from typing import Tuple, Optional
import re


def _reduce_character(s: str) -> str:
    # collapse multiple whitespace into single spaces and strip
    return re.sub(r"\s+", " ", s).strip()


def parse_address(address: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    if not address:
        return None, None, None

    # Reduce newlines, and percept newline as comma
    s = re.sub(r"[\r\n]+", ",", address)
    # Reduce spaces and tabs
    s = re.sub(r"\s+", " ", s)
    s = s.strip()
    if not s:
        return None, None, None

    # Split to street and zip_city parts
    street_zip_city_list = s.split(",")

    if len(street_zip_city_list) == 2:
        street = street_zip_city_list[0]
        zip_city = street_zip_city_list[1]
    else:
        # wrongly formatted address
        return None, None, None

    # Split zip and city
    parts = zip_city.strip().split(" ")

    if len(parts) < 2:
        # wrongly formatted address
        return None, None, None

    # First part is always zip
    zip_parts = [parts.pop(0)]

    # Last part is always city
    city_parts = [parts.pop(-1)]
    # Collect middle parts as zip or city
    for idx, part in enumerate(parts):
        if part.isalpha():
            # only letters part and rest are for city
            city_parts = parts[idx:] + city_parts
            break
        else:
            # alphanumeric or numeric parts are for zip
            zip_parts.append(part)

    zip = " ".join(zip_parts)
    city = " ".join(city_parts)

    return (
        city,
        street,
        zip,
    )


def _split_zip_city_no_commas(s: str):
    parts = s.split(" ")

    if len(parts) < 2:
        return None, s

    NUMERICAL = 0
    ALPHA = 1
    ALPHANUMERICAL = 2

    labels = []
    for part in parts:
        if part.isdigit():
            labels.append(NUMERICAL)
        elif part.isalpha():
            labels.append(ALPHA)
        else:
            labels.append(ALPHANUMERICAL)

    # find first numerical token that is not the first or last part — that token is assumed to be zip
    idx = None
    enumeration = reversed(list(enumerate(labels)))
    for i, label in enumeration:
        if label == ALPHA and 0 < i < len(parts) - 1:
            idx = i
            break

    if not idx:
        # find alphanumerical part as zip
        for i, label in enumeration:
            if label == ALPHANUMERICAL and 0 < i < len(parts) - 1:
                idx = i
                break

    if not idx:
        # we don't have zip, take city as last element
        street_list = parts[0 : len(parts) - 1]
        zip = None
        city_list = [parts[len(parts) - 1]]
    else:
        street_list = parts[0:idx]
        zip = parts[idx]
        city_list = parts[idx + 1 :]

    street = " ".join(street_list)
    city = " ".join(city_list)

    return street, zip, city
