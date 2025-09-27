import requests
import os
import json
from datetime import datetime, timedelta
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.table import Table
import openai
import yaml  # For offline YAML support
from pathlib import Path




console = Console()
OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)


def generate_ai_prompt(logs, event_type):
    base_prompt = f"These are filtered Meraki MX event logs of type '{event_type}':\n{json.dumps(logs[:10], indent=2)}\n\n"

    suggestions = {
        "cf_block": "Analyze why content filtering blocks occurred, check for false positives, and suggest whitelist or policy updates.",
        "dhcp_lease": "Analyze DHCP lease logs for IP conflicts, exhaustion, or abnormal patterns.",
        "dhcp_problem": "Troubleshoot the DHCP problems shown. Identify causes and provide steps to fix them.",
        "martian_vlan": "Explain 'martian VLAN' logs and suggest what might be misconfigured (e.g., VLAN routing).",
        "non_meraki_vpn": "Review non-Meraki VPN events for connection issues or handshake failures.",
        "dhcp_release": "Determine whether DHCP releases are normal or potentially problematic (e.g., flapping clients).",
    }

    analysis_task = suggestions.get(event_type, "Please analyze and summarize any problems, patterns, or misconfigurations.")

    return base_prompt + analysis_task





# ------------------------ Offline Knowledge Config ------------------------ #
OFFLINE_KNOWLEDGE_PATH = Path(__file__).resolve().parent / "data" / "meraki_offline_knowledge.yaml"

def ensure_offline_knowledge_exists():
    if not OFFLINE_KNOWLEDGE_PATH.exists():
        default_knowledge = {
            'cf_block': {'recommendation': 'Review content filter settings and consider whitelisting trusted URLs.'},
            'dhcp_lease': {'recommendation': 'Check for short lease times, IP pool exhaustion, or duplicate IPs.'},
            'dhcp_problem': {'recommendation': 'Investigate VLAN misconfigurations or DHCP scope depletion.'},
            'martian_vlan': {'recommendation': 'Check VLAN routing, trunk/access port settings, and misconfigured interfaces.'},
            'non_meraki_vpn': {'recommendation': 'Ensure correct IPsec settings and that remote peer is reachable.'},
            'dhcp_release': {'recommendation': 'Frequent releases may indicate DHCP flapping; inspect client or switchport stability.'}
        }
        OFFLINE_KNOWLEDGE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(OFFLINE_KNOWLEDGE_PATH, 'w') as f:
            yaml.dump(default_knowledge, f)
        console.print(f"[yellow⚠️ Created default offline knowledge base at {OFFLINE_KNOWLEDGE_PATH}[/yellow]")

def load_offline_knowledge():
    ensure_offline_knowledge_exists()
    with open(OFFLINE_KNOWLEDGE_PATH, 'r') as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Offline knowledge must be a dictionary. Found: {type(data)}")
    return data


def offline_analysis(logs, knowledge_base):
    if not isinstance(knowledge_base, dict):
        console.print("❌ Offline knowledge base format error: expected dict, got", type(knowledge_base))
        return None

    merged_text = json.dumps(logs).lower()
    for keyword, data in knowledge_base.items():
        if keyword in merged_text:
            return f"🧠 [bold cyan]Offline Match:[/bold cyan] {keyword}\n🔧 Recommendation: {data['recommendation']}"
    return None


