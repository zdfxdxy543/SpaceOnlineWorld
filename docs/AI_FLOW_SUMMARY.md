# AI 内容生成链路总结

本项目当前的 AI 内容生成，核心依赖的是 SiliconFlow 兼容的聊天接口，统一走 `POST /chat/completions`，由后端在容器层装配后注入到具体的生成服务里。

## 主要调用链

1. `backend/app/core/config.py` 读取 `LLM_PROVIDER`、`LLM_MODEL`、`SILICONFLOW_API_KEY`、`SILICONFLOW_BASE_URL` 等配置。
2. `backend/app/container.py` 创建 `SiliconFlowLLMClient`、`SiliconFlowStructuredContentGenerator`、`SiliconFlowStoryPlanner` 和 `GenerationService`。
3. `backend/app/infrastructure/llm/siliconflow_client.py` 负责普通文本生成，给模型发送 system/user 消息，直接读取 `choices[0].message.content`。
4. `backend/app/infrastructure/llm/structured_content.py` 负责结构化内容生成，要求模型返回 JSON，再解析成 `GeneratedContent`。
5. `backend/app/infrastructure/llm/siliconflow_planner.py` 负责故事调度规划，要求模型输出 JSON 步骤链，再转成 `StoryPlan`。
6. `backend/app/services/generation_service.py` 先调用 LLM 生成帖子草稿，再交给一致性检查器校验，最后组装事件链。

## 目前的生成策略

- 先整理事实，再让模型写内容，避免模型直接改写世界状态。
- 文本生成前会放入结构化事实、资源引用、主题和站点上下文。
- 生成结果会做一致性检查，重点看必填事实、资源编号、引用是否缺失。
- 调度器层会要求模型输出可执行步骤，并尽量形成 discovery -> investigation -> outcome 的链路。

## 关键接口

- `SiliconFlowLLMClient.generate_forum_post()`：生成论坛帖子正文。
- `SiliconFlowStructuredContentGenerator.generate()`：生成论坛、新闻、网盘、主站页面等结构化内容。
- `SiliconFlowStoryPlanner.build_story_plan()`：生成跨站点的故事执行计划。

## 这次清理的范围

- 已移除前端页面源码，保留前端工程壳，方便后续重建。
- 已移除后端的搜索和学术入口，它们不属于 AI 生成主链路。
- 后端其余 AI 相关模块暂时保留，用于作为新一轮开发的参考骨架。