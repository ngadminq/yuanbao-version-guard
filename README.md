# 版本核验助手：用元宝搜索检查 AI 写的代码是否过时

本工具先用 Python AST 抽取模块、属性、方法和关键字参数，再调用元宝 SearchPro，在配置的官方文档域名中寻找 API 变更证据，输出判定、证据原句和链接。判定规则不调用 LLM。

核心检查、单元测试、实验复算和 HTML 报告生成只需要 **Python 3.10+ 和标准库**，无须安装 pandas、NumPy 或模型 SDK。本次离线验证使用 Python 3.11.16。批量核验采用静态分析；单项 `applymap` 迁移案例另外使用独立的 pandas 3.0.0 环境执行，步骤见下文。

代码仓库：<https://github.com/ngadminq/yuanbao-version-guard>（文章对应版本为 `v1.0` 标签）。先阅读 [参赛文章](参赛文章.md) 和 [API 变更与来源](API变更与来源.md)；后者说明接口资料、目标 API 的官方来源及核验口径。

## 获取代码

```bash
git clone https://github.com/ngadminq/yuanbao-version-guard.git
cd yuanbao-version-guard
python --version
```

以下终端命令都在仓库根目录（同时包含 `evaluate.py`、`version_guard.py` 和 `cases.json` 的目录）中运行。

下文会重新写入派生结果和时间戳；需要恢复原始实验快照时，执行 `git checkout -- data viewer` 即可。缓存和答案按脚本所在目录定位，不按任意终端工作目录定位。

## 方案一：离线复算已有实验，无须密钥

完整材料已包含 186 条搜索缓存、32 份模型原始回答和人工复核 CSV。保留这些文件并使用现有问题、答案和查询参数时，以下命令直接复用缓存，无须搜索或模型密钥：

```powershell
python -m unittest -v test_version_guard
python evaluate.py probe
python evaluate.py run --name qwen3.8-27b
python render_report.py
python version_guard.py check examples/qwen_loop_policy.md
```

各步作用和输出：

| 命令 | 读取与生成 |
|---|---|
| `python -m unittest -v test_version_guard` | 运行 24 个离线规则测试，不调用 API |
| `python evaluate.py probe` | 用 28 条既定查询复算定向实验，写入 `data/probe.json` |
| `python evaluate.py run --name qwen3.8-27b` | 静态扫描 `answers/qwen3.8-27b.json`，写入 `data/run_qwen3.8-27b.json` 和 `data/review_qwen3.8-27b.csv`；按 `(case, symbol)` 保留已有人工复核字段 |
| `python render_report.py` | 汇总全部缓存、原始回答、实验结果、规则迭代存档及复核表，写入 [viewer/index.html](viewer/index.html)，可用浏览器直接打开 |
| `python version_guard.py check examples/qwen_loop_policy.md` | 检查材料中的单条代码示例，在终端显示证据表 |

**`probe` 和 `run` 没有独立的 `--offline` 开关。** `data/cache/` 命中时才不发请求；缓存缺失、修改查询参数、替换答案或检查新的代码，都可能触发 SearchPro 调用，并读取密钥或提示输入密钥。要严格避免联网，可先断网再执行；若出现密钥提示，应停止并检查材料是否完整。`render_report.py` 本身只读取本地材料，不请求搜索或模型服务。

只有 `probe` 和 `run` 不会产生全部统计。文章中的缓存总量、返回结果条数、文档语言/版本分布、历史网络耗时和人工复核比例由 `render_report.py` 额外汇总。报告当前固定读取 `qwen3.8-27b` 这组材料；它不会自动切换到另一个 `--name` 的实验。报告内终端日志来自 `data/logs/` 的已存档文本，普通重跑不会自动更新这些日志。

在完整副本中，禁用 `socket`、`urlopen`、真实 `collect` 和 `getpass` 后，本次实测 24 项单元测试通过，以上 `probe/run/check/render_report` 均完成，未尝试网络调用或密钥输入。核心结果应为：

| 项目 | 已存材料的复算值 |
|---|---|
| 搜索记录 | 186 条，HTTP 200 为 186 条；共 1,852 个返回结果项 |
| 定向实验 | 28/28 命中官方文档；20/28 检出变更；16/28 状态完全一致 |
| 模型答案 | 32 份：28 道变更题、4 道对照题；变更题中 9 份命中过时模式，核验规则抓到其中 4 份 |
| 自动告警 | 检查 136 个符号，标记 27 条；对照题标记 1 条 |
| 人工复核 | 27 条中 5 条判对，约 18.5%；复算不会重新执行人工判断 |
| Python 官方文档结果 | 1,117 条；翻译版占 91.5%，3.11 及更早版本 357 条，占 32.0% |

