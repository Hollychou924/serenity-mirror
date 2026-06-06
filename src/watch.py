#!/usr/bin/env python3
import asyncio, json, os, sys, io, urllib.request
from datetime import datetime
from playwright.async_api import async_playwright

BASE = os.path.dirname(os.path.abspath(__file__))
CFG = json.load(open(os.path.join(BASE, "config.json")))
SEEN_FILE = os.path.join(BASE, "seen.json")
LOG_FILE = os.path.join(BASE, "watch.log")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

def screen_names():
    if CFG.get("screen_names"):
        return CFG["screen_names"]
    return [CFG.get("screen_name", "aleabitoreddit")]

def display_name(sn):
    return (CFG.get("display_names") or {}).get(sn, sn)

def log(msg):
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        open(LOG_FILE, "a").write(line + "\n")
    except Exception:
        pass

def load_seen():
    if os.path.exists(SEEN_FILE):
        try:
            d = json.load(open(SEEN_FILE))
            if isinstance(d, list):
                return {"_legacy": set(d)}
            return {k: set(v) for k, v in d.items()}
        except Exception:
            return {}
    return {}

def save_seen(seen):
    out = {k: list(v)[-400:] for k, v in seen.items()}
    json.dump(out, open(SEEN_FILE, "w"))

def feishu_token():
    req = urllib.request.Request(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        data=json.dumps({"app_id": CFG["feishu_app_id"], "app_secret": CFG["feishu_app_secret"]}).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    return json.loads(urllib.request.urlopen(req, timeout=15).read().decode())["tenant_access_token"]

def process_tweet(text):
    tc = CFG.get("translate") or {}
    if not tc.get("enabled") or not text or not text.strip():
        return None
    import re
    sys_prompt = ("你是资深的美股/A股产业分析助手，服务对象是看不懂英文、不爱看长文的中文产品经理。"
        "针对给你的一条投资类推文，只输出一个JSON对象（不要任何多余文字、不要markdown代码块），字段："
        '{"zh":"完整简体中文翻译；务必按原文的自然段落分段，段落之间用一个空行隔开，列举要点时每条单独成行；保留$代码、公司名、专业术语、@提及原样；不要把多段挤成一坨",'
        '"signal":"strong_buy|watch|neutral","signal_label":"中文档位名",'
        '"stock":"涉及的股票/标的中文名（能识别就给A股/港股/美股常用名），没有就空字符串",'
        '"market":["涉及的股票市场，从[美股,A股,港股,韩股,不区分,其他]里选，可多选的数组；纯宏观或无具体市场就填[不区分]",'
        '"comment":"两到三句中文点评，说清帖子讲什么、博主态度多强、为什么值得或不值得重视，口语化"}'
        "判定规则：博主明确强烈看多/重仓/最看好某具体标的=strong_buy；只是提到关注或温和看好=watch；行业评论/转发/无明确标的=neutral。")
    try:
        payload = {"model": tc.get("model"),
                   "messages": [{"role": "system", "content": sys_prompt},
                                {"role": "user", "content": text}],
                   "temperature": 0.2}
        req = urllib.request.Request(tc["base_url"].rstrip("/") + "/chat/completions",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json", "Authorization": "Bearer " + tc["api_key"]},
            method="POST")
        r = json.loads(urllib.request.urlopen(req, timeout=120).read().decode())
        txt = r["choices"][0]["message"]["content"]
        if txt.strip().startswith("```"):
            txt = re.sub(r"^```[a-zA-Z]*", "", txt.strip()).rstrip("`").strip()
        m = re.search(r"\{.*\}", txt, re.S)
        raw = m.group(0) if m else txt
        try:
            return json.loads(raw)
        except Exception:
            cleaned = "".join(ch for ch in raw if ch >= " " or ch in "\t")
            try:
                return json.loads(cleaned, strict=False)
            except Exception:
                return json.loads(raw, strict=False)
    except Exception as e:
        log(f"process fail: {str(e)[:140]}")
    return None

def upload_image(img_url, tat):
    try:
        u = img_url.split("?")[0] + "?format=jpg&name=large"
        data = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA}), timeout=25).read()
        boundary = "----xwatchboundary"
        body = io.BytesIO()
        def w(s): body.write(s if isinstance(s, bytes) else s.encode())
        w(f"--{boundary}\r\n"); w('Content-Disposition: form-data; name="image_type"\r\n\r\n'); w("message\r\n")
        w(f"--{boundary}\r\n"); w('Content-Disposition: form-data; name="image"; filename="x.jpg"\r\n'); w("Content-Type: image/jpeg\r\n\r\n"); w(data); w("\r\n")
        w(f"--{boundary}--\r\n")
        req = urllib.request.Request("https://open.feishu.cn/open-apis/im/v1/images", data=body.getvalue(),
            headers={"Authorization": "Bearer " + tat, "Content-Type": f"multipart/form-data; boundary={boundary}"}, method="POST")
        r = json.loads(urllib.request.urlopen(req, timeout=30).read().decode())
        if r.get("code") == 0:
            return r["data"]["image_key"]
    except Exception as e:
        log(f"img upload fail: {str(e)[:120]}")
    return None

