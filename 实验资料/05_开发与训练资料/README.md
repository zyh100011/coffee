# 开发与训练资料

用途（方案 6.7）：开发题、可选训练/验证数据。

负责人：三人各提供 10 道本主题开发题；蔡济远负责开发协议和可选训练，张源皓填写土壤/根区部分。

dev_soil_zyh.jsonl 已于2026-10-25依据现有资料补齐10条问答，五种任务类型各两题。每行是一个 JSON 对象；“任务类型”列的值为 knowledge/data/model_explain/scenario/missing_or_conflict。格式沿用原模板，包含参考回答要点、期望工具与评分项；待张源皓/蔡济远人工审核，不算专家验证。正式测试题、参考答案及同义改写不进入此目录。

请保留 qid 的唯一性，逐行填入问题、情境、证据ID、期望工具/参数、参考要点和评分项。写实际出题人和审核状态，不把 Codex 提供的空模板记作已出题。没有可回查依据时保持空缺。

交接入口：`发蔡济远_问答与展示案例.md`；案例索引：`coffee_cases_zyh.json`；逐题证据路径：`dev_soil_zyh_evidence.json`。三例为真实历史水分查询、已有HYDRUS 0/20mm情景对比和缺少开始日期的处理。导出工具为`coffee_digital_twin/backend/tools/export_training_handoff_zyh.py`，仅查询本地库并核验来源哈希，不包含原始数据库或引擎。历史查询尚未正式冻结，HYDRUS快照保留原时间窗与参数身份。
