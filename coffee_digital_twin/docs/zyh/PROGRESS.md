# 张源皓执行进度

执行依据：本目录 CODEX_PLAN.md（2026-10-14 v2）。

| 日期 | 任务 | 改动文件 | 验收 | 遗留 |
|---|---|---|---|---|
| 2026-10-14 | T0.1 | 仓库 AGENTS.md、CODEX_PLAN.md、本表、待人工确认.md | 独立工程已建立；分支 zyh/competition；基线 221a26b | pytest 尚未安装且测试骨架计划在 T0.3 创建；在 T0.3 补验，不能将无测试视为全绿 |
| 2026-10-14 | T0.2 | .gitignore、config.py、requirements.txt/lock、.env.example、start_backend.ps1、配置与启动测试 | Python 3.11.9；8 个指定依赖版本安装成功；pip check 通过；pytest 4 passed；PowerShell 从其他目录启动、实际 HTTP ping 返回 ok | 不修改 APSIM adapter；HYDRUS_MODE/ALLOW_DEMO_FALLBACK 目前仅接入配置，行为修正按 T2.1 执行 |
| 2026-10-14 | T0.3 | tests/conftest.py、test_smoke.py、capture_phase0_baseline.py、baseline_snapshot_before.json | pytest 8 passed；四个旧接口冒烟通过；实际 /api/model/run 一次：APSIM=fallback、HYDRUS=success、BEPS=ok；HTTP 200 | 基线包含旧 demo 和自动补值，只用于工程回归；T0.1 的 pytest 启动依赖已补验 |
| 2026-10-14 | T0.4 | verify_hydrus_baseline.py、test_hydrus_inspection.py、hydrus_phase0_verification.json、根目录开始说明 | HYDRUS 实时可运行：是；adapter=success；T_Level.out/Nod_Inf.out 存在；Error.msg 不存在；Time=0/7；运行约 0.062 秒；pytest 13 passed | 使用假设输入和模板参数，非地块校准；吸水比解析等旧实现问题按 T2.1 修正 |
| 2026-10-14 | T1.1 | 页面接口复用清单.md、待人工确认.md | 六个旧页面和 13 条业务路由逐项核查；新增入口及地块/任务绑定规则明确；pytest 13 passed | 表结构、06 隔离与项目配置差异已记录；不提前改造页面 |
| 2026-10-14 | T1.2 | inventory_assets.py、material_paths.py、fixtures/raw_sample、盘点测试、requirements/lock、资产清单.csv | pytest 19 passed；CSV 重叠检出；字符串 ID 保留；UTF-16 TXT、多工作表 XLSX、同哈希/空目录/损坏文件检查通过；CLI 构造案例 2 文件 1 重叠；真实目录为空正常退出；pip check 通过 | 增补 XLSX 依赖已记录；当前真实数据未提供，不将 fixtures 算作观测 |
| 2026-10-14 | T1.3 | 实验资料目录说明、来源台账.csv、土壤字段映射表.csv、缺项表.csv、raw 使用说明 | 8 目录已建立；7 个可访问目录有 README；A1–A7 目录与负责人明确；18 列台账、21 行空数值土壤字段核验；PDF/raw/06 被忽略；pytest 19 passed | 06 内不写 README，说明放父目录；空目录不进入 Git；raw README 仅本地存在且不提交 |
| 2026-10-14 | T1.4 | ledger_check.py、test_ledger_check.py、A3 检索清单.md | pytest 24 passed；空台账提示待填；构造错误台账 CLI 返回 1 并报告字段缺失和文件不存在；重复 ID/内容、受限路径测试通过 | 检索主题和登记辅助已完成；H1/H2 原文仍待张源皓提供，不算资料齐全或科学核验 |
| 2026-10-14 | T1.5 | dev_soil_zyh.jsonl、开发题说明、根目录开始说明、待人工确认.md | 10 行 JSON 逐行解析通过，qid 唯一，五类型各两行；题目/答案/证据未编造；pytest 24 passed；两工具从仓库根目录调用正常；受保护文件对基线 diff 为空 | 问题由张源皓填写；不接触正式题集 |
| 2026-10-14 | T2.1 | hydrus_adapter.py、tool_result.py、test_hydrus_adapter.py、新旧贡献记录.md | pytest 29 passed；Windows 实际回归 6.1cm 输入、8 时间点、40cm theta 与 0.1935 误差 <0.002；参数文件反读、缺项/失败/fallback/超时测试通过 | 模板土壤参数未校准；未知日期在缺项结果中为 null，不编造 ISO 日期；只认明确 observation/observed 降雨 |

