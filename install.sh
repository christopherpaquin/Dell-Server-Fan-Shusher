#!/bin/bash
#
# Installation script for Dell R730 Fan Control - GPU Aware
# This script sets up the fan control system, including cron jobs or systemd service
#

set -e  # Exit on error
set -u  # Exit on undefined variable
set -o pipefail  # Exit on pipe failure

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SCRIPT_NAME="fan_control.py"
ENV_EXAMPLE="env.example"
ENV_FILE=".env"
SERVICE_FILE="dell-r730-fan-control.service"
TIMER_FILE="dell-r730-fan-control.timer"

# Default values
INSTALL_METHOD=""
CRON_INTERVAL=30  # seconds
LOG_DIR="/var/log"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Dell R730 Fan Control - Installation${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${YELLOW}Warning: Not running as root. Some operations may require sudo.${NC}"
    SUDO="sudo"
else
    SUDO=""
fi

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check dependencies
echo -e "${GREEN}Checking dependencies...${NC}"
MISSING_DEPS=()

if ! command_exists python3; then
    MISSING_DEPS+=("python3")
fi

if ! command_exists ipmitool; then
    MISSING_DEPS+=("ipmitool")
fi

# Check for GPU monitoring tools (at least one should be available)
GPU_TOOL_FOUND=false
if command_exists nvidia-smi; then
    echo -e "${GREEN}Found: nvidia-smi (NVIDIA GPU support)${NC}"
    GPU_TOOL_FOUND=true
fi
if command_exists rocm-smi; then
    echo -e "${GREEN}Found: rocm-smi (AMD GPU support)${NC}"
    GPU_TOOL_FOUND=true
fi
if command_exists intel_gpu_top; then
    echo -e "${GREEN}Found: intel_gpu_top (Intel GPU support)${NC}"
    GPU_TOOL_FOUND=true
fi
if command_exists sensors; then
    echo -e "${GREEN}Found: sensors (lm-sensors - AMD/Intel GPU support)${NC}"
    GPU_TOOL_FOUND=true
fi

if [ "$GPU_TOOL_FOUND" = false ]; then
    echo -e "${YELLOW}Warning: No GPU monitoring tools found.${NC}"
    echo -e "${YELLOW}  Install one of the following for GPU temperature monitoring:${NC}"
    echo -e "${YELLOW}    - NVIDIA: nvidia-smi (NVIDIA drivers)${NC}"
    echo -e "${YELLOW}    - AMD: rocm-smi (ROCm) or sensors (lm-sensors)${NC}"
    echo -e "${YELLOW}    - Intel: intel_gpu_top (intel-gpu-tools) or sensors (lm-sensors)${NC}"
    echo -e "${YELLOW}  Script will use system temperatures only.${NC}"
fi

if [ ${#MISSING_DEPS[@]} -ne 0 ]; then
    echo -e "${RED}Missing dependencies: ${MISSING_DEPS[*]}${NC}"
    echo "Please install missing dependencies and run this script again."
    exit 1
fi

echo -e "${GREEN}All required dependencies found.${NC}"
echo ""

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "Python version: $PYTHON_VERSION"

# Install Python dependencies
echo ""
echo -e "${GREEN}Installing Python dependencies...${NC}"
if [ -f "$SCRIPT_DIR/requirements.txt" ]; then
    if pip3 install -r "$SCRIPT_DIR/requirements.txt" --user 2>/dev/null; then
        echo -e "${GREEN}Python dependencies installed.${NC}"
    else
        echo -e "${YELLOW}Warning: Failed to install Python dependencies as user. Trying with sudo...${NC}"
        if $SUDO pip3 install -r "$SCRIPT_DIR/requirements.txt"; then
            echo -e "${GREEN}Python dependencies installed with sudo.${NC}"
        else
            echo -e "${RED}Error: Failed to install Python dependencies.${NC}"
            echo -e "${RED}Please install manually: pip3 install -r requirements.txt${NC}"
            exit 1
        fi
    fi
else
    echo -e "${YELLOW}Warning: requirements.txt not found. Installing python-dotenv...${NC}"
    if pip3 install python-dotenv --user 2>/dev/null || $SUDO pip3 install python-dotenv; then
        echo -e "${GREEN}python-dotenv installed.${NC}"
    else
        echo -e "${RED}Error: Failed to install python-dotenv.${NC}"
        exit 1
    fi
fi

# Verify python-dotenv is installed
if ! python3 -c "import dotenv" 2>/dev/null; then
    echo -e "${RED}Error: python-dotenv module not found after installation.${NC}"
    exit 1
fi
echo ""

# Create .env file if it doesn't exist
if [ ! -f "$SCRIPT_DIR/$ENV_FILE" ]; then
    echo -e "${GREEN}Creating .env file from template...${NC}"
    if [ -f "$SCRIPT_DIR/$ENV_EXAMPLE" ]; then
        if cp "$SCRIPT_DIR/$ENV_EXAMPLE" "$SCRIPT_DIR/$ENV_FILE"; then
            echo -e "${GREEN}.env file created successfully.${NC}"
            echo -e "${YELLOW}Please edit $SCRIPT_DIR/$ENV_FILE with your iDRAC credentials and settings.${NC}"
        else
            echo -e "${RED}Error: Failed to create .env file.${NC}"
            exit 1
        fi
    else
        echo -e "${RED}Error: $ENV_EXAMPLE not found in $SCRIPT_DIR${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}.env file already exists.${NC}"
fi

# Verify .env file is readable
if [ ! -r "$SCRIPT_DIR/$ENV_FILE" ]; then
    echo -e "${RED}Error: Cannot read .env file. Check permissions.${NC}"
    exit 1
fi
echo ""

# Verify main script exists
if [ ! -f "$SCRIPT_DIR/$SCRIPT_NAME" ]; then
    echo -e "${RED}Error: $SCRIPT_NAME not found in $SCRIPT_DIR${NC}"
    exit 1
fi

# Make script executable
echo -e "${GREEN}Setting script permissions...${NC}"
if chmod +x "$SCRIPT_DIR/$SCRIPT_NAME"; then
    echo "Script is now executable."
else
    echo -e "${RED}Error: Failed to make script executable.${NC}"
    exit 1
fi

# Verify script syntax
echo -e "${GREEN}Validating script syntax...${NC}"
if python3 -m py_compile "$SCRIPT_DIR/$SCRIPT_NAME" 2>/dev/null; then
    echo "Script syntax is valid."
else
    echo -e "${RED}Error: Script has syntax errors.${NC}"
    exit 1
fi
echo ""

# Create log directory
LOG_FILE_PATH=$(grep "^LOG_FILE=" "$SCRIPT_DIR/$ENV_FILE" 2>/dev/null | cut -d'=' -f2 | tr -d '"' || echo "/var/log/dell-r730-fan-control.log")
LOG_DIR_PATH=$(dirname "$LOG_FILE_PATH")

if [ ! -d "$LOG_DIR_PATH" ]; then
    echo -e "${GREEN}Creating log directory: $LOG_DIR_PATH${NC}"
    $SUDO mkdir -p "$LOG_DIR_PATH"
    $SUDO chmod 755 "$LOG_DIR_PATH"
fi

# Set log file permissions if it exists
if [ -f "$LOG_FILE_PATH" ]; then
    $SUDO chmod 644 "$LOG_FILE_PATH" 2>/dev/null || true
fi
echo ""

# Ask for installation method
echo -e "${GREEN}Select installation method:${NC}"
echo "1) Systemd service (recommended)"
echo "2) Cron job"
echo "3) Skip (manual setup)"
read -p "Enter choice [1-3]: " INSTALL_CHOICE

case $INSTALL_CHOICE in
    1)
        INSTALL_METHOD="systemd"
        ;;
    2)
        INSTALL_METHOD="cron"
        ;;
    3)
        INSTALL_METHOD="skip"
        echo -e "${YELLOW}Skipping automatic service setup.${NC}"
        ;;
    *)
        echo -e "${RED}Invalid choice. Skipping automatic service setup.${NC}"
        INSTALL_METHOD="skip"
        ;;
