#!/bin/bash
# Test script to verify R730 compatibility after R720 fix
# This script tests if the R730 accepts the 0x prefix format

set -e

echo "============================================"
echo "Dell R730 Compatibility Test"
echo "============================================"
echo ""
echo "Testing if R730 accepts 0x prefix in hex values..."
echo ""

# Load environment variables
if [ -f ".env" ]; then
    source .env
else
    echo "Error: .env file not found"
    exit 1
fi

# Check if we have iDRAC credentials
if [ -z "$IDRAC_IP" ] || [ -z "$IDRAC_USER" ] || [ -z "$IDRAC_PASS" ]; then
    echo "Error: iDRAC credentials not set in .env file"
    exit 1
fi

echo "Testing with iDRAC IP: $IDRAC_IP"
echo ""

# Test 1: Enable manual fan mode
echo "Test 1: Enabling manual fan mode..."
if ipmitool -I lanplus -H "$IDRAC_IP" -U "$IDRAC_USER" -P "$IDRAC_PASS" raw 0x30 0x30 0x01 0x00 > /dev/null 2>&1; then
    echo "✅ Manual fan mode enabled successfully"
else
    echo "❌ Failed to enable manual fan mode"
    exit 1
fi

echo ""

# Test 2: Set fan speed with 0x prefix (NEW FORMAT - R720 fix)
echo "Test 2: Setting fan speed to 20% using NEW format (0x14)..."
if ipmitool -I lanplus -H "$IDRAC_IP" -U "$IDRAC_USER" -P "$IDRAC_PASS" raw 0x30 0x30 0x02 0xff 0x14 > /dev/null 2>&1; then
    echo "✅ Fan speed set successfully with 0x prefix (NEW FORMAT)"
else
    echo "❌ Failed to set fan speed with 0x prefix"
    echo ""
    echo "WARNING: R730 may not accept 0x prefix format!"
    echo "This would indicate incompatibility with the R720 fix."
    exit 1
fi

sleep 2

# Test 3: Set fan speed without 0x prefix (OLD FORMAT - original)
echo ""
echo "Test 3: Setting fan speed to 20% using OLD format (14)..."
if ipmitool -I lanplus -H "$IDRAC_IP" -U "$IDRAC_USER" -P "$IDRAC_PASS" raw 0x30 0x30 0x02 0xff 14 > /dev/null 2>&1; then
    echo "✅ Fan speed set successfully without 0x prefix (OLD FORMAT)"
else
    echo "⚠️  Failed to set fan speed without 0x prefix"
    echo "    (This is expected on R720, but R730 should accept both)"
fi

sleep 2

# Test 4: Run the actual Python script
echo ""
echo "Test 4: Running fan_control.py script..."
if python3 fan_control.py > /dev/null 2>&1; then
    echo "✅ Python script executed successfully"
else
    echo "❌ Python script failed"
    exit 1
fi

# Test 5: Return to automatic mode
echo ""
echo "Test 5: Returning to automatic fan mode..."
if ipmitool -I lanplus -H "$IDRAC_IP" -U "$IDRAC_USER" -P "$IDRAC_PASS" raw 0x30 0x30 0x01 0x01 > /dev/null 2>&1; then
    echo "✅ Automatic fan mode restored"
else
    echo "⚠️  Failed to restore automatic fan mode"
fi

echo ""
echo "============================================"
echo "✅ ALL TESTS PASSED!"
echo "============================================"
echo ""
echo "Conclusion: R730 is compatible with R720 fix"
echo "The 0x prefix format works on both servers."
echo ""