## Phase 1 当日小结

- T1.1–T1.5 已按顺序实现，任务分别提交；本轮没有提前改造前端或数值模型。
- 原始数据暂缺：已准备放置说明、来源台账、21 行空数值土壤字段和 10 行待填开发题。用户后续放原始文件即可开始盘点，字段/设备映射需要人工确认后才能入库。
- 两个工具都只读原始材料，默认工作目录通过脚本位置定位，支持从不同 cwd 调用；正式测试目录被路径守卫拒绝。
- 微信 AppID/开发者工具 private 配置/本机 BASE_URL 保持当前本地改动，不混入任务提交；原仓库和受保护模型不修改。

## 工程位置与原有改动

- 用户要求在当前文件夹内另建文件夹。工作仓库：`E:\coffe model\coffee_competition_zyh`；工程子目录：`coffee_digital_twin`。
- 从本机 `VX_3Models` 独立 clone（不使用 hardlinks）；原仓库不修改。新仓库 origin 指向本机源仓库，仅本地提交，不推送。
- 原仓库基线：`221a26b 完成本土化注释`。实际内容差异已用 `git diff --ignore-all-space --stat` 核实。
- 继承用户未提交的 requirements 新增 requests、微信 AppID 和 BASE_URL 改动；小程序两个配置文件维持未暂存，不混入任务提交。T0.2 将按计划固定 requirements 版本。
- 复制已有 coffee_demo.db（Git 忽略）；验收使用独立临时库和运行目录，避免污染这份数据。
- 原仓库删除的四个 runtime `.gitkeep` 不迁移为新工程的删除改动；保留 clone 的占位文件。`backend.zip` 是旧备份，不复制。
- 原始 `zyh/`、APSIM/BEPS adapter、HYDRUS EXE 保持基线内容。

## T0.2 运行口径

- `.venv` 位于工程根目录，启动脚本直接调用其 Python（等效于激活后执行，避免依赖 conda 和调用者 cwd）。
- `COFFEE_DB_PATH` 和 `COFFEE_RUNTIME_DIR` 可覆盖存储位置；空值使用工程默认路径。
- `.env` 支持 BOM、注释、引号及等号内容；进程环境变量优先，不输出密钥。
- 已删除 config 中旧 APSIM D 盘探测路径；默认使用工程引擎目录，另一个引擎可通过 APSIM_EXE 指定。
- requirements.txt 固定计划要求的直接依赖；requirements.lock.txt 记录本次完整安装版本，供复现。
- 启动验收选取临时端口，临时 SQLite 和 runtime；验收结束关闭本次启动的进程树。没有遗留后台服务。

## T0.3 基线说明

- 冒烟测试替换三个引擎入口，使用明确的 test_stub 结果；验证 HTTP、调用链及结果持久化，不把构造数据当实测。
- 基线另用真实旧 adapter 执行一次；临时目录隔离，外层监督器限制总运行时间 60 秒。
- APSIM 本机工程目录没有引擎，旧 adapter 回退演示数据；BEPS 是简化计算，且依赖包含 APSIM fallback。不能称为三模型全部真实运行成功。
- HYDRUS 在这次旧工程基线中为 success；T0.4 再独立检查输出文件、模拟时间和错误文件。

## T0.4 核验与当日小结

