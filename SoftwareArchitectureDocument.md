# 神马视频转换 — 技术架构文档

## 概述
- 桌面应用：Python + PySide6 构建 GUI
- 视频处理：FFmpeg 子进程执行
- 并发模型：Qt 原生 QThreadPool + QRunnable
- 打包分发：PyInstaller 单文件 EXE，携带 ffmpeg.exe 与 icon.ico

## 模块划分
- GUI 与控件：[gui.py](file:///d:/trea-ai/gui.py)
  - MainWindow：主界面与布局初始化（文件区、全局配置区、任务区、动作区）
  - FileTableWidget：文件列表（自定义交互：拖拽、双击添加、Alt+左键快速打开、右键菜单）
  - TaskTableWidget：任务列表（右键双击打开输出目录、滚动跟随）
  - 自定义单元格控件：
    - FormatCellWidget（输出格式）
    - QualityCellWidget（压缩质量）
    - RotationCellWidget（视频旋转）
    - TrimCellWidget（剪切）
    - StabilizeCellWidget（增稳）
- 业务主控：[main.py](file:///d:/trea-ai/main.py)
  - ShenmaConverter：主控制器，连接信号、维护文件数据模型、生成任务、更新任务表、帮助对话框
  - 全局配置同步：sync_global_* 将全局设置批量写入列表行控件
  - 任务生成：start_conversion 直接读取每行控件状态，避免缓存不一致
- 任务执行与调度：[worker.py](file:///d:/trea-ai/worker.py)
  - TranscodeTask：任务数据模型（输入、输出、质量、旋转、剪切、增稳、编码参数）
  - Worker（QRunnable）：构建并运行 FFmpeg 命令、解析进度、清理临时文件
  - WorkerSignals：progress/status/finished/error/log 等信号供主界面更新
  - Scheduler：QThreadPool 并发调度、最大线程数控制、活跃 Worker 管理、取消逻辑
- 资源与路径：[utils.py](file:///d:/trea-ai/utils.py)
  - get_base_path：兼容 PyInstaller 的 _MEIPASS 与开发目录
  - get_ffmpeg_path：优先使用随包 ffmpeg.exe，否则退回系统 PATH
- 打包脚本：[build_exe.py](file:///d:/trea-ai/build_exe.py)
  - PyInstaller 配置：--onefile、--windowed、--icon、--add-data、--add-binary
  - 构建后重命名 EXE（附加时间戳）以避免 Windows 图标缓存

## 关键数据流
1) 添加文件
- 读取当前全局配置 → 作为新文件的默认设置
- 渲染行控件（格式、质量、旋转、剪切、增稳）
2) 全局配置同步
- 用户修改全局控件 → 触发 sync_global_* → 批量刷新所有行控件
3) 开始转换
- 逐行读取控件状态（格式/质量/旋转/剪切/增稳）
- 质量到编码参数映射（CRF/preset）与文件名后缀映射
- 生成 TranscodeTask 列表并提交到 Scheduler
4) 执行与反馈
- Worker 启动 FFmpeg 子进程；发射进度与状态信号
- 主界面任务表更新；完成/失败后 UI 复位；清理临时 .trf

## 并发模型与控制
- QThreadPool.setMaxThreadCount(n)：由“同时任务数”滑块控制（范围 1-15）
- Scheduler.active_workers：记录当前运行中的 Worker，支持取消全部
- 暂停/继续：通过 psutil 对子进程进行 suspend/resume（仅对运行中有效）

## 视频处理实现细节
- 增稳（两阶段）
  - 分析：vidstabdetect 生成 trf（路径中冒号转义）
  - 应用：vidstabtransform（smoothing=增稳等级）
  - 等级范围：0 关闭，1-35；建议 <30；处理时间显著增加
- 旋转
  - 左 90°：transpose=2；右 90°：transpose=1；180°：两次 transpose
- 剪切
  - 输入前 -ss（更快）；输出 -t 控制持续时间
  - “倒数第 n 秒”需获取总时长：解析 ffmpeg -i 的 stderr 中 Duration
- 编解码与质量映射
  - 容器：MP4/MKV；视频编码：libx264；音频编码：aac
  - 预设与 CRF：
    - Lossless：CRF=0，preset=ultrafast
    - HD：CRF=18，preset=fast
    - Balanced：CRF=23，preset=medium
    - Compact：CRF=28，preset=slow

## UI 同步策略
- 全局控件变化 → 触发 sync_global_formats/qualities/rotation/trim/stabilization
- 新增文件 → 继承 get_current_global_config 作为初始值
- 执行时 → 直接读取 cellWidget 的 isChecked()/group.checkedId()/文本值，避免数据模型缓存与 UI 脱节

## 文件命名与输出路径
- 输出名：原文件名_质量后缀.格式（Lossless/HD/Balanced/Compact）
- 目录：同源或自定义；自定义需有效且可写

## 错误处理与健壮性
- 任务失败 → 状态置为“转码失败”，在任务行 ToolTip 显示错误信息
- 清空任务列表前校验：运行中或存在活跃 Worker 时禁止清空
- 子进程输出解析进度时容错处理（时间解析失败不崩溃）

## 打包与运行时路径
- 资源解析：get_base_path 兼容 PyInstaller 的运行环境
- FFmpeg 优先使用随包 ffmpeg.exe（--add-binary ffmpeg.exe;.）
- 图标：--icon icon.ico 与 --add-data icon.ico;. 用于 EXE 图标与窗口图标
- 构建后：EXE 重命名加时间戳，避免图标缓存

## 代码位置参考
- 主控制器与任务生成：[main.py](file:///d:/trea-ai/main.py#L439-L540)
- 帮助对话框（“软件快捷使用说明”）：[main.py](file:///d:/trea-ai/main.py#L90-L103)
- 自定义单元格控件与界面布局：[gui.py](file:///d:/trea-ai/gui.py#L301-L497)
- 任务模型与执行流程：[worker.py](file:///d:/trea-ai/worker.py#L16-L190)
- 线程池与调度：[worker.py](file:///d:/trea-ai/worker.py#L257-L299)
- 路径解析与 FFmpeg 定位：[utils.py](file:///d:/trea-ai/utils.py)
- 打包脚本与构建流程：[build_exe.py](file:///d:/trea-ai/build_exe.py#L47-L85)

## 约束与配置
- 同时任务数范围：1-15（UI 标签已标识）
- 增稳等级范围：0-35（UI 提示已标识，建议 <30）

## 未来优化方向
- 更细粒度的队列与暂停策略；避免仅对运行中进程生效
- GPU 编码支持（如 NVENC、QSV）与多编码器拓展
- 进度与剩余时间估算；错误日志收集与导出
- 配置持久化、国际化、多语言帮助文档

