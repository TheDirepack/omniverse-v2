def test_func(count, failure_type):
    if failure_type == "INFRASTRUCTURE_FAILURE":
        if count == 1:
            observation = "1"
        elif count < 3:
            observation = "2"
        else:
            disabled_tools = set()
            disabled_tools.add("test")
            observation = "3"
    return observation

print(test_func(1, "INFRASTRUCTURE_FAILURE"))
print(test_func(2, "INFRASTRUCTURE_FAILURE"))
print(test_func(4, "INFRASTRUCTURE_FAILURE"))
print(test_func(1, "OTHER"))