def analyze_logs_with_ai(logs, event_type, auto_analyze=False):
    console.print("\n🧠 [bold blue]Troubleshooting Assistant[/bold blue]")

    if not auto_analyze and not Confirm.ask("💡 Run log analysis (offline + AI fallback)?"):
        return

    # Offline analysis first
    kb = load_offline_knowledge()
    offline_result = offline_analysis(logs, kb)

    if offline_result:
        console.print(offline_result)
        return

    console.print("⚠️ No offline match found in knowledge base.")

    # Confirm fallback to AI
    if not Confirm.ask("🧠 Would you like to proceed with OpenAI-based analysis?"):
        console.print("❌ Skipping AI analysis as per user choice.")
        return

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        api_key = Prompt.ask("🔐 Enter your OpenAI API Key (starts with 'sk-')").strip()

    content = generate_ai_prompt(logs, event_type)

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        console.print("⚙️ Using modern OpenAI SDK (>=1.0.0)...")

        try:
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a network troubleshooting assistant."},
                    {"role": "user", "content": content}
                ],
                max_tokens=800,
                temperature=0.5
            )
        except Exception:
            console.print("⚠️ GPT-4 not accessible. Falling back to gpt-3.5-turbo...")
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a network troubleshooting assistant."},
                    {"role": "user", "content": content}
                ],
                max_tokens=800,
                temperature=0.5
            )

        result = response.choices[0].message.content
        console.print("\n📊 [bold green]AI Analysis Result:[/bold green]")
        console.print(result)

    except Exception as e:
        console.print(f"❌ AI analysis failed: {e}")
        console.print("💡 Tip: Ensure `openai>=1.0.0` is installed. Try: [italic]pip install --upgrade openai[/]")


# ------------------------ Fetch Event Logs ------------------------ #
def fetch_events(base_url, headers, network_id, days, product_type):
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=int(days))
    url = f"{base_url}/networks/{network_id}/events"

    params = {
        "perPage": 1000,
        "t0": start_time.isoformat() + "Z",
        "t1": end_time.isoformat() + "Z"
    }

    if product_type != "all":
        params["productType"] = product_type

    console.print(f"\n📡 Fetching logs from: [bold green]{params['t0']}[/] to [bold green]{params['t1']}[/]...")
    console.print(f"📦 Product Type Filter: [bold yellow]{product_type}[/]")

    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        events = response.json().get("events", [])
        return events, params['t0'], params['t1']
    except requests.RequestException as e:
        console.print(f"❌ Failed to fetch events: {e}")
        return [], None, None

# ------------------------ Get Unique Event Types ------------------------ #
def get_unique_event_types(events):
    return sorted(set(event.get("type", "unknown") for event in events))

# ------------------------ Filter by Type and Keyword ------------------------ #
def filter_events(events, selected_type, keyword_input=None):
    keywords = [k.strip().lower() for k in keyword_input.split(",") if k.strip()] if keyword_input else []
    filtered = []
    for event in events:
        if event.get("type") == selected_type:
            combined = json.dumps(event).lower()
            if not keywords or any(k in combined for k in keywords):
                filtered.append(event)
    return filtered

# ------------------------ Display Logs with Pagination ------------------------ #
def display_logs_table(logs, page_size=10):
    if not logs:
        console.print("⚠️  No logs found to display.")
        return

    event_type = logs[0].get("type", "generic")
    total = len(logs)
    pages = (total + page_size - 1) // page_size

    for page in range(pages):
        chunk = logs[page * page_size:(page + 1) * page_size]
        render_table(chunk, event_type)
        if page < pages - 1 and not Confirm.ask(f"\n➡️ Show next {page_size} entries?"):
            break

