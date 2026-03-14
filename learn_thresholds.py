#!/usr/bin/env python3
"""
Learning/Analysis script for fan control thresholds
Analyzes historical temperature and fan speed data to suggest optimal thresholds
"""

import os
import sys
import csv
import statistics
import argparse
import shutil
from datetime import datetime, timedelta
from collections import defaultdict
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
# Default to logs/ directory in script directory
default_data_log = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs', 'fan_control_data.log')
DATA_LOG_FILE = os.getenv('DATA_LOG_FILE', default_data_log)
MIN_DATA_POINTS = 100  # Minimum data points required for learning
ANALYSIS_DAYS = 7  # Analyze last N days of data
TEMP_STABILITY_THRESHOLD = 2  # Temperature variation considered "stable" (°C)
FAN_EFFICIENCY_THRESHOLD = 5  # RPM change considered significant
AUTO_APPLY_ENABLED = os.getenv('AUTO_APPLY_LEARNING', 'false').lower() == 'true'
MAX_THRESHOLD_CHANGE = 5  # Maximum change per threshold in one update (°C)

# Target temperature ranges for optimization
TARGET_TEMP_RANGES = {
    'very_low': (0, 30),
    'low': (30, 40),
    'med_low': (40, 50),
    'med': (50, 60),
    'med_high': (60, 70),
    'high': (70, 80),
    'very_high': (80, 100)
}


def parse_data_log():
    """Parse the unified data log file."""
    data = []
    
    if not os.path.exists(DATA_LOG_FILE):
        print(f"Data log file not found: {DATA_LOG_FILE}")
        print("Run fan_control.py normally to start collecting data.")
        return []
    
    try:
        with open(DATA_LOG_FILE, 'r') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                # Format: timestamp|max_gpu|max_system|avg_fan_rpm|fan_speed_pct|gpu_temps_csv|system_temps_csv|fan_speeds_csv
                parts = line.split('|')
                if len(parts) >= 5:
                    try:
                        timestamp_str = parts[0]
                        max_gpu = float(parts[1]) if parts[1] else 0
                        max_system = float(parts[2]) if parts[2] else 0
                        avg_fan_rpm = int(parts[3]) if parts[3] else 0
                        fan_speed_pct = int(parts[4]) if parts[4] else 0
                        
                        timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                        
                        # Only include recent data
                        cutoff_date = datetime.now() - timedelta(days=ANALYSIS_DAYS)
                        if timestamp >= cutoff_date:
                            data.append({
                                'timestamp': timestamp,
                                'max_gpu': max_gpu,
                                'max_system': max_system,
                                'avg_fan_rpm': avg_fan_rpm,
                                'fan_speed_pct': fan_speed_pct,
                                'max_temp': max(max_gpu, max_system)
                            })
                    except (ValueError, IndexError) as e:
                        continue
    except Exception as e:
        print(f"Error reading data log: {e}")
        return []
    
    return sorted(data, key=lambda x: x['timestamp'])


def analyze_fan_efficiency(data):
    """Analyze fan efficiency - find optimal fan speeds for temperature ranges."""
    # Group data by fan speed percentage
    by_fan_pct = defaultdict(list)
    
    for entry in data:
        if entry['fan_speed_pct'] > 0:
            by_fan_pct[entry['fan_speed_pct']].append(entry)
    
    efficiency_analysis = {}
    
    for fan_pct, entries in by_fan_pct.items():
        if len(entries) < 10:  # Need minimum entries for analysis
            continue
        
        temps = [e['max_temp'] for e in entries]
        rpms = [e['avg_fan_rpm'] for e in entries]
        
        avg_temp = statistics.mean(temps)
        temp_std = statistics.stdev(temps) if len(temps) > 1 else 0
        avg_rpm = statistics.mean(rpms)
        
        efficiency_analysis[fan_pct] = {
            'avg_temp': avg_temp,
            'temp_std': temp_std,
            'avg_rpm': avg_rpm,
            'sample_count': len(entries),
            'temp_range': (min(temps), max(temps))
        }
    
    return efficiency_analysis


