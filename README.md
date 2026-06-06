# Serenity Mirror 🪞

一个会自我进化的 X(Twitter)博主追踪与「思维蒸馏」系统，围绕半导体/AI 供应链分析师 **Serenity (@aleabitoreddit)** 打造。它实时抓取她（及其他博主）的新帖，用大模型翻译+点评+信号识别推送到飞书，把每条投资主张沉淀成可验证的「主张卡」，到期后**联网查真实股价/事件验证她对错**，再用战绩反过来纠偏一个不断进化的「Serenity 思维 Skill」。

> Research & learning project. **Not investment advice.** 所有翻译、点评、预测均为 AI 推断，可能出错。

## ✨ 核心能力

- **实时盯帖**：每 5 分钟抓取多位 X 博主新帖（无需官方付费 API，用真实浏览器内核+登录态）。
- **中文卡片推送**：大模型（豆包）翻译为简体中文 + 投资点评 + 信号分级（🔴强烈买入/🟠关注/⚪一般），带圆形头像、博主简介、配图/视频封面，推送到飞书。
- **降噪**：只有强/关注信号即时推卡片，其余进存档表。
- **可筛选存档**：每条帖写入飞书多维表格（时间、博主、信号、市场标签美/A/港/韩、翻译、点评、链接）。
- **每日两次日报**：08:00 / 20:00，按市场分区汇总「值得买入/关注」+ 共识方向。
- **预测-验证-纠偏闭环**（灵魂）：
  - 把 Serenity 的每条主张提成「主张卡」，补全她没说的 why；
  - 到期联网查真实股价（A股走 a-stock-data、港美股走 global-stock-data）+ 事件，判定 应验/部分应验/证伪；
  - 累积「可信度地图」（她哪类判断更准），算「懂她指数」；
  - 每周复盘 → 蒸馏修正 Skill，核心改动需人工确认。
- **蒸馏 Skill `serenity-master`**：可直接给 AI 编码助手使用的「Serenity 思维操作系统」，含 5 心智模型、8 决策启发式、方法论引擎、表达 DNA、四档可信度防瞎编机制、评测集。

