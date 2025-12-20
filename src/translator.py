import csv
from enum import Enum
from pathlib import Path
from urllib.parse import urljoin
from typing import Callable

import pyarrow as pa
import pyarrow.parquet as pq

from src.infra.companies_db import (
    DatabaseEngine,
    initialize_db,
    close_db,
    add_companies,
    get_company,
    find_companies_by_name,
)
from src.field_mapping import (
    ACCOUNTS_NAME_COLUMN,
    COMPANY_ID_COLUMN,
    ACCOUNT_FIELDS_MAP,
    CONTACT_FIELDS_MAP,
    DEAL_FIELDS_MAP,
    build_attrs,
    first_missing_field,
)
from src.infra.dict import get_nested
from src.infra.hubspot import download_objects
from src.settings import Settings

CSV_ENCODING = "utf-8"

OPPORTUNITIES_ACCOUNT_NAME_COLUMN = "Next Step"
ERROR_COLUMN = "Error"


class ErrorCode(Enum):
    DUPLICATE_COMPANY = "Duplicate company name (Account Name)"
    MISSING_VALUE = "Missing value $url_path$ $hs_name$ ($sf_label$)"


# ==== Donwload object from HubSpot with mapping to Salesforce object labels


def download_hs_objects(path: str, progress_bytes_callback: Callable[[int], None]):
    token = Settings.hubspot_token
    if not token:
        raise ValueError("No HubSpot token")

    total_bytes = 0

    def update_progress(bytes):
        nonlocal total_bytes
        total_bytes += bytes
        progress_bytes_callback(total_bytes)

    # Download companies
    url = _build_url(Settings.hubspot_api_companies_path, Settings.hubspot_api_companies_params())

    companies_filepath = Path(path) / Settings.companies_filename
    if companies_filepath.exists():
        companies_filepath.unlink()
    engine = initialize_db(str(companies_filepath))

    download_objects(path, token, url, update_progress, lambda json: _persist_company(json, engine))

    close_db(engine)

    # Download contacts
    url = _build_url(Settings.hubspot_api_contacts_path, Settings.hubspot_api_contacts_params())

    contacts_filepath = Path(path) / Settings.contacts_filename
    schema = _build_pyarrow_schema(list(CONTACT_FIELDS_MAP))
    parquet_writer = pq.ParquetWriter(str(contacts_filepath), schema)
    download_objects(path, token, url, update_progress, lambda json: _persist_contact(json, parquet_writer))
    parquet_writer.close()

    # Download deals
    url = _build_url(Settings.hubspot_api_deals_path, Settings.hubspot_api_deals_params())

    deals_filepath = Path(path) / Settings.deals_filename
    schema = _build_pyarrow_schema(list(DEAL_FIELDS_MAP))
    parquet_writer = pq.ParquetWriter(str(deals_filepath), schema)
    download_objects(path, token, url, update_progress, lambda json: _persist_deal(json, parquet_writer))
    parquet_writer.close()


def _build_url(path: str, params: str) -> str:
    url = urljoin(Settings.hubspot_api_base_url, path) + "?" + params
    return url


def _build_pyarrow_schema(field_list: list[str]) -> pa.Schema:
    return pa.schema([pa.field(name, pa.string()) for name in field_list])


def _persist_company(json: dict, engine: DatabaseEngine):
    results = json.get("results") or []
    id_attrs_list = []
    columns = list(ACCOUNT_FIELDS_MAP)
    for res in results:
        company_id = res.get("id")
        properties = res.get("properties")
        attrs = build_attrs(ACCOUNT_FIELDS_MAP, properties)
        id_attrs_list.append((company_id, attrs, attrs[ACCOUNTS_NAME_COLUMN]))

    # Update duplicate flags
    # Check db, we skip transaction boundary because we update database sequentially
    uniq_names = list(set([row[1][columns[0]] for row in id_attrs_list]))
    ids_seen_before = find_companies_by_name(engine, uniq_names)
    name_to_duplicate_db = {name: bool(found) for name, found in zip(uniq_names, ids_seen_before)}
    # track duplicates in the current batch
    added_names = set()
    for idx, row in enumerate(id_attrs_list):
        cid, attrs, name = row
        duplicate = name_to_duplicate_db.get(name, False) or name in added_names
        # append duplicate flag as the last tuple element
        id_attrs_list[idx] = (cid, attrs, name, duplicate)
        added_names.add(name)

    add_companies(engine, id_attrs_list)


