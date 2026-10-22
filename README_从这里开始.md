# 咖啡农事循证决策助手 · 张源皓工程

## 当前协作入口（2026-10-22）

- 当前协作仓库为 https://github.com/zyh100011/coffee ，以 `zyh/competition` 默认分支展示源码快照；引擎EXE不在新仓库发布。旧仓库中的逐任务历史保留，详见协作说明。
- 查看本届工程时请选择 `zyh/competition` 分支，实际代码在 `coffee_digital_twin/`。下文按日期保留的早期阶段说明不是最新状态。
- Phase 0–5 工程已实现；最新验收为 86 项 pytest 通过。真实监测数据已在张源皓本机入库；正式冻结、蔡的真实循证服务联调、界面人工验收及 Phase 6 尚未完成。
- 队友从 [GitHub协作说明](coffee_digital_twin/docs/zyh/GitHub协作说明.md) 开始，可定位接口契约、模型说明、进度和启动方法。GitHub 上传是否完成以远程分支实际内容为准。
- 原始监测数据、文献 PDF、本地数据库、`.env` 和 Python 虚拟环境不随代码共享；克隆代码不会自动带上本机已导入的数据。

以下为历史阶段记录；本节与最新 `PROGRESS.md` 优先。

这是根据最新版 Claude 计划 v2 建立的独立参赛改造工程。

- 原工程：`E:\coffe model\VX_3Models`，保持原状。
- 本工程：`E:\coffe model\coffee_competition_zyh`。
- Git 分支：`zyh/competition`。只做本地提交，未推送。
- 实施依据：`coffee_digital_twin/docs/zyh/CODEX_PLAN.md` 和根目录 `AGENTS.md`。

## 已完成：Phase 0（T0.1–T0.4）

已建立 Python 3.11.9 虚拟环境、固定依赖、可移植启动脚本、隔离测试、旧接口实际运行基线和 HYDRUS 输出核验。

验收：13 项 pytest 测试通过；真实 HTTP `/api/ping` 返回 `status=ok`。HYDRUS 运行状态为 success，生成 `T_Level.out`、`Nod_Inf.out`，没有 `Error.msg`，输出模拟时间为第 0 和第 7 天。

APSIM 引擎尚未提供，旧接口会返回 fallback 演示数据；BEPS 是简化计算。旧工程的 demo 默认值和建议文字将在后续任务中修正，本阶段结果不能用作田间科学验证。

小程序目前是继承的旧版本。新版工作台、循证问答、农情查询、情景、报告及证据详情按计划后续逐 Phase 实现；尚未接入蔡的真实服务。

## 启动后端

在 PowerShell 中运行：

```powershell
Set-Location -LiteralPath 'E:\coffe model\coffee_competition_zyh\coffee_digital_twin'
.\server\start_backend.ps1
```

脚本调用本工程 `.venv`，默认监听 `127.0.0.1:5000`。已有端口被占用时可以使用 `-Port 5001`。

另开 PowerShell 核验：

```powershell
Invoke-RestMethod http://127.0.0.1:5000/api/ping
```

结束时在启动窗口按 Ctrl+C。本次自动验收启动的服务已经关闭。

## 测试与记录

```powershell
Set-Location -LiteralPath 'E:\coffe model\coffee_competition_zyh\coffee_digital_twin\backend'
..\.venv\Scripts\python.exe -m pytest -q
```

- 进度：`coffee_digital_twin/docs/zyh/PROGRESS.md`。
- 后续人工依赖及事实差异：`coffee_digital_twin/docs/zyh/待人工确认.md`。
- 实际旧接口基线：`coffee_digital_twin/docs/zyh/baseline_snapshot_before.json`。
- HYDRUS 运行目录、文件清单、哈希和核验结果：`coffee_digital_twin/docs/zyh/hydrus_phase0_verification.json`。

已有数据库和小程序配置已复制保留；测试和基线使用隔离存储，不污染已有数据库。微信 AppID 和 BASE_URL 的旧本地改动未混入任务提交。不要把旧公网 BASE_URL 当成本阶段的服务地址。

## 已完成：Phase 1（T1.1–T1.5）

旧页面/API 复用清单、资料目录、空值土壤参数表、原始数据盘点、来源台账检查和 10 道待填开发题模板已建立。全部测试 24 项通过；仅用明确的构造数据验收脚本，真实资料尚未提供，不算已入库或已验证。

