
with open('backend/app/core/agent_engine.py', 'r') as f:
    lines = f.readlines()

# Correct line 364 (32 spaces)
lines[363] = ' ' * 32 + ')\n'

# Correct line 365 (32 spaces)
lines[364] = ' ' * 32 + 'return True, "Submission rejected: The dataset provided is not valid JSON. Please ensure you return a properly formatted JSON object.", messages\n'

# Correct line 366 (28 spaces)
lines[365] = ' ' * 28 + 'except Exception as e:\n'

with open('backend/app/core/agent_engine.py', 'w') as f:
    f.writelines(lines)
