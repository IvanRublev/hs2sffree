import os
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

HUBSPOT_TOKEN = "HUBSPOT_TOKEN"


class Settings:
    """Represents the settings for the application.

    Some of them are loaded from environment variables or have hardcoded values.
    """

    # Loaded from environment variables

    hubspot_token: Optional[str] = os.environ.get(HUBSPOT_TOKEN)
    output_directory: str = "output"

    # Hardcoded

    hubspot_token_env_name = HUBSPOT_TOKEN
    hubspot_api_base_url: str = "https://api.hubapi.com"
    hubspot_api_companies_path: str = "/crm/objects/v3/companies"
    hubspot_api_contacts_path: str = "/crm/objects/v3/contacts"
    hubspot_api_deals_path: str = "/crm/objects/v3/deals"

    response_items_limit = 100

    @classmethod
    def hubspot_api_companies_params(cls) -> str:
        return f"limit={cls.response_items_limit}&properties=name,industry,address,country,domain"

    @classmethod
    def hubspot_api_contacts_params(cls) -> str:
        return (
            f"limit={cls.response_items_limit}"
            "&properties=firstname,lastname,email,phone,address,country,jobtitle&associations=companies"
        )

    @classmethod
    def hubspot_api_deals_params(cls) -> str:
        return (
            f"limit={cls.response_items_limit}"
            "&properties=dealname,closedate,dealstage,amount,dealtype&associations=companies"
        )

    contacts_filename: str = "contacts.parquet"
    deals_filename: str = "deals.parquet"
    companies_filename: str = "companies.sqlite"

    csv_accounts_contacts_filename: str = "accounts_contacts.csv"
    csv_errors_accounts_contacts_filename: str = "errors_accounts_contacts.csv"
    csv_opportunities_filename: str = "opportunities.csv"
    csv_errors_opportunities_filename: str = "errors_opportunities.csv"

    http_request_retries = 3
