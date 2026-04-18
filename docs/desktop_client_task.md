# 桌面客户端任务文档

## 目标

在不改动现有采集主脚本职责和入口的前提下，新增桌面客户端层，支持以下能力：

- 配置数据库连接
- 创建可迁移的任务工作区
- 导入/导出断点续传文件与任务配置
- 选择品牌、车系、城市等抓取范围
- 每完成一项抓取就本地落盘并标记进度
- 在其他电脑导入工作区或断点文件后继续抓取剩余范围

## 约束

- 不重构现有 `dongchedi_client.py` / `guazi_client.py`
- 允许新增桌面端代码、运行时适配层和文档
- 每次功能完成后先测试，再更新文档
- 不触碰用户现有采集结果文件

## 里程碑

| 编号 | 子项 | 状态 | 说明 |
| --- | --- | --- | --- |
| M1 | 创建任务文档与目录骨架 | 已完成 | 建立任务跟踪、模块目录和测试目录 |
| M2 | 工作区模型与导入导出 | 已完成 | 定义配置、范围、进度、工作区打包与恢复 |
| M3 | 运行时数据库配置注入 | 已完成 | 支持 GUI 动态配置数据库，不修改原配置文件 |
| M4 | 桌面客户端基础界面 | 已完成 | 建立桌面端窗口和基础表单 |
| M5 | 自动化测试与文档联动 | 已完成 | 固化“改动后先测再写文档”的流程 |
| M6 | 懂车帝品牌/车系目录运行器 | 已完成 | 支持目录加载、品牌选择、车系断点续拉 |
| M7 | 懂车帝概览/详情运行器 | 已完成 | 支持概览抓取、详情逐条落盘和断点续跑 |
| M8 | GUI 抓取入口与状态摘要 | 已完成 | 支持界面触发概览/详情抓取并刷新状态 |
| M9 | 工作区合并与结果去重 | 已完成 | 支持跨工作区合并配置、范围、进度和结果 |
| M10 | GUI 工作区合并入口 | 已完成 | 支持通过界面导入 ZIP 并合并到当前工作区 |
| M11 | 运行日志与事件回调 | 已完成 | GUI 内置日志面板展示目录加载和落盘事件 |
| M12 | 原脚本默认配置映射 | 已完成 | 接入输出目录、数据库默认值、显示浏览器、继续/重置策略 |
| M13 | 窗口布局重构与原脚本配置对齐 | 已完成 | 重做单页布局，补齐懂车帝关键配置，改为目录多选并修复品牌/车系切换后的旧结果污染 |
| M14 | 全部车系与批量选择交互 | 已完成 | 新增品牌/车系全选与清空按钮，支持选中品牌后一键勾选全部车系再保存 |
| M15 | 后台任务与加载状态可视化 | 已完成 | 长耗时操作移入后台线程，界面不再卡死，并显示当前正在处理的品牌/阶段 |
| M16 | 线程池异步执行与层级进度反馈 | 已完成 | 统一切换到线程池后台执行，品牌/车系按目录、概览、详情状态变色，详情恢复按并发线程抓取 |
| M17 | 视觉设计系统与信息架构重构 | 已完成 | 建立头部徽章、摘要卡片、按钮层级和控制台布局，提升界面观感与状态可读性 |
| M18 | 品牌目录稳定性与紧凑布局优化 | 已完成 | 强化品牌页下载跳转重试，压缩顶部展示高度并扩大日志区默认可视范围 |
| M19 | 自动概览与自动详情串联 | 已完成 | 新增自动抓取勾选，支持保存车系后自动抓取概览，以及概览完成后自动抓取详情 |
| M20 | 启动自动恢复与百分比进度展示 | 已完成 | 打开客户端自动恢复上次工作区，并为品牌/车系显示百分比进度 |

## 当前设计决策

