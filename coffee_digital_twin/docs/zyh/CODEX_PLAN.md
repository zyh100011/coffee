# 张源皓负责部分 · Codex 执行计划

版本：2026-10-14 v2（新增 4.7 小程序改造设计及 T3.0、T3.7、T3.8、T5.4）。依据：《咖啡大模型与三模型小程序融合参赛实验方案》2026-10-13 修订版（以下简称“方案”），以及仓库 `ToomyNike/VX_3Models` main 分支代码现状。

赛题：AI+农业 赛题五“农业智能体与大模型决策服务”。作品：咖啡农事循证决策助手。提交截止 2026-10-30 20:00。

## 0. 使用说明（给张源皓本人看）

1. 在 Windows 上 `git clone https://github.com/ToomyNike/VX_3Models.git`，建议放在 `D:\AAACODE\PYTHON\VX_3Models`。
2. 把本文件放到 `VX_3Models\coffee_digital_twin\docs\zyh\CODEX_PLAN.md`，把配套的 `AGENTS.md` 放到 `VX_3Models\AGENTS.md`。
3. 在 `VX_3Models` 目录启动 Codex，第一句话发：`阅读 AGENTS.md 和 coffee_digital_twin/docs/zyh/CODEX_PLAN.md，从 Phase 0 开始按顺序执行，每完成一个任务更新 PROGRESS.md 并提交。`
4. 之后每次只让它推进一个 Phase，做完先看 `docs/zyh/待人工确认.md`，处理完再推进下一阶段。
5. 第 6 节“人工任务”只有你本人能做（下载文献、确认字段、找蔡确认接口、录屏等），Codex 不会替你做。

## 1. Codex 工作约定（必须遵守）

1. 你是执行者：本计划已经确定设计，按任务说明实现；遇到计划与代码事实冲突时，选最小改动方案并写入 `docs/zyh/待人工确认.md`，不要自行重新设计架构。
2. 工作目录：`VX_3Models/coffee_digital_twin`（下称“工程”）。资料目录：`VX_3Models/实验资料`。
3. Git：在分支 `zyh/competition` 上工作，每个任务一个提交，提交信息格式 `[T2.1] HYDRUS 状态与元数据`。不要推送到 main，不要 force push，不要改 git config。
4. Shell 为 Windows PowerShell，命令用 PowerShell 语法；Python 用工程下 `.venv`。
5. 每个任务完成条件：该任务“验收”里的命令全部通过，且 `cd backend; ..\.venv\Scripts\python -m pytest -q` 全绿。
6. 每完成一个任务，在 `docs/zyh/PROGRESS.md` 追加一行：`日期 | 任务号 | 改动文件 | 验收结果 | 遗留问题`。
7. 不得修改的范围：
   - `backend/models/apsim_adapter.py`、`backend/models/beps_adapter.py`（蔡、简负责，只能在外层包装）；
   - `server/hydrus_engine/H1D_CALC.EXE` 及 HYDRUS 数值求解本身；
   - 蔡济远的大模型、RAG、检索、门控算法（本计划只做客户端和 mock）；
   - `实验资料/06_正式测试资料/`（正式题集隔离，不读不写）。
8. 数据纪律：不得用示例值、demo 值或文献值填补真实数据缺失；缺失就写入 `missing_fields`。设备 ID 一律按字符串读取。
9. 安全：工具只走白名单函数，模型输出不能变成命令、文件路径或脚本；不要打印或提交 `backend/.env` 里的密钥；Flask 服务仅供局域网演示，没有鉴权，部署说明里要写明这一点。
10. 依赖必须固定版本，写入 `backend/requirements.txt`。
11. 需要人工输入才能继续时（缺原始 CSV、缺 PDF、缺蔡的接口），先做好桩代码和模板，写入 `待人工确认.md`，然后继续做不受阻塞的任务。

## 2. 职责边界

张源皓（本计划范围）：A3 土壤与根区资料、HYDRUS 接口核验、小程序与 Flask 业务层、真实数据工具、本地服务接入、情景交互、系统交付与运行终审。

不属于本计划：本地大模型部署、知识入库、检索与门控算法、正式评测（蔡济远）；BEPS-Lite、专家评价、PPT/视频/技术方案（简光耀）；APSIM（蔡济远）。本计划只需要给他们提供接口、数据案例和调用轨迹。

## 3. 代码现状诊断（2026-10-14 已读代码确认）

| 编号 | 位置 | 问题 | 方案要求 | 处理任务 |
|---|---|---|---|---|
| D1 | `services/weather_service.py` | 气象全是生成的 demo 序列（`source: demo`），却直接进入三模型 | 不用示例值；demo 单独标识 | T2.4 |
| D2 | `api/model_api.py::_farm_operations` | 没有农事记录时自动补“25mm 灌溉+10kg 尿素” | 缺农事不自动补记录 | T2.4 |
| D3 | `api/model_api.py::_latest_plot` | 没有地块时返回写死的示例地块 | 缺项追问，不静默补值 | T2.4 |
| D4 | `models/hydrus_adapter.py` | 失败时返回 demo，状态写成 `success_with_fallback` | 不把 fallback 当 success | T2.1 |
| D5 | `models/hydrus_adapter.py` | 所有历史灌溉累加到第 1 天；只取第一条降雨；第 2–7 天降水为 0 | 输入口径正确、可追溯 | T2.1 |
| D6 | `templates/hydrus/ATMOSPH.IN` | 没有 `{{evap}}/{{trans}}` 占位符，蒸发蒸腾固定为 0.15/0.22 cm/d，代码传入的 2.8/3.6mm 不生效 | 写明“实际生效参数” | T2.1、T2.3 |
| D7 | `models/hydrus_adapter.py` | 输出日期写死 `2026-04-30`；只输出第 7 天一个剖面 | 时间口径正确 | T2.1 |
| D8 | `models/hydrus_adapter.py` | 写死“强烈建议立即进行补充灌溉”等建议文本 | 降低无依据具体建议 | T2.1 |
| D9 | `SELECTOR.IN` | 土壤水力参数为通用示例值，非地块实测 | HYDRUS 未校准输出为假设情景 | T2.1、T2.3 |
| D10 | `models/fusion_engine.py` | 不检查状态，固定合并三模型；`status` 恒为 success | 先查状态再解释，按可用证据构建报告 | T2.5 |
| D11 | `services/llm_service.py` | 调外部智谱 GLM；提示词强制“必须分别引用 APSIM、HYDRUS、BEPS” | 换本地服务；取消强制凑三模型依据 | T2.7 |
| D12 | `api/advice_api.py`、`api/result_api.py` | 没有 task_id 时取全局最新结果 | 不默认使用全局最新地块结果 | T2.4 |
| D13 | `api/model_api.py::run_model` | 每次都串行跑三模型 | 按需调用工具 | T2.8 |
| D14 | `demo_data/validation_cases.json` | 预填“专家通过”无原始证明 | 不能算真实专家验证 | T2.5 |
| D15 | `server/start_all.ps1` | 写死 `D:\AAACODE\PYTHON\anaconda` 和 conda 环境 `pyweb` | 启动包可在别的机器上运行 | T0.2、T6.1 |
| D16 | `backend/requirements.txt` | 只有 Flask/CORS，缺 `requests` 等 | 依赖完整、版本固定 | T0.2 |
| D17 | 全局 | 无测试 | 功能可核对 | T0.3 |

## 4. 总体设计（Codex 按此实现，不要改设计）

### 4.1 目标调用链

```
小程序 pages/advice（聊天）、pages/scenario（情景）、pages/report（报告）
        │  HTTP JSON
        ▼
Flask 业务层（张源皓）
  api/assistant_api.py   /api/assistant/chat      ← 新主入口
  api/data_api.py        /api/data/*              ← 真实农情查询
  api/scenario_api.py    /api/scenario/compare    ← A/B 情景
  api/report_api.py      /api/report/*            ← 报告
        │
        ├─ services/evidence_client.py  → 蔡的本地循证服务（EVIDENCE_SERVICE_URL）
        │                                  开发期用 tools/mock_evidence_service.py
        ├─ services/tool_registry.py    → 白名单工具：
        │      query_soil_moisture / query_observation / get_plot_profile
        │      run_hydrus_scenario / read_model_result
        ├─ services/tool_result.py      → 统一工具结果封装与校验
        └─ services/trace_store.py      → 每轮完整调用轨迹（给蔡做评测）
```

一轮对话的固定流程（业务层执行，大模型只做理解和生成）：

1. 小程序发送 `{session_id, plot_id, message, history, supplement}`。
2. 业务层调用 `evidence_client.route()`，得到结构化意图：`intent`、`tool_calls[]`、`missing_fields[]`、`clarify_question`。
3. 业务层逐个校验 `tool_calls`：工具名必须在白名单内，参数按 JSON Schema 校验；缺参数先从地块档案读取，读不到就进入追问。
4. 执行工具，得到统一结果（4.2 节）。
5. 调用 `evidence_client.answer()`，传入问题、工具结果、状态；拿到回答、引用、限制说明。
6. 业务层组装前端 `blocks`（4.5 节），写入轨迹表，返回给前端。
7. 追问最多一轮：用户补充后带 `supplement` 重新执行第 3–6 步。第二次仍缺参数时，输出“现场核查事项”，不再继续追问。

### 4.2 统一工具结果（方案第五节字段，必须完全一致）

新建 `backend/services/tool_result.py`，提供 `make_tool_result(**kw) -> dict` 和 `validate_tool_result(d) -> list[str]`（返回错误列表，空表示通过）。字段如下：

| 字段 | 类型 | 说明 |
|---|---|---|
| tool | str | `hydrus` / `apsim` / `beps` / `data_query` / `plot_profile` |
| task_id | str | 本次调用的任务 ID，必须有值 |
| plot_id | str 或 null | 地块 ID；未知时为 null，不能写成 `plot_001` |
| time_range | {start, end} | ISO 日期 |
| status | 枚举 | 见下表 |
| source_type | 枚举 | 见下表 |
| model_version | str | 例如 `HYDRUS-1D H1D_CALC.EXE sha256:前12位` |
| parameter_version | str | 参数文件哈希，例如 `hydrus-params-<sha256前12位>` |
| inputs | dict | 实际写入模型或查询的参数（以生成文件反读为准） |
| assumptions | list[str] | 假设，例如“土壤参数为通用示例值，非地块实测” |
| outputs | dict | 结果数据 |
| units | dict | 例如 `{"theta": "cm3/cm3", "depth": "cm"}` |
| missing_fields | list[str] | 缺失的字段 |
| warnings | list[str] | 警告 |
| evidence_id | str | 全局唯一，格式 `ev_<tool>_<task_id>_<序号>` |
| created_at | str | ISO 时间（附加字段） |
| mode | `live` / `replay` | 实时运行或历史结果回放（附加字段） |

status 枚举：`success`、`missing_input`、`timeout`、`failed`、`fallback`、`replay`。只有 `success` 和 `replay` 可以进入解释；`fallback` 只能在演示中标成“工程演示数据”。

source_type 枚举：`observation`（实测/田间观测）、`literature`（文献）、`simulation_uncalibrated`（未校准模拟）、`proxy_model`（代理模型，如 APSIM-OilPalm）、`simplified_model`（简化模型，如 BEPS-Lite）、`demo`（演示数据）。

### 4.3 与蔡济远本地服务的接口契约（草案，T2.6 写成文档交蔡确认）

环境变量 `EVIDENCE_SERVICE_URL`，默认 `http://127.0.0.1:8001`。超时：route 20 秒，answer 60 秒。

`POST /v1/route`

