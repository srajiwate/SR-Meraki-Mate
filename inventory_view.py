import requests
from rich.console import Console
from rich.table import Table
from rich.prompt import Confirm
import ipaddress
from time import sleep
from rich.spinner import Spinner
from rich.live import Live
import pandas as pd
from pathlib import Path
from datetime import datetime

# 🔧 Setup paths
OUTPUT_DIR = Path(__file__).resolve().parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

console = Console()

# ---------------- API Calls ---------------- #
def get_networks(headers, org_id):
    url = f"https://api.meraki.com/api/v1/organizations/{org_id}/networks"
    return requests.get(url, headers=headers).json()

def get_devices(headers, network_id):
    url = f"https://api.meraki.com/api/v1/networks/{network_id}/devices"
    return requests.get(url, headers=headers).json()

def get_device_detail(headers, serial):
    url = f"https://api.meraki.com/api/v1/devices/{serial}"
    return requests.get(url, headers=headers).json()

def get_appliance_vlans(headers, network_id):
    url = f"https://api.meraki.com/api/v1/networks/{network_id}/appliance/vlans"
    return requests.get(url, headers=headers).json()

def get_switch_l3_interfaces(headers, serial):
    url = f"https://api.meraki.com/api/v1/devices/{serial}/switch/routing/interfaces"
    return requests.get(url, headers=headers).json()

def get_firmware_upgrades(headers, org_id):
    url = f"https://api.meraki.com/api/v1/organizations/{org_id}/firmware/upgrades"
    return requests.get(url, headers=headers).json()

# ---------------- Utility ---------------- #
def ip_in_subnet(ip, subnet):
    try:
        return ipaddress.IPv4Address(ip) in ipaddress.IPv4Network(subnet, strict=False)
    except:
        return False

def fetch_with_spinner(task_function, *args, message="Processing...", **kwargs):
    with Live(Spinner("dots", text=message), refresh_per_second=10):
        return task_function(*args, **kwargs)

# ---------------- Firmware mapping ---------------- #
def build_firmware_lookup(firmware_data):
    latest_firmware = {}
    for upgrade in firmware_data:
        net_id = upgrade.get("network", {}).get("id")
        product = upgrade.get("productTypes")
        version = upgrade.get("toVersion", {}).get("shortName", "")
        if net_id and product and version:
            latest_firmware[(net_id, product)] = version
    return latest_firmware

def model_to_product_type(model):
    if model.startswith("MX"):
        return "appliance"
    elif model.startswith("MR"):
        return "wireless"
    elif model.startswith("MS"):
        return "switch"
    return None

