# API 变更与来源

本表对应 `cases.json` 的 28 个变更题和 4 个对照题，列出官方来源与解释边界。原始题目、实验标签、模型回答和计分数据保持不变。

## 如何理解这份表

这 28 题是**有意选择已经发生 API 变更的压力样本**，不是随机抽取的日常编程任务；因此其命中比例不能外推为模型在一般编程任务中的过时率。`cases.json` 将其中 23 题标记为 `breaking`、5 题标记为 `deprecated`。这些是实验使用的历史变更标签，不是 28 个目标环境的执行结果。

下表的状态均相对于**本次采用的历史变更基准**：例如 NumPy 2.0 的“弃用”，不代表它在 2026 年所有后续版本中仍然保留；Python 3.12 的“移除”，也不意味着更早版本或另装兼容包的环境必然不能运行。本附件没有在全部目标 Python、pandas、NumPy、LangGraph 和 OpenAI 依赖环境中执行这些回答，不能把文档核对或正则命中写成“已验证运行失败”。

“弃用”表示官方要求迁移；“移除”表示指定发行版删除了接口；“行为变化”须满足文档列出的触发条件。尤其 `asyncio.get_event_loop()` 在 Python 3.14 并未被整个删除。OpenAI 条目的基准则是**服务停用日期**，不是 `openai` Python 包版本。

## 官方历史基准

以下为覆盖本题集的 8 组主要一手来源。日期是官方页面记载的发行或服务事件日期，不把网页抓取时间、页面页眉中的文档站版本或本次核对日期当作发行日期。

