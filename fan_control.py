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
try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(dotenv_path=None):
        """Minimal stdlib .env loader fallback when python-dotenv is not installed."""
        path = dotenv_path or os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
        if not os.path.exists(path):
            return False
        parsed = {}
        try:
            with open(path, 'r') as f:
                for raw_line in f:
                    line = raw_line.strip()
                    if not line or line.startswith('#') or '=' not in line:
                        continue
                    key, val = line.split('=', 1)
                    key = key.strip()
                    val = val.strip().strip('"').strip("'")
                    if key:
                        parsed[key] = val
        except OSError:
            return False
        for k, v in parsed.items():
            os.environ.setdefault(k, v)
        return True

# Load environment variables
load_dotenv()

# Configuration from environment
IDRAC_IP = os.getenv('IDRAC_IP', '10.1.10.20')
IDRAC_USER = os.getenv('IDRAC_USER', 'root')
IDRAC_PASS = os.getenv('IDRAC_PASS', 'calvin')

# Temperature thresholds (in Celsius) - 7 levels for granular control
# GPU thresholds
GPU_TEMP_VERY_LOW = int(os.getenv('GPU_TEMP_VERY_LOW', '35'))
GPU_TEMP_LOW = int(os.getenv('GPU_TEMP_LOW', '45'))
GPU_TEMP_MED_LOW = int(os.getenv('GPU_TEMP_MED_LOW', '55'))
GPU_TEMP_MED = int(os.getenv('GPU_TEMP_MED', '65'))
GPU_TEMP_MED_HIGH = int(os.getenv('GPU_TEMP_MED_HIGH', '75'))
GPU_TEMP_HIGH = int(os.getenv('GPU_TEMP_HIGH', '85'))
GPU_TEMP_VERY_HIGH = int(os.getenv('GPU_TEMP_VERY_HIGH', '95'))

# System thresholds
SYSTEM_TEMP_VERY_LOW = int(os.getenv('SYSTEM_TEMP_VERY_LOW', '25'))
SYSTEM_TEMP_LOW = int(os.getenv('SYSTEM_TEMP_LOW', '35'))
SYSTEM_TEMP_MED_LOW = int(os.getenv('SYSTEM_TEMP_MED_LOW', '45'))
SYSTEM_TEMP_MED = int(os.getenv('SYSTEM_TEMP_MED', '55'))
SYSTEM_TEMP_MED_HIGH = int(os.getenv('SYSTEM_TEMP_MED_HIGH', '65'))
SYSTEM_TEMP_HIGH = int(os.getenv('SYSTEM_TEMP_HIGH', '75'))
SYSTEM_TEMP_VERY_HIGH = int(os.getenv('SYSTEM_TEMP_VERY_HIGH', '85'))

# Fan speed percentages (0-100%) - 7 levels matching temperature ranges
FAN_SPEED_VERY_LOW = int(os.getenv('FAN_SPEED_VERY_LOW', '20'))
FAN_SPEED_LOW = int(os.getenv('FAN_SPEED_LOW', '25'))
FAN_SPEED_MED_LOW = int(os.getenv('FAN_SPEED_MED_LOW', '35'))
FAN_SPEED_MED = int(os.getenv('FAN_SPEED_MED', '45'))
FAN_SPEED_MED_HIGH = int(os.getenv('FAN_SPEED_MED_HIGH', '60'))
FAN_SPEED_HIGH = int(os.getenv('FAN_SPEED_HIGH', '75'))
FAN_SPEED_VERY_HIGH = int(os.getenv('FAN_SPEED_VERY_HIGH', '90'))

# Temperature threshold for switching to automatic mode (let iDRAC handle it)
# If temps exceed this, disable manual mode and let iDRAC take over
# Default to VERY_HIGH threshold if not specified
AUTO_MODE_THRESHOLD = int(os.getenv('AUTO_MODE_THRESHOLD', str(max(GPU_TEMP_VERY_HIGH, SYSTEM_TEMP_VERY_HIGH))))

# IPMI timeout and retry settings (for slow ipmitool responses)
IPMI_TIMEOUT = int(os.getenv('IPMI_TIMEOUT', '20'))  # seconds
IPMI_RETRIES = int(os.getenv('IPMI_RETRIES', '2'))  # number of retries

# GPU Temperature Priority Override
# When enabled, GPU temperatures take priority over system temperatures
# If GPU temps are above GPU_TEMP_LOW, they will be used for fan control
GPU_TEMP_OVERRIDE = os.getenv('GPU_TEMP_OVERRIDE', 'true').lower() in ('true', '1', 'yes', 'on')

# Inlet/Exhaust temperature floor - when inlet or exhaust exceeds these, enforce minimum fan speed
# Helps protect NIC and other components in hot chassis environments
INLET_TEMP_FLOOR_THRESHOLD = int(os.getenv('INLET_TEMP_FLOOR_THRESHOLD', '40'))  # °C
EXHAUST_TEMP_FLOOR_THRESHOLD = int(os.getenv('EXHAUST_TEMP_FLOOR_THRESHOLD', '50'))  # °C
INLET_EXHAUST_FLOOR_FAN_SPEED = int(os.getenv('INLET_EXHAUST_FLOOR_FAN_SPEED', str(FAN_SPEED_MED_LOW)))  # min % when floor triggered

# NIC / HCA temperatures (plain ConnectX via mstflint's MTMP register, and any non-BlueField
# network adapter that exposes a hwmon sensor). Above the floor threshold the fans never go below
# the floor speed; above the auto threshold the iDRAC takes over.
NIC_TEMP_FLOOR_THRESHOLD = int(os.getenv('NIC_TEMP_FLOOR_THRESHOLD', '85'))  # °C
NIC_TEMP_FLOOR_FAN_SPEED = int(os.getenv('NIC_TEMP_FLOOR_FAN_SPEED', str(FAN_SPEED_MED)))  # %
NIC_TEMP_AUTO_THRESHOLD = int(os.getenv('NIC_TEMP_AUTO_THRESHOLD', '95'))  # °C

# NVIDIA BlueField DPU (BF2 / BF3) thresholds - 7-level thermal curve + automatic mode handoff
# Firmware warning threshold on BF2 is 95°C (critical 105°C); normal idle in R730 airflow is ~55-62°C.
BF_TEMP_VERY_LOW = int(os.getenv('BF_TEMP_VERY_LOW', '50'))
BF_TEMP_LOW = int(os.getenv('BF_TEMP_LOW', '60'))
BF_TEMP_MED_LOW = int(os.getenv('BF_TEMP_MED_LOW', '68'))
BF_TEMP_MED = int(os.getenv('BF_TEMP_MED', '75'))
BF_TEMP_MED_HIGH = int(os.getenv('BF_TEMP_MED_HIGH', '82'))
BF_TEMP_HIGH = int(os.getenv('BF_TEMP_HIGH', '88'))
BF_TEMP_VERY_HIGH = int(os.getenv('BF_TEMP_VERY_HIGH', '92'))
BF_TEMP_AUTO_THRESHOLD = int(os.getenv('BF_TEMP_AUTO_THRESHOLD', '95'))

PCI_DEVICES = '/sys/bus/pci/devices'
HWMON_PATH = '/sys/class/hwmon'
NVIDIA_VENDOR = '0x10de'
AMD_VENDOR = '0x1002'
INTEL_VENDOR = '0x8086'
MELLANOX_VENDOR = '0x15b3'
# Onboard server BMC 2D display controllers (Matrox G200eR2, ASPEED AST, QEMU Cirrus) - not GPUs
BMC_DISPLAY_VENDORS = ('0x102b', '0x1a03', '0x1013')
GPU_VENDOR_MAP = {
    NVIDIA_VENDOR: 'nvidia',
    AMD_VENDOR: 'amd',
    INTEL_VENDOR: 'intel',
}
# BlueField-1/2/3 integrated ConnectX network PFs and SoC management DMA interfaces
BLUEFIELD_PF_DEVICE_IDS = ('0xa2d0', '0xa2d2', '0xa2d3', '0xa2d6', '0xa2dc')
BLUEFIELD_SOC_DEVICE_IDS = ('0xc2d2', '0xc2d3', '0xc2d4', '0xc2d5')
BLUEFIELD_DEVICE_IDS = BLUEFIELD_PF_DEVICE_IDS + BLUEFIELD_SOC_DEVICE_IDS

