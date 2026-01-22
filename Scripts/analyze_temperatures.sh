#!/bin/bash

# Script to analyze temperatures from Dell R730 and categorize them
# Based on Dell PowerEdge R730 specifications

# Function to convert Celsius to Fahrenheit
celsius_to_fahrenheit() {
    local celsius=$1
    # F = C * 9/5 + 32
    echo "scale=1; ($celsius * 9/5) + 32" | bc
}

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

# Extract temperature readings from check_temperatures.sh output
# Format: "2026-01-21 23:29:09 | Inlet Temp:21.000°C/69.8°F | Exhaust Temp:30.000°C/86.0°F | ..."
# Find the line with temperature data (contains timestamp and pipe separators)
TEMP_LINE=$(echo "$TEMP_OUTPUT" | grep -E "^[0-9]{4}-[0-9]{2}-[0-9]{2}.*\|" | head -1)

if [ -z "$TEMP_LINE" ]; then
    echo "Warning: Could not find temperature data in expected format"
    echo "$TEMP_OUTPUT"
    exit 1
fi

# Parse each sensor from the line (format: "Sensor Name:temp°C/temp°F")
echo "$TEMP_LINE" | awk -F'|' '{
    for (i=2; i<=NF; i++) {
        # Skip empty fields
        if ($i == "" || $i ~ /^[[:space:]]*$/) continue
        
        # Extract sensor name and temperature
        # Format: " Sensor Name:temp°C/temp°F"
        gsub(/^[[:space:]]+|[[:space:]]+$/, "", $i)  # Trim whitespace
        
        # Match pattern: "Sensor Name:number°C/number°F"
        if (match($i, /^([^:]+):([0-9]+\.[0-9]+)°C\/([0-9]+\.[0-9]+)°F$/, arr)) {
            sensor_name = arr[1]
            temp_c = arr[2]
            temp_f = arr[3]
            
            # Convert to integer for comparison
            temp_int = int(temp_c)
            
            # Determine sensor type and categorize
            sensor_lower = tolower(sensor_name)
            
            category = ""
            color = ""
            
            if (sensor_lower ~ /cpu|processor/) {
                # CPU temperature thresholds
                if (temp_int < 46) {
                    category = "LOW"
                    color = "\033[0;32m"  # Green
                } else if (temp_int < 66) {
                    category = "MEDIUM"
                    color = "\033[0;33m"  # Yellow
                } else if (temp_int < 90) {
                    category = "HIGH"
                    color = "\033[0;31m"  # Red
                } else {
                    category = "CRITICAL"
                    color = "\033[1;31m"  # Bright Red
                }
            } else if (sensor_lower ~ /inlet|ambient|intake|exhaust|outlet/) {
                # Ambient/Inlet temperature thresholds
                if (temp_int < 21) {
                    category = "LOW"
                    color = "\033[0;32m"  # Green
                } else if (temp_int < 31) {
                    category = "MEDIUM"
                    color = "\033[0;33m"  # Yellow
                } else if (temp_int <= 35) {
                    category = "HIGH"
                    color = "\033[0;31m"  # Red
                } else {
                    category = "CRITICAL"
                    color = "\033[1;31m"  # Bright Red
                }
            } else {
                # Generic system temperature thresholds (conservative)
                if (temp_int < 40) {
                    category = "LOW"
                    color = "\033[0;32m"  # Green
                } else if (temp_int < 60) {
                    category = "MEDIUM"
                    color = "\033[0;33m"  # Yellow
                } else if (temp_int < 80) {
                    category = "HIGH"
                    color = "\033[0;31m"  # Red
                } else {
                    category = "CRITICAL"
                    color = "\033[1;31m"  # Bright Red
                }
            }
            
            # Print with color coding (both Celsius and Fahrenheit)
            printf "%s%s\033[0m - %s: %s°C / %s°F\n", color, category, sensor_name, temp_c, temp_f
        }
    }
}'

echo ""
echo "=========================================="
echo "Temperature Thresholds Reference:"
echo "=========================================="
echo "CPU/Processor Sensors:"
echo "  LOW:    < 46°C  / < 115°F  (idle/minimal load)"
echo "  MEDIUM: 46-65°C / 115-149°F (light/moderate load)"
echo "  HIGH:   66-89°C / 151-192°F (heavy load, monitor closely)"
echo "  CRITICAL: >= 90°C / >= 194°F (risk of throttling)"
echo ""
echo "Inlet/Ambient Sensors:"
echo "  LOW:    < 21°C  / < 70°F   (cool ambient)"
echo "  MEDIUM: 21-30°C / 70-86°F  (normal data center)"
echo "  HIGH:   31-35°C / 88-95°F  (approaching upper spec)"
echo "  CRITICAL: > 35°C / > 95°F  (exceeds operating spec)"
echo ""
