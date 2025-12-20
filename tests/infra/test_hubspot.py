import json
import pytest
from pathlib import Path
import re

from requests.exceptions import RetryError
import responses

from src.infra.hubspot import download_objects


TOKEN = "token"


def test_fail_download_hs_object_given_http_endpoint(tmp_path):
    with pytest.raises(ValueError) as exc_info:
        download_objects(tmp_path, TOKEN, "http://some", lambda _: None, lambda _json: None)
    assert "Only https protocol is allowed" in str(exc_info)


@responses.activate
def test_fail_download_hs_object_given_endpoint_failure_retries_three_times(tmp_path):
    rsps = responses.add(responses.GET, re.compile(r".*"), status=500)

    with pytest.raises(RetryError):
        download_objects(tmp_path, TOKEN, "https://some_endpoint", lambda _: None, lambda _json: None)

    assert len(rsps.calls) == 4


@responses.activate
def test_fail_download_hs_object_given_empty_token(tmp_path):
    with pytest.raises(ValueError) as exc_info:
        token = ""
        download_objects(tmp_path, token, "https://some_endpoint", lambda _: None, lambda _json: None)
    assert "Can't request HubSpot without token." in str(exc_info)


@responses.activate
def test_pass_download_hs_object_given_endpoint_url_returns_all_pages():
    url = "https://api.hubapi.com/crm/objects/v3/companies"

    p1_filepath = Path("tests/fixtures") / "companies_p1.json"
    p2_filepath = Path("tests/fixtures") / "companies_p2.json"
    with open(p1_filepath) as f1:
        p1_file = json.load(f1)
    with open(p2_filepath) as f2:
        p2_file = json.load(f2)

    matcher_auth = responses.matchers.header_matcher({"Authorization": f"Bearer {TOKEN}"})
    matcher_not_after_param = responses.matchers.query_param_matcher({})
    matcher_after_param = responses.matchers.query_param_matcher({"after": "326835011779"}, strict_match=False)

    responses.add(
        responses.GET,
        url,
        json=p1_file,
        status=200,
        match=[matcher_auth, matcher_not_after_param],
    )
    responses.add(
        responses.GET,
        url,
        json=p2_file,
        status=200,
        match=[matcher_auth, matcher_after_param],
    )

    all_jsons = []
    download_objects("some_path", TOKEN, url, lambda _: None, lambda json: all_jsons.append(json))

    expected = [p1_file, p2_file]
    assert expected == all_jsons
