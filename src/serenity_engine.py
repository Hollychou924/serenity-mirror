#!/usr/bin/env python3
"""Serenity 懂她引擎：主张提取 + 补全why + 到期联网验证 + 懂她指数。
依赖 /opt/xwatch/watch.py 的飞书/豆包能力与 config。"""
import json, os, time, urllib.request, urllib.parse, urllib.error, re
from datetime import datetime, timedelta
import watch  # 复用 feishu_token / CFG / log

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(BASE_DIR, "engine.log")
CFG = watch.CFG
CLAIMS_TABLE = (CFG.get("base") or {}).get("claims_table_id")
APP = (CFG.get("base") or {}).get("app_token")

def log(m):
    line=f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {m}"
    print(line,flush=True)
    try: open(LOG,"a").write(line+"\n")
    except Exception: pass

def doubao(messages, temp=0.2, timeout=120):
    tc=CFG["translate"]
    payload={"model":tc["model"],"messages":messages,"temperature":temp}
    req=urllib.request.Request(tc["base_url"].rstrip("/")+"/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type":"application/json","Authorization":"Bearer "+tc["api_key"]},method="POST")
    r=json.loads(urllib.request.urlopen(req,timeout=timeout).read().decode())
    return r["choices"][0]["message"]["content"]

def parse_json(txt):
    if txt.strip().startswith("```"):
        txt=re.sub(r"^```[a-zA-Z]*","",txt.strip()).rstrip("`").strip()
    m=re.search(r"\{.*\}",txt,re.S)
    raw=m.group(0) if m else txt
    try: return json.loads(raw)
    except Exception: return json.loads(raw,strict=False)

PERIOD_DAYS={"短(2周)":14,"中(1月)":30,"长(1季度)":90}

def extract_claim(sn, tweet_text, tweet_id, anchor=""):
    """把一条帖提炼成主张卡 + 补全why。返回 dict 或 None（无可验证主张）。"""
    sys_prompt=("你是 Serenity(@aleabitoreddit) 研究助手。给你她的一条推文，判断里面有没有"
      "针对具体标的/方向的可验证投资主张。只输出一个JSON："
      '{"has_claim":true/false,'
      '"stock":"标的中文名+代码，没有就空",'
      '"market":["美股/A股/港股/韩股/不区分/其他，可多选"],'
      '"direction":"看多/看空/中性/关注",'
      '"implied_prediction":"她这条帖隐含的、未来可被现实验证的预测，一句话（如：未来1-3月该股应因拿到大厂订单而上涨）",'
      '"period":"短(2周)/中(1月)/长(1季度)，按催化剂兑现快慢选",'
      '"why":"用她的卡点逻辑/NVIDIA信号/信息不对称框架，补全她没明说的隐含理由，2-3句，标明这是框架推断"}'
      "没有具体可验证主张就 has_claim=false。")
    try:
        info=parse_json(doubao([{"role":"system","content":sys_prompt},{"role":"user","content":tweet_text}]))
    except Exception as e:
        log(f"extract fail {tweet_id}: {str(e)[:120]}"); return None
    if not info.get("has_claim"): return None
    info["sn"]=sn; info["tweet_id"]=tweet_id; info["anchor"]=anchor
    return info

def write_claim(info, tat):
    if not CLAIMS_TABLE: 
        log("no claims_table_id in config"); return False
    period=info.get("period","中(1月)")
    if period not in PERIOD_DAYS: period="中(1月)"
    now=time.time()
    due=int((now+PERIOD_DAYS[period]*86400)*1000)
    mk=info.get("market") or []
    if isinstance(mk,str): mk=[mk]
    mk=[x for x in mk if x in {"美股","A股","港股","韩股","不区分","其他"}]
    dirmap={"看多":"看多","看空":"看空","中性":"中性","关注":"关注"}
    url=f"https://x.com/{info['sn']}/status/{info['tweet_id']}"
    fields={
        "主张摘要": (info.get("implied_prediction","") or "")[:300],
        "博主": watch.display_name(info["sn"]),
        "标的": info.get("stock","") or "",
        "方向": dirmap.get(info.get("direction"),"关注"),
        "隐含预测": info.get("implied_prediction","") or "",
        "提出时间": int(now*1000),
        "锚点价/市值": info.get("anchor","") or "",
        "复查周期": period,
        "到期复查时间": due,
        "验证状态": "待观察",
        "补全why": info.get("why","") or "",
        "原帖链接": {"link":url,"text":"原帖"},
    }
    if mk: fields["市场"]=mk
    api=f"https://open.feishu.cn/open-apis/bitable/v1/apps/{APP}/tables/{CLAIMS_TABLE}/records"
    try:
        req=urllib.request.Request(api,data=json.dumps({"fields":fields}).encode(),
            headers={"Authorization":"Bearer "+tat,"Content-Type":"application/json"},method="POST")
        r=json.loads(urllib.request.urlopen(req,timeout=20).read())
        return r.get("code")==0
    except Exception as e:
        log(f"write_claim fail: {str(e)[:140]}"); return False



