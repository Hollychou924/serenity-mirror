#!/usr/bin/env python3
"""每周懂她复盘：战绩 + 懂她指数 + 可信度地图更新 + 蒸馏建议 + 飞书卡片 + 稳定层改动确认卡。"""
import json, os, time, urllib.request, urllib.parse, re
from datetime import datetime
import watch, serenity_engine as E

BASE_DIR=os.path.dirname(os.path.abspath(__file__))
LOG=os.path.join(BASE_DIR,"weekly.log")
APP=watch.CFG["base"]["app_token"]; CT=watch.CFG["base"]["claims_table_id"]

def log(m):
    line=f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {m}"
    print(line,flush=True)
    try: open(LOG,"a").write(line+"\n")
    except Exception: pass

def _t(v):
    if isinstance(v,list): return " ".join(_t(x) for x in v)
    if isinstance(v,dict): return v.get("text") or v.get("value") or ""
    return str(v) if v is not None else ""

def fetch_claims(tat):
    url=f"https://open.feishu.cn/open-apis/bitable/v1/apps/{APP}/tables/{CT}/records?page_size=200"
    r=json.loads(urllib.request.urlopen(urllib.request.Request(url,headers={"Authorization":"Bearer "+tat}),timeout=20).read())
    return [it["fields"] for it in r.get("data",{}).get("items",[])]

def push_card(tat, title, body, template="purple", actions=None):
    elements=[{"tag":"div","text":{"tag":"lark_md","content":body}}]
    if actions: elements.append({"tag":"action","actions":actions})
    elements.append({"tag":"note","elements":[{"tag":"plain_text","content":"AI 框架推断，非她本人，可能错，非投资建议 · "+datetime.now().strftime('%Y-%m-%d %H:%M')}]})
    card={"config":{"wide_screen_mode":True},"header":{"template":template,"title":{"tag":"plain_text","content":title}},"elements":elements}
    req=urllib.request.Request("https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id",
        data=json.dumps({"receive_id":watch.CFG["feishu_open_id"],"msg_type":"interactive","content":json.dumps(card)}).encode(),
        headers={"Content-Type":"application/json","Authorization":"Bearer "+tat},method="POST")
    return json.loads(urllib.request.urlopen(req,timeout=20).read()).get("code")==0

def main():
    tat=watch.feishu_token()
    # 1) 先跑一遍到期验证（确保战绩最新）
    try: E.run_verify()
    except Exception as e: log(f"verify in weekly fail: {str(e)[:120]}")
    claims=fetch_claims(tat)
    verified=[c for c in claims if _t(c.get("验证状态")) in ("应验","部分应验","证伪")]
    n=len(verified)
    hit=sum(1 for c in verified if _t(c.get("验证状态"))=="应验")
    part=sum(1 for c in verified if _t(c.get("验证状态"))=="部分应验")
    miss=sum(1 for c in verified if _t(c.get("验证状态"))=="证伪")
    # 懂她指数：应验=1，部分=0.5，证伪=0
    index = round((hit*1.0+part*0.5)/n*100) if n else None
    # 2) 让豆包基于战绩出蒸馏建议
    lines=[f"- 标的:{_t(c.get('标的'))}｜方向:{_t(c.get('方向'))}｜结果:{_t(c.get('验证状态'))}｜依据:{_t(c.get('验证依据'))[:120]}" for c in verified[:40]]
    corpus="\n".join(lines) or "（本周暂无已验证主张）"
    sys_prompt=("你是 Serenity 研究复盘助手。基于本周已验证的主张战绩，用简体中文输出一份周复盘，结构："
      "1.【本周战绩】应验/部分/证伪各几条，一句话总结她近期哪类判断更准、哪类翻车\n"
      "2.【可信度更新】哪类逻辑(卡点/NVIDIA信号/小盘挖掘/估值时机/宏观)该加权或该警惕\n"
      "3.【她下一步可能关注】基于近期演变给1-3个方向+置信度(高/中/低)，标明是框架推断\n"
      "4.【蒸馏建议】是否需要给 skill 新增/修正心智模型或表达；若建议改稳定层，单列一行以『[需确认]』开头说明改什么、依据\n"
      "末尾不要加免责（系统会自动加）。不要用markdown代码块。")
    try:
        body=E.doubao([{"role":"system","content":sys_prompt},{"role":"user","content":f"懂她指数:{index}\n已验证{n}条(应验{hit}/部分{part}/证伪{miss})\n明细:\n{corpus}"}],temp=0.3,timeout=180)
    except Exception as e:
        body=f"（复盘生成失败：{str(e)[:100]}）"; log("doubao weekly fail")
    head=f"**懂她指数：{index if index is not None else '—'} 分**（已验证 {n} 条：应验{hit}/部分{part}/证伪{miss}）\n\n"
    ok=push_card(tat, f"🧪 Serenity 懂她周复盘（{datetime.now().strftime('%m-%d')}）", head+body, "purple")
    log(f"weekly push {'ok' if ok else 'fail'} index={index} verified={n}")
    # 3) 若复盘含 [需确认]，单独推稳定层改动确认卡
    if "[需确认]" in (body or ""):
        proposals="\n".join(l for l in body.split("\n") if "[需确认]" in l)
        actions=[
            {"tag":"button","text":{"tag":"plain_text","content":"✅ 同意"},"type":"primary","value":{"action":"approve_stable_change"}},
            {"tag":"button","text":{"tag":"plain_text","content":"❌ 不同意"},"type":"danger","value":{"action":"reject_stable_change"}},
        ]
        push_card(tat,"⚠️ 稳定层改动待你确认", "系统建议修改 serenity-master 的核心(心智模型/表达)。请点下方按钮或直接回复我：\n\n"+proposals, "red", actions)
        log("stable-layer confirm card pushed")
    # 4) 更新可信度地图文件（追加一行时间戳记录，留痕）
    try:
        cm=os.path.join(BASE_DIR,"credibility_log.md")
        open(cm,"a").write(f"\n## {datetime.now().strftime('%Y-%m-%d')} 懂她指数={index} 验证={n}(应验{hit}/部分{part}/证伪{miss})\n")
    except Exception: pass

if __name__=="__main__":
    main()
