# Phase 5 功能核对与交付（2026-10-18）

T5.1–T5.4的工程实现、功能核对、交付路径检查和逐文件贡献表已提供。2026-10-22复核：真实观测已经入库，完整环境自检仍为FAIL，剩余门槛是冻结版本、有效DATA_VERSION和蔡的真实循证服务，不能再将FAIL解释为没有真实监测数据。

在`coffee_digital_twin/backend`目录的PowerShell执行：

```powershell
../.venv/Scripts/python.exe tools/selfcheck.py
../.venv/Scripts/python.exe tools/check_delivery.py
../.venv/Scripts/python.exe tools/audit_claims.py
../.venv/Scripts/python.exe tools/contribution_audit.py --check
../.venv/Scripts/python.exe -m pytest -q
```

自检默认复制数据库，在临时本机端口发真实HTTP请求，不改现有5000服务或源库。结果写入`server/logs/selfcheck_<时间>.txt`，任何FAIL都返回非零。首次实际结果见`selfcheck_phase5_initial.txt`。不要通过填示例数据把FAIL改成PASS。

自检从有效观测按地块、参数、深度、设备、原单位和版本选取一组查询。未配置冻结版本时，仍对已入库实测运行catalog/query诊断，但frozen_data和environment保持FAIL，不能冒充冻结验收通过。回放接口使用0/20mm历史案例原始起始日，核对结果保留原地块、时间范围和参数版本；不将观测日期替换进历史案例。助手请求包含实际参数、来源和单位，真实服务能否按契约处理仍须联调。

交付入口为`交付目录.md`和`delivery_manifest.json`，功能对应关系见`功能核对表.md`，每行措辞核对见`措辞扫描明细.json`。pending项的路径只指缺项说明，不能当成数据、截图或视频实物。补资料后的检查步骤见`待补交付材料.md`。

`新旧贡献记录.md`含基线221a26b的123个旧文件归属和本届全部改动路径；原始Git历史与统计另存TXT，结构化记录见`contribution_audit.json`。Git提交者身份不等于唯一知识产权作者。旧署名和AI注释保留，HYDRUS外层及其他模型包装不算原创数值模型。

源码打包命令（只收已被Git跟踪的文件）：

```powershell
../.venv/Scripts/python.exe tools/package_source.py
```

输出到`backend/runtime/delivery/source_phase5.zip`，只在本地保存。包排除HYDRUS EXE、密钥、数据库、运行目录、原始实验资料及三个用户本地微信配置；微信配置重建和第三方版本见`源码交付配置.md`。缺少的引擎须按H10确认许可后自行获取。完整新机启动包与另一台电脑验收属Phase 6。

当前仍需收尾：H2目标10份文献正文目前8份，土壤参数映射与交叉复核未完成；已有真实监测、土样化学指标和10/12地块档案，降雨累计/复位口径与样品关联等仍待确认；H5真实服务联调、H8开发者工具交互截图/真人演示、H9冻结实测案例、H10许可，以及蔡/简负责的正式效果、专家与试用记录。用户仅有现有监测数据，额外现场校准资料不再作为本期必须补交条件；模拟结果与参数出处保留真实身份和验证边界。
