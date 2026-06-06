#!/usr/bin/env python3
import json, os, time, urllib.request, urllib.error, urllib.parse
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(open(os.path.join(BASE_DIR, "config.json")))
LOG = os.path.join(BASE_DIR, "daily.log")

def log(m):
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {m}"
    print(line, flush=True)
    try: open(LOG, "a").write(line + "\n")
    except Exception: pass

def token():
    req = urllib.request.Request("https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        data=json.dumps({"app_id": CFG["feishu_app_id"], "app_secret": CFG["feishu_app_secret"]}).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    return json.loads(urllib.request.urlopen(req, timeout=15).read())["tenant_access_token"]

def fetch_records(tat, since_ms):
    base = CFG["base"]
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{base['app_token']}/tables/{base['table_id']}/records?page_size=200"
    out = []
    page = ""
    while True:
        u = url + (f"&page_token={page}" if page else "")
        req = urllib.request.Request(u, headers={"Authorization": "Bearer " + tat})
        r = json.loads(urllib.request.urlopen(req, timeout=20).read())
        data = r.get("data", {})
        for it in data.get("items", []):
            f = it.get("fields", {})
            ts = f.get("抓取时间")
            if isinstance(ts, list): ts = ts[0]
            if isinstance(ts, dict): ts = ts.get("value")
            if ts and ts >= since_ms:
                out.append(f)
        if data.get("has_more") and data.get("page_token"):
            page = data["page_token"]
        else:
            break
    return out

def _txt(v):
    if isinstance(v, list):
        return " ".join(_txt(x) for x in v)
    if isinstance(v, dict):
        return v.get("text") or v.get("value") or ""
    return str(v) if v is not None else ""

def summarize(records):
    if not records:
        return None
    lines = []
    for f in records:
        lines.append(f"- 博主：{_txt(f.get('博主'))}｜信号：{_txt(f.get('信号'))}｜标的：{_txt(f.get('标的'))}｜内容：{_txt(f.get('中文翻译'))[:200]}")
    corpus = "\n".join(lines)
    tc = CFG["translate"]
    sys_prompt = ("你是资深投研助手，给一位中文产品经理做X博主盯帖日报。基于给你的多条帖子记录，"
        "用简体中文输出，结构清晰、可扫读，包含：\n"
        "1.【今日重点】一两句话概括今天大家在聊什么\n"
        "2.【值得买入/关注】按市场分区呈现：分别用『A股』『美股』『港股』『韩股』『其他/不区分』小标题，把对应市场里出现的股票或方向列成要点，每条标明信号强弱和提到它的博主；没有的市场就不写该小标题；整体按重要性排序\n"
        "3.【共识方向】如果多位博主聊到同一标的或方向，单独点出来（这是最值得重视的）\n"
        "4.【分博主要点】每个博主一句话\n"
        "末尾加一行：以上为AI整理，不构成投资建议。不要用markdown代码块。")
    payload = {"model": tc["model"], "messages": [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": f"共{len(records)}条记录：\n{corpus}"}], "temperature": 0.3}
    req = urllib.request.Request(tc["base_url"].rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + tc["api_key"]}, method="POST")
    r = json.loads(urllib.request.urlopen(req, timeout=180).read())
    return r["choices"][0]["message"]["content"].strip()

def push(tat, title, body, count):
    card = {"config": {"wide_screen_mode": True},
        "header": {"template": "blue", "title": {"tag": "plain_text", "content": title}},
        "elements": [
            {"tag": "div", "text": {"tag": "lark_md", "content": body}},
            {"tag": "hr"},
            {"tag": "action", "actions": [{"tag": "button", "text": {"tag": "plain_text", "content": "📊 打开存档表格"}, "type": "default", "url": "https://mi.feishu.cn/base/" + CFG["base"]["app_token"]}]},
            {"tag": "note", "elements": [{"tag": "plain_text", "content": f"统计 {count} 条 · {datetime.now().strftime('%Y-%m-%d %H:%M')}"}]}
        ]}
    req = urllib.request.Request("https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id",
        data=json.dumps({"receive_id": CFG["feishu_open_id"], "msg_type": "interactive", "content": json.dumps(card)}).encode(),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + tat}, method="POST")
    r = json.loads(urllib.request.urlopen(req, timeout=20).read())
    return r.get("code") == 0

def write_daily_to_base(tat, label, body, count):
    base = CFG.get("base") or {}
    tid = base.get("daily_table_id")
    if not tid:
        return False
    import time
    period = "晚间" if "晚" in label else "早间"
    title = f"{datetime.now().strftime('%Y-%m-%d')} {period}日报"
    fields = {
        "标题": title,
        "生成时间": int(time.time() * 1000),
        "时段": period,
        "统计条数": count,
        "日报内容": body or "",
    }
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{base['app_token']}/tables/{tid}/records"
    try:
        req = urllib.request.Request(url, data=json.dumps({"fields": fields}).encode(),
            headers={"Authorization": "Bearer " + tat, "Content-Type": "application/json"}, method="POST")
        r = json.loads(urllib.request.urlopen(req, timeout=20).read())
        return r.get("code") == 0
    except Exception as e:
        log(f"daily base write fail: {str(e)[:140]}")
        return False

def main():
    tat = token()
    now = datetime.now()
    # 早报覆盖前一天20:00->今08:00；晚报覆盖今08:00->20:00；用近13小时近似
    since_ms = int((time.time() - 13 * 3600) * 1000)
    label = "🌙 晚间日报" if now.hour >= 18 else "🌅 早间日报"
    recs = fetch_records(tat, since_ms)
    log(f"records in window: {len(recs)}")
    if not recs:
        push(tat, f"{label}（{now.strftime('%m-%d')}）", "过去时段没有新帖。市场安静，休息一下～", 0)
        write_daily_to_base(tat, label, "过去时段没有新帖。", 0)
        return
    body = summarize(recs)
    ok = push(tat, f"{label}（{now.strftime('%m-%d')}）", body or "（生成失败）", len(recs))
    wrote = write_daily_to_base(tat, label, body, len(recs))
    log(f"daily push {'ok' if ok else 'fail'} base={'Y' if wrote else 'N'}")

if __name__ == "__main__":
    main()
