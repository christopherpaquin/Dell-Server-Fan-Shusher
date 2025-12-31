<div align="center">

# 🖥️ Dell Server Fan Shusher

**Intelligent fan speed control for Dell R730 servers with multi-vendor GPU temperature monitoring**

<img src="https://static.wikia.nocookie.net/universalstudios/images/1/1e/Captain_smek132.png/revision/latest?cb=20201014154632" alt="Dell Server Fan Shusher" width="25%">

[![Python](https://img.shields.io/badge/Python-3.6+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Linux-lightgrey.svg)](https://www.linux.org/)
[![GPU Support](https://img.shields.io/badge/GPU-NVIDIA%20%7C%20AMD%20%7C%20Intel-orange.svg)]()

**Repository:** [https://github.com/christopherpaquin/Dell-Server-Fan-Shusher](https://github.com/christopherpaquin/Dell-Server-Fan-Shusher)

[Features](#-features) • [Installation](#-installation) • [Usage](#-usage) • [Configuration](#-configuration) • [Troubleshooting](#-troubleshooting)

</div>

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Features](#-features)
- [Prerequisites](#-prerequisites)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [Usage](#-usage)
- [How It Works](#-how-it-works)
- [GPU Support](#-gpu-support)
- [Logging](#-logging)
- [Troubleshooting](#-troubleshooting)
- [Uninstallation](#-uninstallation)
- [License](#-license)

---

## 🎯 Overview

A Python script that intelligently controls fan speeds on a Dell R730 server based on GPU and system temperatures. The script monitors GPU temperatures from **NVIDIA**, **AMD**, and **Intel** GPUs, and system temperatures via `ipmitool`, then adjusts fan speeds to keep noise low while maintaining safe operating temperatures.

**Designed to run periodically via cron or systemd service.**

### 🏷️ Tags

`dell-r730` `fan-control` `gpu-monitoring` `temperature-control` `ipmi` `idrac` `nvidia` `amd` `intel` `systemd` `cron` `python` `server-management` `thermal-management`

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🔥 **Multi-Vendor GPU Support** | Supports NVIDIA (nvidia-smi), AMD (rocm-smi/sensors), and Intel (intel_gpu_top/sensors) GPUs |
| 🌡️ **System Temperature Monitoring** | Monitors system temperatures via `ipmitool` |
| ⚙️ **Adaptive Fan Control** | Automatically adjusts fan speeds based on temperature thresholds |
| 🧠 **Smart Mode Switching** | Switches to automatic iDRAC control when temperatures are high |
| 📝 **Comprehensive Logging** | All temperature checks and fan adjustments are logged to a file |
| 🎛️ **Configurable Thresholds** | Customize temperature and fan speed settings via environment variables |
| 🔇 **Low Noise Operation** | Keeps fans at minimum speed when temperatures are low |
| 🔍 **Manual Check Modes** | Read-only modes to check temperatures and fan speeds without adjustments |
| 📊 **History Viewing** | View temperature and fan speed history from logs |

---

## 📦 Prerequisites

### Required

- ✅ **Python 3.6+** - [Download Python](https://www.python.org/downloads/)
- ✅ **ipmitool** - IPMI command-line utility
- ✅ **Network access** to the iDRAC interface
- ✅ **iDRAC credentials** (IP, username, password)
- ✅ **Root or sudo access** (for systemd service setup)

### GPU Monitoring Tools (at least one required)

Choose based on your GPU vendor:

| GPU Vendor | Tool | Installation |
|------------|------|---------------|
| 🟢 **NVIDIA** | `nvidia-smi` | Included with NVIDIA drivers |
| 🔴 **AMD** | `rocm-smi` | Part of ROCm software stack |
| | `sensors` | `lm-sensors` package |
| 🔵 **Intel** | `intel_gpu_top` | `intel-gpu-tools` package |
| | `sensors` | `lm-sensors` package |

> 💡 **Note**: The script will automatically detect and use the first available GPU monitoring tool.

---

## 🚀 Installation

### ⚡ Automated Installation (Recommended)

Run the installation script which handles all setup automatically:

```bash
sudo ./install.sh
```

The install script will:
- ✅ Check for required dependencies (python3, ipmitool)
- ✅ Check for GPU monitoring tools
- ✅ Install Python dependencies
- ✅ Create `.env` file from template
- ✅ Set proper permissions
- ✅ Create log directory
- ✅ Set up systemd service or cron job (your choice)
- ✅ Perform a test run

### 🔧 Manual Installation

1. **Clone or download this repository**
   ```bash
   git clone https://github.com/christopherpaquin/Dell-Server-Fan-Shusher.git
   cd Dell-Server-Fan-Shusher
   ```

2. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   # or
   pip3 install -r requirements.txt
   ```

3. **Copy the example environment file**
   ```bash
   cp env.example .env
   ```

4. **Edit `.env` with your iDRAC credentials and settings**
   ```bash
   nano .env
   ```

5. **Make the script executable**
   ```bash
   chmod +x fan_control.py
   ```

---

## ⚙️ Configuration

Edit the `.env` file to configure all settings:

### Configuration Options

| Setting | Description | Default |
|---------|-------------|----------|
| `IDRAC_IP` | iDRAC IP address | `10.1.10.20` |
| `IDRAC_USER` | iDRAC username | `root` |
| `IDRAC_PASS` | iDRAC password | `calvin` |
| `GPU_TEMP_LOW` | Low GPU temperature threshold (°C) | `50` |
| `GPU_TEMP_MED` | Medium GPU temperature threshold (°C) | `60` |
| `GPU_TEMP_HIGH` | High GPU temperature threshold (°C) | `70` |
| `GPU_TEMP_CRITICAL` | Critical GPU temperature threshold (°C) | `80` |
| `SYSTEM_TEMP_LOW` | Low system temperature threshold (°C) | `40` |
| `SYSTEM_TEMP_MED` | Medium system temperature threshold (°C) | `50` |
| `SYSTEM_TEMP_HIGH` | High system temperature threshold (°C) | `60` |
| `SYSTEM_TEMP_CRITICAL` | Critical system temperature threshold (°C) | `70` |
| `FAN_SPEED_LOW` | Low fan speed percentage (0-100) | `20` |
| `FAN_SPEED_MED` | Medium fan speed percentage (0-100) | `40` |
| `FAN_SPEED_HIGH` | High fan speed percentage (0-100) | `60` |
| `FAN_SPEED_CRITICAL` | Critical fan speed percentage (0-100) | `80` |
| `AUTO_MODE_THRESHOLD` | Temperature threshold for auto mode (°C) | `75` |
| `LOG_FILE` | Log file path | `/var/log/dell-r730-fan-control.log` |

### Example Configuration

```env
# Dell R730 iDRAC Credentials
IDRAC_IP=10.1.10.20
IDRAC_USER=root
IDRAC_PASS=your_secure_password

# GPU Temperature Thresholds (Celsius)
GPU_TEMP_LOW=50
GPU_TEMP_MED=60
GPU_TEMP_HIGH=70
GPU_TEMP_CRITICAL=80

# System Temperature Thresholds (Celsius)
SYSTEM_TEMP_LOW=40
SYSTEM_TEMP_MED=50
SYSTEM_TEMP_HIGH=60
SYSTEM_TEMP_CRITICAL=70

# Fan Speed Percentages (0-100)
FAN_SPEED_LOW=20
FAN_SPEED_MED=40
FAN_SPEED_HIGH=60
FAN_SPEED_CRITICAL=80

# Switch to automatic mode when temps exceed this threshold
AUTO_MODE_THRESHOLD=75

# Log file path
LOG_FILE=/var/log/dell-r730-fan-control.log
```

---

## 💻 Usage

### 🔄 Normal Operation

Run the script to check temperatures and adjust fan speeds:

```bash
python3 fan_control.py
```

**What it does:**
1. ✅ Checks GPU and system temperatures
2. ✅ Enables manual fan mode if temps are low, sets appropriate fan speed
3. ✅ Enables automatic fan mode if temps are high (lets iDRAC handle it)
4. ✅ Logs all actions to the log file

### 🔍 Manual Check Commands

#### Check Temperatures Only (Read-Only)

```bash
python3 fan_control.py --temps
# or
python3 fan_control.py --check-temps
```

**Output:** Current GPU and system temperatures with thresholds

#### Check Fan Speeds Only (Read-Only)

```bash
python3 fan_control.py --fans
# or
python3 fan_control.py --check-fans
```

**Output:** Current fan speeds (RPM) and configured settings

#### View Temperature History

```bash
# Show last 50 entries (default)
python3 fan_control.py --history

# Show last N entries
python3 fan_control.py --history 100
```

#### View Detailed History

```bash
# Show detailed history for last 24 hours (default)
python3 fan_control.py --history-detailed

# Show detailed history for last N hours
python3 fan_control.py --history-detailed 12
```

#### Help

```bash
python3 fan_control.py --help
```

### 🔧 Running as a Systemd Service (Recommended)

1. **Edit the service file** (update paths if needed):
   ```bash
   nano dell-r730-fan-control.service
   ```

2. **Edit the timer file** (adjust interval):
   ```bash
   nano dell-r730-fan-control.timer
   ```
   Default: runs every 30 seconds

3. **Install service and timer**:
   ```bash
   sudo cp dell-r730-fan-control.service /etc/systemd/system/
   sudo cp dell-r730-fan-control.timer /etc/systemd/system/
   ```

4. **Enable and start**:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable dell-r730-fan-control.timer
   sudo systemctl start dell-r730-fan-control.timer
   ```

5. **Check status**:
   ```bash
   sudo systemctl status dell-r730-fan-control.timer
   sudo systemctl status dell-r730-fan-control.service
   ```

6. **View logs**:
   ```bash
   sudo journalctl -u dell-r730-fan-control.service -f
   ```

### ⏰ Running via Cron

1. **Edit crontab**:
   ```bash
   crontab -e
   ```

2. **Add entry** (see `cron.example` for more options):
   ```bash
   # Run every 5 minutes
   */5 * * * * /usr/bin/python3 /path/to/fan_control.py
   ```

   **For 30-second intervals** (requires two entries):
   ```bash
   * * * * * /usr/bin/python3 /path/to/fan_control.py
   * * * * * sleep 30; /usr/bin/python3 /path/to/fan_control.py
   ```

---

## 🔄 How It Works

### 1. Temperature Monitoring

- 🔍 Automatically detects and queries GPU monitoring tools
- 🌡️ Supports NVIDIA, AMD, and Intel GPUs
- 📊 Queries `ipmitool` for system temperatures
- 📝 Logs all readings to the log file

### 2. Mode Decision

The script checks temperatures from highest to lowest and uses the first threshold that is exceeded. The logic works as follows:

| Temperature Range | Fan Speed Used | Description |
|-------------------|----------------|-------------|
| **≥ Critical Threshold** | `FAN_SPEED_CRITICAL` | Maximum cooling required |
| **≥ High Threshold** | `FAN_SPEED_HIGH` | High cooling needed |
| **≥ Medium Threshold** | `FAN_SPEED_MED` | Moderate cooling |
| **≥ Low Threshold** | `FAN_SPEED_LOW` | Low cooling (quiet operation) |
| **< Low Threshold** | `FAN_SPEED_LOW` | Low cooling (quiet operation) |
| **≥ Auto Mode Threshold** | Automatic mode | iDRAC takes over control |

**Example with default thresholds:**
- `SYSTEM_TEMP_LOW=40`, `SYSTEM_TEMP_MED=50`, `SYSTEM_TEMP_HIGH=60`, `SYSTEM_TEMP_CRITICAL=70`

| Temperature | Fan Speed |
|-------------|-----------|
| **≥ 70°C** | Critical (80%) |
| **≥ 60°C** | High (60%) |
| **≥ 50°C** | Medium (40%) |
| **≥ 40°C** | Low (20%) |
| **< 40°C** | Low (20%) |

**Important Notes:**
- The script uses the **highest** temperature detected (either GPU or system) to determine fan speed
- When temperature is between LOW and MED thresholds, it uses **LOW** fan speed for quiet operation
- If temperature exceeds the `AUTO_MODE_THRESHOLD`, the script switches to automatic mode and lets iDRAC handle fan control
- The script checks thresholds from highest to lowest, so the first threshold exceeded determines the fan speed

### 3. Fan Speed Adjustment

When in manual mode, sets fan speed based on the highest temperature detected (GPU or system).

### 4. Logging

All temperature checks, mode changes, and fan speed adjustments are logged with timestamps.

---

## 🎮 GPU Support

The script automatically detects and supports multiple GPU vendors:

| Vendor | Tool | Status |
|--------|------|--------|
| 🟢 **NVIDIA** | `nvidia-smi` | ✅ Fully Supported |
| 🔴 **AMD** | `rocm-smi` or `sensors` | ✅ Fully Supported |
| 🔵 **Intel** | `intel_gpu_top` or `sensors` | ✅ Fully Supported |

**Detection Order:**
1. NVIDIA (nvidia-smi)
2. AMD (rocm-smi)
3. Intel (intel_gpu_top)
4. Sensors (lm-sensors) - works for AMD and Intel

> 💡 **Note**: If no GPU monitoring tools are available, the script will fall back to system temperature monitoring only.

---

## 📝 Logging

All operations are logged to the file specified in `LOG_FILE` (default: `/var/log/dell-r730-fan-control.log`).

### Log Contents

- ✅ Timestamp of each check
- ✅ GPU and system temperatures
- ✅ Fan mode changes (manual/automatic)
- ✅ Fan speed adjustments
- ✅ Errors or warnings

### View Logs

```bash
# View last 50 lines
tail -n 50 /var/log/dell-r730-fan-control.log

# Follow log in real-time
tail -f /var/log/dell-r730-fan-control.log

# View with timestamps
tail -f /var/log/dell-r730-fan-control.log | grep -E "GPU|System|Fan"
```

---

## 🔧 Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| **No GPU temperatures detected** | Install appropriate GPU monitoring tool for your vendor (see [GPU Support](#-gpu-support)) |
| **GPU monitoring disabled** | Script will use system temperatures only - this is normal if no GPU tools are installed |
| **Failed to enable manual fan mode** | Check iDRAC credentials and network connectivity |
| **Permission errors** | Ensure `ipmitool` and GPU tools are accessible. For log file, ensure directory exists and is writable |
| **Service not running** | Check status: `sudo systemctl status dell-r730-fan-control.timer` |
| **Log file not writable** | Script will fall back to writing logs in the script directory |

### Quick Diagnostics

```bash
# Check if script can access iDRAC
ipmitool -I lanplus -H <IDRAC_IP> -U <USER> -P <PASS> sdr list | grep Temp

# Check GPU monitoring tools
nvidia-smi --query-gpu=temperature.gpu --format=csv  # NVIDIA
rocm-smi --showtemp                                  # AMD
intel_gpu_top -l 1                                    # Intel
sensors                                              # Generic

# Check service status
sudo systemctl status dell-r730-fan-control.timer
sudo journalctl -u dell-r730-fan-control.service -n 50
```

---

## 🗑️ Uninstallation

To remove the service/cron jobs (but keep the files):

```bash
sudo ./uninstall.sh
```

**This will:**
- ✅ Stop and remove systemd service/timer (if installed)
- ✅ Remove cron jobs (if installed)
- ✅ Keep the script and configuration files intact

---

## 📄 License

This script is provided as-is for use with Dell R730 servers.

**Tags:** `dell-r730` `fan-control` `gpu-monitoring` `temperature-control` `ipmi` `idrac` `nvidia` `amd` `intel` `systemd` `cron` `python` `server-management` `thermal-management`

---

<div align="center">

**Made with ❤️ for Dell R730 server owners**

[⬆ Back to Top](#-dell-server-fan-shusher)

</div>
