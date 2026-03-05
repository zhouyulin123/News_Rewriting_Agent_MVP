from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import os
os.environ["OPENAI_API_KEY"] = ""
os.environ["OPENAI_BASE_URL"] = ""

@dataclass
class FetchConfig:
    timeout_seconds: int = 30
    render_timeout_seconds: int = 60
    max_retries: int = 2
    min_content_length: int = 400
    enable_http_fetch: bool = True
    enable_playwright: bool = True
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/133.0.0.0 Safari/537.36"
    )


@dataclass
class CleanConfig:
    min_paragraph_length: int = 10
    noise_keywords: list[str] = field(
        default_factory=lambda: [
            "责任编辑",
            "免责声明",
            "相关阅读",
            "延伸阅读",
            "推荐阅读",
            "点击查看",
            "点击这里",
            "更多精彩内容",
            "版权声明",
            "广告",
            "订阅",
            "扫码",
            "本文来自",
        ]
    )


@dataclass
class LLMConfig:
    enabled: bool = True
    model: str = ""
    base_url: str = ""
    api_key_env: str = "OPENAI_API_KEY"
    base_url_env: str = "OPENAI_BASE_URL"
    temperature: float = 0.4
    max_retries: int = 2
    timeout_seconds: int = 120


@dataclass
class RewriteConfig:
    tone: str = "口语化新闻解读"
    min_chars: int = 300
    max_chars: int = 600
    max_rewrite_attempts: int = 2
    include_source_line: bool = True
    include_disclaimer: bool = False


@dataclass
class PromptConfig:
    topic_taxonomy: list[str] = field(
        default_factory=lambda: [
            "体育",
            "科技",
            "国际",
            "财经",
            "娱乐",
            "社会",
            "教育",
            "健康",
            "本地",
            "军事",
            "电商",
            "汽车",
            "家居",
            "数码",
        ]
    )
    analysis_system_prompt: str = (
        "你是热点信息解析助手。"
        "你需要从标题和正文中提炼适合短视频口播写作的结构化信息。"
        "只输出 JSON，不要输出解释，不要输出 markdown。"
    )
    rewrite_system_prompt: str = (
        "你是中文短视频口播文案写手，擅长把热点信息改写成自然、口语化、可直接播报的稿子。"
        "请遵守："
        "1) 明确主题，聚焦商品/品牌/消费话题；"
        "2) 开场有悬念；"
        "3) 中间讲清核心信息；"
        "4) 自然延伸相关 query；"
        "5) 字数控制在 300~500；"
        "6) 语气口语化；"
        "7) 不编造事实；"
        "8) 只输出最终文案。"
    )
    built_in_examples: list[str] = field(
        default_factory=lambda: [
            "示例：苹果15充电口大揭秘：C口时代真的来了。苹果15的充电口终于换成了USB-C，这个改变等了整整十一年。从iPhone5的Lightning到现在的USB-C，苹果这次是真的跟上了时代。但你知道吗，这个C口不仅仅是充电那么简单。', '首先，这个C口支持20瓦有线充电，和上一代保持一致。虽然充电速度没有提升，但出门终于不用带两根线了。实测用第三方C口线也能正常充电，功率和原装线一样。', '更厉害的是Pro版的C口，传输速度是标准版的20倍。拷贝一个17GB的视频，15Pro只要1分5秒，而标准版需要7分45秒。对于经常传输大文件的用户来说，这个提升太实用了。', '这个C口还能接拓展坞，连键鼠、给AirPods充电，甚至外接硬盘直接录制4K60帧的ProRes视频。对于视频创作者来说，这简直就是生产力神器。', '不过要注意，标准版和Pro版的C口传输速度差距很大。如果你经常需要传输大量照片视频，建议直接上Pro版。毕竟从2023年9月发布到现在，15Pro的性能依然很能打。', '最后给个建议：如果你还在用Lightning接口的旧iPhone，现在换15系列正是时候。一根C线搞定所有设备，这才是2025年该有的体验。",
            "示例：松木VS橡胶木家具大对决，谁更胜一筹？松木和橡胶木做家具，到底哪个更好？直接告诉你答案：没有绝对的优劣，关键看你的需求。松木适合文艺小清新，橡胶木则是实用派代表。', '先说说它们的共同点。这两种木材都属于经济型实木，价格比红木、胡桃木亲民多了。都需要特殊处理才能用，松木要防腐，橡胶木要脱糖，就像两个都需要化妆的素人，底子不错但得捯饬。', '但差异可就大了。松木来自生长20年以上的松树，密度只有0.4克每立方厘米，轻得能飘起来。橡胶木是割胶15年后的橡胶树二次利用，密度0.65克每立方厘米，硬得像块砖。一个适合做儿童床、装饰柜这些轻量级选手，一个能扛起餐桌、橱柜这些重量级选手。', '颜值党注意了！松木是蜜糖黄带山水纹，还有天然松节疤，就像北欧模特脸上的雀斑，反而成了特色。橡胶木是奶茶灰配直纹，光滑得像精修过的网红脸。一个自带森林清香能留香3-5年，一个刚出厂时有轻微奶酸味，但3-6个月就消散。', '重点来了！松木最怕潮湿，在南方可能分分钟变形给你看。橡胶木经过防潮处理，在潮湿环境里稳如老狗。但橡胶木有个隐藏问题，处理不当会有轻微防腐剂残留，虽然符合标准，但敏感人群可能介意。', '最后给选购指南：要文艺范选松木，MUJI风家具就是标杆；要实用派选橡胶木，网红餐桌基本都是它撑场子。记住，松木看含水率，橡胶木看脱糖工艺，别被无良商家用贴皮货忽悠了。', '所以问题来了：你家装修会选自带文艺buff的松木，还是实用至上的橡胶木？评论区告诉我你的选择！",
        ]
    )


@dataclass
class ExportConfig:
    output_dir: Path | None = None
    write_json: bool = False
    write_markdown: bool = False


@dataclass
class AgentConfig:
    fetch: FetchConfig = field(default_factory=FetchConfig)
    clean: CleanConfig = field(default_factory=CleanConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    rewrite: RewriteConfig = field(default_factory=RewriteConfig)
    prompt: PromptConfig = field(default_factory=PromptConfig)
    export: ExportConfig = field(default_factory=ExportConfig)
