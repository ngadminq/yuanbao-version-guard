# 本地 Qwen3.8-27B 在实验中写出的两段代码（原样保留）
import asyncio
import sqlite3
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

print(f"sqlite3 module version: {sqlite3.version}")
print(f"SQLite library version: {sqlite3.sqlite_version}")


async def main():
    await asyncio.sleep(1)
    print("done")


if __name__ == "__main__":
    asyncio.run(main())
