import pytest
import tempfile
from pathlib import Path

from sqlalchemy.exc import IntegrityError

from src.infra.companies_db import (
    initialize_db,
    close_db,
    add_company,
    get_company,
    add_companies,
    find_companies_by_name,
)


@pytest.fixture
def db_engine():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test.db"
        db_engine = initialize_db(db_path)
        yield db_engine
        close_db(db_engine)


def test_pass_add_company_given_account(db_engine):
    id = "id1"
    attrs = {"param1": "value1"}
    name = "Test Company"
    duplicate = False

    add_company(db_engine, id, attrs, name, duplicate)

    assert {"attrs": attrs, "duplicate": duplicate} == get_company(db_engine, id)


def test_fail_add_company_given_null_id(db_engine):
    with pytest.raises(IntegrityError) as exc_info:
        add_company(db_engine, None, {"param1": "value1"}, "Name", False)
    assert "NOT NULL constraint failed: companies.id'" in str(exc_info)


def test_fail_add_company_given_null_attrs(db_engine):
    with pytest.raises(ValueError) as exc_info:
        add_company(db_engine, "id1", None, "Name", False)
    assert "No attrs provided" in str(exc_info.value)


def test_fail_add_company_given_duplicate_account_id(db_engine):
    id = "id1"
    attrs = {"param1": "value1"}
    name = "Test Company"
    duplicate = False

    add_company(db_engine, id, attrs, name, duplicate)

    with pytest.raises(IntegrityError) as exc_info:
        add_company(db_engine, id, {"param2": "value2"}, "Other Name", False)
    assert "UNIQUE constraint failed: companies.id" in str(exc_info.value)


def test_pass_add_companies_persists_multiple_items(db_engine):
    id1 = "id1"
    attrs1 = {"param1": "value1"}
    duplicate1 = False
    id2 = "id2"
    attrs2 = {"param2": "value2"}
    duplicate2 = True
    companies = [(id1, attrs1, "Name 1", duplicate1), (id2, attrs2, "Name 2", duplicate2)]

    add_companies(db_engine, companies)

    assert {"attrs": attrs1, "duplicate": duplicate1} == get_company(db_engine, id1)
    assert {"attrs": attrs2, "duplicate": duplicate2} == get_company(db_engine, id2)


def test_fail_add_companies_given_no_companies(db_engine):
    with pytest.raises(ValueError) as exc_info:
        add_companies(db_engine, None)
    assert "No companies provided" in str(exc_info)

    with pytest.raises(ValueError) as exc_info:
        add_companies(db_engine, [])
    assert "No companies provided" in str(exc_info)


def test_fail_add_companies_given_missing_properties(db_engine):
    id1 = "id1"
    attrs1 = {"param1": "value1"}
    id2 = "id2"
    attrs2 = {"param2": "value2"}

    # missing attributes
    companies = [(id1, None, "Name 1", False), (id2, attrs2, "Name 2", False)]
    with pytest.raises(ValueError) as exc_info:
        add_companies(db_engine, companies)
    err_message = str(exc_info.value)
    assert "No attrs provided" in err_message
    assert id1 in err_message

    # missing id
    companies = [(id1, attrs1, "Name 1", False), (None, attrs2, "Name 2", False)]
    with pytest.raises(IntegrityError) as exc_info:
        add_companies(db_engine, companies)
    err_message = str(exc_info.value)
    assert "NOT NULL constraint failed: companies.id" in err_message


def test_fail_get_company_given_nonexistend_id(db_engine):
    with pytest.raises(ValueError) as exc_info:
        get_company(db_engine, "nonexistent_id")
    assert "Company not found" in str(exc_info)


def test_fail_get_company_given_null_id(db_engine):
    with pytest.raises(ValueError) as exc_info:
        get_company(db_engine, None)
    assert "No id provided" in str(exc_info)


def test_pass_find_companies_by_name_retruns_ids(db_engine):
    name = "Test Company"

    add_company(db_engine, "id1", {"param1": "value1"}, name, False)
    assert [None, "id1", None] == find_companies_by_name(db_engine, ["nonexisting company", name, None])

    # Given duplicates should return original id
    add_company(db_engine, "id2", {"param1": "value1"}, name, True)
    assert ["id1"] == find_companies_by_name(db_engine, [name])


def test_fail_find_companies_by_name_given_duplicate_names(db_engine):
    with pytest.raises(ValueError) as exc_info:
        find_companies_by_name(db_engine, ["comp0", "comp1", "comp1"])
    assert 'Duplicate names in list: "comp1"' in str(exc_info)


def test_fail_find_companies_by_name_given_null_names(db_engine):
    with pytest.raises(ValueError) as exc_info:
        find_companies_by_name(db_engine, None)
    assert "No names list provided" in str(exc_info)