def _persist_contact(json: dict, parquet_writer: pq.ParquetWriter):
    results = json.get("results") or []
    rows = []
    for res in results:
        properties = res.get("properties")
        companies_resutls = get_nested(res, ["associations", "companies", "results"])
        properties["associations_companies_results"] = companies_resutls

        one_row = build_attrs(CONTACT_FIELDS_MAP, properties)

        rows.append(one_row)

    table = pa.Table.from_pylist(rows)
    parquet_writer.write_table(table)


def _persist_deal(json: dict, parquet_writer: pq.ParquetWriter):
    results = json.get("results") or []
    rows = []
    for res in results:
        properties = res.get("properties")
        companies_resutls = get_nested(res, ["associations", "companies", "results"])
        properties["associations_companies_results"] = companies_resutls

        one_row = build_attrs(DEAL_FIELDS_MAP, properties)

        rows.append(one_row)

    table = pa.Table.from_pylist(rows)
    parquet_writer.write_table(table)


# ==== Build CSV files that can be loaded into Salesforce


def build_sf_csvs(path: str, progress_callback: Callable[[str], None]):
    check_filenames = [Settings.contacts_filename, Settings.deals_filename, Settings.companies_filename]
    for filename in check_filenames:
        if not (Path(path) / filename).exists():
            raise ValueError(f"No {filename} file found")

    companies_db_path = str(Path(path) / Settings.companies_filename)
    engine = initialize_db(companies_db_path)

    contacts_path = Path(path) / Settings.contacts_filename
    errors_csv_path = Path(path) / Settings.csv_errors_accounts_contacts_filename
    output_csv_path = Path(path) / Settings.csv_accounts_contacts_filename

    accounts_contacts_stats = _build_accounts_contacts(
        engine,
        contacts_path,
        output_csv_path,
        errors_csv_path,
        lambda percent: progress_callback(f"[1/2] {percent:.1f}%"),
    )

    deals_path = Path(path) / Settings.deals_filename
    errors_csv_path = Path(path) / Settings.csv_errors_opportunities_filename
    output_csv_path = Path(path) / Settings.csv_opportunities_filename

    opportunities_stats = _build_opportunities(
        engine,
        deals_path,
        output_csv_path,
        errors_csv_path,
        lambda percent: progress_callback(f"[2/2] {percent:.1f}%"),
    )

    close_db(engine)

    aggregated_stats = {
        "accounts_contacts_total_rows": accounts_contacts_stats["total_rows"],
        "accounts_contacts_valid_rows": accounts_contacts_stats["total_rows"] - accounts_contacts_stats["error_rows"],
        "accounts_contacts_error_rows": accounts_contacts_stats["error_rows"],
        "opportunities_total_rows": opportunities_stats["total_rows"],
        "opportunities_valid_rows": opportunities_stats["total_rows"] - opportunities_stats["error_rows"],
        "opportunities_error_rows": opportunities_stats["error_rows"],
    }
    return aggregated_stats


def _build_accounts_contacts(
    engine: DatabaseEngine,
    contacts_path: Path,
    output_csv_path: Path,
    errors_csv_path: Path,
    progress_percent_callback: Callable[[float], None],
):
    """Build accounts_contacts.csv by merging companies and contact rows and dropping compnany id"""
    account_filed_names = list(ACCOUNT_FIELDS_MAP)
    contact_field_names = list(CONTACT_FIELDS_MAP)
    contact_field_names.remove(COMPANY_ID_COLUMN)

    field_names = account_filed_names + contact_field_names
    error_filed_names = [ERROR_COLUMN] + field_names

    stats = {"total_rows": 0, "error_rows": 0}
    parquet_file = pq.ParquetFile(str(contacts_path))
    rows_count_in_file = parquet_file.metadata.num_rows
    with output_csv_path.open("w", newline="", encoding=CSV_ENCODING) as f:
        with errors_csv_path.open("w", newline="", encoding=CSV_ENCODING) as e:
            output_writer = csv.DictWriter(f, fieldnames=field_names)
            output_writer.writeheader()
            errors_writer = csv.DictWriter(e, fieldnames=error_filed_names)
            errors_writer.writeheader()

            for record_batch in parquet_file.iter_batches():
                for row in record_batch.to_pylist():  # iterating over contacts
                    # Check contacts part
                    error_str = None
                    missing_contact_field = first_missing_field(CONTACT_FIELDS_MAP, row)
                    if missing_contact_field:
                        error_str = _build_missing_field_error(
                            missing_contact_field, Settings.hubspot_api_contacts_path
                        )

                    # we remove company_id anyway because we have company name in target csv
                    company_id = row.pop(COMPANY_ID_COLUMN)
                    # Join accounts part
                    company = None
                    if company_id:
                        company = get_company(engine, company_id)
                        company_attrs = company["attrs"]
                        row = {**company_attrs, **row}

                        if not error_str:
                            missing_company_field = first_missing_field(ACCOUNT_FIELDS_MAP, company_attrs)
                            if missing_company_field:
                                error_str = _build_missing_field_error(
                                    missing_company_field, Settings.hubspot_api_companies_path
                                )
                            elif company["duplicate"]:
                                error_str = ErrorCode.DUPLICATE_COMPANY.value

                    row = _normalize_csv_empty_values(row)

                    if error_str:
                        row = {**row, ERROR_COLUMN: error_str}
                        errors_writer.writerow(row)
                        stats["error_rows"] += 1
                    else:
                        output_writer.writerow(row)
                    stats["total_rows"] += 1

                progress_percent_callback(stats["total_rows"] / rows_count_in_file)

    if 0 == stats["error_rows"]:
        errors_csv_path.unlink()

    return stats


