# Dell R730 Compatibility Testing Instructions

## Purpose
Verify that the R720 fix (adding `0x` prefix to hex values) doesn't break R730 compatibility.

---

## Quick Test (5 minutes)

### Step 1: Copy the Fixed Code to R730
Transfer the updated `fan_control.py` to your R730 system:

```bash
# From your R720 system, copy to R730
scp /root/Dell-Server-Fan-Shusher/fan_control.py root@<R730_IP>:/root/Dell-Server-Fan-Shusher/
```

### Step 2: Configure Environment
On the R730 system:

```bash
cd /root/Dell-Server-Fan-Shusher
nano .env
```

Update these values:
```bash
IDRAC_IP=<your_R730_iDRAC_IP>
IDRAC_USER=root
IDRAC_PASS=<your_password>
```

### Step 3: Run Manual Test
```bash
python3 fan_control.py
```

**Expected Output** (Success):
```
2026-01-31 XX:XX:XX,XXX - INFO - ============================================================
2026-01-31 XX:XX:XX,XXX - INFO - Dell R730 Fan Control - GPU Aware - Starting check
2026-01-31 XX:XX:XX,XXX - INFO - iDRAC IP: X.X.X.X
2026-01-31 XX:XX:XX,XXX - INFO - System Temperatures: ...
2026-01-31 XX:XX:XX,XXX - INFO - Current Fan Speeds: ...
2026-01-31 XX:XX:XX,XXX - INFO - Manual fan mode enabled
2026-01-31 XX:XX:XX,XXX - INFO - ACTION: Setting fan speed to XX%
2026-01-31 XX:XX:XX,XXX - INFO - Fan speed INCREASED/DECREASED/UNCHANGED: ...
2026-01-31 XX:XX:XX,XXX - INFO - Check complete
```

**❌ Failure Indicators**:
```
ERROR - Failed to set fan speed: Given data "0x0a" is invalid
ERROR - Failed to set fan speed: Command failed after all retries
```

---

## Detailed Test (15 minutes)

Run the automated test script:

```bash
cd /root/Dell-Server-Fan-Shusher
./TEST_R730.sh
```

### Expected Test Results

**✅ All Tests Pass (R730 Compatible):**
```
============================================
Dell R730 Compatibility Test
============================================
...
Test 1: Enabling manual fan mode...
✅ Manual fan mode enabled successfully

Test 2: Setting fan speed to 20% using NEW format (0x14)...
✅ Fan speed set successfully with 0x prefix (NEW FORMAT)

Test 3: Setting fan speed to 20% using OLD format (14)...
✅ Fan speed set successfully without 0x prefix (OLD FORMAT)

Test 4: Running fan_control.py script...
✅ Python script executed successfully

Test 5: Returning to automatic fan mode...
✅ Automatic fan mode restored

============================================
✅ ALL TESTS PASSED!
============================================
```

**❌ Failure (R730 Incompatible with fix):**
```
Test 2: Setting fan speed to 20% using NEW format (0x14)...
❌ Failed to set fan speed with 0x prefix

WARNING: R730 may not accept 0x prefix format!
This would indicate incompatibility with the R720 fix.
```

---

## Manual IPMI Command Tests

If you want to test at the IPMI level directly:

### Test NEW Format (with 0x prefix - R720 fix)
```bash
# Enable manual mode
ipmitool -I lanplus -H <R730_iDRAC_IP> -U root -P <password> raw 0x30 0x30 0x01 0x00

# Set fan speed to 20% with 0x prefix (NEW)
ipmitool -I lanplus -H <R730_iDRAC_IP> -U root -P <password> raw 0x30 0x30 0x02 0xff 0x14

# Check if it worked - should show ~20% fan speed
ipmitool -I lanplus -H <R730_iDRAC_IP> -U root -P <password> sdr list | grep -i fan
```

### Test OLD Format (without 0x prefix - original)
```bash
# Set fan speed to 30% without 0x prefix (OLD)
ipmitool -I lanplus -H <R730_iDRAC_IP> -U root -P <password> raw 0x30 0x30 0x02 0xff 1e

# Check if it worked
ipmitool -I lanplus -H <R730_iDRAC_IP> -U root -P <password> sdr list | grep -i fan
```

### Restore Automatic Mode
```bash
ipmitool -I lanplus -H <R730_iDRAC_IP> -U root -P <password> raw 0x30 0x30 0x01 0x01
```

---

## What to Report Back

Please share these results:

### 1. Python Script Output
```bash
python3 fan_control.py 2>&1 | tee r730_test_output.txt
```

### 2. Test Script Results
```bash
./TEST_R730.sh 2>&1 | tee r730_automated_test.txt
```

### 3. System Information
```bash
echo "Server Model: $(dmidecode -s system-product-name)"
echo "iDRAC Version: $(ipmitool -I lanplus -H <iDRAC_IP> -U root -P <password> mc info | grep 'Firmware Revision')"
```

---

## Expected Outcome

**High Confidence Prediction: ✅ R730 will work fine**

The R730 should accept BOTH formats because:
1. It previously accepted the non-standard format (without `0x`)
2. Lenient systems typically accept both standard and non-standard formats
3. The `0x` prefix is the official IPMI standard
4. R730 is newer and generally more flexible than R720

---

## If Tests Fail

If R730 rejects the `0x` prefix format, we have options:

### Option 1: Server Detection
Add logic to detect server model and use appropriate format:

```python
def get_server_model():
    # Detect if R720 or R730
    ...

def set_fan_speed(percentage):
    if server_model == "R720":
        hex_value = f'0x{percentage:02x}'  # With prefix
    else:
        hex_value = format(percentage, '02x')  # Without prefix
```

### Option 2: Format Testing
Try both formats automatically:

```python
def set_fan_speed(percentage):
    # Try with 0x prefix first (standard)
    hex_value = f'0x{percentage:02x}'
    success = run_ipmi_command([..., hex_value])
    
    if not success:
        # Fallback to without prefix
        hex_value = format(percentage, '02x')
        success = run_ipmi_command([..., hex_value])
    
    return success
```

### Option 3: Configuration Option
Add an environment variable:

```bash
# In .env
USE_HEX_PREFIX=true   # For R720
# or
USE_HEX_PREFIX=false  # For R730 (if needed)
```

---

## Contact & Support

When you complete testing, please share:
- ✅ Test results (pass/fail)
- 📋 Output logs
- 💻 Server model and iDRAC version

We'll update the compatibility documentation based on your findings!

---

## Rollback (If Needed)

If R730 fails and you need to rollback immediately:

```bash
cd /root/Dell-Server-Fan-Shusher
git diff fan_control.py
# Review the change

# Revert just the hex_value line
# Change: hex_value = f'0x{percentage:02x}'
# Back to: hex_value = format(percentage, '02x')
```

Or restore from backup:
```bash
# If you have git
git checkout fan_control.py
```