- 桌面端技术栈使用 `PySide6`
- 工作区目录是任务的事实来源，配置、范围、断点和结果都落在同一目录
- 工作区支持 `ZIP` 导入/导出，便于跨机器迁移
- 运行时数据库配置通过内存注入，不直接改写 `db_config.py`
- 主窗口采用单页双栏布局：左侧配置与范围，右侧工作区、执行操作、状态和日志
- 品牌、车系改为目录多选，不再依赖手工复制文本
- 品牌和车系列表都支持“全部 / 清空”批量勾选
- “继续已有进度 / 清空旧结果后重跑”直接映射到原脚本语义
- 当品牌或车系选择变更时，自动清理下游结果文件，避免旧概览和旧详情混入新任务
- 当输出目录下已有桌面工作区元数据且选择“继续已有进度”时，创建工作区会保留已有进度和范围
- 目录加载、概览抓取、详情抓取、数据库测试等长耗时操作统一走 `QThreadPool` 后台执行，线程池上限默认映射 `max_workers=10`
- 品牌和车系颜色状态完全根据工作区真实进度推导，不依赖日志关键字硬编码
- 详情抓取阶段恢复按工作区 `max_workers` 并发执行，同时保持逐条落盘和断点续跑
- 桌面端界面采用统一设计系统：头部控制卡、摘要卡片、按钮变体、亮色工作面板和深色日志面板分层展示
- 窗口信息架构调整为“顶部概览 + 左侧配置范围 + 右侧操作控制台 + 垂直反馈区”，状态信息优先于原始日志
- 顶部视觉区保持紧凑优先，默认窗口高度下优先保证右侧运行日志和状态区可见
- 品牌目录和车系目录入口导航统一使用可复用的下载跳转重试逻辑，避免偶发 `Page.goto: Download is starting` 直接中断
- 应用启动时优先恢复上次记忆的工作区；如果没有记忆记录，则回退到发现最近使用的输出目录工作区
- 品牌和车系进度除了颜色状态外，还会根据已完成详情数量计算百分比，直接复用本地目录与结果文件，不再重复加载远端目录

## 当前可用能力

- 创建或更新工作区
- 导入工作区 `ZIP`
- 导出工作区 `ZIP`
- 导入断点 `JSON`
- 导出断点 `JSON`
- 合并两个同源工作区
- 回填 `db_config.py` 默认数据库配置
- 测试数据库连接
- 载入懂车帝原脚本默认配置
- 配置输出目录、并发线程、最大页数、显示浏览器、OCR、数据库同步、继续/重置策略
- 加载懂车帝品牌目录并保存品牌选择
- 按已选品牌加载车系目录并保存车系选择
- 一键勾选当前品牌下的全部车系，再保存为抓取范围
- 抓取所选车系概览数据并写入工作区
- 抓取详情数据，按 `max_workers` 并发执行，仍按 `sku_id` 逐条落盘并更新断点
- 在 GUI 中查看工作区摘要、运行日志和当前后台任务状态
- 在品牌/车系列表中查看层级进度反馈：
  - 品牌车系目录完成后品牌变黄
  - 车系概览完成后车系变黄
  - 车系详情完成后车系变绿
  - 品牌下全部已选车系详情完成后品牌变绿
- 在顶部查看当前数据源、并发线程、续采策略和浏览器模式徽章
- 在摘要卡片中查看工作区、抓取范围、当前任务和结果快照
- 在目录与抓取操作区勾选自动流程：
  - 保存车系后自动抓取概览
  - 概览完成后自动抓取详情
- 打开客户端时自动读取上一次工作区的品牌目录、车系目录、已选范围和断点进度
- 在品牌/车系列表中直接查看百分比进度，例如品牌已完成车系比例、车系详情完成比例

## 本次完成内容（M20）

- 在 [workspace.py](E:/Game/carInfoHandle/desktop_client/runtime/workspace.py) 中新增最近工作区记忆与最近工作区发现逻辑，支持记录上次打开的工作区根目录
- 在 [main_window.py](E:/Game/carInfoHandle/desktop_client/ui/main_window.py) 启动时自动尝试恢复上次工作区：
  - 读取 `task_config.json`
  - 读取 `task_scope.json`
  - 读取 `progress.json`
  - 读取本地 `brand_catalog.json` 与 `series_catalog.json`
- 恢复成功后，品牌目录、车系列表、已选品牌、已选车系和工作区摘要都会直接回填，不需要重新点击加载品牌和加载车系
- 在 [status.py](E:/Game/carInfoHandle/desktop_client/runtime/status.py) 中为品牌和车系新增百分比进度字段：
  - 品牌：按所选车系的详情完成情况计算总体百分比
  - 车系：按 `details / overviews` 计算详情完成百分比
