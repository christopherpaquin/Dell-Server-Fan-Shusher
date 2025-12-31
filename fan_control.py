#!/usr/bin/env python3
"""
Dell R730 Fan Control Script with GPU Temperature Awareness
Monitors GPU temperatures from NVIDIA, AMD, and Intel GPUs, and system temperatures via ipmitool,
then adjusts fan speeds accordingly to keep noise low while maintaining safe temperatures.

GPU Support:
- NVIDIA: Uses nvidia-smi
- AMD: Uses rocm-smi or sensors (lm-sensors)
- Intel: Uses intel_gpu_top or sensors (lm-sensors)

Designed to run periodically via cron or systemd service.
"""

import subprocess
import time
import re
import sys
import os
import logging
import argparse
from datetime import datetime
from collections import defaultdict
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration from environment
IDRAC_IP = os.getenv('IDRAC_IP', '10.1.10.20')
IDRAC_USER = os.getenv('IDRAC_USER', 'root')
IDRAC_PASS = os.getenv('IDRAC_PASS', 'calvin')

# Temperature thresholds (in Celsius)
GPU_TEMP_LOW = int(os.getenv('GPU_TEMP_LOW', '50'))
GPU_TEMP_MED = int(os.getenv('GPU_TEMP_MED', '60'))
GPU_TEMP_HIGH = int(os.getenv('GPU_TEMP_HIGH', '70'))
GPU_TEMP_CRITICAL = int(os.getenv('GPU_TEMP_CRITICAL', '80'))

SYSTEM_TEMP_LOW = int(os.getenv('SYSTEM_TEMP_LOW', '40'))
SYSTEM_TEMP_MED = int(os.getenv('SYSTEM_TEMP_MED', '50'))
SYSTEM_TEMP_HIGH = int(os.getenv('SYSTEM_TEMP_HIGH', '60'))
SYSTEM_TEMP_CRITICAL = int(os.getenv('SYSTEM_TEMP_CRITICAL', '70'))

# Fan speed percentages (0-100%)
FAN_SPEED_LOW = int(os.getenv('FAN_SPEED_LOW', '20'))
FAN_SPEED_MED = int(os.getenv('FAN_SPEED_MED', '40'))
FAN_SPEED_HIGH = int(os.getenv('FAN_SPEED_HIGH', '60'))
FAN_SPEED_CRITICAL = int(os.getenv('FAN_SPEED_CRITICAL', '80'))

# Temperature threshold for switching to automatic mode (let iDRAC handle it)
# If temps exceed this, disable manual mode and let iDRAC take over
AUTO_MODE_THRESHOLD = int(os.getenv('AUTO_MODE_THRESHOLD', '75'))

# IPMI timeout and retry settings (for slow ipmitool responses)
IPMI_TIMEOUT = int(os.getenv('IPMI_TIMEOUT', '20'))  # seconds
IPMI_RETRIES = int(os.getenv('IPMI_RETRIES', '2'))  # number of retries

# GPU Temperature Priority Override
# When enabled, GPU temperatures take priority over system temperatures
# If GPU temps are above GPU_TEMP_LOW, they will be used for fan control
GPU_TEMP_OVERRIDE = os.getenv('GPU_TEMP_OVERRIDE', 'true').lower() in ('true', '1', 'yes', 'on')

# Log file path
LOG_FILE = os.getenv('LOG_FILE', '/var/log/dell-r730-fan-control.log')

# Setup logging (will be reconfigured in main() for read-only modes)
log_dir = os.path.dirname(LOG_FILE)
if log_dir and not os.path.exists(log_dir):
    try:
        os.makedirs(log_dir, exist_ok=True)
    except PermissionError:
        # Fallback to current directory if can't write to /var/log
        LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fan_control.log')

def setup_logging(read_only=False):
    """Setup logging configuration."""
    if read_only:
        # Minimal logging for read-only operations
        logging.basicConfig(
            level=logging.WARNING,
            format='%(message)s',
            handlers=[logging.StreamHandler(sys.stdout)]
        )
    else:
        # Full logging for normal operations
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(LOG_FILE),
                logging.StreamHandler(sys.stdout)
            ],
            force=True  # Reconfigure if already set up
        )

# Initialize logger
logger = logging.getLogger(__name__)