数据之后放进这里，保留原文件名即可：

```text
E:\coffe model\coffee_competition_zyh\实验资料\03_地块与监测数据\raw
```

土壤/根区原文放 `实验资料/01_原始知识资料/A3_土壤根区`，登记同级上一级 `来源台账.csv`。完整放置说明见 `实验资料/README.md`。

数据放入后不会自动入库：T2.6 根据实际文件生成字段映射，确认列含义/单位、设备/地块/深度、有效时间及降雨累计/增量口径后再导入。原始文件不补值、不手工去重、不改设备 ID。资料暂缺不阻塞下一阶段接口和 mock 的实现。

下一步为 Phase 2：HYDRUS 适配层、统一结果/状态、真实查询工具及本地服务接口；新版小程序页面仍按 Phase 3/4 改造，目前不会因资料目录完成而出现新页面。

## Phase 2 后端工程已实现（T2.1–T2.8）

HYDRUS逐日输入/参数反读、四状态案例与0/20mm同参数比较、状态过滤、地块隔离、数据画像/确认映射入库/统计与来源回查、本地循证客户端/mock、5个白名单工具、一次追问、证据与调用轨迹已完成。当前pytest 51 passed，含随机端口实际HTTP知识/缺数据/真实HYDRUS假设情景；仅本地提交。

使用见 coffee_digital_twin/docs/zyh/Phase2使用说明.md；契约见 本地服务接口契约.md；HYDRUS输入/输出与限制见 HYDRUS工具说明.md。已经运行的旧后端需要重新启动以加载新代码；mock独立启动，所有回答显示MOCK标签。

资料暂缺的影响：真实catalog非空、实测参数校准和真实服务联调验收尚未完成。不生成或冻结空data-v1.0，不把构造数据当实测。数据放raw后还须确认column_mapping.yaml和device_plot_map.csv，确认后才可导入；IN-G10原TXT布局待实际格式确认。H1/H2原文、H3/H4数据映射、H5蔡的地址/契约、H10引擎许可仍待人工。

新版小程序界面仍按Phase3/4增量改造，当前Phase2主要完成后端。原仓库和正式测试资料保持隔离。

## Phase 3 工程已实现，真实资料相关验收待补齐

现在小程序已经改造为工作台、问答、农情、情景四个tab，地块/农事、模型结果、证据详情和五节报告也已接入。沿用之前的原生框架与配色。重新启动后端，并在微信开发者工具中打开本工程miniprogram目录、点击编译即可查看新版。

当前61项测试通过，所有WXML原生编译通过；HYDRUS连续五轮双案例10/10成功，最长0.067333秒，保持live。mock四路径已联调，报告HTML支持浏览器打印。

需要继续补齐的是真实资料/映射、蔡的真实服务、开发者工具界面截图，以及20条冻结实测可核验案例。当前没有data-v1.0，资料中的案例包明确partial，只有4条HYDRUS假设案例。A/B情景向导按Phase4继续实现。

最新版使用与验收范围见 `coffee_digital_twin/docs/zyh/Phase3使用说明.md`。本节取代上文旧的“前端待Phase3改造”状态说明；历史阶段记录保留。

## Phase 4 工程已实现（2026-10-18）

情景tab已接入“设定→确认→对比”：单一额外灌溉、假设确认、真实HYDRUS A/B计算、参数反读核验、双线/深度差值、证据与报告、重新确认历史回放、助手只读解释。统一错误码和六步演示脚本已补齐。72项pytest通过，独立本机HTTP实时对比与T2.2一致，继续保留live。

重启后端并在微信开发者工具编译新工程即可查看。入口和验收边界见 `coffee_digital_twin/docs/zyh/Phase4使用说明.md`。真实资料、蔡的真实服务、开发者工具实际截图和真人六步计时仍待补齐。当前工程功能完成不代表正式实测/人工验收全部通过；Phase5工程核对情况见下方。

## Phase 5（2026-10-18）

自检工具、研究任务/成果核对、交付目录与逐文件贡献表已提供，77项pytest通过；实际完整环境自检仍FAIL，缺真实冻结数据/有效版本及蔡的真实服务。截图、录屏、正式评价与HYDRUS许可仍待补。详见[Phase5使用说明](coffee_digital_twin/docs/zyh/Phase5使用说明.md)。
