import requests
import yaml
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.table import Table
import os
from pathlib import Path   # ➡️ add this


console = Console()

# Load YAML config
BULK_DIR = Path(__file__).resolve().parent / "data"

# ------------------------- VLAN Configuration ------------------------- #
def configure_vlan(base_url, headers, network_id):
    vlan_id = Prompt.ask("🔧 Enter VLAN ID")
    name = Prompt.ask("🏷️  Enter VLAN Name")
    subnet = Prompt.ask("🌐 Enter Subnet (e.g., 192.168.1.0/24)")
    appliance_ip = Prompt.ask("🖥️  Enter Appliance IP (e.g., 192.168.1.1)")

    url = f"{base_url}/networks/{network_id}/appliance/vlans"
    payload = {
        "id": vlan_id,
        "name": name,
        "subnet": subnet,
        "applianceIp": appliance_ip
    }
    response = requests.post(url, headers=headers, json=payload)
    if response.ok:
        console.print(f"✅ VLAN '{name}' created successfully.", style="green")
    else:
        console.print(f"❌ Failed to create VLAN: {response.text}", style="red")

def configure_vlan_bulk(base_url, headers, network_id):
    filepath = os.path.join(BULK_DIR, "vlans.yaml")
    with open(filepath) as file:
        data = yaml.safe_load(file)

    for vlan in data["vlans"]:
        url = f"{base_url}/networks/{network_id}/appliance/vlans"
        payload = {
            "id": vlan["id"],
            "name": vlan["name"],
            "subnet": vlan["subnet"],
            "applianceIp": vlan["appliance_ip"]
        }
        response = requests.post(url, headers=headers, json=payload)
        if response.ok:
            console.print(f"✅ VLAN '{vlan['name']}' created.", style="green")
        else:
            console.print(f"❌ Error adding VLAN '{vlan['name']}': {response.text}", style="red")

# ------------------------- DHCP Configuration ------------------------- #
def configure_dhcp(base_url, headers, network_id):
    # First, show a list of existing VLANs
    url = f"{base_url}/networks/{network_id}/appliance/vlans"
    response = requests.get(url, headers=headers)

    if not response.ok:
        console.print(f"❌ Failed to fetch VLANs: {response.text}", style="red")
        return

    vlans = response.json()
    console.print("\n[bold cyan]📋 Available VLANs:[/bold cyan]")
    for vlan in vlans:
        console.print(f"🔹 VLAN ID: [green]{vlan['id']}[/green], Name: [yellow]{vlan.get('name', 'N/A')}[/yellow], Subnet: {vlan.get('subnet', '-')}, Appliance IP: {vlan.get('applianceIp', '-')}")

    # Then proceed with manual input
    vlan_id = Prompt.ask("\n🔧 Enter VLAN ID to configure DHCP")
    mode = Prompt.ask("📡 Enter DHCP mode", choices=["enabled", "relay"])

    payload = {}

    if mode == "enabled":
        payload["dhcpHandling"] = "Run a DHCP server"
        payload["dhcpLeaseTime"] = Prompt.ask("⏳ Lease Time", choices=["30 minutes", "1 hour", "12 hours", "1 day", "1 week"])
        payload["dnsNameservers"] = Prompt.ask("🔎 DNS", choices=["upstream_dns", "google_dns", "opendns", "custom"])
        if payload["dnsNameservers"] == "custom":
            payload["dnsNameservers"] = Prompt.ask("🛠️ Enter custom DNS servers (comma separated)")
    else:
        payload["dhcpHandling"] = "Relay DHCP to another server"
        relay_servers = Prompt.ask("📨 Enter DHCP Relay Servers (comma-separated IPs)")
        payload["dhcpRelayServerIps"] = [ip.strip() for ip in relay_servers.split(",")]

    # PUT the update
    update_url = f"{base_url}/networks/{network_id}/appliance/vlans/{vlan_id}"
    update_response = requests.put(update_url, headers=headers, json=payload)

    if update_response.ok:
        console.print(f"✅ DHCP configuration for VLAN {vlan_id} updated successfully.", style="green")
    else:
        console.print(f"❌ Failed to configure DHCP: {update_response.text}", style="red")