- `hydrus_phase0_verification.json` 保存本次完整运行目录、每个输出文件的大小/SHA256、引擎 SHA256 和检查项。
- 实际 HYDRUS 输出含日期/时钟表头和独立模拟 Time 行；核验器只解析独立模拟行，排除时钟表头，并加入对应回归测试。
- 核验脚本每次创建唯一运行目录，外层监督器限时 60 秒；不改旧 adapter 和 EXE，不删除之前结果。
- Phase 0 已完成。新仓库中四项任务分别提交。后续只按 Phase 1 推进，不提前实施前端或他人负责的模型算法。
- 查看入口为仓库根目录 `README_从这里开始.md`。最终核对：原仓库 git status 与开始时一致；两份已有数据库 SHA256 相同（C52EC13200EF…）；zyh、APSIM/BEPS adapter、HYDRUS EXE 对基线的 git diff 为空。
| 2026-10-14 | T2.2 | generate_hydrus_cases.py、两份 HYDRUS 案例包、回放测试 | pytest 30 passed；两组实际引擎 success、相同参数版本、首日 prec 差 2.0cm、40cm theta 差 0.0115；历史不收敛记录已复制 | 全部输入为假设，不属于实测/校准；回放保留历史日期和地块 |
| 2026-10-14 | T2.3 | HYDRUS工具说明.md（工程/资料两份） | 六节与实际代码/案例逐项核对；backend cwd pytest 30 passed | H2/H10 模板出处、土壤资料和许可待确认；首次从根目录运行pytest导入失败，按约定backend目录重跑通过 |
| 2026-10-14 | T2.4 | model/result/advice API、result_store/weather_service、数据库兼容迁移、request.js、选择测试 | pytest 32 passed；空库run=400；空农事/气象不生成记录；两个地块dashboard需显式选择；跨地块task拒绝 | 对比旧基线：移除固定plot_001、25mm+10kg、默认demo天气和全局最新；旧plot初始化默认字段留到T3.7，不能作已确认档案 |
| 2026-10-14 | T2.5 | tool_registry包装、fusion_engine、model调用外层、validation_cases标记、状态测试 | pytest 35 passed；failed/fallback不进入依据；部分partial、全无failed；缺失指标null、无默认正常解释 | 保护APSIM/BEPS源码；发现旧BEPS无天气仍ok且隐式补气象，外层保守标fallback/demo；仅保留有实际输入的工程阈值，具体灌溉处方改现场核查 |
| 2026-10-14 | T2.6 | data_pipeline、data_api/data_service、schema、字段画像/字典/清洗日志、数据测试 | pytest 39 passed；mean手算误差<1e-9；ID保留、优先级去重、累计雨复位、异常/缺测、来源、事务回滚、冻结拒绝fixture和版本修改通过；真实空raw/未确认映射CLI拒绝 | 工程首版完成；H3/H4真实catalog非空验收待资料；不打data-v1.0。IN-G10原TXT未知，先提供规范CSV入口；原始层级解析待格式确认 |
| 2026-10-14 | T2.7 | evidence_client、mock独立服务/3条语料、llm_service、契约、HTTP测试 | pytest 42 passed；本机随机端口实际health/route/answer通过；停止服务抛EvidenceServiceError；补充/日期/深度契约通过；外部GLM默认关闭 | 蔡真实地址和字段H5待确认；generate/chat转助手在T2.8接入；mock仅联调 |
| 2026-10-14 | T2.8 | assistant API/service、plot_context、5工具schema、trace_store/export、兼容入口、51项测试、使用说明 | pytest 51 passed；四必需路径、白名单/地块/预算/追问重置/证据查找通过；实际HTTP三消息通过；HYDRUS20mm首日2cm、8点；保护范围diff为空 | 真实资料/校准/服务联调仍待H1–H5；旧档案默认字段不进入known；新版前端Phase3；追加日雨总量>300标记及解析错误状态修复 |

## Phase 2 当日小结

