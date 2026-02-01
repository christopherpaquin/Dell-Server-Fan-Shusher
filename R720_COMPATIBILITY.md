# Dell R720 Compatibility

## Status: ✅ WORKING

The Dell-Server-Fan-Shusher now works correctly on Dell R720 servers!

## Issue Found and Fixed

### Problem
The original code was generating hex values without the `0x` prefix:
- Generated: `0a` (for 10%)
- Required: `0x0a` (for 10%)

**IMPORTANT:** Testing revealed that BOTH R720 and R730 require the `0x` prefix. The original code was broken on both servers, as confirmed by user logs showing identical errors on R730:
```
2026-01-31 21:44:18 - ERROR - Failed to set fan speed: Command failed after all retries
```

### Solution
Updated the `set_fan_speed()` function in `fan_control.py`:

**Before:**
```python
hex_value = format(percentage, '02x')  # Produces: '0a'
```

**After:**
```python
hex_value = f'0x{percentage:02x}'  # Produces: '0x0a'
```

## Verified Working Commands

All IPMI commands work correctly on Dell R720:

1. **Enable Manual Fan Mode:**
   ```bash
   ipmitool -I lanplus -H <IDRAC_IP> -U root -P <PASSWORD> raw 0x30 0x30 0x01 0x00
   ```

2. **Set Fan Speed:**
   ```bash
   ipmitool -I lanplus -H <IDRAC_IP> -U root -P <PASSWORD> raw 0x30 0x30 0x02 0xff 0x<HEX>
   ```
   - Example: `0x0a` = 10%, `0x14` = 20%, `0x32` = 50%

3. **Enable Automatic Fan Mode:**
   ```bash
   ipmitool -I lanplus -H <IDRAC_IP> -U root -P <PASSWORD> raw 0x30 0x30 0x01 0x01
   ```

## Tested Configuration

- **Server Model:** Dell PowerEdge R720
- **iDRAC Version:** (varies)
- **Fan Control:** Successfully controlling 6 fans
- **Temperature Monitoring:** Working via sysfs and IPMI

## Installation Notes

The installation process is identical for R720 and R730:

1. Clone the repository
2. Copy `env.example` to `.env`
3. Configure your iDRAC IP, username, and password
4. Run `./install.sh`
5. Enable and start the service

## Compatibility

This fan control solution now works on:
- ✅ Dell PowerEdge R720 (tested and verified - January 31, 2026)
- ✅ Dell PowerEdge R730 (tested and verified - January 31, 2026)
- ⚠️ Other Dell servers (untested, but likely compatible)

### R730 Compatibility - TESTED AND CONFIRMED ✅

**IMPORTANT DISCOVERY**: R730 testing revealed that BOTH R720 and R730 require the `0x` prefix!

#### Test Results (R730 with iDRAC Firmware 2.86):
- ✅ **NEW format (0x14)**: WORKS - `ipmitool raw 0x30 0x30 0x02 0xff 0x14`
- ❌ **OLD format (1e)**: FAILS - `ipmitool raw 0x30 0x30 0x02 0xff 1e` returns "Given data '1e' is invalid"
- ✅ **Python script**: Works perfectly with the new format

#### What This Means:
1. **The fix is universal**: Both R720 and R730 require the `0x` prefix
2. **No compatibility issues**: The change improves compatibility across the board
3. **Standard compliance**: Using the `0x` prefix is the correct IPMI standard format

#### Tested Configuration (R730):
- **Server Model:** Dell PowerEdge R730
- **iDRAC Firmware:** 2.86
- **Fan Control:** Successfully controlling 6 fans
- **Temperature Monitoring:** Working correctly
- **Fan Speed Changes:** Responsive and accurate

## Notes

- The R720 requires the `0x` prefix for hex values in IPMI raw commands
- All temperature thresholds and fan speed settings work identically
- The service runs every 20 seconds by default (configurable via systemd timer)
- Fan speeds are controlled smoothly with 7 temperature levels

## Date Fixed
January 31, 2026