# ---------------- Main Function ---------------- #
def show_inventory(headers, org_id):
    export_data = []
    search_text = console.input(
        "[bold green]🔍 Enter IP, name, serial, subnet, or any field to filter (or press Enter to show all): [/bold green]"
    ).strip().lower()

    networks = fetch_with_spinner(get_networks, headers, org_id, message="🔄 Fetching network list...")
    firmware_upgrades = fetch_with_spinner(get_firmware_upgrades, headers, org_id, message="📦 Fetching firmware info...")
    firmware_lookup = build_firmware_lookup(firmware_upgrades)

    for net in networks:
        devices = fetch_with_spinner(get_devices, headers, net['id'], message=f"📡 Fetching devices for {net['name']}...")
        matched_rows = []
        table = Table(title=f"📡 Network: {net['name']}")
        table.add_column("Model", style="cyan")
        table.add_column("Device Name", style="green")
        table.add_column("Serial", style="yellow")
        table.add_column("LAN IP")
        table.add_column("WAN IP")
        table.add_column("L3 Type")
        table.add_column("VLAN ID")
        table.add_column("VLAN Name / Interface")
        table.add_column("Subnet")
        table.add_column("Interface IP")
        table.add_column("Firmware", style="blue")
        table.add_column("Network", style="bright_magenta")

        for device in devices:
            model = device.get("model", "N/A")
            serial = device.get("serial", "N/A")
            name = device.get("name", "N/A")
            lan_ip = device.get("lanIp", "—")
            device_detail = fetch_with_spinner(get_device_detail, headers, serial, message=f"🔍 Getting device details: {serial}")
            wan_ip = device_detail.get("wan1Ip", "—")

            product_type = model_to_product_type(model)
            firmware = firmware_lookup.get((net['id'], product_type), "—")

            # MR (Access Point)
            if model.startswith("MR"):
                row = {
                    "model": model,
                    "device_name": name,
                    "serial": serial,
                    "lan_ip": lan_ip,
                    "wan_ip": wan_ip,
                    "l3_type": "MR Access Point",
                    "vlan_id": "—",
                    "vlan_name": "—",
                    "subnet": "—",
                    "interface_ip": "—",
                    "firmware": firmware,
                    "network": net['name']
                }

                if not search_text or any(search_text in str(val).lower() for val in row.values()):
                    table.add_row(*row.values())
                    matched_rows.append(row)
                    export_data.append(row)
                continue

            # MX VLANs
            if model.startswith("MX"):
                try:
                    vlans = fetch_with_spinner(get_appliance_vlans, headers, net['id'], message=f"🌐 Fetching MX VLANs for {net['name']}")
                    for v in vlans:
                        row = {
                            "model": model,
                            "device_name": name,
                            "serial": serial,
                            "lan_ip": lan_ip,
                            "wan_ip": wan_ip,
                            "l3_type": "MX VLAN",
                            "vlan_id": str(v.get("id", "—")),
                            "vlan_name": v.get("name", "—"),
                            "subnet": v.get("subnet", "—"),
                            "interface_ip": v.get("applianceIp", "—"),
                            "firmware": firmware,
                            "network": net['name']
                        }

                        if not search_text or any(search_text in str(val).lower() for val in row.values()):
                            table.add_row(*row.values())
                            matched_rows.append(row)
                            export_data.append(row)
                except:
                    continue

            # MS L3 Interfaces
            elif model.startswith("MS"):
                try:
                    interfaces = fetch_with_spinner(get_switch_l3_interfaces, headers, serial, message=f"🔧 Fetching MS L3 interfaces for {serial}")
                    for iface in interfaces:
                        row = {
                            "model": model,
                            "device_name": name,
                            "serial": serial,
                            "lan_ip": lan_ip,
                            "wan_ip": wan_ip,
                            "l3_type": "MS L3 Interface",
                            "vlan_id": str(iface.get("vlanId", "—")),
                            "vlan_name": iface.get("name", "—"),
                            "subnet": iface.get("subnet", "—"),
                            "interface_ip": iface.get("interfaceIp", "—"),
                            "firmware": firmware,
                            "network": net['name']
                        }

                        if not search_text or any(search_text in str(val).lower() for val in row.values()):
                            table.add_row(*row.values())
                            matched_rows.append(row)
                            export_data.append(row)
                except:
                    continue

        if matched_rows:
            console.print(table)
            sleep(1)

    # ---------------- Export Section ---------------- #
    if export_data:
        if Confirm.ask("\n💾 Do you want to export matching results to CSV/Excel?", default=True):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            csv_path = OUTPUT_DIR / f"advanced_meraki_inventory_{timestamp}.csv"
            excel_path = OUTPUT_DIR / f"advanced_meraki_inventory_{timestamp}.xlsx"

            df = pd.DataFrame(export_data)
            df.to_csv(csv_path, index=False)
            df.to_excel(excel_path, index=False)

            console.print(f"[bold blue]✅ Exported to '{csv_path}'[/bold blue]")
            console.print(f"[bold blue]✅ Exported to '{excel_path}'[/bold blue]")
    else:
        console.print("[bold red]❌ No matching entries found. Nothing to export.[/bold red]")
