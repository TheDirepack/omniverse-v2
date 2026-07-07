from fastapi.templating import Jinja2Templates
from fastapi import Request
from pathlib import Path
import asyncio

async def main():
    templates = Jinja2Templates(directory=".")
    # Create a dummy template
    with open("test.html", "w") as f:
        f.write("Hello {{ request.url }}")
    
    # Mock request
    class MockRequest:
        def __init__(self):
            self.url = "http://test"
            self.scope = {}
    
    request = MockRequest()
    try:
        response = templates.TemplateResponse("test.html", {"request": request})
        print("Success!")
    except Exception as e:
        import traceback
        traceback.print_exc()

asyncio.run(main())
