# Dell PowerEdge R730 Temperature Analysis Guide

## Temperature Thresholds

### CPU/Processor Sensors
- **LOW**: < 46°C (idle or minimal load - safe)
- **MEDIUM**: 46-65°C (light to moderate load - normal operation)
- **HIGH**: 66-89°C (heavy load - monitor closely, may indicate cooling issues)
- **CRITICAL**: ≥ 90°C (risk of thermal throttling, potential stability issues)

### Inlet/Ambient/Intake Sensors
- **LOW**: < 21°C (cool ambient - safe margin)
- **MEDIUM**: 21-30°C (normal data center ambient - typical operation)
- **HIGH**: 31-35°C (approaching upper operating spec - monitor closely)
- **CRITICAL**: > 35°C (exceeds Dell's operating specification - risk of component damage)

### Exhaust/Outlet Sensors
- Generally 10-20°C warmer than inlet
- **LOW**: < 30°C
- **MEDIUM**: 30-45°C
- **HIGH**: 46-55°C
- **CRITICAL**: > 55°C

### System Board/Other Components
- **LOW**: < 40°C
- **MEDIUM**: 40-60°C
- **HIGH**: 61-80°C
- **CRITICAL**: > 80°C

## Dell R730 Operating Specifications
- **Operating Temperature Range**: 10°C to 35°C (50°F to 95°F) ambient
- **Maximum Operating Altitude**: 950m (3,117 ft) for full spec
- **Storage Temperature**: -40°C to 65°C (-40°F to 149°F)

## Notes
- Temperatures above the HIGH threshold should be investigated
- Sustained operation at CRITICAL levels can cause:
  - Thermal throttling (performance degradation)
  - Reduced component lifespan
  - System instability
  - Potential hardware failure