# ------------------------- Fixed IP or MAC Binding bulk Configuration ------------------------- #
def configure_fixed_ip_bulk(base_url, headers, network_id):
    yaml_path = os.path.join(BULK_DIR, "fixed_ips.yaml")
    if not os.path.exists(yaml_path):
        console.print(f"[red]❌ File not found: {yaml_path}[/red]")
        return

    try:
        with open(yaml_path, 'r') as file:
            data = yaml.safe_load(file)

        fixed_ips = data.get("fixed_ips", [])
        if not fixed_ips:
            console.print("[red]❌ No fixed IP entries found in YAML.[/red]")
            return

        for entry in fixed_ips:
            vlan_id = str(entry["vlan_id"])
            mac = entry["mac"]
            ip = entry["ip"]
            name = entry["name"]

            # Fetch current VLAN config
            url = f"{base_url}/networks/{network_id}/appliance/vlans/{vlan_id}"
            get_response = requests.get(url, headers=headers)
            if not get_response.ok:
                console.print(f"[red]❌ Failed to retrieve VLAN {vlan_id}: {get_response.text}[/red]")
                continue

            vlan_config = get_response.json()
            fixed_assignments = vlan_config.get("fixedIpAssignments", {})
            fixed_assignments[mac] = {"ip": ip, "name": name}

            vlan_config["fixedIpAssignments"] = fixed_assignments

            put_response = requests.put(url, headers=headers, json=vlan_config)
            if put_response.ok:
                console.print(f"[green]✅ Reserved {ip} for {mac} in VLAN {vlan_id}[/green]")
            else:
                console.print(f"[red]❌ Failed to reserve IP {ip} for MAC {mac}: {put_response.text}[/red]")

    except Exception as e:
        console.print(f"[red]❌ Error in bulk Fixed IP config: {str(e)}[/red]")

# ------------------------- DHCP bulk Configuration ------------------------- #
def configure_dhcp_bulk(base_url, headers, network_id):
    console.print("\n[bold yellow]Bulk DHCP Configuration[/bold yellow]")

    yaml_path = "bulk_configs/dhcp.yaml"
    if not os.path.exists(yaml_path):
        console.print(f"[red]❌ YAML file not found at {yaml_path}[/red]")
        return

    try:
        with open(yaml_path, "r") as file:
            data = yaml.safe_load(file)

        dhcp_configs = data.get("dhcp_settings", [])
        if not dhcp_configs:
            console.print("[red]❌ No DHCP settings found in YAML.[/red]")
            return

        for config in dhcp_configs:
            vlan_id = config.pop("vlan_id", None)
            if not vlan_id:
                console.print("[red]❌ Missing 'vlan_id' in one DHCP config entry.[/red]")
                continue

            url = f"{base_url}/networks/{network_id}/appliance/vlans/{vlan_id}"
            response = requests.put(url, headers=headers, json=config)

            if response.ok:
                console.print(f"[green]✅ DHCP settings updated for VLAN {vlan_id}[/green]")
            else:
                console.print(f"[red]❌ Error in bulk DHCP config for VLAN {vlan_id}:[/red] {response.text}")

    except Exception as e:
        console.print(f"[red]❌ Exception during bulk DHCP config:[/red] {e}")

# ------------------------- Reserved Ranges ------------------------- #
def configure_reserved_range_bulk(base_url, headers, network_id):
    file_path = os.path.join(BULK_DIR, "reserved_ranges.yaml")
    try:
        with open(file_path, 'r') as file:
            data = yaml.safe_load(file)

        reserved_ranges = data.get("reserved_ranges", [])
        vlan_range_map = {}

        for item in reserved_ranges:
            vlan_id = str(item["vlan_id"])
            vlan_range_map.setdefault(vlan_id, []).append({
                "start": item["start"],
                "end": item["end"],
                "comment": item.get("comment", "")
            })

        for vlan_id, ranges in vlan_range_map.items():
            url = f"{base_url}/networks/{network_id}/appliance/vlans/{vlan_id}"
            get_response = requests.get(url, headers=headers)
            if get_response.ok:
                vlan_data = get_response.json()
                vlan_data["reservedIpRanges"] = ranges
                put_response = requests.put(url, headers=headers, json=vlan_data)
                if put_response.ok:
                    console.print(f"✅ Reserved IP ranges configured for VLAN {vlan_id}", style="bold green")
                else:
                    console.print(f"❌ Failed to configure reserved range for VLAN {vlan_id}: {put_response.text}", style="bold red")
            else:
                console.print(f"❌ VLAN {vlan_id} not found: {get_response.text}", style="bold red")
    except Exception as e:
        console.print(f"❌ Error reading YAML file or applying reserved ranges: {e}", style="bold red")

