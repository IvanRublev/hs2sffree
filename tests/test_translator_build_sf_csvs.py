import csv
import freezegun
from pathlib import Path
import pytest

import responses

from src.translator import download_hs_objects, build_sf_csvs
from src.settings import Settings
from tests.conftest import mock_hubspot_responses


@responses.activate
def test_fail_build_sf_csvs_given_no_contact_or_deals_or_companies_files(tmp_path):
    with pytest.raises(ValueError) as exc_info:
        build_sf_csvs(tmp_path, lambda _: None)
    assert f"No {Settings.contacts_filename} file found" in str(exc_info)

    (Path(tmp_path) / Settings.contacts_filename).touch()

    with pytest.raises(ValueError) as exc_info:
        build_sf_csvs(tmp_path, lambda _: None)
    assert f"No {Settings.deals_filename} file found" in str(exc_info)

    (Path(tmp_path) / Settings.deals_filename).touch()

    with pytest.raises(ValueError) as exc_info:
        build_sf_csvs(tmp_path, lambda _: None)
    assert f"No {Settings.companies_filename} file found" in str(exc_info)


@responses.activate
@freezegun.freeze_time("2025-12-20")
def test_pass_build_sf_csvs_given_contact_deals_companies_creates_csv_files(tmp_path):
    mock_hubspot_responses()
    download_hs_objects(tmp_path, lambda _: None)

    build_sf_csvs(tmp_path, lambda _: None)

    # Compare accounts_contacts CSV and opportunities CSV in a compact way
    _assert_generated_equals_fixture(
        tmp_path,
        [
            (Settings.csv_accounts_contacts_filename, "tests/fixtures/accounts_contacts.csv"),
            (Settings.csv_opportunities_filename, "tests/fixtures/opportunities.csv"),
        ],
    )

    # Assert that there are no error files created
    accounts_contacts_errors_path = Path(tmp_path) / Settings.csv_errors_accounts_contacts_filename
    assert not accounts_contacts_errors_path.exists()

    csv_opportunities_errors_path = Path(tmp_path) / Settings.csv_errors_opportunities_filename
    assert not csv_opportunities_errors_path.exists()


@responses.activate
@freezegun.freeze_time("2025-12-20")
def test_pass_build_sf_csvs_given_duplicate_companies_skips_them_as_errors(tmp_path):
    mock_hubspot_responses({"comp2": "duplicate_name/companies_p2_duplicate_name.json"})
    download_hs_objects(tmp_path, lambda _: None)

    stats = build_sf_csvs(tmp_path, lambda _: None)

    # Assert stats
    assert 4 == stats["accounts_contacts_total_rows"]
    assert 3 == stats["accounts_contacts_valid_rows"]
    assert 1 == stats["accounts_contacts_error_rows"]
    assert 3 == stats["opportunities_total_rows"]
    assert 2 == stats["opportunities_valid_rows"]
    assert 1 == stats["opportunities_error_rows"]

    _assert_generated_equals_fixture(
        tmp_path,
        [
            # Assert that function creates errors files with records about skipped duplicate companies
            (
                Settings.csv_errors_accounts_contacts_filename,
                "tests/fixtures/duplicate_name/errors_accounts_contacts.csv",
            ),
            (
                Settings.csv_errors_opportunities_filename,
                "tests/fixtures/duplicate_name/errors_opportunities.csv",
            ),
            # Assert that valid rows dumped to target files
            (Settings.csv_accounts_contacts_filename, "tests/fixtures/duplicate_name/accounts_contacts.csv"),
            (Settings.csv_opportunities_filename, "tests/fixtures/duplicate_name/opportunities.csv"),
        ],
    )


@responses.activate
@freezegun.freeze_time("2025-12-20")
def test_pass_build_sf_csvs_given_missing_fields_skips_records_as_errors(tmp_path):
    mock_hubspot_responses(
        {
            "con2": "missing_req_fields/contacts_p2_missing_req_fields.json",
            "comp1": "missing_req_fields/companies_p1_missing_req_fields.json",
            "deal2": "missing_req_fields/deals_p2_missing_req_fields.json",
        }
    )
    download_hs_objects(tmp_path, lambda _: None)

    build_sf_csvs(tmp_path, lambda _: None)

    _assert_generated_equals_fixture(
        tmp_path,
        [
            # Assert that function creates errors files with records about skipped duplicate companies
            (
                Settings.csv_errors_accounts_contacts_filename,
                "tests/fixtures/missing_req_fields/errors_accounts_contacts.csv",
            ),
            (
                Settings.csv_errors_opportunities_filename,
                "tests/fixtures/missing_req_fields/errors_opportunities.csv",
            ),
            # Assert that valid rows dumped to target files
            (Settings.csv_accounts_contacts_filename, "tests/fixtures/missing_req_fields/accounts_contacts.csv"),
            (Settings.csv_opportunities_filename, "tests/fixtures/missing_req_fields/opportunities.csv"),
        ],
    )


# Helpers


def _assert_generated_equals_fixture(tmp_path, pairs: list[tuple[str, str]]) -> None:
    for gen_filename, fixture_path in pairs:
        gen_path = Path(tmp_path) / gen_filename
        assert gen_path.exists()
        generated_rows = _read_csv(gen_path)
        expected_rows = _read_csv(fixture_path)
        assert generated_rows == expected_rows


def _read_csv(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
        return rows
