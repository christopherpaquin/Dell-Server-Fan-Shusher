<div align="center">

# 🖥️ Dell Server Fan Shusher

**Intelligent fan speed control for Dell R720/R730 servers with multi-vendor GPU temperature monitoring**

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
- [Scripts Reference](#-scripts-reference)
- [Standalone Utility Scripts](#-standalone-utility-scripts)
- [Adaptive Learning System](#-adaptive-learning-system)
- [Troubleshooting](#-troubleshooting)
- [Uninstallation](#-uninstallation)
- [License](#-license)

---

## 🎯 Overview

A Python script that intelligently controls fan speeds on Dell R720/R730 servers based on GPU and system temperatures. The script monitors GPU temperatures from **NVIDIA**, **AMD**, and **Intel** GPUs, and system temperatures via `ipmitool`, then adjusts fan speeds to keep noise low while maintaining safe operating temperatures.

**Designed to run periodically via cron or systemd service.**

### 🏷️ Tags

`dell-r720` `dell-r730` `fan-control` `gpu-monitoring` `temperature-control` `ipmi` `idrac` `nvidia` `amd` `intel` `systemd` `cron` `python` `server-management` `thermal-management`

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🔥 **Multi-Vendor GPU Support** | Supports NVIDIA (nvidia-smi), AMD (rocm-smi/sensors), and Intel (intel_gpu_top/sensors) GPUs |
| 🌡️ **System Temperature Monitoring** | Monitors system temperatures via `ipmitool` |
| ⚙️ **Adaptive Fan Control** | Automatically adjusts fan speeds based on temperature thresholds |
| 🧠 **Smart Mode Switching** | Switches to automatic iDRAC control when temperatures are high |
| 📝 **Verbose Logging** | Detailed logging with decision reasoning, actions taken, and fan speed change tracking |
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

The system uses **7 temperature levels** for granular fan control, perfect for cold room scenarios where you want very low fan speeds at low temperatures.

| Setting | Description | Default |
|---------|-------------|----------|
| `IDRAC_IP` | iDRAC IP address | `10.1.10.20` |
| `IDRAC_USER` | iDRAC username | `root` |
| `IDRAC_PASS` | iDRAC password | `calvin` |
| **GPU Temperature Thresholds (7 levels)** |
| `GPU_TEMP_VERY_LOW` | Very-Low GPU temperature threshold (°C) | `30` |
| `GPU_TEMP_LOW` | Low GPU temperature threshold (°C) | `45` |
| `GPU_TEMP_MED_LOW` | Medium-Low GPU temperature threshold (°C) | `55` |
| `GPU_TEMP_MED` | Medium GPU temperature threshold (°C) | `65` |
| `GPU_TEMP_MED_HIGH` | Medium-High GPU temperature threshold (°C) | `75` |
| `GPU_TEMP_HIGH` | High GPU temperature threshold (°C) | `85` |
| `GPU_TEMP_VERY_HIGH` | Very-High GPU temperature threshold (°C) | `95` |
| **System Temperature Thresholds (7 levels)** |
| `SYSTEM_TEMP_VERY_LOW` | Very-Low system temperature threshold (°C) | `25` |
| `SYSTEM_TEMP_LOW` | Low system temperature threshold (°C) | `40` |
| `SYSTEM_TEMP_MED_LOW` | Medium-Low system temperature threshold (°C) | `50` |
| `SYSTEM_TEMP_MED` | Medium system temperature threshold (°C) | `60` |
| `SYSTEM_TEMP_MED_HIGH` | Medium-High system temperature threshold (°C) | `70` |
| `SYSTEM_TEMP_HIGH` | High system temperature threshold (°C) | `80` |
| `SYSTEM_TEMP_VERY_HIGH` | Very-High system temperature threshold (°C) | `90` |
| **Fan Speed Percentages (7 levels)** |
| `FAN_SPEED_VERY_LOW` | Very-Low fan speed percentage (0-100) | `10` |
| `FAN_SPEED_LOW` | Low fan speed percentage (0-100) | `15` |
| `FAN_SPEED_MED_LOW` | Medium-Low fan speed percentage (0-100) | `25` |
| `FAN_SPEED_MED` | Medium fan speed percentage (0-100) | `35` |
| `FAN_SPEED_MED_HIGH` | Medium-High fan speed percentage (0-100) | `50` |
| `FAN_SPEED_HIGH` | High fan speed percentage (0-100) | `65` |
| `FAN_SPEED_VERY_HIGH` | Very-High fan speed percentage (0-100) | `80` |
| **Other Settings** |
| `AUTO_MODE_THRESHOLD` | Temperature threshold for auto mode (°C) | Auto (max of Very-High thresholds) |
| `GPU_TEMP_OVERRIDE` | Prioritize GPU temps over system temps | `true` |
| `LOG_FILE` | Log file path | `/var/log/dell-r730-fan-control.log` |

### Example Configuration

```env
# Dell R730 iDRAC Credentials
IDRAC_IP=10.1.10.20
IDRAC_USER=root
IDRAC_PASS=your_secure_password

# GPU Temperature Thresholds (Celsius) - 7 levels for granular control
GPU_TEMP_VERY_LOW=30
GPU_TEMP_LOW=45
GPU_TEMP_MED_LOW=55
GPU_TEMP_MED=65
GPU_TEMP_MED_HIGH=75
GPU_TEMP_HIGH=85
GPU_TEMP_VERY_HIGH=95

# System Temperature Thresholds (Celsius) - 7 levels for granular control
SYSTEM_TEMP_VERY_LOW=25
SYSTEM_TEMP_LOW=40
SYSTEM_TEMP_MED_LOW=50
SYSTEM_TEMP_MED=60
SYSTEM_TEMP_MED_HIGH=70
SYSTEM_TEMP_HIGH=80
SYSTEM_TEMP_VERY_HIGH=90

# Fan Speed Percentages (0-100) - 7 levels matching temperature ranges
# For cold room scenarios, lower speeds can be used for lower temperature ranges
FAN_SPEED_VERY_LOW=10
FAN_SPEED_LOW=15
FAN_SPEED_MED_LOW=25
FAN_SPEED_MED=35
FAN_SPEED_MED_HIGH=50
FAN_SPEED_HIGH=65
FAN_SPEED_VERY_HIGH=80

# Switch to automatic mode when temps exceed this threshold
AUTO_MODE_THRESHOLD=95

# GPU Temperature Priority Override
# When enabled (true), GPU temperatures take priority over system temperatures
# If GPU temps are above GPU_TEMP_LOW, they will be used for fan control
# even if system temps are lower. This ensures fans respond to GPU heat.
GPU_TEMP_OVERRIDE=true

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

The script uses a **7-level temperature system** for granular fan control. It checks temperatures from highest to lowest and uses the first threshold that is exceeded.

**Example with default thresholds:**
- System thresholds: Very-Low (25°C), Low (40°C), Medium-Low (50°C), Medium (60°C), Medium-High (70°C), High (80°C), Very-High (90°C)

| Temperature | Fan Speed | Percentage | Description |
|-------------|-----------|------------|-------------|
| **≥ 90°C** | Very-High | 80% | Maximum cooling required |
| **≥ 80°C** | High | 65% | High cooling needed |
| **≥ 70°C** | Medium-High | 50% | Above-average cooling |
| **≥ 60°C** | Medium | 35% | Moderate cooling |
| **≥ 50°C** | Medium-Low | 25% | Light cooling |
| **≥ 40°C** | Low | 15% | Minimal cooling (quiet) |
| **≥ 25°C** | Very-Low | 10% | Very minimal cooling (very quiet) |
| **< 25°C** | Very-Low | 10% | Very minimal cooling (very quiet) |
| **≥ Auto Mode Threshold** | Automatic mode | - | iDRAC takes over control |

**Important Notes:**
- The script uses the **highest** temperature detected (either GPU or system) to determine fan speed
- The 7-level system provides fine-grained control, especially useful for cold room scenarios
- If temperature exceeds the `AUTO_MODE_THRESHOLD`, the script switches to automatic mode and lets iDRAC handle fan control
- The script checks thresholds from highest to lowest, so the first threshold exceeded determines the fan speed

### GPU Temperature Priority Override

By default, the script uses the **higher** of GPU or system temperature. However, you can enable **GPU Temperature Priority Override** to ensure GPU temperatures take priority when GPUs are under load.

**How it works:**
- When `GPU_TEMP_OVERRIDE=true` (default) and GPU temperature is ≥ `GPU_TEMP_LOW`:
  - **GPU temperature is used** for fan control, even if system temperature is lower
  - This ensures fans respond to GPU heat even when the rest of the system is cool
  - GPU thresholds are used for determining fan speed (using the 7-level system)

**Example Scenario:**
- GPU temp: 55°C (above `GPU_TEMP_LOW=45`, in Medium-Low range)
- System temp: 30°C (below `SYSTEM_TEMP_LOW=40`)
- **With override enabled:** Fans use GPU temp (55°C) → MEDIUM-LOW speed (25%)
- **With override disabled:** Fans use max temp (55°C) → MEDIUM-LOW speed (25%)

**When GPU override is active:**
- GPU temps ≥ `GPU_TEMP_LOW` trigger fan response
- System temps are ignored for fan control (but still monitored)
- All system fans spin up to cool the GPUs
- Uses GPU's 7-level temperature thresholds for fan speed determination

**Configuration:**
```env
# Enable GPU temperature priority (default: true)
GPU_TEMP_OVERRIDE=true
```

### 3. Fan Speed Adjustment

When in manual mode, sets fan speed based on the highest temperature detected (GPU or system) using the 7-level threshold system.

### 4. Logging

All temperature checks, mode changes, and fan speed adjustments are logged with timestamps to the configured log file.

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

The script provides **comprehensive verbose logging** that includes:

- ✅ **Timestamp** of each check
- ✅ **Temperature readings** (GPU and system temperatures with maximum values)
- ✅ **Current fan speeds** (before making changes)
- ✅ **Decision reasoning** - Explains why each action was chosen:
  - Which temperature threshold was triggered (VERY-LOW, LOW, MEDIUM-LOW, MEDIUM, MEDIUM-HIGH, HIGH, VERY-HIGH)
  - Whether GPU override is active
  - Which temperature source (GPU vs System) triggered the decision
- ✅ **Action taken** - Clear messages for:
  - Switching to AUTOMATIC mode (with reason)
  - Setting fan speed to a specific percentage (with reason)
- ✅ **Fan speed changes** - Tracks before/after speeds:
  - Shows INCREASED, DECREASED, or UNCHANGED
  - Displays RPM values before and after changes
- ✅ **Errors or warnings**

### Example Log Output

```
============================================================
Dell R730 Fan Control - GPU Aware - Starting check
iDRAC IP: 10.1.10.20
GPU Temperatures: 55, 58°C (max: 58°C)
System Temperatures: 35, 38, 40°C (max: 40°C)
Current Fan Speeds: 2400, 2450, 2380 RPM (avg: 2410 RPM)
Decision: GPU temperature 58°C >= MEDIUM-LOW threshold (55°C) - GPU override active
ACTION: Setting fan speed to 25% (Target: 25%)
Reason: GPU temperature 58°C >= MEDIUM-LOW threshold (55°C) - GPU override active
Manual fan mode enabled
IPMI command successful: Fan speed set to 25%
Fan speed DECREASED: 2410 RPM → 1800 RPM
Check complete
============================================================
```

### View Logs

```bash
# View last 50 lines
tail -n 50 /var/log/dell-r730-fan-control.log

# Follow log in real-time
tail -f /var/log/dell-r730-fan-control.log

# View with timestamps
tail -f /var/log/dell-r730-fan-control.log | grep -E "GPU|System|Fan"

# View only actions and decisions
tail -f /var/log/dell-r730-fan-control.log | grep -E "ACTION|Decision|Reason"

# View fan speed changes
tail -f /var/log/dell-r730-fan-control.log | grep -E "INCREASED|DECREASED|UNCHANGED"
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

## 📜 Scripts Reference

This repository contains several scripts for different purposes:

### Main Scripts

#### `fan_control.py`
**Main fan control script** - The primary Python script that monitors temperatures and adjusts fan speeds automatically.

**Usage:**
```bash
python3 fan_control.py              # Normal operation: check temps and adjust fans
python3 fan_control.py --temps      # Check temperatures only (read-only)
python3 fan_control.py --fans       # Check fan speeds only (read-only)
python3 fan_control.py --history    # View temperature history
```

**Features:**
- Monitors GPU and system temperatures
- Automatically adjusts fan speeds based on 7-level temperature thresholds
- Supports NVIDIA, AMD, and Intel GPUs
- Comprehensive logging
- Can run as a systemd service or cron job

#### `install.sh`
**Installation script** - Automated setup script that handles all installation tasks.

**Usage:**
```bash
sudo ./install.sh
```

**What it does:**
- Checks for required dependencies (python3, ipmitool)
- Checks for GPU monitoring tools
- Installs Python dependencies
- Creates `.env` file from template
- Sets proper permissions
- Creates log directory
- Sets up systemd service or cron job (your choice)
- Performs a test run

#### `uninstall.sh`
**Uninstallation script** - Removes the service/cron jobs while keeping configuration files.

**Usage:**
```bash
sudo ./uninstall.sh
```

**What it does:**
- Stops and removes systemd service/timer (if installed)
- Removes cron jobs (if installed)
- Keeps the script and configuration files intact

### Standalone Utility Scripts

The standalone utility scripts are located in the `Scripts/` directory. These scripts are independent of the main fan control system and use a separate configuration file.

**Location:** `Scripts/` directory

**Setup:**
1. Navigate to the Scripts directory:
   ```bash
   cd Scripts
   ```

2. Copy the example configuration:
   ```bash
   cp ipmi_config.env.example ipmi_config.env
   ```

3. Edit `ipmi_config.env` with your iDRAC credentials:
   ```bash
   nano ipmi_config.env
   ```

**Available Scripts:**

#### `Scripts/check_temperatures.sh`
**Standalone temperature checker** - Reads and displays current system temperatures via IPMI.

**Usage:**
```bash
cd Scripts
./check_temperatures.sh
```

**What it does:**
- Connects to iDRAC via IPMI
- Queries all temperature sensors
- Displays temperatures in both Celsius and Fahrenheit
- Appends data to `temperature_log.txt` for historical tracking
- **Read-only** - does not modify any settings

#### `Scripts/check_fan_speeds.sh`
**Standalone fan speed checker** - Reads and displays current fan speeds via IPMI with formatted table output.

**Usage:**
```bash
cd Scripts
./check_fan_speeds.sh
```

**What it does:**
- Connects to iDRAC via IPMI
- Queries all fan speed sensors
- Displays fan speeds in a formatted table with columns: Fan Name, RPM, and Speed %
- Shows summary statistics (total fans, average, min, max) with percentages
- Appends data to `fan_speed_log.txt` for historical tracking
- **Read-only** - does not modify any settings

#### `Scripts/control_fan_speed.sh`
**Manual fan speed controller** - Allows manual control of fan speeds for testing or emergency situations.

**Usage:**
```bash
cd Scripts
./control_fan_speed.sh manual              # Switch to manual fan control mode
./control_fan_speed.sh auto                # Switch back to automatic mode
./control_fan_speed.sh set <percentage>    # Set fan speed (0-100%)
./control_fan_speed.sh disable-third-party # Disable aggressive cooling for third-party hardware
```

**Examples:**
```bash
./control_fan_speed.sh set 20    # Set fans to 20% (quiet, monitor temps!)
./control_fan_speed.sh set 30    # Set fans to 30% (moderate)
./control_fan_speed.sh auto      # Return to automatic control
```

**What it does:**
- Provides direct IPMI commands for fan control
- Useful for testing or when the main script isn't running
- **WARNING:** Always monitor temperatures when using manual control
- Can disable third-party device cooling response (helps if non-Dell hardware causes high fan speeds)

#### `Scripts/analyze_temperatures.sh`
**Temperature analyzer** - Analyzes current temperatures and categorizes them based on Dell R730 specifications.

**Usage:**
```bash
cd Scripts
./analyze_temperatures.sh
```

**What it does:**
- Runs `check_temperatures.sh` to get current temperatures
- Categorizes each sensor as LOW, MEDIUM, HIGH, or CRITICAL
- Uses color-coded output (green/yellow/red)
- Displays temperatures in both Celsius and Fahrenheit
- Applies different thresholds based on sensor type:
  - **CPU/Processor**: LOW (<46°C / <115°F), MEDIUM (46-65°C / 115-149°F), HIGH (66-89°C / 151-192°F), CRITICAL (≥90°C / ≥194°F)
  - **Inlet/Ambient**: LOW (<21°C / <70°F), MEDIUM (21-30°C / 70-86°F), HIGH (31-35°C / 88-95°F), CRITICAL (>35°C / >95°F)
  - **System Board**: LOW (<40°C), MEDIUM (40-60°C), HIGH (61-80°C), CRITICAL (>80°C)
- Displays reference thresholds at the end

**For detailed documentation on these scripts, see:** `Scripts/README.md`

### Configuration Files

#### `.env`
**Main configuration file** - Used by `fan_control.py` for all fan control settings.

**Location:** Root directory

**Contains:**
- iDRAC credentials
- 7-level temperature thresholds (GPU and System)
- 7-level fan speed settings
- Auto mode threshold
- GPU temperature override settings
- Log file paths

#### `Scripts/ipmi_config.env`
**Standalone scripts configuration** - Used by the standalone shell scripts in the `Scripts/` directory.

**Location:** `Scripts/` directory

**Setup:**
```bash
cd Scripts
cp ipmi_config.env.example ipmi_config.env
nano ipmi_config.env
```

**Contains:**
- `SERVER_IP` - iDRAC IP address
- `IPMI_USERNAME` - iDRAC username
- `IPMI_PASSWORD` - iDRAC password

**Note:** This is separate from `.env` to allow different configurations if needed. The standalone scripts are independent utilities that can be used without the main fan control system.

---

## 🧠 Adaptive Learning System

The fan control system includes an adaptive learning feature that analyzes historical temperature and fan speed data to optimize thresholds automatically.

### How It Works

1. **Data Collection**: The `fan_control.py` script automatically logs unified data (temperatures + fan speeds) to `fan_control_data.log` on each run
2. **Analysis**: The `learn_thresholds.py` script analyzes this data to identify patterns
3. **Suggestions**: The learning script suggests threshold adjustments based on:
   - Temperature stability at different fan speeds
   - Fan efficiency analysis
   - Temperature trends over time

### Using the Learning System

#### Run Learning Analysis

```bash
python3 learn_thresholds.py
```

**What it does:**
- Analyzes last 7 days of data (configurable)
- Identifies optimal temperature thresholds for each fan speed level
- Detects if fans are running too high or too low
- Suggests threshold adjustments with confidence levels

**Output includes:**
- Data analysis summary (total points, date range, temperature statistics)
- Fan speed efficiency analysis (average temps at each fan speed %)
- Temperature trend analysis (detects rising/falling trends)
- Suggested threshold adjustments with reasons

#### Example Output

```
======================================================================
Fan Control Threshold Learning Report
======================================================================

Data Analysis:
  Total data points: 1250
  Date range: 2026-01-15 10:00:00 to 2026-01-21 23:30:00
  Average max temperature: 36.2°C
  Temperature range: 28.0°C - 45.0°C

Fan Speed Efficiency Analysis:
   10%: Avg temp 33.5°C (±1.2°C), Avg RPM 3320, Samples: 450
   15%: Avg temp 38.2°C (±1.8°C), Avg RPM 4200, Samples: 320
   ...

Suggested Threshold Adjustments:
  ✓ SYSTEM_TEMP_LOW: 40°C → 38°C
     Reason: Fan speed 15% maintains stable temp at 36.2°C (±1.8°C)
```

### Configuration

The learning system uses the following settings (in `.env`):

| Setting | Description | Default |
|---------|-------------|---------|
| `DATA_LOG_FILE` | Path to unified data log file | `fan_control_data.log` |

### Data Log Format

The unified data log (`fan_control_data.log`) contains:
- Timestamp
- Max GPU temperature
- Max system temperature
- Average fan RPM
- Fan speed percentage
- All GPU temperatures (CSV)
- All system temperatures (CSV)
- All fan speeds (CSV)

Format: `timestamp|max_gpu|max_system|avg_fan_rpm|fan_speed_pct|gpu_temps_csv|system_temps_csv|fan_speeds_csv`

### Learning Algorithm

The learning system:

1. **Requires minimum data**: Needs at least 100 data points for reliable analysis
2. **Analyzes efficiency**: Groups data by fan speed percentage and calculates:
   - Average temperature maintained
   - Temperature stability (standard deviation)
   - Sample count for confidence
3. **Detects trends**: Identifies if temperatures are rising (fans too low) or falling (fans too high)
4. **Suggests adjustments**: Only suggests changes if:
   - Temperature is stable at a fan speed (low std dev)
   - Suggested change is >2°C different from current
   - Sufficient sample data exists (confidence level)

### Best Practices

1. **Let it collect data**: Run `fan_control.py` normally for at least a few days to collect sufficient data
2. **Review suggestions**: Always review learning suggestions before applying
3. **Monitor after changes**: After applying suggested thresholds, monitor temperatures closely
4. **Run periodically**: Run `learn_thresholds.py` weekly or monthly to optimize thresholds
5. **Consider environment**: Learning suggestions are based on your specific environment - adjust if needed

### Automatic Threshold Updates (Future)

Future versions may include automatic threshold updates based on learning analysis. For now, review suggestions and update `.env` manually.

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