def run_ipmi_command(cmd_args, retries=None, timeout=None):
    """
    Execute an IPMI command with retry logic and increased timeout.
    ipmitool can be slow, especially over network, so we use longer timeout and retries.
    """
    # Use configured values or defaults
    if retries is None:
        retries = IPMI_RETRIES
    if timeout is None:
        timeout = IPMI_TIMEOUT
    
    for attempt in range(retries + 1):
        try:
            result = subprocess.run(
                ['ipmitool', '-I', 'lanplus', '-H', IDRAC_IP, '-U', IDRAC_USER, '-P', IDRAC_PASS] + cmd_args,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            if result.returncode == 0:
                return True, result.stdout, result.stderr
            elif attempt < retries:
                logger.debug(f"IPMI command failed (attempt {attempt + 1}/{retries + 1}), retrying...")
                time.sleep(1)  # Brief delay before retry
        except subprocess.TimeoutExpired:
            if attempt < retries:
                logger.debug(f"IPMI command timed out (attempt {attempt + 1}/{retries + 1}), retrying...")
                time.sleep(1)
            else:
                logger.warning(f"IPMI command timed out after {retries + 1} attempts")
                return False, '', 'Command timed out after retries'
        except Exception as e:
            if attempt < retries:
                logger.debug(f"IPMI command error (attempt {attempt + 1}/{retries + 1}): {e}, retrying...")
                time.sleep(1)
            else:
                return False, '', str(e)
    
    return False, '', 'Command failed after all retries'


def enable_manual_fan_mode():
    """Put iDRAC fans into manual mode."""
    success, stdout, stderr = run_ipmi_command(['raw', '0x30', '0x30', '0x01', '0x00'])
    if success:
        logger.info("Manual fan mode enabled")
        return True
    else:
        logger.error(f"Failed to enable manual fan mode: {stderr}")
        return False


def enable_automatic_fan_mode():
    """Put iDRAC fans into automatic mode (let iDRAC control)."""
    success, stdout, stderr = run_ipmi_command(['raw', '0x30', '0x30', '0x01', '0x01'])
    if success:
        logger.info("Automatic fan mode enabled (iDRAC control)")
        return True
    else:
        logger.error(f"Failed to enable automatic fan mode: {stderr}")
        return False


def set_fan_speed(percentage):
    """Set global fan speed to specified percentage (0-100)."""
    # Clamp percentage to valid range
    percentage = max(0, min(100, percentage))
    hex_value = format(percentage, '02x')
    
    success, stdout, stderr = run_ipmi_command(['raw', '0x30', '0x30', '0x02', '0xff', hex_value])
    if success:
        logger.info(f"Fan speed set to {percentage}%")
        return True
    else:
        logger.error(f"Failed to set fan speed: {stderr}")
        return False


def get_gpu_temperatures_nvidia():
    """Get GPU temperatures from nvidia-smi (NVIDIA GPUs)."""
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=temperature.gpu', '--format=csv,noheader,nounits'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            temps = []
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    try:
                        temps.append(int(line.strip()))
                    except ValueError:
                        pass
            return temps
        return []
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []
    except Exception:
        return []


def get_gpu_temperatures_amd():
    """Get GPU temperatures from rocm-smi (AMD GPUs)."""
    try:
        result = subprocess.run(
            ['rocm-smi', '--showtemp', '--csv'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            temps = []
            # rocm-smi CSV format: device,temperature
            for line in result.stdout.strip().split('\n'):
                if line.strip() and ',' in line:
                    parts = line.split(',')
                    if len(parts) >= 2:
                        try:
                            # Skip header line
                            if 'temperature' in parts[1].lower():
                                continue
                            temp = int(float(parts[1].strip()))
                            temps.append(temp)
                        except (ValueError, IndexError):
                            pass
            return temps
        return []
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []
    except Exception:
        return []


def get_gpu_temperatures_sensors():
    """Get GPU temperatures from sensors (lm-sensors) - works for AMD and some Intel GPUs."""
    try:
        result = subprocess.run(
            ['sensors'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            temps = []
            # Look for GPU temperature readings in sensors output
            # Common patterns: "temp1:", "edge:", "junction:", "Tdie:", etc.
            for line in result.stdout.split('\n'):
                line_lower = line.lower()
                # Look for GPU-related temperature sensors
                if any(keyword in line_lower for keyword in ['gpu', 'radeon', 'amdgpu', 'intel', 'graphics']):
                    # Extract temperature value (format: "temp1: +45.0°C" or "edge: +65.0°C")
                    match = re.search(r'[+\-]?(\d+\.?\d*)\s*°?C', line)
                    if match:
                        try:
                            temp = int(float(match.group(1)))
                            temps.append(temp)
                        except ValueError:
                            pass
            return temps
        return []
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []
    except Exception:
        return []


def get_gpu_temperatures_intel():
    """Get GPU temperatures from intel_gpu_top (Intel GPUs)."""
    try:
        result = subprocess.run(
            ['intel_gpu_top', '-l', '1'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            temps = []
            # intel_gpu_top output format varies, look for temperature patterns
            for line in result.stdout.split('\n'):
                if 'temp' in line.lower() or 'temperature' in line.lower():
                    match = re.search(r'(\d+)\s*°?C', line, re.IGNORECASE)
                    if match:
                        try:
                            temp = int(match.group(1))
                            temps.append(temp)
                        except ValueError:
                            pass
            return temps
        return []
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []
    except Exception:
        return []


def get_gpu_temperatures():
    """
    Get GPU temperatures from available GPU monitoring tools.
    Tries multiple methods to support NVIDIA, AMD, and Intel GPUs.
    Returns list of temperatures in Celsius.
    """
    # Try NVIDIA first (most common in servers)
    temps = get_gpu_temperatures_nvidia()
    if temps:
        logger.debug("GPU temperatures obtained via nvidia-smi (NVIDIA)")
        return temps
    
    # Try AMD
    temps = get_gpu_temperatures_amd()
    if temps:
        logger.debug("GPU temperatures obtained via rocm-smi (AMD)")
        return temps
    
    # Try Intel
    temps = get_gpu_temperatures_intel()
    if temps:
        logger.debug("GPU temperatures obtained via intel_gpu_top (Intel)")
        return temps
    
    # Try sensors (works for AMD and some Intel)
    temps = get_gpu_temperatures_sensors()
    if temps:
        logger.debug("GPU temperatures obtained via sensors (lm-sensors)")
        return temps
    
    # No GPU temperatures found
    return []


def get_system_temperatures_sysfs():
    """Get system temperatures from /sys/class/hwmon (faster than ipmitool)."""
    temps = []
    try:
        # Check all hwmon devices
        hwmon_path = '/sys/class/hwmon'
        if not os.path.exists(hwmon_path):
            return []
        
        for hwmon_dir in os.listdir(hwmon_path):
            hwmon_full_path = os.path.join(hwmon_path, hwmon_dir)
            if not os.path.isdir(hwmon_full_path):
                continue
            
            # Look for temperature files (temp*_input)
            for file in os.listdir(hwmon_full_path):
                if file.startswith('temp') and file.endswith('_input'):
                    temp_file = os.path.join(hwmon_full_path, file)
                    try:
                        with open(temp_file, 'r') as f:
                            temp_millidegrees = int(f.read().strip())
                            temp_celsius = temp_millidegrees // 1000  # Convert from millidegrees
                            if temp_celsius > -50 and temp_celsius < 200:  # Sanity check
                                temps.append(temp_celsius)
                    except (ValueError, IOError, OSError):
                        continue
    except (OSError, PermissionError):
        pass
    
    return temps


def get_system_temperatures_sensors():
    """Get system temperatures from sensors command (lm-sensors)."""
    temps = []
    try:
        result = subprocess.run(
            ['sensors'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            # Parse sensors output for temperature readings
            for line in result.stdout.split('\n'):
                # Look for temperature patterns: "temp1: +45.0°C" or "Core 0: +50.0°C"
                if '°C' in line or '°F' in line:
                    # Extract temperature value
                    match = re.search(r'[+\-]?(\d+\.?\d*)\s*°C', line)
                    if match:
                        try:
                            temp = int(float(match.group(1)))
                            if temp > -50 and temp < 200:  # Sanity check
                                temps.append(temp)
                        except ValueError:
                            pass
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    except Exception:
        pass
    
    return temps


def get_system_temperatures():
    """
    Get system temperatures from multiple sources.
    Tries faster methods first (sysfs, sensors), then falls back to ipmitool.
    """
    # Try sysfs first (fastest, no network)
    temps = get_system_temperatures_sysfs()
    if temps:
        logger.debug("System temperatures obtained via sysfs")
        return temps
    
    # Try sensors command (fast, local)
    temps = get_system_temperatures_sensors()
    if temps:
        logger.debug("System temperatures obtained via sensors command")
        return temps
    
    # Fall back to ipmitool (slower, network-based)
    logger.debug("Falling back to ipmitool for system temperatures")
    success, stdout, stderr = run_ipmi_command(['sdr', 'list'])
    if not success:
        return []
    
    temps = []
    # Parse temperature readings from SDR output
    for line in stdout.split('\n'):
        if 'Temp' in line or 'temperature' in line.lower():
            # Try to extract temperature value
            match = re.search(r'(\d+)\s*degrees', line, re.IGNORECASE)
            if match:
                try:
                    temp = int(match.group(1))
                    temps.append(temp)
                except ValueError:
                    pass
    
    if temps:
        logger.debug("System temperatures obtained via ipmitool")
    
    return temps


def get_fan_speeds_sysfs():
    """Get fan speeds from /sys/class/hwmon (faster than ipmitool)."""
    speeds = []
    try:
        hwmon_path = '/sys/class/hwmon'
        if not os.path.exists(hwmon_path):
            return []
        
        for hwmon_dir in os.listdir(hwmon_path):
            hwmon_full_path = os.path.join(hwmon_path, hwmon_dir)
            if not os.path.isdir(hwmon_full_path):
                continue
            
            # Look for fan speed files (fan*_input)
            for file in os.listdir(hwmon_full_path):
                if file.startswith('fan') and file.endswith('_input'):
                    fan_file = os.path.join(hwmon_full_path, file)
                    try:
                        with open(fan_file, 'r') as f:
                            speed = int(f.read().strip())
                            if speed > 0 and speed < 50000:  # Sanity check (RPM)
                                speeds.append(speed)
                    except (ValueError, IOError, OSError):
                        continue
    except (OSError, PermissionError):
        pass
    
    return speeds


def get_fan_speeds_sensors():
    """Get fan speeds from sensors command (lm-sensors)."""
    speeds = []
    try:
        result = subprocess.run(
            ['sensors'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            # Parse sensors output for fan speeds
            for line in result.stdout.split('\n'):
                if 'fan' in line.lower() and ('RPM' in line.upper() or 'rpm' in line):
                    # Extract RPM value
                    match = re.search(r'(\d+)\s*RPM', line, re.IGNORECASE)
                    if match:
                        try:
                            speed = int(match.group(1))
                            if speed > 0:
                                speeds.append(speed)
                        except ValueError:
                            pass
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    except Exception:
        pass
    
    return speeds


def get_fan_speeds():
    """
    Get current fan speeds from multiple sources.
    Tries faster methods first (sysfs, sensors), then falls back to ipmitool.
    """
    # Try sysfs first (fastest, no network)
    speeds = get_fan_speeds_sysfs()
    if speeds:
        logger.debug("Fan speeds obtained via sysfs")
        return speeds
    
    # Try sensors command (fast, local)
    speeds = get_fan_speeds_sensors()
    if speeds:
        logger.debug("Fan speeds obtained via sensors command")
        return speeds
    
    # Fall back to ipmitool (slower, network-based, but may have more info)
    logger.debug("Falling back to ipmitool for fan speeds")
    success, stdout, stderr = run_ipmi_command(['sdr', 'list'])
    if not success:
        return []
    
    speeds = []
    for line in stdout.split('\n'):
        if 'Fan' in line:
            # Try to extract RPM or percentage
            match = re.search(r'(\d+)\s*(?:RPM|%)', line, re.IGNORECASE)
            if match:
                try:
                    speed = int(match.group(1))
                    speeds.append(speed)
                except ValueError:
                    pass
    
    if speeds:
        logger.debug("Fan speeds obtained via ipmitool")
    
    return speeds


def determine_fan_action(gpu_temps, system_temps):
    """
    Determine what action to take based on temperatures.
    Returns: (action, speed)
    - action: 'manual' or 'auto'
    - speed: fan speed percentage (only used if action is 'manual')
    """
    # Get maximum temperatures
    max_gpu_temp = max(gpu_temps) if gpu_temps else 0
    max_system_temp = max(system_temps) if system_temps else 0
    
    # GPU Temperature Priority Override logic
    # If enabled and GPU temps are above LOW threshold, prioritize GPU temps
    if GPU_TEMP_OVERRIDE and gpu_temps and max_gpu_temp >= GPU_TEMP_LOW:
        # Use GPU temperature for fan control (GPU takes priority)
        decision_temp = max_gpu_temp
        temp_source = 'GPU'
        use_gpu_thresholds = True
        logger.debug(f"GPU override active: Using GPU temp {max_gpu_temp}°C (System: {max_system_temp}°C)")
    else:
        # Use the higher of GPU or system temperature (default behavior)
        decision_temp = max(max_gpu_temp, max_system_temp)
        temp_source = 'GPU' if max_gpu_temp >= max_system_temp else 'System'
        use_gpu_thresholds = False
    
    # If temperatures exceed auto mode threshold, let iDRAC handle it
    if max_gpu_temp >= AUTO_MODE_THRESHOLD or max_system_temp >= AUTO_MODE_THRESHOLD:
        return ('auto', None)
    
    # Determine fan speed based on critical thresholds
    # Checks from highest to lowest temperature
    if use_gpu_thresholds:
        # Use GPU thresholds when GPU is prioritized
        if decision_temp >= GPU_TEMP_CRITICAL:
            return ('manual', FAN_SPEED_CRITICAL)
        elif decision_temp >= GPU_TEMP_HIGH:
            return ('manual', FAN_SPEED_HIGH)
        elif decision_temp >= GPU_TEMP_MED:
            return ('manual', FAN_SPEED_MED)
        elif decision_temp >= GPU_TEMP_LOW:
            return ('manual', FAN_SPEED_LOW)
        else:
            return ('manual', FAN_SPEED_LOW)
    else:
        # Use both GPU and system thresholds (original behavior)
        if max_gpu_temp >= GPU_TEMP_CRITICAL or max_system_temp >= SYSTEM_TEMP_CRITICAL:
            return ('manual', FAN_SPEED_CRITICAL)
        elif max_gpu_temp >= GPU_TEMP_HIGH or max_system_temp >= SYSTEM_TEMP_HIGH:
            return ('manual', FAN_SPEED_HIGH)
        elif max_gpu_temp >= GPU_TEMP_MED or max_system_temp >= SYSTEM_TEMP_MED:
            return ('manual', FAN_SPEED_MED)
        elif max_gpu_temp >= GPU_TEMP_LOW or max_system_temp >= SYSTEM_TEMP_LOW:
            return ('manual', FAN_SPEED_LOW)  # Use LOW speed between LOW and MED thresholds
        else:
            return ('manual', FAN_SPEED_LOW)


def check_temperatures():
    """Check and display current temperatures (read-only)."""
    print("=" * 60)
    print("Temperature Check")
    print("=" * 60)
    print(f"iDRAC IP: {IDRAC_IP}")
    print()
    
    # Get temperatures
    gpu_temps = get_gpu_temperatures()
    system_temps = get_system_temperatures()
    
    # Display GPU temperatures
    if gpu_temps:
        print(f"GPU Temperatures:")
        for i, temp in enumerate(gpu_temps):
            print(f"  GPU {i}: {temp}°C")
        print(f"  Max GPU: {max(gpu_temps)}°C")
    else:
        print("GPU Temperatures: No GPUs detected or GPU monitoring tools unavailable")
    
    print()
    
    # Display system temperatures
    if system_temps:
        print(f"System Temperatures:")
        for i, temp in enumerate(system_temps):
            print(f"  Sensor {i}: {temp}°C")
        print(f"  Max System: {max(system_temps)}°C")
    else:
        print("System Temperatures: Unable to read")
    
    print()
    
    # Show thresholds
    max_temp = max(
        max(gpu_temps) if gpu_temps else 0,
        max(system_temps) if system_temps else 0
    )
    print(f"Current Max Temperature: {max_temp}°C")
    print()
    print("Temperature Thresholds:")
    print(f"  Low: {GPU_TEMP_LOW}°C / {SYSTEM_TEMP_LOW}°C (GPU/System)")
    print(f"  Medium: {GPU_TEMP_MED}°C / {SYSTEM_TEMP_MED}°C")
    print(f"  High: {GPU_TEMP_HIGH}°C / {SYSTEM_TEMP_HIGH}°C")
    print(f"  Critical: {GPU_TEMP_CRITICAL}°C / {SYSTEM_TEMP_CRITICAL}°C")
    print(f"  Auto Mode Threshold: {AUTO_MODE_THRESHOLD}°C")
    print("=" * 60)


def check_fan_speeds():
    """Check and display current fan speeds (read-only)."""
    print("=" * 60)
    print("Fan Speed Check")
    print("=" * 60)
    print(f"iDRAC IP: {IDRAC_IP}")
    print()
    
    # Get fan speeds
    fan_speeds = get_fan_speeds()
    
    if fan_speeds:
        print("Current Fan Speeds:")
        for i, speed in enumerate(fan_speeds):
            print(f"  Fan {i+1}: {speed} RPM")
        print(f"  Average: {sum(fan_speeds) // len(fan_speeds)} RPM")
        print(f"  Min: {min(fan_speeds)} RPM")
        print(f"  Max: {max(fan_speeds)} RPM")
    else:
        print("Fan Speeds: Unable to read")
    
    print()
    print("Configured Fan Speed Settings:")
    print(f"  Low: {FAN_SPEED_LOW}%")
    print(f"  Medium: {FAN_SPEED_MED}%")
    print(f"  High: {FAN_SPEED_HIGH}%")
    print(f"  Critical: {FAN_SPEED_CRITICAL}%")
    print("=" * 60)


def show_temperature_history(lines=50):
    """Show temperature history from log file."""
    print("=" * 60)
    print(f"Temperature History (last {lines} entries)")
    print("=" * 60)
    
    if not os.path.exists(LOG_FILE):
        print(f"Log file not found: {LOG_FILE}")
        return
    
    try:
        with open(LOG_FILE, 'r') as f:
            all_lines = f.readlines()
        
        # Extract temperature entries
        temp_entries = []
        for line in all_lines:
            if 'GPU Temperatures:' in line or 'System Temperatures:' in line:
                temp_entries.append(line.strip())
        
        # Show last N entries
        for entry in temp_entries[-lines:]:
            print(entry)
        
        if not temp_entries:
            print("No temperature entries found in log file.")
        
    except Exception as e:
        print(f"Error reading log file: {e}")


def show_detailed_history(hours=24):
    """Show detailed temperature history with timestamps."""
    print("=" * 60)
    print(f"Detailed Temperature History (last {hours} hours)")
    print("=" * 60)
    
    if not os.path.exists(LOG_FILE):
        print(f"Log file not found: {LOG_FILE}")
        return
    
    try:
        cutoff_time = datetime.now().timestamp() - (hours * 3600)
        gpu_temps_history = []
        system_temps_history = []
        fan_speeds_history = []
        
        with open(LOG_FILE, 'r') as f:
            for line in f:
                # Parse timestamp
                try:
                    # Log format: YYYY-MM-DD HH:MM:SS,XXX - LEVEL - message
                    timestamp_str = line[:19]  # First 19 chars are YYYY-MM-DD HH:MM:SS
                    timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S').timestamp()
                    
                    if timestamp < cutoff_time:
                        continue
                    
                    # Extract GPU temps
                    if 'GPU Temperatures:' in line:
                        match = re.search(r'GPU Temperatures: ([\d\s,]+)°C', line)
                        if match:
                            temps_str = match.group(1)
                            temps = [int(t.strip()) for t in temps_str.split(',') if t.strip().isdigit()]
                            if temps:
                                gpu_temps_history.append((timestamp, temps))
                    
                    # Extract system temps
                    if 'System Temperatures:' in line:
                        match = re.search(r'System Temperatures: ([\d\s,]+)°C', line)
                        if match:
                            temps_str = match.group(1)
                            temps = [int(t.strip()) for t in temps_str.split(',') if t.strip().isdigit()]
                            if temps:
                                system_temps_history.append((timestamp, temps))
                    
                    # Extract fan speeds
                    if 'Current Fan Speeds:' in line:
                        match = re.search(r'Current Fan Speeds: ([\d\s,]+)', line)
                        if match:
                            speeds_str = match.group(1)
                            speeds = [int(s.strip()) for s in speeds_str.split(',') if s.strip().isdigit()]
                            if speeds:
                                fan_speeds_history.append((timestamp, speeds))
                
                except (ValueError, IndexError):
                    continue
        
        # Display history
        print("\nGPU Temperature History:")
        if gpu_temps_history:
            for timestamp, temps in gpu_temps_history[-20:]:  # Last 20 entries
                dt = datetime.fromtimestamp(timestamp)
                max_temp = max(temps)
                print(f"  {dt.strftime('%Y-%m-%d %H:%M:%S')}: {', '.join(map(str, temps))}°C (max: {max_temp}°C)")
        else:
            print("  No GPU temperature data found")
        
        print("\nSystem Temperature History:")
        if system_temps_history:
            for timestamp, temps in system_temps_history[-20:]:  # Last 20 entries
                dt = datetime.fromtimestamp(timestamp)
                max_temp = max(temps)
                print(f"  {dt.strftime('%Y-%m-%d %H:%M:%S')}: {', '.join(map(str, temps))}°C (max: {max_temp}°C)")
        else:
            print("  No system temperature data found")
        
        print("\nFan Speed History:")
        if fan_speeds_history:
            for timestamp, speeds in fan_speeds_history[-20:]:  # Last 20 entries
                dt = datetime.fromtimestamp(timestamp)
                avg_speed = sum(speeds) // len(speeds)
                print(f"  {dt.strftime('%Y-%m-%d %H:%M:%S')}: {', '.join(map(str, speeds))} RPM (avg: {avg_speed} RPM)")
        else:
            print("  No fan speed data found")
        
        print("=" * 60)
        
    except Exception as e:
        print(f"Error reading log file: {e}")


def main():
    """Main function - runs once per execution."""
    parser = argparse.ArgumentParser(
        description='Dell R730 Fan Control - GPU Aware',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                    # Normal operation: check temps and adjust fans
  %(prog)s --temps            # Check temperatures only (read-only)
  %(prog)s --fans             # Check fan speeds only (read-only)
  %(prog)s --history          # Show last 50 temperature log entries
  %(prog)s --history 100      # Show last 100 temperature log entries
  %(prog)s --history-detailed # Show detailed history for last 24 hours
  %(prog)s --history-detailed 12  # Show detailed history for last 12 hours
        """
    )
    
    parser.add_argument('--temps', '--check-temps', action='store_true',
                        help='Check and display current temperatures (read-only)')
    parser.add_argument('--fans', '--check-fans', action='store_true',
                        help='Check and display current fan speeds (read-only)')
    parser.add_argument('--history', type=int, nargs='?', const=50, metavar='N',
                        help='Show temperature history from log (default: 50 entries)')
    parser.add_argument('--history-detailed', type=int, nargs='?', const=24, metavar='HOURS',
                        help='Show detailed temperature history (default: 24 hours)')
    
    args = parser.parse_args()
    
    # Handle different modes
    if args.temps:
        setup_logging(read_only=True)
        check_temperatures()
        return
    
    if args.fans:
        setup_logging(read_only=True)
        check_fan_speeds()
        return
    
    if args.history is not None:
        setup_logging(read_only=True)
        show_temperature_history(args.history)
        return
    
    if args.history_detailed is not None:
        setup_logging(read_only=True)
        show_detailed_history(args.history_detailed)
        return
    
    # Normal operation mode (default)
    setup_logging(read_only=False)
    logger.info("=" * 60)
    logger.info("Dell R730 Fan Control - GPU Aware - Starting check")
    logger.info(f"iDRAC IP: {IDRAC_IP}")
    
    # Get temperatures
    gpu_temps = get_gpu_temperatures()
    system_temps = get_system_temperatures()
    
    # Log temperature readings
    if gpu_temps:
        logger.info(f"GPU Temperatures: {', '.join(map(str, gpu_temps))}°C (max: {max(gpu_temps)}°C)")
    else:
        logger.info("GPU Temperatures: No GPUs detected or GPU monitoring tools unavailable")
    
    if system_temps:
        logger.info(f"System Temperatures: {', '.join(map(str, system_temps))}°C (max: {max(system_temps)}°C)")
    else:
        logger.warning("System Temperatures: Unable to read")
    
    # Determine action
    action, speed = determine_fan_action(gpu_temps, system_temps)
    
    # Execute action
    if action == 'auto':
        logger.info(f"Temperatures high (max: {max(max(gpu_temps) if gpu_temps else 0, max(system_temps) if system_temps else 0)}°C). Enabling automatic fan control.")
        enable_automatic_fan_mode()
    else:
        # Enable manual mode and set fan speed
        if enable_manual_fan_mode():
            set_fan_speed(speed)
            logger.info(f"Manual mode active. Fan speed set to {speed}%")
        else:
            logger.error("Failed to enable manual mode")
            sys.exit(1)
    
    # Get current fan speeds for logging
    fan_speeds = get_fan_speeds()
    if fan_speeds:
        logger.info(f"Current Fan Speeds: {', '.join(map(str, fan_speeds))}")
    
    logger.info("Check complete")
    logger.info("=" * 60)


if __name__ == '__main__':
    main()