def _build_missing_field_error(missing_field: tuple[str, str], path: str):
    src_field, sf_label = missing_field
    error_str = (
        ErrorCode.MISSING_VALUE.value.replace("$url_path$", path)
        .replace("$hs_name$", src_field)
        .replace("$sf_label$", sf_label)
    )
    return error_str


def _build_opportunities(
    engine: DatabaseEngine,
    deals_path: Path,
    output_csv_path: Path,
    errors_csv_path: Path,
    progress_percent_callback: Callable[[float], None],
):
    """
    Build opportunities.csv by mapping deals.
    We persis company name in the OPPORTUNITIES_ACCOUNT_NAME_COLUMN field for further lookup in Salesforce
    """
    opportunities_field_names = list(DEAL_FIELDS_MAP)
    opportunities_field_names.remove(COMPANY_ID_COLUMN)
    opportunities_field_names.append(OPPORTUNITIES_ACCOUNT_NAME_COLUMN)
    error_filed_names = [ERROR_COLUMN] + opportunities_field_names

    stats = {"total_rows": 0, "error_rows": 0}
    parquet_file = pq.ParquetFile(str(deals_path))
    rows_count_in_file = parquet_file.metadata.num_rows
    with output_csv_path.open("w", newline="", encoding=CSV_ENCODING) as f:
        with errors_csv_path.open("w", newline="", encoding=CSV_ENCODING) as e:
            output_writer = csv.DictWriter(f, fieldnames=opportunities_field_names)
            output_writer.writeheader()
            errors_writer = csv.DictWriter(e, fieldnames=error_filed_names)
            errors_writer.writeheader()

            for record_batch in parquet_file.iter_batches():
                for row in record_batch.to_pylist():  # iterating over deals
                    error_str = None
                    missing_deal_field = first_missing_field(DEAL_FIELDS_MAP, row)
                    if missing_deal_field:
                        error_str = _build_missing_field_error(missing_deal_field, Settings.hubspot_api_deals_path)

                    # we remove compnay_id anyway because we have company name in target csv
                    company_id = row.pop(COMPANY_ID_COLUMN)
                    if company_id:
                        company = get_company(engine, company_id)
                        company_attrs = company["attrs"]
                        company_name = company_attrs[ACCOUNTS_NAME_COLUMN]
                        row[OPPORTUNITIES_ACCOUNT_NAME_COLUMN] = company_name
                        if not error_str:
                            missing_company_field = first_missing_field(ACCOUNT_FIELDS_MAP, company_attrs)
                            if missing_company_field:
                                error_str = _build_missing_field_error(
                                    missing_company_field, Settings.hubspot_api_companies_path
                                )
                            elif company["duplicate"]:
                                error_str = ErrorCode.DUPLICATE_COMPANY.value

                    row = _normalize_csv_empty_values(row)

                    if error_str:
                        row = {**row, ERROR_COLUMN: error_str}
                        errors_writer.writerow(row)
                        stats["error_rows"] += 1
                    else:
                        output_writer.writerow(row)
                    stats["total_rows"] += 1

                progress_percent_callback(stats["total_rows"] / rows_count_in_file)

    if 0 == stats["error_rows"]:
        errors_csv_path.unlink()

    return stats


def _normalize_csv_empty_values(row: dict) -> dict:
    """
    Normalize None -> empty string so CSV cells are empty instead of "None"
    """
    return {k: ("" if v is None else v) for k, v in row.items()}


def cleanup(path: str):
    (Path(path) / Settings.companies_filename).unlink()
    (Path(path) / Settings.contacts_filename).unlink()
    (Path(path) / Settings.deals_filename).unlink()