```json
请求 {"session_id":"s1","message":"3号地40cm最近一周墒情","history":[],"plot_context":{"plot_id":"plot_A","known":{...}},"available_tools":[{"name":"query_soil_moisture","schema":{...}}],"supplement":null}
响应 {"intent":"data_query|knowledge|model_explain|scenario|other","tool_calls":[{"name":"query_soil_moisture","arguments":{"plot_id":"plot_A","depth_cm":40,"start":"2026-09-01","end":"2026-09-07"}}],"missing_fields":[],"clarify_question":null,"need_retrieval":false}
```

`POST /v1/answer`

```json
请求 {"session_id":"s1","message":"...","intent":"data_query","tool_results":[<4.2 统一结果>...],"plot_context":{...}}
响应 {"answer":"...","citations":[{"evidence_id":"ev_x","doc_id":"A3-003","title":"...","locator":"p.12 表3","snippet":"..."}],"claims":[{"text":"...","evidence_ids":["ev_x"]}],"limitations":["..."],"check_items":["..."],"clarify_question":null,"retrieval_trace":{...}}
```

业务层规则：`claims` 里引用的 evidence_id 必须存在于本轮 `tool_results` 或 `citations` 中，否则在前端把这条主张标成“未核验”，并在轨迹里记 `unsupported_claim`。服务不可用时进入降级模式：只返回数据查询的事实块和“智能解释暂不可用”，不调用外部 GLM。

### 4.4 工具白名单（`services/tool_registry.py`）

| 工具名 | 参数（JSON Schema 要点） | 实现 |
|---|---|---|
| `get_plot_profile` | plot_id: str 必填 | 读 plots 表和地块档案，返回字段及缺项 |
| `query_soil_moisture` | plot_id 必填；depth_cm ∈ 已有土层；start/end 为 ISO 日期，跨度 ≤ 366 天；agg ∈ {raw, daily_mean} | 读 `obs_long` 表，返回统计和序列 |
| `query_observation` | plot_id 必填；parameter 必填（取自 catalog）；start/end；agg | 同上，通用参数 |
| `run_hydrus_scenario` | plot_id 必填；start_date 必填；extra_irrigation_mm 为 0–100 的数值；baseline_task_id 可选 | 调 hydrus_adapter，返回统一结果 |
| `read_model_result` | task_id 必填；tool ∈ {apsim, hydrus, beps} | 只读 model_results 表，不重新计算 |

每个工具的函数签名为 `fn(args: dict, ctx: dict) -> dict`（返回统一结果）。参数校验失败时直接返回 `status=missing_input`，不执行工具。未知工具名一律拒绝，并在轨迹里记录。

### 4.5 前端消息块协议（`/api/assistant/chat` 的返回）

```json
{"status":"success","session_id":"s1","turn_id":"t_xxx","trace_id":"tr_xxx",
 "blocks":[
  {"type":"text","text":"..."},
  {"type":"fact","label":"40cm 平均含水率","value":0.213,"unit":"cm3/cm3","evidence_id":"ev_..."},
  {"type":"chart","chart":"line","series":[{"name":"40cm","data":[["2026-09-01",0.22],...]}],"evidence_id":"ev_..."},
  {"type":"evidence","items":[{"evidence_id":"...","label":"实测|文献|未校准模拟|代理模型|简化模型|演示","detail":"来源、时间、版本"}]},
  {"type":"missing","fields":["start_date"],"question":"请问要查哪一段时间？","quick_replies":["最近7天","最近30天"]},
  {"type":"warning","text":"HYDRUS 未用本地块土壤参数校准，结果仅为假设情景"},
  {"type":"check_items","items":["核对3号地40cm探头是否正常"]},
  {"type":"report_link","report_id":"rp_xxx"}
 ]}
```

前端只按 `type` 渲染，不自己拼业务逻辑。证据标签颜色固定：实测为绿，文献为蓝，未校准模拟为橙，代理/简化模型为灰，演示为红底白字。



### 4.6 新增文件总览

```
coffee_digital_twin/
  .venv/                              (不提交)
  backend/
    api/assistant_api.py  data_api.py  scenario_api.py  report_api.py
    services/tool_result.py  tool_registry.py  evidence_client.py  trace_store.py
            plot_context.py  report_builder.py
    models/hydrus_adapter.py          (改造)
    data_pipeline/profile_raw.py  ingest_monitoring.py  ingest_lai.py
                 ingest_events.py  ingest_soil_reports.py  column_mapping.yaml
                 device_plot_map.csv  freeze.py
    tools/mock_evidence_service.py  mock_corpus.json  generate_hydrus_cases.py
          selfcheck.py  inventory_assets.py  ledger_check.py  export_traces.py
          export_verifiable_cases.py  seed_demo.py  check_links.py  reset_demo.ps1
    tests/test_*.py
    .env.example
  miniprogram/pages/plots/  data/  report/  evidence/          (新增，见 4.7)
  miniprogram/components/msg-blocks/  evidence-tag/  line-chart/
                         plot-bar/  banner/  empty-state/     (新增)
  miniprogram/utils/session.js  labels.js  errors.js            (新增)
  docs/zyh/CODEX_PLAN.md  PROGRESS.md  待人工确认.md  页面接口复用清单.md
           HYDRUS工具说明.md  本地服务接口契约.md  数据字典.md  清洗日志.md
           错误码与降级.md  演示流程.md  操作手册.md  功能核对表.md  交付目录.md
           新旧贡献记录.md  screenshots/
实验资料/   (方案 6.7 目录，见 T1.3)
```

### 4.7 小程序改造设计（在旧小程序上改，不重写）

#### 4.7.1 原则

1. 在原工程 `miniprogram/` 上增量改造：沿用原来的配色、`app.wxss` 公共类、`status-card`、`risk-badge`、`loading-panel`、`chart-card` 和 `utils/request.js`，不换框架、不引入 npm 包或 UI 库。
2. 方案第十一节要求“本届原创、旧作者贡献不改写成本届原创”。所以每改一个文件，都要在 `docs/zyh/新旧贡献记录.md` 里登记（见 T5.4）。旧代码里的 `AI辅助生成-DeepSeek-V3` 注释和原作者署名保留不删。
3. 作品名改为“咖啡农事循证决策助手”。页面上不再出现“三模型互证”“核心亮点”“专家复核：通过”这类没有依据的说法。
4. 界面上每个数字都要能回答“它从哪来”，统一用证据标签表示来源（4.7.4）。
5. 页面不自己做业务判断。是否可用、状态、缺项都以后端返回的 `status`、`source_type`、`missing_fields`、`blocks` 为准。

#### 4.7.2 对旧小程序的诊断（2026-10-14 读代码确认）

| 编号 | 位置 | 问题 | 处理 |
|---|---|---|---|
| M1 | `utils/config.js` | 本地未提交改动，把 BASE_URL 改成了 cpolar 公网隧道地址；后端没有鉴权，等于把服务暴露到公网 | T6.1：改为环境切换，默认 127.0.0.1；文档写明不要用公网隧道，确实要用的话演示完立刻关掉 |
| M2 | `pages/plotInit` 和 `backend/api/plot_api.py::_default_plot` | 表单预填“潞江坝 12.5 亩”等示例值；后端字段为空时也用示例值补上 | T3.7：表单不预填，后端缺失字段存 null，前端显示“未填写” |
| M3 | `pages/farmLog` | 预填 25mm、10kg 尿素；日期是自由文本；数量为空时 `Number('')` 得到 0 | T3.7：日期用 picker，单位用 picker，必填校验，空值不提交 |
| M4 | `backend/api/farmop_api.py::_latest_plot_id` | 找不到地块时回落到 `"plot_001"` | T3.7：没有 plot_id 时返回 400 |
| M5 | `pages/result` | 内置 3 条“专家复核：通过”的静态验证案例作为兜底；“三模型联合判断”在任何情况下都显示 | T3.2：删除内置案例；验证案例显示“未验证”；联合判断只在后端返回的可用工具 ≥2 时显示 |
| M6 | `pages/advice` | 进入页面自动调用 `/generate`，以“三模型依据”开场；网络错误提示统一写“稍后重试” | T3.1：改为循证问答页 |
| M7 | `ec-canvas/` | 只是 57 字节的空占位，不是真的 ECharts | 不用它。新建原生 Canvas 2D 折线图组件 `line-chart`（4.7.5） |
| M8 | `pages/index` | 首页指标全来自全局最新的模型结果（APSIM 产量等），没有地块选择 | T3.7：首页改为当前地块的工作台 |
| M9 | `app.json` | 没有 tabBar，全靠按钮跳转，演示时容易迷路 | T3.7：加纯文字 tabBar |
| M10 | 全局 | 原生组件上没有无障碍标注；部分提示只靠颜色区分 | 按 4.7.7 补齐 |

`utils/storage.js` 里已经有 `savePlotId/getPlotId`（key 为 `plotId`），直接沿用，不新建 `currentPlotId`。全文凡是写 `setCurrentPlotId/getCurrentPlotId` 的地方，都按 `savePlotId/getPlotId` 实现。

#### 4.7.3 信息架构与导航

`app.json` 的页面顺序和 tabBar（纯文字，不配图标文件）：

```json
"pages": ["pages/index/index","pages/advice/advice","pages/data/data","pages/scenario/scenario",
          "pages/plots/plots","pages/plotInit/plotInit","pages/farmLog/farmLog",
          "pages/result/result","pages/report/report","pages/evidence/evidence"],
"tabBar": {"color":"#5f6b63","selectedColor":"#1f5a3a","backgroundColor":"#ffffff","borderStyle":"black",
  "list":[{"pagePath":"pages/index/index","text":"工作台"},
          {"pagePath":"pages/advice/advice","text":"问答"},
          {"pagePath":"pages/data/data","text":"农情"},
          {"pagePath":"pages/scenario/scenario","text":"情景"}]}
```

- 这 4 个 tab 页之间只能用 `wx.switchTab` 跳转，不能带 query。跨页参数（例如从工作台带一个问题进问答页）先写入 `utils/session.js`，目标页在 `onShow` 时读取并清空。
- 非 tab 页：`plots`（地块列表）、`plotInit`（新建/编辑地块）、`farmLog`（农事记录）、`result`（模型结果，保留旧页面）、`report`（报告）、`evidence`（证据详情），都用 `wx.navigateTo`。
- 全局顶部条：除 evidence 页外，每页顶部都有一行“当前地块：XX ▸ 切换”，点击进入 plots。如果后端 health 显示 mock 或 replay，在这行下面再加一条横幅（4.7.4）。

#### 4.7.4 视觉规范与证据标签

沿用旧色板，新增语义色。以下文字/底色对比度都已计算过，均 ≥ 4.5:1：

| 用途 | 文字色 | 底色 | 对比度 |
|---|---|---|---|
| 主色按钮 | #ffffff | #1f5a3a | 8.1 |
| 正文 | #1d2a22 | #f4f7f3 | 13.8 |
| 次要文字 | #5f6b63 | #ffffff | 5.6 |
| 实测 | #1f6b40 | #e4f2e9 | 5.6 |
| 文献 | #1d4f91 | #e3ecf8 | 6.8 |
| 未校准模拟 | #8a4b00 | #fff1d6 | 6.1 |
| 代理/简化模型 | #4b5563 | #eceff1 | 6.5 |
| 回放 | #5b3fa0 | #efeafb | 6.7 |
| 演示数据（demo/fallback） | #ffffff | #b42318 | 6.6 |

`app.wxss` 新增 CSS 变量（写在 `page{}` 里）和工具类 `.tag`、`.tag-observation`、`.tag-literature`、`.tag-simulation`、`.tag-proxy`、`.tag-replay`、`.tag-demo`、`.banner`、`.banner-mock`、`.banner-replay`。