esac

# Install systemd service
if [ "$INSTALL_METHOD" = "systemd" ]; then
    echo ""
    echo -e "${GREEN}Installing systemd service...${NC}"
    
    # Update service file with correct paths
    # Note: EnvironmentFile removed to avoid SELinux issues
    # The script loads .env file itself using python-dotenv
    SERVICE_CONTENT="[Unit]
Description=Dell R730 Fan Control - GPU Aware
After=network.target

[Service]
Type=oneshot
User=root
WorkingDirectory=$SCRIPT_DIR
ExecStart=$(which python3) $SCRIPT_DIR/$SCRIPT_NAME
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target"

    # Update timer file
    read -p "Enter check interval in seconds [30]: " TIMER_INTERVAL
    TIMER_INTERVAL=${TIMER_INTERVAL:-30}
    
    TIMER_CONTENT="[Unit]
Description=Run Dell R730 Fan Control periodically
Requires=dell-r730-fan-control.service

[Timer]
OnBootSec=1min
OnUnitActiveSec=${TIMER_INTERVAL}s
AccuracySec=1s

[Install]
WantedBy=timers.target"

    # Write service file
    if echo "$SERVICE_CONTENT" | $SUDO tee "/etc/systemd/system/$SERVICE_FILE" > /dev/null; then
        echo "Service file created."
    else
        echo -e "${RED}Error: Failed to create service file.${NC}"
        exit 1
    fi
    
    if echo "$TIMER_CONTENT" | $SUDO tee "/etc/systemd/system/$TIMER_FILE" > /dev/null; then
        echo "Timer file created."
    else
        echo -e "${RED}Error: Failed to create timer file.${NC}"
        exit 1
    fi
    
    # Reload systemd
    if $SUDO systemctl daemon-reload; then
        echo "Systemd daemon reloaded."
    else
        echo -e "${RED}Error: Failed to reload systemd daemon.${NC}"
        exit 1
    fi
    
    # Enable timer
    if $SUDO systemctl enable "$TIMER_FILE"; then
        echo "Timer enabled."
    else
        echo -e "${RED}Error: Failed to enable timer.${NC}"
        exit 1
    fi
    
    # Start timer
    if $SUDO systemctl start "$TIMER_FILE"; then
        echo "Timer started."
    else
        echo -e "${RED}Error: Failed to start timer.${NC}"
        echo -e "${YELLOW}You may need to check the service manually.${NC}"
    fi
    
    # Verify timer is active
    if $SUDO systemctl is-active --quiet "$TIMER_FILE"; then
        echo -e "${GREEN}Systemd service installed and started successfully.${NC}"
    else
        echo -e "${YELLOW}Warning: Timer may not be active. Check status manually.${NC}"
    fi
    
    echo "Service will run every ${TIMER_INTERVAL} seconds."
    echo ""
    echo "Useful commands:"
    echo "  Check status: $SUDO systemctl status dell-r730-fan-control.timer"
    echo "  View logs: $SUDO journalctl -u dell-r730-fan-control.service -f"
    echo "  Stop: $SUDO systemctl stop dell-r730-fan-control.timer"
    echo "  Start: $SUDO systemctl start dell-r730-fan-control.timer"
    echo ""

