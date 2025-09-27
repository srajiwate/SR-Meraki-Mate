import requests
import os
import getpass
import sys
import logging
import hashlib
import argparse
import re
from pathlib import Path

# Add your home directory to path (only useful for srajiwate)
sys.path.append("/home/srajiwate")

from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from rich.console import Console
from rich.prompt import Prompt, Confirm
from pyfiglet import Figlet

from switch_config import switch_config_menu
from wireless_config import wireless_config_menu
from appliance_config import appliance_config_menu
from policy_objects import policy_object_menu
from vpn_exclusion_menu import vpn_exclusion_menu
from troubleshooting import troubleshooting_menu
from vpn_s2s_menu import vpn_s2s_menu
from device_status import device_status_menu
from inventory_view import show_inventory

# Try to import user_vault_config safely
get_vault_and_secret_names = None
try:
    from user_vault_config import get_vault_and_secret_names as vault_fn
    get_vault_and_secret_names = vault_fn
except ImportError:
    pass

console = Console()

# === Banner & Creator Integrity Lock ===
EXPECTED_BANNER = "SR-MerakiMate"
EXPECTED_CREATOR = "Shadab Rajiwate"

MASTER_PASSWORD_HASH = "18fd42d6825d0d15603a67aa0fdf962586f2dfba00e9692e7d0fcb26b3a43a4b"
EXPECTED_BANNER_HASH = "97ec104f414c92792739bdbcc5698d65635e858743c5e7b8c50f50e752023ab6"
EXPECTED_CREATOR_HASH = "15fc4bfecbaffe2072fd0b7e60f72e8b0c4c67455388451d32d27944d8575364"


def regenerate_banner_and_creator_hash():
    """Regenerate string-based banner & creator hashes (requires master password)."""
    password = getpass.getpass("🔐 Enter master password to update hashes: ")
    if hashlib.sha256(password.encode()).hexdigest() != MASTER_PASSWORD_HASH:
        console.print("[red]❌ Invalid master password. Exiting.[/red]")
        exit(1)

    new_banner_hash = hashlib.sha256(EXPECTED_BANNER.encode()).hexdigest()
    new_creator_hash = hashlib.sha256(EXPECTED_CREATOR.encode()).hexdigest()

    file_path = Path(__file__).resolve()
    content = file_path.read_text()
    content = re.sub(r'EXPECTED_BANNER_HASH\s*=\s*".*?"',
                     f'EXPECTED_BANNER_HASH = "{new_banner_hash}"', content)
    content = re.sub(r'EXPECTED_CREATOR_HASH\s*=\s*".*?"',
                     f'EXPECTED_CREATOR_HASH = "{new_creator_hash}"', content)
    file_path.write_text(content)

    console.print(f"[green]✅ Hashes updated successfully![/green]")
    console.print(f"[cyan]Banner hash:[/cyan] {new_banner_hash}")
    console.print(f"[cyan]Creator hash:[/cyan] {new_creator_hash}")
    exit(0)


def verify_integrity():
    """Verify that banner & creator strings are intact."""
    banner_hash = hashlib.sha256(EXPECTED_BANNER.encode()).hexdigest()
    creator_hash = hashlib.sha256(EXPECTED_CREATOR.encode()).hexdigest()

    if banner_hash != EXPECTED_BANNER_HASH or creator_hash != EXPECTED_CREATOR_HASH:
        console.print("[red]⚠️ Script integrity check failed! Banner or creator modified.[/red]")
        password = getpass.getpass("🔐 Enter master password to continue: ")
        if hashlib.sha256(password.encode()).hexdigest() != MASTER_PASSWORD_HASH:
            console.print("[red]❌ Invalid master password. Exiting.[/red]")
            exit(1)
        else:
            console.print("[green]✅ Master password accepted. Continuing...[/green]")
            logging.warning("Integrity bypassed with master password")


