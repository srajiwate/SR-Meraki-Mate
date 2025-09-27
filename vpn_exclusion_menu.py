# vpn_exclusion_menu.py
from rich.console import Console
from rich.prompt import Prompt
import subprocess
import os
import sys

console = Console()

def vpn_exclusion_menu(base_url, headers, org_id):
    while True:
        console.print("\n[bold magenta]🌐 VPN Exclusion Menu[/bold magenta]")
        console.print("1. ➕ Push VPN Exclusions")
        console.print("2. ➖ Remove VPN Exclusions")
        console.print("3. ⬅️ Back to Main Menu")

        choice = Prompt.ask("Choose an option", choices=["1", "2", "3"])

        if choice == "1":
            run_vpn_push()
        elif choice == "2":
            run_vpn_removal()
        elif choice == "3":
            break

def run_vpn_push():
    console.print("\n📤 Running VPN Exclusion Push Script...", style="cyan")
    result = os.system("python3 vpn_exclusion_push.py")
    if result != 0:
        console.print("❌ Push script failed!", style="red")
    else:
        console.print("✅ Push completed successfully.", style="green")

def run_vpn_removal():
    console.print("\n🧹 Running VPN Exclusion Removal Script...", style="cyan")
    result = os.system("python3 vpn_exclusion_remove.py")
    if result != 0:
        console.print("❌ Removal script failed!", style="red")
    else:
        console.print("✅ Removal completed successfully.", style="green")
