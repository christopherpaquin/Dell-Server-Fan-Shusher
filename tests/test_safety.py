"""Safety fallback and NIC temperature parsing (no hardware needed)."""

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import fan_control as fc  # noqa: E402


def test_gpus_present_but_unreadable_hands_over_to_idrac():
    reason = fc.safety_override([], [40], [], gpus_present=True)
    assert reason and "iDRAC takes over" in reason


def test_no_system_temps_hands_over_to_idrac():
    assert fc.safety_override([50], [], [], gpus_present=True)


def test_hot_nic_hands_over_and_normal_readings_do_not():
    assert fc.safety_override([50], [40], [fc.NIC_TEMP_AUTO_THRESHOLD], gpus_present=True)
    assert fc.safety_override([50], [40], [70], gpus_present=True) is None
    assert fc.safety_override([], [40], [], gpus_present=False) is None  # no GPUs: system temps decide


def make_pci(tmp_path, addr, vendor, cls):
    d = tmp_path / addr
    d.mkdir()
    (d / "vendor").write_text(vendor + "\n")
    (d / "class").write_text(cls + "\n")


def test_pci_scan_finds_nvidia_3d_controllers_only(tmp_path, monkeypatch):
    make_pci(tmp_path, "0000:04:00.0", "0x10de", "0x030200")
    make_pci(tmp_path, "0000:04:00.1", "0x10de", "0x040300")  # HDMI audio function
    monkeypatch.setattr(fc, "PCI_DEVICES", str(tmp_path))
    assert fc.nvidia_gpus_present()
    assert [a for a, _, _ in fc._pci_devices(fc.NVIDIA_VENDOR, ("0x03",))] == ["0000:04:00.0"]


def test_mlx_temperature_from_mtmp(tmp_path, monkeypatch):
    make_pci(tmp_path, "0000:81:00.0", "0x15b3", "0x020700")  # ConnectX-4 in IB mode
    make_pci(tmp_path, "0000:81:00.1", "0x15b3", "0x020700")  # second function, same chip
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
    make_pci(tmp_path, "0000:81:00.0", "0x15b3", "0x020700")
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