- 在界面状态文案中追加百分比展示，例如：
  - `车系目录已完成 | 完成 12/40 | 30%`
  - `概览已完成 | 详情 25/80 | 31%`
- 在 [test_workspace.py](E:/Game/carInfoHandle/desktop_client/tests/test_workspace.py)、[test_status.py](E:/Game/carInfoHandle/desktop_client/tests/test_status.py) 和 [test_main_window.py](E:/Game/carInfoHandle/desktop_client/tests/test_main_window.py) 中补充最近工作区恢复与百分比进度测试

## 下一阶段建议

- 接入 OCR 阶段运行器，补齐桌面端完整闭环
- 为概览和详情抓取增加更细粒度的百分比进度
- 为工作区导入、合并、断点导入提供差异摘要
- 继续补充主窗口 GUI 级测试，覆盖更多按钮状态和工作区恢复场景

## 测试记录

| 时间 | 子项 | 命令 | 结果 |
| --- | --- | --- | --- |
| 2026-04-11 | M1 | 目录创建 | 通过 |
| 2026-04-11 | M2 | `python -m unittest desktop_client.tests.test_workspace` | 通过 |
| 2026-04-11 | M2 | `python -m py_compile desktop_client/models.py desktop_client/runtime/workspace.py` | 通过 |
| 2026-04-11 | M3 | `python -m unittest desktop_client.tests.test_db_runtime` | 通过 |
| 2026-04-11 | M3 | `python -m py_compile desktop_client/runtime/db_runtime.py` | 通过 |
| 2026-04-11 | M4 | `python -m unittest desktop_client.tests.test_form_mapping` | 通过 |
| 2026-04-11 | M4 | `python -m py_compile desktop_client/app.py desktop_client/ui/*.py` | 通过 |
| 2026-04-11 | M4 | `python -m desktop_client.app` | 通过，缺依赖时可正确提示 |
| 2026-04-11 | M5 | `python -m unittest desktop_client.tests.test_workspace desktop_client.tests.test_db_runtime desktop_client.tests.test_form_mapping` | 通过 |
| 2026-04-11 | M5 | `python -m py_compile desktop_client/...` | 通过 |
| 2026-04-11 | M6 | `python -m unittest desktop_client.tests.test_dongchedi_runner` | 通过 |
| 2026-04-11 | M6 | `python -m unittest desktop_client.tests.test_workspace desktop_client.tests.test_db_runtime desktop_client.tests.test_form_mapping desktop_client.tests.test_dongchedi_runner` | 通过 |
| 2026-04-11 | M6 | `python -m py_compile desktop_client/runtime/dongchedi_runner.py desktop_client/ui/main_window.py` | 通过 |
| 2026-04-11 | M7 | `python -m unittest desktop_client.tests.test_dongchedi_runner` | 通过 |
| 2026-04-11 | M7 | `python -m unittest desktop_client.tests.test_workspace desktop_client.tests.test_db_runtime desktop_client.tests.test_form_mapping desktop_client.tests.test_dongchedi_runner` | 通过 |
| 2026-04-11 | M7 | `python -m py_compile desktop_client/runtime/dongchedi_runner.py desktop_client/tests/test_dongchedi_runner.py` | 通过 |
| 2026-04-11 | M8 | `python -m unittest desktop_client.tests.test_status` | 通过 |
| 2026-04-11 | M8 | `python -m unittest desktop_client.tests.test_workspace desktop_client.tests.test_db_runtime desktop_client.tests.test_form_mapping desktop_client.tests.test_dongchedi_runner desktop_client.tests.test_status` | 通过 |
| 2026-04-11 | M8 | `python -m py_compile desktop_client/runtime/status.py desktop_client/ui/main_window.py` | 通过 |
| 2026-04-11 | M8 | `python -m desktop_client.app` | 通过，缺依赖时可正确提示 |
| 2026-04-11 | M9 | `python -m unittest desktop_client.tests.test_workspace` | 通过 |
| 2026-04-11 | M9 | `python -m unittest desktop_client.tests.test_workspace desktop_client.tests.test_db_runtime desktop_client.tests.test_form_mapping desktop_client.tests.test_dongchedi_runner desktop_client.tests.test_status` | 通过 |
| 2026-04-11 | M9 | `python -m py_compile desktop_client/runtime/workspace.py desktop_client/tests/test_workspace.py` | 通过 |
| 2026-04-11 | M10 | `python -m unittest desktop_client.tests.test_workspace desktop_client.tests.test_db_runtime desktop_client.tests.test_form_mapping desktop_client.tests.test_dongchedi_runner desktop_client.tests.test_status` | 通过 |
| 2026-04-11 | M10 | `python -m py_compile desktop_client/ui/main_window.py` | 通过 |
| 2026-04-11 | M10 | `python -m desktop_client.app` | 通过，缺依赖时可正确提示 |
| 2026-04-11 | M11 | `python -m unittest desktop_client.tests.test_dongchedi_runner` | 通过 |
| 2026-04-11 | M11 | `python -m unittest desktop_client.tests.test_workspace desktop_client.tests.test_db_runtime desktop_client.tests.test_form_mapping desktop_client.tests.test_dongchedi_runner desktop_client.tests.test_status` | 通过 |
| 2026-04-11 | M11 | `python -m py_compile desktop_client/runtime/dongchedi_runner.py desktop_client/ui/main_window.py` | 通过 |
| 2026-04-11 | M11 | `python -m desktop_client.app` | 通过，缺依赖时可正确提示 |
| 2026-04-11 | M12 | `python -m unittest desktop_client.tests.test_source_defaults desktop_client.tests.test_workspace desktop_client.tests.test_form_mapping` | 通过 |
| 2026-04-11 | M12 | `python -m unittest desktop_client.tests.test_workspace desktop_client.tests.test_db_runtime desktop_client.tests.test_form_mapping desktop_client.tests.test_dongchedi_runner desktop_client.tests.test_status desktop_client.tests.test_source_defaults` | 通过 |
| 2026-04-11 | M12 | `python -m py_compile desktop_client/runtime/source_defaults.py desktop_client/models.py desktop_client/runtime/workspace.py desktop_client/ui/form_mapping.py` | 通过 |
| 2026-04-11 | M13 | `E:/Game/carInfoHandle/.venv/Scripts/python.exe -m unittest desktop_client.tests.test_workspace desktop_client.tests.test_db_runtime desktop_client.tests.test_form_mapping desktop_client.tests.test_dongchedi_runner desktop_client.tests.test_status desktop_client.tests.test_source_defaults` | 通过，32 个测试全部通过 |
| 2026-04-11 | M13 | `E:/Game/carInfoHandle/.venv/Scripts/python.exe -m py_compile E:/Game/carInfoHandle/desktop_client/ui/main_window.py E:/Game/carInfoHandle/desktop_client/runtime/status.py E:/Game/carInfoHandle/desktop_client/runtime/dongchedi_runner.py E:/Game/carInfoHandle/desktop_client/runtime/workspace.py E:/Game/carInfoHandle/desktop_client/runtime/db_runtime.py E:/Game/carInfoHandle/desktop_client/runtime/source_defaults.py` | 通过 |
| 2026-04-11 | M13 | 启动 `E:/Game/carInfoHandle/.venv/Scripts/python.exe -m desktop_client.app` 并观察 5 秒 | 通过，进程成功拉起且启动期无报错 |
| 2026-04-11 | M14 | `E:/Game/carInfoHandle/.venv/Scripts/python.exe -m unittest desktop_client.tests.test_workspace desktop_client.tests.test_db_runtime desktop_client.tests.test_form_mapping desktop_client.tests.test_dongchedi_runner desktop_client.tests.test_status desktop_client.tests.test_source_defaults desktop_client.tests.test_main_window` | 通过，33 个测试全部通过 |
| 2026-04-11 | M14 | `E:/Game/carInfoHandle/.venv/Scripts/python.exe -m py_compile E:/Game/carInfoHandle/desktop_client/ui/main_window.py E:/Game/carInfoHandle/desktop_client/tests/test_main_window.py` | 通过 |
| 2026-04-11 | M14 | 启动 `E:/Game/carInfoHandle/.venv/Scripts/python.exe -m desktop_client.app` 并观察 5 秒 | 通过，进程成功拉起且启动期无报错 |
| 2026-04-11 | M15 | `E:/Game/carInfoHandle/.venv/Scripts/python.exe -m unittest desktop_client.tests.test_workspace desktop_client.tests.test_db_runtime desktop_client.tests.test_form_mapping desktop_client.tests.test_dongchedi_runner desktop_client.tests.test_status desktop_client.tests.test_source_defaults desktop_client.tests.test_main_window` | 通过，34 个测试全部通过 |
| 2026-04-11 | M15 | `E:/Game/carInfoHandle/.venv/Scripts/python.exe -m py_compile E:/Game/carInfoHandle/desktop_client/ui/main_window.py E:/Game/carInfoHandle/desktop_client/tests/test_main_window.py` | 通过 |
| 2026-04-11 | M15 | 启动 `E:/Game/carInfoHandle/.venv/Scripts/python.exe -m desktop_client.app` 并观察 5 秒 | 通过，进程成功拉起且启动期无报错 |
| 2026-04-11 | M16 | `E:/Game/carInfoHandle/.venv/Scripts/python.exe -m unittest desktop_client.tests.test_workspace desktop_client.tests.test_db_runtime desktop_client.tests.test_form_mapping desktop_client.tests.test_dongchedi_runner desktop_client.tests.test_status desktop_client.tests.test_source_defaults desktop_client.tests.test_main_window` | 通过，36 个测试全部通过 |
| 2026-04-11 | M16 | `E:/Game/carInfoHandle/.venv/Scripts/python.exe -m py_compile E:/Game/carInfoHandle/desktop_client/ui/main_window.py E:/Game/carInfoHandle/desktop_client/runtime/status.py E:/Game/carInfoHandle/desktop_client/runtime/dongchedi_runner.py E:/Game/carInfoHandle/desktop_client/tests/test_main_window.py E:/Game/carInfoHandle/desktop_client/tests/test_status.py` | 通过 |
| 2026-04-11 | M16 | 启动 `E:/Game/carInfoHandle/.venv/Scripts/python.exe -m desktop_client.app` 并观察 5 秒 | 通过，进程成功拉起且启动期无报错 |
| 2026-04-11 | M17 | `E:/Game/carInfoHandle/.venv/Scripts/python.exe -m unittest desktop_client.tests.test_workspace desktop_client.tests.test_db_runtime desktop_client.tests.test_form_mapping desktop_client.tests.test_dongchedi_runner desktop_client.tests.test_status desktop_client.tests.test_source_defaults desktop_client.tests.test_main_window` | 通过，38 个测试全部通过 |
| 2026-04-11 | M17 | `E:/Game/carInfoHandle/.venv/Scripts/python.exe -m py_compile E:/Game/carInfoHandle/desktop_client/ui/main_window.py E:/Game/carInfoHandle/desktop_client/runtime/status.py E:/Game/carInfoHandle/desktop_client/runtime/dongchedi_runner.py E:/Game/carInfoHandle/desktop_client/tests/test_main_window.py E:/Game/carInfoHandle/desktop_client/tests/test_status.py` | 通过 |
| 2026-04-11 | M17 | 启动 `E:/Game/carInfoHandle/.venv/Scripts/python.exe -m desktop_client.app` 并观察 5 秒 | 通过，进程成功拉起且启动期无报错 |
| 2026-04-11 | M18 | `E:/Game/carInfoHandle/.venv/Scripts/python.exe -m unittest desktop_client.tests.test_dongchedi_api desktop_client.tests.test_workspace desktop_client.tests.test_db_runtime desktop_client.tests.test_form_mapping desktop_client.tests.test_dongchedi_runner desktop_client.tests.test_status desktop_client.tests.test_source_defaults desktop_client.tests.test_main_window` | 通过，40 个测试全部通过 |
| 2026-04-11 | M18 | `E:/Game/carInfoHandle/.venv/Scripts/python.exe -m py_compile E:/Game/carInfoHandle/dongchedi_api.py E:/Game/carInfoHandle/desktop_client/ui/main_window.py E:/Game/carInfoHandle/desktop_client/tests/test_dongchedi_api.py E:/Game/carInfoHandle/desktop_client/tests/test_main_window.py` | 通过 |
| 2026-04-11 | M18 | 真实执行品牌目录拉取校验 `DongchediRunner.load_brand_catalog(...)` | 通过，成功返回 641 个品牌 |
| 2026-04-11 | M18 | 启动 `E:/Game/carInfoHandle/.venv/Scripts/python.exe -m desktop_client.app` 并观察 5 秒 | 通过，进程成功拉起且启动期无报错 |
| 2026-04-11 | M19 | `E:/Game/carInfoHandle/.venv/Scripts/python.exe -m unittest desktop_client.tests.test_main_window` | 通过，8 个测试全部通过 |
| 2026-04-11 | M19 | `E:/Game/carInfoHandle/.venv/Scripts/python.exe -m unittest desktop_client.tests.test_dongchedi_api desktop_client.tests.test_workspace desktop_client.tests.test_db_runtime desktop_client.tests.test_form_mapping desktop_client.tests.test_dongchedi_runner desktop_client.tests.test_status desktop_client.tests.test_source_defaults desktop_client.tests.test_main_window` | 通过，43 个测试全部通过 |
| 2026-04-11 | M19 | `E:/Game/carInfoHandle/.venv/Scripts/python.exe -m py_compile E:/Game/carInfoHandle/desktop_client/ui/main_window.py E:/Game/carInfoHandle/desktop_client/tests/test_main_window.py` | 通过 |
| 2026-04-11 | M19 | 启动 `E:/Game/carInfoHandle/.venv/Scripts/python.exe -m desktop_client.app` 并观察 5 秒 | 通过，进程成功拉起且启动期无报错 |
| 2026-04-13 | M20 | `E:/Game/carInfoHandle/.venv/Scripts/python.exe -m unittest desktop_client.tests.test_workspace desktop_client.tests.test_status desktop_client.tests.test_main_window` | 通过，20 个测试全部通过 |
| 2026-04-13 | M20 | `E:/Game/carInfoHandle/.venv/Scripts/python.exe -m unittest desktop_client.tests.test_dongchedi_api desktop_client.tests.test_workspace desktop_client.tests.test_db_runtime desktop_client.tests.test_form_mapping desktop_client.tests.test_dongchedi_runner desktop_client.tests.test_status desktop_client.tests.test_source_defaults desktop_client.tests.test_main_window` | 通过，45 个测试全部通过 |
| 2026-04-13 | M20 | `PYTHONPYCACHEPREFIX=E:/Game/carInfoHandle/.pycache_temp python -m py_compile desktop_client/runtime/workspace.py desktop_client/runtime/status.py desktop_client/ui/main_window.py desktop_client/tests/test_workspace.py desktop_client/tests/test_status.py desktop_client/tests/test_main_window.py` | 通过 |
| 2026-04-13 | M20 | 离屏创建 `MainWindow(default_workspace_root())` 并检查 `current_workspace` | 通过，自动恢复到 `E:/Game/carInfoHandle/client_output` |
| 2026-04-13 | M20 | 启动 `E:/Game/carInfoHandle/.venv/Scripts/python.exe -m desktop_client.app` 并观察 5 秒 | 通过，进程成功拉起且启动期无报错 |

