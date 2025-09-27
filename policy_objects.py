import requests
import yaml
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.table import Table
from pathlib import Path

console = Console()
BULK_DIR = Path(__file__).resolve().parent / "data"

def view_policy_object_groups(base_url, headers, organization_id):
    url = f"{base_url}/organizations/{organization_id}/policyObjects/groups"
    response = requests.get(url, headers=headers)

    if response.status_code == 404:
        console.print("[yellow]⚠️ No policy object groups exist.")
        return

    if response.ok:
        groups = response.json()
        if not groups:
            console.print("[yellow]⚠️ No policy object groups found.")
            return

        table = Table(title="📦 Policy Object Groups")
        table.add_column("ID", style="cyan")
        table.add_column("Name", style="magenta")
        table.add_column("Object IDs", style="green")

        for group in groups:
            table.add_row(group.get("id", "-"), group.get("name", "-"), ", ".join(group.get("objectIds", [])))
        console.print(table)
    else:
        console.print(f"[red]❌ Error fetching object groups: {response.text}")

def view_policy_objects(base_url, headers, organization_id):
    url = f"{base_url}/organizations/{organization_id}/policyObjects"
    response = requests.get(url, headers=headers)

    if response.ok:
        objects = response.json()
        if not objects:
            console.print("[yellow]⚠️ No policy objects found.")
            return

        table = Table(title="📘 Policy Objects")
        table.add_column("ID", style="cyan")
        table.add_column("Name", style="magenta")
        table.add_column("Type", style="green")
        table.add_column("Category", style="blue")

        for obj in objects:
            table.add_row(obj.get("id", "-"), obj.get("name", "-"), obj.get("type", "-"), obj.get("category", "-"))
        console.print(table)
    else:
        console.print(f"[red]❌ Error fetching policy objects: {response.text}")

# ---------------- Delete Policy Objects ---------------- #
def delete_policy_objects(base_url, headers, org_id):
    url = f"{base_url}/organizations/{org_id}/policyObjects"
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        console.print(f"[red]❌ Failed to fetch policy objects: {response.text}[/red]")
        return

    all_objects = response.json()
    if not all_objects:
        console.print("[yellow]⚠️ No policy objects found.[/yellow]")
        return

    search_term = Prompt.ask("🔍 Enter name or IP (partial or exact) to search")
    matches = [obj for obj in all_objects if search_term.lower() in obj.get("name", "").lower() or search_term in obj.get("cidr", "")]

    if not matches:
        console.print("[yellow]⚠️ No matching policy objects found.")
        return

    table = Table(title="🔍 Matching Policy Objects")
    table.add_column("Index", justify="right")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="magenta")
    table.add_column("Type", style="green")
    table.add_column("CIDR", style="blue")

    for idx, obj in enumerate(matches, 1):
        table.add_row(str(idx), obj.get("id", "-"), obj.get("name", "-"), obj.get("type", "-"), obj.get("cidr", "-"))
    console.print(table)

    indexes = Prompt.ask("🔢 Enter index(es) to delete (comma-separated), or press Enter to cancel", default="")
    if not indexes:
        return

    try:
        indexes = [int(i.strip()) for i in indexes.split(',') if i.strip().isdigit() and 1 <= int(i.strip()) <= len(matches)]
    except ValueError:
        console.print("[red]❌ Invalid selection.[/red]")
        return

    for idx in indexes:
        obj = matches[idx - 1]
        confirm = Confirm.ask(f"❗ Are you sure you want to delete object '{obj['name']}'?")
        if confirm:
            del_url = f"{base_url}/organizations/{org_id}/policyObjects/{obj['id']}"
            del_response = requests.delete(del_url, headers=headers)
            if del_response.status_code == 204:
                console.print(f"[green]✅ Deleted object: {obj['name']}[/green]")
            else:
                console.print(f"[red]❌ Failed to delete object {obj['name']}: {del_response.text}[/red]")