证据标签组件 `components/evidence-tag/`：

- 属性：`sourceType`、`status`、`mode`、`size`（`sm`/`md`）。
- 文案映射：observation→“实测”，literature→“文献”，simulation_uncalibrated→“模拟·未校准”，proxy_model→“代理模型”，simplified_model→“简化模型”，demo→“演示数据”。`mode=replay` 时在文案后加“·回放”。`status` ∈ {failed, timeout, missing_input} 时整体显示为“不可用”（灰底），不显示来源。
- 标签必须带文字，不能只有色块；`aria-label` 写完整含义，例如“证据类型：未校准模拟，历史结果回放”。

横幅：

- mock 服务：红底白字“当前为 MOCK 服务，回答由规则生成，仅用于联调”；
- 回放模式：紫色“HYDRUS 为历史结果回放（生成于 X）”；
- 后端离线：灰色“后端未连接 · 重试”。

字号（rpx）：页标题 36/700，区块标题 30/700，正文 28，辅助 24，数值 44/700。触控目标高度不小于 88rpx，间距按 8 的倍数取。

#### 4.7.5 组件清单

| 组件 | 状态 | 属性 | 说明 |
|---|---|---|---|
| `status-card` | 改造 | `label, value, unit, sub, sourceType, status` | 新增来源标签槽；status 不可用时 value 显示“—”，sub 显示原因 |
| `risk-badge` | 保留 | — | 只在 fusion 顶层 status ≠ failed 时使用 |
| `loading-panel` | 改造 | `text, steps` | 新增 `steps` 数组，按顺序展示处理阶段（见 msg-blocks 的 trace） |
| `chart-card` | 保留 | — | 继续用于土壤剖面横条 |
| `line-chart` | 新建 | `series:[{name, color, data:[[x,y]...]}], unit, yMin, yMax, height=420` | 用 `<canvas type="2d">` 原生绘制：坐标轴、5 个刻度、最多 3 条折线、图例、无数据提示。在 `ready` 生命周期里用 `wx.createSelectorQuery().in(this)` 获取节点，并按 `wx.getWindowInfo().pixelRatio` 缩放。下方提供“查看数据表”切换，以表格列出所有点（无障碍和数据核验都需要）。不引入 ECharts |
| `evidence-tag` | 新建 | 见 4.7.4 | — |
| `msg-blocks` | 新建 | `blocks, disabled` | 按 type 渲染全部消息块；对外触发事件 `quickreply(detail:{text, supplement})`、`openevidence(detail:{evidence_id})`、`openreport(detail:{report_id})` |
| `plot-bar` | 新建 | `plot` | 顶部“当前地块”条，点击跳 plots |
| `banner` | 新建 | `kind, text, actionText` | mock、回放、离线三种横幅，可带一个操作按钮 |
| `empty-state` | 新建 | `title, desc, actionText` | 空状态加一个主操作，例如“还没有地块 → 新建地块” |

对 4.5 节的补充：后端每轮回复的 `blocks` 末尾都追加一个处理轨迹块：

```json
{"type":"trace","steps":[
  {"name":"理解问题","status":"done","detail":"农情查询"},
  {"name":"查依据","status":"skipped","detail":"本题不需要文献"},
  {"name":"查农情","status":"done","detail":"query_soil_moisture · 7天 · 40cm"},
  {"name":"选工具","status":"done","detail":"白名单校验通过"},
  {"name":"比较情景","status":"skipped"},
  {"name":"解释结果","status":"done"},
  {"name":"核对答案","status":"warn","detail":"1 条主张未核验"}]}
```

这 7 步对应方案第一节的闭环“理解问题—查依据—查农情—选工具—比较情景—解释结果—输出报告”。`status` 取值为 done、skipped、warn、failed。前端默认折叠成一行，例如“处理过程 6/7 完成 ▸”。T2.8 的 assistant_api 负责生成这个块。

#### 4.7.6 页面设计

全局状态由 `utils/session.js` 管理（新建）：`sessionId`（问答页首次进入时生成，`s_` + 时间戳 + 4 位随机数）、`pendingQuestion`、`health`（启动时请求 `/api/assistant/health`，缓存 60 秒）、`lastCompareId`。

页面状态统一分为 5 种：loading、ready、empty、error（显示错误码对应的文案和“重试”）、offline。每个页面都要实现这 5 种状态。

**P1 工作台 `pages/index`（改造，tab）**

```
┌ 当前地块：3号地 ▸ 切换 ───────────────┐
│ [MOCK/回放 横幅，按 health 显示]         │
├ 地块档案完整度  7/12  缺：土质、遮阴 ▸ ┤  → plots
├ 最近墒情（实测）                        │
│  40cm 0.213 cm³/cm³ · 09-07  [实测]     │  ← /api/data/query 最近 7 天 daily_mean
│  [line-chart 7 天]                       │
├ 快捷提问                                 │
│  [这块地40cm最近一周墒情怎么样]          │  → 写 pendingQuestion，切到问答 tab
│  [咖啡根系主要分布在多深]                │
│  [如果多浇20mm，土壤水分会怎样]          │
├ 模型工具状态  APSIM 代理 · HYDRUS 回放 · BEPS 简化 ┤ ← health / 最近一次 tool_status
├ [农事记录]  [模型结果]  [历史报告]      │
└──────────────────────────────────────────┘
```

- 删掉原来的“采收倒计时/预计亩产”大卡片。APSIM 的数值只在 result 页显示，并带“代理模型”标签。
- 没有地块时整页显示 empty-state：“还没有地块 → 新建地块”。
- 当前地块没有监测数据时，墒情区显示“该地块暂无已入库的监测数据”，不画图。

**P2 问答 `pages/advice`（改造，tab）**

```
┌ plot-bar ───────────────────────────────┐
│ 循证问答 · 回答会标出处、数据来源和缺项 │
├ 聊天流（scroll-view）                   │
│  用户气泡                                │
│  助手：msg-blocks                        │
│   ├ text                                 │
│   ├ fact 卡片 [实测] 0.213 cm³/cm³ ▸     │ → evidence 页
│   ├ chart(line-chart)                    │
│   ├ missing：请问查哪段时间？[最近7天][最近30天] │
│   ├ warning（黄条）                       │
│   ├ check_items（复选清单，仅展示）       │
│   ├ evidence 列表（折叠）                 │
│   ├ trace（折叠）                         │
│   └ [生成报告]                            │
├ 示例问题 chips（聊天为空时显示）        │
├ 输入框  [发送]                           │
└──────────────────────────────────────────┘
```

- 发送时，等待区用 `loading-panel` 的 steps 依次高亮“理解问题 → 查询/检索 → 生成答案”。这只是前端计时动画（每 1.5 秒推进一步，最多停在最后一步），文字写“处理中”，不能冒充真实进度。真实轨迹以返回的 trace 块为准。
- 历史：只保留最近 10 轮的 `{role, content}`，助手的 content 取 text 块拼接，不把 blocks 整个发回后端。
- 点 missing 的 quick reply 时，把它作为 `supplement` 和原问题一起发送；用户手动输入的补充同样按 supplement 处理（当前轮还有未解决的 missing 时）。
- 失败处理：按错误码显示文案；`retryable` 为真时显示“重试”，重发上一条消息。
- 从工作台进入时，`onShow` 读取 `pendingQuestion`，自动发送一次后清空。
- 不再在进入页面时调用 `/api/advice/generate`。旧接口保留给 result 页的“生成建议”按钮。

**P3 农情查询 `pages/data`（新建，tab）**

不依赖大模型，直接查真实数据。这是方案研究任务 2 的人工入口，也是 LLM 服务不可用时的演示备用路径。

```
┌ plot-bar ───────────────────────────────┐
│ 参数 [土壤含水量 ▾]  深度 [40cm ▾]       │ ← /api/data/catalog
│ 时间 [2026-09-01] ~ [2026-09-07]  聚合 [日均 ▾] │
│ [查询]                                   │
├ 结果  [实测]  data-v1.0                  │
│ n=7  均值 0.213  最小 0.198  最大 0.231  缺测 0 天 │
│ [line-chart]  [查看数据表]               │
│ 已排除异常 2 条（out_of_range）▸          │
│ 来源：文件 xxx.csv  ▸ 逐条回查            │ → evidence 页
└──────────────────────────────────────────┘
```

- 参数、深度、日期的可选范围全部来自 catalog，不在前端写死；日期 picker 的 start/end 限制在 catalog 的日期范围内。
- catalog 为空时显示 empty-state：“该地块暂无入库数据，请先完成数据导入（见操作手册）”。
- 本页不提供任何建议文字。

**P4 情景 `pages/scenario`（改造，tab）**：三步向导，用顶部步骤条显示“1 设定 → 2 确认 → 3 对比”。

```
Step1 设定
  基线：3号地 · 起始 [2026-09-01] · 窗口 7 天
  窗口内已记录灌溉：09-02 15mm（农事记录）/ 无
  变化：额外灌溉 [20] mm  (slider 0–100，步长 5，旁边有数字输入框)
  快捷：[+10mm] [+20mm] [+30mm]   其他情景卡片：遮阴/追肥 → “本期不支持”灰卡
  [下一步]
Step2 确认（/api/scenario/compare confirm=false 返回）
  将比较：基线 vs 基线+20mm（第1天）
  模型：HYDRUS-1D [模拟·未校准]（回放时加 ·回放）
  假设（逐条列出 assumptions）
  ⚠ 模拟假设，非实际灌溉指令
  [返回修改]  [确认运行]
Step3 对比（confirm=true 返回）
  line-chart：40cm 逐日 theta，两条线（基线 #5f6b63 实线，变化组 #1f5a3a），图例写明
  表格：深度 | 基线第7天 | 变化第7天 | 差值   (10/20/40/60/100cm)
  湿润锋 X→Y cm，吸水比 a→b
  参数核验：第1天降水 +2.0cm ✓（来自调用轨迹）
  未确定条件：undetermined 列表
  [生成报告] [问问助手怎么理解]  ← 后者写 pendingQuestion="解释情景对比 <compare_id>" 并切到问答 tab
```

- 运行中显示 loading-panel，文字为“HYDRUS 计算中（最长约 60 秒）”。超时后提示“计算超时，可重试或改用历史结果”，按钮调用 `mode: replay`。
- 返回 `status=failed` 时，第 3 步只显示失败原因和恢复按钮，不显示任何差值。

**P5 地块 `pages/plots`（新建）和 `pages/plotInit`（改造）**

- plots：列表来自 `/api/plot/list`。每项显示名称、品种、档案完整度（X/12）和缺失字段。操作有“设为当前”（`savePlotId`）、“编辑”（plotInit?plot_id=）、“农事记录”（farmLog?plot_id=）。底部按钮“新建地块”。
- plotInit：所有输入框不预填，只给 placeholder 示例（例如“如：赤红壤”）。字段分三组：基本（名称*、品种、树龄、面积）、位置（经纬度、海拔）、栽培（土质、遮阴、密度、行距、株距）。只有名称必填，其余可以空着，空值提交为 null。提交后返回 plots。
- 字段旁的“来源”下拉（现场记录/估计/未知）写入 `raw_json.field_sources`。后端原样保存，供大模型区分已核验档案和估计值（方案 2.2“缺失的关键参数先从已核验地块档案读取”）。

**P6 农事记录 `pages/farmLog`（改造）**