TRUSTED_SYSTEM_HWMON_PREFIXES = (
    'coretemp', 'k10temp', 'zenpower', 'acpitz', 'pch_', 'dell_smm',
    'nct', 'it87', 'w83', 'jc42', 'drivetemp', 'ibmaem', 'ipmi',
)
GPU_SENSOR_CHIP_PREFIXES = {
    'amd': ('amdgpu', 'radeon'),
    'intel': ('i915', 'xe'),
    'nvidia': ('nouveau',),
}
_PCI_ADDR_RE = re.compile(r'^[0-9a-fA-F]{4}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}\.[0-7]$')
_HEX4_RE = re.compile(r'^0x[0-9a-fA-F]{4}$')
_HEX6_RE = re.compile(r'^0x[0-9a-fA-F]{6}$')

# Log file path
LOG_FILE = os.getenv('LOG_FILE', '/var/log/dell-r730-fan-control.log')

# Unified data log file for learning (temperatures + fan speeds together)
# Default to logs/ directory in script directory
default_data_log = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs', 'fan_control_data.log')
DATA_LOG_FILE = os.getenv('DATA_LOG_FILE', default_data_log)

# Setup logging (will be reconfigured in main() for read-only modes)
log_dir = os.path.dirname(LOG_FILE)
if log_dir and not os.path.exists(log_dir):
    try:
        os.makedirs(log_dir, exist_ok=True)
    except PermissionError:
        # Fallback to logs/ directory in script directory if can't write to /var/log
        logs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
        os.makedirs(logs_dir, exist_ok=True)
        LOG_FILE = os.path.join(logs_dir, 'fan_control.log')

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
            else:
                # Last attempt failed - preserve actual ipmitool error
                err_msg = result.stderr.strip() if result.stderr else result.stdout.strip() or f"Exit code {result.returncode}"
                return False, result.stdout, err_msg or 'Command failed after all retries'
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
    # Dell iDRAC expects decimal format, not hex (hex "0a" returns "Given data invalid")
    value_str = str(percentage)

    success, stdout, stderr = run_ipmi_command(['raw', '0x30', '0x30', '0x02', '0xff', value_str])
    if success:
        logger.debug(f"IPMI command successful: Fan speed set to {percentage}%")
        return True
    else:
        logger.error(f"Failed to set fan speed: {stderr}")
        return False


def _valid_temp_c(value):
    """Return True if value is a plausible sensor temperature in Celsius."""
    return 0 < value < 200


def _parse_sensors_blocks(stdout):
    """
    Parse `sensors` output into (chip_header, pci_bdf_hint, temps_c) blocks.
    Extracts only the current input reading (before any threshold parenthetical)
    with its sign preserved, rejecting non-positive or out-of-range values.
    """
    blocks = []
    for raw_block in re.split(r'\n\s*\n', stdout.strip()):
        lines = [ln.strip() for ln in raw_block.splitlines() if ln.strip()]
        if not lines:
            continue
        header = lines[0].lower()
        pci_match = re.search(r'-pci-([0-9a-f]{4,6})\b', header)
        pci_hint = pci_match.group(1) if pci_match else None
        temps = []
        for line in lines[1:]:
            if line.lower().startswith('adapter:') or ':' not in line:
                continue
            # Strip threshold info in parentheses so '(high = +93.0°C)' is never misread as input
            head = line.split('(', 1)[0]
            _, val_part = head.split(':', 1)
            match = re.search(r'([+\-]?\d+(?:\.\d+)?)\s*°C\b', val_part)
            if match:
                try:
                    temp_c = int(float(match.group(1)))
                    if _valid_temp_c(temp_c):
                        temps.append(temp_c)
                except ValueError:
                    continue
        blocks.append((header, pci_hint, temps))
    return blocks


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
                        val = int(line.strip())
                        if _valid_temp_c(val):
                            temps.append(val)
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
            for line in result.stdout.strip().split('\n'):
                if line.strip() and ',' in line:
                    parts = line.split(',')
                    if len(parts) >= 2:
                        try:
                            if 'temperature' in parts[1].lower():
                                continue
                            temp = int(float(parts[1].strip()))
                            if _valid_temp_c(temp):
                                temps.append(temp)
                        except (ValueError, IndexError):
                            pass
            return temps
        return []
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []
    except Exception:
        return []