T2.1–T2.8后端工程按顺序完成并各自本地提交。真实数据与服务相关验收仍待资料到位；代码/假设案例/构造测试不等于科学核验。当前51项测试全绿，实际本机HTTP链路通过。原工程、APSIM/BEPS源码、EXE、原始zyh保持不变；开发者工具3个本地配置不混入提交。没有停止用户5000服务，验收服务已关闭。
| 2026-10-14 | T3.0 | session/labels/errors/chart、request、7公共组件、app.wxss、_dev调试页、前端行为测试 | pytest 53 passed；JS语法/空单点双线/标签/请求错误通过；component=true；pages无ec-canvas | H8截图待开发者工具验收：CLI服务端口关闭；_dev开发注册 |
| 2026-10-14 | T3.7 | plot/farm API、工作台/plots/plotInit/farmLog/data、app导航、共享page工具、接口测试 | pytest 55 passed；12项完整度、空值/来源、农事400、地块隔离通过；4文字tab及catalog驱动查询 | H8实际界面截图待工具；情景接口按T4.1，当前入口明示Phase4；report/evidence暂占位随后任务接入 |
| 2026-10-14 | T3.1 | advice四件、前端行为测试 | pytest 55 passed；原问题补充/历史20消息/防重复提交行为通过；120s、离线重试、文字头像、pending消费 | mock数字展示由后端返回；H8实际截图待完成；报告按钮待T3.3 |
| 2026-10-14 | T3.8 | evidence四件、data_query_evidence、trace lookup、来源回查测试 | 工具输入/假设/状态与原文件行号回查接入；直接农情查询持久证据 | H8截图待完成；直接obs_id入口显示原始记录 |
| 2026-10-14 | T3.2 | result四件、hydrus去兼容字段 | 状态驱动卡片、outputs读取、无内置验证兜底；受保护BEPS通过外层映射读取 | H8失败界面截图待完成；旧历史案例可能仍有冗余字段，读取仅outputs |
| 2026-10-14 | T3.3 | report_builder/report_api、reports表、report页面、报告/原生WXML编译测试 | pytest 57 passed；固定五节、证据绑定、HTML转义、地块隔离、所有WXML原生编译通过 | 浏览器打印视觉与H8截图待验收；compare接口按Phase4接入 |
| 2026-10-14 | T3.4 | e2e四场景、catalog唯一深度补充、联调记录 | pytest 58 passed；实际mock HTTP K/D/M/F通过；SQL均值一致；HTML打印模式五节无横溢 | fixture明确demo；真实数据/蔡服务验收待H3-H5；开发者工具H8待验收 |
| 2026-10-14 | T3.5 | export_verifiable_cases.py、test_verifiable_cases.py、可核验案例_zyh.json、联调记录 | pytest 60 passed；隔离20条查询SQL/复跑一致、哈希/06守卫通过；实际默认导出拒绝未冻结版本 | 正式20条实测待H3/H4；当前partial包只有4条HYDRUS假设案例，H9不能视为完成 |
| 2026-10-14 | T3.6 | verify_hydrus_stability.py、test_hydrus_stability.py、hydrus_phase3_stability.json、两份HYDRUS工具说明 | pytest 61 passed；5轮双案例10/10 success；最长0.067333s；输入与版本一致 | 提前执行10/18规则，保持live；仅本机假设模拟工程核验，非校准 |
| 2026-10-14 | T3收尾 | dates工具、地块切换请求隔离、mock证据来源、报告HTML来源、app注册、README/Phase3使用说明 | pytest 61 passed；官方WXML编译/JS语法/页面组件存在性/旧请求丢弃通过；保护模型与zyh diff为空 | H3/H4/H5/H8/H9待补；已移除_dev交付注册；三个用户配置保持未提交 |

## Phase 3 当日小结

