try:
    raise slice(None, 500, None)
except Exception as e:
    print(f"Caught: {e}")
except BaseException as e:
    print(f"Caught BaseException: {e}")
