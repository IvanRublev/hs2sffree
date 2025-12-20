from time import perf_counter
from pathlib import Path

import rich_click as click
from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table
from rich.traceback import install as install_exception_handler

from src.settings import Settings
from src.translator import download_hs_objects, build_sf_csvs, cleanup


install_exception_handler(show_locals=False)


@click.command()
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(file_okay=False),
    default=(Path(".") / Settings.output_directory),
    help="Output deirectory for CSV files.",
)
def main(output_dir):
    output_dir = Path(output_dir)
    console = Console()

    _print_header(console)

    _ensure_hubspot_token(console)
    _ensure_output_dir(console, output_dir)

    _download_hubspot_objects(console, output_dir)
    stats = _build_salesforce_csvs(console, output_dir)
    cleanup(str(output_dir))

    _print_build_stats(console, stats)
    _print_import_help(console, output_dir)


def _ensure_hubspot_token(console: Console):
    # Ensure we have a HubSpot token
    if not Settings.hubspot_token:
        hubspot_app_help = r"""
You should add a legacy app in your HubSpot account to run this tool,
see https://developers.hubspot.com/docs/apps/legacy-apps/private-apps/overview .

When creating the app set checkboxes for all company, contact, deal read scopes.

"""
        console.print(hubspot_app_help)
        console.print(f"No HubSpot token found in the environment variable {Settings.hubspot_token_env_name}.")
        token = Prompt.ask("Please enter your HubSpot token", password=True)
        # store it on the Settings class for this run
        Settings.hubspot_token = token


def _ensure_output_dir(console: Console, path: Path):
    path.mkdir(parents=True, exist_ok=True)
    if any(path.iterdir()):
        raise RuntimeError(f"Output directory '{path}' is not empty.")

    console.print(f"Using output directory: [bold]{path}[/bold]")


def _download_hubspot_objects(console: Console, output_dir: Path):
    console.print("\n[bold]Downloading HubSpot objects...[/bold]")

    status_bytes_str = ""

    def collect_status_bytes_str(bytes: int) -> str:
        nonlocal status_bytes_str
        status_bytes_str = _human_readable_bytes(bytes)
        return status_bytes_str

    start = perf_counter()
    with console.status("Downloading…", spinner="dots") as status:
        download_hs_objects(
            str(output_dir),
            lambda bytes: status.update(f"Downloading… {collect_status_bytes_str(bytes)}"),
        )
    elapsed = perf_counter() - start
    console.print(f"Done downloading {status_bytes_str} in {elapsed:.2f}s\n")


def _build_salesforce_csvs(console: Console, output_dir: Path) -> dict:
    console.print("[bold]Building Salesforce CSVs...[/bold]")
    start = perf_counter()
    with console.status("Building…", spinner="dots") as status:
        stats = build_sf_csvs(str(output_dir), lambda progress: status.update(f"Building… {progress}"))
    elapsed = perf_counter() - start
    console.print(f"Done building in {elapsed:.2f}s\n")
    return stats


def _human_readable_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024.0:
            return f"{n:.1f}{unit}"
        n /= 1024.0
    return f"{n:.1f}TB"


def _print_header(console: Console):
    header = r"""
        __        ___        ________             
       / /_  ____|__ \ _____/ __/ __/_______  ___ 
      / __ \/ ___/_/ // ___/ /_/ /_/ ___/ _ \/ _ \
     / / / (__  ) __/(__  ) __/ __/ /  /  __/  __/
    /_/ /_/____/____/____/_/ /_/ /_/   \___/\___/ 

    hs2sffree — data migration tool from HubSpot to Salesforce Free CRM 
    for Contacts -> Contacts, Companies -> Accounts, Deals -> Opportunities.

    Downloads HubSpot data and build Salesforce CSVs ready to import.

    If Contact or Deal has more than one association with a Company only the first one will be taken.


    
"""
    console.print(header, style="bold cyan")


def _print_build_stats(console: Console, stats: dict):
    table = Table(title="Build statistics")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="magenta")

    for k, v in stats.items():
        table.add_row(k, str(v))

    console.print(table)


def _print_import_help(console: Console, output_dir: str):
    console.print(f"\nThe CSV files are saved to the [bold]{output_dir}[/bold] directory:\n")
    console.print(f"    [bold]{Settings.csv_accounts_contacts_filename}[/bold]")
    console.print(f"    [bold]{Settings.csv_opportunities_filename}[/bold]")
    console.print("\nYou can import them in Salesforce.")

    import_help = f"""

    [bold underline]How to import {Settings.csv_accounts_contacts_filename}[/bold underline]
    
    1. Open Accounts → Import → Data Import Wizard
    2. Select "Accounts and Contacts" - "Add new records"
    3. Match Contact by Name, Match Account by Name & Site
    4. Choose CSV with Character Code option set to Unicode (UTF-8)
    5. Upload `{Settings.csv_accounts_contacts_filename}` by pressing the Browse button and follow the wizard


    [bold underline]How to import {Settings.csv_opportunities_filename}[/bold underline]

    1. Open Sales → Opportunities → Import
    2. Select "Import From File"
    3. Upload `opportunities.csv` and follow the wizard
    4. When import has finished, perform the association step described below

    The tool persists Account name in the Next Step field of the Opportunity. 
    To complete the association create and run the Flow automation in Salesforce 
    as shown in the following video:

    https://github.com/IvanRublev/hb2sffree/raw/refs/heads/master/flow_to_set_opportunity_accounts.mp4

"""
    console.print(import_help, style="bold cyan")


if __name__ == "__main__":
    main()
