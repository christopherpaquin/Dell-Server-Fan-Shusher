# Changelog

All notable changes to Dell-Server-Fan-Shusher will be documented in this file.

## [Unreleased]

### Added
- **BlueField DPU (BF2 / BF3) thermal awareness**: detects BlueField cards on the PCI bus (`15b3:a2d6` / `15b3:c2d3`, etc.), reads per-card temperatures via `mlx5` `hwmon` with automatic `mstreg` `MTMP` fallback across present PFs, logs `BlueField Temperatures` (including `--temps`, `--history`, and `--history-detailed`), and drives a dedicated 7-level `BF_TEMP_*` fan curve (`50/60/68/75/82/88/92°C`, automatic iDRAC handoff at `BF_TEMP_AUTO_THRESHOLD=95°C` or if any detected BlueField card is unreadable)
- **GPU presence gating**: checks `/sys/bus/pci/devices` for discrete GPUs (NVIDIA, AMD, Intel display/3D controllers while ignoring onboard Matrox/ASPEED BMC video) and skips all GPU monitoring tool subprocesses (`nvidia-smi`, `rocm-smi`, `intel_gpu_top`, `sensors`) when no GPUs are installed
- `install.sh --non-interactive [--interval N]`: systemd timer install with no prompts (for automated builds);
  skips pip when `python-dotenv` is already importable (e.g. apt `python3-dotenv`; pip is blocked by PEP 668 on new distros)
- NIC/HCA temperatures: ConnectX adapters via `mstflint`'s `mstreg` MTMP register, plus any network adapter with a
  hwmon sensor. `NIC_TEMP_FLOOR_THRESHOLD` / `NIC_TEMP_FLOOR_FAN_SPEED` / `NIC_TEMP_AUTO_THRESHOLD`
- `tests/` (pytest) for GPU absence skipping, BlueField DPU thermal curves, hwmon/lm-sensors attribution, safety fallbacks, and NIC parsing
- Dell R720 compatibility support
- R730 compatibility test script (`TEST_R730.sh`)
- Comprehensive testing documentation (`R730_TEST_INSTRUCTIONS.md`)
- R720 compatibility documentation (`R720_COMPATIBILITY.md`)

### Fixed
- **Sensor isolation**: excluded PCI GPU, BlueField DPU, and NIC `hwmon` / `lm-sensors` blocks (`mlx5`, `amdgpu`, etc.) from `System Temperatures` so idle ~60°C Mellanox/BlueField ASICs no longer falsely trigger CPU/system medium/high fan speeds
- **Safety exit codes & installer sequencing**: `fan_control.py` now exits non-zero when either automatic-mode handoff or manual fan-speed IPMI commands fail, and `install.sh` quiesces active timers before running its verification check to prevent overlapping IPMI writes
- **SAFETY**: missing readings no longer count as 0 °C. With NVIDIA GPUs present but no GPU temperature readable
  (e.g. no driver), or no system temperature, the script hands the fans to the iDRAC (automatic mode). Before, it
  pinned the fans at the lowest speed, which can overheat passively cooled Tesla cards (seen on an R730 with 2× T4
  and no driver: the old logic chose 25 %).
- **CRITICAL FIX**: IPMI hex value formatting for Dell R720 compatibility
  - Changed: `hex_value = format(percentage, '02x')` → produces `0a`
  - To: `hex_value = f'0x{percentage:02x}'` → produces `0x0a`
  - Reason: R720 iDRAC requires `0x` prefix for IPMI raw commands
  - Impact: Fan speed setting now works on Dell R720 servers

### Changed
- Updated README.md to reflect R720/R730 dual compatibility
- Improved hex formatting to use IPMI standard format (0x prefix)

## [1.0.0] - 2026-01-31

### Initial Release
- Python-based fan control script with GPU temperature monitoring
- Support for NVIDIA, AMD, and Intel GPUs
- 7-level temperature threshold system
- Systemd service and timer integration
- Comprehensive logging and monitoring
- Temperature history tracking
- Adaptive learning system for threshold optimization
- Originally designed for Dell R730, now supports R720 as well

---

## Compatibility Matrix

| Server Model | Status | Tested Date | iDRAC Version | Notes |
|-------------|--------|-------------|---------------|-------|
| Dell R720   | ✅ Working | 2026-01-31 | Various | Requires 0x prefix |
| Dell R730   | ✅ Working | 2026-01-31 | 2.86 | Also requires 0x prefix |
| Dell R720xd | ⚠️ Untested | - | - | Likely compatible |
| Dell R730xd | ⚠️ Untested | - | - | Likely compatible |

---

## Migration Notes

### For Existing R730 Users
If you're upgrading from a previous version on an R730:
1. The hex formatting change should be transparent
2. R730 should accept both old and new formats
3. If issues occur, please report and see rollback instructions in R730_TEST_INSTRUCTIONS.md

### For New R720 Users
The current version includes the R720 compatibility fix. Installation is identical to R730:
1. Clone repository
2. Configure `.env` with your iDRAC credentials
3. Run `./install.sh`
4. Enable and start the service

---

## Known Issues

### None Currently

### Resolved
- ✅ R720 fan speed control failures (fixed with 0x prefix)
- ✅ R730 compatibility verified (also requires 0x prefix)
- ✅ IPMI command timeout issues (increased timeout to 20s)
- ✅ Temperature sensor detection on various Dell models

---

## Contributing

When reporting issues or submitting compatibility reports, please include:
- Server model (e.g., Dell R720, R730)
- iDRAC version
- Test results from `TEST_R730.sh` (if applicable)
- Relevant log output from `journalctl -u dell-r730-fan-control`
