#!/usr/bin/env python3
from __future__ import annotations

import json, os, re, sys, time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
CONFIG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
OUT = ROOT / "events.json"
DATA_JS = ROOT / "events-data.js"

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/152 Safari/537.36"
S = requests.Session()
S.headers.update({"User-Agent": UA, "Accept-Language": "ja,en;q=0.8"})

WALKER_LIST_URLS = [
    "https://www.walkerplus.com/event_list/ar0700/",
    "https://www.walkerplus.com/event_list/ar0700/eg0127/",
    "https://www.walkerplus.com/event_list/ar0700/eg0135/",
    "https://www.walkerplus.com/event_list/ar0700/eg0126/",
]

def fetch(url, headers=None, params=None):
    r = S.get(url, headers=headers, params=params, timeout=30)
    r.raise_for_status()
    return r

def flatten_jsonld(obj):
    if isinstance(obj, list):
        for x in obj:
            yield from flatten_jsonld(x)
    elif isinstance(obj, dict):
        typ = obj.get("@type")
        if typ == "Event" or (isinstance(typ, list) and "Event" in typ):
            yield obj
        if "@graph" in obj:
            yield from flatten_jsonld(obj["@graph"])

def iso_date(v):
    if not v:
        return None
    m = re.match(r"(\d{4}-\d{2}-\d{2})", str(v))
    return m.group(1) if m else None

def area_from_text(text):
    aliases = [
        ("大阪府", "大阪"), ("京都府", "京都"), ("兵庫県", "兵庫"),
        ("奈良県", "奈良"), ("滋賀県", "滋賀"), ("和歌山県", "和歌山"),
        ("神戸", "兵庫"), ("大阪", "大阪"), ("京都", "京都"),
        ("奈良", "奈良"), ("滋賀", "滋賀"), ("和歌山", "和歌山"),
    ]
    for needle, area in aliases:
        if needle in text:
            return area
    return "関西"

def classify(text):
    if re.search(r"鉄道|電車|列車|新幹線|京阪|阪急|近鉄|JR|南海|阪神", text, re.I):
        return "rail"
    if re.search(r"\bAI\b|生成AI|\bIT\b|DX|XR|VR|AR|ガジェット|PC", text, re.I):
        return "tech"
    if re.search(r"アニメ|マンガ|漫画|声優|コスプレ|ゲーム|eスポーツ", text, re.I):
        return "anime"
    if re.search(r"グルメ|フード|食フェス|ラーメン|カレー|スイーツ|パン|肉フェス|日本酒|ビール|食べ放題", text, re.I):
        return "food"
    if re.search(r"展示|展覧|博物館|美術館", text):
        return "exhibition"
    return "tourism"

def score(text, category):
    base = {
        "rail": 72, "tech": 70, "anime": 72, "food": 68,
        "exhibition": 56, "tourism": 50
    }.get(category, 50)

    low = text.lower()
    for k, v in CONFIG.get("interest_keywords", {}).items():
        if k.lower() in low:
            base += v
    for k, v in CONFIG.get("negative_keywords", {}).items():
        if k.lower() in low:
            base += v
    return max(35, min(99, base))

def make_tags(text, cat):
    tags = []
    mapping = [
        ("鉄道", r"鉄道|電車|列車|新幹線|京阪|阪急|近鉄|南海"),
        ("AI・IT", r"\bAI\b|生成AI|\bIT\b|DX|XR|VR|AR|ガジェット"),
        ("アニメ", r"アニメ|マンガ|漫画|声優|コスプレ"),
        ("ゲーム", r"ゲーム|eスポーツ"),
        ("グルメ", r"グルメ|フード|ラーメン|カレー|スイーツ|パン|肉|日本酒|ビール"),
        ("展示", r"展示|展覧|博物館|美術館"),
        ("フェス", r"フェス|祭り|フェア|マルシェ"),
    ]
    for name, pat in mapping:
        if re.search(pat, text, re.I):
            tags.append(name)

    if not tags:
        tags = [{
            "rail": "鉄道",
            "tech": "AI・IT",
            "anime": "アニメ・ゲーム",
            "food": "食・グルメ",
            "exhibition": "展示",
            "tourism": "イベント"
        }.get(cat, "イベント")]

    return tags[:4]

def extract_image_from_jsonld(ev):
    img = ev.get("image")
    if isinstance(img, str):
        return img
    if isinstance(img, list):
        for item in img:
            if isinstance(item, str):
                return item
            if isinstance(item, dict):
                if item.get("url"):
                    return item["url"]
                if item.get("contentUrl"):
                    return item["contentUrl"]
    if isinstance(img, dict):
        return img.get("url") or img.get("contentUrl")
    return None