# Install cron job
elif [ "$INSTALL_METHOD" = "cron" ]; then
    echo ""
    echo -e "${GREEN}Installing cron job...${NC}"
    
    read -p "Enter check interval in seconds [30]: " CRON_INTERVAL
    CRON_INTERVAL=${CRON_INTERVAL:-30}
    
    PYTHON_PATH=$(which python3)
    CRON_CMD="$PYTHON_PATH $SCRIPT_DIR/$SCRIPT_NAME"
    
    # Calculate cron schedule
    if [ "$CRON_INTERVAL" -ge 60 ]; then
        # For intervals >= 60 seconds, use standard cron format
        CRON_MIN=$(($CRON_INTERVAL / 60))
        CRON_ENTRY="*/$CRON_MIN * * * * $CRON_CMD"
        if (crontab -l 2>/dev/null | grep -v "$SCRIPT_NAME"; echo "$CRON_ENTRY") | crontab -; then
            echo -e "${GREEN}Cron job installed to run every $CRON_MIN minutes.${NC}"
        else
            echo -e "${RED}Error: Failed to install cron job.${NC}"
            exit 1
        fi
    else
        # For intervals < 60 seconds, use two entries
        CRON_ENTRY1="* * * * * $CRON_CMD"
        CRON_ENTRY2="* * * * * sleep $CRON_INTERVAL; $CRON_CMD"
        if (crontab -l 2>/dev/null | grep -v "$SCRIPT_NAME"; echo "$CRON_ENTRY1"; echo "$CRON_ENTRY2") | crontab -; then
            echo -e "${GREEN}Cron job installed to run every $CRON_INTERVAL seconds.${NC}"
        else
            echo -e "${RED}Error: Failed to install cron job.${NC}"
            exit 1
        fi
    fi
    
    # Verify cron job was added
    echo ""
    echo "Current crontab entries:"
    if crontab -l 2>/dev/null | grep "$SCRIPT_NAME"; then
        echo -e "${GREEN}Cron job verified.${NC}"
    else
        echo -e "${YELLOW}Warning: Cron job not found in crontab.${NC}"
    fi
    echo ""
fi

# Test run
echo -e "${GREEN}Performing test run...${NC}"
echo ""

# Check if .env has been configured
DEFAULT_PASS_DETECTED=false
if grep -q "^IDRAC_PASS=" "$SCRIPT_DIR/$ENV_FILE" 2>/dev/null; then
    ENV_PASS=$(grep "^IDRAC_PASS=" "$SCRIPT_DIR/$ENV_FILE" 2>/dev/null | cut -d'=' -f2 | tr -d '"' | tr -d "'")
    if [ "$ENV_PASS" = "calvin" ]; then
        DEFAULT_PASS_DETECTED=true
    fi
fi

