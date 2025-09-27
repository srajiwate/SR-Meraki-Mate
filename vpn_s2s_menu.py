from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table
import requests

console = Console()

def vpn_s2s_menu(base_url, headers, org_id, network_id):
    while True:
        console.rule("[bold blue]🌐 Site-to-Site VPN Menu")
        console.print("[1] View Third-Party VPN Peers")
        console.print("[2] View Network Site-to-Site VPN Settings")
        console.print("[3] 🔙 Return to Main Menu")

        choice = Prompt.ask("Choose an option", choices=["1", "2", "3"], default="3")

        if choice == "1":
            view_third_party_vpn_peers(base_url, headers, org_id)
        elif choice == "2":
            view_network_site_to_site_vpn(base_url, headers, network_id)
        elif choice == "3":
            break

# ---------------- Helper Functions ---------------- #

def mask_secret(secret: str) -> str:
    """Mask the secret, showing only the first and last two characters."""
    if secret and secret != "N/A":
        return f"{secret[:2]}****{secret[-2:]}"
    return "N/A"

def has_write_access(base_url, headers, org_id) -> bool:
    """
    Check if the API key has write access by attempting a harmless POST.
    Creates a temporary policy object and deletes it immediately.
    """
    test_url = f"{base_url}/organizations/{org_id}/policyObjects"
    test_payload = {
        "name": "test-check",
        "category": "network",
        "type": "cidr",
        "cidr": "192.0.2.1/32"   # TEST-NET IP
    }
    try:
        response = requests.post(test_url, headers=headers, json=test_payload)
        if response.status_code == 201:
            # Clean up created object
            obj_id = response.json().get("id")
            if obj_id:
                requests.delete(f"{test_url}/{obj_id}", headers=headers)
            return True
    except requests.RequestException:
        pass
    return False

# ---------------- View Functions ---------------- #

def view_third_party_vpn_peers(base_url, headers, org_id):
    url = f"{base_url}/organizations/{org_id}/appliance/vpn/thirdPartyVPNPeers"
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        vpn_peers = response.json().get("peers", [])

        if not vpn_peers:
            console.print("🚫 No VPN peers found.", style="bold red")
            return

        # Check if user has write access
        can_unmask = has_write_access(base_url, headers, org_id)

        table = Table(title="Site-to-Site VPN Peers", show_lines=True)
        table.add_column("Name", style="cyan", no_wrap=True)
        table.add_column("Public IP", style="green")
        table.add_column("IKE Version", justify="center")
        table.add_column("Secret")
        table.add_column("Subnets")
        table.add_column("Priority")

        for peer in vpn_peers:
            secret = peer.get("secret", "N/A")
            masked_secret = mask_secret(secret)

            # Allow unmask only if API key has write permissions
            if can_unmask and Prompt.ask(
                f"Do you want to unmask the secret for peer '{peer.get('name', 'N/A')}'?",
                choices=["yes", "no"], default="no"
            ) == "yes":
                masked_secret = secret

            table.add_row(
                peer.get("name", "N/A"),
                peer.get("publicIp", "N/A"),
                peer.get("ikeVersion", "N/A"),
                masked_secret,
                ", ".join(peer.get("privateSubnets", [])),
                str(peer.get("priorityInGroup", "N/A"))
            )

        console.print(table)
    except requests.exceptions.RequestException as e:
        console.print(f"❌ Error fetching VPN settings: {e}", style="bold red")

def view_network_site_to_site_vpn(base_url, headers, network_id):
    url = f"{base_url}/networks/{network_id}/appliance/vpn/siteToSiteVpn"
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()

        console.rule("[bold green]🔍 Site-to-Site VPN Settings")
        console.print(f"📡 Mode: [bold]{data.get('mode', 'N/A')}[/bold]")

        # Display Subnets
        subnets = data.get("subnets", [])
        if subnets:
            subnet_table = Table(title="🔁 Subnets Participating in VPN")
            subnet_table.add_column("Local Subnet", style="cyan")
            subnet_table.add_column("Use VPN", style="green")
            for subnet in subnets:
                subnet_table.add_row(
                    subnet.get("localSubnet", "N/A"),
                    str(subnet.get("useVpn", False))
                )
            console.print(subnet_table)
        else:
            console.print("⚠️ No subnets found in VPN config.")

        # Display Hubs (for hub mode)
        if data.get("mode") == "hub":
            hubs = data.get("hubs", [])
            if hubs:
                hub_table = Table(title="🏢 Hub Networks")
                hub_table.add_column("Hub ID", style="cyan")
                hub_table.add_column("Use Default Route", style="green")
                for hub in hubs:
                    hub_table.add_row(
                        hub.get("hubId", "N/A"),
                        str(hub.get("useDefaultRoute", False))
                    )
                console.print(hub_table)
            else:
                console.print("ℹ️ No hubs configured.")

    except requests.exceptions.RequestException as e:
        console.print(f"❌ Error fetching site-to-site VPN settings: {e}")
