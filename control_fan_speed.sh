#!/bin/bash

# Script to control fan speeds on Dell R730 server via IPMI
# This allows manual control to reduce noise

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

# Check if ipmitool is installed
if ! command -v ipmitool &> /dev/null; then
    echo "Error: ipmitool is not installed or not in PATH"
    echo "Please install ipmitool to use this script"
    exit 1
fi

# Function to convert percentage to hex
percent_to_hex() {
    local percent=$1
    printf "0x%02X" $percent
}

# Function to set manual fan control
set_manual_mode() {
    echo "Setting fan control to MANUAL mode..."
    ipmitool -I lanplus -H "$SERVER_IP" -U "$IPMI_USERNAME" -P "$IPMI_PASSWORD" raw 0x30 0x30 0x01 0x00
    if [ $? -eq 0 ]; then
        echo "✓ Manual mode enabled"
        return 0
    else
        echo "✗ Failed to set manual mode"
        return 1
    fi
}

# Function to set automatic fan control
set_automatic_mode() {
    echo "Setting fan control to AUTOMATIC mode..."
    ipmitool -I lanplus -H "$SERVER_IP" -U "$IPMI_USERNAME" -P "$IPMI_PASSWORD" raw 0x30 0x30 0x01 0x01
    if [ $? -eq 0 ]; then
        echo "✓ Automatic mode enabled"
        return 0
    else
        echo "✗ Failed to set automatic mode"
        return 1
    fi
}

# Function to set fan speed percentage
set_fan_speed() {
    local percent=$1
    if [ -z "$percent" ] || [ "$percent" -lt 0 ] || [ "$percent" -gt 100 ]; then
        echo "Error: Fan speed must be between 0 and 100 percent"
        return 1
    fi
    
    local hex_value=$(percent_to_hex $percent)
    echo "Setting fan speed to ${percent}% (${hex_value})..."
    
    # Command format: raw 0x30 0x30 0x02 0xff <hex_percentage>
    ipmitool -I lanplus -H "$SERVER_IP" -U "$IPMI_USERNAME" -P "$IPMI_PASSWORD" raw 0x30 0x30 0x02 0xff $hex_value
    
    if [ $? -eq 0 ]; then
        echo "✓ Fan speed set to ${percent}%"
        echo "  WARNING: Monitor temperatures closely!"
        echo "  Run './check_temperatures.sh' to verify temps stay safe"
        return 0
    else
        echo "✗ Failed to set fan speed"
        return 1
    fi
}

# Function to disable third-party cooling response
disable_third_party_cooling() {
    echo "Disabling third-party device cooling response..."
    echo "  (This helps if non-Dell hardware is causing high fan speeds)"
    ipmitool -I lanplus -H "$SERVER_IP" -U "$IPMI_USERNAME" -P "$IPMI_PASSWORD" raw 0x30 0xce 0x00 0x16 0x05 0x00 0x00 0x00 0x05 0x00 0x01 0x00 0x00
    if [ $? -eq 0 ]; then
        echo "✓ Third-party cooling response disabled"
        return 0
    else
        echo "✗ Failed to disable third-party cooling response"
        return 1
    fi
}

# Main script logic
case "$1" in
    manual)
        set_manual_mode
        ;;
    auto)
        set_automatic_mode
        ;;
    set)
        if [ -z "$2" ]; then
            echo "Usage: $0 set <percentage>"
            echo "Example: $0 set 25  (sets fans to 25% speed)"
            exit 1
        fi
        set_manual_mode && set_fan_speed "$2"
        ;;
    disable-third-party)
        disable_third_party_cooling
        ;;
    *)
        echo "Dell R730 Fan Speed Control"
        echo "=========================="
        echo ""
        echo "Usage: $0 <command> [options]"
        echo ""
        echo "Commands:"
        echo "  manual              - Switch to manual fan control mode"
        echo "  auto                - Switch back to automatic fan control mode"
        echo "  set <percentage>    - Set manual mode and set fan speed (0-100%)"
        echo "                        Example: $0 set 25"
        echo "  disable-third-party - Disable aggressive cooling for third-party hardware"
        echo ""
        echo "Examples:"
        echo "  $0 set 20           # Set fans to 20% (quiet, monitor temps!)"
        echo "  $0 set 30           # Set fans to 30% (moderate)"
        echo "  $0 auto             # Return to automatic control"
        echo ""
        echo "WARNING:"
        echo "  - Always monitor temperatures when using manual fan control"
        echo "  - Start with 20-30% and verify temps stay safe"
        echo "  - Use './check_temperatures.sh' to monitor"
        echo "  - Return to auto mode if temperatures rise too high"
        exit 1
        ;;
esac
