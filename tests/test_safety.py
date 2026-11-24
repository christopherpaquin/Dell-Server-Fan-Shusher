"""Unit tests for GPU absence skipping, BlueField DPU thermal control, NIC/system attribution, and safety fallbacks."""

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import fan_control as fc  # noqa: E402


def make_pci(base_dir, addr, vendor, cls, device=None, is_vf=False):
    d = base_dir / addr
    d.mkdir(parents=True, exist_ok=True)
    if vendor is not None:
        (d / "vendor").write_text(vendor + "\n")
    if cls is not None:
        (d / "class").write_text(cls + "\n")
    if device is not None:
        (d / "device").write_text(device + "\n")
    if is_vf:
        (d / "physfn").mkdir(exist_ok=True)
    return d


def make_hwmon(hwmon_root, idx, name, temps_mc, pci_dev_dir=None, dev_attrs=None):
    h = hwmon_root / f"hwmon{idx}"
    h.mkdir(parents=True, exist_ok=True)
    if name is not None:
        (h / "name").write_text(name + "\n")
    for i, val in enumerate(temps_mc, start=1):
        (h / f"temp{i}_input").write_text(f"{val}\n")
    if pci_dev_dir is not None:
        (h / "device").symlink_to(pci_dev_dir)
    elif dev_attrs:
        dev = h / "device"
        dev.mkdir()
        for k, v in dev_attrs.items():
            (dev / k).write_text(v + "\n")
    return h


# ---------------------------------------------------------------------------
# Existing baseline safety & MTMP tests (backwards compatibility)
# ---------------------------------------------------------------------------

def test_gpus_present_but_unreadable_hands_over_to_idrac():
    reason = fc.safety_override([], [40], [], gpus_present=True)
    assert reason and "iDRAC takes over" in reason


def test_no_system_temps_hands_over_to_idrac():
    assert fc.safety_override([50], [], [], gpus_present=True)


def test_hot_nic_hands_over_and_normal_readings_do_not():
    assert fc.safety_override([50], [40], [fc.NIC_TEMP_AUTO_THRESHOLD], gpus_present=True)
    assert fc.safety_override([50], [40], [70], gpus_present=True) is None
    assert fc.safety_override([], [40], [], gpus_present=False) is None  # no GPUs: system temps decide


def test_pci_scan_finds_nvidia_3d_controllers_only(tmp_path, monkeypatch):
    make_pci(tmp_path, "0000:04:00.0", "0x10de", "0x030200")
    make_pci(tmp_path, "0000:04:00.1", "0x10de", "0x040300")  # HDMI audio function
    monkeypatch.setattr(fc, "PCI_DEVICES", str(tmp_path))
    assert fc.nvidia_gpus_present()
    assert [a for a, _, _ in fc._pci_devices(fc.NVIDIA_VENDOR, ("0x03",))] == ["0000:04:00.0"]


def test_mlx_temperature_from_mtmp(tmp_path, monkeypatch):
    make_pci(tmp_path, "0000:81:00.0", "0x15b3", "0x020700", device="0x1013")  # ConnectX-4 in IB mode
    make_pci(tmp_path, "0000:81:00.1", "0x15b3", "0x020700", device="0x1013")  # second function, same chip
    monkeypatch.setattr(fc, "PCI_DEVICES", str(tmp_path))
    calls = []

    def fake_run(argv, **kw):
        calls.append(argv)
        out = "temperature                 | 0x00000260\nmax_temperature             | 0x00000270\n"
        return subprocess.CompletedProcess(argv, 0, out, "")

    monkeypatch.setattr(fc.subprocess, "run", fake_run)
    assert fc.get_nic_temperatures_mlx() == [76]  # 0x260 = 608 eighths of a degree
    assert len(calls) == 1  # one reading per adapter