- 上半部分是记录列表（`/api/farmop/list?plot_id=`），按日期倒序；下半部分是新增表单。
- 日期用 `picker mode="date"`；灌溉单位 picker 选项为 [mm, 吨/亩]，施肥单位为 [kg/亩, kg/ha]。数量必填且大于 0，没填时不允许提交，并在字段下方显示错误文字。
- 去掉所有预填数值，“肥料类型”只给 placeholder。
- 每条记录显示来源标签“农事记录（用户录入）”。这类记录不是实测数据，标签用灰色系，文案为“记录”。

**P7 模型结果 `pages/result`（改造，保留旧页面）**

- 顶部显示 `tool_status` 三个徽章。每张模型卡片标题右侧放 evidence-tag。
- status 不是 success/replay 的模型，卡片只显示“不可用：<warnings[0]>”，不画图、不显示数值。
- “三模型联合判断”区块：只有 available_evidence ≥ 2 时显示，标题改为“可用模型综合说明”；如果有 `dependency_note`，原文显示在下方。
- 验证案例区块：标题改为“示范案例（未经专家验证）”，删除“专家复核”这一行和内置的静态兜底案例；接口失败就不显示这个区块。
- HYDRUS 卡片：剖面用 chart-card，逐日序列用 line-chart（d10/d40/d60 三条线）。
- “模型说明”文案按 `HYDRUS工具说明.md` 改写为如实描述：APSIM 写成“OilPalm 代理映射，无咖啡产量验证”，BEPS 写成“简化计算”，HYDRUS 写成“未校准，假设情景”。删除“避免误判”这类没有依据的说法。

**P8 报告 `pages/report`（新建）**

- 参数为 `report_id`，数据来自 `GET /api/report/<id>`。按“事实 → 依据 → 情景差异 → 建议/核查 → 缺项与限制”分节显示，每节标题旁列出 evidence-tag，节末附“依据：ev_xxx ▸”。
- 底部按钮：“复制 HTML 报告链接”（`wx.setClipboardData`，内容为 `<BASE_URL>/api/report/<id>.html`），提示“在电脑浏览器打开后可打印为 PDF”。
- 工作台的“历史报告”入口打开报告列表。需要新增 `GET /api/report/list?plot_id=`，在 T3.3 里一并实现。

**P9 证据详情 `pages/evidence`（新建）**

- 参数为 `evidence_id`，数据来自新增接口 `GET /api/evidence/<evidence_id>`（T2.8 一并实现）：在 `assistant_traces`、`scenario_compares`、`model_results` 中查找该证据，返回统一工具结果或 citation 原文。
- 工具结果显示：tool、status、source_type、time_range、model_version、parameter_version、inputs（键值表）、assumptions、warnings。observation 类加“逐条回查”按钮，调用 `/api/data/source/<obs_id>` 显示原文件和行号。
- 文献类显示：doc_id、标题、页码定位、snippet。
- 找不到证据时显示“证据未找到：该主张未核验”。

#### 4.7.7 无障碍与可用性要求（每个页面都要满足）

- 可点击的 `view` 都要加 `aria-role="button"` 和 `aria-label`；图标或符号旁边必须有文字。
- 状态不能只用颜色表达，标签和横幅都要写文字。
- 折线图必须提供“查看数据表”入口。
- 表单错误文字放在字段下方，不能只弹 toast。
- 系统字体放大到 1.3 倍时布局不溢出：卡片用 flex-wrap，不写死高度。
- 网络请求期间禁止重复提交：按钮设 loading 和 disabled。

#### 4.7.8 前端改动与后端接口的对应

| 页面 | 调用 | 后端任务 |
|---|---|---|
| 全局 | `GET /api/assistant/health` | T2.8 |
| index | `/api/plot/list`、`/api/data/query`、`/api/model/result?plot_id=` | T3.7、T2.6 |
| advice | `POST /api/assistant/chat` | T2.8 |
| data | `GET /api/data/catalog`、`POST /api/data/query`、`GET /api/data/source/<id>` | T2.6 |
| scenario | `POST /api/scenario/compare` | T4.1 |
| plots/plotInit | `GET /api/plot/list`、`GET /api/plot/<id>`、`POST /api/plot/init` | T3.7 |
| farmLog | `GET /api/farmop/list`、`POST /api/farmop/add` | T3.7 |
| result | `GET /api/model/result/<task_id>` | T2.5 |
| report | `POST /api/report/create`、`GET /api/report/<id>`、`GET /api/report/list` | T3.3 |
| evidence | `GET /api/evidence/<id>` | T2.8 |

## 5. 任务清单

每个任务都写明了目标、步骤和验收。日期是最迟完成日。

### Phase 0 · 环境与基线（10/14）

T0.1 建分支和进度文件
- 执行 `git status`。如果有未提交的改动（例如只有换行符 CRLF/LF 的差异），先运行 `git diff --ignore-all-space --stat` 确认实际内容差异，再写进 PROGRESS；不要 `reset` 或 `checkout --` 丢弃这些改动。
- 执行 `git checkout -b zyh/competition`。
- 新建 `docs/zyh/PROGRESS.md`（表头：日期 | 任务 | 改动文件 | 验收 | 遗留）和 `docs/zyh/待人工确认.md`（表头：编号 | 问题 | 需要谁 | 阻塞的任务 | 状态）。
- 验收：`git branch --show-current` 输出 `zyh/competition`。

T0.2 可移植运行环境
- 在工程根目录执行 `py -3.11 -m venv .venv`；没有 3.11 就用本机 3.10–3.12，并在 PROGRESS 中记录版本。
- `backend/requirements.txt` 固定为：`Flask==3.0.3`、`Flask-Cors==4.0.1`、`requests==2.32.3`、`pandas==2.2.3`、`PyYAML==6.0.2`、`charset-normalizer==3.4.0`、`jsonschema==4.23.0`、`pytest==8.3.3`。安装失败时换成该包最近的稳定版本，并记录。
- 新建 `backend/.env.example`，包含：`EVIDENCE_SERVICE_URL=http://127.0.0.1:8001`、`HYDRUS_EXE=`、`HYDRUS_TIMEOUT_S=60`、`HYDRUS_MODE=live`、`ALLOW_DEMO_FALLBACK=0`、`FLASK_DEBUG=0`、`DATA_VERSION=`。`config.py` 读取这些变量，并在启动时自动加载 `.env`（自己写 10 行解析，不引入 python-dotenv）。
- `.gitignore` 增加 `.venv/`、`backend/.env`、`实验资料/01_原始知识资料/**/*.pdf`、`实验资料/03_地块与监测数据/raw/`、`实验资料/06_正式测试资料/`。
- 新建 `server/start_backend.ps1`：激活 `.venv` 后运行 `python backend\app.py`，不依赖 conda 或 D 盘路径。保留旧的 `start_all.ps1`，不删除。
- 验收：`.\server\start_backend.ps1` 启动后，`Invoke-RestMethod http://127.0.0.1:5000/api/ping` 返回 `status=ok`。

T0.3 测试骨架和现状快照
- 新建 `backend/tests/conftest.py`：使用 Flask test_client，`DATABASE_PATH` 指向临时目录（通过环境变量 `COFFEE_DB_PATH` 覆盖，`config.py` 要支持）。
- 新建 `backend/tests/test_smoke.py`：覆盖 `/api/ping`、`/api/plot/latest`、`/api/farmop/list`、`/api/model/run`，只断言 HTTP 200 和顶层 key，不断言数值。
- 运行一次 `/api/model/run`，把返回 JSON 存到 `docs/zyh/baseline_snapshot_before.json`，留作改造前对照。
- 注意：T2.4 之后 `/api/model/run` 没有地块时会返回 400，届时同步更新这个冒烟测试（先建地块再运行）。
- 验收：`pytest -q` 全绿。

T0.4 HYDRUS 引擎在本机可运行
- 运行 `cd backend; ..\.venv\Scripts\python -c "from models.hydrus_adapter import run_hydrus_model as r; import json; print(json.dumps(r({'task_id':'t0_4','plot_id':'p','farm_operations':[{'op_type':'irrigation','amount':25,'unit':'mm'}]}),ensure_ascii=False)[:800])"`。
- 检查 `backend/runtime/hydrus_runs/t0_4/` 下是否生成了 `T_Level.out`、`Nod_Inf.out`，并且没有 `Error.msg`。
- 输出的 status 是 `success_with_fallback` 时，就是没跑通：把报错写进 `待人工确认.md`，然后继续后面的任务。
- 验收：PROGRESS 里写明“HYDRUS 实时可运行：是/否”，并附运行目录文件清单。

### Phase 1 · 复用清单、资料目录与数据资产（10/14–15）

T1.1 页面和接口复用清单 → `docs/zyh/页面接口复用清单.md`
- 逐个读 `miniprogram/pages/*` 和 `backend/api/*`，填一张表，列为：页面/接口 | 当前功能 | 调用的 API | 结论（直接复用 / 改造 / 新增 / 弃用） | 改造点 | 对应任务号。
- 下面的预设结论按代码核实后填写，与代码不符的写进待人工确认：

| 对象 | 结论 | 改造点 |
|---|---|---|
| pages/index | 改造 | 改为当前地块工作台（4.7.6 P1） |
| pages/plotInit | 改造 | 去掉预填示例值，支持编辑（P5） |
| pages/farmLog | 改造 | 列表+表单、日期/单位 picker、必填校验（P6） |
| pages/result | 改造 | 状态徽章、证据标签、删除“专家通过”兜底（P7） |
| pages/scenario | 改造 | 改成 A/B 情景确认和对比页（T4.1） |
| pages/advice | 改造 | 接 `/api/assistant/chat`，按 blocks 渲染（T3.1） |
| pages/report | 新增 | 报告页（T3.3，P8） |
| pages/plots、data、evidence | 新增 | 地块列表、农情查询、证据详情（P5、P3、P9） |
| /api/advice/generate、/api/advice/chat | 改造 | 转接新服务；必须传 task_id 或 plot_id |
| /api/model/run | 改造 | 去掉自动补地块、补农事；结果带状态 |
| /api/dashboard | 改造 | 必须指定 plot_id |
| /api/model/validation_cases | 改造 | 加 `verification_status: "unverified"` |

- 地块与任务绑定规则（写进清单）：沿用已有的 `utils/storage.js::savePlotId/getPlotId`（storage key 为 `plotId`），所有请求带 plot_id；每次模型运行生成 task_id，并与 plot_id、时间段、参数版本一起写入 `model_tasks`。
- 验收：清单覆盖 6 个页面和全部 API，没有遗漏。

T1.2 资产盘点脚本 → `backend/tools/inventory_assets.py`
- 递归扫描 `实验资料/03_地块与监测数据/raw/`，对每个文件输出：文件名、相对路径、大小、sha256、扩展名、编码猜测；CSV/TXT/XLSX 还要输出行数、列名、前 3 行，以及能识别出的日期列的最小和最大值。
- 输出 `实验资料/03_地块与监测数据/资产清单.csv`，同时打印汇总：文件数和疑似重复（同一 sha256，或列名相同且日期区间重叠）。
- 目录为空时提示“请把原始导出放入 raw/”，正常退出（返回码 0）。
- 验收：在 `backend/tests/fixtures/raw_sample/` 放两份构造的小 CSV（一份是另一份的重叠导出），测试能识别出重叠。

