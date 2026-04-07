# Auto Scheduler Runner

自动调度器运行器，用于定期执行概率调度器。

## 功能

- 每 1 小时自动运行 `run_probabilistic_scheduler.py`
- 每 2 小时自动运行 `run_probabilistic_detective_scheduler.py`
- 支持自定义演员、循环次数等参数
- 后台持续运行，自动记录日志

## 文件说明

- `auto_scheduler_runner.py` - Python 调度器运行脚本
- `start_auto_scheduler.sh` - Ubuntu 启动脚本（支持后台运行）

## 使用方法

### 方法 1：直接运行 Python 脚本（前台运行）

```bash
cd /path/to/OnlineWorld/backend

# 使用默认设置
python3 scripts/auto_scheduler_runner.py

# 指定演员
python3 scripts/auto_scheduler_runner.py --actors aria,milo

# 指定每次运行的循环次数
python3 scripts/auto_scheduler_runner.py --cycles 3

# 查看所有选项
python3 scripts/auto_scheduler_runner.py --help
```

### 方法 2：使用 Shell 脚本（推荐，支持后台运行）

```bash
cd /path/to/OnlineWorld/backend

# 添加执行权限
chmod +x scripts/start_auto_scheduler.sh

# 启动调度器（后台运行）
./scripts/start_auto_scheduler.sh

# 指定演员启动
./scripts/start_auto_scheduler.sh --actors aria,milo

# 指定循环次数
./scripts/start_auto_scheduler.sh --cycles 3

# 查看运行状态
./scripts/start_auto_scheduler.sh --status

# 查看日志
./scripts/start_auto_scheduler.sh --logs

# 停止调度器
./scripts/start_auto_scheduler.sh --stop

# 查看帮助
./scripts/start_auto_scheduler.sh --help
```

## 命令行选项

### Python 脚本选项

- `--base-url BASE_URL` - API 服务器地址（默认：http://localhost:8000）
- `--actors ACTORS` - 演员列表，逗号分隔（默认：空，使用所有演员）
- `--cycles CYCLES` - 每次调度器执行的循环次数（默认：1）

### Shell 脚本选项

- `--base-url BASE_URL` - API 服务器地址
- `--actors ACTORS` - 演员列表
- `--cycles CYCLES` - 循环次数
- `--stop` - 停止运行中的调度器
- `--status` - 查看运行状态
- `--logs` - 实时查看日志
- `--help` - 显示帮助信息

## 日志文件

- PID 文件：`scripts/.auto_scheduler.pid`
- 日志文件：`scripts/.auto_scheduler.log`

## 调度时间表

| 调度器 | 频率 | 说明 |
|--------|------|------|
| run_probabilistic_scheduler | 每 1 小时 | 常规故事线调度 |
| run_probabilistic_detective_scheduler | 每 2 小时 | 侦探故事线调度 |

## 系统要求

- Python 3.8+
- Ubuntu/Linux（使用 Shell 脚本时）
- 项目依赖已安装

## 注意事项

1. 确保 API 服务器正在运行（默认端口 8000）
2. 首次运行前请确保已安装所有项目依赖
3. 建议使用 Shell 脚本后台运行，避免终端关闭后停止
4. 定期检查日志文件，确保调度器正常运行
5. 如需修改调度频率，请编辑 `auto_scheduler_runner.py` 中的以下变量：
   - `scheduler_interval = 3600` （常规调度器间隔，单位：秒）
   - `detective_scheduler_interval = 7200` （侦探调度器间隔，单位：秒）

## 示例输出

```
============================================================
Auto Scheduler Runner Started
============================================================
Base URL: http://localhost:8000
Actors: all
Cycles per run: 1
Schedule:
  - run_probabilistic_scheduler: every 1 hour
  - run_probabilistic_detective_scheduler: every 2 hours
============================================================

============================================================
[2026-03-13T10:00:00+00:00] Running: run_probabilistic_scheduler.py
Command: python3 /path/to/backend/scripts/run_probabilistic_scheduler.py --cycles 1
============================================================

[SUCCESS] run_probabilistic_scheduler.py completed successfully

[INFO] Next regular scheduler run in 60.0 minutes
```

## 故障排除

### 调度器无法启动

1. 检查 Python 版本：`python3 --version`
2. 检查依赖是否安装：`pip3 install -r requirements.txt`
3. 检查 API 服务器是否运行：`curl http://localhost:8000`

### 调度器频繁失败

1. 查看日志文件：`./scripts/start_auto_scheduler.sh --logs`
2. 检查 API 服务器日志
3. 减少循环次数或调整调度频率

### 停止调度器

如果 Shell 脚本无法正常停止，可以手动终止：

```bash
# 查找进程
ps aux | grep auto_scheduler_runner

# 终止进程
kill <PID>

# 或删除 PID 文件
rm scripts/.auto_scheduler.pid
```