## 本次完成内容（M21）

- 将工作区创建/更新、工作区导入导出、断点导入导出、工作区合并、品牌选择、车系选择、摘要刷新、启动恢复统一迁移到 `QThreadPool` 后台执行。
- 后台任务完成后统一构建工作区快照，包含 `workspace`、`summary`、`scope_progress`、`brand_catalog`、`series_catalog`，主线程只负责界面回填。
- 作用域进度计算改为后台刷新并缓存，运行时消息只做调度，避免主线程频繁读取大 JSON。
- 配置回填时通过 `QSignalBlocker` 阻断控件信号，避免恢复工作区时重复触发同步摘要计算。
- 品牌和车系列表回填增加 `QSignalBlocker` 与 `setUpdatesEnabled(False)`，降低大目录场景的界面抖动和选择事件风暴。
- 修复后台任务结束后“当前任务”停留在旧任务名称的问题，空闲态会正确恢复。

## M21 测试记录

| 时间 | 子项 | 命令 | 结果 |
| --- | --- | --- | --- |
| 2026-04-13 | M21 | `E:/Game/carInfoHandle/.venv/Scripts/python.exe -m unittest desktop_client.tests.test_main_window` | 通过，9 个测试全部通过 |
| 2026-04-13 | M21 | `E:/Game/carInfoHandle/.venv/Scripts/python.exe -m unittest desktop_client.tests.test_dongchedi_api desktop_client.tests.test_workspace desktop_client.tests.test_db_runtime desktop_client.tests.test_form_mapping desktop_client.tests.test_dongchedi_runner desktop_client.tests.test_status desktop_client.tests.test_source_defaults desktop_client.tests.test_main_window` | 通过，45 个测试全部通过 |
| 2026-04-13 | M21 | `PYTHONPYCACHEPREFIX=E:/Game/carInfoHandle/.pycache_temp E:/Game/carInfoHandle/.venv/Scripts/python.exe -m py_compile E:/Game/carInfoHandle/dongchedi_api.py E:/Game/carInfoHandle/desktop_client/ui/main_window.py E:/Game/carInfoHandle/desktop_client/runtime/status.py E:/Game/carInfoHandle/desktop_client/runtime/workspace.py E:/Game/carInfoHandle/desktop_client/runtime/dongchedi_runner.py E:/Game/carInfoHandle/desktop_client/tests/test_main_window.py` | 通过 |
| 2026-04-13 | M21 | 离屏运行 `MainWindow`，自动恢复 `E:/Game/carInfoHandle/client_output_demo_small`，执行“保存车系选择 -> 抓取概览” | 通过，概览 5 条，界面恢复空闲态，进度显示正常 |