T1.3 实验资料目录（方案 6.7） → `VX_3Models/实验资料/`
- 建立 01–08 八个目录，每个目录放一份 `README.md`，写明用途和负责人（照抄方案 6.7 的注释）。
- 在 `01_原始知识资料/` 下建 `A1_咖啡农技 … A7_模型接口` 子目录，并新建 `来源台账.csv`，表头严格使用方案 6.3 的字段：`doc_id,标题,作者/机构,发布年份/版本,原始链接或内部来源,保存路径,主题,地区,作物/品种,生育期,土壤/冠层条件,有效状态,使用权限,审核状态,采集人`。另加三列：`参数类型(文献/推算/实测)`、`页码定位`、`交叉核查人`。
- 在 `02_标准化知识语料/` 下新建 `土壤字段映射表.csv`，列为：`模型字段,HYDRUS变量,含义,单位,土层/深度,数值,参数类型(实测/文献/推算),doc_id,页码,适用条件,备注`。预填行（数值留空）：thr、ths、Alfa、n、Ks、l、土层分界深度、初始压力水头 h、根系分布 Beta、Feddes P0/P2H/P2L/P3、容重、质地（砂/粉/黏）、pH、EC、田间持水量、凋萎点。
- 新建 `缺项表.csv`，列为：`字段,需要它的模型,当前状态,替代做法,负责人,预计获取日期`。
- 新建 `实验资料/03_地块与监测数据/raw/README.md`：说明六份主要 CSV、六份补充导出、IN-G10 TXT、土壤报告按原样放入，不改文件名。
- 验收：目录结构存在；正式测试资料目录被 gitignore；`git status` 里看不到 PDF 和 raw 原始数据。

T1.4 A3 土壤资料辅助（文献由张源皓本人下载，Codex 不爬取）
- 新建 `backend/tools/ledger_check.py`：读 `来源台账.csv`，检查必填字段是否为空（未知应填“未知”而不是留空）、doc_id 是否重复、保存路径的文件是否存在、同一 sha256 是否重复登记。输出问题列表。
- 在 `01_原始知识资料/A3_土壤根区/检索清单.md` 写 10 个检索主题，供张源皓自己去找原文：①云南咖啡园土壤理化性质 ②赤红壤/砖红壤水力特性与 van Genuchten 参数 ③咖啡根系分布深度 ④咖啡园土壤含水量与灌溉 ⑤土壤容重与质地测定方法（标准） ⑥土壤水分传感器（FDR/TDR）标定 ⑦HYDRUS-1D 在热带果园/咖啡上的应用 ⑧田间持水量与凋萎点测定 ⑨入渗与 Ks 测定方法 ⑩pH/EC 测定标准。
- 验收：`python tools/ledger_check.py` 对示例台账能正确报错。

T1.5 开发集土壤 10 题模板 → `实验资料/05_开发与训练资料/dev_soil_zyh.jsonl`
- 每行字段：`qid,任务类型(knowledge|data|model_explain|scenario|missing_or_conflict),问题,情境,证据ID,期望工具,期望参数,参考回答要点,评分项,出题人`。
- 写 10 行骨架，5 种任务类型各 2 题。问题文本先用占位“【待张源皓填写】”，Codex 不编造参考答案。
- 验收：文件能被 `json.loads` 逐行解析。

### Phase 2 · HYDRUS 工具包、业务层修正、数据工具、本地服务接入（10/15–16）

T2.1 改造 `backend/models/hydrus_adapter.py`（只改适配层，不改数值求解）
- 保留函数名 `run_hydrus_model(model_input_json)`，返回值改为 4.2 节的统一结果。为了兼容旧前端，把 `outputs` 里的 `water_status`、`root_uptake_ratio`、`infiltration_depth_cm`、`soil_profile_current`、`soil_moisture_series` 同时复制到顶层，T3.2 完成后再删掉。
- 输入构建 `_build_hydrus_input(model_input_json)`：
  - `start_date`：依次取 `scenario.start_date`、`model_input_json.start_date`；都没有时返回 `status=missing_input`、`missing_fields=["start_date"]`，不运行引擎。
  - 模拟窗口固定 7 天（与模板中 MaxAL=7、tMax=7 一致）。
  - 第 i 天降水 = 当天实测降雨 + 当天灌溉。实测降雨只取 `weather_series` 中 `source != "demo"` 且日期匹配的记录；取不到时按 0，并在 assumptions 里写“无实测降雨，第 X–Y 天降雨按 0 mm 假设”。
  - 灌溉只统计 `farm_operations` 中日期落在窗口内的 irrigation（用 `normalize_irrigation_mm` 换算）。`scenario.extra_irrigation_mm` 加在第 1 天，并写入 assumptions。
  - 不再把全部历史灌溉累加到第 1 天（D5）。
- ATMOSPH.IN 改为由代码逐行生成 7 行，格式与模板保持一致（列宽、表头、`end` 行照抄模板）：Prec 为当天降水（cm，保留 3 位）；rSoil=0.15、rRoot=0.22、hCritA=100000 等其余列沿用模板值。只有调用方显式传入 `rsoil_cm_d`/`rroot_cm_d`，并同时提供 `*_source` 说明时才覆盖。是否覆盖写入 assumptions（解决 D6）。
- SELECTOR.IN：复制模板后，只在运行目录里把 MPL 改为 7、TPrint 改为 `1 2 3 4 5 6 7`（逐日输出），其他内容不动。模板文件本身不修改。
- `inputs` 字段必须反读运行目录里生成的 ATMOSPH.IN，得到 `daily_prec_cm[7]`，再加上 start_date、extra_irrigation_mm 和窗口内的灌溉记录。
- 执行：`subprocess.run(..., timeout=HYDRUS_TIMEOUT_S)`，超时返回 `status=timeout`；stdout/stderr 写入 `run_dir/engine_stdout.txt`；生成了 `Error.msg` 返回 `status=failed`，warnings 附上 Error.msg 原文；`os.name != "nt"` 且 HYDRUS_EXE 不是 `.sh` 包装脚本时，直接返回 `failed`，warnings 写 `engine_unavailable_non_windows`。
- 解析：
  - `Nod_Inf.out` 按 `Time:` 分块，得到第 0–7 天每个节点的 theta。输出 `soil_moisture_series`：每天一条，含 date（start_date+t）、d10、d20、d40、d60、d100。`soil_profile_current` 取第 7 天。去掉写死的 `2026-04-30`（D7）。
  - `T_Level.out` 按表头名定位 `sum(rRoot)`、`sum(vRoot)` 两列，不用硬编码列号。`root_uptake_ratio = sum(vRoot)/sum(rRoot)`。
  - 湿润锋 `infiltration_depth_cm`：第 7 天 theta 比第 0 天高出 0.01 以上的最深节点深度，替换原来写死的 0.18 阈值。
  - `water_status` 和逐层 `status` 继续沿用 0.24/0.20/0.16 分级，但 outputs 增加 `classification_basis: "工程默认阈值，未依据本地块田间持水量/凋萎点"`，并写入 warnings。
  - 删除 `hydrus_explain` 里的建议性文字（D8），改为中性事实，例如“第7天40cm含水率0.193，较初始+0.012；累计根系实际/潜在吸水比0.87”。
- 固定 assumptions（必须包含）：土壤水力参数为模板通用值、非地块实测（D9）；初始压力水头剖面为模板值；下边界自由排水；蒸发/蒸腾强度为模板固定值；模拟窗口 7 天；结果未经田间校准。
- `source_type="simulation_uncalibrated"`；`model_version="HYDRUS-1D H1D_CALC.EXE sha256:<前12位>"`；`parameter_version="hydrus-params-<SELECTOR.IN+PROFILE.DAT 的 sha256 前12位>"`；`units={"theta":"cm3/cm3","depth":"cm","prec":"cm/d"}`。
- fallback：只有 `ALLOW_DEMO_FALLBACK=1` 时才读 demo，返回 `status=fallback`、`source_type=demo`，并在 warnings 写“工程演示数据，不是模拟结果”；默认（0）返回失败结果，outputs 为空（D4）。
- 回放：`HYDRUS_MODE=replay` 时不调用引擎，从 `backend/data/hydrus_cases/` 找 `extra_irrigation_mm` 相同的案例，返回 `status=replay`、`mode=replay`，warnings 写“历史结果回放，生成于 <created_at>”；找不到时返回 `failed`。
- 每次运行把结果写入 `run_dir/hydrus_result.json`。
- 测试 `tests/test_hydrus_adapter.py`：
  - 无 start_date → missing_input；
  - 非 Windows 或 exe 路径不存在 → failed，且 outputs 为空；
  - ALLOW_DEMO_FALLBACK=1 → status=fallback；
  - 回归测试（仅 Windows，否则 skip）：start_date 任意，第 1 天降水 6.1cm、其余 0，第 7 天 40cm theta 与仓库 `zyh/runtime/hydrus_runs/gui_test_run` 的 0.1935 相差小于 0.002；
  - 反读得到的 daily_prec_cm[0] 等于输入值。
- 验收：pytest 全绿；Windows 上手动运行一次，status=success，series 有 8 个时间点。

T2.2 HYDRUS 案例包 → `backend/tools/generate_hydrus_cases.py`
- 生成 4 个案例到 `backend/data/hydrus_cases/`，同时复制到 `实验资料/04_三模型工具资料/HYDRUS/cases/`：
  - `case_baseline_0mm.json`：start_date=2026-09-01，不加灌溉，无实测降雨（假设输入）；
  - `case_irrig_20mm.json`：同上，加 extra_irrigation_mm=20（变化组）；
  - `case_missing_input.json`：不传 start_date；
  - `case_engine_failed.json`：HYDRUS_EXE 指向不存在的路径。
- 每个案例写入 `input_label: "假设输入"`，以及完整的统一结果。
- 另外生成 `case_compare_0_vs_20.json`：两组的输入差异（逐日 prec）、输出差异（各深度第 7 天 theta 差值、湿润锋深度差、吸水比差），并写明“同一参数版本、同一窗口”。
- 把历史失败样例 `zyh/runtime/hydrus_runs/test_001/Error.msg` 复制为 `cases/historic_nonconverge_Error.msg`，作为不收敛的真实记录。
- 验收：两组 success 案例的 parameter_version 相同；20mm 组第 1 天 prec 比基线多 2.0cm；compare 文件里 40cm theta 差值不为 0。

T2.3 HYDRUS 工具说明 → `docs/zyh/HYDRUS工具说明.md`（同时复制到 `实验资料/04_三模型工具资料/HYDRUS/`）
- 按方案 6.5 的 6 节写，内容只能来自代码和 T2.2 的案例，不能写代码做不到的能力：
  1. 名称、实现类型（机理模型，外部 exe 调用）、版本哈希、执行入口、依赖（Windows、exe 路径、环境变量）；
  2. 输入字段表：字段、类型、单位、是否必需、允许范围、来源、默认假设、是否实际生效。必须写明：rSoil/rRoot 是模板固定值，土壤参数是模板通用值；
  3. 输出字段表：单位、时间/空间尺度、计算方法、可支持哪些解释、不能支持哪些解释（例如不能给出产量或田间节水结论）；
  4. 状态表：6 种 status 的触发条件和前端展示方式；
  5. 案例包索引（T2.2）；
  6. 日志位置、参数版本、上游依赖（降雨来自哪里、灌溉来自哪里）、适用限制。
- 文末加“待张源皓确认”小节，列出 Codex 无法判断的内容（例如模板土壤参数的原始出处）。
- 验收：文档里每个字段都能在代码中找到出处。