按 T3.0→T3.7→T3.1→T3.8→T3.2→T3.3→T3.4→T3.5→T3.6 执行并分别本地提交，工程功能完成。61项测试全绿，所有WXML原生编译通过，MOCK四路径与打印样式通过；HYDRUS稳定性10/10通过保留live。真实资料和服务、H8页面交互截图及正式20条数据案例验收仍待补齐，不声称Phase3全部人工/实测验收通过。未进入Phase4功能实现。
| 2026-10-18 | T4.1 | scenario_service/scenario_api、工具上下文与HYDRUS适配层mode、compare表/trace、report_builder、test_scenario | pytest 64 passed；确认前零执行；单变量/版本/窗口核验；Windows live 0/20mm差值与T2.2完全一致；回放保留历史窗口；失败无差值 | H3/H4真实数据未到；当前未校准假设模拟；H8交互待验收 |
| 2026-10-18 | T4.2 | scenario三步页、助手compare上下文、frontend_contract/test_scenario | pytest 64 passed；原生WXML编译与三步/回放重新确认行为通过；报告及白名单读结果接入 | H8真实界面点击截图待完成；mock解释仍标演示 |
| 2026-10-18 | T4.3 | verify_scenario_live.py、scenario_phase4_verification.json | pytest 64 passed；随机本机HTTP确认→真实引擎A/B，参数核验及T2.2差值全部一致 | 按10/21规则提前核验通过，保持live，不触发replay锁定；结果仅未校准假设 |
| 2026-10-18 | T4.4 | errors.py、app异常/HTTP错误规范化与日志、assistant降级errors、情景失败恢复、request/errors.js、错误码与降级.md、test_errors_phase4 | pytest 69 passed；各计划错误码可触发；内部异常脱敏；网络/超时与200业务错误前端识别通过 | 工具协议保留状态，情景failed响应附恢复字段；H8界面验收待补 |
| 2026-10-18 | T4.5 | seed_demo.py、test_seed_demo/test_phase4_flow、演示流程/Phase4使用说明、README | pytest 72 passed；六步接口链0.67s（总1.48s）；缺快照CLI拒绝、真实来源/哈希/非空目标保护通过 | 构造测试非正式演示；真实3–5分钟微信流程与H8/H3-H5待验收；保留旧演示脚本 |

## Phase 4 当日小结（2026-10-18）

按T4.1→T4.2→T4.3→T4.4→T4.5实施并分别本地提交。实时A/B参数核验和T2.2输出差值一致，保持live；72项测试通过，WXML原生编译与三步行为、错误码、来源回查、六步接口演练通过。缺少真实资料/服务/微信截图，因此这些人工/实测验收仍待补齐；未将构造测试记作真实演示。保护模型/EXE/原zyh未改，06未读写；3个用户配置保留不提交，不推送，不进入Phase5。
| 2026-10-18 | T5.1 | tools/selfcheck.py、tests/test_selfcheck.py、selfcheck_phase5_initial.txt | pytest 74 passed；真实HTTP六接口均已请求；隔离构造完整环境PASS机制与缺项FAIL机制通过；实际环境自检非零退出 | 实际冻结实测/DATA_VERSION/真实服务缺失，自检未全PASS；默认隔离副本，源库不修改 |
| 2026-10-18 | T5.2 | 功能核对表、措辞核查/明细、audit_claims.py与测试、旧docs说明修订 | pytest 75 passed；PDF第1/14页研究1–5与成果1–7逐项对应；60处命中均核对、无待处理主张 | H1–H5/H8/正式效果/专家/试用仍明确待验收；历史基线不冒称科学证据 |
| 2026-10-18 | T5.3 | 交付目录/manifest、check_delivery/package_source、源码交付配置/待补材料、screenshots说明、审计测试 | pytest 76 passed；26项声明路径全部存在；pending指向缺项说明；打包规则排除EXE/密钥/原始资料/数据库/三本地配置 | H10许可待确认，不带EXE；真实数据/截图/录屏仍缺，不以目录存在冒充交付齐全 |

| 2026-10-18 | T5.4 | contribution_audit及测试、逐文件双表/JSON/Git历史统计、Phase5说明/交付入口/措辞复核 | pytest 77 passed；123个旧文件归属，本届差异全部覆盖，旧署名/AI注释无缺失；本地ZIP排除规则核验 | T5.1全PASS受C19阻塞；真实知识/观测/服务、H8/H9/H10及正式评价待补，Phase5工程完成不等于真实交付验收齐全 |

| 2026-10-20 | T1.4/T2.3 文献补充 | 来源台账/下载核验、5条文献证据卡、16条文献对照数值及使用说明 | 原文4个PDF+1份HTML全文、2个SI PDF及7文件哈希核验；5条台账零问题；pytest 77 passed | 未达10份土壤原文；003主PDF验证码、006全文403；仅文献依据，未入实测/替换模型参数；真实知识服务接入与交叉核查待蔡/简 |