## 变更记录

- 2026-04-11：创建桌面客户端任务文档、目录骨架和测试目录。
- 2026-04-11：完成工作区模型、断点导入导出、ZIP 工作区打包恢复及对应单元测试。
- 2026-04-11：完成运行时数据库配置注入、配置恢复和连通性测试能力。
- 2026-04-11：完成桌面端基础界面、任务表单映射和工作区操作入口。
- 2026-04-11：完成当前阶段全量回归校验并固化“先测试再记文档”流程。
- 2026-04-11：完成懂车帝品牌/车系目录运行器，支持目录加载、品牌选择、断点续拉车系。
- 2026-04-11：完成懂车帝概览运行器与详情逐条落盘运行器，支持 `sku_id` 级断点续跑。
- 2026-04-11：完成 GUI 概览/详情抓取入口和工作区状态摘要展示。
- 2026-04-11：完成跨工作区合并能力，支持结果去重和断点状态合并。
- 2026-04-11：完成 GUI 工作区合并入口，支持从 ZIP 导入并与当前任务合并。
- 2026-04-11：完成运行器事件回调和 GUI 日志面板，支持阶段日志与逐项落盘反馈。
- 2026-04-11：完成原脚本默认配置映射，接入输出目录、数据库默认值、显示浏览器和继续/重置策略。
- 2026-04-11：完成主窗口重构、品牌/车系目录多选、状态文案清理、品牌/车系切换结果清理和真实“继续已有进度”语义。
- 2026-04-11：新增品牌/车系全选与清空操作，支持选中品牌后一键勾选全部车系并保存。
- 2026-04-11：将长耗时操作移入后台线程，增加 loading 状态区，并在运行时显示当前正在处理的品牌或阶段。
- 2026-04-11：将后台执行统一切换到线程池，补齐品牌/车系层级颜色反馈，修正高频事件下的状态刷新，并恢复详情阶段按 `max_workers` 并发抓取。
- 2026-04-11：完成桌面客户端视觉设计系统重构，新增头部徽章、摘要卡片、按钮层级和控制台式反馈布局，并补充对应窗口级测试。
- 2026-04-11：强化懂车帝品牌页和车系页下载跳转重试逻辑，修复品牌目录偶发无法加载的问题，同时压缩顶部展示高度并提高日志区默认可视面积。
- 2026-04-11：新增自动概览与自动详情勾选，支持保存车系后自动继续概览，并在概览完成后自动衔接详情抓取。
- 2026-04-13：新增上次工作区自动恢复能力，启动时直接读取本地品牌目录、车系目录和断点进度，同时为品牌和车系列表增加百分比进度展示。