T2.4 业务层风险修正（D1、D2、D3、D12）
- `services/weather_service.py`：新增 `get_observed_weather(plot_id, start, end)`，从 `obs_long` 表读降雨等记录（T2.6 建表后生效），读不到时返回空列表。原来的 demo 生成函数改名为 `get_demo_weather_series`，只有在演示开关 `ALLOW_DEMO_WEATHER=1` 打开时才使用，且每条记录保留 `source: demo`。
- `api/model_api.py`：
  - 删除 `_latest_plot` 中写死的示例地块。没有 plot_id 时：库里只有一个地块就用它，并在 warnings 写“未指定地块，使用唯一地块 X”；否则返回 400，`status=missing_input`、`missing_fields=["plot_id"]`。
  - 删除 `_farm_operations` 中自动补的灌溉/施肥记录。没有记录时返回空列表，并在 model_input 的 `missing_fields` 里记 `farm_operations`。
  - `build_model_input` 增加 `start_date`（请求传入或取当天），以及 `data_sources: {weather: observed|demo|none, farm_operations: db|none}`。
- `api/advice_api.py`、`api/result_api.py`：去掉“取全局最新结果”。必须带 task_id 或 plot_id；只带 plot_id 时取该地块最新的结果，并在返回里写 `result_selected_by: "plot_latest"` 和结果时间。
- 小程序沿用 `utils/storage.js` 的 `savePlotId()/getPlotId()`；`utils/request.js` 在请求体或查询参数没有 plot_id 时自动带上当前 plot_id。
- 测试：没有地块时 `/api/model/run` 返回 400；没有农事记录时不会出现 25mm 灌溉；有两个地块时 `/api/dashboard` 不带 plot_id 返回 400。
- 验收：pytest 全绿；`docs/zyh/baseline_snapshot_before.json` 和新结果对比后，差异写进 PROGRESS。

T2.5 状态驱动的结果融合（D10、D14）
- 新建 `services/tool_registry.py` 中的 `wrap_legacy_result(tool, raw, ctx)`，把 apsim/beps adapter 的原始返回包装成统一结果，不改它们的源码：
  - APSIM：raw.status=success → `success`，source_type=`proxy_model`，assumptions 写“OilPalm 代理映射咖啡指标，无咖啡产量验证”；raw.status=fallback → `fallback`，source_type=`demo`。
  - BEPS：raw.status=ok → `success`，source_type=`simplified_model`；raw.status=fallback → `fallback`，source_type=`demo`。
  - 不认识的状态 → `failed`，并在 warnings 里记录原始值。
- `models/fusion_engine.py::merge`：
  - 只有 status ∈ {success, replay} 的工具才进入 `available_evidence`；`model_basis` 只为这些工具生成，没有的就不写，不再凑够三个模型。
  - 顶层 `status`：全部可用为 `success`，部分可用为 `partial`，全部不可用为 `failed`。
  - 新增 `tool_status: {apsim:{status,source_type}, hydrus:{...}, beps:{...}}`，供前端徽章使用。
  - dashboard 中来自不可用工具的数值改为 null。
  - 风险融合逻辑保持不变，但输入只用可用工具的结果。
- 如果 BEPS 读取了 APSIM 的 LAI 或 HYDRUS 的水分因子，在 `mechanism_explanation` 中加 `dependency_note`，说明三者不是相互独立的证据（方案 3.2）。
- `/api/model/validation_cases`：每条结果加 `verification_status: "unverified"`、`note: "预填结论，无原始专家记录"`。原 JSON 文件不改。
- 测试：hydrus 返回 failed 时，`model_basis` 里没有 hydrus，顶层 status=partial。
- 验收：pytest 全绿。

T2.6 真实数据工具首版（10/16 首版，10/18 冻结）
- 第一步，画像：`data_pipeline/profile_raw.py` 读 `raw/` 下全部文件，所有列都按 `dtype=str` 读取，编码用 charset-normalizer 判断。输出 `实验资料/03_地块与监测数据/字段画像.md`，每个文件写：列名、非空率、示例值、疑似类型（时间/设备ID/数值/单位）。设备 ID 列如果出现 `E+` 科学计数法或末尾补零，标记 `precision_loss_suspect`。
- 第二步，映射：生成 `data_pipeline/column_mapping.yaml` 草稿，每个文件包括 `file_glob`、`time_col`、`time_format`、`device_col`、`value_cols: [{col, parameter, depth_cm, unit}]`、`rain_mode: increment|cumulative|unknown`、`priority`。不确定的项填 `TODO_HUMAN`，并写进待人工确认。还要生成 `device_plot_map.csv` 模板（列：device_id、plot_id、depth_cm、valid_from、valid_to、备注）。
- 第三步，入库：`data_pipeline/ingest_monitoring.py`，只有 YAML 里没有 TODO_HUMAN 时才运行，否则退出并列出待填项。写入 SQLite（与业务库同一个 DB），建以下表：
  - `raw_files(file_id, path, sha256, rows, imported_at, data_version)`
  - `obs_long(obs_id, plot_id, device_id, ts, date, parameter, depth_cm, value_raw, value, unit, source_file_id, source_row, qc_flag, data_version)`
  - `device_plot_map(device_id, plot_id, depth_cm, valid_from, valid_to)`
  - `lai_obs(plot_id, date, quadrat, plant, repeat_no, lai, method, source_file_id, source_row)`（`ingest_lai.py` 读 IN-G10 TXT，保留测次、植株、样方层级；单日 LAI 不插值成序列）
  - `farm_events(plot_id, date, op_type, amount, unit, source, source_ref, verified)`（`ingest_events.py`，来源是蔡整理的事件表）
  - `soil_reports(plot_id, sample_date, depth_top_cm, depth_bottom_cm, item, value, unit, method, report_ref, status)`（`ingest_soil_reports.py`；报告没返回时 status=pending）
  - `data_versions(data_version, created_at, file_hashes_json, row_counts_json, note)`
- 质量规则（每一条都写进清洗日志）：
  - 去重键为 (device_id, ts, parameter, depth_cm)，冲突时保留 priority 高的文件，被丢弃的行数写进日志；
  - 含水量单位为 % 时除以 100，统一为 cm3/cm3，value_raw 保留原值；
  - rain_mode=cumulative 时按相邻差分换算成增量，出现负差分视为计数器复位，标 `qc_flag=rain_reset`；
  - 范围检查：含水量不在 0–0.6、温度不在 -5–50 ℃、降雨不在 0–300 mm/日 之间时，标 `qc_flag=out_of_range`，数值保留，统计时默认排除；
  - 缺测保持 null，不插值；
  - 时间统一转为 Asia/Shanghai；
  - 文件名或内容显示是茶、水稻的数据时整文件跳过并记录（作物隔离）；
  - 早期监测和 9 月观测用不同的 data_version 标签区分。
- 输出 `docs/zyh/数据字典.md`（由脚本根据表结构和 YAML 自动生成）和 `docs/zyh/清洗日志.md`（每次运行追加：时间、data_version、各文件读入/去重/异常行数）。
- `api/data_api.py`：
  - `GET /api/data/catalog?plot_id=` 返回该地块可查的 parameter、depth、日期范围、设备列表；
  - `POST /api/data/query`，请求体 `{plot_id, parameter, depth_cm?, start, end, agg: raw|daily_mean, include_flagged:false}`，返回统一结果：outputs 含 n、mean、min、max、first、last、缺测天数、series；source_type=`observation`；inputs 写入实际执行的筛选条件；warnings 写入排除的异常条数；
  - `GET /api/data/source/<obs_id>` 回查原文件路径、行号、原始值（来源回查）。
- 测试：在 fixtures 里放构造数据，覆盖重叠导出、% 单位、累计降雨、复位、设备 ID 精度这几种情况；断言 query 的 mean 和手算结果一致，误差小于 1e-9。
- 冻结：10/18 运行 `python data_pipeline/freeze.py --version data-v1.0`，写 `data_versions`，并打 git tag `data-v1.0`。冻结后再改数据必须升版本号。
- 验收：fixtures 测试全绿；真实数据入库后，`/api/data/catalog` 返回非空（这一步依赖人工任务 H3、H4）。

T2.7 本地服务客户端和 mock（D11）
- `services/evidence_client.py`：
  - 提供 `route(payload)`、`answer(payload)`、`health()` 三个函数，按 4.3 节契约实现；超时和非 2xx 统一抛 `EvidenceServiceError(code, msg)`；
  - 校验响应：route 的 `tool_calls[].name` 必须是字符串，arguments 必须是 dict；格式不对按服务错误处理。
- `tools/mock_evidence_service.py`：独立 Flask 应用，端口 8001，规则是确定的（不调用任何大模型）：
  - 消息含“墒情/含水/湿度”+深度 → intent=data_query，调 `query_soil_moisture`；消息里没有日期 → 返回 `missing_fields=["start","end"]` 和 `clarify_question`；
  - 消息含“如果/多浇/灌溉…mm” → intent=scenario，调 `run_hydrus_scenario`，参数取消息里的数字；
  - 消息含“解释/为什么”且带 task_id → intent=model_explain，调 `read_model_result`；
  - 其他情况 → intent=knowledge，从 `tools/mock_corpus.json`（3 条明显标注“MOCK 语料”的示例）里返回 citations；
  - answer 用模板拼接工具结果里的数值，claims 绑定对应的 evidence_id；
  - 所有响应都带 `"mock": true`。
- 新建 `docs/zyh/本地服务接口契约.md`：把 4.3 节整理成文档，附 mock 的请求/响应样例，文末写“待蔡济远确认：字段名、超时、部署地址、是否 OpenAI 兼容”。（人工任务 H5：张源皓发给蔡。）
- `services/llm_service.py`：`generate_advice` 和 `chat_with_context` 改为调用 assistant 流程（T2.8）；原 GLM 调用代码保留，放在 `LEGACY_GLM=1` 开关后面，默认关闭；删除提示词里“必须分别引用 APSIM、HYDRUS、BEPS”的要求；`_rule_fallback` 输出的 source 改为 `rule_fallback_not_evidence`，前端显示为“规则示例，非循证建议”。
- 验收：启动 mock 后，`python -c "from services.evidence_client import health; print(health())"` 能返回结果；断开 mock 时抛出 EvidenceServiceError。

T2.8 助手主入口 `/api/assistant/chat`（D13）
- `services/plot_context.py`：`load_plot_context(plot_id)` 返回 `{plot_id, known:{品种, 树龄, 土质, 遮阴, 株行距...}, unknown:[...]}`。没有的字段放进 unknown，不填默认值。
- `services/tool_registry.py`：
  - 按 4.4 节注册 5 个工具，每个都有 JSON Schema（jsonschema 校验）；
  - `execute(tool_calls, ctx)` 逐个执行。执行前先用 plot_context 补参数，仍缺参数时返回 `missing_input`；
  - 单轮最多执行 3 个工具，一轮里最多 1 次 `run_hydrus_scenario`。
- `services/trace_store.py`：建表 `assistant_traces(trace_id, session_id, turn_id, plot_id, message, route_json, tool_calls_json, tool_results_json, answer_json, blocks_json, latency_ms_json, errors_json, service_mode, created_at)`；`service_mode` ∈ {live, mock, degraded}。导出脚本 `tools/export_traces.py --out 实验资料/07_实验结果/traces_<日期>.jsonl`。
- `api/assistant_api.py`，`POST /api/assistant/chat`：
  - 请求 `{session_id, plot_id, message, history, supplement?}`，执行 4.1 节第 1–7 步；
  - 会话状态 `clarify_count` 存在内存 dict 里，按 session_id 区分；`clarify_count>=1` 后仍缺参数，就返回 `check_items` 块，不再追问；
  - 组装 blocks：数值型 outputs 生成 `fact` 块；有 series 时生成 `chart` 块；每个工具结果和每条 citation 生成 `evidence` 项；status≠success/replay 时生成 `warning` 块；answer 里 claims 引用的 evidence_id 不存在时，这条主张加前缀“[未核验]”，并在 errors 中记 `unsupported_claim`；
  - 服务不可用时进入降级模式：如果 route 失败，但消息能被 mock 规则识别为数据查询，就直接执行查询，只返回 fact/chart/evidence 块，再加一个 warning 块“智能解释暂不可用”；其他情况返回 warning 块。降级时一律不调用外部 GLM；
  - 时间预算：route 20 秒、工具 60 秒、answer 60 秒，总计不超过 120 秒。
