# GitHub 协作说明

更新日期：2026-10-22。

## 查看与下载

当前协作仓库：https://github.com/zyh100011/coffee 。协作分支：`zyh/competition`。本届代码位于 `coffee_digital_twin/`；`zyh/` 是旧 HYDRUS 实现参考，不是本届主入口。

队友可在 GitHub 切换到 `zyh/competition`，或执行：

```powershell
git clone --branch zyh/competition --single-branch https://github.com/zyh100011/coffee.git coffee_competition_zyh
Set-Location coffee_competition_zyh
```

## 给队友的文档入口

- [本地服务接口契约](本地服务接口契约.md)：蔡的 route/answer 服务请求、响应和错误处理约定。真实地址、字段确认及联调仍待完成。
- [HYDRUS 工具说明](HYDRUS工具说明.md)：输入、输出、版本、案例和适用限制。
- [进度记录](PROGRESS.md)：实际完成任务与验收结果，最新一行优先。
- [待人工确认](待人工确认.md)：仍待确认的接口、许可和人工验收。
- [功能核对表](功能核对表.md)、[交付目录](交付目录.md)：页面、接口及交付成果位置。
- [新旧贡献记录](新旧贡献记录.md)：继承内容和本届改造的归属。

## 本机启动

需要 Windows 和 Python 3.11，微信开发者工具用于查看小程序。以下命令在克隆仓库根目录运行；已有 `.venv` 时不必重建。

```powershell
Set-Location coffee_digital_twin
py -3.11 -m venv .venv
& ./.venv/Scripts/python.exe -m pip install -r ./backend/requirements.lock.txt
if (-not (Test-Path ./backend/.env)) { Copy-Item ./backend/.env.example ./backend/.env }
& ./server/start_backend.ps1
```

另开 PowerShell 查看 `http://127.0.0.1:5000/api/ping`。微信开发者工具导入 `coffee_digital_twin/miniprogram/`；使用自己本地的开发者配置，并核对 `utils/config.js` 的后端地址。真机中的 `127.0.0.1` 指手机自身，需按实际局域网环境配置。后端没有鉴权，仅供本机或可信局域网联调，不应直接开放到公网。

## 数据、引擎与验收边界

代码共享不包含 `.env`、本地虚拟环境、运行数据库、原始监测文件或文献 PDF。字段画像、数据处理逻辑、报告结构和测试可查看；克隆后真实农情查询可能为空，数据需通过团队单独约定的渠道提供并按现有导入流程处理，不生成替代真实数据的示例值。

新仓库采用当前已提交源码的独立快照，保留原作者署名、AI辅助注释及已导出的贡献记录；此前逐任务 Git 历史保留在本机与原仓库的 `zyh/competition` 分支：https://github.com/ToomyNike/VX_3Models/tree/zyh/competition 。新仓库不包含 HYDRUS EXE，待许可确认后按合法渠道另行配置；本地原有引擎文件不修改。未配置引擎的电脑不能直接进行实时 HYDRUS 运算，可查看已有案例和回放结果。

贡献审计工具引用旧基线 `221a26b`；独立快照克隆本身不含该历史对象。需要复跑 Git 归属审计时，可在克隆目录执行 `git fetch https://github.com/ToomyNike/VX_3Models.git main` 取得基线历史；已导出的贡献表可直接阅读。86项测试通过的记录来自具有完整历史和本地引擎的开发仓库，不代表新电脑无需配置即可全部运行。

目前完整环境自检仍有未通过项：环境配置、正式冻结版本及真实循证服务。mock 仅用于开发联调，必须保留 MOCK 标识。雨量口径复核尚未生成模型日雨量输入。Phase 6、正式评测、截图和录屏未完成。

## 后续同步

在干净工作区并确认当前分支为 `zyh/competition` 后，可用 `git pull --ff-only` 更新。不要覆盖自己的未提交配置，不向 `main` 直接推送，也不要 force push。
