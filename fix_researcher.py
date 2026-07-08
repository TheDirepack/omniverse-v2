
with open('backend/app/research/researcher.py', 'r') as f:
    lines = f.readlines()

# Line 236 is index 235.
# We want it to match the indentation of line 233 (index 232).
indent = len(lines[232]) - len(lines[232].lstrip())
lines[235] = ' ' * indent + lines[235].lstrip()

# Also fix the following lines in the dict
for i in range(236, 241):
    if i < len(lines):
        lines[i] = ' ' * (indent + 4) + lines[i].lstrip()

with open('backend/app/research/researcher.py', 'w') as f:
    f.writelines(lines)