- 新增 `GET /api/assistant/health`，返回 evidence 服务状态、HYDRUS 模式、数据版本、是否为 mock。
- 每轮 blocks 末尾追加 4.7.5 的 `trace` 块（7 步闭环）。
- 新增 `GET /api/evidence/<evidence_id>`（P9 用）：依次在 assistant_traces、scenario_compares、model_results 中查找，返回统一工具结果或 citation；找不到返回 404 和 `E_EVIDENCE_NOT_FOUND`。
- 测试 `tests/test_assistant.py`（用 monkeypatch 替换 evidence_client）：覆盖 4 种路径，分别是 data_query 成功、缺日期追问一次后转核查事项、hydrus failed 时出现 warning 块、未核验主张被标记。
- 验收：pytest 全绿；mock 启动时，用 curl 发三条典型消息都能拿到 blocks。

### Phase 3 · 前端展示、报告和三场景联调（10/17–18）

本阶段的执行顺序（不按编号）：T3.0 → T3.7 → T3.1 → T3.8 → T3.2 → T3.3 → T3.4 → T3.5 → T3.6。前端任务都以 4.7 节为准；4.7 和本节写法有出入时，以 4.7 为准。

T3.0 前端基础件（先做，后面页面都依赖它）
- 新建 `utils/session.js`、`utils/labels.js`（source_type、status 到中文文案和 class 的映射，唯一来源，组件和页面都从这里取）、`utils/errors.js`（错误码到文案和 retryable 的映射，与 T4.4 文档一致）。
- `utils/request.js`：保留原有 Promise 封装；增加以下能力：
  - 自动带 plot_id：只针对 GET 的 query 和 POST 的 body，并且只有 url 不是 `/api/plot/*` 时才加；
  - 非 2xx 响应统一转成 `{code, message, retryable}` 对象，再 reject；
  - 网络失败时 reject `{code:'E_OFFLINE'}`。
- `app.wxss`：加入 4.7.4 的颜色变量、`.tag-*`、`.banner-*` 类；旧公共类保持不变。
- 新建 4.7.5 中标为“新建”的组件，改造 `status-card` 和 `loading-panel`。
- `line-chart`：在一个临时调试页 `pages/_dev/_dev`（只在开发时注册，交付前从 app.json 移除）里放 3 组样例数据，验证以下情况：空数据、单点、两条线、y 轴范围自动计算、数据表切换。
- 验收：调试页截图（H8）；`grep -rn "ec-canvas" miniprogram/pages` 没有结果；所有新组件的 `.json` 都声明了 `"component": true`。

T3.1 问答页（4.7.6 P2）
- 按 P2 的线框和交互规则改造 `pages/advice`，用 `msg-blocks` 渲染。会话、追问、历史、pendingQuestion、失败重试都按 P2 的规则实现。
- 删除页面里的 emoji 头像，换成文字头像“你”和“助手”。旧样式的气泡配色保留。
- 请求 timeout 设为 120000 毫秒。
- 验收：mock 服务下，3 条示例问题分别渲染出 fact+chart、citations、missing→补充→fact 三种结果；后端停掉时显示离线文案和重试按钮。截图（H8）。

T3.2 模型结果页（4.7.6 P7）
- 按 P7 改造 `pages/result`。删除 `_loadValidationCases` 里内置的静态案例数组，删除 `MODEL_INFO_LIST` 中没有依据的表述，改为如实文案。
- 删除 T2.1 为兼容旧前端加在顶层的字段，前端改为从 `hydrus.outputs.*` 读取。
- 验收：把 HYDRUS_EXE 指向错误路径后运行，result 页显示 HYDRUS 不可用，另外两个模型照常显示且带各自的标签；页面上搜不到“专家复核”“通过”字样。

T3.3 报告（后端 + 4.7.6 P8）
- `services/report_builder.py`：输入一个 trace_id（或 compare_id），按方案 3.1 第 6 步的固定顺序生成报告：事实 → 依据 → 情景差异 → 建议/核查 → 缺项与限制。每一段都带 evidence_id 列表；没有 evidence 的段落写“无可用证据”。
- `api/report_api.py`：
  - `POST /api/report/create {trace_id|compare_id}` → `{report_id}`，存入 `reports(report_id, plot_id, source_id, report_json, created_at)` 表；
  - `GET /api/report/<id>` 返回 JSON；
  - `GET /api/report/<id>.html` 返回可以打印成 PDF 的 HTML（内联 CSS，不引用外部资源，配色和小程序一致）；
  - `GET /api/report/list?plot_id=` 返回列表。
- 小程序：新建 `pages/report/` 和报告列表（放在 report 页里，当没有 `report_id` 参数时显示列表），按 P8 渲染。
- 验收：从一次数据查询的 trace 能生成报告；HTML 在浏览器里打印预览正常；小程序报告页每节都有证据标签。

T3.4 三场景联调用例 → `tests/test_e2e_scenarios.py` 和 `docs/zyh/联调记录.md`
- 场景 K（知识）：“咖啡根系主要分布在多深？”，期望 intent=knowledge，至少 1 条 citation，回答里没有工具数值。
- 场景 D（数据）：“<真实地块> 40cm 最近 7 天平均含水率”，期望调用 query_soil_moisture，fact 块里的数值和直接用 SQL 算的一致。
- 场景 M（缺条件）：“帮我看看墒情”，期望出现 missing 块；补充“最近7天”后出现 fact 块；如果故意第二次仍不补，期望出现 check_items 块。
- 场景 F（失败）：HYDRUS 不可用时问“多浇20mm会怎样”，期望出现 warning 块，没有具体的灌溉建议数字。
- e2e 测试用 mock 服务跑；接入蔡的真实服务后再人工跑一遍，结果记在联调记录里（时间、服务模式、通过/失败、trace_id）。
- 验收：mock 模式下 4 个场景全过。这对应方案的里程碑“知识、数据、缺条件场景真实闭环”。

T3.5 给正式题集准备的可核验案例（交给简光耀）
- `tools/export_verifiable_cases.py`：从冻结后的 data-v1.0 中，选出 20 个数据查询案例（覆盖不同地块、深度、时间段、带缺测的时段），以及 HYDRUS 的 2 个 success 案例和 2 个失败案例。
- 每个案例输出：查询条件、执行的 SQL 或调用参数、结果数值、evidence_id、data_version。只给事实，不写参考回答，也不写入 06 目录。
- 输出到 `实验资料/04_三模型工具资料/可核验案例_zyh.json`，由张源皓转交简光耀（H9）。
- 验收：每个案例重新执行后结果一致。

T3.6 10/18 HYDRUS 实时调用核验决定
- 在 Windows 上连续跑 T2.2 案例 5 次，记录成功率和耗时，写进 `docs/zyh/HYDRUS工具说明.md` 第 6 节。
- 5 次全部 success 且单次耗时不超过 30 秒：保持 `HYDRUS_MODE=live`；否则改成 `HYDRUS_MODE=replay`，并在 PROGRESS 中写明“按方案 10/18 规则改为历史结果解释模式”。
- 验收：PROGRESS 中有明确结论。

T3.7 工作台、地块、农事、农情页和 tabBar（4.7.3、4.7.6 P1/P3/P5/P6）
- 后端：
  - `plot_api.py` 新增 `GET /api/plot/list` 和 `GET /api/plot/<plot_id>`；
  - `_default_plot` 改为“缺字段存 null”，删除所有示例默认值；名称为空时返回 400；
  - 新增函数 `profile_completeness(plot)`，按 12 个字段（名称、品种、树龄、面积、纬度、经度、海拔、土质、遮阴、密度、行距、株距）计算完整度，list 和 detail 都返回 `completeness: {filled, total, missing:[...]}`；
  - `farmop_api.py` 删除回落到 `plot_001` 的逻辑（M4），没有 plot_id 时返回 400；amount 缺失或不大于 0 时（irrigation/fertilization）返回 400 `E_PARAM_INVALID`。
- 前端：
  - 按 4.7.3 修改 app.json（页面列表和 tabBar）；
  - index、advice、scenario 改为 tab 页，原来的 `navigateTo` 都改为 `switchTab`；
  - 新建 `pages/plots`、`pages/data`；按 P1、P5、P6 改造 index、plotInit、farmLog。
- 验收：测试覆盖 plot list、completeness、farmop 400 三种情况；开发者工具里走通：新建地块 → 设为当前 → 录入农事 → 农情查询（fixtures 数据）→ 回到工作台看到最近墒情。截图（H8）。

T3.8 证据详情页（4.7.6 P9）
- 新建 `pages/evidence`，接 `GET /api/evidence/<id>`。从 fact 卡片、evidence 列表、农情页来源链接都能进入这个页面。
- 验收：从问答页任意一个 fact 卡片点进去，都能看到 inputs、assumptions；observation 类能回查到原文件和行号。

### Phase 4 · 情景页、失败处理、演示流程（10/19–22）

T4.1 A/B 情景接口 `POST /api/scenario/compare`
- 请求：`{plot_id, start_date, change: {extra_irrigation_mm: 20}, confirm: true}`。只允许单一变化，`change` 里只能有一个键；当前只支持 `extra_irrigation_mm`（0–100）。遮阴参数属于 BEPS，接口预留 `tool` 字段，本期返回 `missing_input: "当前仅支持灌溉情景"`。
- `confirm` 不为 true 时不运行，返回确认卡片数据：基线是什么、变化是什么、哪些是假设（全部来自 assumptions），等前端确认。
- 运行：基线和变化组用同一个 start_date、同一参数版本，各调用一次 `run_hydrus_scenario`；replay 模式下读案例。
- 参数核验：对比两组 `inputs.daily_prec_cm`，第 1 天的差值必须等于 change/10（误差小于 0.001），否则 `status=failed` 并写入 warnings“参数未进入模型”。这对应方案“参数是否实际进入模型通过调用轨迹核验”。
- 返回：`{compare_id, baseline, variant, input_diff, output_diff:{theta_day7_by_depth, infiltration_depth_cm, root_uptake_ratio}, assumptions, undetermined:[未确定条件], mode, status}`。写入 `scenario_compares` 表和轨迹。
- 测试：用 monkeypatch 替换 hydrus，验证差值核验通过和失败两种情况；同时验证 change 有两个键时被拒绝。
- 验收：pytest 全绿；Windows live 模式下返回的 0 vs 20mm 对比和 T2.2 的 compare 文件一致。

T4.2 情景页改造 `pages/scenario`（4.7.6 P4）
- 按 P4 的三步向导实现，用 `line-chart` 画双折线，差值表用原生 view 表格。基线信息来自 compare(confirm=false) 的返回，不在前端拼装。
- 原来的 4 个预设情景卡片：“明天补充滴灌”改成快捷项 +20mm；“暂不浇水”对应基线本身，删除；“本期少量追肥”和遮阴类显示灰色“本期不支持”。页面上不再出现“比较补水后产量”这类 HYDRUS 做不到的描述。
- replay 模式下标题旁固定显示“历史结果回放”标签，并显示 banner。
- 验收：开发者工具里完整走通 3 步；HYDRUS 不可用时第 3 步只显示失败原因和回放按钮。截图（H8）。

