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

# Format fan speeds on one line: timestamp, fan_name:rpm_value (repeated for each fan)
OUTPUT_LINE="$TIMESTAMP"
while IFS= read -r line; do
    if [ -n "$line" ]; then
        # Extract fan name (first field before |)
        fan_name=$(echo "$line" | awk -F'|' '{print $1}' | xargs | tr ' ' '_')
        # Extract RPM value (second field, get numeric value)
        rpm_value=$(echo "$line" | awk -F'|' '{print $2}' | grep -oE '[0-9]+\.?[0-9]*' | head -1)
        if [ -n "$rpm_value" ]; then
            OUTPUT_LINE="$OUTPUT_LINE | ${fan_name}:${rpm_value}"
        fi
    fi
done <<< "$FAN_DATA"

# Append to log file
echo "$OUTPUT_LINE" >> "$LOG_FILE"

# Also display to console
echo "$FAN_DATA"
echo ""
echo "$OUTPUT_LINE"
echo ""
echo "Data appended to: $LOG_FILE"
echo "=========================================="
echo "Fan speed check completed"
echo "=========================================="
