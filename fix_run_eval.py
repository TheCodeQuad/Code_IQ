#!/usr/bin/env python3
"""Fix the run_eval.py file"""

file_path = r'c:\CODEIQ\Code_IQ\backend\run_eval.py'

with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Show line 200 before fix
print(f"Line 200 BEFORE fix: {repr(lines[199])}")

# Fix line 200 - remove the " 205." prefix
if ' 205.' in lines[199]:
    lines[199] = lines[199].replace(' 205.', '', 1)
    print(f"Line 200 AFTER fix: {repr(lines[199])}")
    print("✓ Fixed line 200")
else:
    print("✗ Line 200 doesn't contain ' 205.' - may already be fixed")

# Write back
with open(file_path, 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("✓ File saved")