这些数字复算的是随包保存的实验快照。重跑产生的 `recorded_at` 会变化，历史搜索耗时和原始模型耗时仍读取缓存值。静态抽取使用运行时的 `sys.stdlib_module_names`；若要对齐本次验证环境，可使用 Python 3.11。上述验证不代表已验证全部 Python 版本和目标依赖组合。

## 方案二：在线检查新代码或重新收集模型回答

### 1. SearchPro 接口和凭证

`research_client.py` 使用以下实际接口约定：

- Endpoint：`https://api.wsa.cloud.tencent.com/SearchPro`，HTTP `POST`。
- 请求头：`Content-Type: application/json`、`Authorization: Bearer <API Key>`。
- 搜索密钥环境变量：`YUANBAO_API_KEY`；未设置时，检查 CLI 会在首次缺少缓存时通过 `getpass` 隐藏输入。
- 请求示例参数：`Query`、`Mode=0`、`Cnt=10`、`Site=docs.python.org`。`Query` 在本客户端中要求非空且不超过 64 个字符。

接口字段、鉴权和变更说明以 [API 变更与来源](API变更与来源.md) 中记录的来源为准。密钥不写入缓存；缓存保留请求参数、HTTP 状态、耗时、时间和原始 JSON 响应，且排除 Authorization 头。不要把密钥写入源码或提交到仓库。

### 2. 最小可复制调用

将下面完整代码保存为代码根目录下的 `searchpro_minimal.py`，然后运行 `python searchpro_minimal.py`。它复用本项目的 `collect` 和 `decode_pages`，包含导入、参数、HTTP/业务错误及网络/JSON 异常处理。**此示例每次执行都会真实请求 SearchPro，不经过 `data/cache/`，可能消耗 API 配额。** 本次材料整理未执行真实在线调用。

```python
import getpass
import os
from urllib.error import URLError

from research_client import collect, decode_pages


def main():
    api_key = os.environ.get("YUANBAO_API_KEY", "").strip()
    if not api_key:
        api_key = getpass.getpass("Yuanbao API Key (hidden): ").strip()
    if not api_key:
        raise SystemExit("未提供 YUANBAO_API_KEY，已停止。")

    job = {
        "id": "readme-minimal",
        "label": "Python asyncio 官方变更说明",
        "request": {
            "Query": "python asyncio set_event_loop_policy deprecated",
            "Mode": 0,
            "Cnt": 10,
            "Site": "docs.python.org",
        },
    }
    try:
        record = collect(job, api_key)
    except (URLError, TimeoutError, OSError) as exc:
        raise SystemExit(f"网络请求失败：{type(exc).__name__}") from None
    except (ValueError, UnicodeError):
        raise SystemExit("请求参数不合法或接口未返回有效 JSON。") from None

    # collect 会将 HTTPError 转为 status/response 记录；非 JSON 错误页在上方处理。
    if record["status"] != 200:
        raise SystemExit(f"HTTP 错误：{record['status']}")
    try:
        # HTTP 200 也可能含 Response.Error，不能直接当作业务成功。
        # Pages 的元素可能是 JSON 字符串，decode_pages 负责逐项解码。
        pages = decode_pages(record["response"])
    except (ValueError, TypeError, AttributeError) as exc:
        raise SystemExit(f"业务错误或响应结构异常：{exc}") from None

    print(f"HTTP {record['status']}，返回 {len(pages)} 条结果")
    for page in pages[:3]:
        print(page.get("title", ""))
        print(page.get("url", ""))


if __name__ == "__main__":
    main()
```

`decode_pages` 也兼容已存 `Mode=1` 空结果响应省略 `Pages` 的情况。空结果不等于“API 没有变更”。

### 3. 检查自己的代码

将待检查的 Python 代码或带 Python 代码块的 Markdown 放在代码根目录，例如 `my_code.py`，执行：

```powershell
python version_guard.py check my_code.py --json my_code_result.json
```

已有相同请求参数的缓存会继续复用。需要获取新的搜索快照时，请在另一份工作副本中运行，并在该副本移走旧 `data/cache/`；当前检查 CLI 没有强制刷新选项。新增查询会真实请求接口并新增缓存，可能消耗配额。保留原始材料中的缓存可用于对照。

