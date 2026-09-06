#!/usr/bin/env python3
from __future__ import annotations

import json, os, re, sys, time, hashlib, mimetypes
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

MULTI_SOURCES = [
    # 大阪中心：大型会場・商業施設
    {"name":"大阪観光局","url":"https://osaka-info.jp/event/","base":"https://osaka-info.jp","area":"大阪","link_patterns":[r"/event/[^?#]+"],"max_links":100},
    {"name":"インテックス大阪","url":"https://www.intex-osaka.com/jp/event/","base":"https://www.intex-osaka.com","area":"大阪","link_patterns":[r"/jp/event/[^?#]+", r"/event/[^?#]+"],"max_links":100},
    {"name":"ATC","url":"https://www.atc-co.com/event/","base":"https://www.atc-co.com","area":"大阪","link_patterns":[r"/event/[^?#]+"],"max_links":100},
    {"name":"グランフロント大阪","url":"https://www.grandfront-osaka.jp/event/","base":"https://www.grandfront-osaka.jp","area":"大阪","link_patterns":[r"/event/[^?#]+"],"max_links":100},
    {"name":"なんばパークス","url":"https://nambaparks.com/event","base":"https://nambaparks.com","area":"大阪","link_patterns":[r"/event/[^?#]+", r"/event\?[^#]+"],"max_links":100},
    {"name":"LUCUA大阪","url":"https://www.lucua.jp/topics_category/event_info/","base":"https://www.lucua.jp","area":"大阪","link_patterns":[r"/topics/[^?#]+", r"/topics_category/[^?#]+"],"max_links":100},

    # 百貨店催事
    {"name":"阪急うめだ本店","url":"https://www.hankyu-dept.co.jp/honten/event/index.html","base":"https://www.hankyu-dept.co.jp","area":"大阪","link_patterns":[r"/honten/[^?#]+", r"/event/[^?#]+"],"max_links":100},
    {"name":"大丸梅田店","url":"https://www.daimaru.co.jp/umedamise/event/","base":"https://www.daimaru.co.jp","area":"大阪","link_patterns":[r"/umedamise/[^?#]+"],"max_links":100},
    {"name":"あべのハルカス近鉄本店","url":"https://abenoharukas.d-kintetsu.co.jp/eventschedule/","base":"https://abenoharukas.d-kintetsu.co.jp","area":"大阪","link_patterns":[r"/eventschedule/[^?#]*", r"/event/[^?#]+", r"/news/[^?#]+"],"max_links":100},

    # アニメ・ポップカルチャー公式
    {"name":"アニメイト","url":"https://www.animate.co.jp/event/","base":"https://www.animate.co.jp","area":"関西","link_patterns":[r"/event/[^?#]+", r"/onlyshop/[^?#]+", r"/fair/[^?#]+"],"max_links":120},
    {"name":"アニメイト大阪日本橋","url":"https://www.animate.co.jp/shop/nipponbashi/","base":"https://www.animate.co.jp","area":"大阪","link_patterns":[r"/event/[^?#]+", r"/onlyshop/[^?#]+", r"/fair/[^?#]+"],"max_links":80},

    # 車イベント公式
    {"name":"大阪オートメッセ","url":"https://www.automesse.jp/","base":"https://www.automesse.jp","area":"大阪","link_patterns":[r"/20\d{2}/[^?#]+", r"/event[^?#]*", r"/news/[^?#]+"],"max_links":80},

    # 鉄道会社公式
    {"name":"JR西日本","url":"https://www.jr-odekake.net/","base":"https://www.jr-odekake.net","area":"関西","link_patterns":[r"/navi/[^?#]+", r"/railroad/[^?#]+", r"/event/[^?#]+"],"max_links":100},
    {"name":"近鉄","url":"https://www.kintetsu.co.jp/railway/","base":"https://www.kintetsu.co.jp","area":"関西","link_patterns":[r"/railway/[^?#]+", r"/event/[^?#]+", r"/news/[^?#]+"],"max_links":100},
    {"name":"阪急電鉄","url":"https://www.hankyu.co.jp/area_info/","base":"https://www.hankyu.co.jp","area":"関西","link_patterns":[r"/area_info/[^?#]+", r"/event/[^?#]+"],"max_links":100},
    {"name":"南海電鉄","url":"https://www.nankai.co.jp/","base":"https://www.nankai.co.jp","area":"大阪","link_patterns":[r"/traffic/[^?#]+", r"/event/[^?#]+", r"/news/[^?#]+"],"max_links":100},

    # 大阪周辺の補助ソース
    {"name":"Feel KOBE","url":"https://www.feel-kobe.jp/event/","base":"https://www.feel-kobe.jp","area":"兵庫","link_patterns":[r"/event/[^?#]+"],"max_links":60},
    {"name":"京都観光Navi","url":"https://ja.kyoto.travel/event/","base":"https://ja.kyoto.travel","area":"京都","link_patterns":[r"/event/[^?#]+"],"max_links":60},
    {"name":"Peatix","url":"https://peatix.com/search?q=%E5%A4%A7%E9%98%AA","base":"https://peatix.com","area":"大阪","link_patterns":[r"/event/\d+", r"/event/[^?#]+"],"max_links":60},
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
        ("滋賀県", "滋賀"), ("和歌山県", "和歌山"),
        ("神戸", "兵庫"), ("大阪", "大阪"), ("京都", "京都"),
        ("滋賀", "滋賀"), ("和歌山", "和歌山"),
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
    if re.search(r"自動車|クルマ|モーターショー|オートショー|カスタムカー|チューニングカー|旧車|クラシックカー|スーパーカー|スポーツカー|電気自動車|モータースポーツ|サーキット|ラリー|ドリフト|試乗会|カーイベント|カーミーティング", text, re.I):
        return "car"
    if re.search(r"グルメ|フード|食フェス|ラーメン|カレー|スイーツ|パン|肉フェス|日本酒|ビール|食べ放題", text, re.I):
        return "food"
    if re.search(r"展示|展覧|博物館|美術館", text):
        return "exhibition"
    return "tourism"

def score(text, category):
    base = {
        "rail": 72, "tech": 70, "anime": 72, "car": 72, "food": 68,
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
        ("クルマ", r"自動車|クルマ|モーターショー|オートショー|カスタムカー|旧車|クラシックカー|スーパーカー|スポーツカー|電気自動車|試乗会"),
        ("モータースポーツ", r"モータースポーツ|レース|サーキット|ラリー|ドリフト"),
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
            "car": "クルマ",
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
# 汎用イベントサイト収集
# Google検索のイベント表示で利用される Event JSON-LD を中心に解析
# -------------------------
def is_probable_event_link(href, patterns):
    if not href:
        return False
    if href.startswith(("#", "mailto:", "javascript:")):
        return False
    return any(re.search(pat, href, re.I) for pat in patterns)

def extract_generic_detail_urls(html, source):
    soup = BeautifulSoup(html, "html.parser")
    urls, seen = [], set()
    for a in soup.find_all("a", href=True):
        href = a.get("href", "").strip()
        if not is_probable_event_link(href, source.get("link_patterns", [r"/event/"])):
            continue
        u = urljoin(source["base"], href)
        if u.rstrip("/") == source["url"].rstrip("/") or u in seen:
            continue
        seen.add(u)
        urls.append(u)
        if len(urls) >= int(source.get("max_links", 60)):
            break
    return urls

def parse_event_jsonld_page(url, source_name, forced_area=None):
    html = fetch(url).text
    soup = BeautifulSoup(html, "html.parser")
    meta_image = extract_meta_image(soup)
    found = []

    for script in soup.find_all("script", type="application/ld+json"):
        raw = script.get_text(strip=True)
        if not raw:
            continue
        try:
            obj = json.loads(raw)
        except Exception:
            continue

        for ev in flatten_jsonld(obj):
            title = ev.get("name")
            sd = iso_date(ev.get("startDate"))
            ed = iso_date(ev.get("endDate")) or sd
            if not title or not sd:
                continue

            loc = ev.get("location") or {}
            if isinstance(loc, list):
                loc = loc[0] if loc else {}

            venue = ""
            address_text = ""
            if isinstance(loc, dict):
                venue = str(loc.get("name") or "").strip()
                addr = loc.get("address") or {}
                if isinstance(addr, dict):
                    address_text = " ".join(str(addr.get(k) or "") for k in ["addressRegion","addressLocality","streetAddress"]).strip()
                else:
                    address_text = str(addr)

            desc = BeautifulSoup(str(ev.get("description", "")), "html.parser").get_text(" ", strip=True)
            image_url = extract_image_from_jsonld(ev) or meta_image
            full = " ".join([title, venue, address_text, desc])
            area = area_from_text(full)
            if area == "関西" and forced_area:
                area = forced_area
            cat = classify(full)
            found.append({
                "title": title,
                "start_date": sd,
                "end_date": ed,
                "area": area,
                "venue": venue or area,
                "category": cat,
                "score": score(full, cat),
                "tags": make_tags(full, cat),
                "description": desc[:150] or "詳しくはイベント公式ページをご確認ください。",
                "image_url": image_url,
                "source": source_name,
                "source_url": url,
            })
    return found

def parse_simple_event_page(url, source_name, forced_area=None):
    html = fetch(url).text
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n", strip=True)

    h1 = soup.find("h1")
    title = h1.get_text(" ", strip=True) if h1 else ""
    if not title:
        ogt = soup.find("meta", property="og:title")
        title = ogt.get("content", "").strip() if ogt else ""
    if not title:
        return []

    start_date = None
    base_year = date.today().year
    patterns = [
        re.compile(r"(20\d{2})[年./-](\d{1,2})[月./-](\d{1,2})日?"),
        re.compile(r"(?<!\d)(\d{1,2})月(\d{1,2})日"),
    ]
    for pat in patterns:
        m = pat.search(text[:10000])
        if not m:
            continue
        try:
            if len(m.groups()) == 3:
                y, mo, da = map(int, m.groups())
            else:
                y = base_year
                mo, da = map(int, m.groups())
                if date(y, mo, da) < date.today() - timedelta(days=60):
                    y += 1
            start_date = date(y, mo, da).isoformat()
            break
        except Exception:
            pass

    if not start_date:
        return []

    kansai_tokens = ["大阪", "京都", "兵庫", "神戸", "滋賀", "和歌山"]
    if not any(x in text[:14000] for x in kansai_tokens) and forced_area == "関西":
        return []

    desc_meta = soup.find("meta", attrs={"name": "description"})
    desc = desc_meta.get("content", "").strip() if desc_meta else ""
    if not desc:
        desc = text.replace("\n", " ")[:150]

    image_url = extract_meta_image(soup)
    full = " ".join([title, desc, text[:5000]])
    area = area_from_text(full)
    if area == "関西" and forced_area:
        area = forced_area
    cat = classify(full)

    return [{
        "title": title[:100],
        "start_date": start_date,
        "end_date": start_date,
        "area": area,
        "venue": area,
        "category": cat,
        "score": score(full, cat),
        "tags": make_tags(full, cat),
        "description": desc[:150],
        "image_url": image_url,
        "source": source_name,
        "source_url": url,
    }]

def collect_generic_sources():
    events = []
    for source in MULTI_SOURCES:
        try:
            list_html = fetch(source["url"]).text
            try:
                events.extend(parse_event_jsonld_page(source["url"], source["name"], source.get("area")))
            except Exception:
                pass

            urls = extract_generic_detail_urls(list_html, source)
            print(f"[{source['name']}] detail candidates: {len(urls)}")
            for u in urls:
                try:
                    parsed = parse_event_jsonld_page(u, source["name"], source.get("area"))
                    if not parsed:
                        parsed = parse_simple_event_page(u, source["name"], source.get("area"))
                    events.extend(parsed)
                except Exception as e:
                    print(f"[{source['name']}] detail error: {u}: {e}", file=sys.stderr)
                time.sleep(0.12)
        except Exception as e:
            print(f"[{source['name']}] list error: {source['url']}: {e}", file=sys.stderr)
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
    if not any(x in text for x in ["大阪", "京都", "兵庫", "神戸", "滋賀", "和歌山"]):
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
# 画像をローカル保存
# -------------------------
IMAGE_DIR = ROOT / "images"
IMAGE_DIR.mkdir(exist_ok=True)

def image_extension(content_type, url):
    ctype = (content_type or "").split(";")[0].strip().lower()
    mapping = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
    }
    if ctype in mapping:
        return mapping[ctype]

    lower = (url or "").lower()
    for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
        if ext in lower:
            return ".jpg" if ext == ".jpeg" else ext
    return ".jpg"

def localize_event_image(event):
    """
    外部画像をGitHubリポジトリ内 images/ に保存。
    Fire TVは外部サイトへ直接画像アクセスしない。
    """
    url = (event.get("image_url") or "").strip()
    if not url:
        event["image_url"] = ""
        return event

    key_source = "|".join([
        event.get("title", ""),
        event.get("start_date", ""),
        event.get("source_url", ""),
        url,
    ])
    digest = hashlib.sha1(key_source.encode("utf-8")).hexdigest()[:18]

    try:
        r = S.get(
            url,
            timeout=30,
            stream=True,
            headers={
                "User-Agent": UA,
                "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
                "Referer": event.get("source_url", "") or "https://www.walkerplus.com/",
            }
        )
        r.raise_for_status()

        content_type = r.headers.get("content-type", "")
        if not content_type.lower().startswith("image/"):
            raise ValueError(f"not image: {content_type}")

        ext = image_extension(content_type, url)
        path = IMAGE_DIR / f"{digest}{ext}"

        # 大きすぎる画像は無制限に保存しない（最大8MB）
        total = 0
        with path.open("wb") as f:
            for chunk in r.iter_content(65536):
                if not chunk:
                    continue
                total += len(chunk)
                if total > 8 * 1024 * 1024:
                    raise ValueError("image too large")
                f.write(chunk)

        if total < 1024:
            path.unlink(missing_ok=True)
            raise ValueError("image too small")

        event["original_image_url"] = url
        event["image_url"] = f"images/{path.name}"
        return event

    except Exception as e:
        print(f"[Image] download error: {event.get('title')}: {e}", file=sys.stderr)
        event["image_url"] = ""
        return event

def localize_images(events):
    used = set()

    for event in events:
        localize_event_image(event)
        local = event.get("image_url", "")
        if local.startswith("images/"):
            used.add(Path(local).name)
        time.sleep(0.05)

    # 古い画像キャッシュを整理
    for p in IMAGE_DIR.iterdir():
        if p.name == ".gitkeep":
            continue
        if p.is_file() and p.name not in used:
            try:
                p.unlink()
            except Exception:
                pass

    return events



def apply_priority_bonus(event):
    # 大阪中心に順位を上げる
    bonus = 0
    area = event.get("area", "")
    if area == "大阪":
        bonus += 12
    elif area in ("兵庫", "京都"):
        bonus += 3

    source_bonus = CONFIG.get("source_bonus", {}).get(event.get("source", ""), 0)
    bonus += int(source_bonus or 0)
    event["score"] = max(35, min(99, int(event.get("score", 50)) + bonus))
    return event


# -------------------------
# 広告・セール・常設キャンペーン除外
# -------------------------
def is_noise_event(event):
    """
    サイネージに不要な広告・単なるセール・常設キャンペーンを除外する。
    """
    title = event.get("title", "") or ""
    desc = event.get("description", "") or ""
    venue = event.get("venue", "") or ""
    text = " ".join([title, desc, venue])

    excludes = CONFIG.get("exclude_keywords", [])
    event_intents = CONFIG.get("event_intent_keywords", [])

    low = text.lower()

    # 強い除外語
    for kw in excludes:
        if kw.lower() in low:
            # 「期間限定ショップ」「催事」等の明確なイベント性があれば一部救済
            if any(pos.lower() in low for pos in [
                "期間限定ショップ", "期間限定ストア", "ポップアップ", "pop up",
                "物産展", "催事", "展示", "展覧会", "イベント", "フェス",
                "試乗会", "モーターショー", "オートメッセ"
            ]):
                continue
            return True

    # タイトルが価格訴求だけのもの
    price_sale_patterns = [
        r"\d+%OFF",
        r"\d+％OFF",
        r"最大\d+%OFF",
        r"最大\d+％OFF",
        r"ポイント\d+倍",
        r"送料無料",
        r"クーポン",
    ]
    if any(re.search(p, text, re.I) for p in price_sale_patterns):
        return True

    # 常設展示・常設サービス
    if re.search(r"常設展|常設展示|常設コーナー|常設ショップ|常設店舗", text, re.I):
        return True

    # イベント性が弱いもの
    has_event_intent = any(kw.lower() in low for kw in event_intents)

    # 日付が1年近く続くものは、イベント性が弱ければ常設扱い
    try:
        sd = date.fromisoformat(event.get("start_date", ""))
        ed = date.fromisoformat(event.get("end_date", "") or event.get("start_date", ""))
        duration = (ed - sd).days
        if duration > 240 and not has_event_intent:
            return True
    except Exception:
        pass

    # EC/オンラインだけのもの
    if re.search(r"オンラインショップ|オンラインストア|ECサイト|通販", text, re.I) and not has_event_intent:
        return True

    return False


def filter_noise_events(events):
    kept = []
    removed = 0
    for e in events:
        if is_noise_event(e):
            removed += 1
            print(f"[Filter] excluded: {e.get('title')}")
            continue
        kept.append(e)
    print(f"[Filter] removed {removed} noise entries")
    return kept


# -------------------------
# Merge
# -------------------------
def normalize_title(s):
    s = re.sub(r"\s+", "", s or "")
    s = re.sub(r"[【】\[\]（）()「」『』・!！?？:：\-ー]", "", s)
    return s.lower()

def dedupe(events):
    groups = {}
    for e in events:
        key = (normalize_title(e.get("title", ""))[:36], e.get("start_date", ""), e.get("area", ""))
        if key not in groups:
            groups[key] = dict(e)
            groups[key]["sources"] = [e.get("source")] if e.get("source") else []
            continue
        cur = groups[key]
        if e.get("source") and e.get("source") not in cur.get("sources", []):
            cur.setdefault("sources", []).append(e.get("source"))
        if e.get("score", 0) > cur.get("score", 0):
            old_image = cur.get("image_url")
            srcs = cur.get("sources", [])
            cur.update(e)
            cur["sources"] = srcs
            if not cur.get("image_url") and old_image:
                cur["image_url"] = old_image
        else:
            if not cur.get("image_url") and e.get("image_url"):
                cur["image_url"] = e.get("image_url")
            if len(cur.get("description", "")) < 40 and e.get("description"):
                cur["description"] = e["description"]
    result = list(groups.values())
    for e in result:
        srcs = [x for x in e.pop("sources", []) if x]
        if len(srcs) > 1:
            e["source"] = " / ".join(srcs[:3])
    result.sort(key=lambda x: (-x.get("score", 0), x.get("start_date", "9999")))
    return result

def main():
    events = []
    events.extend(collect_walker())
    events.extend(collect_generic_sources())
    events.extend(collect_x())

    today = date.today().isoformat()
    events = [
        e for e in events
        if (e.get("end_date") or e.get("start_date") or "") >= today
        and e.get("area") != "奈良"
        and "道の駅" not in ((e.get("title") or "") + " " + (e.get("description") or ""))
    ]
    events = [apply_priority_bonus(e) for e in events]
    events = filter_noise_events(events)
    events = dedupe(events)[:int(CONFIG.get("max_events", 100))]
    events = localize_images(events)

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
