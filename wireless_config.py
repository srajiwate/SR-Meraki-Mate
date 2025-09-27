from rich.console import Console
from rich.prompt import Prompt
import requests
import getpass

console = Console()
BASE_URL = "https://api.meraki.com/api/v1"

def rename_access_points(network_id, headers):
    url = f"{BASE_URL}/networks/{network_id}/devices"
    devices = requests.get(url, headers=headers).json()
    aps = [d for d in devices if d.get("model", "").startswith("MR")]
    for ap in aps:
        serial = ap["serial"]
        console.print(f"\n📡 [bold blue]Access Point:[/bold blue] {ap.get('name', serial)}")
        if Prompt.ask("Rename this access point?", choices=["yes", "no"]) == "yes":
            new_name = Prompt.ask("Enter new name")
            rename_device(serial, new_name, headers)

def rename_device(serial, name, headers):
    url = f"{BASE_URL}/devices/{serial}"
    requests.put(url, headers=headers, json={"name": name})

def configure_ssids(network_id, headers):
    num = int(Prompt.ask("How many SSIDs to configure?", default="1"))
    for i in range(num):
        ssid_number = int(Prompt.ask(f"SSID number (0–14) for SSID #{i+1}"))
        name = Prompt.ask("SSID Name")
        auth_mode = Prompt.ask("SSID Type", choices=["guest", "corporate"])

        ip_mode = Prompt.ask("IP Assignment Mode", choices=["NAT mode", "Bridge mode"], default="NAT mode")

        # WPA Encryption Mode Choices
        wpa_modes = {
            "1": "WPA2 only",
            "2": "WPA1 and WPA2",
            "3": "WPA3 Transition Mode",
            "4": "WPA3 only",
            "5": "WPA3 192-bit Security"
        }
        console.print("\n🔐 [bold cyan]WPA Encryption Modes:[/bold cyan]")
        for k, v in wpa_modes.items():
            console.print(f"{k}. {v}")
        selected_wpa = Prompt.ask("Select WPA Encryption Mode", choices=list(wpa_modes.keys()), default="1")
        selected_wpa_mode = wpa_modes[selected_wpa]

        payload = {
            "name": name,
            "enabled": True,
            "splashPage": "None",
            "ssidAdminAccessible": False,
            "dot11r": {"enabled": False, "adaptive": False},
            "minBitrate": 11,
            "bandSelection": "Dual band operation",
            "ipAssignmentMode": ip_mode,
            "visible": True,
            "availableOnAllAps": True,
            "wpaEncryptionMode": selected_wpa_mode
        }

        # Enable WPA3-required fields if applicable
        if selected_wpa_mode in ["WPA3 Transition Mode", "WPA3 only", "WPA3 192-bit Security"]:
            payload["dot11w"] = {"enabled": True, "required": False}
        else:
            payload["dot11w"] = {"enabled": False, "required": False}

        # Auth Configuration
        if auth_mode == "guest":
            payload.update({
                "authMode": "psk",
                "psk": Prompt.ask("Enter PSK (min 8 chars)"),
                "encryptionMode": "wpa"
            })
        else:
            radius_ip = Prompt.ask("RADIUS Server IP")
            radius_port = int(Prompt.ask("RADIUS Port", default="1812"))
            shared_secret = getpass.getpass("RADIUS Shared Secret (input hidden): ")

            acct_ip = Prompt.ask("RADIUS Accounting Server IP", default=radius_ip)
            acct_port = int(Prompt.ask("RADIUS Accounting Port", default="1813"))

            payload.update({
                "authMode": "8021x-radius",
                "encryptionMode": "wpa-eap",
                "radiusServers": [{"host": radius_ip, "port": radius_port, "secret": shared_secret}],
                "radiusAccountingEnabled": True,
                "radiusAccountingServers": [{"host": acct_ip, "port": acct_port, "secret": shared_secret}],
                "radiusTestingEnabled": True,
                "radiusServerTimeout": 1,
                "radiusServerAttemptsLimit": 3
            })

        # VLAN tagging for Bridge mode
        if ip_mode == "Bridge mode":
            if Prompt.ask("Enable VLAN Tagging?", choices=["yes", "no"], default="no") == "yes":
                vlan_id = int(Prompt.ask("Enter VLAN ID"))
                payload["useVlanTagging"] = True
                payload["defaultVlanId"] = vlan_id
            else:
                payload["useVlanTagging"] = False

        url = f"{BASE_URL}/networks/{network_id}/wireless/ssids/{ssid_number}"
        response = requests.put(url, headers=headers, json=payload)

        if response.status_code == 200:
            console.print(f"✅ SSID '{name}' configured successfully.", style="green")
        else:
            console.print(f"❌ Failed to configure SSID: {response.text}", style="red")

def wireless_config_menu(network_id, headers):
    while True:
        console.print("\n📶 [bold magenta]Wireless Configuration[/bold magenta]:")
        console.print("1. 📡 Rename Access Points")
        console.print("2. 🔐 Configure SSIDs")
        console.print("3. ⬅️  Back to Main Menu")
        choice = Prompt.ask("Select an option", choices=["1", "2", "3"], default="3")
        if choice == "1":
            rename_access_points(network_id, headers)
        elif choice == "2":
            configure_ssids(network_id, headers)
        elif choice == "3":
            break