### 4. 模型原始回答：复用与再生成是两种操作

离线步骤只读取 `answers/qwen3.8-27b.json`，不会再次询问模型。完整模型测试提示词在 `evaluate.py` 的 `SYSTEM` 与 [cases.json](cases.json) 的逐题 `question` 字段中；`questions` 子命令仅导出题目，不会代替自动调用时的系统提示词。

重新采集需要**自行提供可访问的 OpenAI 兼容模型服务**及模型 ID。发布材料不提供作者的内网服务地址，发布副本中相关 `endpoint_host` 已脱敏，其他回答内容、耗时和用量字段保留。`evaluate.py collect` 向 `--base-url` 后追加 `/chat/completions`；base URL 应包含服务所需的前缀（通常为 `/v1`），不要包含完整 `/chat/completions` 路径。

模型凭证使用 `LLM_API_KEY` 环境变量，经 Bearer 请求头发送；也可以传 `--ask-key` 隐藏输入。无需鉴权的自建服务可以留空。模型密钥与 `YUANBAO_API_KEY` 分开；搜索密钥不会充当模型密钥。PowerShell 示例：

```powershell
$modelBaseUrl = Read-Host '模型 base URL（通常以 /v1 结尾）'
$modelId = Read-Host '服务中实际存在的模型 ID'
python evaluate.py collect --name my-model --base-url $modelBaseUrl --model $modelId --ask-key
python evaluate.py run --name my-model
```

使用**新的 `--name`** 保留原始 Qwen 回答。`collect` 会写入 `answers/my-model.json`，每完成一题保存一次；已有同名回答会跳过，重复执行同名命令是断点续采，不是重新生成。若要再次全量生成，请另取新名字。原实验设置为 `--reasoning-effort medium`；只在自己的服务支持该字段时添加这一选项。新回答受模型、采样、提示词、服务实现和时间影响，不保证得到原实验数字。

首次使用新名字通常会调用模型 32 次，可能产生模型服务费用；随后 `run` 遇到新查询时还可能调用 SearchPro。新模型的结果在 `data/run_my-model.json` 和 `data/review_my-model.csv` 中；当前 `render_report.py` 仍展示冻结的 Qwen 实验。

也可手工收集回答：

```powershell
python evaluate.py questions
python evaluate.py import-md --name manual-model answers/manual-model.md
python evaluate.py run --name manual-model
```

先按 `questions.md` 逐题新开对话，配合 `evaluate.py` 的系统提示词；把回答以 `## 用例ID` 标题写入 `answers/manual-model.md`，保留 Python 代码块。`import-md` 只导入已提供内容，不请求模型；已有同名 JSON 会被导入结果覆盖。之后 `run` 仍遵循搜索缓存命中规则。

## 修复实验：把元宝原文交回给模型

```powershell
python fix_experiment.py --base-url $modelBaseUrl --model $modelId
```

脚本读取 `data/run_qwen3.8-27b.json` 中标为过时的 9 份回答，以及缓存里的元宝搜索结果，向模型发送两种提示：

- A 组只提醒“检查已弃用或已删除的 API”；
- B 组在同样的提醒之外，附上该 API 的元宝搜索结果中排名前 3 的官方页面标题、链接和 `passage`，原样粘贴，不经过规则筛选。

每种条件各 3 次。已存在的试验会跳过，因此重复执行是断点续跑，不会覆盖原结果；要完整重跑，请先在副本中移走 `data/fix_qwen3.8-27b.json`。

评分为静态检查：去掉注释后，旧 API 不再出现，没有引入其他用例的过时写法，并且能通过 `ast` 解析。替代写法由人工逐条核对；除 applymap 单项案例外，修复后的代码未在目标环境中执行。

若本机设置了 `HTTP_PROXY`，访问内网模型服务前，需要把该地址加入 `NO_PROXY`，否则请求可能被代理拦截并返回 502。

## 单项迁移复现：applymap 改为 map

此案例读取保存的 `pd-applymap` 回答，先完整执行原代码，再仅将一处 `.applymap(` 换为 `.map(` 执行。输入、处理函数和其他代码都保持一致。已实测的环境为 Python 3.12.3、pandas 3.0.0；旧调用抛出 `AttributeError`，替代调用输出逐元素翻倍的结果。

在代码根目录用 uv 准备独立依赖环境：

```powershell
uv run --python 3.12 --with pandas==3.0.0 python examples/migrate_applymap.py
```

也可用 Python 3.12 的普通 venv（Windows PowerShell）：