def show_logo_and_confirm():
    figlet = Figlet(font='slant')
    logo_text = figlet.renderText(EXPECTED_BANNER)
    console.print(logo_text, style="bold cyan")

    verify_integrity()

    proceed = Confirm.ask(f"🚀 Developed By, {EXPECTED_CREATOR}! Ready to begin?")
    if not proceed:
        console.print("👋 Exiting script. Come back soon!", style="bold yellow")
        exit()


BASE_URL = "https://api.meraki.com/api/v1"

# === Vault & Logging ===
def prompt_vault_details(use_vault=True):
    """For srajiwate use preset, for others always prompt unless skipped."""
    if not use_vault:
        return None, None

    current_user = getpass.getuser()

    if current_user == "srajiwate" and get_vault_and_secret_names:
        KEY_VAULT_NAME, SECRET_NAME = get_vault_and_secret_names(current_user)
        if KEY_VAULT_NAME and SECRET_NAME:
            console.print(f"[green]🔐 Using Key Vault preset for [bold]{current_user}[/bold][/green]")
            return KEY_VAULT_NAME, SECRET_NAME

    console.print(f"[yellow]🔐 No preset found. Please enter manually.[/yellow]")
    KEY_VAULT_NAME = Prompt.ask("Enter your Azure Key Vault name")
    SECRET_NAME = Prompt.ask("Enter your Secret name storing the Meraki API key")
    return KEY_VAULT_NAME, SECRET_NAME


LOG_DIR = Path.home() / ".meraki_deploy"
LOG_DIR.mkdir(mode=0o700, exist_ok=True)
LOG_FILE = LOG_DIR / "meraki_wireless_deploy.log"

logging.basicConfig(filename=str(LOG_FILE),
                    level=logging.INFO,
                    format='%(asctime)s - %(message)s')


def log_event(message, style="green"):
    logging.info(message)
    console.print(message, style=style)


def fetch_api_key(KEY_VAULT_NAME=None, SECRET_NAME=None):
    if not KEY_VAULT_NAME or not SECRET_NAME:
        return getpass.getpass("🔑 Enter your Meraki API Key: ")
    try:
        kv_uri = f"https://{KEY_VAULT_NAME}.vault.azure.net"
        credential = DefaultAzureCredential()
        client = SecretClient(vault_url=kv_uri, credential=credential)
        return client.get_secret(SECRET_NAME).value
    except Exception as e:
        console.print(f"[yellow]⚠️ Azure Key Vault not available ({e}).[/yellow]")
        return getpass.getpass("🔑 Enter your Meraki API Key: ")


def get_headers(api_key):
    return {"Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json"}


# === Org & Network Functions (unchanged) ===
def choose_organization(headers):
    url = f"{BASE_URL}/organizations"
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        log_event("❌ Failed to fetch organizations.", style="red")
        return None
    orgs = response.json()
    console.print("\n[bold cyan]📂 Available Organizations:[/bold cyan]")
    for idx, org in enumerate(orgs, 1):
        console.print(f"{idx}. {org['name']} ({org['id']})")
    sel = int(Prompt.ask("Select organization by number"))
    return orgs[sel - 1]['id'] if 1 <= sel <= len(orgs) else None


def get_networks(org_id, headers):
    url = f"{BASE_URL}/organizations/{org_id}/networks"
    response = requests.get(url, headers=headers)
    return response.json() if response.status_code == 200 else []


def choose_network(org_id, headers):
    nets = get_networks(org_id, headers)
    console.print("\n[bold cyan]   Available Networks:[/bold cyan]")
    for i, net in enumerate(nets, 1):
        console.print(f"{i}. {net['name']} ({net['id']})")
    sel = int(Prompt.ask("Select network by number"))
    return nets[sel - 1]['id'] if 1 <= sel <= len(nets) else None


