# AGENTS.md（放在 VX_3Models 仓库根目录）

本仓库是“咖啡农事循证决策助手”竞赛项目。你（Codex）负责执行张源皓的任务清单。

完整计划：`coffee_digital_twin/docs/zyh/CODEX_PLAN.md`。开始工作前先读完整份计划，再读 `docs/zyh/PROGRESS.md` 和 `docs/zyh/待人工确认.md`。

硬性规则（详见计划第 1 节）：

1. 按任务号顺序执行；设计已经定好，只实现，不重新设计。遇到计划与代码事实冲突时，选最小改动方案，并写进 `待人工确认.md`。
2. 只在 `zyh/competition` 分支工作；每个任务一个提交，提交信息格式为 `[任务号] 简述`；不 push 到 main、不 force push、不改 git config。
3. 不修改：`backend/models/apsim_adapter.py`、`backend/models/beps_adapter.py`、`server/hydrus_engine/H1D_CALC.EXE`，以及 `实验资料/06_正式测试资料/` 里的任何内容。
4. 不用示例值或 demo 值填补真实数据缺失，缺失写进 `missing_fields`；demo/fallback 必须带上明确的状态和标签。
5. 工具调用只走白名单；不执行模型生成的命令或路径；不输出、不提交 `.env` 里的密钥。
6. 环境是 Windows PowerShell，Python 用 `coffee_digital_twin/.venv`；依赖固定版本。
7. 任务完成的条件：该任务的验收全部通过，`pytest -q` 全绿，并且已经在 PROGRESS.md 记录。
8. 遇到需要人工输入的阻塞，先做桩代码和模板，记录下来，再继续做不受阻塞的任务。
9. `zyh/` 目录是张源皓原始的 HYDRUS 实现，只读，用作参考和回归测试数据；改造只在 `coffee_digital_twin/backend/models/hydrus_adapter.py` 上做。
10. 小程序在原 `miniprogram/` 上增量改造，设计以计划 4.7 节为准（页面、组件、配色、文案、无障碍要求）；不引入 npm 包或 UI 库，不使用 ECharts；旧文件头的署名和 `AI辅助生成` 注释保留不删。