```powershell
py -3.12 -m venv .venv-migration
.\.venv-migration\Scripts\python.exe -m pip install pandas==3.0.0
.\.venv-migration\Scripts\python.exe examples/migrate_applymap.py
```

安装依赖需要下载 Python 包；脚本本身只运行本地 DataFrame 计算，不调用搜索或模型服务。新结果写入 [validation/migration/applymap_pandas300.json](validation/migration/applymap_pandas300.json) 和 [运行日志](validation/migration/applymap_pandas300.log)，原始 `data/`、`answers/` 保持不变。重新执行会覆盖这两份单项验证结果。

JSON 保存了原回答文本哈希、实际 Python/pandas 版本、输入、原错误和新输出。发布副本会脱敏模型内网服务地址，因此对照采用 `answer_text_sha256`，整份回答文件哈希只作参考。该案例独立于原来的批量实验，不改变 9/28、4/9 等计数。

## 文件与判定边界

| 文件或目录 | 作用 |
|---|---|
| [version_guard.py](version_guard.py) | AST 抽取、query 构造、官方域名过滤、句子级判定和检查 CLI |
| [research_client.py](research_client.py) | SearchPro HTTP 调用、原始响应保留和 `Pages` 解析 |
| [evaluate.py](evaluate.py) | `probe / questions / collect / import-md / run`；含完整系统提示词 |
| [cases.json](cases.json) | 32 题、过时模式、预期状态、替代写法和官方标准答案链接 |
| [test_version_guard.py](test_version_guard.py) | 24 个离线规则测试 |
| `data/cache/` | 186 条历史真实搜索调用记录，不含请求密钥 |
| `data/probe*.json`、`data/run_*.json` | 派生实验结果；`_rules_v1` 至 `_rules_v3` 为迭代存档，无规则后缀为冻结 v4 |
| [data/review_qwen3.8-27b.csv](data/review_qwen3.8-27b.csv) | 27 条告警的人工复核；统计直接读取既有结论 |
| [answers/qwen3.8-27b.json](answers/qwen3.8-27b.json) | 32 份模型原始回答，含历史耗时和 token 用量 |
| [render_report.py](render_report.py) → [viewer/index.html](viewer/index.html) | 从本地材料生成完整实验报告 |
| `examples/`、`data/logs/`、`images/` | 示例回答、原始终端日志和报告截图 |
| `examples/hands-on/`、`images/hands-on/` | 文章第六节实操：Claude（官方元宝搜索 MCP）与 WorkBuddy（官方元宝搜索 Skill）演示用代码的修改前后版本，以及已打码、带标注的截图 |
| [examples/migrate_applymap.py](examples/migrate_applymap.py)、`validation/migration/` | 固定 pandas 3.0.0 环境的单项迁移执行与证据 |
| [fix_experiment.py](fix_experiment.py) | 修复实验：9 份过时回答，在“只提醒”和“提醒 + 元宝原文（前 3 条官方摘要）”两种条件下各修 3 次；证据读自缓存，不发起搜索；需要 `--base-url` 和 `--model` |
| [data/fix_qwen3.8-27b.json](data/fix_qwen3.8-27b.json) | 54 次修复试验的提示条件、证据来源（查询与 RequestId）、模型全文、耗时与评分；A 组 18/27、B 组 27/27 |
| `data/cache_query_variants/`、[data/query_variants.json](data/query_variants.json) | 为 4 个缺证据用例补做的 12 次查询词对照（版本号 + whatsnew / 中文 / `Freshness=y1`）；单独存放，不计入上表 186 条 |

规则先过滤 `DOC_SITES` 中的官方域名，再在包含目标符号的句子及附近 120 字窗口中寻找删除、弃用或替代描述，先严格匹配再宽松匹配；会跳过推荐替代写法和所有者类名等情况。输出 `breaking`、`deprecated`、`mentioned`、`no_evidence` 或 `unsupported_lib`。后两类不表示代码已通过目标版本的运行验证；搜索到旧版、翻译版文档，以及同一句中多个 API 的变更，仍可能影响结果。规则在同一批材料上迭代，测试和复核数据的局限见文章。

文章配图可直接使用材料中的现成图片。当前八张小黑手绘插画位于 `images/xiaohei/`，来源和校验值见该目录的README与清单。可选的 `article_charts.py` 只重绘留存的历史统计图，需要另装 `Pillow`，不会生成小黑插画；它不属于上述标准库离线复算流程，也不是生成 `viewer/index.html` 的前置依赖。
