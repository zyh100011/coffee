# Phase 2 使用与验收

后端工程T2.1–T2.8已实现。真实资料/映射、土壤参数出处、蔡的真实服务尚未确认；这三项科学/真实联调验收待人工完成。小程序页面仍旧版，新blocks渲染按Phase3实施。

启动后端沿用server/start_backend.ps1；在另一PowerShell窗口切换backend，运行 `..\.venv\Scripts\python.exe tools/mock_evidence_service.py`。mock默认127.0.0.1:8001，只用于接口联调。后端若已运行旧代码，先在原启动窗口Ctrl+C，再重新启动。不得把mock结果称为文献检索或正式评测。

接口：GET /api/assistant/health；POST /api/assistant/chat；GET /api/evidence/<evidence_id>；GET /api/data/catalog?plot_id=；POST /api/data/query；GET /api/data/source/<obs_id>。聊天请求示例：`{"session_id":"s1","plot_id":"已建地块ID","message":"40cm墒情","history":[]}`，随后带supplement={start,end}补充日期。数据为空返回缺项，不自动生成观测。假设情景消息示例：如果2026-09-01多浇20mm，结果标未校准模拟。

单轮≤3工具、≤1次HYDRUS；数据窗口≤366天；拒绝未知工具、额外路径/命令参数、跨地块；仅读取已确认档案。每轮写assistant_traces；导出在backend运行 `..\.venv\Scripts\python.exe tools/export_traces.py --out "实验结果路径/traces.jsonl"`。正式测试目录不可读写，凭据字段/环境密钥会脱敏。

服务离线时只开放可确定的数据查询，展示事实、图表、来源及解释不可用警告。失败/demo工具不会传给解释作为可用结果；未知证据主张标未核验。MOCK引用明确演示标签。LEGACY_GLM默认0，保留旧代码但不自动外调。

资料操作：原文件放实验资料/03_地块与监测数据/raw；运行profile_raw生成画像；确认column_mapping.yaml的列、单位、雨量累计/增量、priority、crop与时期版本及confirmed=true；填device_plot_map.csv的字符串ID/地块/深度/有效期；运行ingest_monitoring。LAI/事件/报告暂有规范CSV契约，原IN-G10 TXT布局待确认。确认非空实测后才运行freeze并按计划打版本标签，目前不冻结data-v1.0。

验收使用隔离临时库/目录和随机HTTP端口；不污染原数据库、不停止用户后端。实际HTTP三请求覆盖知识mock、数据缺失、Windows真实HYDRUS20mm假设；服务停机错误也已核验。APSIM引擎未提供，其fallback不作为证据；BEPS内部默认气象由外层标为演示。原模型源码/zyh/EXE保持不变。