| 来源组 | 本次采用的历史基准 | 官方记录的日期或日期说明 | 主要官方出处 |
| --- | --- | --- | --- |
| S1 | Python 3.12 | 2023-10-02 发布 | [What’s New in Python 3.12](https://docs.python.org/3.12/whatsnew/3.12.html) |
| S2 | Python 3.13 | 2024-10-07 发布 | [What’s New in Python 3.13](https://docs.python.org/3.13/whatsnew/3.13.html) |
| S3 | Python 3.14 | 2025-10-07 发布 | [What’s New in Python 3.14](https://docs.python.org/3.14/whatsnew/3.14.html) |
| S4 | pandas 2.0.0 | 2023-04-03 发布 | [What’s new in 2.0.0](https://pandas.pydata.org/docs/whatsnew/v2.0.0.html) |
| S5 | pandas 3.0.0 | 2026-01-21 发布 | [What’s new in 3.0.0](https://pandas.pydata.org/docs/whatsnew/v3.0.0.html) |
| S6 | NumPy 2.0.0 | 2024-06-16 发布，日期见官方新闻 | [2.0.0 发布说明](https://numpy.org/doc/2.0/release/2.0.0-notes.html)、[2.0 迁移指南](https://numpy.org/doc/2.0/numpy_2_0_migration_guide.html)、[官方发布日期](https://numpy.org/news/#numpy-2-0-0-released) |
| S7 | LangGraph 1.0 | 迁移页未署独立发布日期；本表以 v1 为版本基准 | [LangGraph v1 migration guide](https://docs.langchain.com/oss/python/migrate/langgraph-v1) |
| S8 | OpenAI Assistants API 服务停用 | 2026-08-26 停用；弃用页正文写明 2025-08-26 通知 | [弃用与停用记录](https://developers.openai.com/api/docs/deprecations#2025-08-20-assistants-api)、[Assistants 迁移指南](https://developers.openai.com/api/docs/assistants/migration) |

S8 的官方弃用页小节标题为 `2025-08-20: Assistants API`，正文通知日期为 2025-08-26；两者存在日期差异。本表不将小节标题日期直接当作通知日期，实验使用的 2026-08-26 停用日期在官方表格和迁移指南中一致。

## 28 项变更对照

每行保留原题 ID，便于对照原始回答、规则和审查记录。“替代建议”是文档层面的迁移方向；是否满足完整业务语义仍须结合导入方式、数据类型和运行环境判断。

| 题目 ID / API 或写法 | 本次采用的历史变更基准 | 弃用、移除或行为变化 | 替代建议 | 官方出处 |
| --- | --- | --- | --- | --- |
| `py-utcnow`：`datetime.datetime.utcnow()` | Python 3.12 | 弃用；应改用带 UTC 时区的时间对象。 | `import datetime` 后使用 `datetime.datetime.now(datetime.UTC)`；或导入 `datetime, UTC` 后用 `datetime.now(UTC)`，再调用 `isoformat()`。 | [S1：Deprecated](https://docs.python.org/3.12/whatsnew/3.12.html#deprecated) |
| `py-distutils`：`distutils` | Python 3.12 | 从标准库移除；安装 Setuptools 后仍可能有其提供的兼容实现。 | 将示例的打包导入改为 `setuptools`。 | [S1：distutils](https://docs.python.org/3.12/whatsnew/3.12.html#distutils) |
| `py-imp`：`import imp`、`imp.reload()` | Python 3.12 | `imp` 模块移除。 | `importlib.reload(module)`。 | [S1：imp 迁移表](https://docs.python.org/3.12/whatsnew/3.12.html#imp) |
| `py-wrap-socket`：`ssl.wrap_socket()` | Python 3.12 | 顶层函数移除；不等于 `SSLContext.wrap_socket()` 被移除。 | 创建合适的 `SSLContext`，再用其 `wrap_socket()`；客户端可从 `ssl.create_default_context()` 开始，并传入服务器主机名。 | [S1：ssl](https://docs.python.org/3.12/whatsnew/3.12.html#ssl) |
| `py-safeconfigparser`：`configparser.SafeConfigParser` | Python 3.12 | 旧类名移除。 | `configparser.ConfigParser`。 | [S1：configparser](https://docs.python.org/3.12/whatsnew/3.12.html#configparser) |
| `py-assertequals`：`unittest.TestCase.assertEquals()` | Python 3.12 | 旧方法别名移除。 | `assertEqual()`。 | [S1：移除的 TestCase 别名表](https://docs.python.org/3.12/whatsnew/3.12.html#unittest-testcase-removed-aliases) |
| `py-cgi`：`cgi`、`cgi.FieldStorage` | Python 3.13 | `cgi` 从标准库移除。 | 依表单编码选择解析方式：查询串可用 `urllib.parse.parse_qsl()`；POST/PUT 或 multipart 场景按文档选择 `email.message`、`multipart` 等。 | [S2：PEP 594 移除与迁移建议](https://docs.python.org/3.13/whatsnew/3.13.html#pep-594-remove-dead-batteries-from-the-standard-library) |
| `py-telnetlib`：`telnetlib` | Python 3.13 | 从标准库移除。 | 按接口与同步/异步需求评估第三方 `telnetlib3` 或 `Exscript`，不能只替换模块名。 | [S2：PEP 594 移除与迁移建议](https://docs.python.org/3.13/whatsnew/3.13.html#pep-594-remove-dead-batteries-from-the-standard-library) |
| `py-pipes`：`pipes.quote()` | Python 3.13 | `pipes` 模块移除。 | POSIX shell 的单参数转义可用 `shlex.quote()`；无需 shell 时优先给 `subprocess.run(..., shell=False)` 传参数列表。 | [S2：pipes 替代建议](https://docs.python.org/3.13/whatsnew/3.13.html#pep-594-remove-dead-batteries-from-the-standard-library)、[shlex 的平台边界](https://docs.python.org/3.13/library/shlex.html#shlex.quote) |
| `py-imghdr`：`imghdr` | Python 3.13 | 从标准库移除。 | 按文件内容识别格式时，可评估 `filetype`、`puremagic`、`python-magic`。 | [S2：PEP 594 移除与迁移建议](https://docs.python.org/3.13/whatsnew/3.13.html#pep-594-remove-dead-batteries-from-the-standard-library) |
| `py-get-event-loop`：`asyncio.get_event_loop()` | Python 3.14 | **没有当前事件循环时**改为抛出 `RuntimeError`，不再隐式创建循环；已有当前循环的情形不能一概判失败。 | 普通同步入口运行协程用 `asyncio.run()`；需多次运行并管理同一循环时可用 `asyncio.Runner`。 | [S3：Removed](https://docs.python.org/3.14/whatsnew/3.14.html#removed)、[3.14 的条件说明](https://docs.python.org/3.14/library/asyncio-eventloop.html#asyncio.get_event_loop) |
| `py-ast-num`：`ast.Num`、`ast.Str`、`visit_Num` | Python 3.14 | 旧常量节点类别移除；`NodeVisitor` 不再派发 `visit_Num()` 等旧访问方法，可能表现为漏处理，而非抛异常。 | `ast.Constant`、`visit_Constant()`；数字题还应按 `node.value` 类型筛选。 | [S3：Removed](https://docs.python.org/3.14/whatsnew/3.14.html#removed)、[NodeVisitor 变更](https://docs.python.org/3.14/library/ast.html#ast.NodeVisitor) |
| `py-loop-policy`：`asyncio.set_event_loop_policy()` | Python 3.14 | 事件循环策略系统弃用；此基准下不应写成已删除。 | 需要指定循环实现时，用 `asyncio.run()` 或 `Runner` 的 `loop_factory`；例如文档中的 `asyncio.SelectorEventLoop`。具体退出异常还需单独诊断。 | [S3：New deprecations](https://docs.python.org/3.14/whatsnew/3.14.html#new-deprecations) |
| `py-sqlite-version`：`sqlite3.version` | Python 3.14 | `version`、`version_info` 移除；它们原本也不是底层 SQLite 库版本。 | 查询底层运行库用 `sqlite3.sqlite_version`；它不能等价提供原来的包装模块版本。 | [S3：sqlite3](https://docs.python.org/3.14/whatsnew/3.14.html#sqlite3)、[旧字段含义](https://docs.python.org/3.12/library/sqlite3.html#sqlite3.version) |
| `pd-append`：`DataFrame.append()` | pandas 2.0.0 | 方法移除。 | 将新行组织成合适的 DataFrame，再用 `pd.concat()`；是否保留索引由任务决定。 | [S4：Removal of prior version deprecations/changes](https://pandas.pydata.org/docs/whatsnew/v2.0.0.html#removal-of-prior-version-deprecations-changes) |
| `pd-applymap`：`DataFrame.applymap()` | pandas 3.0.0 | 方法移除；此前在 2.1.0 弃用。 | `DataFrame.map()`。 | [S5：Other Removals](https://pandas.pydata.org/docs/whatsnew/v3.0.0.html#other-removals)、[2.1.0 的改名与弃用记录](https://pandas.pydata.org/docs/whatsnew/v2.1.0.html#deprecations) |
| `pd-fillna-method`：`fillna(method="ffill")` | pandas 3.0.0 | `Series.fillna()`、`DataFrame.fillna()` 的 `method` 参数移除。 | 向前填充用 `.ffill()`；向后填充用 `.bfill()`。 | [S5：Other Removals](https://pandas.pydata.org/docs/whatsnew/v3.0.0.html#other-removals)、[2.1.0 的迁移方向](https://pandas.pydata.org/docs/whatsnew/v2.1.0.html#deprecations) |
| `pd-delim-whitespace`：`read_csv(delim_whitespace=True)` | pandas 3.0.0 | `read_csv()`、`read_table()` 的旧参数移除。 | `sep=r"\s+"`。 | [S5：Other Removals](https://pandas.pydata.org/docs/whatsnew/v3.0.0.html#other-removals) |
| `pd-freq-h`：`freq="H"` | pandas 3.0.0 | 大写小时频率别名的既有弃用被执行；本表限定于小时频率，不将所有大写频率一并判旧。 | `freq="h"`。 | [S5：Other Removals](https://pandas.pydata.org/docs/whatsnew/v3.0.0.html#other-removals)、[2.2.0 的别名迁移](https://pandas.pydata.org/docs/whatsnew/v2.2.0.html#deprecations) |
| `pd-resample-m`：`resample("M")` | pandas 3.0.0 | 月末 **offset** 别名 `M` 移除并改用 `ME`；此结论不能套用于所有使用 `M` 的 Period 语义。 | 月末重采样用 `resample("ME")`。 | [S5：offset 别名表](https://pandas.pydata.org/docs/whatsnew/v3.0.0.html#enforced-deprecation-of-aliases-m-q-y-etc-in-favour-of-me-qe-ye-etc-for-offsets) |
| `pd-groupby-axis`：`groupby(..., axis=1)` | pandas 3.0.0 | `groupby` 的 `axis` 参数移除。 | 本题按列分组时，先转置，再按行分组求和，最后转置回来：`df.T.groupby(...).sum().T`。 | [S5：Other Removals](https://pandas.pydata.org/docs/whatsnew/v3.0.0.html#other-removals)、[2.1.0 的转置迁移建议](https://pandas.pydata.org/docs/whatsnew/v2.1.0.html#deprecations) |
| `np-float_`：`np.float_` | NumPy 2.0.0 | 主命名空间旧别名移除。 | `np.float64`。 | [S6：Main namespace](https://numpy.org/doc/2.0/numpy_2_0_migration_guide.html#main-namespace) |
| `np-nan`：`np.NaN`、`np.NAN`、`np.Inf`、`np.Infinity` | NumPy 2.0.0 | 旧别名移除；不表示缺失值和正无穷功能被移除。`NAN` 的文档清理另见官方 2.0.1 记录。 | `np.nan`、`np.inf`。 | [S6：Main namespace](https://numpy.org/doc/2.0/numpy_2_0_migration_guide.html#main-namespace)、[2.0.1 的别名文档清理](https://numpy.org/doc/2.1/release/2.0.1-notes.html#pull-requests-merged) |
| `np-product`：`np.product()`、`np.cumproduct()` | NumPy 2.0.0 | 主命名空间旧名称移除。 | 分别使用 `np.prod()`、`np.cumprod()`。 | [S6：Main namespace](https://numpy.org/doc/2.0/numpy_2_0_migration_guide.html#main-namespace) |
| `np-trapz`：`np.trapz()` | NumPy 2.0.0 | 在 2.0 基准下为弃用，不能按此来源写成当时已删除。 | `np.trapezoid()`，或适当的 `scipy.integrate` 函数。 | [S6：Main namespace 的弃用表](https://numpy.org/doc/2.0/numpy_2_0_migration_guide.html#main-namespace) |
| `np-in1d`：`np.in1d()` | NumPy 2.0.0 | 在 2.0 基准下为弃用。 | `np.isin()`；注意它保留首个输入的形状，迁移需检查输出形状要求。 | [S6：Main namespace 的弃用表](https://numpy.org/doc/2.0/numpy_2_0_migration_guide.html#main-namespace)、[isin 的形状说明](https://numpy.org/doc/2.0/reference/generated/numpy.isin.html#numpy.isin) |
| `lc-react-agent`：`langgraph.prebuilt.create_react_agent` | LangGraph 1.0 | v1 迁移指南列为弃用；不是已移除结论。此行限定上述命名空间，不能仅凭同名函数认定来源。 | `from langchain.agents import create_agent`；依迁移说明调整调用参数。 | [S7：Deprecations](https://docs.langchain.com/oss/python/migrate/langgraph-v1#deprecations) |
| `oa-assistants`：`client.beta.assistants`、`client.beta.threads` | OpenAI 服务于 2026-08-26 停用 | 官方确认 Assistants API 已停用；这是服务生命周期变化，不是某个 Python SDK 版本删名的证据，也不是本实验的失败请求日志。 | 多轮服务端状态场景采用 Responses API 与 Conversations API，并按迁移指南重做对象和调用流程。 | [S8：停用日期表](https://developers.openai.com/api/docs/deprecations#2025-08-20-assistants-api)、[官方迁移指南](https://developers.openai.com/api/docs/assistants/migration) |

## 4 个对照题的解释范围

`current` 只表示本次题集没有为该对照题设定相应的历史变更模式。它不保证库的所有版本都不会变化，也不保证模型给出的任何具体实现都正确；本次也没有借这 4 题完成跨版本兼容性认证。

| 对照题 ID | 本次对照的任务 | 可以据此说明的范围 |
| --- | --- | --- |
| `ctl-json` | 用 Python 读取 JSON 并取 `user.name` | 本次没有给该任务设定待检出的变更模式。 |
| `ctl-pathlib` | 递归列出目录中的 `.py` 文件 | 同上；目录权限、符号链接等运行条件仍须结合具体实现判断。 |
| `ctl-groupby` | pandas 按 `city` 分组计算 `price` 均值 | 本次没有对应的旧 API 检测项；不能推广为所有 `groupby` 用法永不变化。 |
| `ctl-requests` | requests 发送 JSON POST、设置超时并处理异常 | 本次没有对应的旧 API 检测项；网络请求成功与异常处理正确性未由来源核对证明。 |

## 与原始题集需要一同保留的说明

本次核对未发现需要改变 28 项历史基准版本或 `status` 标签的证据，但有两处 `replacement` 表述需要在讲解时纠正。本附件保留原始实验文件，避免在结果产生后改变标签：

1. `py-utcnow` 的 `datetime.now(datetime.UTC)` 混用了类名与模块名。在通常的 `import datetime` 或 `from datetime import datetime` 导入方式下，它都不是完整正确的替代写法；应采用上表中导入与调用相匹配的形式。依据是 [Python 3.12 官方 UTC 迁移建议](https://docs.python.org/3.12/whatsnew/3.12.html#deprecated)。
2. `py-sqlite-version` 的 `sqlite3.sqlite_version` 只提供底层运行库版本，不能保持题目中“模块版本号和底层 SQLite 版本号”两个输出的原有含义。官方说明旧模块版本常量已失去实用意义；正确回答应解释该差别，而非把两者改成同一个值。依据是 [旧模块版本字段说明](https://docs.python.org/3.12/library/sqlite3.html#sqlite3.version) 与 [3.14 移除记录](https://docs.python.org/3.14/whatsnew/3.14.html#sqlite3)。

此外，`py-get-event-loop` 的 `breaking` 标签须带“无当前循环”的条件，`py-ast-num` 的旧访问方法可能静默漏处理，`py-loop-policy` 的替代方案也不等于已经证明能修复题设中的所有退出异常。[官方 3.14 行为说明](https://docs.python.org/3.14/library/asyncio-eventloop.html#asyncio.get_event_loop) 与 [NodeVisitor 文档](https://docs.python.org/3.14/library/ast.html#ast.NodeVisitor) 支持这些边界。它们影响结果的解释，不构成已完成目标环境运行验证的证据。