def suggest_threshold_adjustments(data, current_thresholds):
    """Suggest threshold adjustments based on historical data."""
    suggestions = []
    
    if len(data) < MIN_DATA_POINTS:
        return suggestions, f"Insufficient data: {len(data)} points (need {MIN_DATA_POINTS})"
    
    # Analyze temperature stability at different fan speeds
    efficiency = analyze_fan_efficiency(data)
    
    # Find optimal temperature ranges for each fan speed level
    fan_speed_levels = [10, 15, 25, 35, 50, 65, 80]  # Current 7 levels
    
    for level in fan_speed_levels:
        if level not in efficiency:
            continue
        
        eff = efficiency[level]
        avg_temp = eff['avg_temp']
        temp_std = eff['temp_std']
        
        # If temperature is stable at this fan speed, we can optimize
        if temp_std < TEMP_STABILITY_THRESHOLD:
            # Find which threshold this corresponds to
            threshold_name = None
            if level == 10:
                threshold_name = 'SYSTEM_TEMP_VERY_LOW'
            elif level == 15:
                threshold_name = 'SYSTEM_TEMP_LOW'
            elif level == 25:
                threshold_name = 'SYSTEM_TEMP_MED_LOW'
            elif level == 35:
                threshold_name = 'SYSTEM_TEMP_MED'
            elif level == 50:
                threshold_name = 'SYSTEM_TEMP_MED_HIGH'
            elif level == 65:
                threshold_name = 'SYSTEM_TEMP_HIGH'
            elif level == 80:
                threshold_name = 'SYSTEM_TEMP_VERY_HIGH'
            
            if threshold_name:
                current_thresh = current_thresholds.get(threshold_name.lower(), None)
                if current_thresh:
                    # Suggest adjustment if there's a significant difference
                    suggested_temp = int(avg_temp + (temp_std * 2))  # Add 2 std devs for safety margin
                    
                    if abs(suggested_temp - current_thresh) > 2:  # Only suggest if >2°C difference
                        suggestions.append({
                            'threshold': threshold_name,
                            'current': current_thresh,
                            'suggested': suggested_temp,
                            'reason': f"Fan speed {level}% maintains stable temp at {avg_temp:.1f}°C (±{temp_std:.1f}°C)",
                            'confidence': 'high' if eff['sample_count'] > 50 else 'medium'
                        })
    
    return suggestions, f"Analyzed {len(data)} data points"