| 2026-10-20 | T2.3 土壤来源补充 | 新增006–008文献台账/证据卡，区域土壤依据、分层物理/水力参数JSON、潞江坝湿度单位画像 | 3篇PDF地点/物种/页码核对；表2/4图像核对；8条台账零问题；10文件哈希一致；pytest 77 passed（41.01s）；措辞60处零待处理；旧署名无缺失 | 006公开PDF已取得、保留前次403；新增SI页403，未完整核查。橡胶林7行物理/7行模型优化参数仅文献对照；表层颗粒合计101%保留。三层%RH/%不推定体积含水率和实测埋深；原数据/模型/06不修改，未冻结真实库 |

| 2026-10-20 | T2.6 现有数据接入 | 长表真实导入/profile、来源/拒绝行/独立报告样品表、查询来源/分页、农情页与首页、真实接口验收和缺项文档 | 31CSV493846原始行平衡；476215条观测入库，9样品81检测值；实际HTTP原CSV均值837条误差7.11e-14；源行/多来源拒绝/幂等/库完整性通过；pytest 80 passed（44.79s），含原生WXML编译/JS行为；措辞61处零待处理，旧署名无缺失；5000本机服务启动并实查入库量和9报告样品 | 深度/湿度口径/雨量口径、农事和本站校准等缺项保留；未冻结/未接蔡服务；原文件/保护模型/06不改，三个本地配置保留 |

| 2026-10-20（10-21收尾） | T2.6 用户档案确认 | 删除三个重复档案的备份迁移、单基地profile、用户层区间/湿度转换、唯一档案自动选择、数据说明 | 本地指定三档案删除，476215条原观测和81报告值不改；pytest 82 passed（47.18s），含备份/只删除指定档案/重复执行/原值保留及换算核验、原生WXML与JS行为；措辞61处零待处理、旧署名无缺失 | 湿度处理按用户指定口径，标定仍缺；自然降雨累计口径仍缺，历史灌溉不补零；旧农事/模型存档不冒充实测 |

| 2026-10-21 | T3.7 数值显示精度 | format.js、status-card/msg-blocks/line-chart、农情报告显示 | 界面数值统一两位小数；曲线坐标和数据表两位；原值与绘图计算不舍入；完整验收待运行 | 0.2356…为约23.56%的口径换算值，适宜性仍需本站持水参数 |

| 2026-10-21 | T2.6 档案补充确认 | real_data_profile.json、现有数据接入与缺项、待人工确认 | JSON校验通过；pytest 82 passed（46.45s）；用户确认卡蒂姆、10亩、海拔1050m、定位坐标、自然降雨+旱时灌水原记、有机肥；已核对监测含三层土壤温湿度、实验室报告为化学项；LAI原始记录保留但不接入本期模型/验证 | 本次更新数据画像与说明，未迁移运行数据库；土壤容重/质地/水力参数、传感器标定、逐次农事日期与实际用量仍缺 |

