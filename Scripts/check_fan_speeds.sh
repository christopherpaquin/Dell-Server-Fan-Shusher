#!/bin/bash

# Script to check fan speeds on Dell server via IPMI

# Load configuration from environment file
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/ipmi_config.env"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: Configuration file not found: $CONFIG_FILE"
    exit 1
fi

# Source the configuration file
source "$CONFIG_FILE"

# Validate required variables
if [ -z "$SERVER_IP" ] || [ -z "$IPMI_USERNAME" ] || [ -z "$IPMI_PASSWORD" ]; then
    echo "Error: Required configuration variables not set in $CONFIG_FILE"
    echo "Required variables: SERVER_IP, IPMI_USERNAME, IPMI_PASSWORD"
    exit 1
fi

echo "=========================================="
echo "Fan Speed Check - Server: $SERVER_IP"
echo "=========================================="
echo ""

# Check if ipmitool is installed
if ! command -v ipmitool &> /dev/null; then
    echo "Error: ipmitool is not installed or not in PATH"
    echo "Please install ipmitool to use this script"
    exit 1
fi

# Set log file path
LOG_FILE="${SCRIPT_DIR}/fan_speed_log.txt"

# Query fan-related sensors
echo "Querying fan speeds..."
echo ""

# Get timestamp
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# Get fan data
FAN_DATA=$(ipmitool -I lanplus -H "$SERVER_IP" -U "$IPMI_USERNAME" -P "$IPMI_PASSWORD" sensor list 2>/dev/null | grep -i fan | grep -v "Fan Redundancy")

if [ $? -ne 0 ] || [ -z "$FAN_DATA" ]; then
    echo ""
    echo "Error: Failed to connect to server or retrieve fan data"
    echo "Please verify:"
    echo "  - Server IP is reachable: $SERVER_IP"
    echo "  - IPMI is enabled on the server"
    echo "  - Credentials are correct"
    exit 1
fi

# Maximum RPM for percentage calculation (Dell R730 typical max is ~15,000-20,000 RPM)
# Using 15,000 as a reasonable default for percentage calculation
MAX_RPM=15000

# Display formatted table with headers
echo "Fan Name                    | RPM      | Speed %"
echo "----------------------------|----------|--------"

# Arrays to store data for summary
declare -a FAN_NAMES
declare -a RPM_VALUES
declare -a PERCENTAGES

# Process each fan
FAN_COUNT=0
while IFS= read -r line; do
    if [ -n "$line" ]; then
        # Extract fan name (first field before |)
        fan_name=$(echo "$line" | awk -F'|' '{print $1}' | xargs)
        # Extract RPM value (second field, get numeric value)
        rpm_value=$(echo "$line" | awk -F'|' '{print $2}' | grep -oE '[0-9]+\.?[0-9]*' | head -1)
        
        if [ -n "$rpm_value" ]; then
            # Convert RPM to integer for calculations (remove decimal part)
            rpm_int=$(echo "$rpm_value" | cut -d. -f1)
            
            # Calculate percentage (rounded to 1 decimal place)
            percent=$(echo "scale=1; ($rpm_int / $MAX_RPM) * 100" | bc)
            # Ensure percentage doesn't exceed 100%
            if (( $(echo "$percent > 100" | bc -l) )); then
                percent=100.0
            fi
            
            # Store for summary (use integer RPM for calculations)
            FAN_NAMES[$FAN_COUNT]="$fan_name"
            RPM_VALUES[$FAN_COUNT]=$rpm_int
            PERCENTAGES[$FAN_COUNT]=$percent
            
            # Display formatted row (show original RPM value with decimals if present)
            printf "%-27s | %8s | %6s%%\n" "$fan_name" "$rpm_value" "$percent"
            
            FAN_COUNT=$((FAN_COUNT + 1))
        fi
    fi
done <<< "$FAN_DATA"

echo "----------------------------|----------|--------"

# Calculate and display summary statistics
if [ $FAN_COUNT -gt 0 ]; then
    # Calculate average RPM
    total_rpm=0
    total_percent=0
    min_rpm=${RPM_VALUES[0]}
    max_rpm=${RPM_VALUES[0]}
    
    for i in $(seq 0 $((FAN_COUNT - 1))); do
        rpm=${RPM_VALUES[$i]}
        total_rpm=$((total_rpm + rpm))
        total_percent=$(echo "$total_percent + ${PERCENTAGES[$i]}" | bc)
        
        if [ "$rpm" -lt "$min_rpm" ]; then
            min_rpm=$rpm
        fi
        if [ "$rpm" -gt "$max_rpm" ]; then
            max_rpm=$rpm
        fi
    done
    
    avg_rpm=$((total_rpm / FAN_COUNT))
    avg_percent=$(echo "scale=1; $total_percent / $FAN_COUNT" | bc)
    
    echo ""
    echo "Summary:"
    echo "  Total Fans: $FAN_COUNT"
    echo "  Average RPM: $avg_rpm RPM (${avg_percent}%)"
    echo "  Min RPM: $min_rpm RPM ($(echo "scale=1; ($min_rpm / $MAX_RPM) * 100" | bc)%)"
    echo "  Max RPM: $max_rpm RPM ($(echo "scale=1; ($max_rpm / $MAX_RPM) * 100" | bc)%)"
fi

# Format fan speeds on one line for log file: timestamp, fan_name:rpm_value:percent (repeated for each fan)
OUTPUT_LINE="$TIMESTAMP"
for i in $(seq 0 $((FAN_COUNT - 1))); do
    fan_name_log=$(echo "${FAN_NAMES[$i]}" | tr ' ' '_')
    OUTPUT_LINE="$OUTPUT_LINE | ${fan_name_log}:${RPM_VALUES[$i]}RPM:${PERCENTAGES[$i]}%"
done

# Append to log file
echo "$OUTPUT_LINE" >> "$LOG_FILE"

echo ""
echo "Data appended to: $LOG_FILE"
echo "=========================================="
echo "Fan speed check completed"
echo "=========================================="
