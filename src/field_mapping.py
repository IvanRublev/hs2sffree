"""
This module contains mappings from HubSpot to Salesforce fields used when
transforming HubSpot deal objects into Salesforce Opportunity fields.

Notes
-----
- Keys are expected to be in HubSpot's API respoinse JSON objects
  and values are the human-readable Salesforce labels.

- If HubSpot introduces new types or stages, extend these dictionaries and
  ensure Salesforce picklist values exist or are created beforehand.
"""

from collections import OrderedDict
from datetime import datetime

from src.infra.address_parser import parse_address
from src.models.field_map import FieldMap

ACCOUNTS_NAME_COLUMN = "Account Name"
COMPANY_ID_COLUMN = "company_id"

DEALTYPE_MAP = {
    "newbusiness": "New Business",
    "existingbusiness": "Existing Business",
}

DEALSTAGE_MAP = {
    "qualifiedtobuy": "Qualify",
    "presentationscheduled": "Meet & Present",
    "appointmentscheduled": "Propose",
    "decisionmakerboughtin": "Negotiate",
    "closedwon": "Closed Won",
    "closedlost": "Closed Lost",
}


def _split_street_from_city_zip_code(address: str, _ctx: FieldMap.Context):
    """Parses adderess, returns street and context with city and zip code"""
    city, street, zip_code = parse_address(address)
    return street, {"city": city, "zip_code": zip_code}


ACCOUNT_FIELDS_MAP = OrderedDict(
    [
        # ACCOUNTS_NAME_COLUMN is required in Salesforce, and in companies_db module
        (ACCOUNTS_NAME_COLUMN, FieldMap("name", required=True)),
        ("Account Website", FieldMap("domain", lambda domain, _: "https://" + domain)),
        ("Account Billing Street", FieldMap("address", _split_street_from_city_zip_code)),
        ("Account Billing City", FieldMap("address", lambda _, ctx: ctx["city"])),
        ("Account Billing Zip/Postal Code", FieldMap("address", lambda _, ctx: ctx["zip_code"])),
        ("Account Billing Country", FieldMap("country")),
    ]
)


def _get_company_id_from_assoc(associations_companies_results: dict, _ctx: dict):
    company_id = None
    if associations_companies_results and len(associations_companies_results) > 0:
        company_id = associations_companies_results[0].get("id")
    return company_id


CONTACT_FIELDS_MAP = OrderedDict(
    [
        # we need COMPANY_ID_COLUMN because the link to account is required in Salesforce
        (COMPANY_ID_COLUMN, FieldMap("associations_companies_results", _get_company_id_from_assoc, required=True)),
        ("Contact First Name", FieldMap("firstname", required=True)),
        ("Contact Last Name", FieldMap("lastname", required=True)),
        ("Contact Phone", FieldMap("phone")),
        ("Contact Email", FieldMap("email")),
        ("Contact Title", FieldMap("jobtitle")),
        ("Contact Mailing Street", FieldMap("address", _split_street_from_city_zip_code)),
        ("Contact Mailing City", FieldMap("address", lambda _, ctx: ctx["city"])),
        ("Contact Mailing Zip/Postal Code", FieldMap("address", lambda _, ctx: ctx["zip_code"])),
        ("Contact Mailing Country", FieldMap("country")),
    ]
)


def _get_closedate(closedate: str, _ctx: dict):
    if closedate:
        # convert "2020-01-01T12:00:00Z" -> "2020-01-01 12:00:00" by removing Z and replacing T with space
        closedate = closedate.replace("T", " ").replace("Z", "")
    else:
        # set todays midnight as closedate
        closedate = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).strftime("%Y-%m-%d %H:%M:%S")
    return closedate


DEAL_FIELDS_MAP = OrderedDict(
    [
        (COMPANY_ID_COLUMN, FieldMap("associations_companies_results", _get_company_id_from_assoc, required=True)),
        ("Name", FieldMap("dealname", required=True)),
        ("Type", FieldMap("dealtype", lambda val, _: DEALTYPE_MAP.get(val))),
        ("Stage", FieldMap("dealstage", lambda val, _: DEALSTAGE_MAP.get(val), required=True)),
        ("Amount", FieldMap("amount")),
        ("Close Date", FieldMap("closedate", _get_closedate, required=True)),
    ]
)

# Functions to operate fields map


def build_attrs(fields_map: OrderedDict[str, FieldMap], hs_record: dict) -> dict:
    """Returns attributes dictionary to be persisted in Salesforce from the given HubSpot record"""
    attrs = {}
    ctx = {}
    for sf_label, field in fields_map.items():
        if field.transform_fun:
            # apply transformation
            result = field.transform_fun(hs_record.get(field.src_field), ctx)
            # transform functions may return either a (value, context_update) tuple
            # or a plain value; handle both cases and merge any returned context.
            if isinstance(result, tuple):
                value, new_ctx = result
                ctx.update(new_ctx)
            else:
                value = result
        else:
            # no transform function, return source value as is
            value = hs_record.get(field.src_field)

        attrs[sf_label] = value

    return attrs


def first_missing_field(fields_map: OrderedDict[str, FieldMap], attrs: dict) -> tuple[str, str] | None:
    """Returns first missing HubSpot field with Salesforce label that is required according to the fields_map"""
    for sf_label, field in fields_map.items():
        if field.required and not attrs.get(sf_label):
            return field.src_field, sf_label
    return None
