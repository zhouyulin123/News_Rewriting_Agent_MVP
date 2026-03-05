# 新闻写作 Agent 方案（面向口播视频脚本）

## 0. 目标与边界

### 目标
实现一个“新闻写作 Agent”，输入为 **URL（或URL列表）+ 示例格式/模板**，输出为适用于 **口播视频** 的新闻稿（结构化、可控风格、可复用）。

### 非目标（建议明确）
- 不做“自动发布/自动配音/自动剪辑”闭环（可预留接口）。
- 不做“全网舆情监测”级别规模（可扩展到订阅源/定时抓取）。

### 核心约束
- 版权与合规：输出为“改写/二次创作”，避免逐句复刻；保留来源信息用于追溯。
- 可控性：可配置主题分类体系、稿件结构、口播语气、长度、敏感词策略。
- 稳定性：面对动态站点、反爬、广告/杂志/推荐流等噪声，尽可能稳健提取正文。

---

## 1. 总体架构（Agent 视角）

### 1.1 组件分层
- **Orchestrator（编排层 / Agent）**
  - 任务规划：抓取 → 解析 → 清洗 → 主题分类 → 结构化要点 → 口播改写 → 质检 → 输出
- **Fetch & Render（采集渲染层）**
  - 静态抓取（HTTP）
  - 动态渲染（Playwright）
  - 反爬与容错（重试、代理、限速、UA轮换）
- **Content Extraction（正文提取层）**
  - trafilatura / readability-lxml / newspaper3k（备选）
  - DOM密度/规则增强
- **Cleaning & Normalization（清洗归一层）**
  - 规则清洗 + 统计/模型辅助去噪
  - 标题/时间/作者/来源抽取
- **Topic & Metadata（主题与元信息层）**
  - 主题分类（体育/科技/国际/财经/娱乐/社会/本地…）
  - 实体抽取（人物/组织/地点/事件）可选
- **Rewrite & Script (LLM)（改写与口播脚本层）**
  - 基于示例/模板生成口播稿
  - 事实一致性校验（轻量自检）
- **QA & Compliance（质检合规层）**
  - 重复率/相似度、敏感词、免责声明、引用规范
- **Storage & Observability（存储与可观测性）**
  - 原文、清洗后正文、结构化要点、最终稿、日志与评估指标

### 1.2 数据流（推荐）
1) URL → 抓取HTML / 渲染后HTML
2) 提取正文（title, publish_time, body, images?）
3) 清洗去噪（杂志信息/推荐/广告/导航/页脚）
4) 主题分类 + 关键信息抽取（5W1H / 要点）
5) 按示例模板改写成口播稿（可多版本）
6) 质检（事实一致性/格式/敏感词/长度）
7) 输出（Markdown/JSON，便于下游做TTS、分镜）

---

## 2. 子任务拆解与技术方案

## 2.1 URL 内容获取：静态 vs 动态判断

### 2.1.1 判断策略（建议多信号）
**快速探测（HEAD/GET）**
- `content-type` 是否为 `text/html`
- 初始HTML长度、是否包含大量 `script`，正文区域是否为空
- 是否存在典型 CSR 标识：`__NEXT_DATA__`（Next.js）、`nuxt`, `data-reactroot`、`id="app"` 且正文为空等

**DOM正文可得性评分**
- 用 trafilatura/readability 对原始HTML尝试提取：若正文长度 < 阈值（如 < 400 chars）或置信度低，则判定可能需要渲染

**网络请求特征（可选增强）**
- Playwright 记录 XHR/fetch：若存在明显的 `article/detail?id=` JSON 接口，可走“直连API”替代渲染（更稳更快）

### 2.1.2 抓取策略（分层回退）
- Level 1：`httpx`/`aiohttp` 异步抓取静态HTML → trafilatura 抽取
- Level 2：如果失败/正文过短 → `async_playwright` 渲染（等待 `networkidle` 或特定 selector）→ 抽取
- Level 3：若站点有JSON接口 → 解析接口并提取字段（优先，减少噪声）
- Level 4：极端情况：截图+OCR（不推荐，成本高，最后手段）

### 2.1.3 工程细节（必须）
- 并发控制：async semaphore（例如每域名 2~4 并发）
- 重试策略：指数退避 + 状态码白名单（429/5xx）
- 缓存：URL→HTML/正文缓存（避免重复抓取）
- 代理/UA：配置化（按域名开关）
- 失败可观测：错误分类（DNS/超时/403/解析失败/正文为空）

---

## 2.2 正文提取与去噪清洗（重点）

### 2.2.1 正文提取（推荐组合）
- **trafilatura**：新闻正文提取强，支持 metadata 提取
- 备选：readability-lxml / goose3 / newspaper3k（按站点差异做 fallback）

策略：
- 先 trafilatura（含 title/date/author）
- 若正文结构异常或提取为空 → readability-lxml
- 仍失败 → Playwright 渲染后再 trafilatura/readability

### 2.2.2 “杂志信息/多余信息”去除方案（你提到的重点）
建议采用 **“规则 + 结构 + 轻量模型”** 三段式，保证稳定：