def delete_policy_object_group(base_url, headers, org_id):
    url = f"{base_url}/organizations/{org_id}/policyObjects/groups"
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        console.print(f"[red]❌ Failed to fetch policy object groups: {response.text}[/red]")
        return

    groups = response.json()
    if not groups:
        console.print("[yellow]⚠️ No policy object groups found.[/yellow]")
        return

    table = Table(title="📦 Policy Object Groups")
    table.add_column("Index", justify="right")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="magenta")
    table.add_column("Object IDs", style="green")

    for idx, group in enumerate(groups, 1):
        table.add_row(str(idx), group.get("id", "-"), group.get("name", "-"), ", ".join(group.get("objectIds", [])))
    console.print(table)

    indexes = Prompt.ask("🔢 Enter index(es) of group(s) to delete (comma-separated), or press Enter to cancel", default="")
    if not indexes:
        return

    try:
        indexes = [int(i.strip()) for i in indexes.split(',') if i.strip().isdigit() and 1 <= int(i.strip()) <= len(groups)]
    except ValueError:
        console.print("[red]❌ Invalid selection.[/red]")
        return

    for idx in indexes:
        group = groups[idx - 1]
        group_id = group["id"]
        confirm = Confirm.ask(f"❗ Are you sure you want to delete group '{group['name']}'?")
        if confirm:
            del_url = f"{base_url}/organizations/{org_id}/policyObjects/groups/{group_id}"
            del_response = requests.delete(del_url, headers=headers)
            if del_response.status_code == 204:
                console.print(f"[green]✅ Successfully deleted group: {group['name']}[/green]")
            else:
                console.print(f"[red]❌ Failed to delete group: {del_response.text}[/red]")

# ---------------- Create Policy Objects from YAML ---------------- #
def create_policy_objects_from_ip_yaml(base_url, headers, org_id):
    file_path = BULK_DIR / "policy_objects.yaml"
    
    if not file_path.exists():
        console.print(f"[red]❌ YAML file not found: {file_path}[/red]")
        return

    with open(file_path, "r") as f:
        data = yaml.safe_load(f)

    ip_list = data.get("ips", [])
    if not ip_list:
        console.print("[red]❌ No IPs found in YAML file.[/red]")
        return

    base_name = Prompt.ask("📛 Enter base name for policy objects (e.g., Web-Server)")
    created_ids = []

    for ip in ip_list:
        sanitized_ip = ip.replace('.', '-')
        name = f"{base_name}-{sanitized_ip}"
        payload = {
            "name": name,
            "category": "network",
            "type": "cidr",
            "cidr": f"{ip}/32"
        }
        url = f"{base_url}/organizations/{org_id}/policyObjects"
        response = requests.post(url, headers=headers, json=payload)

        if response.status_code == 201:
            obj = response.json()
            created_ids.append(obj["id"])
            console.print(f"[green]✅ Created: {name}[/green]")
        else:
            console.print(f"[red]❌ Failed to create {name}: {response.text}[/red]")

    if created_ids and Confirm.ask("📦 Group created objects into object group(s)?"):
        max_per_group = 149
        group_chunks = [created_ids[i:i+max_per_group] for i in range(0, len(created_ids), max_per_group)]

        for idx, chunk in enumerate(group_chunks, 1):
            group_name = f"{base_name}_Group_{idx}"
            payload = {"name": group_name, "objectIds": chunk}
            group_url = f"{base_url}/organizations/{org_id}/policyObjects/groups"
            response = requests.post(group_url, headers=headers, json=payload)

            if response.status_code == 201:
                console.print(f"[cyan]✅ Created group: {group_name}[/cyan]")
            else:
                console.print(f"[red]❌ Failed to create group {group_name}: {response.text}[/red]")

# ---------------- Menu ---------------- #
def policy_object_menu(base_url, headers, network_id, org_id):
    while True:
        console.print("\n[bold yellow]📘 Policy Objects Configuration[/bold yellow]")
        console.print("1) 📄 View Policy Object Groups")
        console.print("2) ❌ Delete Policy Object Group")
        console.print("3) 👁️  View All Policy Objects")
        console.print("4) 🚀 Create Policy Objects from IPs (Bulk via YAML)")
        console.print("5) 🧹 Delete Policy Objects")
        console.print("6) 🔙 Back to Previous Menu")

        choice = Prompt.ask("Select an option [1-6]", choices=["1", "2", "3", "4", "5", "6"], default="6")

        if choice == "1":
            view_policy_object_groups(base_url, headers, org_id)
        elif choice == "2":
            delete_policy_object_group(base_url, headers, org_id)
        elif choice == "3":
            view_policy_objects(base_url, headers, org_id)
        elif choice == "4":
            create_policy_objects_from_ip_yaml(base_url, headers, org_id)
        elif choice == "5":
            delete_policy_objects(base_url, headers, org_id)
        elif choice == "6":
            break