def test_mlx_without_mstflint_is_silent(tmp_path, monkeypatch):
    make_pci(tmp_path, "0000:81:00.0", "0x15b3", "0x020700", device="0x1013")
    monkeypatch.setattr(fc, "PCI_DEVICES", str(tmp_path))

    def missing(argv, **kw):
        raise FileNotFoundError("mstreg")

    monkeypatch.setattr(fc.subprocess, "run", missing)
    assert fc.get_nic_temperatures_mlx() == []


@pytest.mark.parametrize("flag", [[], ["--interval", "abc"], ["--bogus"]])
def test_installer_rejects_bad_arguments(flag):
    if not flag:
        pytest.skip("no-arg run is interactive")
    proc = subprocess.run(["bash", "install.sh", *flag], capture_output=True, text=True, timeout=30,
                          cwd=Path(__file__).resolve().parent.parent)
    assert proc.returncode == 2


# ---------------------------------------------------------------------------
# GPU absence & vendor-scoped probing
# ---------------------------------------------------------------------------

def test_no_gpus_with_matrox_bmc_skips_all_gpu_subprocesses(tmp_path, monkeypatch):
    pci_dir = tmp_path / "pci"
    pci_dir.mkdir()
    # Matrox G200eR2 BMC VGA + BlueField-2 + ConnectX-4 (exact prometheus.lab topology)
    make_pci(pci_dir, "0000:0c:00.0", "0x102b", "0x030000", device="0x0534")
    make_pci(pci_dir, "0000:05:00.0", "0x15b3", "0x020000", device="0xa2d6")
    make_pci(pci_dir, "0000:05:00.1", "0x15b3", "0x020000", device="0xa2d6")
    make_pci(pci_dir, "0000:05:00.2", "0x15b3", "0x080100", device="0xc2d3")
    make_pci(pci_dir, "0000:81:00.0", "0x15b3", "0x020700", device="0x1013")
    monkeypatch.setattr(fc, "PCI_DEVICES", str(pci_dir))

    inv = fc.scan_pci_inventory()
    assert fc.pci_inventory_ok(inv)
    assert not fc.gpus_present(inv)
    assert not fc.nvidia_gpus_present()

    def forbid_subprocess(*args, **kwargs):
        raise AssertionError(f"GPU subprocess should not be called when no GPUs exist: {args}")

    monkeypatch.setattr(fc.subprocess, "run", forbid_subprocess)
    temps, missing = fc.collect_gpu_telemetry(inv)
    assert temps == []
    assert missing == []
    assert fc.get_gpu_temperatures(inv) == []


def test_mixed_gpu_vendors_detects_partial_vendor_failure(tmp_path, monkeypatch):
    pci_dir = tmp_path / "pci"
    pci_dir.mkdir()
    make_pci(pci_dir, "0000:04:00.0", "0x10de", "0x030200", device="0x1eb8")  # NVIDIA T4
    make_pci(pci_dir, "0000:06:00.0", "0x1002", "0x030000", device="0x744c")  # AMD GPU
    monkeypatch.setattr(fc, "PCI_DEVICES", str(pci_dir))

    def fake_run(argv, **kw):
        if argv[0] == "nvidia-smi":
            return subprocess.CompletedProcess(argv, 0, "52\n", "")
        # AMD rocm-smi and sensors fail to return AMD temp
        return subprocess.CompletedProcess(argv, 1, "", "failed")

    monkeypatch.setattr(fc.subprocess, "run", fake_run)
    inv = fc.scan_pci_inventory()
    temps, missing = fc.collect_gpu_telemetry(inv)
    assert temps == [52]
    assert missing == ["amd"]
    reason = fc.safety_override(temps, [35], [], gpus_present=True, missing_gpu_vendors=missing)
    assert reason and "amd" in reason and "iDRAC takes over" in reason


