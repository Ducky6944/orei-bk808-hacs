# 🔌 Orei BK808 HDMI Matrix Controller for Home Assistant

[![HACS Badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

A fully-featured Home Assistant integration for the Orei BK808 8x8 HDMI Matrix Switch, with complete CEC control, routing, presets, and a guided GUI setup — no YAML or manual file edits required.

## ✨ Features

- 🚀 **4-step GUI setup wizard** with automatic connection testing
- 🎮 **Full CEC control** for all inputs and outputs
- 🔄 **8×8 routing matrix** — route any input to any output
- ⚡ **Preset save/recall** for instant scene switching
- 🏷️ **Custom input/output names** set during setup
- 🔐 **Encrypted credential storage** — nothing hardcoded
- 🧪 **Automated test suite** with CI

## 🎯 Supported Devices

- ✅ Orei BK808 8K 8x8 HDMI Matrix Switch (tested)
- 🔶 Orei BK404 4x4 (partial, untested)

## 📋 Prerequisites

- Home Assistant 2024.1 or later
- HACS installed (recommended)
- Your Orei BK808 connected to your network via Ethernet
- Your matrix login credentials (change the defaults first!)

## 🚀 Installation

### Step 1: Install via HACS

1. Open **HACS** in Home Assistant
2. Go to **⋮ (three-dot menu)** → **Custom repositories**
3. Add this repository with category **Integration**
4. Search for **"Orei BK808"** → click **Download**
5. **Restart Home Assistant**

### Step 2: Connect Your Matrix (GUI Only)

1. Go to **Settings → Devices & Services → + Add Integration**
2. Search for **"Orei BK808"**
3. The setup wizard will walk you through:

| Step | What You Do |
|------|-------------|
| 1. Connection | Enter your matrix's IP address, username, and password |
| 2. Verify | The integration tests the connection automatically |
| 3. Naming | Optionally rename inputs/outputs (comma-separated) |
| 4. Done | Entities appear automatically — start using! |

**That's it.** No configuration files, no YAML, no edits. If the connection test fails, you'll get a clear error and can fix your credentials right in the wizard.

## 🎨 Dashboard

After setup, add entities to any dashboard via the UI editor:
**Edit Dashboard → + Add Card → Entities / Button / Tile**

Pick from routing selectors, CEC buttons, power switches, and status sensors — all available through the standard entity picker. A ready-made example dashboard YAML is included in this repo (`lovelace_dashboard.yaml`) for those who want a head start, but it's entirely optional.

## 🎮 CEC Commands Available

Per input device: play, pause, stop, fast forward, rewind, navigation (up/down/left/right), select, back, standby, power on, menu, and more.

Per output/display: power on, standby, volume up/down, mute.

## 🔧 Services

| Service | Description |
|---------|-------------|
| `orei_bk808.route` | Route an input to an output |
| `orei_bk808.save_preset` | Save current routing to a slot (1-8) |
| `orei_bk808.recall_preset` | Recall a saved preset |
| `orei_bk808.cec_command` | Send a CEC command to a port |
| `orei_bk808.get_status` | Refresh matrix status |

All services are callable from the UI (Developer Tools → Actions) as well as automations and scripts.

## 🔐 Security

- Credentials are entered in the setup wizard and stored encrypted in Home Assistant's config entry storage — never in files you edit
- All traffic uses HTTPS to your local device
- We strongly recommend changing the matrix's default password before installation, and placing AV equipment on an isolated VLAN if possible

## 🐛 Troubleshooting

### Connection failed during setup?

Verify your credentials work in a browser by visiting your matrix's web interface directly. Common causes:

- Wrong IP address
- Firewall blocking HTTPS (port 443)
- Password changed but old credentials entered
- Matrix powered off

### CEC commands not working?

- Enable CEC on your devices (Samsung: Anynet+, LG: SimpLink, Sony: BRAVIA Sync)
- Use certified HDMI cables — cheap cables often fail CEC
- Some devices ignore certain CEC commands

## 🧪 Development

```bash
git clone <your-repo-url>
cd orei_bk808
pip install pytest pytest-asyncio pytest-homeassistant-custom-component
pytest tests/ -v 
```
