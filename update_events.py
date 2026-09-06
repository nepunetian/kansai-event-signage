#!/usr/bin/env python3
"""
関西イベントサイネージ 自動更新スクリプト

- Walkerplus の関西イベント一覧からイベント詳細URLを収集
- 詳細ページの JSON-LD(Event) を優先して解析
- JSON-LD が無い場合はHTML本文から最低限の情報を抽出
- 終了済みイベントを除外
- config.json の興味キーワードからおすすめ度を算出
- 取得失敗時は既存 events.json を壊さない

実行:
    pip install requests beautifulsoup4
    python update_events.py
"""
from __future__ import annotations
import json, re, sys, time
from datetime import datetime, date
from pathlib import Path
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
CONFIG = json.loads((ROOT/"config.json").read_text(encoding="utf-8"))
OUT = ROOT/"events.json"

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/152 Safari/537.36"
S = requests.Session()
S.headers.update({"User-Agent":UA,"Accept-Language":"ja,en;q=0.8"})

# 関西総合 + 興味に近いカテゴリを複数巡回
LIST_URLS = [
    "https://www.walkerplus.com/event_list/ar0700/",
    "https://www.walkerplus.com/event_list/ar0700/eg0127/", # アニメ・ゲーム
    "https://www.walkerplus.com/event_list/ar0700/eg0126/", # 展示会
    "https://www.walkerplus.com/event_list/ar0700/eg0128/", # 展示会系（サイト変更時の補助）
]

def fetch(url):
    r = S.get(url, timeout=25)
    r.raise_for_status()
    return r.text

def flatten_jsonld(obj):
    if isinstance(obj, list):
        for x in obj: yield from flatten_jsonld(x)
    elif isinstance(obj, dict):
        if obj.get("@type") == "Event" or (isinstance(obj.get("@type"), list) and "Event" in obj["@type"]):
            yield obj
        if "@graph" in obj:
            yield from flatten_jsonld(obj["@graph"])

def iso_date(v):
    if not v: return None
    m = re.match(r"(\d{4}-\d{2}-\d{2})", str(v))
    return m.group(1) if m else None

def area_from_text(text):
    for p in CONFIG["regions"]:
        if p in text:
            return p.replace("府","").replace("県","")
    return "関西"

def classify(text):
    if re.search(r"鉄道|電車|列車|新幹線|駅\b|京阪|阪急|近鉄|JR", text, re.I): return "rail"
    if re.search(r"\bAI\b|生成AI|\bIT\b|DX|XR|VR|AR|ガジェット|PC", text, re.I): return "tech"
    if re.search(r"アニメ|ゲーム|マンガ|漫画", text): return "anime"
    if re.search(r"展示|展覧|博物館|美術館", text): return "exhibition"
    return "tourism"

def score(text, category):
    base = {"rail":72,"tech":70,"anime":66,"exhibition":58,"tourism":52}.get(category,50)
    for k,v in CONFIG["interest_keywords"].items():
        if k.lower() in text.lower(): base += v
    for k,v in CONFIG["negative_keywords"].items():
        if k.lower() in text.lower(): base += v
    return max(40,min(99,base))

def extract_detail_urls(html):
    soup = BeautifulSoup(html, "html.parser")
    urls = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if re.search(r"/event/ar\d+e\d+/?", href):
            u = urljoin("https://www.walkerplus.com", href)
            if u not in urls: urls.append(u)
    return urls

