# iDRAC Redfish Timeout Optimizations

## Issue Identified
Based on Home Assistant logs and real-world testing with iDRAC at `192.168.50.131`, the integration was hitting timeout issues:

```
2025-06-27 18:16:31.227 ERROR Primary data timeout on 192.168.50.131:443 after 6.00s
2025-06-27 18:16:40.234 WARNING Redfish update took 19.52 seconds - consider optimizing
```

## Root Cause Analysis

### Test Results from `test_redfish_clean.py`:
- **Service Root**: 8.464 seconds
- **System Info**: 4.139 seconds  
- **Thermal Data**: 5.183 seconds
- **Power Data**: 4.961 seconds
- **Manager Info**: 7.440 seconds
- **Chassis Info**: 4.289 seconds

### Performance Characteristics:
- Individual endpoints take **4-8 seconds** each
- Concurrent requests should complete in **5-8 seconds** (not 3x individual time)
- This specific iDRAC is slower than modern units but still functional

## Timeout Adjustments Made

### 1. Primary Data Timeout
**Before**: 6.0 seconds
**After**: 12.0 seconds
**Reason**: Allow time for concurrent 5-8s responses from slow iDRAC

```python
# Based on real iDRAC testing: endpoints take 4-8 seconds each
primary_timeout = 12.0  # Allow time for concurrent 5-8s responses
```

### 2. Secondary Data Conditions
**Before**: Only fetch if primary < 5.0s
**After**: Only fetch if primary < 10.0s
**Reason**: Account for slower but still acceptable response times

### 3. Secondary Data Timeout  
**Before**: 4.0 seconds
**After**: 10.0 seconds
**Reason**: Allow time for 2 concurrent 5-8s calls

### 4. Emergency Fallback Timeout
**Before**: 3.0 seconds each
**After**: 8.0 seconds each  
**Reason**: Match individual endpoint performance characteristics

### 5. Performance Warning Thresholds
**Before**: Warn if > 8 seconds
**After**: 
- Warn if > 15 seconds (optimization needed)
- Info if > 10 seconds (acceptable for this iDRAC)
- Debug if ≤ 10 seconds (good performance)

## Expected Performance Improvement

### Before Optimization:
- Hitting 6s timeout → falling back to individual requests
- Total time: ~19.5 seconds (sequential fallback)
- Frequent timeout errors in logs

### After Optimization:
- Concurrent requests should succeed within 12s timeout
- Total time: ~8-12 seconds (concurrent success)
- No timeout errors for normal operations
- Graceful handling of slow iDRACs

## Implementation Details

### Timeout Strategy:
1. **Primary Phase** (Essential sensors): 12s for 3 concurrent calls
2. **Secondary Phase** (Optional data): 10s for 2 concurrent calls  
3. **Emergency Fallback**: 8s per individual call
4. **Performance Monitoring**: Adaptive logging based on timing

### Concurrency Benefits:
- 3 endpoints taking 5-8s each individually
- With proper concurrency: Complete in ~8s total (not 15-24s)
- Maintains integration responsiveness

### Error Handling:
- Graceful degradation with partial data
- Clear logging for troubleshooting
- No integration failures due to timeouts

## Testing Recommendations

1. **Monitor logs** for timing after restart
2. **Expected behavior**: 
   - INFO: "Redfish update completed in X.X seconds (acceptable for this iDRAC)" 
   - Should see 8-12 second total times
3. **Success metrics**:
   - No more "Primary data timeout" errors
   - Consistent sensor data updates
   - ~50% faster overall performance

## iDRAC-Specific Notes

The tested iDRAC (2.84.84.84, 13G Monolithic) represents a slower but typical enterprise deployment:
- **Response times**: 4-8 seconds per endpoint
- **Redfish version**: 1.4.0 (older but functional)
- **Sensor coverage**: Full (temps, fans, power, voltages)

These optimizations accommodate real-world iDRAC performance while maintaining reliability and comprehensive monitoring capabilities.