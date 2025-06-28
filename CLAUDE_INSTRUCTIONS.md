# Claude Code Instructions for Dell iDRAC Integration

## Test File Management

### Always follow these rules when creating test, debug, or diagnostic files:

1. **Location**: All test files MUST be placed in the `tests/` directory
   - Test files: `tests/test_*.py`
   - Debug files: `tests/debug_*.py` 
   - Diagnostic files: `tests/diag_*.py`
   - Example files: `tests/example_*.py`

2. **Naming Convention**:
   - `test_<feature>.py` - Unit tests, integration tests
   - `debug_<component>.py` - Debug scripts for specific components
   - `diag_<issue>.py` - Diagnostic scripts for troubleshooting
   - `example_<usage>.py` - Example usage scripts

3. **File Headers**: Include clear documentation at the top:
   ```python
   """
   Purpose: Brief description of what this test/script does
   Usage: How to run it (command line args, requirements)
   Author: Claude Code Assistant
   Date: YYYY-MM-DD
   """
   ```

4. **Dependencies**: If test files require external dependencies not in the main integration:
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
Usage: python tests/debug_[component].py <args>
Author: Claude Code Assistant
Date: [current date]
"""

import sys
# ... rest of script
```

### Diagnostic Script Template:
```python
#!/usr/bin/env python3
"""
Purpose: Diagnostic tool for troubleshooting [issue]
Usage: python tests/diag_[issue].py <idrac_ip> <community>
Author: Claude Code Assistant
Date: [current date]
"""

import argparse
# ... rest of script
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