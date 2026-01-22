#!/bin/bash

# Script to check system temperatures on Dell server via IPMI

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
echo "Temperature Check - Server: $SERVER_IP"
echo "=========================================="
echo ""

# Check if ipmitool is installed
if ! command -v ipmitool &> /dev/null; then
    echo "Error: ipmitool is not installed or not in PATH"
    echo "Please install ipmitool to use this script"
    exit 1
fi

# Set log file path
LOG_FILE="${SCRIPT_DIR}/temperature_log.txt"

# Query temperature-related sensors
echo "Querying system temperatures..."
echo ""

# Get timestamp
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# Get temperature data and format as single line
TEMP_DATA=$(ipmitool -I lanplus -H "$SERVER_IP" -U "$IPMI_USERNAME" -P "$IPMI_PASSWORD" sensor list 2>/dev/null | grep -iE "temp|temperature" | grep -v "Mem Overtemp")

if [ $? -ne 0 ] || [ -z "$TEMP_DATA" ]; then
    echo ""
    echo "Error: Failed to connect to server or retrieve temperature data"
    echo "Please verify:"
    echo "  - Server IP is reachable: $SERVER_IP"
    echo "  - IPMI is enabled on the server"
    echo "  - Credentials are correct"
    exit 1
fi

# Function to convert Celsius to Fahrenheit
celsius_to_fahrenheit() {
    local celsius=$1
    # F = C * 9/5 + 32
    echo "scale=1; ($celsius * 9/5) + 32" | bc
}

# Format temperatures on one line: timestamp, sensor_name:temp_value (repeated for each sensor)
OUTPUT_LINE="$TIMESTAMP"
OUTPUT_LINE_DISPLAY="$TIMESTAMP"
while IFS= read -r line; do
    if [ -n "$line" ]; then
        # Extract sensor name (first field before |)
        sensor_name=$(echo "$line" | awk -F'|' '{print $1}' | xargs | tr ' ' '_')
        sensor_display=$(echo "$line" | awk -F'|' '{print $1}' | xargs)
        # Extract temperature value (second field, get numeric value)
        temp_value=$(echo "$line" | awk -F'|' '{print $2}' | grep -oE '[0-9]+\.?[0-9]*' | head -1)
        if [ -n "$temp_value" ]; then
            # Convert to Fahrenheit
            temp_f=$(celsius_to_fahrenheit "$temp_value")
            # Log file format (both Celsius and Fahrenheit)
            OUTPUT_LINE="$OUTPUT_LINE | $sensor_name:${temp_value}°C/${temp_f}°F"
            # Display format (both Celsius and Fahrenheit)
            OUTPUT_LINE_DISPLAY="$OUTPUT_LINE_DISPLAY | $sensor_display:${temp_value}°C/${temp_f}°F"
        fi
    fi
done <<< "$TEMP_DATA"

# Append to log file (both Celsius and Fahrenheit)
echo "$OUTPUT_LINE" >> "$LOG_FILE"

# Display to console (both Celsius and Fahrenheit)
echo "$OUTPUT_LINE_DISPLAY"
echo ""
echo "Data appended to: $LOG_FILE"
echo "=========================================="
echo "Temperature check completed"
echo "=========================================="