def test_incomplete_or_unknown_display_pci_inventory_triggers_safety_override(tmp_path, monkeypatch):
    pci_dir = tmp_path / "pci"
    pci_dir.mkdir()
    # Unknown display controller vendor 0x9999
    make_pci(pci_dir, "0000:09:00.0", "0x9999", "0x030000", device="0x0001")
    monkeypatch.setattr(fc, "PCI_DEVICES", str(pci_dir))

    inv = fc.scan_pci_inventory()
    assert not fc.pci_inventory_ok(inv)
    reason = fc.safety_override([], [35], [], gpus_present=False, pci_inventory_ok=fc.pci_inventory_ok(inv))
    assert reason and "PCI device inventory" in reason and "iDRAC takes over" in reason

    # Malformed vendor hex also marks inventory incomplete
    pci_bad = tmp_path / "pci_bad"
    pci_bad.mkdir()
    make_pci(pci_bad, "0000:01:00.0", "corrupt", "0x020000")
    monkeypatch.setattr(fc, "PCI_DEVICES", str(pci_bad))
    inv_bad = fc.scan_pci_inventory()
    assert not fc.pci_inventory_ok(inv_bad)


# ---------------------------------------------------------------------------
# BlueField DPU detection, hwmon/system/NIC isolation, and MTMP fallback
# ---------------------------------------------------------------------------

def test_prometheus_hwmon_isolates_bf2_from_system_and_plain_nic(tmp_path, monkeypatch):
    pci_dir = tmp_path / "pci"
    hwmon_dir = tmp_path / "hwmon"
    pci_dir.mkdir()
    hwmon_dir.mkdir()

    bf_pf0 = make_pci(pci_dir, "0000:05:00.0", "0x15b3", "0x020000", device="0xa2d6")
    bf_pf1 = make_pci(pci_dir, "0000:05:00.1", "0x15b3", "0x020000", device="0xa2d6")
    make_pci(pci_dir, "0000:05:00.2", "0x15b3", "0x080100", device="0xc2d3")
    # SR-IOV VF should be ignored as a separate card
    make_pci(pci_dir, "0000:05:01.0", "0x15b3", "0x020000", device="0xa2d6", is_vf=True)
    make_pci(pci_dir, "0000:81:00.0", "0x15b3", "0x020700", device="0x1013")  # ConnectX-4

    # BF2 exposes two mlx5 hwmon nodes (ports 0 and 1); port 1 also has a warmer optical sensor (67°C)
    make_hwmon(hwmon_dir, 0, "mlx5", [61000], pci_dev_dir=bf_pf0)
    make_hwmon(hwmon_dir, 1, "mlx5", [62000, 67000], pci_dev_dir=bf_pf1)
    # ACPI power_meter (no temp) + unknown unattributed sensor (must NOT enter system_temps)
    make_hwmon(hwmon_dir, 2, "mystery_sensor", [88000])
    # CPU coretemp sensors
    make_hwmon(hwmon_dir, 3, "coretemp", [32000, 27000, 26000])
    make_hwmon(hwmon_dir, 4, "coretemp", [33000, 28000, 27000])

    monkeypatch.setattr(fc, "PCI_DEVICES", str(pci_dir))
    monkeypatch.setattr(fc, "HWMON_PATH", str(hwmon_dir))

    mtmp_calls = []

    def fake_run(argv, **kw):
        mtmp_calls.append(argv)
        # ConnectX-4 at 81:00.0 returns 59°C (0x1d8 = 472 / 8)
        out = "temperature                 | 0x000001d8\n"
        return subprocess.CompletedProcess(argv, 0, out, "")

    monkeypatch.setattr(fc.subprocess, "run", fake_run)

    inv = fc.scan_pci_inventory()
    assert list(fc.bluefield_cards(inv).keys()) == ["0000:05:00"]

    sys_temps = fc.get_system_temperatures_sysfs(inv=inv)
    assert sys_temps == [32, 27, 26, 33, 28, 27]  # 61/62/67 BF2 and 88 mystery excluded!

    bf_temps, missing_bf = fc.collect_bf_telemetry(inv)
    assert bf_temps == [67]  # One BF2 card, retains hottest sensor (67°C)
    assert missing_bf == []

    nic_temps = fc.get_nic_temperatures(inv)
    assert nic_temps == [59]  # Only ConnectX-4 (BF2 excluded)
    assert len(mtmp_calls) == 1 and "0000:81:00.0" in mtmp_calls[0]


