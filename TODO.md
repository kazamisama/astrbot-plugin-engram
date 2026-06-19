# TODO / 待办候选

> 候选改进项，均为「已讨论、未实现」。动手前需确认范围与最小 diff。

## 1. 召回结果自动注入（可选）

**现状**：召回结果只通过 `recall_long_term_memory` function tool 暴露给 LLM，由 LLM 自行决定是否调用（`hippocampus/tools.py`、`handlers/init.py:_register_agent_tools`）。不自动注入，因此 LLM 不主动调时记忆用不上。

**目标**：参考 livingmemory，加一个可配置的「自动注入」路径，把召回结果（摘要 + 置信度）直接拼进 system prompt / 对话上下文，与现有 function-tool 路径并存。

**要点**：
- 新增配置开关（默认关，保持现有行为），放进 `_conf_schema.json` 的 `memory_settings` 分组 + `MemoryConfig` + `ConfigManager._FIELDS`。
- 注入方式可选（system prompt / 上下文），注入条数上限、是否随近期上下文一起注入。
- 监听 AstrBot 的 LLM 请求钩子（需确认 AstrBot 是否暴露 on_llm_request / 等价 hook）做注入。
- 注意 token 预算，避免上下文爆炸。

## 2. 硬回收（GC）条件改用「有效强度 / 上次访问时长」

**现状**：`HippocampalStore.gc_pass()`（`hippocampus/storage.py:290`）硬删条件为
`strength < floor` 且 `access_count == 0` 且 `够老`。
`access_count` 单调递增、永不衰减（`hippocampus/recall.py:13` touch 时 +1，仅对 top-k 生效）。
后果：只要历史上进过一次召回 top-k，`access_count` 永久 ≥1，永远无法被硬回收——只有「自创建起从未进过任何 top-k」的纯冷记忆才会被删。偏保守。

**目标**：让「曾被召回过但早已冷却」的旧记忆也能被回收，更贴近艾宾浩斯「长期不用就忘」。

**候选改法**：GC 条件从 `access_count == 0` 改为基于
- 衰减后的有效强度（已随 decay 降到 floor 以下），和/或
- 距 `last_accessed` 的时长超过阈值（如 N 天没再被召回）。
保留软忘记审计（`forgotten_at`），仍只硬删「弱 + 长期未访问 + 够老」。

**要点**：
- 改 `gc_pass()` 判据；新增阈值配置（默认值需保守，避免误删）。
- 同步 atom 层 `atom_lifecycle_manager.run_gc()` 是否要一致改。
- GC 自动循环目前默认关闭（`atom_gc_interval_seconds=0.0`），改判据不改变「默认不自动跑」的前提。
- 需补烟测：构造一条「曾召回、已冷却」的 engram，断言新判据下可被回收、未冷却的不被回收。