#!/bin/bash

# Script to check system temperatures on Dell server via IPMI, nvidia-smi, and lm-sensors

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

# Set log file path
LOG_FILE="${SCRIPT_DIR}/temperature_log.txt"

# Get timestamp
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# Function to convert Celsius to Fahrenheit
celsius_to_fahrenheit() {
    local celsius=$1
    # F = C * 9/5 + 32
    echo "scale=1; ($celsius * 9/5) + 32" | bc
}

# Function to get GPU temperatures from nvidia-smi
get_nvidia_temps() {
    local temps=()
    if command -v nvidia-smi &> /dev/null; then
        local nvidia_output=$(nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader,nounits 2>/dev/null)
        if [ $? -eq 0 ] && [ -n "$nvidia_output" ]; then
            while IFS= read -r line; do
                if [ -n "$line" ] && [[ "$line" =~ ^[0-9]+$ ]]; then
                    temps+=("$line")
                fi
            done <<< "$nvidia_output"
        fi
    fi
    echo "${temps[@]}"
}

# Function to get temperatures from sensors (lm-sensors)
get_sensors_temps() {
    local temps=()
    if command -v sensors &> /dev/null; then
        local sensors_output=$(sensors 2>/dev/null)
        if [ $? -eq 0 ] && [ -n "$sensors_output" ]; then
            # Extract temperature values from sensors output
            # Look for patterns like "temp1: +45.0°C" or "Core 0: +50.0°C"
            while IFS= read -r line; do
                # Match temperature patterns
                if echo "$line" | grep -qE '[+\-]?[0-9]+\.[0-9]+°C'; then
                    # Extract temperature value
                    local temp=$(echo "$line" | grep -oE '[+\-]?[0-9]+\.[0-9]+' | head -1)
                    if [ -n "$temp" ]; then
                        # Convert to integer (round)
                        local temp_int=$(echo "$temp" | awk '{printf "%.0f", $1}')
                        # Only add if it's a reasonable temperature (-50 to 200°C)
                        if [ "$temp_int" -ge -50 ] && [ "$temp_int" -le 200 ]; then
                            temps+=("$temp_int")
                        fi
                    fi
                fi
            done <<< "$sensors_output"
        fi
    fi
    echo "${temps[@]}"
}

# Initialize output lines
OUTPUT_LINE="$TIMESTAMP"
OUTPUT_LINE_DISPLAY="$TIMESTAMP"
TEMP_COUNT=0

# Query temperature-related sensors from IPMI
echo "Querying temperatures from multiple sources..."
echo ""

# Check if ipmitool is installed
if command -v ipmitool &> /dev/null; then
    # Get temperature data from IPMI
    TEMP_DATA=$(ipmitool -I lanplus -H "$SERVER_IP" -U "$IPMI_USERNAME" -P "$IPMI_PASSWORD" sensor list 2>/dev/null | grep -iE "temp|temperature" | grep -v "Mem Overtemp")
    
    if [ $? -eq 0 ] && [ -n "$TEMP_DATA" ]; then
        echo "IPMI Temperatures:"
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
                    OUTPUT_LINE="$OUTPUT_LINE | IPMI_${sensor_name}:${temp_value}°C/${temp_f}°F"
                    # Display format (both Celsius and Fahrenheit)
                    echo "  $sensor_display: ${temp_value}°C / ${temp_f}°F"
                    TEMP_COUNT=$((TEMP_COUNT + 1))
                fi
            fi
        done <<< "$TEMP_DATA"
        echo ""
    else
        echo "Warning: Failed to retrieve IPMI temperature data"
        echo ""
    fi
else
    echo "Warning: ipmitool is not installed - skipping IPMI temperature check"
    echo ""
fi

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

# Get GPU temperatures from nvidia-smi
NVIDIA_TEMPS=($(get_nvidia_temps))
if [ ${#NVIDIA_TEMPS[@]} -gt 0 ]; then
    echo "NVIDIA GPU Temperatures (nvidia-smi):"
    gpu_index=0
    for temp in "${NVIDIA_TEMPS[@]}"; do
        temp_f=$(celsius_to_fahrenheit "$temp")
        OUTPUT_LINE="$OUTPUT_LINE | NVIDIA_GPU${gpu_index}:${temp}°C/${temp_f}°F"
        echo "  GPU $gpu_index: ${temp}°C / ${temp_f}°F"
        TEMP_COUNT=$((TEMP_COUNT + 1))
        gpu_index=$((gpu_index + 1))
    done
    echo ""
fi

# Get temperatures from sensors (lm-sensors)
SENSORS_TEMPS=($(get_sensors_temps))
if [ ${#SENSORS_TEMPS[@]} -gt 0 ]; then
    echo "System Temperatures (lm-sensors):"
    sensor_index=0
    for temp in "${SENSORS_TEMPS[@]}"; do
        temp_f=$(celsius_to_fahrenheit "$temp")
        OUTPUT_LINE="$OUTPUT_LINE | Sensors_Temp${sensor_index}:${temp}°C/${temp_f}°F"
        echo "  Sensor $sensor_index: ${temp}°C / ${temp_f}°F"
        TEMP_COUNT=$((TEMP_COUNT + 1))
        sensor_index=$((sensor_index + 1))
    done
    echo ""
fi

# Check if we got any temperatures
if [ $TEMP_COUNT -eq 0 ]; then
    echo "Error: No temperature data retrieved from any source"
    echo "Please verify:"
    echo "  - IPMI: Server IP is reachable, IPMI is enabled, credentials are correct"
    echo "  - NVIDIA: nvidia-smi is installed and GPUs are available"
    echo "  - Sensors: lm-sensors is installed and sensors are configured"
    exit 1
fi

# Append to log file (both Celsius and Fahrenheit)
echo "$OUTPUT_LINE" >> "$LOG_FILE"

echo "=========================================="
echo "Summary: Retrieved $TEMP_COUNT temperature readings"
echo "Data appended to: $LOG_FILE"
echo "=========================================="
echo "Temperature check completed"
echo "=========================================="