| 2026-10-21 | T2.6/T3.7 最新档案同步 | ingest_project_raw、apply_catimor_confirmation、test_project_raw、plots页面、贡献审计 | pytest 83 passed（46.79s）；先SQLite备份再profile-only同步、不删除档案；实际5000接口返回10亩/1050m/坐标及灌水有机肥说明，完整度6/12；隔离测试核验观测原行不变、不生成农事；原生WXML编译通过、旧署名无缺失 | 微信重新编译后查看地块档案；本次不改HYDRUS参数，文献参数尚未作为运行参数接入 |
| 2026-10-21 | T2.6 种植信息同步 | real_data_profile、ingest_project_raw、test_project_raw、数据说明、待人工确认、贡献审计 | pytest 83 passed（46.76s）；备份后profile-only同步，实际接口返回2023年种植、2026年约3年树龄、无遮挡、行距2m/株距1m，完整度10/12；测试核验SQL/JSON一致、观测不变且未生成农事；旧署名无缺失 | 树龄来源标记estimated并保留年份推算说明；既有编辑页面可查看；实际密度/株数未推填；文献土壤参数接入仍待后续 |
| 2026-10-21 | T2.6 降雨与文献参数口径确认 | real_data_profile、ingest_project_raw、test_project_raw、数据说明、待人工确认 | 用户确认CSV逐时/逐日降雨；旱时补水只作管理说明；缺失土壤物理参数可用云南/卡蒂姆区域文献值并标注来源；雨量累计/复位核验仍未完成，未生成HYDRUS日雨量 | 文献参数仍不替换本站未校准HYDRUS配置；不把连续重复雨量直接求和 |
| 2026-10-22 | T3.5 多来源案例导出修复 | export_verifiable_cases、test_verifiable_cases、联调记录、待人工确认、贡献记录 | pytest 84 passed（48.53s）；多设备/同设备异单位隔离SQL与均值、20条成功查询、真实缺测窗口、重复导出、失败拒写及哈希保护通过 | 机制修复完成；正式冻结版本及20条真实包转交H9待完成。现场额外校准资料调整为后续研究限制，不阻塞本期工程 |
| 2026-10-22 | T5.1 自检修复 | selfcheck、test_selfcheck、Phase5使用说明、待人工确认、贡献记录 | pytest 85 passed（49.04s）；多来源/异单位诊断、未冻结不误报通过、历史日期独立核验通过；实际隔离HTTP catalog/query/compare_replay均200且PASS，日志selfcheck_20261022_093857_21a0e634.txt | 工程修复通过；完整环境仍FAIL于environment/frozen_data/evidence_health/http_assistant，未将真实服务和冻结门槛改成通过 |
| 2026-10-22 | T5.3 更新交付状态 | delivery_manifest、交付目录、功能核对表、待补交付材料、selfcheck_latest、贡献/措辞记录 | pytest 85 passed（50.72s）；26项声明路径检查通过；措辞62处零待处理；修正文献/真实监测未到的过时描述，归档最新实际自检 | 两批真实监测已在临时副本各导出20条success，40条均值与独立SQL误差0，导出器逐条复跑通过；源库冻结记录仍0，正式冻结/转交、真实服务、Phase6及人工验收仍待完成 |
| 2026-10-22 | T2.6 降雨与土样口径复核 | 降雨累计特征证据、监测层与报告样品区分、C06代表样、32条原始来源路径按SHA256重链接、data_api/profile/测试 | pytest 86 passed（51.23s）；32个来源文件哈希唯一匹配；重链接前后476215条观测和81项土壤检测摘要一致；C06代表样标记与监测三层0–15/15–30/30–45cm口径核验通过 | 三个历史环境传感器读数主要呈日累计计数器特征，存在短时归零异常，另一站点降幅特征不同；尚未生成模型日雨量输入。报告样品无深度/采样日期，不套用监测层深度；C06为9样品化学指标中位数/MAD距离最小的工程代表选择，不等于全地块统计代表性；未做现场校准或正式数据冻结 |
| 2026-10-22 | T5.3 GitHub协作准备 | 根目录最新入口、GitHub协作说明、贡献/措辞记录 | pytest 86 passed（50.08s）；411个已跟踪路径未发现.env/数据库/raw/常见私钥或令牌；贡献283项、旧署名无缺失；API确认当前账号具有原仓库push权限 | 用户授权上传至原仓库zyh/competition，不推main、不改git config；origin仍指向本机原仓库，使用显式GitHub地址。GitHub API可达但Git HTTPS连接多次超时/重置；本行记录共享准备，远程上传须另以推送结果和远程提交校验确认；三个用户本地配置未纳入提交；历史已有EXE未新增或修改，许可仍待确认 |

| 2026-10-22 | T5.3 新独立仓库共享准备 | GitHub协作说明、根目录入口、贡献/措辞记录 | pytest 86 passed（51.60s）；贡献283项、旧署名无缺失；措辞64处零待处理；新仓库管理权限确认 | 用户指定zyh100011/coffee；采用当前已提交源码独立快照，保留署名和导出贡献记录，旧逐任务历史保留本机/原协作仓库；排除两份引擎EXE，不改本地保护文件。上传目标zyh/competition并设为默认展示，保留新仓库原main；上传结果与逐文件哈希另存项目核验目录。原始数据/密钥/本地配置修改不上传；快照复跑Git归属审计需取得旧基线历史 |