T4.3 10/21 情景功能核验
- 21 日前如果 live 模式下 T4.1 没有通过参数核验，就把情景功能锁定为 replay，并在页面、报告、演示脚本中都标明“回放”（方案第八节）。结论写进 PROGRESS。

T4.4 失败处理和恢复 → `docs/zyh/错误码与降级.md`
- 统一错误响应：`{status:"error", code, message, retryable, trace_id}`。错误码：`E_PLOT_REQUIRED`、`E_PARAM_INVALID`、`E_TOOL_NOT_ALLOWED`、`E_HYDRUS_TIMEOUT`、`E_HYDRUS_FAILED`、`E_HYDRUS_UNAVAILABLE`、`E_EVIDENCE_TIMEOUT`、`E_EVIDENCE_DOWN`、`E_EVIDENCE_NOT_FOUND`、`E_DATA_EMPTY`、`E_INTERNAL`；前端本地的 `E_OFFLINE`。`utils/errors.js` 与本表保持一致。`app.py` 的全局异常处理改为返回 `E_INTERNAL`，不把堆栈暴露给前端（堆栈写进 `server/logs/backend.log`）。
- 前端 `utils/request.js`：
  - 识别 `retryable=true`，在页面上显示“重试”按钮；
  - 网络失败时显示“后端未连接，请检查电脑与手机在同一网络、BASE_URL 是否正确”；
  - 超时时显示“计算超时，已保留输入，可重试或改用历史结果”。
- 情景页超时后提供“改用历史结果回放”按钮（调用 compare 时传 `mode: replay`）。
- 文档里列一张表：错误码 | 触发条件 | 前端提示 | 恢复动作。
- 测试：每个错误码至少有一个测试能触发。
- 验收：pytest 全绿。

T4.5 演示流程 → `docs/zyh/演示流程.md`（更新旧的 `演示流程脚本.md`，旧文件保留）
- 3–5 分钟 6 步，每步写明：操作、输入原文、预期画面、对应的证据标签、失败时的备用操作：
  1. 选择真实地块，展示地块档案和缺项；
  2. 知识问答（K），展开出处；
  3. 数据问答（D），展示图表和来源回查；
  4. 缺条件追问（M），补充后得到结果；
  5. A/B 灌溉情景（确认 → 对比 → 假设说明）；
  6. 生成报告。
- 每步都要说清楚画面上是实测、文献、模拟还是回放，不说“增产/节水”这类没有实验依据的话。
- 新建 `backend/tools/seed_demo.py`：只导入真实地块档案和冻结数据，不生成虚构数据；缺数据时报错并列出缺什么。
- 验收：按脚本完整走一遍不出错，用时记进 PROGRESS。

### Phase 5 · 功能核对与交付目录（10/22–24）

T5.1 自检脚本 `backend/tools/selfcheck.py`
- 依次检查：Python 版本和依赖版本；`.env` 关键项；数据库表是否齐全；data_version 是否为冻结版本；HYDRUS 模式和引擎是否存在；evidence 服务 health；6 个核心接口各发一次真实请求（ping、catalog、query、assistant/chat、scenario/compare(replay)、report）。
- 输出 PASS/FAIL 表格，并把结果写到 `server/logs/selfcheck_<时间>.txt`。有任何一项 FAIL，返回码非 0。
- 验收：在完整环境下全部 PASS。

T5.2 功能核对表 → `docs/zyh/功能核对表.md`
- 逐条对照方案“研究任务 1–5”和第十节完成标志，列为：功能 | 接口 | 页面 | 测试用例 | 自检项 | 证据（截图/trace_id）| 状态。
- 一致性扫描：在小程序 wxml/js 和 docs 里搜索“增产”“节水”“精准”“专家通过”“已验证”“success”等字样。每一处都要核对是否有实验依据，没有的就改成如实的表述，并列出修改清单。
- 验收：核对表里没有“未核对”的条目。

T5.3 交付目录 → `docs/zyh/交付目录.md`
- 列出代码、配置、数据版本、案例包、文档、截图、录屏，写清它们在仓库或网盘中的位置，以及每项对应方案第十节的哪一条成果。
- 列出第三方组件：Flask 等 Python 包、HYDRUS-1D 引擎（前端图表为自研 Canvas 组件，不含 ECharts；`ec-canvas/` 空占位目录在 T3.0 删除并从 app 中移除引用）。HYDRUS 的再分发许可写“待确认（H10）”，确认前代码包里不带 exe，只给获取说明。
- 验收：目录里每个路径都存在（写一个小脚本检查）。

T5.4 新旧贡献记录 → `docs/zyh/新旧贡献记录.md`（方案第十一节，交简光耀汇总）
- 用 `git log --format="%h %an %ad %s" --date=short` 和 `git diff --stat <改造前基线提交>..HEAD -- coffee_digital_twin` 生成两张表。改造前基线提交取 `221a26b`，即本计划开始前 main 的最新提交；先在 T0.1 中确认。
  - 表一·旧工程：文件 | 原作者/来源（看 git 历史和文件头注释） | 原功能。
  - 表二·本届改动：文件 | 改动类型（新增/改造/仅适配） | 对应任务号 | 简述。
- 标为“仅适配”的：hydrus_adapter 外层、apsim/beps 的结果包装。标为“新增”的：assistant、data、scenario、report、evidence 接口，以及新页面、新组件。
- 不改写任何旧文件头的署名，也不删除 `AI辅助生成` 注释。
- 验收：表二覆盖 `git diff --name-only` 的全部文件。

### Phase 6 · 启动包、录屏环境、交付修复（10/25–27）

T6.1 启动包
- 新建 `server/setup_windows.ps1`：检查 Python，创建 `.venv` 并安装 requirements；`.env` 不存在时从 `.env.example` 复制，并提示需要填写的项；初始化数据库；导入冻结数据；运行 selfcheck。
- 新建 `server/start_demo.ps1`：启动后端（`FLASK_DEBUG=0`），如果 `EVIDENCE_SERVICE_URL` 指向本机 8001 且该端口没有服务，就询问是否启动 mock，选“是”时启动 mock 并在控制台醒目提示 MOCK；打印本机局域网 IP，提示把它填进小程序 `utils/config.js` 的 `BASE_URL`。
- `utils/config.js` 支持两套地址：开发者工具里用 127.0.0.1，真机用局域网 IP，注释写清楚怎么切换。默认值为 127.0.0.1。注释里写明：不要使用 cpolar 或 ngrok 这类公网隧道（M1）；后端没有鉴权，暴露到公网后任何人都能调用。
- 全仓库搜索 `D:/`、`D:\\`、`C:\\Users`、`anaconda`，只要不是文档里的示例，就改为相对路径或环境变量。
- 验收：在一个新目录里 clone 仓库，只运行 `setup_windows.ps1` 和 `start_demo.ps1` 就能通过 selfcheck（数据文件按交付目录说明放好之后）。

T6.2 操作手册 → `docs/zyh/操作手册.md`
- 内容依次为：环境要求、安装、配置 `.env`、导入数据、启动、小程序导入和真机预览、演示流程链接、常见问题（按错误码表）、安全说明（服务没有鉴权，只能在可信局域网使用，演示后关闭）。
- 验收：张源皓按手册在另一台 Windows 电脑上走通（H11）。

T6.3 录屏环境
- 新建 `tools/reset_demo.ps1`：备份当前数据库；恢复到冻结版数据库快照；清空 `runtime/` 和本轮轨迹（先导出到 07_实验结果）；设置 `FLASK_DEBUG=0`；关闭控制台里的 emoji 输出。
- 验收：运行后 selfcheck 全部 PASS，演示流程能从第 1 步开始。

T6.4 交付检查和修复
- 运行 `pytest`、`selfcheck`、功能核对表，再按演示流程完整跑三遍。每个问题都开一行写进 `docs/zyh/交付问题清单.md`（问题 | 严重度 | 修复提交 | 复测结果），并逐条修复。
- 验收：清单里没有未关闭的“高”严重度问题；三人都能按手册演示（H12）。

### Phase 7 · 运行终审和提交（10/28–30）

T7.1 干净环境复测：重新 clone 一份，按操作手册从零跑一遍，过程记进 PROGRESS。
T7.2 链接和文件检查：新建 `tools/check_links.py`，读取 `docs/zyh/交付目录.md` 中的 URL 和路径，逐个检查（URL 只发 HEAD 请求），输出不可访问的条目。
T7.3 代码冻结：打 tag `submit-v1`。之后只修阻断性问题，每次修复都单独提交并在 PROGRESS 中说明原因。10/30 20:00 前不再加功能。
T7.4 答辩准备：在 `docs/答辩问题准备.md` 末尾追加“业务与 HYDRUS”小节，覆盖这些问题：为什么 HYDRUS 是未校准情景；参数怎么核验确实进入了模型；fallback 怎么区分；真实数据怎么去重和回查；没有鉴权的安全边界。答案只能引用本仓库里的实际实现。

## 6. 人工任务（张源皓本人，Codex 不能代做）

| 编号 | 任务 | 截止 | 阻塞 |
|---|---|---|---|
| H1 | 下载 A3 土壤首批 4–5 份原文，登记台账 | 10/14 | T1.4 |
| H2 | 补齐 10 份土壤原文，填土壤字段映射表（区分实测/文献/推算） | 10/16 | T2.3 |
| H3 | 把六份主要 CSV、补充导出、IN-G10 TXT、土壤报告放进 `raw/` | 10/15 | T2.6 |
| H4 | 确认 `column_mapping.yaml` 中的 TODO_HUMAN 项和 `device_plot_map.csv`（设备对应哪个地块、哪个深度） | 10/16 | T2.6 |
| H5 | 把《本地服务接口契约》发给蔡济远，拿到确认后的地址和字段 | 10/16 | T3.4 真实服务联调 |
| H6 | 写开发集 10 道土壤题（Codex 只给模板） | 10/16 | 蔡的开发集 |
| H7 | 交叉核查蔡济远的资料样例 | 10/16 | — |
| H8 | 在微信开发者工具中验收页面并截图 | 每个 Phase 结束 | — |
| H9 | 把可核验案例交给简光耀 | 10/18 | 正式题集 |
| H10 | 确认 HYDRUS-1D 引擎能否随代码一起提交（许可） | 10/24 | T5.3 |
| H11 | 在另一台 Windows 电脑上按手册安装 | 10/26 | T6.2 |
| H12 | 组织三人按手册演示、录屏 | 10/27 | — |

## 7. 降级开关（进度落后时按这个顺序收缩，不拖主线）

1. HYDRUS 实时调用 10/18 前没核验通过：`HYDRUS_MODE=replay`。
2. 情景对比 10/21 前没通过参数核验：情景功能锁定为回放并标明。
3. 蔡的服务没就绪：演示和联调用 mock，页面有 MOCK 横幅；正式评测不能用 mock 的结果。
4. 真实数据映射没确认：数据问答只开放已确认的设备和参数，catalog 里不出现其他的。
4a. 大模型服务完全不可用时：演示改用“农情”tab（P3）直接查真实数据，再加情景 tab 的回放，问答 tab 显示降级横幅。
5. 报告 HTML 来不及：只保留小程序报告页。

优先保障的顺序（方案第十一节）：本地问答接入 → 真实数据查询 → 结果解释 → 证据追溯 → 情景比较 → 报告美化。

## 8. 每日节奏

每天开始时，Codex 先读 PROGRESS.md 和待人工确认.md，列出当天要做的任务号，有阻塞的先跳过。每天结束时，在 PROGRESS 中写一行“当日小结”，供张源皓在 10–15 分钟的站会上同步。

