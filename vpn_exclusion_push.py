from pathlib import Path
import requests
import pandas as pd
import json
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
import logging
import sys
import os
from datetime import datetime

# === CONFIGURATION ===
KEYS_TO_CHECK = ["protocol", "destination", "port"]
BACKUP_DIR = "vpn_exclusion_backups"

# === LOGGING SETUP ===
logging.basicConfig(
    filename='vpn_exclusion_audit.log',
    level=logging.INFO,
    format='%(asctime)s - %(message)s'
)

def log_event(message):
    logging.info(message)
    print(message)

# === FETCH API KEY FROM AZURE KEY VAULT ===
def fetch_api_key(key_vault_name, secret_name):
    kv_uri = f"https://{key_vault_name}.vault.azure.net"
    credential = DefaultAzureCredential()
    client = SecretClient(vault_url=kv_uri, credential=credential)
    return client.get_secret(secret_name).value

# === HELPER FUNCTIONS ===
def read_excel_data(file_path):
    df_orgs = pd.read_excel(file_path, sheet_name='Organizations')
    df_ips = pd.read_excel(file_path, sheet_name='IPList')
    return df_orgs, df_ips

def get_existing_exclusions(org_id, api_key):
    url = f"https://api.meraki.com/api/v1/organizations/{org_id}/appliance/trafficShaping/vpnExclusions/byNetwork"
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json().get("items", [])

def prompt_user_selection(network_list, org_id):
    print(f"\nAvailable Networks in Org {org_id}:")
    for idx, net in enumerate(network_list):
        print(f"[{idx}] {net['networkName']} ({net['networkId']})")

    print("\nOptions:")
    print(" - Enter comma-separated index numbers to update (e.g., 0,2)")
    print(" - Enter 'c' to update all listed networks")
    print(" - Enter 's' to skip this organization")

    selection = input("Your selection: ").strip().lower()

    if selection == "s":
        return None  # Skip org
    elif selection == "c":
        return network_list  # Select all
    else:
        try:
            indices = [int(i.strip()) for i in selection.split(",")]
            return [network_list[i] for i in indices]
        except Exception:
            print("? Invalid selection. Skipping organization.")
            return None

def merge_and_handle_duplicates(existing, new_entries):
    seen = {tuple(e.get(k) for k in KEYS_TO_CHECK) for e in existing}
    duplicates = [e for e in new_entries if tuple(e.get(k) for k in KEYS_TO_CHECK) in seen]

    if duplicates:
        print("\n?? Duplicate entries detected:")
        for d in duplicates:
            print(f" - {d}")

        confirm = input("Do you want to overwrite existing duplicates? (yes/no): ").strip().lower()
        if confirm != "yes":
            new_entries = [e for e in new_entries if tuple(e.get(k) for k in KEYS_TO_CHECK) not in seen]

    return existing + new_entries

def backup_config(network_id, custom, major):
    os.makedirs(BACKUP_DIR, exist_ok=True)
    backup_file = os.path.join(
        BACKUP_DIR,
        f"{network_id}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    with open(backup_file, 'w') as f:
        json.dump({"custom": custom, "majorApplications": major}, f, indent=2)
    log_event(f"? Backup saved: {backup_file}")

def update_exclusion(network_id, custom, major, api_key):
    url = f"https://api.meraki.com/api/v1/networks/{network_id}/appliance/trafficShaping/vpnExclusions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"custom": custom, "majorApplications": major}

    response = requests.put(url, headers=headers, json=payload)
    if response.status_code == 200:
        log_event(f"? Updated VPN exclusions for {network_id}")
    else:
        log_event(f"? Failed to update {network_id}: {response.status_code} - {response.text}")

# === MAIN ===
def main():
    # Try to import vault details from main.py
    try:
        from .main import prompt_vault_details
        key_vault_name, secret_name = prompt_vault_details()
    except ImportError:
        # Fallback if run standalone
        key_vault_name = input("Enter Azure Key Vault name: ").strip()
        secret_name = input("Enter Secret name (Meraki API Key): ").strip()

    api_key = fetch_api_key(key_vault_name, secret_name)

    data_dir = Path(__file__).resolve().parent / "data"
    input_file = data_dir / "vpn_exclusion_input.xlsx"
    orgs_df, ips_df = read_excel_data(input_file)

    new_custom_rules = [
        {"protocol": "any", "destination": str(ip).strip(), "port": "any"}
        for ip in ips_df["IP"]
    ]

    for _, row in orgs_df.iterrows():
        org_id = str(row["OrganizationId"])
        log_event(f"\n--- Processing Org {org_id} ---")
        all_exclusions = get_existing_exclusions(org_id, api_key)

        selected_networks = prompt_user_selection(all_exclusions, org_id)
        if not selected_networks:
            log_event(f"?? Skipping organization {org_id}")
            continue

        for net in selected_networks:
            net_id = net["networkId"]
            net_name = net["networkName"]
            log_event(f"Updating network: {net_name} ({net_id})")

            existing_custom = net.get("custom", [])
            existing_apps = net.get("majorApplications", [])

            backup_config(net_id, existing_custom, existing_apps)

            updated_custom = merge_and_handle_duplicates(existing_custom, new_custom_rules)
            update_exclusion(net_id, updated_custom, existing_apps, api_key)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n?? Exiting... Operation cancelled by user.")