def test_two_bf_cards_one_unreadable_and_mtmp_fallback_on_nonzero_pf(tmp_path, monkeypatch):
    pci_dir = tmp_path / "pci"
    hwmon_dir = tmp_path / "hwmon"
    pci_dir.mkdir()
    hwmon_dir.mkdir()

    # Card 1 at 05:00 has invalid hwmon (0 m°C) and only PF .1 visible -> falls back to MTMP on 05:00.1
    bf1_pf1 = make_pci(pci_dir, "0000:05:00.1", "0x15b3", "0x020000", device="0xa2d6")
    make_hwmon(hwmon_dir, 0, "mlx5", [0], pci_dev_dir=bf1_pf1)

    # Card 2 at 82:00 has no hwmon and MTMP times out -> reported in missing_bf_slots!
    make_pci(pci_dir, "0000:82:00.0", "0x15b3", "0x020000", device="0xa2d6")

    # Unrelated Mellanox DMA device without BF PF/network PF is NOT treated as BlueField
    make_pci(pci_dir, "0000:90:00.0", "0x15b3", "0x080100", device="0x9999")

    monkeypatch.setattr(fc, "PCI_DEVICES", str(pci_dir))
    monkeypatch.setattr(fc, "HWMON_PATH", str(hwmon_dir))

    def fake_run(argv, **kw):
        addr = argv[argv.index("-d") + 1]
        if addr == "0000:05:00.1":
            return subprocess.CompletedProcess(argv, 0, "temperature | 0x000001f0\n", "")  # 62°C
        raise subprocess.TimeoutExpired(argv, 5)

    monkeypatch.setattr(fc.subprocess, "run", fake_run)

    inv = fc.scan_pci_inventory()
    assert sorted(fc.bluefield_cards(inv).keys()) == ["0000:05:00", "0000:82:00"]
    bf_temps, missing_bf = fc.collect_bf_telemetry(inv)
    assert bf_temps == [62]
    assert missing_bf == ["0000:82:00"]

    reason = fc.safety_override([], [32], [], gpus_present=False, bf_temps=bf_temps,
                                bf_present=True, missing_bf_slots=missing_bf)
    assert reason and "0000:82:00" in reason and "iDRAC takes over" in reason


def test_lm_sensors_block_attribution_for_gpu_and_system(tmp_path, monkeypatch):
    pci_dir = tmp_path / "pci"
    pci_dir.mkdir()
    make_pci(pci_dir, "0000:03:00.0", "0x1002", "0x030000", device="0x744c")
    monkeypatch.setattr(fc, "PCI_DEVICES", str(pci_dir))

    sensors_out = """\
mlx5-pci-0500
Adapter: PCI adapter
sensor0:      +62.0°C  (crit = +105.0°C, highest = +63.0°C)

amdgpu-pci-0300
Adapter: PCI adapter
edge:         +64.0°C  (crit = +100.0°C, hyst = -273.1°C)
junction:     +71.0°C  (crit = +110.0°C)

coretemp-isa-0000
Adapter: ISA adapter
Package id 0:  +34.0°C  (high = +93.0°C, crit = +103.0°C)
Core 0:        -5.0°C  (high = +93.0°C, crit = +103.0°C)
"""
    monkeypatch.setattr(
        fc.subprocess, "run",
        lambda argv, **kw: subprocess.CompletedProcess(argv, 0, sensors_out, ""),
    )
    inv = fc.scan_pci_inventory()
    assert fc.get_gpu_temperatures_sensors(vendors=("amd",), inv=inv) == [64, 71]
    assert fc.get_system_temperatures_sensors() == [34]  # mlx5, amdgpu, and negative -5°C excluded!