def render_table(logs, event_type):
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Time", width=18)

    if event_type == "cf_block":
        table.add_column("Type", width=12)
        table.add_column("Description", width=30)
        table.add_column("Client", width=20)
        table.add_column("URL", overflow="fold")
        for e in logs:
            table.add_row(
                e.get("occurredAt", "")[:19],
                e.get("type", ""),
                e.get("description", ""),
                e.get("clientDescription") or e.get("clientId") or "N/A",
                e.get("eventData", {}).get("url", "N/A")
            )

    elif event_type == "dhcp_lease":
        table.add_column("Client", width=20)
        table.add_column("IP", width=15)
        table.add_column("VLAN", width=8)
        table.add_column("Duration", width=10)
        table.add_column("DNS", overflow="fold")
        for e in logs:
            ed = e.get("eventData", {})
            table.add_row(
                e.get("occurredAt", "")[:19],
                e.get("clientDescription", "N/A"),
                ed.get("ip", "N/A"),
                ed.get("vlan", "N/A"),
                ed.get("duration", "N/A"),
                ed.get("dns", "N/A")
            )

    elif event_type == "dhcp_problem":
        table.add_column("Client", width=25)
        table.add_column("VLAN", width=8)
        table.add_column("Issue", overflow="fold")
        for e in logs:
            ed = e.get("eventData", {})
            table.add_row(
                e.get("occurredAt", "")[:19],
                e.get("clientDescription", "N/A"),
                ed.get("vlan", "N/A"),
                ed.get("extra", "N/A")
            )

    elif event_type == "martian_vlan":
        table.add_column("Client", width=25)
        table.add_column("VLAN", width=8)
        table.add_column("Note", overflow="fold")
        for e in logs:
            ed = e.get("eventData", {})
            table.add_row(
                e.get("occurredAt", "")[:19],
                e.get("clientDescription", "N/A"),
                ed.get("vlan", "N/A"),
                ed.get("extra", "N/A")
            )

    elif event_type == "non_meraki_vpn":
        table.add_column("Device", width=25)
        table.add_column("Message", overflow="fold")
        for e in logs:
            ed = e.get("eventData", {})
            table.add_row(
                e.get("occurredAt", "")[:19],
                e.get("deviceName", "N/A"),
                ed.get("msg", "N/A")
            )

    elif event_type == "dhcp_release":
        table.add_column("Client", width=25)
        table.add_column("VLAN", width=8)
        table.add_column("Device", overflow="fold")
        for e in logs:
            ed = e.get("eventData", {})
            table.add_row(
                e.get("occurredAt", "")[:19],
                e.get("clientDescription", "N/A"),
                ed.get("vlan", "N/A"),
                e.get("deviceName", "N/A")
            )

    else:
        # Generic handler
        sample = logs[0]
        extra_cols = [k for k in sample.keys() if k not in ["occurredAt", "eventData"]]
        for col in extra_cols:
            table.add_column(col, overflow="fold")
        table.add_column("eventData", overflow="fold")

        for e in logs:
            row = [e.get("occurredAt", "")[:19]]
            for col in extra_cols:
                row.append(str(e.get(col, "N/A")))
            row.append(json.dumps(e.get("eventData", {})))
            table.add_row(*row)

    console.print(f"\n🔍 [bold]Filtered Meraki Events — {event_type}[/bold]")
    console.print(table)

# ------------------------ Export Logs ------------------------ #
def export_logs(logs):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{OUTPUT_DIR}/filtered_events_{timestamp}.json"
    with open(filename, "w") as f:
        json.dump(logs, f, indent=2)
    console.print(f"\n💾 Logs exported to: [green]{filename}[/]")

# ------------------------ Main Menu ------------------------ #
def troubleshooting_menu(base_url, headers, network_id):
    console.rule("[bold blue]📡 Meraki MX Event Log Viewer[/bold blue]")

    days = Prompt.ask("📆 Enter number of days to go back", default="1")

    product_type = Prompt.ask(
        "🧩 Enter product type [appliance/switch/wireless]",
        choices=["appliance", "switch", "wireless"],
        default="appliance"
    )

    events, t0, t1 = fetch_events(base_url, headers, network_id, days, product_type)

    if not events:
        console.print("❌ No events found!")
        return

    console.print(f"\n📆 Available Time Range: [green]{t0}[/] to [green]{t1}[/]")

    event_types = get_unique_event_types(events)
    if not event_types:
        console.print("❌ No event types found.")
        return

    console.print("\n📂 Available Event Types:")
    for idx, e_type in enumerate(event_types, 1):
        console.print(f"{idx}. {e_type}")

    selected_index = Prompt.ask("\n🔢 Select an event type by number", choices=[str(i) for i in range(1, len(event_types)+1)])
    selected_type = event_types[int(selected_index)-1]

    keyword = Prompt.ask("🔍 Enter keyword(s) to filter logs (comma-separated, leave blank to skip)", default="").strip()

    filtered_logs = filter_events(events, selected_type, keyword)

    display_logs_table(filtered_logs)

    if filtered_logs:
        auto_ai = False
        analyze_logs_with_ai(filtered_logs, selected_type, auto_analyze=auto_ai)

    if Confirm.ask("\n📤 Do you want to export these logs?"):
        export_logs(filtered_logs)

# ------------------------ Example Usage ------------------------ #
# troubleshooting_menu(base_url, headers, network_id)
