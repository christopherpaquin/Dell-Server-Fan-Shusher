# Migration Guide: Organizing Standalone Scripts

This guide helps you organize the standalone utility scripts into the `Scripts/` directory.

## Steps to Organize Scripts

### 1. Create Scripts Directory (if not exists)
```bash
mkdir -p Scripts
```

### 2. Move Standalone Scripts
```bash
mv check_temperatures.sh Scripts/
mv check_fan_speeds.sh Scripts/
mv control_fan_speed.sh Scripts/
mv analyze_temperatures.sh Scripts/
```

### 3. Move/Create Configuration Files
```bash
# Move existing ipmi_config.env if it exists
if [ -f ipmi_config.env ]; then
    mv ipmi_config.env Scripts/
else
    # Copy example if it doesn't exist
    cp Scripts/ipmi_config.env.example Scripts/ipmi_config.env
    # Edit with your credentials
    nano Scripts/ipmi_config.env
fi
```

### 4. Move Log Files (if they exist)
```bash
# Move log files to Scripts directory if they exist
[ -f temperature_log.txt ] && mv temperature_log.txt Scripts/
[ -f fan_speed_log.txt ] && mv fan_speed_log.txt Scripts/
```

### 5. Update Script References (if needed)

The scripts are designed to work from any directory, but if you have any custom scripts or cron jobs that reference them, update the paths:

**Before:**
```bash
./check_temperatures.sh
```

**After:**
```bash
./Scripts/check_temperatures.sh
# or
cd Scripts && ./check_temperatures.sh
```

## Verification

After migration, verify the structure:

```bash
ls -la Scripts/
```

You should see:
- `check_temperatures.sh`
- `check_fan_speeds.sh`
- `control_fan_speed.sh`
- `analyze_temperatures.sh`
- `ipmi_config.env` (or `ipmi_config.env.example`)
- `README.md`

## Notes

- The scripts use relative paths, so they will work from the Scripts directory
- The `ipmi_config.env` file should be in the Scripts directory
- Log files (`temperature_log.txt`, `fan_speed_log.txt`) will be created in the Scripts directory
- All scripts are executable and ready to use