if [ "$DEFAULT_PASS_DETECTED" = true ]; then
    echo -e "${YELLOW}Warning: Default password detected in .env file.${NC}"
    echo -e "${YELLOW}Please update $SCRIPT_DIR/$ENV_FILE with your actual iDRAC credentials before running.${NC}"
    read -p "Continue with test run anyway? [y/N]: " TEST_RUN
    if [[ ! "$TEST_RUN" =~ ^[Yy]$ ]]; then
        echo "Skipping test run."
        echo -e "${YELLOW}Remember to update .env file before using the script!${NC}"
    else
        echo "Running test with default credentials..."
        if python3 "$SCRIPT_DIR/$SCRIPT_NAME" 2>&1; then
            echo -e "${GREEN}Test run completed.${NC}"
        else
            echo -e "${YELLOW}Test run completed with warnings (may be due to default credentials).${NC}"
        fi
    fi
else
    echo "Running test..."
    if python3 "$SCRIPT_DIR/$SCRIPT_NAME" 2>&1; then
        echo -e "${GREEN}Test run completed successfully.${NC}"
    else
        echo -e "${YELLOW}Warning: Test run completed with errors. Check the output above.${NC}"
        echo -e "${YELLOW}You may need to verify your iDRAC credentials in .env file.${NC}"
    fi
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Installation Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Summary:"
echo "  Script location: $SCRIPT_DIR/$SCRIPT_NAME"
echo "  Config file: $SCRIPT_DIR/$ENV_FILE"
echo "  Log file: $LOG_FILE_PATH"
if [ "$INSTALL_METHOD" = "systemd" ]; then
    echo "  Service: systemd timer (every ${TIMER_INTERVAL}s)"
    echo ""
    echo -e "${GREEN}Checking service status...${NC}"
    echo ""
    # Check timer status
    if $SUDO systemctl is-active --quiet "$TIMER_FILE" 2>/dev/null; then
        echo -e "${GREEN}✓ Timer is active${NC}"
    else
        echo -e "${YELLOW}⚠ Timer is not active${NC}"
    fi
    
    # Show timer status
    echo ""
    echo "Timer status:"
    $SUDO systemctl status "$TIMER_FILE" --no-pager -l | head -10 || true
    
    # Check if service has run
    echo ""
    echo "Last service run:"
    if $SUDO systemctl is-failed --quiet "$SERVICE_FILE" 2>/dev/null; then
        echo -e "${RED}✗ Service failed on last run${NC}"
        echo "Recent errors:"
        $SUDO journalctl -u "$SERVICE_FILE" -n 5 --no-pager || true
    else
        echo -e "${GREEN}✓ Service appears to be working${NC}"
        echo "Recent output:"
        $SUDO journalctl -u "$SERVICE_FILE" -n 10 --no-pager | tail -5 || true
    fi
    
elif [ "$INSTALL_METHOD" = "cron" ]; then
    echo "  Service: cron job (every ${CRON_INTERVAL}s)"
    echo ""
    echo -e "${GREEN}Current crontab entries:${NC}"
    echo ""
    if crontab -l 2>/dev/null | grep -q "$SCRIPT_NAME"; then
        echo -e "${GREEN}✓ Cron jobs found:${NC}"
        crontab -l 2>/dev/null | grep "$SCRIPT_NAME" | while read line; do
            echo "  $line"
        done
    else
        echo -e "${YELLOW}⚠ No cron jobs found for $SCRIPT_NAME${NC}"
        echo "  Current crontab:"
        crontab -l 2>/dev/null | sed 's/^/    /' || echo "    (empty)"
    fi
    echo ""
    echo "To view all crontab entries: crontab -l"
fi

echo ""
echo -e "${YELLOW}Next steps:${NC}"
if [ "$DEFAULT_PASS_DETECTED" = true ]; then
    echo -e "${RED}  1. ⚠️  IMPORTANT: Edit $SCRIPT_DIR/$ENV_FILE with your actual iDRAC credentials${NC}"
else
    echo "  1. Edit $SCRIPT_DIR/$ENV_FILE with your iDRAC credentials (if not already done)"
fi
echo "  2. Adjust temperature thresholds and fan speeds as needed"
echo "  3. Test manually:"
echo "     - Check temperatures (GPU + System): python3 $SCRIPT_DIR/$SCRIPT_NAME --temps"
echo "     - Check fan speeds: python3 $SCRIPT_DIR/$SCRIPT_NAME --fans"
echo "     - View help: python3 $SCRIPT_DIR/$SCRIPT_NAME --help"
echo "  4. Monitor logs: tail -f $LOG_FILE_PATH"
echo ""
echo -e "${GREEN}Installation script completed successfully!${NC}"
echo ""

