#!/bin/bash

# Script to analyze temperatures from Dell R730 and categorize them
# Based on Dell PowerEdge R730 specifications

# Run the temperature check and capture output
TEMP_OUTPUT=$(./check_temperatures.sh 2>&1)

# Check if the command succeeded
if [ $? -ne 0 ]; then
    echo "Error: Failed to retrieve temperature data"
    echo "$TEMP_OUTPUT"
    exit 1
fi

echo "=========================================="
echo "Temperature Analysis - Dell R730"
echo "=========================================="
echo ""

# Extract temperature readings (assuming format from ipmitool sensor list)
# This will parse lines that contain temperature values
echo "$TEMP_OUTPUT" | grep -iE "temp|temperature" | while IFS= read -r line; do
    # Extract sensor name and value
    # ipmitool sensor list format typically: Sensor Name | Value | Status | ...
    sensor_name=$(echo "$line" | awk -F'|' '{print $1}' | xargs)
    temp_value=$(echo "$line" | awk -F'|' '{print $2}' | grep -oE '[0-9]+\.?[0-9]*' | head -1)
    status=$(echo "$line" | awk -F'|' '{print $3}' | xargs)
    
    if [ -z "$temp_value" ]; then
        continue
    fi
    
    # Convert to integer for comparison
    temp_int=${temp_value%.*}
    
    # Determine sensor type and categorize
    sensor_lower=$(echo "$sensor_name" | tr '[:upper:]' '[:lower:]')
    
    if echo "$sensor_lower" | grep -qE "cpu|processor"; then
        # CPU temperature thresholds
        if [ "$temp_int" -lt 46 ]; then
            category="LOW"
            color="\033[0;32m"  # Green
        elif [ "$temp_int" -lt 66 ]; then
            category="MEDIUM"
            color="\033[0;33m"  # Yellow
        elif [ "$temp_int" -lt 90 ]; then
            category="HIGH"
            color="\033[0;31m"  # Red
        else
            category="CRITICAL"
            color="\033[1;31m"  # Bright Red
        fi
    elif echo "$sensor_lower" | grep -qE "inlet|ambient|intake|exhaust|outlet"; then
        # Ambient/Inlet temperature thresholds
        if [ "$temp_int" -lt 21 ]; then
            category="LOW"
            color="\033[0;32m"  # Green
        elif [ "$temp_int" -lt 31 ]; then
            category="MEDIUM"
            color="\033[0;33m"  # Yellow
        elif [ "$temp_int" -le 35 ]; then
            category="HIGH"
            color="\033[0;31m"  # Red
        else
            category="CRITICAL"
            color="\033[1;31m"  # Bright Red
        fi
    else
        # Generic system temperature thresholds (conservative)
        if [ "$temp_int" -lt 40 ]; then
            category="LOW"
            color="\033[0;32m"  # Green
        elif [ "$temp_int" -lt 60 ]; then
            category="MEDIUM"
            color="\033[0;33m"  # Yellow
        elif [ "$temp_int" -lt 80 ]; then
            category="HIGH"
            color="\033[0;31m"  # Red
        else
            category="CRITICAL"
            color="\033[1;31m"  # Bright Red
        fi
    fi
    
    # Print with color coding
    echo -e "${color}${category}\033[0m - $sensor_name: ${temp_value}°C (Status: $status)"
done

echo ""
echo "=========================================="
echo "Temperature Thresholds Reference:"
echo "=========================================="
echo "CPU/Processor Sensors:"
echo "  LOW:    < 46°C  (idle/minimal load)"
echo "  MEDIUM: 46-65°C (light/moderate load)"
echo "  HIGH:   66-89°C (heavy load, monitor closely)"
echo "  CRITICAL: >= 90°C (risk of throttling)"
echo ""
echo "Inlet/Ambient Sensors:"
echo "  LOW:    < 21°C  (cool ambient)"
echo "  MEDIUM: 21-30°C (normal data center)"
echo "  HIGH:   31-35°C (approaching upper spec)"
echo "  CRITICAL: > 35°C (exceeds operating spec)"
echo ""