def upload_avatar(img_url, tat):
    try:
        data = urllib.request.urlopen(urllib.request.Request(img_url, headers={"User-Agent": UA}), timeout=20).read()
        boundary = "----xwatchboundary"
        body = io.BytesIO()
        def w(s2): body.write(s2 if isinstance(s2, bytes) else s2.encode())
        w(f"--{boundary}\r\n"); w('Content-Disposition: form-data; name="image_type"\r\n\r\n'); w("message\r\n")
        w(f"--{boundary}\r\n"); w('Content-Disposition: form-data; name="image"; filename="a.jpg"\r\n'); w("Content-Type: image/jpeg\r\n\r\n"); w(data); w("\r\n")
        w(f"--{boundary}--\r\n")
        req = urllib.request.Request("https://open.feishu.cn/open-apis/im/v1/images", data=body.getvalue(),
            headers={"Authorization": "Bearer " + tat, "Content-Type": f"multipart/form-data; boundary={boundary}"}, method="POST")
        r = json.loads(urllib.request.urlopen(req, timeout=30).read().decode())
        if r.get("code") == 0:
            return r["data"]["image_key"]
    except Exception as e:
        log(f"avatar upload fail: {str(e)[:120]}")
    return None

AVATAR_CACHE = os.path.join(BASE, "avatars.json")

def _load_avatar_cache():
    if os.path.exists(AVATAR_CACHE):
        try:
            return json.load(open(AVATAR_CACHE))
        except Exception:
            return {}
    return {}

def _save_avatar_cache(d):
    try:
        json.dump(d, open(AVATAR_CACHE, "w"))
    except Exception:
        pass

def get_avatar_key(sn, tat):
    avatars = CFG.get("avatars") or {}
    url = avatars.get(sn)
    if not url:
        return None
    cache = _load_avatar_cache()
    entry = cache.get(sn)
    if isinstance(entry, dict) and entry.get("url") == url and entry.get("key"):
        return entry["key"]
    ik = upload_avatar(url, tat)
    if not ik:
        ik = upload_avatar(url.replace("_normal", "_bigger"), tat)
    if ik:
        cache[sn] = {"url": url, "key": ik}
        _save_avatar_cache(cache)
    return ik