def get_gpu_temperatures_sensors(vendors=('amd', 'intel'), inv=None):
    """Get GPU temperatures from sensors (lm-sensors) scoped to verified GPU chip blocks."""
    allowed_prefixes = []
    for v in vendors:
        allowed_prefixes.extend(GPU_SENSOR_CHIP_PREFIXES.get(v, ()))
    if not allowed_prefixes:
        return []

    expected_bus_dev = None
    if inv is not None and inv.get('available') and inv.get('complete'):
        expected_bus_dev = set()
        for dev in inv.get('devices', ()):
            if dev['is_vf'] or not dev['class'].startswith('0x03'):
                continue
            if GPU_VENDOR_MAP.get(dev['vendor']) in vendors:
                # 0000:bb:dd.f -> bbdd (4-hex lm-sensors suffix)
                parts = dev['slot'].split(':')
                if len(parts) == 3:
                    expected_bus_dev.add((parts[1] + parts[2]).lower())

    try:
        result = subprocess.run(
            ['sensors'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode != 0:
            return []
        temps = []
        for header, pci_hint, block_temps in _parse_sensors_blocks(result.stdout):
            if not any(header.startswith(p + '-') or header == p for p in allowed_prefixes):
                continue
            if expected_bus_dev is not None and pci_hint is not None:
                if pci_hint[-4:] not in expected_bus_dev:
                    continue
            temps.extend(block_temps)
        return temps
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
            for line in result.stdout.split('\n'):
                if 'temp' in line.lower() or 'temperature' in line.lower():
                    match = re.search(r'([+\-]?\d+)\s*°?C', line, re.IGNORECASE)
                    if match:
                        try:
                            temp = int(match.group(1))
                            if _valid_temp_c(temp):
                                temps.append(temp)
                        except ValueError:
                            pass
            return temps
        return []
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []
    except Exception:
        return []


def collect_gpu_telemetry(inv=None):
    """
    Collect GPU temperatures gated on PCI device discovery.
    Returns (gpu_temps, missing_gpu_vendors).
    - When PCI inventory confirms no discrete GPUs exist, skips all GPU tool subprocesses
      and returns ([], []).
    - When specific GPU vendors exist on PCI, queries only those vendors' tools and records
      any present vendor returning zero valid temperatures in missing_gpu_vendors.
    - When PCI inventory is unavailable/incomplete, falls back to probing tools while
      safety_override receives pci_inventory_ok=False.
    """
    if inv is None:
        inv = scan_pci_inventory()

    if pci_inventory_ok(inv):
        vendors = detected_gpu_vendors(inv)
        if not vendors:
            logger.debug("No discrete GPUs detected on PCI bus; skipping GPU temperature sensing")
            return [], []

        all_temps = []
        missing_vendors = []
        for vendor in vendors:
            v_temps = []
            if vendor == 'nvidia':
                v_temps = get_gpu_temperatures_nvidia()
            elif vendor == 'amd':
                v_temps = get_gpu_temperatures_amd()
                if not v_temps:
                    v_temps = get_gpu_temperatures_sensors(vendors=('amd',), inv=inv)
            elif vendor == 'intel':
                v_temps = get_gpu_temperatures_intel()
                if not v_temps:
                    v_temps = get_gpu_temperatures_sensors(vendors=('intel',), inv=inv)

            if v_temps:
                logger.debug(f"GPU temperatures obtained for {vendor}: {v_temps}")
                all_temps.extend(v_temps)
            else:
                missing_vendors.append(vendor)
        return all_temps, missing_vendors

    # Fallback when PCI sysfs is unavailable or inconclusive
    temps = get_gpu_temperatures_nvidia()
    if temps:
        return temps, []
    temps = get_gpu_temperatures_amd()
    if temps:
        return temps, []
    temps = get_gpu_temperatures_intel()
    if temps:
        return temps, []
    temps = get_gpu_temperatures_sensors(vendors=('amd', 'intel', 'nvidia'), inv=None)
    return temps, []


def get_gpu_temperatures(inv=None):
    """
    Get GPU temperatures from available GPU monitoring tools when GPUs are present on PCI.
    Skips probing entirely when PCI inventory confirms no discrete GPUs are installed.
    """
    temps, _missing = collect_gpu_telemetry(inv)
    return temps


def _read_sysfs_token(path):
    """Read and strip a single-line sysfs attribute, or return None on OSError."""
    try:
        with open(path, 'r') as f:
            return f.read().strip()
    except OSError:
        return None


def _resolve_hwmon_device_identity(hwmon_entry_path):
    """
    Resolve a /sys/class/hwmon/hwmonX entry to its backing PCI physical function (if any)
    and hwmon chip name. Supports both real sysfs symlink trees and direct test fixtures.
    Returns dict with keys: name, pci_addr, pci_slot, vendor, class, device, is_vf.
    """
    chip_name = (_read_sysfs_token(os.path.join(hwmon_entry_path, 'name')) or '').lower()
    dev_path = os.path.join(hwmon_entry_path, 'device')
    info = {
        'name': chip_name,
        'pci_addr': None,
        'pci_slot': None,
        'vendor': None,
        'class': None,
        'device': None,
        'is_vf': False,
    }
    if not os.path.exists(dev_path):
        return info

    # Direct attributes on hwmonX/device (covers PCI endpoint symlinks and test fixtures)
    ven = _read_sysfs_token(os.path.join(dev_path, 'vendor'))
    cls = _read_sysfs_token(os.path.join(dev_path, 'class'))
    dev_id = _read_sysfs_token(os.path.join(dev_path, 'device'))
    if ven:
        info['vendor'] = ven.lower()
    if cls:
        info['class'] = cls.lower()
    if dev_id:
        info['device'] = dev_id.lower()

    # Walk resolved device path ancestry to locate nearest PCI endpoint (DDDD:BB:SS.F)
    real_dev = os.path.realpath(dev_path)
    cur = real_dev
    while cur and cur not in ('/', ''):
        base = os.path.basename(cur)
        if _PCI_ADDR_RE.match(base):
            physfn_link = os.path.join(cur, 'physfn')
            if os.path.exists(physfn_link):
                info['is_vf'] = True
                pf_real = os.path.realpath(physfn_link)
                pf_base = os.path.basename(pf_real)
                if _PCI_ADDR_RE.match(pf_base):
                    cur = pf_real
                    base = pf_base
            info['pci_addr'] = base.lower()
            info['pci_slot'] = base.lower().rsplit('.', 1)[0]
            if not info['vendor']:
                v = _read_sysfs_token(os.path.join(cur, 'vendor'))
                if v:
                    info['vendor'] = v.lower()
            if not info['class']:
                c = _read_sysfs_token(os.path.join(cur, 'class'))
                if c:
                    info['class'] = c.lower()
            if not info['device']:
                d = _read_sysfs_token(os.path.join(cur, 'device'))
                if d:
                    info['device'] = d.lower()
            break
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent

    return info


def _read_hwmon_temps(hwmon_entry_path):
    """Read valid Celsius integer temperatures from temp*_input files under hwmon_entry_path."""
    temps = []
    try:
        files = sorted(os.listdir(hwmon_entry_path))
    except OSError:
        return temps
    for name in files:
        if name.startswith('temp') and name.endswith('_input'):
            raw = _read_sysfs_token(os.path.join(hwmon_entry_path, name))
            if raw is None:
                continue
            try:
                temp_c = int(raw) // 1000
                if _valid_temp_c(temp_c):
                    temps.append(temp_c)
            except ValueError:
                continue
    return temps


def _classify_hwmon_entry(hwmon_entry_path, bf_slot_set):
    """
    Classify a hwmon directory as 'bf', 'nic', 'gpu', 'bmc_vga', 'system', or 'unknown'.
    PCI GPU/NIC/BlueField devices are isolated from 'system', and 'system' requires a
    trusted CPU/chassis/board hwmon driver name.
    """
    ident = _resolve_hwmon_device_identity(hwmon_entry_path)
    slot = ident['pci_slot']
    cls = ident['class'] or ''
    ven = ident['vendor'] or ''
    dev_id = ident['device'] or ''
    chip = ident['name']

    if (slot and slot in bf_slot_set) or (ven == MELLANOX_VENDOR and dev_id in BLUEFIELD_DEVICE_IDS):
        return 'bf', ident
    if cls.startswith('0x02'):
        return 'nic', ident
    if cls.startswith('0x03'):
        if ven in BMC_DISPLAY_VENDORS:
            return 'bmc_vga', ident
        return 'gpu', ident
    if any(chip.startswith(prefix) for prefix in TRUSTED_SYSTEM_HWMON_PREFIXES):
        return 'system', ident
    return 'unknown', ident


def get_system_temperatures_sysfs(inv=None):
    """Get trusted CPU/chassis system temperatures from /sys/class/hwmon (excluding GPU/NIC/BF)."""
    temps = []
    if not os.path.exists(HWMON_PATH):
        return []
    bf_slot_set = set(bluefield_cards(inv).keys())
    try:
        entries = sorted(os.listdir(HWMON_PATH))
    except (OSError, PermissionError):
        return []

    for hwmon_dir in entries:
        hwmon_full_path = os.path.join(HWMON_PATH, hwmon_dir)
        if not os.path.isdir(hwmon_full_path):
            continue
        kind, _ident = _classify_hwmon_entry(hwmon_full_path, bf_slot_set)
        if kind != 'system':
            continue
        temps.extend(_read_hwmon_temps(hwmon_full_path))

    return temps


def get_system_temperatures_sensors():
    """Get trusted CPU/chassis system temperatures from sensors command (lm-sensors)."""
    temps = []
    try:
        result = subprocess.run(
            ['sensors'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            for header, _pci_hint, block_temps in _parse_sensors_blocks(result.stdout):
                if any(header.startswith(prefix) for prefix in TRUSTED_SYSTEM_HWMON_PREFIXES):
                    temps.extend(block_temps)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    except Exception:
        pass

    return temps


def get_inlet_exhaust_temps():
    """
    Get Inlet and Exhaust temperatures from iDRAC via IPMI.
    Uses `sdr type Temperature` (much faster than full `sensor list`) and supports both formats.
    Returns: dict with 'inlet', 'exhaust', 'differential' (exhaust - inlet), or empty dict on failure.
    """
    success, stdout, stderr = run_ipmi_command(['sdr', 'type', 'Temperature'])
    if not success:
        return {}
    result = {}
    for line in stdout.split('\n'):
        if 'Inlet Temp' in line:
            match = re.search(r'\|\s*([+\-]?\d+(?:\.\d+)?)\s*(?:\|\s*)?degrees\s*C', line, re.IGNORECASE)
            if match:
                try:
                    val = int(float(match.group(1)))
                    if -20 < val < 150:
                        result['inlet'] = val
                except (ValueError, TypeError):
                    pass
        elif 'Exhaust Temp' in line:
            match = re.search(r'\|\s*([+\-]?\d+(?:\.\d+)?)\s*(?:\|\s*)?degrees\s*C', line, re.IGNORECASE)
            if match:
                try:
                    val = int(float(match.group(1)))
                    if -20 < val < 150:
                        result['exhaust'] = val
                except (ValueError, TypeError):
                    pass
    if 'inlet' in result and 'exhaust' in result:
        result['differential'] = result['exhaust'] - result['inlet']
    return result


def get_system_temperatures(inv=None):
    """
    Get system temperatures from multiple sources.
    Tries faster methods first (sysfs, sensors), then falls back to ipmitool.
    """
    temps = get_system_temperatures_sysfs(inv=inv)
    if temps:
        logger.debug("System temperatures obtained via sysfs")
        return temps

    temps = get_system_temperatures_sensors()
    if temps:
        logger.debug("System temperatures obtained via sensors command")
        return temps

    # Fall back to ipmitool (targeted Temperature SDR query)
    logger.debug("Falling back to ipmitool for system temperatures")
    success, stdout, stderr = run_ipmi_command(['sdr', 'type', 'Temperature'])
    if not success:
        return []

    temps = []
    for line in stdout.split('\n'):
        if 'Temp' in line or 'temperature' in line.lower():
            if 'Inlet Temp' in line or 'Exhaust Temp' in line:
                continue
            match = re.search(r'([+\-]?\d+(?:\.\d+)?)\s*degrees\s*C', line, re.IGNORECASE)
            if match:
                try:
                    temp = int(float(match.group(1)))
                    if _valid_temp_c(temp):
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


def log_unified_data(gpu_temps, system_temps, fan_speeds, fan_speed_pct, inlet_exhaust=None):
    """
    Log unified data (temperatures + fan speeds) for learning/analysis.
    Format: timestamp|max_gpu_temp|max_system_temp|avg_fan_rpm|fan_speed_pct|gpu_temps_csv|system_temps_csv|fan_speeds_csv|inlet|exhaust|differential
    """
    try:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        max_gpu = max(gpu_temps) if gpu_temps else 0
        max_system = max(system_temps) if system_temps else 0
        avg_fan_rpm = int(sum(fan_speeds) / len(fan_speeds)) if fan_speeds else 0
        fan_pct = fan_speed_pct if fan_speed_pct is not None else 0

        gpu_csv = ','.join(map(str, gpu_temps)) if gpu_temps else ''
        system_csv = ','.join(map(str, system_temps)) if system_temps else ''
        fan_csv = ','.join(map(str, fan_speeds)) if fan_speeds else ''

        inlet = inlet_exhaust.get('inlet', '') if inlet_exhaust else ''
        exhaust = inlet_exhaust.get('exhaust', '') if inlet_exhaust else ''
        diff = inlet_exhaust.get('differential', '') if inlet_exhaust else ''

        log_entry = f"{timestamp}|{max_gpu}|{max_system}|{avg_fan_rpm}|{fan_pct}|{gpu_csv}|{system_csv}|{fan_csv}|{inlet}|{exhaust}|{diff}\n"

        # Ensure log directory exists
        log_dir = os.path.dirname(DATA_LOG_FILE)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)

        # Append to unified data log
        with open(DATA_LOG_FILE, 'a') as f:
            f.write(log_entry)

    except Exception as e:
        logger.debug(f"Failed to write unified data log: {e}")


def get_fan_speeds():
    """
    Get current fan speeds from multiple sources.
    Tries faster methods first (sysfs, sensors), then falls back to ipmitool.
    """
    speeds = get_fan_speeds_sysfs()
    if speeds:
        logger.debug("Fan speeds obtained via sysfs")
        return speeds

    speeds = get_fan_speeds_sensors()
    if speeds:
        logger.debug("Fan speeds obtained via sensors command")
        return speeds

    # Fall back to ipmitool (targeted Fan SDR query)
    logger.debug("Falling back to ipmitool for fan speeds")
    success, stdout, stderr = run_ipmi_command(['sdr', 'type', 'Fan'])
    if not success:
        return []

    speeds = []
    for line in stdout.split('\n'):
        if 'Fan' in line and 'Redundancy' not in line:
            match = re.search(r'(\d+)\s*(?:RPM|%)', line, re.IGNORECASE)
            if match:
                try:
                    speed = int(match.group(1))
                    if speed > 0:
                        speeds.append(speed)
                except ValueError:
                    pass

    if speeds:
        logger.debug("Fan speeds obtained via ipmitool")

    return speeds


def scan_pci_inventory():
    """
    Scan /sys/bus/pci/devices and return structured PCI inventory:
      available: True if PCI_DEVICES directory was listed successfully
      complete: True if every enumerated device had valid BDF, vendor, class (and device if present)
      devices: list of dicts {addr, slot, vendor, class, device, is_vf}
      unknown_display: list of non-VF 0x03* PCI addresses with unrecognized display vendors
    """
    inv = {
        'available': False,
        'complete': False,
        'devices': [],
        'unknown_display': [],
    }
    try:
        names = sorted(os.listdir(PCI_DEVICES))
    except OSError:
        return inv

    inv['available'] = True
    complete = True
    for addr in names:
        if not _PCI_ADDR_RE.match(addr):
            complete = False
            continue
        dev_dir = os.path.join(PCI_DEVICES, addr)
        ven = _read_sysfs_token(os.path.join(dev_dir, 'vendor'))
        cls = _read_sysfs_token(os.path.join(dev_dir, 'class'))
        if not ven or not cls or not _HEX4_RE.match(ven) or not _HEX6_RE.match(cls):
            complete = False
            continue
        ven = ven.lower()
        cls = cls.lower()

        dev_file = os.path.join(dev_dir, 'device')
        dev_id = None
        if os.path.exists(dev_file):
            raw_dev = _read_sysfs_token(dev_file)
            if not raw_dev or not _HEX4_RE.match(raw_dev):
                complete = False
                continue
            dev_id = raw_dev.lower()

        is_vf = os.path.exists(os.path.join(dev_dir, 'physfn'))
        addr_norm = addr.lower()
        entry = {
            'addr': addr_norm,
            'slot': addr_norm.rsplit('.', 1)[0],
            'vendor': ven,
            'class': cls,
            'device': dev_id,
            'is_vf': is_vf,
        }
        inv['devices'].append(entry)
        if not is_vf and cls.startswith('0x03'):
            if ven not in GPU_VENDOR_MAP and ven not in BMC_DISPLAY_VENDORS:
                inv['unknown_display'].append(addr_norm)

    inv['complete'] = complete
    return inv


def pci_inventory_ok(inv):
    """True when PCI inventory is completely enumerated with no unrecognized display hardware."""
    return bool(inv and inv.get('available') and inv.get('complete') and not inv.get('unknown_display'))


def _pci_devices(vendor=None, class_prefixes=()):
    """(address, vendor, class) for physical PCI devices from sysfs, optionally filtered."""
    out = []
    try:
        names = sorted(os.listdir(PCI_DEVICES))
    except OSError:
        return out
    vendor_norm = vendor.lower() if vendor else None
    prefixes_norm = tuple(p.lower() for p in class_prefixes)
    for addr in names:
        dev_dir = os.path.join(PCI_DEVICES, addr)
        if os.path.exists(os.path.join(dev_dir, 'physfn')):
            continue
        try:
            with open(os.path.join(dev_dir, 'vendor')) as f:
                ven = f.read().strip().lower()
            with open(os.path.join(dev_dir, 'class')) as f:
                cls = f.read().strip().lower()
        except OSError:
            continue
        if vendor_norm and ven != vendor_norm:
            continue
        if prefixes_norm and not any(cls.startswith(c) for c in prefixes_norm):
            continue
        out.append((addr, ven, cls))
    return out


def detected_gpu_vendors(inv=None):
    """Sorted list of discrete GPU vendor keys ('nvidia', 'amd', 'intel') present on PCI."""
    if inv is None:
        inv = scan_pci_inventory()
    found = set()
    for dev in inv.get('devices', ()):
        if dev['is_vf'] or not dev['class'].startswith('0x03'):
            continue
        v_name = GPU_VENDOR_MAP.get(dev['vendor'])
        if v_name:
            found.add(v_name)
    return sorted(found)


def nvidia_gpus_present():
    """True if an NVIDIA display/3D controller (PCI class 0x03xxxx) is in the box."""
    return 'nvidia' in detected_gpu_vendors()


def amd_gpus_present():
    """True if an AMD display/3D controller (PCI class 0x03xxxx) is in the box."""
    return 'amd' in detected_gpu_vendors()


def intel_gpus_present():
    """True if an Intel display/3D controller (PCI class 0x03xxxx) is in the box."""
    return 'intel' in detected_gpu_vendors()


def gpus_present(inv=None):
    """True if any supported discrete GPU (NVIDIA, AMD, Intel) is present on PCI."""
    return bool(detected_gpu_vendors(inv))


def bluefield_cards(inv=None):
    """
    Return dict mapping physical PCI slot (DDDD:BB:SS) -> list of PF dicts for detected
    NVIDIA/Mellanox BlueField DPU cards.
    Requires explicit BlueField PF device IDs (e.g. 0xa2d6 for BF2) or corroborated
    Mellanox network PF + BlueField SoC management DMA interface on the same physical card.
    """
    if inv is None:
        inv = scan_pci_inventory()
    by_slot = defaultdict(list)
    for dev in inv.get('devices', ()):
        if dev['is_vf'] or dev['vendor'] != MELLANOX_VENDOR:
            continue
        by_slot[dev['slot']].append(dev)

    bf_map = {}
    for slot in sorted(by_slot.keys()):
        funcs = sorted(by_slot[slot], key=lambda d: d['addr'])
        has_bf_pf = any(d['device'] in BLUEFIELD_PF_DEVICE_IDS for d in funcs)
        has_net_pf = any(d['class'].startswith('0x02') for d in funcs)
        has_bf_soc = any(d['device'] in BLUEFIELD_SOC_DEVICE_IDS for d in funcs)
        if has_bf_pf or (has_net_pf and has_bf_soc):
            bf_map[slot] = funcs
    return bf_map


def bluefield_present(inv=None):
    """True if at least one BlueField DPU card is present on PCI."""
    return bool(bluefield_cards(inv))


def _read_mlx_mtmp(pci_addr):
    """
    Read ASIC temperature (°C) via mstflint's MTMP register (units of 0.125 °C) for pci_addr.
    Returns int Celsius on valid read, or None on missing tool, error, timeout, or invalid value.
    """
    try:
        result = subprocess.run(
            ['mstreg', '-d', pci_addr, '--reg_name', 'MTMP', '--get', '--indexes', 'sensor_index=0x0'],
            capture_output=True,
            text=True,
            timeout=IPMI_TIMEOUT,
        )
    except (FileNotFoundError, PermissionError, subprocess.TimeoutExpired, OSError):
        return None
    if result.returncode != 0:
        return None
    match = re.search(r'^temperature\s*\|\s*(0x[0-9a-fA-F]+)', result.stdout, re.M)
    if not match:
        return None
    raw = int(match.group(1), 16)
    # MTMP temperature is signed 16-bit in 1/8 °C units
    if raw >= 0x8000:
        return None
    temp_c = raw // 8
    return temp_c if _valid_temp_c(temp_c) else None


def collect_bf_telemetry(inv=None):
    """
    Collect per-card BlueField DPU temperatures.
    Returns (bf_temps, missing_bf_slots):
      - One max temperature reading per detected physical BlueField card (preserving hotter
        optical/module sensors while collapsing duplicate dual-port ASIC readings on one card,
        and preserving distinct cards even at equal temperatures).
      - Falls back to read-only mstreg MTMP across present network PFs of any BlueField card
        whose hwmon sensors are absent or yielded no valid readings.
      - Any detected BlueField card with neither valid hwmon nor valid MTMP telemetry is listed
        in missing_bf_slots so safety_override hands fan control to iDRAC.
    """
    if inv is None:
        inv = scan_pci_inventory()
    cards = bluefield_cards(inv)
    if not cards:
        return [], []

    bf_slot_set = set(cards.keys())
    hwmon_by_slot = defaultdict(list)
    if os.path.exists(HWMON_PATH):
        try:
            entries = sorted(os.listdir(HWMON_PATH))
        except OSError:
            entries = []
        for entry in entries:
            entry_path = os.path.join(HWMON_PATH, entry)
            if not os.path.isdir(entry_path):
                continue
            kind, ident = _classify_hwmon_entry(entry_path, bf_slot_set)
            if kind == 'bf' and ident['pci_slot'] in bf_slot_set:
                hwmon_by_slot[ident['pci_slot']].extend(_read_hwmon_temps(entry_path))

    bf_temps = []
    missing_slots = []
    for slot, funcs in cards.items():
        readings = list(hwmon_by_slot.get(slot, []))
        if not readings:
            # Try present network PFs first (0x02*), then any remaining non-SoC PF if needed
            net_pfs = [f for f in funcs if f['class'].startswith('0x02')]
            for pf in net_pfs:
                mtmp_temp = _read_mlx_mtmp(pf['addr'])
                if mtmp_temp is not None:
                    readings.append(mtmp_temp)
                    break
        if readings:
            bf_temps.append(max(readings))
        else:
            missing_slots.append(slot)

    return bf_temps, missing_slots


def get_bf_temperatures(inv=None):
    """Return list of per-card BlueField DPU temperatures in Celsius."""
    temps, _missing = collect_bf_telemetry(inv)
    return temps


def _collect_plain_nic_hwmon_by_card(inv=None):
    """Map plain-NIC card key -> list of valid hwmon temperatures (excluding BlueField cards)."""
    by_card = defaultdict(list)
    if not os.path.exists(HWMON_PATH):
        return by_card
    bf_slot_set = set(bluefield_cards(inv).keys())
    try:
        entries = sorted(os.listdir(HWMON_PATH))
    except OSError:
        return by_card
    for entry in entries:
        entry_path = os.path.join(HWMON_PATH, entry)
        if not os.path.isdir(entry_path):
            continue
        kind, ident = _classify_hwmon_entry(entry_path, bf_slot_set)
        if kind != 'nic':
            continue
        card_key = ident['pci_slot'] or f"hwmon:{entry}"
        vals = _read_hwmon_temps(entry_path)
        if vals:
            by_card[card_key].extend(vals)
    return by_card


def _collect_plain_nic_mlx_by_card(inv=None):
    """Map plain Mellanox NIC slot -> MTMP temperature (excluding BlueField cards)."""
    if inv is None:
        inv = scan_pci_inventory()
    bf_slot_set = set(bluefield_cards(inv).keys())
    by_slot = defaultdict(list)
    for dev in inv.get('devices', ()):
        if dev['is_vf'] or dev['vendor'] != MELLANOX_VENDOR or not dev['class'].startswith('0x02'):
            continue
        if dev['slot'] in bf_slot_set:
            continue
        by_slot[dev['slot']].append(dev['addr'])

    mlx_temps = {}
    for slot in sorted(by_slot.keys()):
        for addr in sorted(by_slot[slot]):
            temp_c = _read_mlx_mtmp(addr)
            if temp_c is not None:
                mlx_temps[slot] = temp_c
                break
    return mlx_temps


def get_nic_temperatures_hwmon(inv=None):
    """Temperatures of non-BlueField network adapters (PCI class 0x02xxxx) via hwmon (one max per card)."""
    by_card = _collect_plain_nic_hwmon_by_card(inv)
    return [max(by_card[k]) for k in sorted(by_card.keys())]


def get_nic_temperatures_mlx(inv=None):
    """Plain ConnectX temperatures via mstflint's MTMP register (one reading per non-BlueField card)."""
    mlx_by_card = _collect_plain_nic_mlx_by_card(inv)
    return [mlx_by_card[k] for k in sorted(mlx_by_card.keys())]


def get_nic_temperatures(inv=None):
    """
    Temperatures of plain (non-BlueField) network adapters, combining hwmon and MTMP per physical
    card and retaining the hottest valid reading per card while preserving distinct cards.
    """
    if inv is None:
        inv = scan_pci_inventory()
    combined = defaultdict(list)
    for card_key, vals in _collect_plain_nic_hwmon_by_card(inv).items():
        combined[card_key].extend(vals)
    for slot, val in _collect_plain_nic_mlx_by_card(inv).items():
        combined[slot].append(val)
    return [max(combined[k]) for k in sorted(combined.keys())]


def safety_override(
    gpu_temps,
    system_temps,
    nic_temps,
    gpus_present,
    bf_temps=None,
    bf_present=False,
    missing_gpu_vendors=None,
    missing_bf_slots=None,
    pci_inventory_ok=True,
):
    """Hand the fans to the iDRAC whenever PCI discovery is inconclusive, a reading the decision
    depends on is missing, or a BlueField/NIC card exceeds its auto threshold.
    Returns a reason string, or None when manual control is safe."""
    if not pci_inventory_ok:
        return "PCI device inventory unavailable or incomplete - iDRAC takes over"
    if gpus_present and (not gpu_temps or missing_gpu_vendors):
        if missing_gpu_vendors:
            vendors_str = ', '.join(missing_gpu_vendors)
            return f"GPUs present ({vendors_str}) but GPU temperature unreadable (driver missing?) - iDRAC takes over"
        return "GPUs present but no GPU temperature readable (driver missing?) - iDRAC takes over"
    if missing_bf_slots:
        slots_str = ', '.join(missing_bf_slots)
        return f"BlueField DPU present ({slots_str}) but temperature unreadable - iDRAC takes over"
    if bf_present and not bf_temps:
        return "BlueField DPU present but no temperature readable - iDRAC takes over"
    if not system_temps:
        return "System temperatures unreadable - iDRAC takes over"
    if bf_temps and max(bf_temps) >= BF_TEMP_AUTO_THRESHOLD:
        return (f"BlueField temperature {max(bf_temps)}°C >= auto threshold"
                f" ({BF_TEMP_AUTO_THRESHOLD}°C) - iDRAC takes over")
    if nic_temps and max(nic_temps) >= NIC_TEMP_AUTO_THRESHOLD:
        return f"NIC temperature {max(nic_temps)}°C >= auto threshold ({NIC_TEMP_AUTO_THRESHOLD}°C) - iDRAC takes over"
    return None


def _evaluate_temp_curve(temp, thresholds):
    """
    Evaluate temp against 7 ascending thresholds (very_low..very_high).
    Returns (level_idx 0..7, fan_speed_pct, level_label, matched_threshold).
    """
    very_low, low, med_low, med, med_high, high, very_high = thresholds
    levels = (
        (7, FAN_SPEED_VERY_HIGH, 'VERY-HIGH', very_high),
        (6, FAN_SPEED_HIGH, 'HIGH', high),
        (5, FAN_SPEED_MED_HIGH, 'MEDIUM-HIGH', med_high),
        (4, FAN_SPEED_MED, 'MEDIUM', med),
        (3, FAN_SPEED_MED_LOW, 'MEDIUM-LOW', med_low),
        (2, FAN_SPEED_LOW, 'LOW', low),
        (1, FAN_SPEED_VERY_LOW, 'VERY-LOW', very_low),
    )
    for idx, speed, label, thresh in levels:
        if temp >= thresh:
            return idx, speed, label, thresh
    return 0, FAN_SPEED_VERY_LOW, 'BELOW-VERY-LOW', very_low


def determine_fan_action(gpu_temps, system_temps, bf_temps=None):
    """
    Determine what action to take based on active temperature domains (GPU, System, BlueField).
    Returns: (action, speed, reason)
    - action: 'manual' or 'auto'
    - speed: fan speed percentage (only used if action is 'manual')
    - reason: String explaining why this action was chosen

    Uses 7 temperature levels per domain and chooses the highest required cooling demand so a
    cooler domain (including GPU_TEMP_OVERRIDE) can never starve a hotter CPU or BlueField card.
    """
    bf_temps = bf_temps or []
    max_gpu_temp = max(gpu_temps) if gpu_temps else None
    max_system_temp = max(system_temps) if system_temps else None
    max_bf_temp = max(bf_temps) if bf_temps else None

    # Automatic mode handoff checks
    if (max_gpu_temp is not None and max_gpu_temp >= AUTO_MODE_THRESHOLD) or (
        max_system_temp is not None and max_system_temp >= AUTO_MODE_THRESHOLD
    ):
        gpu_desc = f"{max_gpu_temp}°C" if max_gpu_temp is not None else "N/A"
        sys_desc = f"{max_system_temp}°C" if max_system_temp is not None else "N/A"
        reason = (f"Temperature exceeds auto mode threshold ({AUTO_MODE_THRESHOLD}°C):"
                  f" GPU={gpu_desc}, System={sys_desc}")
        return ('auto', None, reason)

    if max_bf_temp is not None and max_bf_temp >= BF_TEMP_AUTO_THRESHOLD:
        reason = (f"BlueField temperature {max_bf_temp}°C >= auto mode threshold"
                  f" ({BF_TEMP_AUTO_THRESHOLD}°C)")
        return ('auto', None, reason)

    gpu_thresholds = (
        GPU_TEMP_VERY_LOW, GPU_TEMP_LOW, GPU_TEMP_MED_LOW, GPU_TEMP_MED,
        GPU_TEMP_MED_HIGH, GPU_TEMP_HIGH, GPU_TEMP_VERY_HIGH,
    )
    system_thresholds = (
        SYSTEM_TEMP_VERY_LOW, SYSTEM_TEMP_LOW, SYSTEM_TEMP_MED_LOW, SYSTEM_TEMP_MED,
        SYSTEM_TEMP_MED_HIGH, SYSTEM_TEMP_HIGH, SYSTEM_TEMP_VERY_HIGH,
    )
    bf_thresholds = (
        BF_TEMP_VERY_LOW, BF_TEMP_LOW, BF_TEMP_MED_LOW, BF_TEMP_MED,
        BF_TEMP_MED_HIGH, BF_TEMP_HIGH, BF_TEMP_VERY_HIGH,
    )

    candidates = []
    gpu_override_active = bool(GPU_TEMP_OVERRIDE and max_gpu_temp is not None and max_gpu_temp >= GPU_TEMP_LOW)

    if max_gpu_temp is not None:
        idx, speed, label, thresh = _evaluate_temp_curve(max_gpu_temp, gpu_thresholds)
        suffix = " - GPU override active" if gpu_override_active else ""
        if idx > 0:
            reason = f"GPU temperature {max_gpu_temp}°C >= {label} threshold ({thresh}°C){suffix}"
        else:
            reason = f"GPU temperature {max_gpu_temp}°C < VERY-LOW threshold ({thresh}°C){suffix}"
        # Priority tie-breaker: GPU (3 when override active, else 2), BlueField (1), System (0)
        prio = 3 if gpu_override_active else 2
        candidates.append((speed, idx, prio, reason))

    if max_bf_temp is not None:
        idx, speed, label, thresh = _evaluate_temp_curve(max_bf_temp, bf_thresholds)
        if idx > 0:
            reason = f"BlueField temperature {max_bf_temp}°C >= {label} threshold ({thresh}°C)"
        else:
            reason = f"BlueField temperature {max_bf_temp}°C < VERY-LOW threshold ({thresh}°C)"
        candidates.append((speed, idx, 1, reason))

    if max_system_temp is not None:
        idx, speed, label, thresh = _evaluate_temp_curve(max_system_temp, system_thresholds)
        if idx > 0:
            reason = f"System temperature {max_system_temp}°C >= {label} threshold ({thresh}°C)"
        else:
            reason = f"System temperature {max_system_temp}°C < VERY-LOW threshold ({thresh}°C)"
        candidates.append((speed, idx, 0, reason))

    if not candidates:
        return ('manual', FAN_SPEED_VERY_LOW, "Temperatures below all thresholds")

    best_speed, best_idx, _prio, best_reason = max(candidates, key=lambda c: (c[0], c[1], c[2]))
    if best_idx == 0:
        parts = []
        if max_gpu_temp is not None:
            parts.append(f"GPU: {max_gpu_temp}°C")
        if max_bf_temp is not None:
            parts.append(f"BlueField: {max_bf_temp}°C")
        if max_system_temp is not None:
            parts.append(f"System: {max_system_temp}°C")
        best_reason = f"Temperatures below all thresholds ({', '.join(parts)})"

    return ('manual', best_speed, best_reason)


def check_temperatures():
    """Check and display current temperatures (read-only)."""
    print("=" * 60)
    print("Temperature Check")
    print("=" * 60)
    print(f"iDRAC IP: {IDRAC_IP}")
    print()

    inv = scan_pci_inventory()
    has_gpus = gpus_present(inv)
    has_bf = bluefield_present(inv)

    gpu_temps, missing_gpu = collect_gpu_telemetry(inv)
    bf_temps, missing_bf = collect_bf_telemetry(inv)
    nic_temps = get_nic_temperatures(inv)
    system_temps = get_system_temperatures(inv=inv)
    inlet_exhaust = get_inlet_exhaust_temps()

    # Display inlet/exhaust
    if inlet_exhaust:
        print("Inlet/Exhaust Temperatures:")
        print(f"  Inlet: {inlet_exhaust.get('inlet', 'N/A')}°C")
        print(f"  Exhaust: {inlet_exhaust.get('exhaust', 'N/A')}°C")
        print(f"  Differential (exhaust - inlet): {inlet_exhaust.get('differential', 'N/A')}°C")
    else:
        print("Inlet/Exhaust: Unable to read (requires IPMI)")
    print()

    # Display GPU temperatures
    if not has_gpus and pci_inventory_ok(inv):
        print("GPU Temperatures: No GPUs detected on PCI bus (skipped)")
    elif gpu_temps:
        print("GPU Temperatures:")
        for i, temp in enumerate(gpu_temps):
            print(f"  GPU {i}: {temp}°C")
        print(f"  Max GPU: {max(gpu_temps)}°C")
        if missing_gpu:
            print(f"  WARNING: Unreadable GPU vendor(s): {', '.join(missing_gpu)}")
    else:
        print("GPU Temperatures: GPUs detected but temperatures unreadable")
    print()

    # Display BlueField temperatures if present
    if has_bf or bf_temps:
        if bf_temps:
            print("BlueField DPU Temperatures:")
            for i, temp in enumerate(bf_temps):
                print(f"  BlueField {i}: {temp}°C")
            print(f"  Max BlueField: {max(bf_temps)}°C")
        else:
            print("BlueField DPU Temperatures: Detected on PCI bus but unreadable!")
        if missing_bf:
            print(f"  WARNING: Unreadable BlueField slot(s): {', '.join(missing_bf)}")
        print()

    # Display plain NIC temperatures if present
    if nic_temps:
        print("NIC Temperatures:")
        for i, temp in enumerate(nic_temps):
            print(f"  NIC {i}: {temp}°C")
        print(f"  Max NIC: {max(nic_temps)}°C")
        print()

    # Display system temperatures
    if system_temps:
        print("System Temperatures:")
        for i, temp in enumerate(system_temps):
            print(f"  Sensor {i}: {temp}°C")
        print(f"  Max System: {max(system_temps)}°C")
    else:
        print("System Temperatures: Unable to read")
    print()

    # Show thresholds
    active_maxes = [
        max(t) for t in (gpu_temps, bf_temps, nic_temps, system_temps) if t
    ]
    max_temp = max(active_maxes) if active_maxes else 0
    print(f"Current Max Temperature: {max_temp}°C")
    print()
    print("Temperature Thresholds (7 levels — GPU / System / BlueField):")
    print(f"  Very-Low:    {GPU_TEMP_VERY_LOW}°C / {SYSTEM_TEMP_VERY_LOW}°C / {BF_TEMP_VERY_LOW}°C")
    print(f"  Low:         {GPU_TEMP_LOW}°C / {SYSTEM_TEMP_LOW}°C / {BF_TEMP_LOW}°C")
    print(f"  Medium-Low:  {GPU_TEMP_MED_LOW}°C / {SYSTEM_TEMP_MED_LOW}°C / {BF_TEMP_MED_LOW}°C")
    print(f"  Medium:      {GPU_TEMP_MED}°C / {SYSTEM_TEMP_MED}°C / {BF_TEMP_MED}°C")
    print(f"  Medium-High: {GPU_TEMP_MED_HIGH}°C / {SYSTEM_TEMP_MED_HIGH}°C / {BF_TEMP_MED_HIGH}°C")
    print(f"  High:        {GPU_TEMP_HIGH}°C / {SYSTEM_TEMP_HIGH}°C / {BF_TEMP_HIGH}°C")
    print(f"  Very-High:   {GPU_TEMP_VERY_HIGH}°C / {SYSTEM_TEMP_VERY_HIGH}°C / {BF_TEMP_VERY_HIGH}°C")
    print(f"  Auto Mode Threshold (GPU/System): {AUTO_MODE_THRESHOLD}°C | BlueField: {BF_TEMP_AUTO_THRESHOLD}°C | NIC: {NIC_TEMP_AUTO_THRESHOLD}°C")
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
    print("Configured Fan Speed Settings (7 levels):")
    print(f"  Very-Low: {FAN_SPEED_VERY_LOW}%")
    print(f"  Low: {FAN_SPEED_LOW}%")
    print(f"  Medium-Low: {FAN_SPEED_MED_LOW}%")
    print(f"  Medium: {FAN_SPEED_MED}%")
    print(f"  Medium-High: {FAN_SPEED_MED_HIGH}%")
    print(f"  High: {FAN_SPEED_HIGH}%")
    print(f"  Very-High: {FAN_SPEED_VERY_HIGH}%")
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
            if any(h in line for h in ('GPU Temperatures:', 'BlueField Temperatures:', 'NIC Temperatures:', 'System Temperatures:')):
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
        bf_temps_history = []
        system_temps_history = []
        fan_speeds_history = []

        with open(LOG_FILE, 'r') as f:
            for line in f:
                try:
                    timestamp_str = line[:19]
                    timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S').timestamp()

                    if timestamp < cutoff_time:
                        continue

                    if 'GPU Temperatures:' in line:
                        match = re.search(r'GPU Temperatures: ([\d\s,]+)°C', line)
                        if match:
                            temps_str = match.group(1)
                            temps = [int(t.strip()) for t in temps_str.split(',') if t.strip().isdigit()]
                            if temps:
                                gpu_temps_history.append((timestamp, temps))

                    if 'BlueField Temperatures:' in line:
                        match = re.search(r'BlueField Temperatures: ([\d\s,]+)°C', line)
                        if match:
                            temps_str = match.group(1)
                            temps = [int(t.strip()) for t in temps_str.split(',') if t.strip().isdigit()]
                            if temps:
                                bf_temps_history.append((timestamp, temps))

                    if 'System Temperatures:' in line:
                        match = re.search(r'System Temperatures: ([\d\s,]+)°C', line)
                        if match:
                            temps_str = match.group(1)
                            temps = [int(t.strip()) for t in temps_str.split(',') if t.strip().isdigit()]
                            if temps:
                                system_temps_history.append((timestamp, temps))

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
            for timestamp, temps in gpu_temps_history[-20:]:
                dt = datetime.fromtimestamp(timestamp)
                max_temp = max(temps)
                print(f"  {dt.strftime('%Y-%m-%d %H:%M:%S')}: {', '.join(map(str, temps))}°C (max: {max_temp}°C)")
        else:
            print("  No GPU temperature data found")

        if bf_temps_history:
            print("\nBlueField Temperature History:")
            for timestamp, temps in bf_temps_history[-20:]:
                dt = datetime.fromtimestamp(timestamp)
                max_temp = max(temps)
                print(f"  {dt.strftime('%Y-%m-%d %H:%M:%S')}: {', '.join(map(str, temps))}°C (max: {max_temp}°C)")

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

    # Discover PCI hardware and gather temperatures
    inv = scan_pci_inventory()
    inv_ok = pci_inventory_ok(inv)
    has_gpus = gpus_present(inv)
    has_bf = bluefield_present(inv)

    gpu_temps, missing_gpu_vendors = collect_gpu_telemetry(inv)
    bf_temps, missing_bf_slots = collect_bf_telemetry(inv)
    system_temps = get_system_temperatures(inv=inv)
    inlet_exhaust = get_inlet_exhaust_temps()

    # Log temperature readings
    if not has_gpus and inv_ok:
        logger.info("GPU Temperatures: No GPUs detected (skipping GPU sensor checks)")
    elif gpu_temps:
        logger.info(f"GPU Temperatures: {', '.join(map(str, gpu_temps))}°C (max: {max(gpu_temps)}°C)")
        if missing_gpu_vendors:
            logger.warning(f"GPU Temperatures: Missing telemetry from present vendor(s): {', '.join(missing_gpu_vendors)}")
    else:
        logger.warning("GPU Temperatures: GPUs detected on PCI bus but temperatures unreadable")

    if has_bf or bf_temps:
        if bf_temps:
            logger.info(f"BlueField Temperatures: {', '.join(map(str, bf_temps))}°C (max: {max(bf_temps)}°C)")
        if missing_bf_slots:
            logger.warning(f"BlueField Temperatures: Unreadable card(s) at PCI slot(s): {', '.join(missing_bf_slots)}")

    if system_temps:
        logger.info(f"System Temperatures: {', '.join(map(str, system_temps))}°C (max: {max(system_temps)}°C)")
    else:
        logger.warning("System Temperatures: Unable to read")

    if inlet_exhaust:
        inlet = inlet_exhaust.get('inlet', 'N/A')
        exhaust = inlet_exhaust.get('exhaust', 'N/A')
        diff = inlet_exhaust.get('differential', 'N/A')
        logger.info(f"Inlet: {inlet}°C, Exhaust: {exhaust}°C, Differential: {diff}°C")
    else:
        logger.info("Inlet/Exhaust: Unable to read (requires IPMI)")

    # Get current fan speeds before making changes (for comparison)
    current_fan_speeds = get_fan_speeds()
    if current_fan_speeds:
        avg_current_speed = sum(current_fan_speeds) // len(current_fan_speeds)
        logger.info(f"Current Fan Speeds: {', '.join(map(str, current_fan_speeds))} RPM (avg: {avg_current_speed} RPM)")

    nic_temps = get_nic_temperatures(inv)
    if nic_temps:
        logger.info(f"NIC Temperatures: {', '.join(map(str, nic_temps))}°C (max: {max(nic_temps)}°C)")

    # Determine action
    action, speed, reason = determine_fan_action(gpu_temps, system_temps, bf_temps=bf_temps)
    override = safety_override(
        gpu_temps,
        system_temps,
        nic_temps,
        has_gpus,
        bf_temps=bf_temps,
        bf_present=has_bf,
        missing_gpu_vendors=missing_gpu_vendors,
        missing_bf_slots=missing_bf_slots,
        pci_inventory_ok=inv_ok,
    )
    if override:
        action, speed, reason = 'auto', None, override
    elif action == 'manual' and speed is not None and nic_temps and max(nic_temps) >= NIC_TEMP_FLOOR_THRESHOLD:
        if speed < NIC_TEMP_FLOOR_FAN_SPEED:
            reason = (f"{reason}; NIC {max(nic_temps)}°C >= {NIC_TEMP_FLOOR_THRESHOLD}°C"
                      f" - applying floor {NIC_TEMP_FLOOR_FAN_SPEED}%")
            speed = NIC_TEMP_FLOOR_FAN_SPEED

    # Apply inlet/exhaust floor - boost minimum when chassis is hot (protects NIC, etc.)
    if action == 'manual' and speed is not None and inlet_exhaust:
        inlet = inlet_exhaust.get('inlet')
        exhaust = inlet_exhaust.get('exhaust')
        if inlet is not None and inlet >= INLET_TEMP_FLOOR_THRESHOLD:
            if speed < INLET_EXHAUST_FLOOR_FAN_SPEED:
                reason = f"{reason}; Inlet {inlet}°C >= {INLET_TEMP_FLOOR_THRESHOLD}°C - applying floor {INLET_EXHAUST_FLOOR_FAN_SPEED}%"
                speed = INLET_EXHAUST_FLOOR_FAN_SPEED
        elif exhaust is not None and exhaust >= EXHAUST_TEMP_FLOOR_THRESHOLD:
            if speed < INLET_EXHAUST_FLOOR_FAN_SPEED:
                reason = f"{reason}; Exhaust {exhaust}°C >= {EXHAUST_TEMP_FLOOR_THRESHOLD}°C - applying floor {INLET_EXHAUST_FLOOR_FAN_SPEED}%"
                speed = INLET_EXHAUST_FLOOR_FAN_SPEED

    # Log the decision reasoning
    logger.info(f"Decision: {reason}")

    # Execute action
    if action == 'auto':
        logger.info("ACTION: Switching to AUTOMATIC mode - iDRAC will control fans")
        logger.info(f"Reason: {reason}")
        auto_ok = enable_automatic_fan_mode()
        if current_fan_speeds:
            log_unified_data(gpu_temps, system_temps, current_fan_speeds, None, inlet_exhaust)
        if not auto_ok:
            logger.error("Failed to enable automatic fan mode")
            sys.exit(1)
    else:
        # Enable manual mode and set fan speed
        if enable_manual_fan_mode():
            speed_change = f" (Target: {speed}%)" if current_fan_speeds else ""
            logger.info(f"ACTION: Setting fan speed to {speed}%{speed_change}")
            logger.info(f"Reason: {reason}")

            if set_fan_speed(speed):
                new_fan_speeds = get_fan_speeds()
                if new_fan_speeds:
                    avg_new_speed = sum(new_fan_speeds) // len(new_fan_speeds)
                    if current_fan_speeds:
                        avg_old_speed = sum(current_fan_speeds) // len(current_fan_speeds)
                        if avg_new_speed > avg_old_speed:
                            logger.info(f"Fan speed INCREASED: {avg_old_speed} RPM → {avg_new_speed} RPM")
                        elif avg_new_speed < avg_old_speed:
                            logger.info(f"Fan speed DECREASED: {avg_old_speed} RPM → {avg_new_speed} RPM")
                        else:
                            logger.info(f"Fan speed UNCHANGED: {avg_new_speed} RPM")
                    else:
                        logger.info(f"Fan speeds after change: {', '.join(map(str, new_fan_speeds))} RPM (avg: {avg_new_speed} RPM)")

                    log_unified_data(gpu_temps, system_temps, new_fan_speeds, speed, inlet_exhaust)
            else:
                logger.error("Failed to set fan speed")
                if current_fan_speeds:
                    log_unified_data(gpu_temps, system_temps, current_fan_speeds, None, inlet_exhaust)
                sys.exit(1)
        else:
            logger.error("Failed to enable manual mode")
            sys.exit(1)

    logger.info("Check complete")
    logger.info("=" * 60)


if __name__ == '__main__':
    main()
