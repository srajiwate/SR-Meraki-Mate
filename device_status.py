from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.progress import track
from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta
from dateutil.parser import isoparse
import requests
import pandas as pd
import os
import logging

console = Console()
BASE_URL = "https://api.meraki.com/api/v1"
OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Setup logging
logging.basicConfig(
    filename=os.path.join(OUTPUT_DIR, "device_status.log"),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

def get_device_statuses(org_id, headers):
    url = f"{BASE_URL}/organizations/{org_id}/devices/statuses"
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logging.error(f"Failed to fetch device statuses: {e}")
        raise

def calculate_last_reported_human(last_reported_str, status):
    if not last_reported_str:
        return "N/A", None

    try:
        last_reported = isoparse(last_reported_str)
    except Exception:
        return "Invalid timestamp", None

    now = datetime.now(timezone.utc)
    delta = now - last_reported
    hours = round(delta.total_seconds() / 3600, 2)

    if status == "online":
        rd = relativedelta(now, last_reported)
        parts = []
        if rd.years: parts.append(f"{rd.years} year{'s' if rd.years > 1 else ''}")
        if rd.months: parts.append(f"{rd.months} month{'s' if rd.months > 1 else ''}")
        if rd.days: parts.append(f"{rd.days} day{'s' if rd.days > 1 else ''}")
        if rd.hours: parts.append(f"{rd.hours} hour{'s' if rd.hours > 1 else ''}")
        if rd.minutes and not parts:
            parts.append(f"{rd.minutes} minute{'s' if rd.minutes > 1 else ''}")
        return f"Reported {', '.join(parts)} ago", hours
    else:
        return f"Offline for {hours} hours", hours

def export_to_csv_and_excel(devices):
    df = pd.DataFrame.from_records(devices)
    csv_path = os.path.join(OUTPUT_DIR, "device_uptime_report.csv")
    excel_path = os.path.join(OUTPUT_DIR, "device_uptime_report.xlsx")

    try:
        df.to_csv(csv_path, index=False)
        df.to_excel(excel_path, index=False)
        console.print(f"\n📁 [green]Exported to:[/green] {csv_path}")
        console.print(f"📁 [green]Exported to:[/green] {excel_path}")
    except Exception as e:
        logging.error(f"Failed to export reports: {e}")
        console.print(f"[red]❌ Failed to export reports: {e}[/red]")

def show_device_uptime(org_id, headers):
    console.clear()
    console.rule("[bold cyan]📡 Meraki Device Last Seen / Status Report")

    try:
        devices = get_device_statuses(org_id, headers)
    except Exception as e:
        console.print(f"[red]Failed to fetch device statuses: {e}[/red]")
        return

    threshold_hours = float(Prompt.ask("⚠️ Highlight devices offline more than how many hours?", default="12"))

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Name", style="cyan")
    table.add_column("Model")
    table.add_column("Serial", style="yellow")
    table.add_column("Status")
    table.add_column("Last Reported", style="white")
    table.add_column("Last Reported / Offline Duration", style="green")

    enriched_devices = []

    for device in track(devices, description="Processing devices..."):
        name = device.get("name", "N/A")
        model = device.get("model", "N/A")
        serial = device.get("serial", "N/A")
        last_reported = device.get("lastReportedAt", "N/A")
        status = device.get("status", "offline")

        reported_str, hours = calculate_last_reported_human(last_reported, status)

        enriched_devices.append({
            "name": name,
            "model": model,
            "serial": serial,
            "status": status,
            "lastReportedAt": last_reported,
            "uptime": reported_str
        })

        # Style status cell if offline beyond threshold
        if status == "offline" and hours and hours > threshold_hours:
            status_display = f"[bold red]{status}[/bold red]"
        else:
            status_display = f"[green]{status}[/green]" if status == "online" else status

        table.add_row(name, model, serial, status_display, last_reported or "N/A", reported_str)

    console.print("\n[bold cyan]✅ Device Status Summary:[/bold cyan]\n")
    console.print(table)

    if Confirm.ask("📤 Export this report to Excel and CSV?", default=True):
        export_to_csv_and_excel(enriched_devices)

def device_status_menu(org_id, network_id, headers):
    while True:
        console.rule("[bold blue]📡 Device Status Menu")
        console.print("[1] Show Device Last Reported Info")
        console.print("[2] Back to Main Menu")

        choice = Prompt.ask("Choose an option", choices=["1", "2"], default="1")

        if choice == "1":
            show_device_uptime(org_id, headers)
        elif choice == "2":
            break
