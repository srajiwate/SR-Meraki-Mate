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
BACKUP_DIR = "vpn_exclusion_backups"
EXPORT_DIR = "vpn_exclusion_exports"
REMOVAL_KEYS = ["destination"]  # Only match on destination now

# === LOGGING SETUP ===
logging.basicConfig(
    filename='vpn_exclusion_removal.log',
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

# === BACKUP FUNCTION ===
def backup_config(network_id, custom, major):
    os.makedirs(BACKUP_DIR, exist_ok=True)
    backup_file = os.path.join(
        BACKUP_DIR,
        f"{network_id}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    with open(backup_file, 'w') as f:
        json.dump({"custom": custom, "majorApplications": major}, f, indent=2)
    log_event(f"? Backup saved: {backup_file}")

# === EXPORT FUNCTION ===
def export_to_excel(network_name, network_id, custom, major):
    os.makedirs(EXPORT_DIR, exist_ok=True)
    writer = pd.ExcelWriter(
        os.path.join(EXPORT_DIR, f"{network_name}_{network_id}_export.xlsx")
    )
    pd.DataFrame(custom).to_excel(writer, sheet_name="CustomRules", index=False)
    pd.DataFrame(major).to_excel(writer, sheet_name="MajorApplications", index=False)
    writer.close()
    log_event(f"? Exported current exclusions for {network_name} to Excel.")

# === READ INPUT ===
def read_input_file(path):
    df_ip = pd.read_excel(path, sheet_name='IPList')
    df_apps = pd.read_excel(path, sheet_name='AppList') if 'AppList' in pd.ExcelFile(path).sheet_names else pd.DataFrame()
    return df_ip, df_apps

def remove_matching_entries(existing, to_remove_list):
    to_remove_set = set(str(row['destination']).strip() for _, row in to_remove_list.iterrows())
    new_entries = [entry for entry in existing if str(entry.get("destination")) not in to_remove_set]
    removed_count = len(existing) - len(new_entries)
    return new_entries, removed_count

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
    input_file = data_dir / "vpn_exclusion_removal_input.xlsx"
    orgs_df = pd.read_excel(input_file, sheet_name="Organizations")

    for _, row in orgs_df.iterrows():
        org_id = str(row["OrganizationId"])
        log_event(f"\n--- Processing Org {org_id} ---")

        url = f"https://api.meraki.com/api/v1/organizations/{org_id}/appliance/trafficShaping/vpnExclusions/byNetwork"
        headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        networks = response.json().get("items", [])

        if not networks:
            log_event(f"?? No networks found for Org {org_id}")
            continue

        for net in networks:
            net_id = net.get("networkId")
            net_name = net.get("networkName")
            custom = net.get("custom", [])
            major = net.get("majorApplications", [])

            backup_config(net_id, custom, major)
            export_to_excel(net_name, net_id, custom, major)

        # Prompt once after all exports
        removal_path = input("Enter path to Excel file containing rules to remove (after reviewing exports): ").strip()
        if not os.path.exists(removal_path):
            log_event("?? Provided file path does not exist. Skipping removal.")
            return

        df_ips, df_apps = read_input_file(removal_path)

        for net in networks:
            net_id = net.get("networkId")
            net_name = net.get("networkName")
            custom = net.get("custom", [])
            major = net.get("majorApplications", [])

            custom, removed_ips = remove_matching_entries(custom, df_ips)
            app_ids_to_remove = set(df_apps['id'].astype(str).str.strip()) if not df_apps.empty else set()
            major_new = [entry for entry in major if entry['id'] not in app_ids_to_remove]
            removed_apps = len(major) - len(major_new)

            log_event(f"\n? Network {net_name} ({net_id}):")
            log_event(f" - Removed {removed_ips} custom IP entries.")
            log_event(f" - Removed {removed_apps} majorApplication entries.")

            update_exclusion(net_id, custom, major_new, api_key)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n?? Exiting... Operation cancelled by user.")
