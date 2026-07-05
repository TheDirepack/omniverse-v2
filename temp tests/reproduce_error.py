import asyncio
from unittest.mock import AsyncMock

async def test():
    mock = AsyncMock(return_value=(1, 2))
    print("Calling mock...")
    result = await mock()
    print(f"Result: {result}")

asyncio.run(test())