**A. 规则清洗（强制）**
- 删除常见噪声段落模式（正则/关键词）
  - “更多精彩内容/订阅/广告/责任编辑/版权声明/推荐阅读/延伸阅读/点击这里/免责声明”
- 删除短段落堆（< 10字、纯符号、链接堆）
- 删除“图片说明/图集入口/相关阅读列表”块

**B. 结构清洗（强制）**
- DOM 层面去除：`nav, footer, aside, form, button, iframe` 等
- 链接密度阈值：`link_text_len / total_text_len` 高的块倾向为推荐区
- 段落密度：正文通常是“长段落连续”，推荐区是“短句+大量链接”

**C. 轻量模型辅助（可选但强烈建议）**
- 训练或少量标注一个“段落是否正文”的二分类器（fastText/轻量BERT均可）
  - 特征：段长、标点密度、链接密度、位置、关键词、语言模型困惑度等
- 价值：对“杂志式排版/推荐流穿插”更稳

输出结构建议：
```json
{
  "url": "...",
  "title": "...",
  "publish_time": "...",
  "source": "...",
  "clean_text": "...",
  "paragraphs": [
    {"text": "...", "is_main": true, "score": 0.93},
    ...
  ]
}

2.3 主题识别（体育/科技/国际…）
2.3.1 分类体系

建议先定义一套可配置 taxonomy（后期可扩展多标签）：

体育、科技、国际、财经、娱乐、社会、教育、健康、本地、军事（可选）

2.3.2 技术实现（两级）

Level 1（快速稳定）：Embedding + 近邻分类

为每个主题准备 20~100 条“代表性样本文本”（内部可持续补充）

计算文章 embedding，与主题样本库做相似度，取 top1/topk 做主题

Level 2（更准）：LLM 分类（带约束输出）

输入：标题 + 摘要/要点（避免整篇过长）

输出：{"topic": "...", "confidence": 0-1, "tags": [...]}

建议采用“Embedding 先验 + LLM 复核”：

embedding 给出候选 top3

LLM 在候选中选择，降低跑偏概率

2.4 结构化要点抽取（为改写服务）

为减少幻觉、提升可控性，改写前先做“事实要点提炼”。

2.4.1 要点格式（建议）

事件一句话：发生了什么

5W1H：谁/何时/何地/什么/为什么/如何

关键数字：时间、数量、金额、比分、排名等

引用/观点：如果原文有引语，提取“说话人 + 核心观点”（可选）

风险点：不确定表述、推测性语言标记

输出示例：

{
  "summary": "...",
  "who": ["..."],
  "when": "...",
  "where": "...",
  "what": "...",
  "why": "...",
  "how": "...",
  "numbers": ["..."],
  "quotes": [{"speaker":"...", "quote":"..."}]
}

实现方式：

LLM 抽取（强约束 JSON schema）

也可用规则补充：时间表达式识别（dateparser/regex）

2.5 基于示例与格式的口播改写（核心产出）
2.5.1 口播稿“模板化输出”

建议统一为可复用结构（可按主题自动选择模板）：

通用口播模板

开场一句（抓注意力）

事件概述（20~40字）

关键事实 3 点（每点 1~2 句）

背景补充（1 段，解释因果/影响）

收尾（总结 + 引导关注/互动）

可配置参数：

时长：30s / 60s / 90s（对应字数区间）

语气：新闻播报 / 轻松口播 / 专业解读

禁用项：夸张标题党、过度情绪化词汇

必含项：来源标注、日期、免责声明（如需要）

2.5.2 Prompt / 调用策略（建议两段式）

Step A：给 LLM 输入“要点 + 示例模板”，生成初稿

Step B：自检与修订（LLM 作为校对员）

检查：是否遗漏关键信息、是否有新增事实、是否符合长度、是否符合格式

输出：最终稿 + 变更说明（内部日志用）

输出格式建议（便于视频制作）：

script_text：完整口播稿

segments：分句/分段（便于字幕与分镜）

title：视频标题（可选）

hashtags/tags：主题标签（可选）

3. Agent 框架与技术选型
3.1 推荐技术栈（Python）

Web 抓取：httpx（async） / aiohttp

动态渲染：playwright（async_playwright）

正文提取：trafilatura（主） + readability-lxml（备）

HTML解析：lxml / beautifulsoup4

清洗：自研规则 + 结构特征 +（可选）fastText/BERT 段落分类

主题分类：embedding（bge-m3 / text-embedding-*）+ LLM 复核

LLM 编排：LangGraph（推荐）或轻量自研 state machine

存储：

元数据与结果：PostgreSQL/MySQL

原始HTML与日志：对象存储（S3/MinIO）

向量库：Milvus/FAISS（主题样本、示例检索用）

服务化：FastAPI + Celery/RQ（异步任务）或纯 async worker

监控：Prometheus + Grafana（可选），Sentry（异常）

3.2 LangGraph（推荐）状态机示意

Node: Fetch

Node: DetectDynamic

Node: RenderIfNeeded

Node: ExtractMainText

Node: CleanText

Node: TopicClassify

Node: KeyPointsExtract

Node: RewriteScript

Node: QACompliance

Node: Export

每个 node 输出统一 state（JSON），便于回放与调试。