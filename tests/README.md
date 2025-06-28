# Dell iDRAC Integration Tests

This directory contains test scripts, debugging tools, and diagnostic utilities for the Dell iDRAC Home Assistant integration.

## Files

### Debug Scripts
- **`debug_intrusion.py`** - Basic intrusion detection sensor debugging
- **`test_all_intrusion_oids.py`** - Comprehensive intrusion sensor OID testing

## Usage

### Prerequisites
Most test scripts require direct SNMP access to your iDRAC. Ensure you have:
- Network connectivity to the iDRAC
- Valid SNMP community string (usually 'public' for read-only)
- Python dependencies: `pip install pysnmp python-dotenv`

### Configuration
1. **Copy the test environment file**:
   ```bash
   cp .env.test .env.local
   ```

2. **Edit `.env.local` with your iDRAC settings**:
   ```bash
   # Update these values for your environment
   IDRAC_HOST=192.168.1.100
   IDRAC_COMMUNITY=public
   IDRAC_USERNAME=root
   IDRAC_PASSWORD=calvin
   ```

3. **Ensure `.env.local` is in .gitignore** (it should be already)

### Running Tests

**Recommended (using .env.test configuration)**:
```bash
# Tests will automatically load configuration from .env.test
python tests/debug_intrusion.py
python tests/test_all_intrusion_oids.py
```

**Alternative (command line arguments)**:
```bash
# Override .env.test values with command line arguments
python tests/debug_intrusion.py --host 192.168.1.100 --community public
python tests/test_all_intrusion_oids.py --host 192.168.1.100 --community public
```

## Development

When adding new test files:
1. Use appropriate naming: `test_*.py`, `debug_*.py`, `diag_*.py`
2. Include proper headers with purpose, usage, author, and date
3. Document any additional dependencies
4. Test with actual iDRAC hardware when possible

## Troubleshooting

### Common Issues
- **Connection timeout**: Check network connectivity and iDRAC IP
- **SNMP errors**: Verify community string and SNMP is enabled on iDRAC
- **No data returned**: iDRAC may not support the specific sensors being tested

### Getting Help
1. Run the diagnostic scripts to gather information
2. Check Home Assistant logs for integration errors
3. Verify iDRAC firmware version and SNMP configuration