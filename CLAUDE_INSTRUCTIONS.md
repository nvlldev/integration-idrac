# Claude Code Instructions for Dell iDRAC Integration

## Test File Management

### Always follow these rules when creating test, debug, or diagnostic files:

1. **Location**: All test files MUST be placed in the `tests/` directory
   - Test files: `tests/test_*.py`
   - Debug files: `tests/debug_*.py` 
   - Diagnostic files: `tests/diag_*.py`
   - Example files: `tests/example_*.py`

2. **Environment Configuration**: ALWAYS use environment files for test configuration
   - Load `.env.local` first (private config), fallback to `.env.test` (template)
   - Access variables with `os.getenv('VARIABLE_NAME')`
   - Never hardcode IP addresses, passwords, or connection details
   - Example:
   ```python
   from dotenv import load_dotenv
   import os
   
   # Load .env.local first (private), fallback to .env.test (template)
   load_dotenv('.env.local')  
   load_dotenv('.env.test')
   
   idrac_host = os.getenv('IDRAC_HOST')
   community = os.getenv('IDRAC_COMMUNITY')
   ```

3. **Naming Convention**:
   - `test_<feature>.py` - Unit tests, integration tests
   - `debug_<component>.py` - Debug scripts for specific components
   - `diag_<issue>.py` - Diagnostic scripts for troubleshooting
   - `example_<usage>.py` - Example usage scripts

4. **File Headers**: Include clear documentation at the top:
   ```python
   """
   Purpose: Brief description of what this test/script does
   Usage: python tests/script.py (uses .env.local or .env.test for config)
   Requirements: List any external dependencies (pysnmp, python-dotenv, etc.)
   Author: Claude Code Assistant
   Date: YYYY-MM-DD
   """
   ```

5. **Dependencies**: If test files require external dependencies not in the main integration:
   - Document them clearly in the file header
   - Consider adding a `tests/requirements.txt` if needed

## Commit Process

### When creating or modifying test files:

1. **Always commit test files** along with the main code changes
2. **Use descriptive commit messages** that mention test additions:
   ```
   Fix sensor issues and add diagnostic tests
   
   - Fix DIMM Socket Health availability 
   - Add intrusion sensor diagnostic scripts in tests/
   - Create instruction file for test management
   ```

3. **Push immediately after committing** unless explicitly told otherwise

## Test File Examples

### Debug Script Template:
```python
#!/usr/bin/env python3
"""
Purpose: Debug script for [component name]
Usage: python tests/debug_[component].py (uses .env.local or .env.test)
Requirements: python-dotenv, pysnmp
Author: Claude Code Assistant
Date: [current date]
"""

from dotenv import load_dotenv
import os
import sys

# Load environment variables (.env.local preferred, .env.test fallback)
load_dotenv('.env.local')
load_dotenv('.env.test')

# Get configuration from environment
idrac_host = os.getenv('IDRAC_HOST')
community = os.getenv('IDRAC_COMMUNITY')

if not idrac_host or not community:
    print("Error: Please configure IDRAC_HOST and IDRAC_COMMUNITY in .env.local or .env.test")
    sys.exit(1)

# ... rest of script
```

### Diagnostic Script Template:
```python
#!/usr/bin/env python3
"""
Purpose: Diagnostic tool for troubleshooting [issue]
Usage: python tests/diag_[issue].py (uses .env.local or .env.test)
Requirements: python-dotenv, pysnmp
Author: Claude Code Assistant
Date: [current date]
"""

from dotenv import load_dotenv
import os
import sys
import argparse

# Load environment variables (.env.local preferred, .env.test fallback)
load_dotenv('.env.local')
load_dotenv('.env.test')

def main():
    parser = argparse.ArgumentParser(description='Diagnostic tool for [issue]')
    parser.add_argument('--host', default=os.getenv('IDRAC_HOST'), 
                       help='iDRAC host (default from .env.local/.env.test)')
    parser.add_argument('--community', default=os.getenv('IDRAC_COMMUNITY'),
                       help='SNMP community (default from .env.local/.env.test)')
    
    args = parser.parse_args()
    
    if not args.host or not args.community:
        print("Error: Please provide --host and --community or configure .env.local/.env.test")
        sys.exit(1)
    
    # ... rest of script

if __name__ == "__main__":
    main()
```

## Integration Testing

### When adding new features:
1. Create corresponding test files in `tests/`
2. Document test procedures in the test file header
3. Include both positive and negative test cases
4. Test with actual iDRAC hardware when possible

## Cleanup Policy

- Keep test files that provide ongoing diagnostic value
- Remove temporary debug files after issues are resolved
- Update test files when the main code changes
- Archive old test files rather than deleting them

---

**Remember**: The `tests/` directory is your workspace for all testing, debugging, and diagnostic code. Keep it organized and well-documented!