# ---------------------------------------------------------------------------
# 7-level BlueField thermal curve, multi-domain max demand, and auto handoff
# ---------------------------------------------------------------------------

def test_bf_curve_levels_and_multi_domain_priority():
    # Idle CPU (32°C -> Very-Low 20%) + idle BF2 (61°C -> BF Low 25%) => 25%
    action, speed, reason = fc.determine_fan_action([], [32], bf_temps=[61])
    assert (action, speed) == ("manual", fc.FAN_SPEED_LOW)
    assert "BlueField temperature 61°C >= LOW" in reason

    # Warm BF2 (76°C >= BF_TEMP_MED 75°C -> 45%) beats cool GPU (48°C -> 25%) even with GPU_TEMP_OVERRIDE
    action, speed, reason = fc.determine_fan_action([48], [32], bf_temps=[76])
    assert (action, speed) == ("manual", fc.FAN_SPEED_MED)
    assert "BlueField" in reason

    # Hot BF2 (>= 95°C) triggers automatic mode handoff
    action, speed, reason = fc.determine_fan_action([], [32], bf_temps=[fc.BF_TEMP_AUTO_THRESHOLD])
    assert action == "auto" and speed is None
    assert "BlueField" in reason

    # safety_override also enforces BF_TEMP_AUTO_THRESHOLD
    override = fc.safety_override([], [32], [59], gpus_present=False,
                                  bf_temps=[fc.BF_TEMP_AUTO_THRESHOLD], bf_present=True)
    assert override and "BlueField" in override and "iDRAC takes over" in override


def test_main_exits_nonzero_when_automatic_handoff_fails(tmp_path, monkeypatch):
    pci_dir = tmp_path / "pci"
    pci_dir.mkdir()
    monkeypatch.setattr(fc, "PCI_DEVICES", str(pci_dir))
    monkeypatch.setattr(fc, "LOG_FILE", str(tmp_path / "fan.log"))
    monkeypatch.setattr(fc, "DATA_LOG_FILE", str(tmp_path / "data.log"))
    monkeypatch.setattr(fc, "get_system_temperatures", lambda inv=None: [])  # forces auto mode
    monkeypatch.setattr(fc, "get_inlet_exhaust_temps", lambda: {})
    monkeypatch.setattr(fc, "get_fan_speeds", lambda: [4800])
    monkeypatch.setattr(fc, "enable_automatic_fan_mode", lambda: False)
    monkeypatch.setattr(sys, "argv", ["fan_control.py"])

    with pytest.raises(SystemExit) as exc:
        fc.main()
    assert exc.value.code == 1


def test_history_commands_parse_bluefield_and_legacy_logs(tmp_path, monkeypatch, capsys):
    log_file = tmp_path / "fan.log"
    now_str = fc.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_file.write_text(
        f"{now_str},100 - INFO - GPU Temperatures: No GPUs detected (skipping GPU sensor checks)\n"
        f"{now_str},101 - INFO - BlueField Temperatures: 61°C (max: 61°C)\n"
        f"{now_str},102 - INFO - System Temperatures: 27, 32°C (max: 32°C)\n"
        f"{now_str},103 - INFO - Current Fan Speeds: 4800, 4920 RPM (avg: 4860 RPM)\n"
    )
    monkeypatch.setattr(fc, "LOG_FILE", str(log_file))

    fc.show_temperature_history(10)
    out = capsys.readouterr().out
    assert "BlueField Temperatures: 61°C" in out

    fc.show_detailed_history(1)
    detailed = capsys.readouterr().out
    assert "BlueField Temperature History:" in detailed
    assert "61°C (max: 61°C)" in detailed