def extract_meta_image(soup):
    for selector in [
        ('meta', {'property': 'og:image'}),
        ('meta', {'name': 'og:image'}),
        ('meta', {'name': 'twitter:image'}),
        ('meta', {'property': 'twitter:image'}),
    ]:
        tag = soup.find(*selector)
        if tag and tag.get('content'):
            return tag['content']
    return None

# -------------------------
# Walkerplus
# -------------------------
def extract_detail_urls(html):
    soup = BeautifulSoup(html, "html.parser")
    urls = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if re.search(r"/event/ar\d+e\d+/?", href):
            u = urljoin("https://www.walkerplus.com", href)
            if u not in urls:
                urls.append(u)
    return urls

def parse_walker_event(url):
    html = fetch(url).text
    soup = BeautifulSoup(html, "html.parser")

    meta_image = extract_meta_image(soup)

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

            if isinstance(loc, list):
                loc = loc[0] if loc else {}

            venue = loc.get("name", "") if isinstance(loc, dict) else ""
            addr = loc.get("address", {}) if isinstance(loc, dict) else {}
            addrtext = json.dumps(addr, ensure_ascii=False) if isinstance(addr, dict) else str(addr)
            desc = BeautifulSoup(str(ev.get("description", "")), "html.parser").get_text(" ", strip=True)
            image_url = extract_image_from_jsonld(ev) or meta_image
            full = " ".join([title or "", venue, addrtext, desc])

            if title and sd:
                cat = classify(full)
                return {
                    "title": title,
                    "start_date": sd,
                    "end_date": ed,
                    "area": area_from_text(full),
                    "venue": venue or area_from_text(full),
                    "category": cat,
                    "score": score(full, cat),
                    "tags": make_tags(full, cat),
                    "description": desc[:140] or "詳しくはイベント情報ページをご確認ください。",
                    "image_url": image_url,
                    "source": "ウォーカープラス",
                    "source_url": url,
                }

    return None

def collect_walker():
    urls = []
    events = []

    for list_url in WALKER_LIST_URLS:
        try:
            html = fetch(list_url).text
            for u in extract_detail_urls(html):
                if u not in urls:
                    urls.append(u)
        except Exception as e:
            print(f"[Walker] list error: {list_url}: {e}", file=sys.stderr)

    for u in urls[:160]:
        try:
            ev = parse_walker_event(u)
            if ev:
                events.append(ev)
        except Exception as e:
            print(f"[Walker] detail error: {u}: {e}", file=sys.stderr)
        time.sleep(0.15)

    return events

# -------------------------
# X
# -------------------------
JP_TZ = timezone(timedelta(hours=9))

def parse_japanese_event_date(text, created_at=None):
    base = datetime.now(JP_TZ)

    if created_at:
        try:
            base = datetime.fromisoformat(created_at.replace("Z", "+00:00")).astimezone(JP_TZ)
        except Exception:
            pass

    patterns = [
        re.compile(r"(?P<y>20\d{2})[年./-](?P<m>\d{1,2})[月./-](?P<d>\d{1,2})日?"),
        re.compile(r"(?<!\d)(?P<m>\d{1,2})月(?P<d>\d{1,2})日"),
        re.compile(r"(?<!\d)(?P<m>\d{1,2})/(?P<d>\d{1,2})(?!\d)"),
    ]

    for pat in patterns:
        m = pat.search(text)
        if not m:
            continue

        gd = m.groupdict()
        y = int(gd.get("y") or base.year)
        mo = int(gd["m"])
        da = int(gd["d"])

        try:
            dt = date(y, mo, da)
        except ValueError:
            continue

        if not gd.get("y") and dt < base.date() - timedelta(days=45):
            try:
                dt = date(y + 1, mo, da)
            except ValueError:
                pass

        return dt.isoformat()

    return None

def x_place_from_text(text):
    venue_patterns = [
        r"(?:会場|場所|開催場所)[：:\s]*([^\n。]{2,45})",
        r"於[：:\s]*([^\n。]{2,45})",
    ]

    for pat in venue_patterns:
        m = re.search(pat, text)
        if m:
            return m.group(1).strip(" #　")
    return area_from_text(text)

def is_likely_event_post(text):
    if not re.search(r"イベント|開催|フェス|フェア|祭|展示|展覧|ライブ|セミナー|マルシェ|コラボ|POP.?UP|ポップアップ", text, re.I):
        return False
    if not any(x in text for x in ["大阪", "京都", "兵庫", "神戸", "奈良", "滋賀", "和歌山"]):
        return False
    return True

