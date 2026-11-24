# Worklog

## 2026-11-24 17:58
**Task:** Skip GPU temperature probing when no discrete GPUs are present and add BlueField-2 (BF2) DPU thermal monitoring & redeploy to prometheus.lab
**Decision:** Gate GPU tool subprocesses on validated sysfs PCI inventory (`0x10de`/`0x1002`/`0x8086` class `0x03*`, ignoring onboard BMC VGA like Matrox `0x102b`); isolate PCI GPU/NIC/BlueField `hwmon` and `lm-sensors` chips from `System Temperatures`; add per-card BlueField DPU detection (`15b3:a2d6`/`15b3:c2d3`, etc.), `mlx5` `hwmon` + `mstreg` `MTMP` fallback, missing-card safety handoff, and a dedicated 7-level `BF_TEMP_*` curve (`50/60/68/75/82/88/92°C`, auto at `95°C`), plus a stdlib `.env` fallback when `python-dotenv` is absent.
**Why:** On `prometheus.lab`, both Tesla T4 GPUs were removed and a Mellanox BlueField-2 DPU was installed in Slot 5 (`05:00`). Previously, `fan_control.py` still spawned GPU CLI tools every 30s and swept BF2's `mlx5` `hwmon` (~60-62°C idle, firmware warn 95°C / crit 105°C) into CPU `System Temperatures`, falsely triggering `SYSTEM_TEMP_MED=55°C` (45% / ~8780 RPM at idle) while risking premature `AUTO_MODE_THRESHOLD=75°C` handoff under normal DPU load.
**Progress:** in-progress (local code, docs, and tests verified; committing, pushing, and redeploying to prometheus.lab next)

## 2026-11-24 18:01
**Task:** Fix Inlet/Exhaust `sdr type Temperature` regex matching entity ID `7.1` on live prometheus.lab verification
**Decision:** Anchor Inlet/Exhaust regex to `degrees C` (`\|\s*([+\-]?\d+(?:\.\d+)?)\s*(?:\|\s*)?degrees\s*C`) and `tail -n 1` duplicate `LOG_FILE=` entries in `install.sh`.
**Why:** Live `--temps` verification on `prometheus.lab` revealed `ipmitool sdr type Temperature` emits `| 04h | ok | 7.1 | 23 degrees C`, where the unanchored `\|` branch matched entity ID `7.1` (`7°C`) instead of `23 degrees C`.
**Progress:** done
