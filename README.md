<p align="center">
  <img width="730" height="117" alt="image" src="https://github.com/user-attachments/assets/5ef3a31a-6609-451f-b22e-f4f1116066c0" />
</p>

<p align="center">
    <a href="https://github.com/srajiwate">
      <img src="https://img.shields.io/badge/-AUTHOR-black?logo=github&style=for-the-badge">
    </a>
    &nbsp;
    <a href="https://community.meraki.com/">
      <img src="https://img.shields.io/badge/-CISCO%20MERAKI-black?logo=cisco&style=for-the-badge">
    </a>
    &nbsp;
    <a href="https://learn.microsoft.com/azure/key-vault/general/overview">
      <img src="https://img.shields.io/badge/-AZURE%20KEYVAULT-black?logo=microsoftazure&style=for-the-badge">
    </a>
</p>

<p align="center">
  <a style="margin-right: 10px;" href="https://github.com/srajiwate/SR-Meraki-Mate#installation">
    <img src="https://dabuttonfactory.com/button.png?t=INSTALL&f=Open+Sans&ts=15&tc=000&hp=25&vp=10&c=5&bgt=unicolored&bgc=00e2ff">
  </a>
  <a style="margin-right: 10px;" href="https://github.com/srajiwate/SR-Meraki-Mate#usage">
    <img src="https://dabuttonfactory.com/button.png?t=USAGE&f=Open+Sans&ts=15&tc=000&hp=25&vp=10&c=5&bgt=unicolored&bgc=00e2ff">
  </a>
  <a href="https://github.com/srajiwate/SR-Meraki-Mate#demo">
    <img src="https://dabuttonfactory.com/button.png?t=DEMO&f=Open+Sans&ts=15&tc=000&hp=25&vp=10&c=5&bgt=unicolored&bgc=00e2ff">
  </a>
</p>

## 💡 Why SR-MerakiMate? (Concept Behind It)

**Idea arise insense of CLI lover.**

Cisco Meraki provides a clean web dashboard and some basic templates, but in real-world enterprise operations these have limitations:

- **⏱️ Speed vs GUI**  
  The Dashboard is point-and-click. Great for one-off changes, but slow for bulk configuration across multiple networks and devices.

- **📋 Consistency vs Templates**  
  Meraki templates enforce the same config everywhere. But in practice, every branch/site often has *slight variations* (VLAN IDs, SSIDs, DHCP ranges). Templates can become rigid or force workarounds.

- **⚡ Bulk Automation**  
  SR-MerakiMate uses **YAML/Excel inputs** to push site-specific configs at scale — e.g. hundreds of VLANs, DHCP scopes, firewall rules — in minutes, without manual clicks.

- **🔐 Security Built-In**  
  - Supports **Azure Key Vault** integration for API key management.  
  - API key masking in CLI (safe during screen-sharing).  

- **🧠 Smarter Troubleshooting**  
  - Offline YAML knowledge base for common issues.  
  - Optional OpenAI integration for advanced analysis of Meraki event logs.  

- **📊 Reporting & Exports**  
  Export device uptime, advanced inventory, VPN configs, and more — to CSV/XLSX. Something the GUI doesn’t provide in one click.

---

👉 In short: **SR-MerakiMate bridges the gap between GUI simplicity and DevOps automation**, giving network engineers a faster, repeatable, and more secure way to manage Meraki environments at scale.


---

## ⚠️ Disclaimer  

**This tool is a Proof of Concept and is for Educational Purposes Only.**  
SR-MerakiMate demonstrates how Meraki’s Dashboard API can be automated for faster deployments and troubleshooting.  

- It is **not officially affiliated with Cisco Meraki**.  
- Use only in environments where you are authorized.  
- Always validate configs before pushing to production.  

By using SR-MerakiMate, you agree that the author and contributors are **not responsible for any misuse, misconfiguration, or damage** caused by this tool.

<img width="1536" height="1024" alt="image" src="https://github.com/user-attachments/assets/55f4d6d6-1954-4c94-a046-e36caf929328" />


## Features

- 📦 Claim Meraki devices into networks  
- 🔀 Configure switch ports (bulk access/trunk VLANs)  
- 📡 Wireless config: rename APs, SSIDs  
- 🔥 Appliance config: VLAN, DHCP, reserved ranges, fixed IPs (YAML bulk)  
- 🧱 Policy Objects: create/delete, group objects (YAML/Excel bulk)  
- 🌐 VPN Exclusions (Excel-driven push/remove)  
- 🔐 Site-to-Site VPN viewer (secrets masked by default)  
- 🧪 Troubleshooting Assistant  
  - Offline YAML heuristics  
  - Optional OpenAI integration  
- 📶 Device uptime/status reporting (CSV/XLSX export)  
- 🗂️ Advanced inventory export (firmware, VLANs, L3 interfaces) 

## Templates

## 📂 Available Templates in `/data`

* dhcp.yaml                     # Bulk DHCP settings for VLANs
* fixed_ips.yaml                # Bulk reserved IPs (MAC ↔ IP mapping)
* inbound_firewall_rules.yaml   # Inbound firewall rules
* l3_firewall_rules.yaml        # L3 firewall rules
* meraki_offline_knowledge.yaml # (Reference) Offline knowledge base for Meraki
* policy_objects.yaml           # Policy object definitions (IPs for object creation)
* reserved_ranges.yaml          # Reserved IP ranges inside VLANs
* vlans.yaml                    # VLAN definitions (IDs, names, subnets, appliance IPs)
* vpn_exclusion_input.xlsx      # Excel input for VPN exclusion (push list)
* vpn_exclusion_removal_input.xlsx # Excel input for VPN exclusion (removal list)



## Tested On :

* Ubuntu
Distributor ID: Ubuntu
Description:    Ubuntu 24.04.2 LTS
Release:        24.04


## Installation

### Ubuntu

```bash
git clone https://github.com/srajiwate/SR-Meraki-Mate.git
cd SR-Meraki-Mate

````
### 🛠️ Prerequisites
📦 Installation Requirements
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

```
**Azure Login**

az login 
<img width="1322" height="130" alt="image" src="https://github.com/user-attachments/assets/34362c63-5ddb-43e4-9aad-164eb38eb9aa" />

Enter the code which was displayed in terminal during command az login
<img width="1432" height="802" alt="image" src="https://github.com/user-attachments/assets/3acfe1f5-a9ec-4fb9-9ac8-37c89e6f1346" />

Post login you will see tenant information
<img width="1905" height="471" alt="image" src="https://github.com/user-attachments/assets/692d14ff-113d-4077-a4fe-de189d927881" />

`
## Usage

```bash
python3 main.py -h

usage: main.py [-h] [--update-banner] [--no-vault]

options:
  -h, --help       show this help message and exit
  --update-banner  Regenerate hashes (requires master password)
  --no-vault       Skip Azure Key Vault and prompt API key manually


##################
# Usage Examples #
##################

# Step 1 : In terminal
$ python3 main.py

# Step 2 : Proceed by type y

```

## Demo

1) Available Organization and networks

<img width="951" height="832" alt="image" src="https://github.com/user-attachments/assets/3d6da14b-8bab-40df-a757-d2480f768264" />

2) Main Menu After selecting network

<img width="548" height="305" alt="image" src="https://github.com/user-attachments/assets/661bda93-27e8-4681-88c6-d4d83605c16e" />

🚀 If you have new ideas or feature requests, feel free to open an Issue or Pull Request — **contributions are always welcome!**