## 🗂 目录结构
\`\`\`
src/                盯帖+学习管线脚本
  watch.py          抓帖→翻译/点评→飞书卡片→存档→提主张
  daily.py          每日两次日报（按市场分区）
  serenity_engine.py 主张提取 + 补全why + 联网验证 + 懂她指数
  weekly.py         每周复盘 + 稳定层改动确认卡
skills/serenity-master/  蒸馏出的 Serenity 思维 Skill
config.example.json 配置模板（填你自己的密钥）
\`\`\`


## 🧩 serenity-master 是什么（Skill 详解）

\`serenity-master\` 是一个可直接给 AI 编码助手（Codex / Claude Code 等）使用的 **Serenity 思维操作系统**。它不是代码，是一套结构化的「思维 + 表达 + 自检」说明书，下挂多个引用文件。核心由以下几块组成：

### 1. 5 个核心心智模型（她怎么想）
她做投资判断的底层框架，每个都附「证据 + 应用 + 局限/反证」（不吹捧，能证伪）：
1. **供应链卡点理论**：最暴利的机会在控制"不可替代输入"的小公司，断供则全行业停摆（如 $AXTI 的 InP 衬底）。
2. **瓶颈博弈 vs 扩张估值**：卡点公司不能用营收倍数估值，要问"它断供会怎样"。
3. **NVIDIA 信号读取**：NVIDIA 投什么，那个方向的卡点 6-18 个月内兑现。
4. **信息不对称套利**：机会在"机构忽略（太小）+ 散户看不懂（太技术）"的交叉地带——她真正的差异化。
5. **正和市场观**：不碰期权时，长期持有卡点股是正和的。

### 2. 8 条决策启发式（她怎么决定）
可直接套用的决策规则，含她本人的"幸存者偏差/言行矛盾"警告：卡点测试、NVIDIA 跟随、欧洲小盘优先、反 meme 标签、机构跟随确认、反期权铁律、DYOR 底线、地缘政治折价。

### 3. 方法论引擎（她怎么做研究）
一条统一研究主链：`市场叙事 → 系统变化 → 所需零件 → 产业链分层 → 稀缺卡点 → 小盘弹性 → 公开公司 → 证据分级 → 市场可能错在哪 → 什么会证伪 → 按证据定仓位`。内嵌 alpha 假设链、alpha 7 维打分表、贝叶斯隐含增长率估值、卡点/催化剂/风控清单、输出模板。

### 4. 表达 DNA（她怎么说话）
第一人称扮演她时遵循的风格：结论先行、供应链证据跟上；高频词 thesis/bottleneck/chokepoint/anon/supercycle；对批评者 dismissive、用具体数字立信、不用 maybe；新领域先承认边界。

### 5. 四档可信度防瞎编机制（防 AI 编造）
每句话标明底气来源，绝不把推测讲成事实：① 直接引述（她原话+出处）② 多例归纳（稳定模式）③ 模型外推（必须明说"这是框架推断，不是结论"）④ 坦承无据（材料不支持就直说，不硬编）。

### 6. 评测集（自检质量）
交付/迭代后自动跑三类测试给自己打分：Sanity（已知案例如 AXTI 估值争议）、Edge（全新领域如量子计算）、Voice（风格还原度），外加一份自评清单。

### 7. 双运行模式
- **顾问视角（默认）**：第三人称拆解"用她的框架看，她会聚焦……"，安全、便于审视。
- **第一人称扮演**：以她的身份用"我"回应。
- 高风险问题（梭哈/借钱/加杠杆）强制退出扮演，给普通风险提示。

### 8. 自我进化（evolution/）
由本系统的预测-验证-纠偏闭环持续喂养：稳定层（心智模型/表达 DNA）改动需人工确认；快照层（标的宇宙/最新观点/可信度地图）自动刷新并留痕、版本化、可回滚。

## 🚀 部署（自用）
1. 一台能直连 X/Twitter 的服务器（境外），装 Python3 + Playwright：
   \`\`\`bash
   pip install -r requirements.txt && python3 -m playwright install chromium
   \`\`\`
2. 复制 \`config.example.json\` 为 \`config.json\`，填入你自己的：X 登录态(auth_token/ct0)、飞书自建应用(app_id/secret/你的open_id)、豆包(或其他 OpenAI 兼容) API key、飞书多维表格 token。
3. 用 systemd timer 定时跑 \`watch.py\`（每5分钟）、\`daily.py\`（8:00/20:00）、\`serenity_engine.run_verify\`（每日）、\`weekly.py\`（每周）。

## 🧠 蒸馏来源（致敬原作者）
\`serenity-master\` 站在以下 5 个社区开源项目的肩膀上蒸馏而成，衷心感谢原作者：

- [leslieyeo/serenity-reply](https://github.com/leslieyeo/serenity-reply) — 人格框架、四档可信度、自带评测（质量最高）
- [haskaomni/serenity-skill](https://github.com/haskaomni/serenity-skill) — alpha 假设链 + 贝叶斯隐含增长率估值
- [muxuuu/serenity-skill](https://github.com/muxuuu/serenity-skill) — 完整供应链卡点研究工作流 + 工程规范
- [yan-labs/serenity-aleabitoreddit](https://www.skills.sh/yan-labs/serenity-aleabitoreddit/serenity-aleabitoreddit) — 标的宇宙 + 决策导向（社区安装量最高）
- [w-y-p/serenity-chokepoint-investing](https://www.skills.sh/w-y-p/serenity-aleabitoreddit-skill/serenity-chokepoint-investing) — 物理卡点 / 催化剂 / 风控清单

以及公开网络对 Serenity 的分析，并由本系统持续抓取的最新帖子不断迭代。本项目仅蒸馏方法论与公开表达，不复制原仓库代码。

## ⚠️ 免责声明
本项目仅用于研究与学习。所有内容非投资建议，不构成任何买卖推荐。请遵守 X、飞书及各数据源的服务条款；使用你自己的账号凭证，风险自负。