def parse_event(url):
    html = fetch(url)
    soup = BeautifulSoup(html, "html.parser")

    # JSON-LDを最優先
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            obj = json.loads(script.get_text(strip=True))
        except Exception:
            continue
        for ev in flatten_jsonld(obj):
            title = ev.get("name")
            sd = iso_date(ev.get("startDate"))
            ed = iso_date(ev.get("endDate")) or sd
            loc = ev.get("location") or {}
            if isinstance(loc, list): loc = loc[0] if loc else {}
            venue = loc.get("name","") if isinstance(loc,dict) else ""
            addr = loc.get("address",{}) if isinstance(loc,dict) else {}
            addrtext = json.dumps(addr, ensure_ascii=False) if isinstance(addr,dict) else str(addr)
            desc = BeautifulSoup(str(ev.get("description","")), "html.parser").get_text(" ", strip=True)
            full = " ".join([title or "",venue,addrtext,desc])
            if title and sd:
                cat = classify(full)
                return {
                    "title":title,
                    "start_date":sd,
                    "end_date":ed,
                    "area":area_from_text(full),
                    "venue":venue or area_from_text(full),
                    "category":cat,
                    "score":score(full,cat),
                    "tags":make_tags(full,cat),
                    "description":desc[:120] or "詳しくはイベント公式情報をご確認ください。",
                    "source":"ウォーカープラス",
                    "source_url":url
                }

    # フォールバック: 見えているテキストを解析
    text = soup.get_text("\n", strip=True)
    h1 = soup.find("h1")
    title = h1.get_text(" ",strip=True) if h1 else ""
    dm = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日.*?(?:～|〜|-).*?(?:(\d{4})年)?(\d{1,2})月(\d{1,2})日", text)
    one = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", text)
    if not title or not one: return None
    def dstr(y,m,d): return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
    sd = dstr(*one.groups())
    ed = sd
    if dm:
        y1,m1,d1,y2,m2,d2 = dm.groups()
        ed = dstr(y2 or y1,m2,d2)
    venue = ""
    pm = re.search(r"場所\s+関西\s+(大阪府|京都府|兵庫県|奈良県|滋賀県|和歌山県)\s+([^\n]+)", text)
    if pm: venue = pm.group(2).strip()
    full = title+" "+text[:4000]
    cat=classify(full)
    return {
        "title":title,"start_date":sd,"end_date":ed,
        "area":area_from_text(full),"venue":venue or area_from_text(full),
        "category":cat,"score":score(full,cat),"tags":make_tags(full,cat),
        "description":"詳しくはイベント情報ページをご確認ください。",
        "source":"ウォーカープラス","source_url":url
    }

def make_tags(text, cat):
    tags=[]
    mapping=[
        ("鉄道",r"鉄道|電車|列車|新幹線|京阪|阪急|近鉄"),
        ("AI・IT",r"\bAI\b|生成AI|\bIT\b|DX|XR|VR|AR"),
        ("アニメ",r"アニメ"),
        ("ゲーム",r"ゲーム"),
        ("展示",r"展示|展覧|博物館|美術館"),
        ("観光",r"観光|祭り|フェア|マルシェ"),
    ]
    for name,pat in mapping:
        if re.search(pat,text,re.I): tags.append(name)
    if not tags:
        tags=[{"rail":"鉄道","tech":"AI・IT","anime":"アニメ・ゲーム","exhibition":"展示","tourism":"イベント"}.get(cat,"イベント")]
    return tags[:4]

def main():
    today = date.today().isoformat()
    detail_urls=[]
    errors=[]
    for list_url in LIST_URLS:
        try:
            for u in extract_detail_urls(fetch(list_url)):
                if u not in detail_urls: detail_urls.append(u)
        except Exception as e:
            errors.append(f"{list_url}: {e}")

    events=[]
    for i,u in enumerate(detail_urls[:100]):
        try:
            ev=parse_event(u)
            if ev and (ev["end_date"] or ev["start_date"]) >= today:
                events.append(ev)
        except Exception as e:
            errors.append(f"{u}: {e}")
        time.sleep(0.25)

    # 重複排除
    uniq={}
    for e in events:
        key=(e["title"],e["start_date"])
        if key not in uniq or e["score"]>uniq[key]["score"]:
            uniq[key]=e
    events=list(uniq.values())
    events.sort(key=lambda e:(-e["score"],e["start_date"]))
    events=events[:int(CONFIG.get("max_events",60))]

    if not events:
        print("イベントを1件も取得できなかったため既存events.jsonを保持します。", file=sys.stderr)
        for x in errors[-10:]: print(x,file=sys.stderr)
        sys.exit(2)

    tmp=OUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(events,ensure_ascii=False,indent=2),encoding="utf-8")
    tmp.replace(OUT)
    print(f"{len(events)}件を更新しました。")
    if errors:
        print(f"一部取得失敗: {len(errors)}件", file=sys.stderr)

if __name__=="__main__":
    main()
