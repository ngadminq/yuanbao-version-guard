

```python
import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

async def main():
    # 你的异步逻辑
    await asyncio.sleep(1)
    print("done")

if __name__ == "__main__":
    asyncio.run(main())
```