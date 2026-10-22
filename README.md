# 咖啡农事循证决策助手

本仓库用于本届比赛的项目协作，主要内容如下：

| 目录 | 用途 |
|---|---|
| `coffee_digital_twin/` | 本届主工程：小程序、Flask后端、模型适配、数据处理和文档 |
| `zyh/` | 张源皓的原始HYDRUS实现，作为只读参考与回归案例 |
| `实验资料/` | 本届资料目录、来源台账、字段映射、案例和交付说明 |

此前比赛的独立 `JGY/` 工程、旧开发文档及临时解析脚本已从当前分支移除。本届 `coffee_digital_twin/` 内沿用并改造的小程序和后端、模型外层接口属于当前运行所需代码，继续保留；原作者署名和AI辅助注释保留。

- [协作说明与启动方法](coffee_digital_twin/docs/zyh/GitHub协作说明.md)
- [最新进度](coffee_digital_twin/docs/zyh/PROGRESS.md)
- [蔡的本地服务接口契约](coffee_digital_twin/docs/zyh/本地服务接口契约.md)
- [HYDRUS工具说明](coffee_digital_twin/docs/zyh/HYDRUS工具说明.md)
- [新旧贡献记录](coffee_digital_twin/docs/zyh/新旧贡献记录.md)

当前默认分支为 `zyh/competition`。原始监测文件、文献PDF、本地数据库、密钥、虚拟环境和HYDRUS EXE未包含在上传内容中；`实验资料/` 中不是本机全部资料，正式测试资料保持隔离。实时运行需要另行配置环境、数据和合法取得的引擎。

开发源仓库86项测试通过。真实循证服务联调、正式数据冻结和人工验收仍待完成。新仓库为源码快照，旧逐任务历史与贡献审计基线见协作说明；当前目录精简只调整GitHub共享范围，本机旧文件不删除。
