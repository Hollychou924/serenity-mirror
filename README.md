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

## 🚀 部署（自用）
1. 一台能直连 X/Twitter 的服务器（境外），装 Python3 + Playwright：
   \`\`\`bash
   pip install -r requirements.txt && python3 -m playwright install chromium
   \`\`\`
2. 复制 \`config.example.json\` 为 \`config.json\`，填入你自己的：X 登录态(auth_token/ct0)、飞书自建应用(app_id/secret/你的open_id)、豆包(或其他 OpenAI 兼容) API key、飞书多维表格 token。
3. 用 systemd timer 定时跑 \`watch.py\`（每5分钟）、\`daily.py\`（8:00/20:00）、\`serenity_engine.run_verify\`（每日）、\`weekly.py\`（每周）。

## 🧠 蒸馏来源
\`serenity-master\` 蒸馏自社区 5 个公开 Serenity skill（leslieyeo/serenity-reply、haskaomni/serenity-skill、muxuuu/serenity-skill、yan-labs、w-y-p）+ 公开网络分析，并由本系统持续抓取的最新帖子迭代。

## ⚠️ 免责声明
本项目仅用于研究与学习。所有内容非投资建议，不构成任何买卖推荐。请遵守 X、飞书及各数据源的服务条款；使用你自己的账号凭证，风险自负。
