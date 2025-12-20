import requests
from requests.adapters import HTTPAdapter
from typing import Callable
from urllib3.util.retry import Retry
from urllib.parse import urlparse

from src.settings import Settings
from src.infra.dict import get_nested


def download_objects(
    path: str,
    token: str,
    endpoint_url: str,
    progress_bytes_callback: Callable[[int], None],
    json_callback: Callable[[dict], None],
):
    parsed_url = urlparse(endpoint_url)
    if parsed_url.scheme != "https":
        raise ValueError("Only https protocol is allowed")
    if not token:
        raise ValueError("Can't request HubSpot without token.")

    session = requests.Session()
    retry_strategy = Retry(total=Settings.http_request_retries, backoff_factor=1, status_forcelist=range(400, 600))
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    headers = {"Authorization": f"Bearer {token}"}

    response = session.get(endpoint_url, headers=headers)

    # send length of response in bytes
    progress_bytes_callback(len(response.content))

    json = response.json()
    json_callback(json)

    link = get_nested(json, ["paging", "next", "link"])
    if link:
        download_objects(path, token, link, progress_bytes_callback, json_callback)