def build_card(sn, tweet, media_items, zh_text, analysis, avatar_key=None):
    name = display_name(sn)
    kind = "转推" if tweet.get("retweet") else "新帖"
    url = f"https://x.com/{sn}/status/{tweet['id']}"
    sig = (analysis or {}).get("signal", "neutral")
    bio = (CFG.get("bios") or {}).get(sn, "")
    en = (tweet["text"] or "").strip()
    elements = []
    name_line = f"**{name}**  ·  @{sn}"
    if bio:
        name_line += f"\n{bio}"
    if avatar_key:
        avatar_img = {"tag": "img", "img_key": avatar_key,
                      "alt": {"tag": "plain_text", "content": "头像"},
                      "mode": "fit_horizontal", "preview": False, "corner_radius": "50%"}
        elements.append({"tag": "column_set", "flex_mode": "none", "columns": [
            {"tag": "column", "width": "44px", "vertical_align": "center", "elements": [avatar_img]},
            {"tag": "column", "width": "weighted", "weight": 1, "vertical_align": "center",
             "elements": [{"tag": "div", "text": {"tag": "lark_md", "content": name_line}}]}
        ]})
    else:
        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": name_line}})
    elements.append({"tag": "hr"})
    if zh_text:
        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": zh_text}})
    elif en:
        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": en}})
    for m in media_items:
        if m.get("image_key"):
            elements.append({"tag": "img", "img_key": m["image_key"],
                             "alt": {"tag": "plain_text", "content": "image"},
                             "mode": "fit_horizontal", "preview": True})
            if m["kind"] == "video":
                elements.append({"tag": "note", "elements": [
                    {"tag": "plain_text", "content": "▶️ 这是视频封面，点下方按钮到 X 看视频"}]})
    if analysis:
        emoji = {"strong_buy": "\ud83d\udd34", "watch": "\ud83d\udfe0", "neutral": "\u26aa"}.get(sig, "\u26aa")
        label = analysis.get("signal_label") or {"strong_buy": "\u5f3a\u4fe1\u53f7", "watch": "\u5173\u6ce8", "neutral": "\u4e00\u822c"}.get(sig, "\u4e00\u822c")
        stock = analysis.get("stock") or ""
        comment = analysis.get("comment") or ""
        head_line = f"{emoji} **\u8c46\u5305\u70b9\u8bc4 \u00b7 {label}**"
        if stock:
            head_line += f"\uff08\u6807\u7684\uff1a{stock}\uff09"
        elements.append({"tag": "hr"})
        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": head_line + "\n\n" + comment}})
    elements.append({"tag": "hr"})
    elements.append({"tag": "action", "actions": [
        {"tag": "button", "text": {"tag": "plain_text", "content": "🔗 在 X 查看原帖"}, "type": "primary", "url": url}
    ]})
    elements.append({"tag": "note", "elements": [
        {"tag": "plain_text", "content": ("以上不构成投资建议· " + f"来源 X · @{sn} · {datetime.now().strftime('%m-%d %H:%M')} 抓取")}
    ]})
    header = {
        "template": ("red" if sig=="strong_buy" else ("orange" if sig=="watch" else ("indigo" if not tweet.get("retweet") else "wathet"))),
        "title": {"tag": "plain_text", "content": ({"strong_buy":"⚠️ 强烈买入信号","watch":"🟠 值得关注","neutral":f"🐦 新{kind}"}.get(sig, f"🐦 新{kind}"))}
    }
    return {
        "config": {"wide_screen_mode": True},
        "header": header,
        "elements": elements
    }

def feishu_push_card(card, tat):
    req = urllib.request.Request(
        "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id",
        data=json.dumps({"receive_id": CFG["feishu_open_id"], "msg_type": "interactive", "content": json.dumps(card)}).encode(),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + tat}, method="POST")
    r = json.loads(urllib.request.urlopen(req, timeout=20).read().decode())
    return r.get("code") == 0, r.get("msg")

