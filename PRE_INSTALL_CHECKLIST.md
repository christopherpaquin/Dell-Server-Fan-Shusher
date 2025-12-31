# ✅ Pre-Installation Checklist

## Quick Verification

All scripts have been validated:
- ✅ `fan_control.py` - Syntax OK
- ✅ `install.sh` - Syntax OK  
- ✅ `uninstall.sh` - Syntax OK
- ✅ All required files present

## Before You Run Install

### 1. **Verify You're on the Target Server**
```bash
hostname
# Should show your Dell R730 server
```

### 2. **Check Prerequisites**
```bash
# Python 3.6+
python3 --version

# ipmitool
which ipmitool
ipmitool -V

# GPU monitoring (at least one)
which nvidia-smi    # NVIDIA
which rocm-smi      # AMD
which intel_gpu_top # Intel
which sensors       # Generic (lm-sensors)
```

### 3. **Verify Network Access to iDRAC**
```bash
# Ping iDRAC (replace with your IP)
ping -c 2 10.1.10.20

# Test IPMI access (replace with your credentials)
ipmitool -I lanplus -H 10.1.10.20 -U root -P calvin sdr list | head -5
```

### 4. **Check Permissions**
```bash
# You'll need sudo/root for installation
sudo -v
```

### 5. **Review Configuration**
```bash
# Check the example config
cat env.example

# Note: You'll edit .env after installation with your actual credentials
```

## Installation Steps

1. **Run the installer:**
   ```bash
   sudo ./install.sh
   ```

2. **The installer will:**
   - Check dependencies
   - Install Python packages
   - Create .env file
   - Ask you to choose systemd or cron
   - Perform a test run

3. **After installation:**
   - Edit `.env` with your iDRAC credentials
   - Test manually: `python3 fan_control.py --temps`
   - Monitor logs: `tail -f /var/log/dell-r730-fan-control.log`

## What to Watch For

### During Installation:
- ✅ Dependencies found (python3, ipmitool)
- ✅ GPU monitoring tool detected (or warning if none)
- ✅ Python packages installed successfully
- ✅ .env file created
- ✅ Service/timer installed (if chosen)

### After Installation:
- ⚠️ **IMPORTANT:** Edit `.env` with your actual iDRAC credentials
- ✅ Test read-only mode: `python3 fan_control.py --temps`
- ✅ Check service status: `sudo systemctl status dell-r730-fan-control.timer`
- ✅ Monitor logs: `tail -f /var/log/dell-r730-fan-control.log`

## Troubleshooting

If installation fails:
1. Check error message - it will tell you what's missing
2. Verify prerequisites are installed
3. Check network connectivity to iDRAC
4. Review logs for specific errors

## Ready to Install?

Run:
```bash
sudo ./install.sh
```

Good luck! 🚀

