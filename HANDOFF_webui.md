# 工作交接笔记 — WebUI 入口 + 配置中文化 + LLM/embedding 走 AstrBot

> 本轮任务：①WebUI 在 AstrBot 找不到入口 ②配置项中文 ③LLM/embedding 调 AstrBot 接口 ④参考 livingmemory
> 调查证据来源：AstrBot 安装于 C:\application\AstrBot\backend\app\astrbot（源码）；参考插件 livingmemory 在 .astrbot/data/plugins/

## 已确认事实（核心机制）

### A. WebUI 页面入口机制（最大未知 → 已查清）
- AstrBot Dashboard 自动扫描 `<插件目录>/pages/<页面名>/index.html`（文件系统约定，**不需要 metadata.pages 声明**）。
  证据：dashboard/routes/plugin.py `_discover_plugin_pages` 遍历 `pages/` 子目录，含 `index.html` 即登记为一个 Page。
  常量：`_PLUGIN_PAGE_ROOT_DIR_NAME="pages"`，`_PLUGIN_PAGE_ENTRY_FILE_NAME="index.html"`。
- livingmemory 之所以有侧边栏入口 = 它有 `pages/dashboard/index.html`。**我们仓库没有 pages/ 目录 → 没有入口。这就是根因。**
- 页面内容经 `/api/plugin/page/content/<plugin>/<page>/...` 在 iframe 中加载；AstrBot 注入桥 SDK `window.AstrBotPluginPage`（dashboard/plugin_page_bridge.js）。
  前端通过 `bridge.apiGet("page/xxx", params)` / `apiPost("page/xxx", body)` 调后端，桥自动加 `/<plugin_name>/` 前缀。

### B. 后端 web api 注册（已有，但有两个 BUG）
- `context.register_web_api(route, view_handler, methods, desc)` —— 4 参签名，已确认。
- 路由实际调用：server.py `srv_plug_route` → `await view_handler(*args, **path_values)`。
  **关键**：只传 path 变量，**不传 query/body**！handler 必须是 **async** 且自己从 `quart.request.args/get_json()` 读参数。
- BUG1：main.py 定义了 `_register_official_page_api_if_available()` 但 **__init__ 里从未调用** → 后端 API 根本没注册。
- BUG2：page_api.py 的 register 用 `lambda actor_id="",k=50: handler(...)` 同步 lambda。AstrBot `await` 它 → await 一个 dict 直接 TypeError；且 query 参数永远收不到。
  → 必须改成 async handler + 从 request 读参（参照 livingmemory page_api_modules/*_handler.py 用 `request.args`）。

### C. LLM/embedding 走 AstrBot（大部分已具备）
- handlers/init.py `_install_bridges()` 已把 astrmock 注册：
  - LLM: `context.get_using_provider()` → `provider.text_chat(system_prompt=, prompt=)`
  - embedding: `emb_bridge_for_context()`（handlers/recall.py，探测 `get_using_embedding_provider()` / `get_using_provider()` 的 get_embedding/embed/encode）
- AstrBot 真实 API（C:\application\AstrBot\...\core\star\context.py）：
  - `get_using_provider(umo=None)` 取当前对话 LLM
  - `get_provider_by_id(provider_id)` 按 ID 取（LLM 或 embedding 都行，返回类型含 EmbeddingProvider）
  - **没有** `get_using_embedding_provider`；embedding 取法应为 `get_provider_by_id(id)` 或 `get_all_embedding_providers()`
  - EmbeddingProvider 抽象方法是 `async get_embedding(text)`（不是 embed/encode）
- 缺口：①默认 `embedding_name="hash"` `llm_name="rule"`（mock），用户拿不到真实模型；应让默认走 astrmock。
  ②livingmemory 范式：加 `embedding_provider_id`/`llm_provider_id` 配置项（留空=用 AstrBot 默认），hint 提示「AstrBot 后台 → 服务提供商 ID」。
  ③emb_bridge_for_context 探测的方法名 get_embedding 命中（OK），但优先 `get_using_embedding_provider` 不存在 → 应改用 provider_id / get_all_embedding_providers。

### D. 配置中文化
- `_conf_schema.json` 当前全英文 description。改中文 description + 加 hint（livingmemory 范式）。
- ConfigManager 只认 14 字段；新增 embedding_provider_id/llm_provider_id 需在 config.py(MemoryConfig)+config_manager.py(_FieldSpec) 同步，否则被静默丢弃。

## 待办落地
1. 建 `pages/dashboard/index.html`(+css/js)：调 bridge.apiGet("page/health"/"page/stats"/...)，展示 stats/记忆列表/召回测试/备份。
2. main.py __init__ 末尾调用 `self._register_official_page_api_if_available()`。
3. page_api.py：lambda → async def，从 quart.request 读参；handler 内部签名保持不变（仍可同步返回 dict，由 async wrapper await/直接 return）。
4. _conf_schema.json 中文化 + 加 embedding_provider_id/llm_provider_id。
5. config.py + config_manager.py 加这两个字段；init.py 用 provider_id 取 provider。
6. 烟测分批 ALL PASS + 包导入模拟 OK。提交推送，四象限交付。

## 工具约束（沿用上一轮）
- apply_patch 不可用；编辑用 .NET ReadAllText/WriteAllText + UTF8(no BOM)，绝对路径，CRLF 保持。
- 编辑后 python ast.parse 校验。烟测分两批跑 timeout 60s。
- git push 用 `git push origin HEAD:main`（stderr 染红但成功）。