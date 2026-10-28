# GitHub协作说明

更新日期：2026-10-29。

## 先看当前交接

- [团队最新交接说明](../../../团队交接说明.md)：现有代码、监测数据、来源口径、运行方式与共享边界。
- [三人联调待办](三人联调待办_20261029.md)：蔡济远、简光耀、张源皓的收尾任务和完成依据。
- [操作手册](操作手册.md)：安装、快照导入、启动、手机预览及恢复。
- [最新进度](PROGRESS.md)、[交付问题清单](交付问题清单.md)：详细核验记录。

## 查看与下载

协作仓库为 https://github.com/zyh100011/coffee ，默认展示与协作分支为zyh/competition。本届入口是coffee_digital_twin/；zyh/为旧HYDRUS只读参考，不是主入口。无需下载上一届独立JGY工程。

```powershell
git clone --branch zyh/competition --single-branch https://github.com/zyh100011/coffee.git coffee_competition_zyh
Set-Location coffee_competition_zyh\coffee_digital_twin
```

也可在仓库选择Code → Download ZIP；更新前保存自己的配置和改动。Git克隆的干净工作区可以在确认分支后用git pull --ff-only，不要直接覆盖自己的未提交修改。

## 数据与引擎

原始监测和土检目录已共享33个文件（31个CSV、1份土检PDF、1份README），更新时保留原内容。原数据有来源、时段和单位差异，实际筛选以catalog为准；不能把所有记录直接混接。

运行数据库不在GitHub。按当前核验安装流程，需另取张源皓的data-v1.0.db冻结快照及匹配原始文件，按操作手册放置或传入-Snapshot和-RawRoot后再运行server/setup_windows.ps1。需显示JGY历史气象时另交匹配原始目录，并按手册配置-TeamRoot。已有数据库不会被安装脚本直接覆盖；缺资料时不要生成假数据补齐。

本地数据冻结已完成，原始监测476,215条，其中有效424,988条；土检9样品81项。日降雨已按已确认计数器规则接入HYDRUS外层。快照实际交接与接收电脑复跑仍需登记，这不等于“尚未冻结”。

HYDRUS EXE未上传；新机须合法取得并配置引擎，或使用原日期的历史回放。再分发许可未确认前不把EXE随包发布。.env、令牌、虚拟环境、本机配置的未提交修改、运行数据库、完整队友交付目录及正式测试资料不随本次文档更新上传。

## 启动与联调

数据和环境齐备后，在coffee_digital_twin目录执行：

```powershell
.\server\setup_windows.ps1
.\server\start_demo.ps1
```

要求Windows、Python 3.11和微信开发者工具；依赖固定在backend/requirements.lock.txt，小程序不用npm。查看本机5000端口的/api/ping后，微信工具导入miniprogram/。新机根据utils/config.example.js创建本机配置；手机预览须改用电脑的可信局域网IP，手机127.0.0.1并不指电脑。

蔡的真实模型服务在另一台电脑。按[蔡服务接入操作](蔡服务接入操作.md)配置可达业务地址和后端本地令牌，重启后验证health、route与answer；原模型电脑的127.0.0.1不能直接跨电脑访问。客户端与mock可用不代表真实服务已接通。

小程序默认用户模式；工作台基地名连续点击5次切换开发者模式，可查看服务模式、来源、假设和轨迹。后端接口与报告HTML保留证据状态。当前业务接口无鉴权，仅供本机或可信局域网，不向公网暴露。

## 验收与历史

开发电脑最近完整回归115项通过；最近综合自检12项通过，evidence_health/http_assistant两项因真实服务仍未完成而未通过。真实服务、微信/手机、案例实际交接、引擎许可、第二台电脑和录屏仍须分别验收。不要把模板、mock、模拟图或同机新目录当成真实验收。

新仓库以独立快照方式接收本机提交内容，保留已有远程提交和原作者署名、AI辅助注释。本机逐任务历史与导出的[新旧贡献记录](新旧贡献记录.md)用于溯源；快照Git历史不同于本机开发历史。

贡献审计引用旧基线221a26b；仅克隆新仓库时不含该对象。如需复跑Git归属审计，可取原仓库基线：

```powershell
git fetch https://github.com/ToomyNike/VX_3Models.git main
```

数据版本data-v1.0已在本地建立，本次不上传DB或新增远程标签；最终submit-v1待人工验收完成。只更新zyh/competition，不向main推送、不force push、不修改Git配置。
