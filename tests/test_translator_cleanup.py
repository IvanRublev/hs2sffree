import responses

from src.settings import Settings
from src.translator import download_hs_objects, cleanup
from tests.conftest import mock_hubspot_responses


@responses.activate
def test_pass_cleanup_removes_companies_contacts_deals_files(tmp_path):
    mock_hubspot_responses()
    download_hs_objects(tmp_path, lambda _: None)
    assert (tmp_path / Settings.companies_filename).exists()
    assert (tmp_path / Settings.contacts_filename).exists()
    assert (tmp_path / Settings.deals_filename).exists()

    cleanup(tmp_path)

    assert not (tmp_path / Settings.companies_filename).exists()
    assert not (tmp_path / Settings.contacts_filename).exists()
    assert not (tmp_path / Settings.deals_filename).exists()