def write_to_base(sn, tweet, info, tat):
    base = CFG.get("base") or {}
    if not base.get("app_token") or not base.get("table_id"):
        return False
    import time
    info = info or {}
    sig = info.get("signal", "neutral")
    sig_label = {"strong_buy": "强烈买入", "watch": "值得关注", "neutral": "一般"}.get(sig, "一般")
    url = f"https://x.com/{sn}/status/{tweet['id']}"
    fields = {
        "抓取时间": int(time.time() * 1000),
        "博主": display_name(sn),
        "账号": "@" + sn,
        "类型": "转推" if tweet.get("retweet") else "新帖",
        "信号": sig_label,
        "标的": info.get("stock", "") or "",
        "中文翻译": info.get("zh", "") or (tweet.get("text") or ""),
        "豆包点评": info.get("comment", "") or "",
        "原帖链接": {"link": url, "text": "查看原帖"},
    }
    mk = info.get("market")
    if isinstance(mk, str):
        mk = [mk]
    if isinstance(mk, list) and mk:
        allow = {"美股", "A股", "港股", "韩股", "不区分", "其他"}
        mk = [x for x in mk if x in allow]
        if mk:
            fields["市场"] = mk
    api_url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{base['app_token']}/tables/{base['table_id']}/records"
    try:
        req = urllib.request.Request(api_url, data=json.dumps({"fields": fields}).encode(),
            headers={"Authorization": "Bearer " + tat, "Content-Type": "application/json"}, method="POST")
        r = json.loads(urllib.request.urlopen(req, timeout=20).read().decode())
        if r.get("code") == 0:
            return True
        log(f"[{sn}] base write code={r.get('code')} msg={r.get('msg')}")
    except Exception as e:
        log(f"[{sn}] base write fail: {str(e)[:140]}")
    return False

def parse_tweets(payload, sn):
    out = []
    def walk(o):
        if isinstance(o, dict):
            if o.get("__typename") == "Tweet" or ("rest_id" in o and "legacy" in o):
                lg = o.get("legacy") or {}
                tid = o.get("rest_id") or lg.get("id_str")
                ft = lg.get("full_text")
                note = o.get("note_tweet") or {}
                note_text = ((note.get("note_tweet_results") or {}).get("result") or {}).get("text")
                text = note_text if note_text else ft
                author = ((o.get("core") or {}).get("user_results") or {}).get("result") or {}
                author_sn = ((author.get("legacy") or {}).get("screen_name") or
                             ((author.get("core") or {}).get("screen_name")))
                if tid and text is not None:
                    media = (lg.get("extended_entities") or {}).get("media") or []
                    items = []
                    for m in media:
                        mt = m.get("type")
                        if mt == "photo" and m.get("media_url_https"):
                            items.append({"kind": "photo", "thumb": m["media_url_https"]})
                        elif mt in ("video", "animated_gif") and m.get("media_url_https"):
                            items.append({"kind": "video", "thumb": m["media_url_https"]})
                    out.append({"id": str(tid), "text": text,
                                "retweet": "retweeted_status_result" in lg,
                                "media": items,
                                "author_sn": author_sn})
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(payload)
    # 只保留该博主本人原创/转推（过滤页面里混入的引用他人推文）
    res = []
    seen_ids = set()
    for t in out:
        if t["id"] in seen_ids:
            continue
        if t.get("author_sn") and t["author_sn"].lower() != sn.lower():
            continue
        seen_ids.add(t["id"])
        res.append(t)
    return res

async def fetch_user(ctx, sn):
    captured = []
    page = await ctx.new_page()
    async def on_resp(r):
        if "UserTweets" in r.url:
            try:
                captured.append(await r.json())
            except Exception:
                pass
    page.on("response", on_resp)
    try:
        await page.goto("https://x.com/" + sn, wait_until="domcontentloaded", timeout=45000)
        for _ in range(10):
            await page.wait_for_timeout(2500)
            if captured:
                break
            try:
                await page.mouse.wheel(0, 1200)
            except Exception:
                pass
        if not captured:
            try:
                await page.reload(wait_until="domcontentloaded", timeout=45000)
                for _ in range(6):
                    await page.wait_for_timeout(2500)
                    if captured:
                        break
            except Exception:
                pass
    finally:
        await page.close()
    tweets = []
    for pl in captured:
        tweets.extend(parse_tweets(pl, sn))
    uniq = {}
    for t in tweets:
        uniq[t["id"]] = t
    return list(uniq.values())

