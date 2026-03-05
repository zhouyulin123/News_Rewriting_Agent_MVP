# News Rewriting Agent MVP

基于 LangGraph 的热点改写项目基础功能实现，用于把热点信息转换成口播文案。

## 输入模式

- `URL 模式`：抓取网页并抽取正文
- `文本模式`：直接给标题和正文，跳过抓取

## 节点命名（已对齐）

图中的业务节点名，已和 `services` 文件名一一对应：

- `提取HTML` -> `services/fetcher.py`
- `摘取HTML内容` -> `services/extractor.py`
- `内容清洗` -> `services/cleaner.py`
- `内容分类` -> `services/classifier.py`
- `重写新闻内容` -> `services/rewriter.py`
- `内容检验` -> `services/qa.py`
- `输出内容` -> `services/exporter.py`

说明：`route_input` 和 `prepare_text` 是编排控制节点，在 `agent.py` 内实现，不属于 services 文件。

## 流程图

```text
START
  -> route_input
      -> (url)  fetcher -> extractor -> cleaner
      -> (text) prepare_text ---------> cleaner
  -> classifier
  -> rewriter
  -> qa
  -> qa_decision (不通过则回到 rewriter，最多重写 N 次)
  -> exporter
  -> END
```

## 目录结构

```text
News_Rewriting_Agent/
├─ main.py
├─ requirements.txt
└─ news_agent/
   ├─ agent.py
   ├─ config.py
   ├─ models.py
   └─ services/
      ├─ __init__.py
      ├─ fetcher.py
      ├─ extractor.py
      ├─ cleaner.py
      ├─ classifier.py
      ├─ rewriter.py
      ├─ qa.py
      ├─ exporter.py
      └─ llm_client.py
```

## 安装

```bash
pip install -r requirements.txt
playwright install chromium
```

## 环境变量

```bash
set OPENAI_API_KEY=你的密钥
set OPENAI_BASE_URL=https://api.siliconflow.cn/v1
```

## 运行

### URL 模式

```bash
python main.py "https://example.com/news"
python main.py "https://example.com/news" --json
```

### 文本模式

```bash
python main.py --title "热点标题" --content-file ".\\hot_topic.txt"
python main.py --title "热点标题" --content-file ".\\hot_topic.txt" --reference-file ".\\ref1.txt" --reference-file ".\\ref2.txt" --style-file ".\\my_style.txt"
```

### 节点级流式日志

```bash
python main.py "https://example.com/news" --stream
python main.py --title "热点标题" --content-file ".\\hot_topic.txt" --stream
```

`--stream` 输出包含：
- 当前节点名（与图节点名一致）
- 新增日志（如 `start:cleaner` / `end:cleaner`）
- 新增错误（如有）
- 图执行完成摘要

## QA 回写重试机制

- `qa` 会给出未通过原因（例如字数过短/过长）。
- `qa_decision` 节点读取这些原因，决定是否回到 `rewriter`。
- 重写次数受 `RewriteConfig.max_rewrite_attempts` 限制，避免死循环。
