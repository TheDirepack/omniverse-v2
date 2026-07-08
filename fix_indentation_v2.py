
with open('backend/app/core/agent_engine.py', 'r') as f:
    lines = f.readlines()

for i in range(len(lines)):
    # Fix the closing parenthesis of the messages.append() call
    if i == 363 and lines[i].strip() == ')':
        lines[i] = ' ' * 32 + ')\n'
    # Fix the return statement
    if i == 364 and 'return True, "Submission rejected' in lines[i]:
        lines[i] = ' ' * 32 + 'return True, "Submission rejected: The dataset provided is not valid JSON. Please ensure you return a properly formatted JSON object.", messages\n'
    # Fix the except block
    if i == 365 and 'except Exception as e:' in lines[i]:
        lines[i] = ' ' * 28 + 'except Exception as e:\n'

with open('backend/app/core/agent_engine.py', 'w') as f:
    f.writelines(lines)
