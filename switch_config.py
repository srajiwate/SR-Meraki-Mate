from rich.console import Console
from rich.prompt import Prompt
import requests

BASE_URL = "https://api.meraki.com/api/v1"
console = Console()


def rename_switches(network_id, headers):
    url = f"{BASE_URL}/networks/{network_id}/devices"
    devices = requests.get(url, headers=headers).json()
    switches = [d for d in devices if d.get("model", "").startswith("MS")]

    for switch in switches:
        serial = switch["serial"]
        console.print(f"\n[bold blue]?? Switch:[/bold blue] {switch.get('name', serial)}")
        if Prompt.ask("Rename this switch?", choices=["yes", "no"], default="no") == "yes":
            new_name = Prompt.ask("Enter new name")
            url = f"{BASE_URL}/devices/{serial}"
            response = requests.put(url, headers=headers, json={"name": new_name})
            if response.status_code == 200:
                console.print(f"? Renamed {serial} to '{new_name}'", style="green")


def expand_port_list(port_input):
    ports = []
    for part in port_input.split(","):
        if "-" in part:
            start, end = map(int, part.strip().split("-"))
            ports.extend([str(i) for i in range(start, end + 1)])
        elif part.strip().isdigit():
            ports.append(part.strip())
    return ports


def apply_port_config(serial, headers, config):
    ports_url = f"{BASE_URL}/devices/{serial}/switch/ports"
    current_ports = requests.get(ports_url, headers=headers).json()

    for port in current_ports:
        port_id = port['portId']
        if port_id in config.get("access", {}):
            vlan = config["access"][port_id]
            payload = {**port, "portMode": "access", "vlan": vlan, "type": "access"}
        elif port_id in config.get("trunk", {}):
            trunk_cfg = config["trunk"][port_id]
            payload = {
                **port,
                "portMode": "trunk",
                "vlan": trunk_cfg["native"],
                "nativeVlan": trunk_cfg["native"],
                "allowedVlans": trunk_cfg["allowed"],
                "type": "trunk"
            }
        else:
            continue

        update_url = f"{BASE_URL}/devices/{serial}/switch/ports/{port_id}"
        r = requests.put(update_url, headers=headers, json=payload)
        msg = f"? Port {port_id} updated" if r.status_code == 200 else f"? Failed: {r.text}"
        console.print(msg, style="green" if r.status_code == 200 else "red")


def configure_ports(network_id, headers):
    url = f"{BASE_URL}/networks/{network_id}/devices"
    devices = requests.get(url, headers=headers).json()
    switches = [d for d in devices if d.get("model", "").startswith("MS")]

    configured = False
    saved_config = {}

    for idx, switch in enumerate(switches):
        serial = switch["serial"]
        name = switch.get('name', serial)
        console.print(f"\n[bold blue]?? Switch:[/bold blue] {name}")

        if idx != 0 and configured:
            replicate = Prompt.ask("Replicate previous switch config to this one?", choices=["yes", "no"], default="no")
            if replicate == "yes":
                apply_port_config(serial, headers, saved_config)
                continue

        if Prompt.ask("Configure ports on this switch?", choices=["yes", "no"], default="no") != "yes":
            continue

        ports_url = f"{BASE_URL}/devices/{serial}/switch/ports"
        ports = requests.get(ports_url, headers=headers).json()

        config_map = {"access": {}, "trunk": {}}

        access_ports = Prompt.ask("Access port numbers (e.g. 1-3,5)", default="").strip()
        if access_ports:
            vlan_id = int(Prompt.ask("VLAN ID for access ports"))
            for port in ports:
                if port['portId'] in expand_port_list(access_ports):
                    update_url = f"{BASE_URL}/devices/{serial}/switch/ports/{port['portId']}"
                    payload = {**port, "portMode": "access", "vlan": vlan_id, "type": "access"}
                    r = requests.put(update_url, headers=headers, json=payload)
                    console.print(f"?? Port {port['portId']} -> Access VLAN {vlan_id}" if r.status_code == 200 else f"? Failed: {r.text}", style="green" if r.status_code == 200 else "red")
                    config_map["access"][port['portId']] = vlan_id

        trunk_ports = Prompt.ask("Trunk port numbers (e.g. 2-4,8)", default="").strip()
        if trunk_ports:
            native_vlan = int(Prompt.ask("Native VLAN"))
            allowed_vlans = Prompt.ask("Allowed VLANs (e.g. 1,10-20)").strip()
            for port in ports:
                if port['portId'] in expand_port_list(trunk_ports):
                    update_url = f"{BASE_URL}/devices/{serial}/switch/ports/{port['portId']}"
                    payload = {
                        **port,
                        "portMode": "trunk",
                        "vlan": native_vlan,
                        "nativeVlan": native_vlan,
                        "allowedVlans": allowed_vlans,
                        "type": "trunk"
                    }
                    r = requests.put(update_url, headers=headers, json=payload)
                    console.print(f"?? Port {port['portId']} -> Trunk VLAN {native_vlan}" if r.status_code == 200 else f"? Failed: {r.text}", style="green" if r.status_code == 200 else "red")
                    config_map["trunk"][port['portId']] = {"native": native_vlan, "allowed": allowed_vlans}

        saved_config = config_map
        configured = True


def switch_config_menu(network_id, headers):
    while True:
        console.print("\n📶 [bold magenta]Switch Configuration[/bold magenta]:")
        console.print("1. 📡 Rename Switches")
        console.print("2. 🔐 Configure Switch Ports")
        console.print("3. ⬅️ Back to Main Menu")
        choice = Prompt.ask("Select an option", choices=["1", "2", "3"], default="3")
        if choice == "1":
            rename_switches(network_id, headers)
        elif choice == "2":
            configure_ports(network_id, headers)
        elif choice == "3":
            break