async def run_once(first_run=False):
    seen = load_seen()
    tat = None
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        ctx = await b.new_context(user_agent=UA)
        await ctx.add_cookies([
            {"name": "auth_token", "value": CFG["auth_token"], "domain": ".x.com", "path": "/"},
            {"name": "ct0", "value": CFG["ct0"], "domain": ".x.com", "path": "/"},
        ])
        for sn in screen_names():
            try:
                tweets = await fetch_user(ctx, sn)
            except Exception as e:
                log(f"[{sn}] fetch error: {type(e).__name__} {str(e)[:160]}")
                continue
            if not tweets:
                log(f"[{sn}] no tweets captured")
                continue
            sn_seen = seen.setdefault(sn, set())
            tweets_sorted = sorted(tweets, key=lambda x: int(x["id"]))
            new_ones = [t for t in tweets_sorted if t["id"] not in sn_seen]
            if first_run or (sn not in seen) or (len(sn_seen) == 0):
                for t in tweets_sorted:
                    sn_seen.add(t["id"])
                log(f"[{sn}] baseline {len(tweets_sorted)} tweets, no push")
                continue
            if not new_ones:
                log(f"[{sn}] checked {len(tweets_sorted)}, nothing new")
                continue
            if tat is None:
                tat = feishu_token()
            push_signals = CFG.get("push_signals") or ["strong_buy", "watch", "neutral"]
            for t in new_ones:
                info = process_tweet(t["text"])
                zh = (info or {}).get("zh") if info else None
                if not zh:
                    log(f"[{sn}] skip(no-zh, retry next round) id={t['id']} len={len(t['text'] or '')}")
                    continue
                sig = (info or {}).get("signal", "neutral")
                # 先写存档表（所有信号都存）
                wrote = write_to_base(sn, t, info, tat)
                # 仅对 Serenity 的有观点帖，提取"主张卡"进预测-验证闭环
                if sn == "aleabitoreddit" and sig in ("strong_buy", "watch"):
                    try:
                        import serenity_engine as _SE
                        _claim = _SE.extract_claim(sn, t["text"], t["id"], anchor=(info or {}).get("stock", ""))
                        if _claim:
                            _SE.write_claim(_claim, tat)
                            log(f"[{sn}] claim extracted id={t['id']} stock={_claim.get('stock')}")
                    except Exception as _e:
                        log(f"[{sn}] claim extract error id={t['id']}: {str(_e)[:120]}")
                # 再按降噪规则决定是否即时推卡片
                if sig in push_signals:
                    media_items = []
                    for m in (t.get("media") or [])[:4]:
                        ik = upload_image(m["thumb"], tat)
                        media_items.append({"kind": m["kind"], "image_key": ik})
                    avatar_key = get_avatar_key(sn, tat)
                    card = build_card(sn, t, media_items, zh, info, avatar_key)
                    try:
                        ok, msg = feishu_push_card(card, tat)
                        log(f"[{sn}] push {'ok' if ok else 'FAIL('+str(msg)+')'} id={t['id']} sig={sig} base={'Y' if wrote else 'N'}")
                        if ok:
                            sn_seen.add(t["id"])
                    except Exception as e:
                        log(f"[{sn}] push error id={t['id']}: {str(e)[:150]}")
                else:
                    log(f"[{sn}] archived(no-push) id={t['id']} sig={sig} base={'Y' if wrote else 'N'}")
                    if wrote:
                        sn_seen.add(t["id"])
        await b.close()
    save_seen(seen)

if __name__ == "__main__":
    asyncio.run(run_once(first_run="--first" in sys.argv))
