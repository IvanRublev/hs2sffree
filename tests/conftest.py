import json
from pathlib import Path
import pytest
from urllib.parse import urljoin

import responses

from src.settings import Settings

BASE_URL = "https://api.hubapi.com"
TOKEN = "hubspottoken"


def patch_setting(monkeypatch, attr_name: str, value: any):
    if not hasattr(Settings, attr_name):
        raise AttributeError(f"Settings object is missing '{attr_name}' attribute")
    monkeypatch.setattr(Settings, attr_name, value)


@pytest.fixture(autouse=True)
def mock_settings(monkeypatch):
    patch_setting(monkeypatch, "hubspot_api_base_url", BASE_URL)
    patch_setting(monkeypatch, "hubspot_token", TOKEN)
    patch_setting(monkeypatch, "response_items_limit", 3)


def mock_hubspot_responses(fixture_names: dict = {}):
    # clear any previously registered response mocks and recorded calls
    responses.reset()
    responses.calls.reset()

    json_names = {
        "con1": "contacts_p1.json",
        "con2": "contacts_p2.json",
        "comp1": "companies_p1.json",
        "comp2": "companies_p2.json",
        "deal1": "deals_p1.json",
        "deal2": "deals_p2.json",
        **fixture_names,
    }

    # Map of endpoint URLs with query params to fixture file paths
    query_to_fixture = {
        (Settings.hubspot_api_contacts_path, Settings.hubspot_api_contacts_params()): json_names["con1"],
        (
            Settings.hubspot_api_contacts_path,
            Settings.hubspot_api_contacts_params() + "&after=582043056333",
        ): json_names["con2"],
        (Settings.hubspot_api_companies_path, Settings.hubspot_api_companies_params()): json_names["comp1"],
        (
            Settings.hubspot_api_companies_path,
            Settings.hubspot_api_companies_params() + "&after=326835011779",
        ): json_names["comp2"],
        (Settings.hubspot_api_deals_path, Settings.hubspot_api_deals_params()): json_names["deal1"],
        (
            Settings.hubspot_api_deals_path,
            Settings.hubspot_api_deals_params() + "&after=398944889067",
        ): json_names["deal2"],
    }

    # Register mock responses from fixture files
    for (url_path, params), fixture_path in query_to_fixture.items():
        fixture_file = Path("tests/fixtures") / fixture_path
        with open(fixture_file) as f:
            url = urljoin(BASE_URL, url_path)
            data = json.load(f)

            params_dict = dict(param.split("=") for param in params.split("&"))
            matchers = [
                responses.matchers.query_param_matcher(params_dict),
                responses.matchers.header_matcher({"Authorization": f"Bearer {TOKEN}"}),
            ]

            responses.add(responses.GET, url, json=data, status=200, match=matchers)
