# Standalone Utility Scripts

This directory contains standalone utility scripts for manual temperature and fan speed monitoring/control.

## Configuration

All scripts in this directory use `ipmi_config.env` for configuration (separate from the main `.env` file used by `fan_control.py`).

### Setup

1. Copy the example configuration file:
   ```bash
   cp ipmi_config.env.example ipmi_config.env
   ```

2. Edit `ipmi_config.env` with your iDRAC credentials:
   ```bash
   nano ipmi_config.env
   ```

3. Configure the following variables:
   - `SERVER_IP` - iDRAC IP address
   - `IPMI_USERNAME` - iDRAC username  
   - `IPMI_PASSWORD` - iDRAC password

## Available Scripts

### `check_temperatures.sh`
**Standalone temperature checker** - Reads and displays current system temperatures via IPMI.

**Usage:**
```bash
./check_temperatures.sh
```

**What it does:**
- Connects to iDRAC via IPMI
- Queries all temperature sensors
- Displays temperatures in both Celsius and Fahrenheit
- Appends data to `temperature_log.txt` for historical tracking
- **Read-only** - does not modify any settings

### `check_fan_speeds.sh`
**Standalone fan speed checker** - Reads and displays current fan speeds via IPMI with formatted table output.

**Usage:**
```bash
./check_fan_speeds.sh
```

**What it does:**
- Connects to iDRAC via IPMI
- Queries all fan speed sensors
- Displays fan speeds in a formatted table with columns: Fan Name, RPM, and Speed %
- Shows summary statistics (total fans, average, min, max) with percentages
- Appends data to `fan_speed_log.txt` for historical tracking
- **Read-only** - does not modify any settings

### `control_fan_speed.sh`
**Manual fan speed controller** - Allows manual control of fan speeds for testing or emergency situations.

**Usage:**
```bash
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

### `analyze_temperatures.sh`
**Temperature analyzer** - Analyzes current temperatures and categorizes them based on Dell R730 specifications.

**Usage:**
```bash
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

## Log Files

These scripts create log files in the Scripts directory:
- `temperature_log.txt` - Historical temperature data
- `fan_speed_log.txt` - Historical fan speed data

These log files are automatically added to `.gitignore` to prevent committing sensitive data.

## Notes

- These scripts are **independent** of the main `fan_control.py` system
- They use a separate configuration file (`ipmi_config.env`) to allow different server configurations if needed
- All scripts require `ipmitool` to be installed
- All scripts require network access to the iDRAC interface