def clean_x_title(text):
    lines = [re.sub(r"https?://\S+", "", x).strip() for x in text.splitlines()]
    lines = [x for x in lines if x]
    title = lines[0] if lines else "Xで告知されたイベント"
    title = re.sub(r"^[【\[]?(?:告知|お知らせ|イベント情報)[】\]]?[！!：:\s]*", "", title)
    return title[:64]

def collect_x():
    token = os.getenv("X_BEARER_TOKEN", "").strip()
    if not token:
        print("[X] X_BEARER_TOKEN が未設定のためX収集をスキップします。", file=sys.stderr)
        return []

    api = "https://api.x.com/2/tweets/search/recent"
    headers = {"Authorization": f"Bearer {token}"}
    out = []

    for query in CONFIG.get("x_queries", []):
        params = {
            "query": query,
            "max_results": max(10, min(100, int(CONFIG.get("x_max_results_per_query", 50)))),
            "tweet.fields": "created_at,author_id,lang,entities,public_metrics,attachments",
            "expansions": "author_id,attachments.media_keys",
            "user.fields": "username,name,verified",
            "media.fields": "type,url,preview_image_url",
        }

        try:
            r = requests.get(api, headers=headers, params=params, timeout=30)
            if r.status_code in (401, 403, 429):
                print(f"[X] API status {r.status_code}: {r.text[:300]}", file=sys.stderr)
                continue
            r.raise_for_status()
            payload = r.json()
        except Exception as e:
            print(f"[X] query error: {e}", file=sys.stderr)
            continue

        users = {u["id"]: u for u in payload.get("includes", {}).get("users", [])}
        medias = {m["media_key"]: m for m in payload.get("includes", {}).get("media", [])}

        for tw in payload.get("data", []):
            text = tw.get("text", "")
            if not is_likely_event_post(text):
                continue

            sd = parse_japanese_event_date(text, tw.get("created_at"))
            if not sd:
                continue
            if sd < date.today().isoformat():
                continue
            if "道の駅" in text:
                continue

            author = users.get(tw.get("author_id"), {})
            username = author.get("username", "")
            source_url = f"https://x.com/{username}/status/{tw['id']}" if username else f"https://x.com/i/web/status/{tw['id']}"
            full = text
            cat = classify(full)

            image_url = None
            media_keys = tw.get("attachments", {}).get("media_keys", []) if isinstance(tw.get("attachments"), dict) else []
            for key in media_keys:
                media = medias.get(key, {})
                image_url = media.get("url") or media.get("preview_image_url")
                if image_url:
                    break

            out.append({
                "title": clean_x_title(text),
                "start_date": sd,
                "end_date": sd,
                "area": area_from_text(full),
                "venue": x_place_from_text(full),
                "category": cat,
                "score": score(full, cat),
                "tags": make_tags(full, cat),
                "description": re.sub(r"https?://\S+", "", text).replace("\n", " ")[:150],
                "image_url": image_url,
                "source": f"X @{username}" if username else "X",
                "source_url": source_url,
            })

        time.sleep(0.5)

    return out

# -------------------------
# Merge
# -------------------------
def normalize_title(s):
    s = re.sub(r"\s+", "", s or "")
    s = re.sub(r"[【】\[\]（）()「」『』・!！?？:：\-ー]", "", s)
    return s.lower()

def dedupe(events):
    result = []
    seen = set()
    for e in sorted(events, key=lambda x: (-x.get("score", 0), x.get("start_date", "9999"))):
        key = (normalize_title(e.get("title", ""))[:30], e.get("start_date", ""), e.get("area", ""))
        if key in seen:
            continue
        seen.add(key)
        result.append(e)
    return result

def main():
    events = []
    events.extend(collect_walker())
    events.extend(collect_x())

    today = date.today().isoformat()
    events = [
        e for e in events
        if (e.get("end_date") or e.get("start_date") or "") >= today
        and "道の駅" not in ((e.get("title") or "") + " " + (e.get("description") or ""))
    ]
    events = dedupe(events)[:int(CONFIG.get("max_events", 80))]

    if not events:
        print("イベント取得結果が0件のため既存events.jsonを保持します。", file=sys.stderr)
        sys.exit(2)

    json_text = json.dumps(events, ensure_ascii=False, indent=2)

    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(json_text, encoding="utf-8")
    tmp.replace(OUT)

    DATA_JS.write_text(
        "window.EVENT_DATA = " + json_text + ";\n",
        encoding="utf-8"
    )

    print(f"{len(events)}件を events.json / events-data.js に保存しました。")
    print("Walkerplus / X 統合。image_url 付き。")

if __name__ == "__main__":
    main()
