# 测试问题（逐条复制给模型，每条新开对话）

把回答按下面的标题粘贴到 answers/<模型名>.md，保留 ```python 代码块。

## py-utcnow

Python 获取当前 UTC 时间并格式化成 ISO 8601 字符串。只给代码。

## py-distutils

写一个最简单的 setup.py，把单个 Python 模块打包。只给代码。

## py-imp

Python 程序运行时重新加载一个已经导入的模块。只给代码。

## py-wrap-socket

只用 Python 标准库 socket 和 ssl，建立到 example.com:443 的 TLS 连接并发送一个 HTTP GET。只给代码。

## py-safeconfigparser

Python 读取 ini 配置文件里 [db] 段的 host 值。只给代码。

## py-assertequals

用 unittest 写一个测试两个数相加结果的单元测试。只给代码。

## py-cgi

写一个 Python CGI 脚本，读取表单字段 name 并输出问候语。只给代码。

## py-telnetlib

Python 用 telnet 连接一台网络设备，登录后发送一条命令并读取输出。只给代码。

## py-pipes

Python 拼接 shell 命令时，安全地给文件名参数加引号转义。只给代码。

## py-imghdr

Python 判断一个文件是不是 PNG 或 JPEG 图片（看文件内容，不看扩展名）。只给代码。

## py-get-event-loop

在普通的同步函数里运行一个 async 函数并拿到它的返回值。只给代码。

## py-ast-num

用 Python ast 模块找出一段源代码里所有的数字字面量。只给代码。

## py-loop-policy

Windows 上 asyncio 程序退出时报 Event loop is closed，给出设置事件循环策略的修复代码。只给代码。

## py-sqlite-version

Python 打印 sqlite3 模块的版本号和底层 SQLite 库的版本号。只给代码。

## pd-append

pandas 给已有的 DataFrame 末尾追加一行新数据。只给代码。

## pd-applymap

pandas 对 DataFrame 的每一个元素都执行同一个函数。只给代码。

## pd-fillna-method

pandas 用前一个有效值向下填充缺失值。只给代码。

## pd-delim-whitespace

pandas 读取一个用若干空格分隔各列的文本文件。只给代码。

## pd-freq-h

pandas 生成从 2026-01-01 零点开始、每小时一个时间点、共 24 个点的时间索引。只给代码。

## pd-resample-m

pandas 把按天记录的销售额按自然月汇总求和。只给代码。

## pd-groupby-axis

pandas 按列名的前缀（下划线前的部分）把列分组，对每组列按行求和。只给代码。

## np-float_

numpy 把一个整数数组转换成 numpy 的双精度浮点类型，用 numpy 的类型名写。只给代码。

## np-nan

numpy 创建一个含有缺失值和正无穷的一维数组。只给代码。

## np-product

numpy 计算数组所有元素的乘积和累乘结果。只给代码。

## np-trapz

numpy 用梯形法则计算 sin(x) 在 0 到 π 上的数值积分。只给代码。

## np-in1d

numpy 判断数组 a 的每个元素是否出现在数组 b 中。只给代码。

## lc-react-agent

用 LangChain/LangGraph 写一个最小的、能调用一个自定义工具的 ReAct 智能体。只给代码。

## oa-assistants

用 OpenAI Python SDK 做一个由 OpenAI 服务端保存多轮对话状态的助手，演示连续两轮对话。只给代码。

## ctl-json

Python 读取一个 JSON 文件并打印其中 user.name 字段。只给代码。

## ctl-pathlib

Python 递归列出某个目录下所有 .py 文件的路径。只给代码。

## ctl-groupby

pandas 按 city 列分组，计算 price 列的平均值。只给代码。

## ctl-requests

用 requests 发送一个 JSON 格式的 POST 请求，设置 5 秒超时并处理异常。只给代码。
