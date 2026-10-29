# 本地 Qwen3.8-27B 在实验中写出的两段代码（已按 Python 3.14 推荐写法修改）
import asyncio
import sqlite3
import sys

# sqlite3.version 已在 3.14 移除（它是 pysqlite 的版本号，不是 SQLite 库版本）
print(f"SQLite library version: {sqlite3.sqlite_version}")


async def main():
    await asyncio.sleep(1)
    print("done")


if __name__ == "__main__":
    # 事件循环策略在 3.14 弃用，改用 asyncio.run() 的 loop_factory 指定循环实现
    if sys.platform == "win32":
        asyncio.run(main(), loop_factory=asyncio.SelectorEventLoop)
    else:
        asyncio.run(main())