# ------------------------- Firewall L3 Configuration ------------------------- #

def configure_firewall_menu(base_url, headers, network_id):
    while True:
        console.print("\n🔐 [bold yellow]Firewall Configuration Menu[/bold yellow]")
        console.print("1. Configure [bold]L3 Outbound[/bold] Firewall Rules (Manual/YAML)")
        console.print("2. Configure [bold]Inbound[/bold] Firewall Rules (Manual/YAML)")
        console.print("3. Bulk Configure [bold green]L3 Outbound[/bold green] from YAML")
        console.print("4. Bulk Configure [bold green]Inbound[/bold green] from YAML")
        console.print("5. [bold]Return[/bold] to Appliance Menu")
        choice = Prompt.ask("Choose an option", choices=["1", "2", "3", "4", "5"], default="5")

        if choice == "1":
            configure_l3_firewall_rules(base_url, headers, network_id)
        elif choice == "2":
            configure_inbound_firewall_rules(base_url, headers, network_id)
        elif choice == "3":
            configure_l3_firewall_bulk(base_url, headers, network_id)
        elif choice == "4":
            configure_inbound_firewall_bulk(base_url, headers, network_id)
        else:
            break


def display_rules(rules):
    table = Table(title="Existing Firewall Rules", show_lines=True)
    table.add_column("Index", justify="center")
    table.add_column("Policy")
    table.add_column("Protocol")
    table.add_column("Src Cidr")
    table.add_column("Src Port")
    table.add_column("Dst Cidr")
    table.add_column("Dst Port")
    table.add_column("Comment")
    for i, rule in enumerate(rules):
        table.add_row(
            str(i),
            rule.get("policy", ""),
            rule.get("protocol", ""),
            rule.get("srcCidr", ""),
            rule.get("srcPort", ""),
            rule.get("destCidr", ""),
            rule.get("destPort", ""),
            rule.get("comment", "")
        )
    console.print(table)


def load_yaml_rules():
    yaml_path = Prompt.ask("Enter path to YAML file")
    with open(yaml_path, 'r') as f:
        return yaml.safe_load(f)


def configure_firewall_rules(base_url, headers, network_id, rule_type):
    endpoint = f"{base_url}/networks/{network_id}/appliance/firewall/{rule_type}FirewallRules"
    response = requests.get(endpoint, headers=headers)
    if response.status_code != 200:
        console.print(f"❌ Failed to get existing rules: {response.text}", style="bold red")
        return

    existing_rules = response.json().get("rules", [])
    display_rules(existing_rules)

    mode = Prompt.ask("Add rules manually or from YAML?", choices=["manual", "yaml"], default="manual")
    action = Prompt.ask("Would you like to overwrite or append?", choices=["overwrite", "append"], default="append")

    if mode == "yaml":
        new_rules = load_yaml_rules()
    else:
        new_rules = []
        while True:
            rule = {
                "policy": Prompt.ask("Policy", choices=["allow", "deny"]),
                "protocol": Prompt.ask("Protocol", default="any"),
                "srcCidr": Prompt.ask("Source CIDR", default="any"),
                "srcPort": Prompt.ask("Source Port", default="any"),
                "destCidr": Prompt.ask("Destination CIDR", default="any"),
                "destPort": Prompt.ask("Destination Port", default="any"),
                "comment": Prompt.ask("Comment", default="")
            }
            new_rules.append(rule)
            if not Confirm.ask("Add another rule?"):
                break

    final_rules = new_rules if action == "overwrite" else existing_rules + new_rules

    payload = {"rules": final_rules}
    put_response = requests.put(endpoint, headers=headers, json=payload)
    if put_response.status_code == 200:
        console.print("✅ Firewall rules updated successfully!", style="bold green")
    else:
        console.print(f"❌ Failed to update rules: {put_response.text}", style="bold red")


