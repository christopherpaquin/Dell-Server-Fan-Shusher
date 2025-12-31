# ⏰ Scheduling and Frequency Guide

## How Often Does It Run?

### Systemd Timer (Recommended)

**Default Frequency:** Every 30 seconds (configurable during installation)

**How it works:**
- The systemd timer uses `OnUnitActiveSec` which means it runs X seconds **after the previous run completed**
- This ensures the script doesn't overlap with itself
- The timer starts 1 minute after boot (`OnBootSec=1min`)

**Configuration:**
- During installation, you're prompted: `Enter check interval in seconds [30]:`
- You can set any interval (e.g., 30, 60, 120 seconds)
- The timer file is created with your chosen interval

**Example Timer Configuration:**
```ini
[Timer]
OnBootSec=1min          # Start 1 minute after boot
OnUnitActiveSec=30s     # Run every 30 seconds after previous completion
AccuracySec=1s          # Accuracy of 1 second
```

**Check current interval:**
```bash
sudo systemctl cat dell-r730-fan-control.timer | grep OnUnitActiveSec
```

**Change interval after installation:**
```bash
# Edit the timer file
sudo systemctl edit dell-r730-fan-control.timer

# Add this (example for 60 seconds):
[Timer]
OnUnitActiveSec=60s

# Reload and restart
sudo systemctl daemon-reload
sudo systemctl restart dell-r730-fan-control.timer
```

### Cron Job

**Default Frequency:** Every 30 seconds (requires two entries)

**How it works:**
- Cron has a **minimum interval of 1 minute**
- To run every 30 seconds, the install script creates **two cron entries**:
  1. One that runs at :00 of every minute
  2. One that runs at :30 of every minute (with a 30-second sleep)
- For intervals >= 60 seconds, a single standard cron entry is used

**Cron Entry Examples:**

**Every 30 seconds (two entries):**
```bash
* * * * * /usr/bin/python3 /path/to/fan_control.py
* * * * * sleep 30; /usr/bin/python3 /path/to/fan_control.py
```

**Every 5 minutes (single entry):**
```bash
*/5 * * * * /usr/bin/python3 /path/to/fan_control.py
```

**Configuration:**
- During installation, you're prompted: `Enter check interval in seconds [30]:`
- The script automatically creates the appropriate cron entries

**View current cron jobs:**
```bash
crontab -l | grep fan_control
```

**Change interval after installation:**
```bash
# Edit crontab
crontab -e

# Remove old entries and add new ones
# For 60 seconds (every minute):
* * * * * /usr/bin/python3 /path/to/fan_control.py

# For 30 seconds (two entries):
* * * * * /usr/bin/python3 /path/to/fan_control.py
* * * * * sleep 30; /usr/bin/python3 /path/to/fan_control.py
```

## Comparison: Systemd vs Cron

| Feature | Systemd Timer | Cron |
|---------|---------------|------|
| **Minimum Interval** | Any (even < 1 second) | 1 minute |
| **30-second intervals** | ✅ Native support | ⚠️ Requires 2 entries |
| **Accuracy** | Very high (1 second) | Lower (minute-level) |
| **Overlap Prevention** | ✅ Automatic | ❌ Manual (sleep) |
| **Boot Delay** | ✅ Configurable | ❌ Runs immediately |
| **Logging** | ✅ journalctl | ⚠️ Manual setup |
| **Dependency Management** | ✅ Built-in | ❌ None |

## Recommended Settings

### For Quiet Operation (Low Load)
- **Interval:** 60-120 seconds
- **Reason:** Lower frequency reduces system overhead

### For Active Monitoring (High Load)
- **Interval:** 30 seconds
- **Reason:** More frequent checks catch temperature spikes faster

### For Critical Systems
- **Interval:** 15-30 seconds
- **Reason:** Maximum responsiveness to temperature changes

## Monitoring Schedule Status

### Systemd Timer
```bash
# Check if timer is active
sudo systemctl status dell-r730-fan-control.timer

# Check when it last ran
sudo systemctl status dell-r730-fan-control.service

# View timer details
systemctl list-timers dell-r730-fan-control.timer
```

### Cron Job
```bash
# View cron entries
crontab -l | grep fan_control

# Check cron logs (location varies by distro)
# Ubuntu/Debian:
grep CRON /var/log/syslog | grep fan_control

# CentOS/RHEL:
grep CRON /var/log/cron | grep fan_control
```

## Troubleshooting Schedule Issues

### Systemd Timer Not Running
```bash
# Check timer status
sudo systemctl status dell-r730-fan-control.timer

# Check if timer is enabled
sudo systemctl is-enabled dell-r730-fan-control.timer

# View timer configuration
sudo systemctl cat dell-r730-fan-control.timer

# Restart timer
sudo systemctl restart dell-r730-fan-control.timer
```

### Cron Job Not Running
```bash
# Verify cron service is running
sudo systemctl status cron  # or crond on some systems

# Check cron syntax
crontab -l

# Test cron entry manually
* * * * * /usr/bin/python3 /path/to/fan_control.py --temps
```

## Changing Frequency After Installation

### Systemd Timer
1. Edit timer: `sudo systemctl edit dell-r730-fan-control.timer`
2. Add new interval: `OnUnitActiveSec=60s`
3. Reload: `sudo systemctl daemon-reload`
4. Restart: `sudo systemctl restart dell-r730-fan-control.timer`

### Cron Job
1. Edit crontab: `crontab -e`
2. Modify or add entries
3. Save and exit (cron automatically reloads)

