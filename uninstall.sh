#!/bin/bash
#
# Uninstallation script for Dell R730 Fan Control - GPU Aware
# Removes both systemd service/timer and cron jobs
#

set -e  # Exit on error
set -u  # Exit on undefined variable

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SCRIPT_NAME="fan_control.py"
SERVICE_FILE="dell-r730-fan-control.service"
TIMER_FILE="dell-r730-fan-control.timer"

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${YELLOW}Warning: Not running as root. Some operations may require sudo.${NC}"
    SUDO="sudo"
else
    SUDO=""
fi

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Dell R730 Fan Control - Uninstallation${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Check for and remove systemd service/timer
SYSTEMD_FOUND=false

# Check if timer is active
if $SUDO systemctl list-units --type=timer --all 2>/dev/null | grep -q "$TIMER_FILE"; then
    SYSTEMD_FOUND=true
    echo -e "${GREEN}Found systemd timer. Stopping and disabling...${NC}"
    $SUDO systemctl stop "$TIMER_FILE" 2>/dev/null || echo -e "${YELLOW}Timer was not running.${NC}"
    $SUDO systemctl disable "$TIMER_FILE" 2>/dev/null || echo -e "${YELLOW}Timer was not enabled.${NC}"
    echo "Timer stopped and disabled."
fi

# Check if service file exists
if [ -f "/etc/systemd/system/$SERVICE_FILE" ] || [ -f "/etc/systemd/system/$TIMER_FILE" ]; then
    SYSTEMD_FOUND=true
    echo -e "${GREEN}Removing systemd service files...${NC}"
    $SUDO rm -f "/etc/systemd/system/$SERVICE_FILE" 2>/dev/null || true
    $SUDO rm -f "/etc/systemd/system/$TIMER_FILE" 2>/dev/null || true
    
    # Reload systemd daemon
    if $SUDO systemctl daemon-reload 2>/dev/null; then
        echo "Systemd daemon reloaded."
    else
        echo -e "${YELLOW}Warning: Failed to reload systemd daemon.${NC}"
    fi
    echo "Service files removed."
fi

if [ "$SYSTEMD_FOUND" = false ]; then
    echo -e "${GREEN}No systemd service/timer found.${NC}"
fi

echo ""

# Check for and remove cron jobs
CRON_FOUND=false

# Check if cron job exists
if crontab -l 2>/dev/null | grep -q "$SCRIPT_NAME"; then
    CRON_FOUND=true
    echo -e "${GREEN}Found cron jobs. Removing...${NC}"
    
    # Get current crontab, remove entries with script name, and update
    NEW_CRONTAB=$(crontab -l 2>/dev/null | grep -v "$SCRIPT_NAME" || true)
    
    if [ -z "$NEW_CRONTAB" ]; then
        # If crontab is now empty, remove it
        crontab -r 2>/dev/null || true
        echo "Cron jobs removed (crontab is now empty)."
    else
        # Update crontab with remaining entries
        echo "$NEW_CRONTAB" | crontab -
        echo "Cron jobs removed."
    fi
    
    # Verify removal
    if crontab -l 2>/dev/null | grep -q "$SCRIPT_NAME"; then
        echo -e "${YELLOW}Warning: Some cron entries may still exist. Please check manually with: crontab -l${NC}"
    else
        echo "Cron jobs verified as removed."
    fi
else
    echo -e "${GREEN}No cron jobs found.${NC}"
fi

echo ""
echo -e "${GREEN}Uninstallation complete!${NC}"
echo ""
echo -e "${YELLOW}Note: The following files were NOT removed:${NC}"
echo "  - $SCRIPT_DIR/$SCRIPT_NAME"
echo "  - $SCRIPT_DIR/.env"
echo "  - Log files"
echo ""
echo "To remove these files manually, delete the directory:"
echo "  $SCRIPT_DIR"
echo ""

