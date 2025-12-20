import pytest
import re

import responses

from src.infra.companies_db import initialize_db, close_db, get_company
from src.settings import Settings
from src.translator import download_hs_objects, ACCOUNTS_NAME_COLUMN
from tests.conftest import mock_hubspot_responses


@responses.activate
def test_pass_download_hs_objects_creates_companies_database(tmp_path):
    mock_hubspot_responses()

    download_hs_objects(tmp_path, lambda _: None)

    assert (tmp_path / Settings.companies_filename).exists()
    assert (tmp_path / Settings.contacts_filename).exists()
    assert (tmp_path / Settings.deals_filename).exists()


@responses.activate
def test_fail_download_hs_objects_given_network_error(tmp_path):
    responses.add(responses.GET, re.compile(r".*"), body=ConnectionError("Network error"))
    with pytest.raises(ConnectionError):
        download_hs_objects(tmp_path, lambda _: None)


@responses.activate
def test_pass_download_hs_object_given_duplicate_company_name_marks_company_as_duplicate(tmp_path):
    # Duplicate is in the same batch
    mock_hubspot_responses({"comp1": "companies_p1_duplicate_names_same_batch.json"})

    download_hs_objects(tmp_path, lambda _: None)

    db_path = tmp_path / Settings.companies_filename
    engine = initialize_db(db_path)
    original_co = get_company(engine, "326789966068")
    duplicate_co = get_company(engine, "326835011780")

    assert "Krebs OHG mbH" == original_co["attrs"][ACCOUNTS_NAME_COLUMN]
    assert not original_co["duplicate"]
    assert "Krebs OHG mbH" == duplicate_co["attrs"][ACCOUNTS_NAME_COLUMN]
    assert duplicate_co["duplicate"]

    close_db(engine)
    db_path.unlink()

    # Our duplicate in the next batch
    mock_hubspot_responses({"comp2": "duplicate_name/companies_p2_duplicate_name.json"})

    download_hs_objects(tmp_path, lambda _: None)

    db_path = tmp_path / Settings.companies_filename
    engine = initialize_db(db_path)
    original_co = get_company(engine, "326835011778")
    duplicate_co = get_company(engine, "326835011779")

    assert "Rose Cichorius GmbH" == original_co["attrs"][ACCOUNTS_NAME_COLUMN]
    assert not original_co["duplicate"]
    assert "Rose Cichorius GmbH" == duplicate_co["attrs"][ACCOUNTS_NAME_COLUMN]
    assert duplicate_co["duplicate"]

    close_db(engine)