# ============ 预测-验证-纠偏闭环 ============
def _tencent_raw(qcode):
    url="https://qt.gtimg.cn/q="+qcode
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
    data=urllib.request.urlopen(req,timeout=12).read().decode("gbk","ignore")
    m=re.search(r'"(.+)"',data)
    if not m: return None
    return m.group(1).split("~")

def get_price(stock_text, markets):
    """按市场用对应数据源(腾讯统一接口)查现价。A股->a-stock-data口径(sh/sz/bj)，港美股->global-stock-data口径(us/r_hk)。"""
    mk = markets[0] if markets else ""
    code = (re.search(r"[0-9]{4,6}", stock_text or "") or [None])
    code = code.group(0) if hasattr(code,"group") else None
    try:
        if "A股" in mk and code:
            if code.startswith(("6","9")): q="sh"+code
            elif code.startswith("8"): q="bj"+code
            else: q="sz"+code
            v=_tencent_raw(q)
            if v and len(v)>45:
                return {"market":"A股","name":v[1],"price":float(v[3] or 0),"last_close":float(v[4] or 0),
                        "change_pct":float(v[32] or 0),"pe_ttm":float(v[39] or 0),"mcap_yi":float(v[44] or 0),"source":"腾讯/a-stock-data"}
        if "港股" in mk and code:
            q="r_hk"+code.zfill(5)
            v=_tencent_raw(q)
            if v and len(v)>45:
                return {"market":"港股","name":v[1],"price":float(v[3] or 0),"prev_close":float(v[4] or 0),
                        "change_pct":float(v[32] or 0),"mcap_yi_hkd":float(v[44] or 0),"source":"腾讯/global-stock-data"}
        # 美股：用英文代码(从 stock_text 抽大写字母 ticker)
        tk=re.search(r"[A-Z]{1,5}", (stock_text or "").upper())
        if ("美股" in mk or not mk) and tk:
            q="us"+tk.group(0)
            v=_tencent_raw(q)
            if v and len(v)>50:
                return {"market":"美股","name":v[1],"name_en":v[27] if len(v)>27 else "","price":float(v[3] or 0),
                        "prev_close":float(v[4] or 0),"change_pct":float(v[32] or 0),"mcap_yi_usd":float(v[44] or 0),"source":"腾讯/global-stock-data"}
    except Exception as e:
        return {"error":str(e)[:120],"note":"查价失败"}
    return {"note":"未能按市场定位代码","stock":stock_text,"market":mk}

def web_search(q, n=5):
    """DuckDuckGo HTML 轻量搜索，返回标题+摘要文本。"""
    try:
        url="https://html.duckduckgo.com/html/?q="+urllib.parse.quote(q)
        req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
        html=urllib.request.urlopen(req,timeout=15).read().decode("utf-8","ignore")
        snips=re.findall(r'result__snippet[^>]*>(.*?)</a>',html,re.S)[:n]
        clean=[re.sub(r"<[^>]+>","",s).strip() for s in snips]
        return " | ".join(c for c in clean if c)[:1500]
    except Exception as e:
        return f"(search fail {str(e)[:80]})"

def guess_symbol(stock_text, markets):
    """从'绿的谐波688017'这类文本+市场，猜 Yahoo 代码。让豆包给最可能的 Yahoo 代码。"""
    try:
        prompt=("给你一个股票名称和它所属市场，只输出该股票在 Yahoo Finance 的代码（如 AXTI、688017.SS、0700.HK、SIVE.ST），"
                "只输出代码本身，不确定就输出 NONE。")
        out=doubao([{"role":"system","content":prompt},
                    {"role":"user","content":f"名称:{stock_text} 市场:{','.join(markets) if markets else '未知'}"}],temp=0).strip()
        out=out.split()[0].strip("`") if out else "NONE"
        return None if out.upper()=="NONE" else out
    except Exception:
        return None

