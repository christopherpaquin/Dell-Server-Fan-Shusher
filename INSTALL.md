# 🚀 Quick Installation Guide

## First Steps

**Run the install script first:**

```bash
sudo ./install.sh
```

## What the Install Script Does

The install script now includes comprehensive error checking:

✅ **Dependency Validation**
- Checks for Python 3.6+
- Verifies ipmitool is installed
- Detects available GPU monitoring tools
- Exits with clear error messages if required dependencies are missing

✅ **Python Package Installation**
- Installs python-dotenv
- Verifies installation succeeded
- Tries user install first, then sudo if needed
- Exits on failure with helpful messages

✅ **File Validation**
- Verifies all required files exist
- Checks file permissions
- Validates Python script syntax
- Ensures .env file is readable

✅ **Service Installation**
- Verifies systemd service files created successfully
- Checks systemd daemon reload
- Confirms timer is enabled and started
- Validates cron job installation

✅ **Test Run**
- Detects default credentials
- Warns if using default password
- Runs test and reports success/failure
- Provides clear next steps

## Installation Process

1. **Run the installer:**
   ```bash
   sudo ./install.sh
   ```

2. **The script will:**
   - Check all dependencies
   - Install Python packages
   - Create .env file from template
   - Ask you to choose systemd or cron
   - Perform a test run

3. **After installation:**
   - Edit `.env` with your iDRAC credentials
   - Test manually: `python3 fan_control.py --temps`
   - Monitor logs: `tail -f /var/log/dell-r730-fan-control.log`

## Error Handling

The script will:
- ❌ **Exit immediately** if critical dependencies are missing
- ❌ **Exit with error** if file operations fail
- ❌ **Exit with error** if service installation fails
- ⚠️ **Warn** if default credentials are detected
- ⚠️ **Warn** if GPU tools are not found (but continue)
- ✅ **Verify** each step before proceeding

## Troubleshooting Installation

If installation fails:

1. **Check error message** - The script provides specific error details
2. **Verify dependencies:**
   ```bash
   python3 --version
   which ipmitool
   which nvidia-smi  # or rocm-smi, intel_gpu_top, sensors
   ```
3. **Check permissions:**
   ```bash
   ls -la install.sh
   chmod +x install.sh  # If needed
   ```
4. **Run with verbose output:**
   ```bash
   bash -x ./install.sh
   ```

## Manual Verification

After installation, verify everything works:

```bash
# Check script syntax
python3 -m py_compile fan_control.py

# Test temperature reading (read-only)
python3 fan_control.py --temps

# Check service status (if using systemd)
sudo systemctl status dell-r730-fan-control.timer

# View recent logs
tail -n 50 /var/log/dell-r730-fan-control.log
```