def configure_l3_firewall_rules(base_url, headers, network_id):
    configure_firewall_rules(base_url, headers, network_id, rule_type="l3")


def configure_inbound_firewall_rules(base_url, headers, network_id):
    configure_firewall_rules(base_url, headers, network_id, rule_type="inbound")

# ------------------------- Bulk L3 and Inbound Firewall Rules ------------------------- #

def configure_l3_firewall_bulk(base_url, headers, network_id):
    yaml_path = os.path.join(BULK_DIR, "l3_firewall_rules.yaml")
    if not os.path.exists(yaml_path):
        console.print(f"[red]❌ L3 firewall YAML file not found: {yaml_path}[/red]")
        return

    try:
        with open(yaml_path, 'r') as file:
            rules = yaml.safe_load(file)

        if not isinstance(rules, list):
            console.print(f"[red]❌ Invalid format. Expected a list of rules.[/red]")
            return

        url = f"{base_url}/networks/{network_id}/appliance/firewall/l3FirewallRules"
        response = requests.put(url, headers=headers, json={"rules": rules})

        if response.ok:
            console.print(f"[green]✅ L3 Firewall rules updated from l3_firewall.yaml[/green]")
        else:
            console.print(f"[red]❌ Failed to update L3 rules: {response.text}[/red]")

    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")


def configure_inbound_firewall_bulk(base_url, headers, network_id):
    yaml_path = os.path.join(BULK_DIR, "inbound_firewall_rules.yaml")
    if not os.path.exists(yaml_path):
        console.print(f"[red]❌ Inbound firewall YAML file not found: {yaml_path}[/red]")
        return

    try:
        with open(yaml_path, 'r') as file:
            rules = yaml.safe_load(file)

        if not isinstance(rules, list):
            console.print(f"[red]❌ Invalid format. Expected a list of rules.[/red]")
            return

        url = f"{base_url}/networks/{network_id}/appliance/firewall/inboundFirewallRules"
        response = requests.put(url, headers=headers, json={"rules": rules})

        if response.ok:
            console.print(f"[green]✅ Inbound Firewall rules updated from inbound_firewall.yaml[/green]")
        else:
            console.print(f"[red]❌ Failed to update Inbound rules: {response.text}[/red]")

    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")



# ------------------------- Appliance Config Menu ------------------------- #
def appliance_config_menu(network_id, headers):
    base_url = "https://api.meraki.com/api/v1"
    while True:
        console.print("\n[bold yellow]🔧 Appliance Configuration Menu[/bold yellow]", style="cyan")
        console.print("1. Configure VLAN")
        console.print("2. Configure DHCP")
        console.print("3. Bulk Configure VLAN")
        console.print("4. Bulk Configure DHCP")
        console.print("5. Bulk Configure Fixed IP")
        console.print("6. Bulk Configure Reserved Ranges")
        console.print("7. Configure L3 Firewall Rules")
        console.print("8. Back to Main Menu")



        choice = Prompt.ask("Choose an option", choices=["1", "2", "3", "4", "5", "6", "7", "8"])

        if choice == "1":
            configure_vlan(base_url, headers, network_id)
        elif choice == "2":
            configure_dhcp(base_url, headers, network_id)
        elif choice == "3":
            configure_vlan_bulk(base_url, headers, network_id)
        elif choice == "4":
            configure_dhcp_bulk(base_url, headers, network_id)
        elif choice == "5":
            configure_fixed_ip_bulk(base_url, headers, network_id)
        elif choice == "6":
            configure_reserved_range_bulk(base_url, headers, network_id)
        elif choice == "7":
            configure_firewall_menu(base_url, headers, network_id)
        elif choice == "8":
            break


    
            