def list_due_claims(tat):
    if not CLAIMS_TABLE: return []
    now=int(time.time()*1000)
    url=f"https://open.feishu.cn/open-apis/bitable/v1/apps/{APP}/tables/{CLAIMS_TABLE}/records?page_size=200"
    req=urllib.request.Request(url,headers={"Authorization":"Bearer "+tat})
    r=json.loads(urllib.request.urlopen(req,timeout=20).read())
    due=[]
    for it in r.get("data",{}).get("items",[]):
        f=it.get("fields",{})
        st=f.get("验证状态")
        st=st[0] if isinstance(st,list) else st
        if isinstance(st,dict): st=st.get("text")
        duets=f.get("到期复查时间")
        if isinstance(duets,list): duets=duets[0]
        if isinstance(duets,dict): duets=duets.get("value")
        if st=="待观察" and duets and duets<=now:
            due.append((it["record_id"],f))
    return due

def _t(v):
    if isinstance(v,list): return " ".join(_t(x) for x in v)
    if isinstance(v,dict): return v.get("text") or v.get("value") or ""
    return str(v) if v is not None else ""

def verify_claim(record_id, f, tat):
    stock=_t(f.get("标的")); markets=[_t(f.get("市场"))]
    pred=_t(f.get("隐含预测")); anchor=_t(f.get("锚点价/市值"))
    price=get_price(stock, markets) if stock else {"note":"无标的"}
    news=web_search(f"{stock} stock news") if stock else ""
    sys_prompt=("你是投研验证助手。给你一条某博主当时的投资主张、当时锚点、现在的行情和近期新闻，"
        "判断这条主张到现在是否被现实验证。只输出JSON："
        '{"verdict":"应验/部分应验/证伪/待观察","basis":"2-3句中文依据，引用价格变化和事件","confidence":"高/中/低"}')
    user=(f"主张：{pred}\n标的：{stock}\n当时锚点：{anchor}\n现在行情：{json.dumps(price,ensure_ascii=False)}\n近期新闻：{news}")
    try:
        res=parse_json(doubao([{"role":"system","content":sys_prompt},{"role":"user","content":user}]))
    except Exception as e:
        log(f"verify judge fail {record_id}: {str(e)[:120]}"); return None
    verdict=res.get("verdict","待观察")
    basis=res.get("basis","")
    src=""
    fields={"验证状态": verdict if verdict in ("应验","部分应验","证伪") else "已复查",
            "验证依据": (basis+f"（行情:{price.get('price')} {price.get('currency','')}）")[:500]}
    # 行情来源为腾讯实时接口(a-stock-data/global-stock-data 口径)
    api=f"https://open.feishu.cn/open-apis/bitable/v1/apps/{APP}/tables/{CLAIMS_TABLE}/records/{record_id}"
    try:
        req=urllib.request.Request(api,data=json.dumps({"fields":fields}).encode(),
            headers={"Authorization":"Bearer "+tat,"Content-Type":"application/json"},method="PUT")
        r=json.loads(urllib.request.urlopen(req,timeout=20).read())
        ok=r.get("code")==0
        log(f"verify {record_id} stock={stock} verdict={verdict} ok={ok}")
        return verdict if ok else None
    except Exception as e:
        log(f"verify write fail {record_id}: {str(e)[:120]}"); return None

def run_verify():
    tat=watch.feishu_token()
    due=list_due_claims(tat)
    log(f"due claims: {len(due)}")
    stats={}
    for rid,f in due:
        v=verify_claim(rid,f,tat)
        if v: stats[v]=stats.get(v,0)+1
    log(f"verify done: {stats}")
    return stats

if __name__=="__main__":
    import sys
    if len(sys.argv)>1 and sys.argv[1]=="test-extract":
        tat=watch.feishu_token()
        text=("Specially written for my Chinese readers: LeaderDrive (688017) is the Chinese listed stock "
              "I favor most in the humanoid robot track. Harmonic reducers 60%+ domestic share. "
              "I'm extremely bullish on the robotics track.")
        info=extract_claim("aleabitoreddit",text,"2062433114933334487","688017 锚点约57.7B RMB")
        print("CLAIM:",json.dumps(info,ensure_ascii=False))
        if info:
            print("write:",write_claim(info,tat))