def choose_or_create_network(org_id, headers):
    choice = Prompt.ask("1. Create new network\n2. Use existing network\nEnter choice", choices=["1", "2"])
    if choice == "1":
        name = Prompt.ask("Enter new network name")
        types = Prompt.ask("Enter product types (e.g. appliance,switch,wireless)").split(",")
        tags_input = Prompt.ask("Enter tags (comma-separated or blank)", default="")
        tags = [t.strip() for t in tags_input.split(",")] if tags_input else []
        payload = {"name": name,
                   "timeZone": "Asia/Kolkata",
                   "productTypes": [t.strip() for t in types],
                   "tags": tags}
        url = f"{BASE_URL}/organizations/{org_id}/networks"
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 201:
            log_event(f"✅ Created network '{name}'", style="green")
            return response.json()['id']
        else:
            log_event(f"❌ Failed to create network: {response.text}", style="red")
            return None
    else:
        return choose_network(org_id, headers)


def get_claimed_serials(org_id, headers):
    url = f"{BASE_URL}/organizations/{org_id}/devices"
    response = requests.get(url, headers=headers)
    return [device["serial"] for device in response.json()] if response.status_code == 200 else []


def claim_devices(network_id, headers):
    serials = [s.strip().upper() for s in Prompt.ask("Enter serials (comma-separated)").split(",")]
    existing_serials = get_claimed_serials(org_id, headers)
    serials_to_claim = [s for s in serials if s not in existing_serials]
    if not serials_to_claim:
        log_event("⚠️ No new serials to claim.", style="yellow")
        return
    url = f"{BASE_URL}/networks/{network_id}/devices/claim"
    payload = {"serials": serials_to_claim}
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code in [200, 204]:
        log_event(f"✅ Claimed serials: {', '.join(serials_to_claim)}", style="green")
    else:
        log_event(f"❌ Failed to claim serials: {response.text}", style="red")


# === Main Menu ===
def main_menu():
    while True:
        console.print("\n[bold green]📋 Main Menu[/bold green]")
        console.print("1. 📦 Claim Devices")
        console.print("2. 🔀 Switch Configuration")
        console.print("3. 📡 Wireless Configuration")
        console.print("4. 🔥 Appliance Configuration")
        console.print("5. 🧱 Policy Object Automation")
        console.print("6. 🌐 VPN Exclusion (Local Internet Breakout)")
        console.print("7. 🔐 Site-to-Site VPN Configuration")
        console.print("8. 🧪 Troubleshooting")
        console.print("9. 📶 Device Status")
        console.print("10. 🗂️ Inventory View")
        console.print("11. ⬅️ Exit")

        choice = Prompt.ask("Choose an action", choices=[str(i) for i in range(1, 12)])

        if choice == "1":
            claim_devices(network_id, headers)
        elif choice == "2":
            switch_config_menu(network_id, headers)
        elif choice == "3":
            wireless_config_menu(network_id, headers)
        elif choice == "4":
            appliance_config_menu(network_id, headers)
        elif choice == "5":
            policy_object_menu(BASE_URL, headers, network_id, org_id)
        elif choice == "6":
            vpn_exclusion_menu(BASE_URL, headers, org_id)
        elif choice == "7":
            vpn_s2s_menu(BASE_URL, headers, org_id, network_id)
        elif choice == "8":
            troubleshooting_menu(BASE_URL, headers, network_id)
        elif choice == "9":
            device_status_menu(org_id, network_id, headers)
        elif choice == "10":
            show_inventory(headers, org_id)
        elif choice == "11":
            log_event("👋 Exiting deployment script.", style="cyan")
            break


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--update-banner", action="store_true", help="Regenerate hashes (requires master password)")
    parser.add_argument("--no-vault", action="store_true", help="Skip Azure Key Vault and prompt API key manually")
    args = parser.parse_args()

    if args.update_banner:
        regenerate_banner_and_creator_hash()

    try:
        show_logo_and_confirm()
        KEY_VAULT_NAME, SECRET_NAME = prompt_vault_details(use_vault=not args.no_vault)
        api_key = fetch_api_key(KEY_VAULT_NAME, SECRET_NAME)
        headers = get_headers(api_key)
        org_id = choose_organization(headers)
        if not org_id:
            exit()
        network_id = choose_or_create_network(org_id, headers)
        if not network_id:
            exit()
        main_menu()
    except KeyboardInterrupt:
        print("\n👋 Exiting... Operation cancelled by user.")
        exit()
