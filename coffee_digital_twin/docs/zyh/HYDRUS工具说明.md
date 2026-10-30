# HYDRUS 工具说明

## 1. 名称、版本和执行入口

HYDRUS-1D 为外部机理模型 EXE；本届仅适配输入、执行、解析和来源状态，不修改数值求解。入口 `backend/models/hydrus_adapter.py::run_hydrus_model(dict)`。Windows、Python 3.11 和工程固定依赖；引擎位置 `HYDRUS_EXE`，默认 server/hydrus_engine/H1D_CALC.EXE。model_version 记录实际 EXE SHA256 前12位。HYDRUS_TIMEOUT_S 默认60秒；HYDRUS_MODE=live/replay；ALLOW_DEMO_FALLBACK 默认0。案例参数版本为 hydrus-params-3e5da27bd790。

## 2. 输入字段、单位与生效方式

| 字段 | 类型/单位 | 必需/允许值 | 来源、默认和实际生效 |
|---|---|---|---|
| task_id | 字符串 | 可省略自动生成；字母数字下划线短横线，≤100字符 | 标识运行目录，不执行外来路径 |
| plot_id | 字符串/null | 适配器可空，业务层要求地块 | 未知不补示例地块 |
| scenario.start_date / start_date | ISO日期 | 必需，scenario优先 | 初始时刻，第7日输出为 start+7 |
| weather_series[].date/source/rain_mm | 日期/字符串/mm | 可缺；仅 observation/observed | 窗口内逐日累计；未知降雨按0假设，demo不作实测 |
| farm_operations[].op_type/date/amount/unit | 字符串/日期/数值 | 可缺；灌溉单位 mm 或吨/亩、t/mu、ton/mu、tons/mu | 仅7天窗口内 irrigation，换算后进入对应日期；无记录不证明未灌溉 |
| scenario.extra_irrigation_mm | 数值/mm | 0–100，默认0 | 第一天追加的假设输入，不是操作指令 |
| rsoil_cm_d、rroot_cm_d | 数值/cm/d | 非负，覆盖必须带同名 _source | 默认0.15/0.22，模板固定蒸发/潜在蒸腾，实际写入7行并反读 |
| SELECTOR.IN / PROFILE.DAT | 模板文件 | 固定 | 通用土壤水力参数、初始压力水头、自由排水下边界；非地块实测；只在运行副本修改逐日打印时间 |

Prec=(当天实测降雨+记录灌溉+首日额外灌溉)/10 cm，写入精度0.001cm。其余大气字段沿模板（hCritA=100000等）。inputs.daily_prec_cm、rsoil_cm_d、rroot_cm_d 从实际生成文件反读；inputs还含日期、窗口灌溉和run_directory。

## 3. 输出与能力范围

| outputs字段 | 单位/尺度 | 方法与限制 |
|---|---|---|
| soil_moisture_series | cm3/cm3；第0–7日8点；10/20/40/60/100cm | 按Nod_Inf.out独立Time分块；不是观测序列 |
| soil_profile_current | cm3/cm3/cm；第7日5深度 | 对应节点theta；status用0.24/0.20/0.16工程阈值 |
| root_uptake_ratio | 无量纲，7日累计 | T_Level.out列名sum(vRoot)/sum(rRoot)，潜在值为0时null |
| root_uptake_totals | cm，7日累计 | 实际/潜在吸水累计量 |
| infiltration_depth_cm | cm，第7日 | 相比初始theta增量>0.01的最深节点，无则0；不是现场测量湿润锋 |
| water_status/classification_basis | 字符串 | 40cm阈值分级；未依据本地块持水量/凋萎点 |
| hydrus_explain | 中性文本 | 第7日40cm值和初始差值，不输出灌溉处方 |

仅支持同参数、同窗口的假设水分响应比较。不能支持产量、田间节水、已校准准确性或实际最优灌溉量结论。source_type始终simulation_uncalibrated（显式fallback除外）。T3.2 已移除顶层兼容字段，前端仅从 outputs 读取。

## 4. 状态与展示

| status | 触发条件 | 前端处理 |
|---|---|---|
| success | 引擎退出正常，无Error.msg，必要输出及8剖面齐全 | 未校准模拟标签；可解释假设 |
| missing_input | 无日期/输入不合法 | 展示缺项，不显示结果数字 |
| timeout | 引擎超时 | 保留输入，重试或回放 |
| failed | 无引擎、非Windows无包装、错误文件/退出码/解析失败 | 展示失败原因，outputs为空 |
| fallback | 失败且显式ALLOW_DEMO_FALLBACK=1 | 红色工程演示标签，不作证据 |
| replay | 找到相同额外灌溉的历史success案例 | 历史回放标签；保留原日期、参数、地块，不能改称当前地块新结果 |

仅success/replay可进入解释。统一结果包含证据ID、task/plot、时间、输入、假设、版本、单位、缺项、警告、created_at及mode。

## 5. 案例索引

backend/data/hydrus_cases 与 实验资料/04_三模型工具资料/HYDRUS/cases 各保存一份：baseline_0mm、irrig_20mm、missing_input、engine_failed（文件均带case_前缀和.json后缀）。成功案例为2026-09-01起始、无实测降雨的假设输入。case_compare_0_vs_20.json记录同参数版本同窗口：首日prec差2.0cm，第7日40cm theta差0.0115。historic_nonconverge_Error.msg是原zyh/test_001不收敛日志，只作失败记录，不是上述成功案例的日志。

生成命令：在backend执行 `..\.venv\Scripts\python.exe tools/generate_hydrus_cases.py`，需要本地可运行的引擎；生成器不会修改原zyh或EXE。

## 6. 日志、依赖与适用限制

每次创建独立runtime/hydrus_runs/<task>_<随机ID>，保存运行副本、engine_stdout.txt、数值输出和hydrus_result.json；不删除历史目录。参数版本由实际SELECTOR.IN+PROFILE.DAT字节联合哈希生成，大气输入单独保存在inputs。降雨来自业务观测查询，灌溉来自地块记录；目前真实资料未提供，案例只用明确假设。历史回放包含原证据ID及请求地块元数据。

待张源皓确认：土壤模板参数/初始剖面的原始出处；当地土壤实测、边界与根系参数；工程分级阈值适用性；HYDRUS再分发许可。未确认前不得对外打包EXE或声称田间校准通过。

### T3.6 本机实时调用核验（提前执行）

2026-10-14 按计划 10/18 的规则提前核验，五轮 baseline 0mm / extra 20mm，共 10 次真实 Windows 引擎调用。10/10 success，最长 0.067333 秒，均低于 30 秒；统一结果契约和逐日输入反读全部通过，参数版本一致。决定保持 `HYDRUS_MODE=live`。核验使用假设输入和模板土壤参数，只证明本机工程稳定性，不是田间校准或准确率验证。

完整记录：`docs/zyh/hydrus_phase3_stability.json`，含每轮证据ID、输入、耗时、版本、输出文件及 SHA256。运行目录独立，不覆盖 T2.2 历史案例。复核命令：在 backend 执行 `..\.venv\Scripts\python.exe tools/verify_hydrus_stability.py`。如果后续复核不满足全部成功且每次≤30秒，应改为 replay 并记录实际结论。
