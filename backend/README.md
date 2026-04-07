# Backend

`backend/` 负责 `OnlineWorld` 的服务端能力，目标是为前端、多网站模拟系统和后续 AI 叙事引擎提供稳定基础。

## 当前技术方向

- `FastAPI`：主要 Web API 框架
- `Uvicorn`：本地开发服务器
- 分层结构：`API -> Services -> Domain -> Repositories -> Infrastructure`

## 设计原则

- 先创建事实，再生成文本
- 路由层不直接操作数据库
- `LLM` 不直接写世界状态
- 所有跨站行为都形成事件链
- 目录按职责拆分，避免单目录堆叠 `Python` 文件

## 目录结构

```text
backend/
├─ app/
│  ├─ api/                  # 对前端暴露的 HTTP API
│  ├─ consistency/          # 一致性校验
│  ├─ core/                 # 配置与应用级基础设施
│  ├─ domain/               # 核心实体与事件模型
│  ├─ infrastructure/       # 数据库、LLM 等外部依赖适配
│  ├─ repositories/         # 仓储抽象与最小实现
│  ├─ schemas/              # API 请求/响应模型
│  ├─ services/             # 业务用例编排
│  ├─ simulation/           # 世界推进与内容草稿生成
│  ├─ container.py          # 依赖装配
│  └─ main.py               # FastAPI 入口
├─ tests/
│  └─ smoke_check.py        # 最小导入验证
└─ requirements.txt
```

## 已提供的最小能力

- `GET /api/v1/health`：健康检查
- `GET /api/v1/world/summary`：世界摘要示例
- `POST /api/v1/world/demo-post`：演示“事实先行、文本后生成”的帖子创建流程
- `POST /api/v1/ai/scheduler/run`：AI 调度执行入口
- `POST /api/v1/ai/execute`：手动执行单个 capability

## 通用五步骤链

当前 AI 驱动的写操作开始统一走以下链路：

1. **调度步骤**：调度器先产出结构化 `StoryStep`
2. **事实执行**：先在数据库中创建草稿事实或保留对象 ID
3. **内容生成**：再调用结构化内容生成器补全文本字段
4. **一致性校验**：检查必填字段、未解析引用、提示词残留等问题
5. **正式发布**：只有校验通过后才写入公开内容表

当前论坛能力已经作为首个站点接入这套通用链，后续商店、私信应复用同样协议，而不是各自写一套流程。

`demo-post` 的行为链：

1. 创建行为意图
2. 执行业务动作，例如生成文件资源
3. 将事实整理为结构化数据
4. 调用 `LLM` 适配器生成文字草稿
5. 进行一致性校验
6. 返回可发布内容与事件链

## 本地启动

在 Windows PowerShell 中：

```powershell
cd D:\Else\OnlineWorld\backend
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

启动后可访问：

- `http://127.0.0.1:8000/api/v1/health`
- `http://127.0.0.1:8000/docs`

## 最小验证

```powershell
cd D:\Else\OnlineWorld\backend
.\venv\Scripts\python.exe tests\smoke_check.py
```

## 下一步建议

1. 让商店、私信按同一五步骤协议接入
2. 为事实草稿、发布结果、失败原因增加专门审计表
3. 将结构化内容生成器扩展到图片/附件描述等多模态占位
4. 为五步骤链补充端到端自动化测试