def analyze_temperature_trends(data):
    """Analyze temperature trends to detect if fans are too low or too high."""
    if len(data) < 50:
        return None
    
    # Group by fan speed percentage
    by_fan_pct = defaultdict(list)
    for entry in data:
        if entry['fan_speed_pct'] > 0:
            by_fan_pct[entry['fan_speed_pct']].append(entry)
    
    trends = {}
    
    for fan_pct, entries in by_fan_pct.items():
        if len(entries) < 20:
            continue
        
        temps = [e['max_temp'] for e in entries]
        
        # Check if temperatures are rising over time (fan too low)
        recent_temps = temps[-20:]  # Last 20 entries
        older_temps = temps[:20] if len(temps) >= 40 else temps[:len(temps)//2]
        
        if len(recent_temps) > 0 and len(older_temps) > 0:
            recent_avg = statistics.mean(recent_temps)
            older_avg = statistics.mean(older_temps)
            
            temp_increase = recent_avg - older_avg
            
            if temp_increase > 3:  # Temperature rising significantly
                trends[fan_pct] = {
                    'issue': 'fan_too_low',
                    'temp_increase': temp_increase,
                    'current_avg': recent_avg,
                    'suggestion': f"Consider increasing fan speed from {fan_pct}% or lowering temperature threshold"
                }
            elif temp_increase < -3:  # Temperature decreasing (fan might be too high)
                trends[fan_pct] = {
                    'issue': 'fan_too_high',
                    'temp_decrease': abs(temp_increase),
                    'current_avg': recent_avg,
                    'suggestion': f"Consider decreasing fan speed from {fan_pct}% or raising temperature threshold"
                }
    
    return trends


def load_current_thresholds():
    """Load current thresholds from .env file."""
    thresholds = {}
    
    env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    if os.path.exists(env_file):
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if '=' in line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    # Extract temperature thresholds
                    if 'TEMP' in key and 'THRESHOLD' not in key:
                        try:
                            thresholds[key.lower()] = int(value)
                        except ValueError:
                            pass
    
    return thresholds


def apply_threshold_updates(suggestions, auto_apply=False):
    """Apply threshold updates to .env file."""
    if not suggestions:
        return False, "No suggestions to apply"
    
    env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    if not os.path.exists(env_file):
        return False, f".env file not found: {env_file}"
    
    # Filter suggestions based on safety criteria
    safe_suggestions = []
    for sug in suggestions:
        change = abs(sug['suggested'] - sug['current'])
        # Only apply if:
        # 1. High confidence
        # 2. Change is reasonable (not too drastic)
        # 3. Change is significant enough (>2°C)
        if (sug['confidence'] == 'high' and 
            change <= MAX_THRESHOLD_CHANGE and 
            change > 2):
            safe_suggestions.append(sug)
    
    if not safe_suggestions:
        return False, "No safe suggestions to apply (all require manual review)"
    
    # Create backup
    backup_file = f"{env_file}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    try:
        shutil.copy2(env_file, backup_file)
    except Exception as e:
        return False, f"Failed to create backup: {e}"
    
    # Read current .env file
    try:
        with open(env_file, 'r') as f:
            lines = f.readlines()
    except Exception as e:
        return False, f"Failed to read .env file: {e}"
    
    # Update thresholds
    updated_count = 0
    new_lines = []
    for line in lines:
        updated = False
        for sug in safe_suggestions:
            # Match threshold name (case-insensitive)
            threshold_key = sug['threshold']
            if line.strip().startswith(threshold_key + '=') or line.strip().startswith(threshold_key.upper() + '='):
                # Preserve comments and formatting
                if '#' in line:
                    comment = line[line.index('#'):]
                    new_lines.append(f"{threshold_key}={sug['suggested']}  {comment}")
                else:
                    new_lines.append(f"{threshold_key}={sug['suggested']}\n")
                updated = True
                updated_count += 1
                break
        
        if not updated:
            new_lines.append(line)
    
    # Write updated .env file
    try:
        with open(env_file, 'w') as f:
            f.writelines(new_lines)
    except Exception as e:
        # Restore backup on failure
        try:
            shutil.copy2(backup_file, env_file)
        except:
            pass
        return False, f"Failed to write .env file: {e}"
    
    return True, f"Applied {updated_count} threshold updates. Backup saved to {backup_file}"


def generate_report(data, suggestions, trends, auto_apply=False, apply_result=None):
    """Generate a learning report."""
    print("=" * 70)
    print("Fan Control Threshold Learning Report")
    print("=" * 70)
    print()
    
    if not data:
        print("No data available for analysis.")
        print("Run fan_control.py normally to start collecting data.")
        return
    
    print(f"Data Analysis:")
    print(f"  Total data points: {len(data)}")
    if data:
        print(f"  Date range: {data[0]['timestamp'].strftime('%Y-%m-%d %H:%M:%S')} to {data[-1]['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  Average max temperature: {statistics.mean([d['max_temp'] for d in data]):.1f}°C")
        print(f"  Temperature range: {min([d['max_temp'] for d in data]):.1f}°C - {max([d['max_temp'] for d in data]):.1f}°C")
    print()
    
    # Efficiency analysis
    efficiency = analyze_fan_efficiency(data)
    if efficiency:
        print("Fan Speed Efficiency Analysis:")
        for fan_pct in sorted(efficiency.keys()):
            eff = efficiency[fan_pct]
            print(f"  {fan_pct:3d}%: Avg temp {eff['avg_temp']:.1f}°C (±{eff['temp_std']:.1f}°C), "
                  f"Avg RPM {eff['avg_rpm']:.0f}, Samples: {eff['sample_count']}")
        print()
    
    # Temperature trends
    if trends:
        print("Temperature Trend Analysis:")
        for fan_pct, trend in sorted(trends.items()):
            print(f"  Fan Speed {fan_pct}%: {trend['suggestion']}")
        print()
    
    # Suggestions
    if suggestions:
        print("Suggested Threshold Adjustments:")
        safe_suggestions = []
        for sug in suggestions:
            change = abs(sug['suggested'] - sug['current'])
            confidence_icon = "✓" if sug['confidence'] == 'high' else "~"
            safety_note = ""
            
            # Mark safe suggestions
            if (sug['confidence'] == 'high' and 
                change <= MAX_THRESHOLD_CHANGE and 
                change > 2):
                safety_note = " [SAFE TO AUTO-APPLY]"
                safe_suggestions.append(sug)
            elif change > MAX_THRESHOLD_CHANGE:
                safety_note = " [REQUIRES MANUAL REVIEW - Change too large]"
            elif sug['confidence'] != 'high':
                safety_note = " [REQUIRES MANUAL REVIEW - Low confidence]"
            
            print(f"  {confidence_icon} {sug['threshold']}: {sug['current']}°C → {sug['suggested']}°C{safety_note}")
            print(f"     Reason: {sug['reason']}")
        
        print()
        
        # Auto-apply result
        if auto_apply:
            if apply_result[0]:
                print(f"✓ AUTO-APPLIED: {apply_result[1]}")
            else:
                print(f"✗ AUTO-APPLY FAILED: {apply_result[1]}")
            print()
        else:
            if safe_suggestions:
                print(f"Note: {len(safe_suggestions)} suggestion(s) are safe to auto-apply.")
                print("      Enable AUTO_APPLY_LEARNING=true in .env to apply automatically.")
            print("To apply suggestions manually, update your .env file with the new values.")
    else:
        print("No threshold adjustments suggested at this time.")
        print("Current thresholds appear to be working well.")
    
    print("=" * 70)


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Analyze fan control data and optimize thresholds')
    parser.add_argument('--auto-apply', action='store_true',
                        help='Automatically apply safe threshold updates to .env file')
    args = parser.parse_args()
    
    # Determine if auto-apply should be enabled
    auto_apply = args.auto_apply or AUTO_APPLY_ENABLED
    
    print("Analyzing fan control data for threshold optimization...")
    if auto_apply:
        print("Auto-apply mode: ENABLED (safe suggestions will be applied automatically)")
    print()
    
    # Load current thresholds
    current_thresholds = load_current_thresholds()
    
    # Parse data
    data = parse_data_log()
    
    if not data:
        return
    
    # Analyze
    suggestions, analysis_msg = suggest_threshold_adjustments(data, current_thresholds)
    trends = analyze_temperature_trends(data)
    
    # Apply updates if requested
    apply_result = None
    if auto_apply and suggestions:
        apply_result = apply_threshold_updates(suggestions, auto_apply=True)
    
    # Generate report
    generate_report(data, suggestions, trends, auto_apply=auto_apply, apply_result=apply_result)
    
    print(f"\nAnalysis: {analysis_msg}")
    
    # Exit with appropriate code
    if auto_apply and apply_result and not apply_result[0]:
        sys.exit(1)


if __name__ == '__main__':
    main()
