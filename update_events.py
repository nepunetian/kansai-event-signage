#!/usr/bin/env python3
from __future__ import annotations

import json, os, re, sys, time, hashlib, mimetypes, xml.etree.ElementTree as ET, html as html_lib
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

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

    {"name":"ATCトップ","url":"https://www.atc-co.com/","base":"https://www.atc-co.com","area":"大阪","link_patterns":[r"/event/[^?#]+"],"max_links":120,"max_sitemap_links":0},
    {"name":"ATC","url":"https://www.atc-co.com/event/","base":"https://www.atc-co.com","area":"大阪","link_patterns":[r"/event/[^?#]+"],"max_links":100},
    {"name":"グランフロント大阪","url":"https://www.grandfront-osaka.jp/event/","base":"https://www.grandfront-osaka.jp","area":"大阪","link_patterns":[r"/event/[^?#]+"],"max_links":100},
    {"name":"なんばパークス","url":"https://nambaparks.com/event","base":"https://nambaparks.com","area":"大阪","link_patterns":[r"/event/[^?#]+", r"/event\?[^#]+"],"max_links":100},
    {"name":"LUCUA大阪","url":"https://www.lucua.jp/topics_category/event_info/","base":"https://www.lucua.jp","area":"大阪","link_patterns":[r"/topics/[^?#]+", r"/topics_category/[^?#]+"],"max_links":100},

    # 百貨店催事
    {"name":"阪急うめだ本店","url":"https://www.hankyu-dept.co.jp/honten/event/index.html","base":"https://www.hankyu-dept.co.jp","area":"大阪","link_patterns":[r"/honten/[^?#]+", r"/event/[^?#]+"],"max_links":100},
    {"name":"大丸梅田店","url":"https://www.daimaru.co.jp/umedamise/event/","base":"https://www.daimaru.co.jp","area":"大阪","link_patterns":[r"/umedamise/[^?#]+"],"max_links":100},
    {"name":"あべのハルカス近鉄本店","url":"https://abenoharukas.d-kintetsu.co.jp/eventschedule/","base":"https://abenoharukas.d-kintetsu.co.jp","area":"大阪","link_patterns":[r"/eventschedule/[^?#]*", r"/event/[^?#]+", r"/news/[^?#]+"],"max_links":100},

    # アニメ・ポップカルチャー公式
    {"name":"アニメイト大阪日本橋","url":"https://www.animate.co.jp/onlyshop/search/relation_shop%3A105/","base":"https://www.animate.co.jp","area":"大阪","link_patterns":[r"/onlyshop/\d+/", r"/gratte/\d+/", r"/fair/\d+/"],"max_links":120},

    # 車イベント公式
    {"name":"大阪オートメッセ","url":"https://www.automesse.jp/","base":"https://www.automesse.jp","area":"大阪","link_patterns":[r"/20\d{2}/[^?#]+", r"/event[^?#]*", r"/news/[^?#]+"],"max_links":80},

    # 鉄道会社公式
    {"name":"JR西日本","url":"https://www.jr-odekake.net/","base":"https://www.jr-odekake.net","area":"関西","link_patterns":[r"/navi/[^?#]+", r"/railroad/[^?#]+", r"/event/[^?#]+"],"max_links":100},
    {"name":"近鉄","url":"https://www.kintetsu.co.jp/railway/","base":"https://www.kintetsu.co.jp","area":"関西","link_patterns":[r"/railway/[^?#]+", r"/event/[^?#]+", r"/news/[^?#]+"],"max_links":100},
    {"name":"阪急電鉄","url":"https://www.hankyu.co.jp/area_info/","base":"https://www.hankyu.co.jp","area":"関西","link_patterns":[r"/area_info/[^?#]+", r"/event/[^?#]+"],"max_links":100},
    {"name":"南海電鉄","url":"https://www.nankai.co.jp/","base":"https://www.nankai.co.jp","area":"大阪","link_patterns":[r"/traffic/[^?#]+", r"/event/[^?#]+", r"/news/[^?#]+"],"max_links":100},


    {"name":"セブンパーク天美","url":"https://amami.sevenpark.jp/event/","base":"https://amami.sevenpark.jp","area":"大阪","link_patterns":[r"/event/\d+/"],"max_links":140},

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
    """
    主カテゴリ判定。
    短い英字（AR/VR/AI/EV等）は必ず単語境界を付けて誤爆を防ぐ。
    """
    t = text or ""

    if re.search(
        r"鉄道|電車|列車|新幹線|鉄道模型|駅弁|京阪電車|阪急電鉄|近鉄|JR西日本|南海電鉄|阪神電車",
        t, re.I
    ):
        return "rail"

    if re.search(
        r"生成AI|人工知能|ChatGPT|LLM|DX|ガジェット|パソコン|スマートフォン|"
        r"(?<![A-Za-z])AI(?![A-Za-z])|(?<![A-Za-z])IT(?![A-Za-z])|"
        r"(?<![A-Za-z])XR(?![A-Za-z])|(?<![A-Za-z])VR(?![A-Za-z])|"
        r"(?<![A-Za-z])AR(?![A-Za-z])|(?<![A-Za-z])PC(?![A-Za-z])",
        t, re.I
    ):
        return "tech"

    if re.search(
        r"アニメ|マンガ|漫画|声優|コスプレ|コミック|キャラクター|"
        r"ゲーム(?:大会|イベント|フェス|体験|展示)?|eスポーツ|アニメイト|オンリーショップ",
        t, re.I
    ):
        return "anime"

    if re.search(
        r"モーターショー|オートメッセ|オートショー|カスタムカー|チューニングカー|"
        r"旧車|クラシックカー|スーパーカー|スポーツカー|電気自動車|EV車|"
        r"モータースポーツ|サーキット|ラリー|ドリフト|試乗会|カーイベント|カーミーティング|"
        r"自動車展示",
        t, re.I
    ):
        return "car"

    if re.search(
        r"グルメ(?:フェス|イベント)?|フード(?:フェス|イベント|コート)?|食フェス|"
        r"ラーメン(?:祭|フェス|博|イベント)?|カレー(?:祭|フェス|博|イベント)?|"
        r"スイーツ(?:フェア|フェス|イベント)?|パン(?:祭|フェス|マルシェ|イベント)?|"
        r"肉フェス|日本酒(?:祭|フェス|イベント)?|ビール(?:祭|フェス|イベント)?|"
        r"物産展|北海道展|駅弁大会",
        t, re.I
    ):
        return "food"

    if re.search(
        r"展覧会|企画展|特別展|美術展|写真展|博物館|美術館|アート展|原画展",
        t, re.I
    ):
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
    """
    タグは高信頼キーワードだけ。
    主カテゴリタグ + 明確な副タグのみ付与する。
    最大3個。
    """
    t = text or ""
    tags = []

    primary = {
        "rail": "鉄道",
        "tech": "AI・IT",
        "anime": "アニメ・ゲーム",
        "car": "クルマ",
        "food": "食・グルメ",
        "exhibition": "展示",
        "tourism": "イベント",
    }
    tags.append(primary.get(cat, "イベント"))

    # カテゴリ内の詳細タグ
    secondary_rules = [
        ("鉄道模型", r"鉄道模型|Nゲージ|HOゲージ"),
        ("新幹線", r"新幹線"),
        ("駅弁", r"駅弁"),

        ("生成AI", r"生成AI|ChatGPT|LLM"),
        ("XR", r"(?<![A-Za-z])XR(?![A-Za-z])|(?<![A-Za-z])VR(?![A-Za-z])|(?<![A-Za-z])AR(?![A-Za-z])"),
        ("ガジェット", r"ガジェット|スマートフォン|パソコン|(?<![A-Za-z])PC(?![A-Za-z])"),

        ("声優", r"声優"),
        ("コスプレ", r"コスプレ"),
        ("マンガ", r"マンガ|漫画|コミック"),
        ("ゲーム", r"eスポーツ|ゲーム(?:大会|イベント|フェス|体験|展示)"),

        ("旧車", r"旧車|クラシックカー"),
        ("スーパーカー", r"スーパーカー"),
        ("カスタムカー", r"カスタムカー|チューニングカー"),
        ("モータースポーツ", r"モータースポーツ|レース|サーキット|ラリー|ドリフト"),
        ("EV", r"電気自動車|EV車|(?<![A-Za-z])EV(?![A-Za-z])"),

        ("ラーメン", r"ラーメン(?:祭|フェス|博|イベント)?"),
        ("カレー", r"カレー(?:祭|フェス|博|イベント)?"),
        ("スイーツ", r"スイーツ(?:フェア|フェス|イベント)?"),
        ("パン", r"パン(?:祭|フェス|マルシェ|イベント)?"),
        ("物産展", r"物産展|北海道展"),
        ("日本酒", r"日本酒(?:祭|フェス|イベント)?"),
        ("ビール", r"ビール(?:祭|フェス|イベント)?"),

        ("美術", r"美術展|美術館|アート展"),
        ("写真", r"写真展"),
        ("特別展", r"特別展|企画展"),

        ("フェス", r"フェス(?:ティバル)?|祭り"),
        ("マルシェ", r"マルシェ"),
        ("ポップアップ", r"POP[\s-]?UP|ポップアップ"),
    ]

    # 明確な関連があるタグだけ追加
    for name, pat in secondary_rules:
        if re.search(pat, t, re.I):
            # カテゴリと明らかに矛盾するものは付けない
            allowed = True
            if name in ("鉄道模型","新幹線","駅弁") and cat != "rail":
                allowed = False
            if name in ("生成AI","XR","ガジェット") and cat != "tech":
                allowed = False
            if name in ("声優","コスプレ","マンガ","ゲーム") and cat != "anime":
                allowed = False
            if name in ("旧車","スーパーカー","カスタムカー","モータースポーツ","EV") and cat != "car":
                allowed = False
            if name in ("ラーメン","カレー","スイーツ","パン","物産展","日本酒","ビール") and cat != "food":
                allowed = False
            if name in ("美術","写真","特別展") and cat != "exhibition":
                allowed = False

            if allowed and name not in tags:
                tags.append(name)

    # 一般イベント系の補助タグは主カテゴリを問わず可
    if re.search(r"フェス(?:ティバル)?|祭り", t, re.I) and "フェス" not in tags:
        tags.append("フェス")
    elif re.search(r"マルシェ", t, re.I) and "マルシェ" not in tags:
        tags.append("マルシェ")
    elif re.search(r"POP[\s-]?UP|ポップアップ", t, re.I) and "ポップアップ" not in tags:
        tags.append("ポップアップ")

    return tags[:3]

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
# 収集診断 / サイトマップ探索
# -------------------------
DIAGNOSTICS = {}
DIAGNOSTICS_PATH = ROOT / "collection-report.json"

def diag(source_name, **kwargs):
    d = DIAGNOSTICS.setdefault(source_name, {
        "list_links": 0,
        "sitemap_links": 0,
        "candidates": 0,
        "parsed": 0,
        "errors": 0,
        "notes": []
    })
    for k, v in kwargs.items():
        if k == "note":
            d["notes"].append(str(v)[:300])
        elif isinstance(v, (int, float)) and isinstance(d.get(k), (int, float)):
            d[k] += v
        else:
            d[k] = v

def same_host(url, base):
    try:
        return urlparse(url).netloc.lower().replace("www.", "") == urlparse(base).netloc.lower().replace("www.", "")
    except Exception:
        return False

def parse_sitemap_xml(xml_text):
    """
    sitemap / sitemapindex の両方を読み取る。
    namespaceは無視して loc / lastmod を抽出。
    """
    out = []
    try:
        root = ET.fromstring(xml_text)
    except Exception:
        return out

    for node in root.iter():
        tag = node.tag.rsplit("}", 1)[-1].lower()
        if tag not in ("url", "sitemap"):
            continue
        loc = None
        lastmod = None
        for child in list(node):
            ctag = child.tag.rsplit("}", 1)[-1].lower()
            if ctag == "loc":
                loc = (child.text or "").strip()
            elif ctag == "lastmod":
                lastmod = (child.text or "").strip()
        if loc:
            out.append((tag, loc, lastmod))
    return out

def candidate_url_for_source(url, source):
    patterns = source.get("link_patterns", [r"/event/"])
    path = urlparse(url).path + ("?" + urlparse(url).query if urlparse(url).query else "")
    return any(re.search(p, path, re.I) for p in patterns)

def sitemap_seeds(source):
    base = source["base"].rstrip("/")
    explicit = source.get("sitemaps", [])
    seeds = list(explicit)
    for suffix in ("/sitemap.xml", "/sitemap_index.xml", "/sitemap-index.xml"):
        u = base + suffix
        if u not in seeds:
            seeds.append(u)
    return seeds

def discover_from_sitemaps(source):
    """
    公式サイトのサイトマップからイベント詳細URLを発見。
    一覧ページがJavaScript描画でも拾えることがある。
    """
    source_name = source["name"]
    found = []
    seen = set()
    queue = sitemap_seeds(source)
    visited_maps = set()
    max_maps = int(source.get("max_sitemaps", 12))
    max_links = int(source.get("max_sitemap_links", 180))

    while queue and len(visited_maps) < max_maps and len(found) < max_links:
        sm = queue.pop(0)
        if sm in visited_maps:
            continue
        visited_maps.add(sm)

        try:
            r = fetch(sm)
            entries = parse_sitemap_xml(r.text)
            if not entries:
                continue

            for typ, loc, lastmod in entries:
                if typ == "sitemap":
                    # イベント・ニュース・現在年のsitemapを優先
                    loc_low = loc.lower()
                    if (
                        any(k in loc_low for k in ["event", "news", "topic", "post", "page"])
                        or str(date.today().year) in loc_low
                        or len(queue) < 3
                    ):
                        if loc not in visited_maps and loc not in queue:
                            queue.append(loc)
                    continue

                if not same_host(loc, source["base"]):
                    continue
                if not candidate_url_for_source(loc, source):
                    continue
                if loc in seen:
                    continue
                seen.add(loc)
                found.append(loc)
                if len(found) >= max_links:
                    break

        except Exception as e:
            # sitemapが存在しないサイトは普通にある
            diag(source_name, note=f"sitemap {sm}: {type(e).__name__}")
            continue

    diag(source_name, sitemap_links=len(found))
    return found

def discover_source_urls(list_html, source):
    """
    1) 一覧HTMLのリンク
    2) sitemap
    を統合する。
    """
    source_name = source["name"]
    list_urls = extract_generic_detail_urls(list_html, source)
    diag(source_name, list_links=len(list_urls))

    sitemap_urls = discover_from_sitemaps(source)

    out = []
    seen = set()
    for u in list_urls + sitemap_urls:
        if u in seen:
            continue
        seen.add(u)
        out.append(u)

    # サイト別最大値。UIはページ送りできるので以前より多め。
    limit = int(source.get("max_total_links", max(
        source.get("max_links", 100),
        source.get("max_sitemap_links", 180)
    )))
    out = out[:limit]
    diag(source_name, candidates=len(out))
    return out

def parse_iso_or_japanese_date(value):
    if not value:
        return None
    s = str(value).strip()
    m = re.search(r"(20\d{2})-(\d{1,2})-(\d{1,2})", s)
    if m:
        try:
            return date(*map(int, m.groups())).isoformat()
        except Exception:
            pass
    m = re.search(r"(20\d{2})[年/.](\d{1,2})[月/.](\d{1,2})日?", s)
    if m:
        try:
            return date(*map(int, m.groups())).isoformat()
        except Exception:
            pass
    return None

def extract_dates_from_html(soup, text_body):
    """
    JSON-LD以外の明示日付を幅広く拾う。
    """
    # <time datetime=...>
    time_values = []
    for t in soup.find_all("time"):
        if t.get("datetime"):
            time_values.append(t.get("datetime"))
        if t.get_text(strip=True):
            time_values.append(t.get_text(" ", strip=True))

    # meta/itemprop
    for tag in soup.find_all(["meta", "data"], attrs={"itemprop": re.compile(r"startDate|endDate", re.I)}):
        val = tag.get("content") or tag.get("value") or tag.get_text(strip=True)
        if val:
            time_values.append(val)

    parsed = [parse_iso_or_japanese_date(v) for v in time_values]
    parsed = [x for x in parsed if x]
    if parsed:
        return min(parsed), max(parsed)

    # ATC形式: 2026.08.01 → 08.23 / 2026.08.18、08.19 ... 08.30
    m = re.search(
        r"(20\d{2})[./](\d{1,2})[./](\d{1,2})"
        r".{0,35}?(?:→|～|〜|~|\.\.\.|…|-)"
        r".{0,25}?(?:(20\d{2})[./])?(?:(\d{1,2})[./])?(\d{1,2})",
        text_body[:18000], re.S
    )
    if m:
        try:
            y1, m1, d1, y2, m2, d2 = m.groups()
            sd = date(int(y1), int(m1), int(d1))
            ed = date(int(y2 or y1), int(m2 or m1), int(d2))
            return sd.isoformat(), ed.isoformat()
        except Exception:
            pass

    # LUCUA形式: 8/22(土)〜8/23(日)
    m = re.search(
        r"(?<!\d)(\d{1,2})/(\d{1,2})"
        r".{0,12}?(?:～|〜|~|→|-)"
        r".{0,12}?(\d{1,2})/(\d{1,2})(?!\d)",
        text_body[:18000], re.S
    )
    if m:
        try:
            m1,d1,m2,d2 = map(int, m.groups())
            y = date.today().year
            sd = date(y,m1,d1)
            ed = date(y,m2,d2)
            if ed < sd:
                ed = date(y+1,m2,d2)
            if ed < date.today() - timedelta(days=60):
                sd = date(y+1,m1,d1)
                ed = date(y+1,m2,d2) if m2 >= m1 else date(y+2,m2,d2)
            return sd.isoformat(), ed.isoformat()
        except Exception:
            pass

    # 百貨店形式: 9月2日(水)→8日(火)
    m = re.search(
        r"(?<!\d)(\d{1,2})月\s*(\d{1,2})日"
        r".{0,12}?(?:→|～|〜|~|-)"
        r".{0,12}?(?:(\d{1,2})月\s*)?(\d{1,2})日",
        text_body[:18000], re.S
    )
    if m:
        try:
            m1,d1,m2,d2 = m.groups()
            m1,d1,d2 = int(m1),int(d1),int(d2)
            m2 = int(m2 or m1)
            y = date.today().year
            sd = date(y,m1,d1)
            ed = date(y,m2,d2)
            if ed < sd:
                ed = date(y+1,m2,d2)
            if ed < date.today() - timedelta(days=60):
                sd = date(y+1,m1,d1)
                ed = date(y+1,m2,d2) if m2 >= m1 else date(y+2,m2,d2)
            return sd.isoformat(), ed.isoformat()
        except Exception:
            pass

    # 本文: 年付きレンジ
    patterns = [
        re.compile(
            r"(20\d{2})年\s*(\d{1,2})月\s*(\d{1,2})日"
            r".{0,40}?(?:～|〜|~|-|ー)"
            r".{0,20}?(?:(20\d{2})年\s*)?(\d{1,2})月\s*(\d{1,2})日",
            re.S
        ),
        re.compile(
            r"(20\d{2})[/.](\d{1,2})[/.](\d{1,2})"
            r".{0,40}?(?:～|〜|~|-)"
            r".{0,20}?(?:(20\d{2})[/.])?(\d{1,2})[/.](\d{1,2})",
            re.S
        )
    ]
    for pat in patterns:
        m = pat.search(text_body[:18000])
        if m:
            try:
                y1,m1,d1,y2,m2,d2 = m.groups()
                sd = date(int(y1),int(m1),int(d1))
                ed = date(int(y2 or y1),int(m2),int(d2))
                return sd.isoformat(), ed.isoformat()
            except Exception:
                pass

    # 年付き単日
    single = re.search(r"(20\d{2})年\s*(\d{1,2})月\s*(\d{1,2})日", text_body[:18000])
    if not single:
        single = re.search(r"(20\d{2})[/.](\d{1,2})[/.](\d{1,2})", text_body[:18000])
    if single:
        try:
            d = date(*map(int, single.groups())).isoformat()
            return d, d
        except Exception:
            pass

    # 年なし単日。今後の日付として推定
    single = re.search(r"(?<!\d)(\d{1,2})月\s*(\d{1,2})日", text_body[:18000])
    if single:
        try:
            mo, da = map(int, single.groups())
            y = date.today().year
            d = date(y, mo, da)
            if d < date.today() - timedelta(days=60):
                d = date(y+1, mo, da)
            return d.isoformat(), d.isoformat()
        except Exception:
            pass

    return None, None

def extract_venue_from_html(soup, text_body, forced_area=None):
    selectors = [
        '[itemprop="location"]',
        '[class*="venue"]',
        '[class*="place"]',
        '[class*="access"]',
        '[class*="location"]',
    ]
    for sel in selectors:
        try:
            node = soup.select_one(sel)
        except Exception:
            node = None
        if node:
            s = node.get_text(" ", strip=True)
            if 2 <= len(s) <= 100:
                return s

    m = re.search(r"(?:会場|開催場所|場所|ところ)[：:\s]+([^\n]{2,90})", text_body)
    if m:
        return m.group(1).strip()

    return forced_area or "関西"

def page_looks_like_event(title, text_body):
    merged = (title + " " + text_body[:7000]).lower()
    positives = CONFIG.get("event_intent_keywords", [])
    if any(k.lower() in merged for k in positives):
        return True
    # よくある追加語
    return bool(re.search(
        r"開催期間|開催日時|会期|入場|会場|open|event|exhibition|festival|popup|pop-up",
        merged, re.I
    ))


# -------------------------
# 一覧ページから直接イベントカードを解析
# -------------------------
def img_from_node(node, base):
    if not node:
        return None
    img = node.find("img")
    if not img:
        return None
    for key in ("src", "data-src", "data-original", "data-lazy-src"):
        val = img.get(key)
        if val and not str(val).startswith("data:"):
            return urljoin(base, val)
    srcset = img.get("srcset")
    if srcset:
        first = srcset.split(",")[0].strip().split(" ")[0]
        if first:
            return urljoin(base, first)
    return None

def meaningful_title_from_node(node, fallback=""):
    if not node:
        return fallback
    for tagname in ("h1","h2","h3","h4","h5"):
        h = node.find(tagname)
        if h:
            t = re.sub(r"\s+", " ", h.get_text(" ", strip=True)).strip()
            if 3 <= len(t) <= 130:
                return t
    # anchor strong/b text
    for tagname in ("strong","b"):
        h = node.find(tagname)
        if h:
            t = re.sub(r"\s+", " ", h.get_text(" ", strip=True)).strip()
            if 3 <= len(t) <= 130 and not re.fullmatch(r"詳細を見る|詳しくはこちら|MORE|VIEW MORE", t, re.I):
                return t
    return fallback

def nearest_event_block(anchor):
    """
    詳細リンクから親要素を遡り、日付を含む適度なサイズのカードを探す。
    """
    node = anchor
    best = anchor.parent
    for _ in range(6):
        if not node or not getattr(node, "parent", None):
            break
        node = node.parent
        txt = re.sub(r"\s+", " ", node.get_text(" ", strip=True))
        if 25 <= len(txt) <= 1800:
            sd, ed = extract_dates_from_html(node, txt)
            if sd:
                best = node
                # タイトルも取れそうなら即採用
                if meaningful_title_from_node(node):
                    return node
    return best

def collect_events_from_listing_cards(html, source):
    """
    ATC/LUCUA/阪急/大丸など:
    詳細ページが読めなくても一覧ページのカードから拾う。
    """
    soup = BeautifulSoup(html, "html.parser")
    events = []
    seen = set()

    for a in soup.find_all("a", href=True):
        href = a.get("href", "").strip()
        if not is_probable_event_link(href, source.get("link_patterns", [r"/event/"])):
            continue

        url = urljoin(source["base"], href)
        block = nearest_event_block(a)
        block_text = re.sub(r"\s+", " ", block.get_text(" ", strip=True))
        sd, ed = extract_dates_from_html(block, block_text)
        if not sd:
            # LUCUAのようにリンク本文に「タイトル 9/6〜9/7」が入るケース
            sd, ed = extract_dates_from_html(a, a.get_text(" ", strip=True))
        if not sd:
            continue
        if (ed or sd) < date.today().isoformat():
            continue

        anchor_text = re.sub(r"\s+", " ", a.get_text(" ", strip=True)).strip()
        anchor_text = re.sub(
            r"\s+\d{1,2}/\d{1,2}.*$",
            "",
            anchor_text
        ).strip()
        if anchor_text in ("詳細を見る", "詳しくはこちら", "MORE", "VIEW MORE"):
            anchor_text = ""

        title = meaningful_title_from_node(block, anchor_text)
        if not title:
            continue

        # 状態語や日付の前置きを削る
        title = re.sub(r"^(開催中|開催予定|終了|予告)\s*", "", title).strip()
        title = re.sub(r"\s+", " ", title)[:110]

        key = (normalize_title(title)[:36], sd, url)
        if key in seen:
            continue
        seen.add(key)

        venue = extract_venue_from_html(block, block_text, source.get("area"))
        image_url = img_from_node(block, source["base"])
        desc = block_text
        # タイトル・日付・詳細を見るなどを少し整理
        desc = re.sub(r"\s+", " ", desc)
        desc = desc.replace("詳細を見る", "").strip()
        if desc.startswith(title):
            desc = desc[len(title):].strip(" -｜|")
        desc = desc[:170]

        full = " ".join([title, venue, desc])
        area = area_from_text(full)
        if area == "関西" and source.get("area"):
            area = source.get("area")

        cat = classify(full)
        events.append({
            "title": title,
            "start_date": sd,
            "end_date": ed or sd,
            "area": area,
            "venue": venue,
            "category": cat,
            "score": score(full, cat),
            "tags": make_tags(full, cat),
            "description": desc or "詳しくは公式ページをご確認ください。",
            "image_url": image_url,
            "source": source["name"],
            "source_url": url,
        })

    return events

def monthless_date_range(text_value):
    """
    百貨店一覧の「9月2日(水)→8日(火)」にも対応。
    """
    m = re.search(
        r"(?:(20\d{2})年)?\s*(\d{1,2})月\s*(\d{1,2})日"
        r".{0,20}?(?:→|～|〜|~|-)"
        r".{0,15}?(?:(\d{1,2})月)?\s*(\d{1,2})日",
        text_value, re.S
    )
    if not m:
        return None, None
    y, m1, d1, m2, d2 = m.groups()
    y = int(y or date.today().year)
    m1 = int(m1); d1 = int(d1); m2 = int(m2 or m1); d2 = int(d2)
    try:
        sd = date(y,m1,d1)
        ed = date(y,m2,d2)
        if ed < sd:
            ed = date(y+1,m2,d2)
        if ed < date.today() - timedelta(days=60):
            sd = date(y+1,m1,d1)
            ed = date(y+1,m2,d2) if m2 >= m1 else date(y+2,m2,d2)
        return sd.isoformat(), ed.isoformat()
    except Exception:
        return None, None

def collect_department_store_text(html, source):
    """
    阪急・大丸のように一覧ページ本文だけで多数の催事が完結しているページを解析。
    各日付レンジの直前の見出し/短文をタイトル候補にする。
    """
    soup = BeautifulSoup(html, "html.parser")
    # script/style除外
    for x in soup(["script","style","noscript"]):
        x.decompose()

    # ブロック単位で読む
    nodes = soup.find_all(["h2","h3","h4","h5","p","li","div"])
    events = []
    seen = set()

    for node in nodes:
        txt = re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip()
        if not (10 <= len(txt) <= 1200):
            continue

        sd, ed = monthless_date_range(txt)
        if not sd:
            sd, ed = extract_dates_from_html(node, txt)
        if not sd or (ed or sd) < date.today().isoformat():
            continue

        # タイトルは日付直前のテキスト
        date_pos = None
        for pat in [
            r"(?:(20\d{2})年)?\s*\d{1,2}月\s*\d{1,2}日",
            r"\d{1,2}/\d{1,2}"
        ]:
            mm = re.search(pat, txt)
            if mm:
                date_pos = mm.start()
                break

        before = txt[:date_pos].strip(" ◎・｜|:-") if date_pos is not None else ""
        # 長すぎる説明文なら末尾100字程度からタイトルらしい部分
        if len(before) > 150:
            # 説明の末尾にイベント名が来る阪急形式を想定
            candidates = re.split(r"[。！？!?\n]", before)
            before = next((c.strip() for c in reversed(candidates) if 4 <= len(c.strip()) <= 120), before[-120:])

        title = re.sub(r"^(予告|〖予告〗|開催中|開催予定)\s*", "", before).strip()
        if not (3 <= len(title) <= 130):
            continue
        if re.search(r"営業時間|アクセス|電話|住所|検索|カレンダー", title):
            continue

        key = (normalize_title(title)[:36], sd)
        if key in seen:
            continue
        seen.add(key)

        venue = extract_venue_from_html(node, txt, source.get("area"))
        full = " ".join([title, txt, venue])
        cat = classify(full)
        events.append({
            "title": title[:110],
            "start_date": sd,
            "end_date": ed or sd,
            "area": source.get("area","大阪"),
            "venue": venue,
            "category": cat,
            "score": score(full, cat),
            "tags": make_tags(full, cat),
            "description": txt[:170],
            "image_url": img_from_node(node, source["base"]),
            "source": source["name"],
            "source_url": source["url"],
        })

    return events



# -------------------------
# インテックス大阪専用収集
# -------------------------
INTEX_VARIANTS = [
    "https://www.intex-osaka.com/jp/",
    "https://www.intex-osaka.com/jp/?interfaceLocale=ja-JP&locale=ja-JP",
    "https://www.intex-osaka.com/jp/?locale=ja-JP",
    "https://www.intex-osaka.com/jp/?accessToken=undefined&interfaceLocale=ja-JP&locale=ja-JP",
]

def _intex_parse_date_pair(text_value):
    """
    2026 08/14 FRI. 2026 08/16 SUN.
    のような表記を解析。
    """
    m = re.search(
        r"(20\d{2})\s+(\d{1,2})/(\d{1,2})\s+[A-Z]{3}\.?"
        r".{0,80}?"
        r"(20\d{2})\s+(\d{1,2})/(\d{1,2})\s+[A-Z]{3}\.?",
        text_value, re.S | re.I
    )
    if m:
        try:
            y1,m1,d1,y2,m2,d2 = map(int, m.groups())
            return date(y1,m1,d1).isoformat(), date(y2,m2,d2).isoformat()
        except Exception:
            pass

    m = re.search(
        r"(20\d{2})\s+(\d{1,2})/(\d{1,2})\s+[A-Z]{3}\.?",
        text_value, re.S | re.I
    )
    if m:
        try:
            y,m,d = map(int, m.groups())
            iso = date(y,m,d).isoformat()
            return iso, iso
        except Exception:
            pass
    return None, None

def parse_intex_homepage(html, source_url):
    """
    インテックス大阪トップページのEVENTカードを直接解析。
    h3タイトルの周囲にある開始日・終了日・会場・説明を取得する。
    """
    soup = BeautifulSoup(html, "html.parser")
    events = []
    seen = set()

    for h in soup.find_all(["h2","h3","h4"]):
        title = re.sub(r"\s+", " ", h.get_text(" ", strip=True)).strip()
        if not title or len(title) < 4:
            continue
        if title in ("EVENT", "イベント", "ACCESS", "NEWS"):
            continue

        node = h
        block = None
        for _ in range(7):
            node = getattr(node, "parent", None)
            if not node:
                break
            txt = re.sub(r"\s+", " ", node.get_text(" ", strip=True))
            if (
                re.search(r"20\d{2}\s+\d{1,2}/\d{1,2}", txt)
                and ("会場" in txt or "開催時間" in txt or "料金" in txt)
                and len(txt) < 7000
            ):
                block = node
                break

        if not block:
            continue

        txt = re.sub(r"\s+", " ", block.get_text(" ", strip=True))
        sd, ed = _intex_parse_date_pair(txt)
        if not sd:
            sd, ed = extract_dates_from_html(block, txt)
        if not sd or (ed or sd) < date.today().isoformat():
            continue

        # 会場: 「会場 3号館 4号館 5号館A」など
        venue = "インテックス大阪"
        vm = re.search(
            r"会場\s+(.+?)(?:開催時間|料金|ホームページ|詳しく見る|$)",
            txt
        )
        if vm:
            hall_text = re.sub(r"\s+", " ", vm.group(1)).strip()
            if 1 <= len(hall_text) <= 180:
                venue = "インテックス大阪 " + hall_text

        # 説明はタイトル後〜会場前
        desc = ""
        if title in txt:
            after = txt.split(title, 1)[1]
            desc = re.split(r"\s+会場\s+", after, maxsplit=1)[0].strip()
        desc = desc[:220] or "詳しくはインテックス大阪公式サイトをご確認ください。"

        full = f"{title} {venue} {desc}"
        cat = classify(full)
        image_url = img_from_node(block, "https://www.intex-osaka.com")

        key = (normalize_title(title)[:40], sd)
        if key in seen:
            continue
        seen.add(key)

        # 外部公式ホームページへのリンクがあればそれを優先
        official = None
        for a in block.find_all("a", href=True):
            href = a["href"].strip()
            if href.startswith("http") and "intex-osaka.com" not in href:
                official = href
                break

        events.append({
            "title": title[:110],
            "start_date": sd,
            "end_date": ed or sd,
            "area": "大阪",
            "venue": venue,
            "category": cat,
            "score": min(99, score(full, cat) + 8),
            "tags": make_tags(full, cat),
            "description": desc,
            "image_url": image_url,
            "source": "インテックス大阪",
            "source_url": official or source_url,
        })

    return events

def _bing_rss_search(query):
    """
    Bingの公開RSS検索を使った補助的なイベント発見。
    APIキー不要。失敗しても他の収集には影響しない。
    """
    import urllib.parse
    url = "https://www.bing.com/search?format=rss&q=" + urllib.parse.quote(query)
    try:
        r = S.get(url, timeout=25, headers={
            "User-Agent": UA,
            "Accept": "application/rss+xml,application/xml,text/xml,*/*",
            "Accept-Language": "ja-JP,ja;q=0.9"
        })
        r.raise_for_status()
        root = ET.fromstring(r.text)
        out = []
        for item in root.findall(".//item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            desc = html_lib.unescape(item.findtext("description") or "")
            if link:
                out.append((title, link, re.sub("<[^>]+>", " ", desc)))
        return out
    except Exception as e:
        print(f"[INTEX Search] RSS error: {e}", file=sys.stderr)
        return []

def collect_intex_search_discovery():
    """
    インテックス大阪公式カレンダーにイベント名が出ない場合を補完するため、
    当月〜5か月先について公開検索RSSから主催者公式ページを発見する。
    発見ページはEvent JSON-LDまたは本文解析でイベント化する。
    """
    found = []
    seen_urls = set()
    today = date.today()

    for offset in range(0, 6):
        y = today.year + ((today.month - 1 + offset) // 12)
        m = ((today.month - 1 + offset) % 12) + 1
        queries = [
            f'"インテックス大阪" {y}年{m}月 イベント',
            f'"インテックス大阪" {y}/{m} 展示会',
        ]
        for q in queries:
            for result_title, link, snippet in _bing_rss_search(q):
                if link in seen_urls:
                    continue
                seen_urls.add(link)

                merged = f"{result_title} {snippet}"
                if "インテックス大阪" not in merged:
                    continue
                # インテックス公式そのものはhomepage collectorで処理する
                if "intex-osaka.com" in urlparse(link).netloc:
                    continue

                try:
                    parsed = parse_event_jsonld_page(link, "インテックス大阪関連", "大阪")
                    if not parsed:
                        parsed = parse_simple_event_page(link, "インテックス大阪関連", "大阪")
                    for e in parsed:
                        # 会場にインテックス大阪が明示されるイベントだけ採用
                        verify = " ".join([
                            e.get("title",""), e.get("venue",""),
                            e.get("description",""), merged
                        ])
                        if "インテックス大阪" not in verify:
                            continue
                        e["source"] = "インテックス大阪関連"
                        e["score"] = min(99, e.get("score", 50) + 5)
                        found.append(e)
                except Exception as e:
                    print(f"[INTEX Search] parse error {link}: {e}", file=sys.stderr)
                time.sleep(0.08)

    return found

def collect_intex_events():
    events = []
    seen = set()

    # 複数URLバリアントを試す。サイト側キャッシュ差でEVENTカードが出ることがある。
    for url in INTEX_VARIANTS:
        try:
            html = fetch(url).text
            parsed = parse_intex_homepage(html, url)
            for e in parsed:
                key = (normalize_title(e.get("title",""))[:40], e.get("start_date",""))
                if key not in seen:
                    seen.add(key)
                    events.append(e)
        except Exception as e:
            print(f"[INTEX] homepage error {url}: {e}", file=sys.stderr)

    # 外部主催者サイト探索も補助的に実行
    try:
        for e in collect_intex_search_discovery():
            key = (normalize_title(e.get("title",""))[:40], e.get("start_date",""))
            if key not in seen:
                seen.add(key)
                events.append(e)
    except Exception as e:
        print(f"[INTEX] search discovery error: {e}", file=sys.stderr)

    return events



# -------------------------
# ATCトップページ専用
# -------------------------
def dedicated_atc_home(html, source):
    """
    ATCトップページのEVENT欄を直接読む。
    例:
      2026.09.19 → 09.22 OSAKAアート＆てづくりバザール VOL.52
      2026.09.06、10.04、10.25 第39回 ATC咲洲ダンスフェス
    """
    soup = BeautifulSoup(html, "html.parser")
    events = []
    seen = set()

    # aタグを優先
    for a in soup.find_all("a", href=True):
        txt = re.sub(r"\s+", " ", a.get_text(" ", strip=True)).strip()
        if not re.search(r"20\d{2}[./]\d{1,2}[./]\d{1,2}", txt):
            continue

        # 先頭の日付部分とタイトルを分離
        m = re.match(
            r"^(20\d{2})[./](\d{1,2})[./](\d{1,2})"
            r"(?P<dates>(?:\s*(?:→|～|〜|-)\s*(?:20\d{2}[./])?\d{1,2}[./]\d{1,2}|(?:、\s*\d{1,2}[./]\d{1,2})*)?)"
            r"\s*(?P<title>.+)$",
            txt
        )
        if not m:
            continue

        y, mo, da = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            sd_obj = date(y, mo, da)
        except Exception:
            continue

        date_tail = m.group("dates") or ""
        title = clean_event_title(m.group("title"))
        if not title:
            continue

        # 終了日
        ed_obj = sd_obj
        range_match = re.search(
            r"(?:→|～|〜|-)\s*(?:(20\d{2})[./])?(\d{1,2})[./](\d{1,2})",
            date_tail
        )
        if range_match:
            y2, m2, d2 = range_match.groups()
            try:
                ed_obj = date(int(y2 or y), int(m2), int(d2))
                if ed_obj < sd_obj:
                    ed_obj = date(int(y2 or y) + 1, int(m2), int(d2))
            except Exception:
                ed_obj = sd_obj

        # 複数開催日は最初の日を代表日、説明に全日程を残す
        if sd_obj < date.today() and ed_obj < date.today():
            # 「9/6、10/4、10/25」のような複数日程は未来日が残っている可能性あり
            future = []
            for mm, dd in re.findall(r"(\d{1,2})[./](\d{1,2})", date_tail):
                try:
                    d = date(y, int(mm), int(dd))
                    if d >= date.today():
                        future.append(d)
                except Exception:
                    pass
            if not future:
                continue
            sd_obj = min(future)
            ed_obj = sd_obj

        url = urljoin(source["base"], a["href"])
        parent = a.parent
        block = parent.parent if parent and parent.parent else parent
        desc = re.sub(r"\s+", " ", block.get_text(" ", strip=True)) if block else txt
        full = f"{title} ATC {desc}"
        cat = classify(full)

        key = (normalize_title(title), sd_obj.isoformat())
        if key in seen:
            continue
        seen.add(key)

        events.append({
            "title": title[:110],
            "start_date": sd_obj.isoformat(),
            "end_date": ed_obj.isoformat(),
            "area": "大阪",
            "venue": "ATC",
            "category": cat,
            "score": min(99, score(full, cat) + 10),
            "tags": make_tags(full, cat),
            "description": desc[:180],
            "image_url": img_from_node(block, source["base"]) if block else None,
            "source": "ATC",
            "source_url": url,
        })

    # aタグで取れない場合、ページ全体のテキストからも拾う
    body = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))
    pattern = re.compile(
        r"(20\d{2})[./](\d{1,2})[./](\d{1,2})"
        r"\s*(?:(→|～|〜|-)\s*(?:(20\d{2})[./])?(\d{1,2})[./](\d{1,2}))?"
        r"\s+(.{4,100}?)(?=\s+20\d{2}[./]\d{1,2}[./]\d{1,2}|\s+イベント一覧|\s+レストラン|$)"
    )
    for m in pattern.finditer(body):
        y,m1,d1,arrow,y2,m2,d2,title = m.groups()
        title = clean_event_title(title)
        if not title:
            continue
        try:
            sd = date(int(y),int(m1),int(d1))
            ed = date(int(y2 or y),int(m2 or m1),int(d2 or d1))
        except Exception:
            continue
        if ed < date.today():
            continue

        key = (normalize_title(title), sd.isoformat())
        if key in seen:
            continue
        seen.add(key)
        full = f"{title} ATC"
        cat = classify(full)
        events.append({
            "title": title[:110],
            "start_date": sd.isoformat(),
            "end_date": ed.isoformat(),
            "area": "大阪",
            "venue": "ATC",
            "category": cat,
            "score": min(99, score(full, cat) + 10),
            "tags": make_tags(full, cat),
            "description": "ATC公式サイト掲載イベント。",
            "image_url": None,
            "source": "ATC",
            "source_url": source["url"],
        })

    return events


# -------------------------
# あべのハルカス専用 v2
# -------------------------
def dedicated_harukas_v3(html, source):
    """
    あべのハルカス近鉄本店の催しスケジュール専用。

    HTML上の表示順をそのまま使い、
      秋のリビングフェスティバル［9月3日(木)→7日(月)］
      大北海道展［9月9日(水)→23日(水・祝)］
    のような同一行形式と、

      黄金工芸逸品展
      ［9月2日(水)→8日(火)］

    のような改行形式の両方を解析する。

    「11月29日まで」のように開始日が明記されない開催中イベントは、
    収集日を開始日として扱う。
    """
    soup = BeautifulSoup(html, "html.parser")
    events = []
    seen = set()

    lines = [re.sub(r"\s+", " ", s).strip() for s in soup.stripped_strings]
    lines = [s for s in lines if s]

    # ページ上の年月（例: 2026 9）
    joined_head = " ".join(lines[:120])
    ym = re.search(r"\b(20\d{2})\s+(\d{1,2})\b", joined_head)
    base_year = int(ym.group(1)) if ym else date.today().year

    # リンクをタイトル文字列から逆引き
    link_map = {}
    for a in soup.find_all("a", href=True):
        at = re.sub(r"\s+", " ", a.get_text(" ", strip=True)).strip()
        if at:
            link_map[normalize_title(at)[:80]] = urljoin(source["base"], a["href"])

    current_floor = ""
    current_venue = "あべのハルカス近鉄本店"

    def update_venue(line, next_line=""):
        nonlocal current_floor, current_venue
        if re.search(r"(?:ウイング館|タワー館).*(?:階|地\d階)$", line):
            current_floor = line
            # 次行が催会場等なら次ループで結合
            current_venue = f"あべのハルカス近鉄本店 {current_floor}"
            return True
        if re.search(r"催会場|第\d催会場|美術画廊|アートギャラリー|イベントホール|イベントスペース|デリシャスステージ|POP UP SWEETS|トレンドスペース", line, re.I):
            if current_floor:
                current_venue = f"あべのハルカス近鉄本店 {current_floor} {line}"
            else:
                current_venue = f"あべのハルカス近鉄本店 {line}"
            return True
        return False

    # 日付ブロック
    date_pat = re.compile(
        r"[［\[]\s*"
        r"(?:(?P<year>20\d{2})年\s*)?"
        r"(?P<m1>\d{1,2})月\s*(?P<d1>\d{1,2})日[^］\]]*?"
        r"(?:(?P<range>→|～|〜|~|-)\s*(?:(?P<m2>\d{1,2})月\s*)?(?P<d2>\d{1,2})日[^］\]]*|(?P<until>まで))?"
        r"[］\]]"
    )

    def parse_range(match):
        y = int(match.group("year") or base_year)
        m1 = int(match.group("m1"))
        d1 = int(match.group("d1"))
        try:
            first = date(y, m1, d1)
        except Exception:
            return None, None

        if match.group("until"):
            # 開始日不明。今日時点で開催中として扱う。
            end = first
            start = date.today() if end >= date.today() else first
            return start, end

        if match.group("d2"):
            m2 = int(match.group("m2") or m1)
            d2 = int(match.group("d2"))
            try:
                end = date(y, m2, d2)
                if end < first:
                    end = date(y + 1, m2, d2)
            except Exception:
                end = first
            return first, end

        return first, first

    def good_title_piece(s):
        s = clean_event_title(s)
        if not (2 <= len(s) <= 130):
            return False
        if re.fullmatch(r"\d+|\([月火水木金土日]\)|[|｜]+", s):
            return False
        if re.search(r"^(EVENT SCHEDULE|催しスケジュール|催会場|食品のフロア|美術画廊・アートギャラリー|営業時間|フロアガイド)$", s):
            return False
        if re.search(r"※最終日|閉場|午前\d|午後\d", s):
            return False
        if re.search(r"(?:ウイング館|タワー館).*(?:階|地\d階)$", s):
            return False
        if re.search(r"催会場|第\d催会場|美術画廊|アートギャラリー|イベントホール|イベントスペース|デリシャスステージ|POP UP SWEETS", s, re.I):
            return False
        return True

    for i, line in enumerate(lines):
        next_line = lines[i + 1] if i + 1 < len(lines) else ""
        if update_venue(line, next_line):
            continue

        dm = date_pat.search(line)
        if not dm:
            continue

        sd_obj, ed_obj = parse_range(dm)
        if not sd_obj or not ed_obj or ed_obj < date.today():
            continue

        # 同一行の日付より前を第一候補
        before = clean_event_title(line[:dm.start()].strip())
        title_parts = []

        if good_title_piece(before):
            title_parts = [before]
        else:
            # 改行型。直前1～3行からタイトルを組み立てる。
            for j in range(i - 1, max(-1, i - 4), -1):
                cand = clean_event_title(lines[j])
                if not good_title_piece(cand):
                    continue
                title_parts.insert(0, cand)
                # ブランド表記+商品名、あるいは展覧会の副題を最大2行まで
                if len(title_parts) >= 2:
                    break

        if not title_parts:
            continue

        # 同じ文言の繰り返しを除いて結合
        compact_parts = []
        for part in title_parts:
            if not compact_parts or normalize_title(part) != normalize_title(compact_parts[-1]):
                compact_parts.append(part)
        title = " ".join(compact_parts).strip()[:110]

        # ページヘッダ・キャンペーン等のノイズは後段フィルタでも落ちるが、
        # ここでも明らかなものだけ除外
        if re.search(r"プレミアム付商品券|アプリ大感謝祭|新規・増口ご入会キャンペーン", title):
            continue

        # 前後文脈
        context = " ".join(lines[max(0, i - 3):min(len(lines), i + 3)])
        full = f"{title} {current_venue} {context}"
        cat = classify(full)

        # タイトルを含むリンクを探す
        source_url = source["url"]
        nt = normalize_title(title)
        for k, u in link_map.items():
            if nt[:28] and (nt[:28] in k or k[:28] in nt):
                source_url = u
                break

        key = (normalize_title(title)[:45], sd_obj.isoformat(), current_venue)
        if key in seen:
            continue
        seen.add(key)

        events.append({
            "title": title,
            "start_date": sd_obj.isoformat(),
            "end_date": ed_obj.isoformat(),
            "area": "大阪",
            "venue": current_venue,
            "category": cat,
            "score": min(99, score(full, cat) + 14),
            "tags": make_tags(full, cat),
            "description": context[:180],
            "image_url": None,
            "source": "あべのハルカス近鉄本店",
            "source_url": source_url,
        })

    return events


# -------------------------
# セブンパーク天美専用
# -------------------------
def parse_sevenpark_detail(url):
    html = fetch(url).text
    soup = BeautifulSoup(html, "html.parser")
    text_body = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))

    h1 = soup.find("h1")
    title = h1.get_text(" ", strip=True) if h1 else ""
    if not title:
        ogt = soup.find("meta", property="og:title")
        title = ogt.get("content", "").strip() if ogt else ""
    title = clean_event_title(title)
    if not title:
        return None

    # 日程 2026/07/26(日)
    dm = re.search(r"日程\s*(20\d{2})/(\d{1,2})/(\d{1,2})", text_body)
    if not dm:
        dm = re.search(r"(20\d{2})/(\d{1,2})/(\d{1,2})", text_body)
    if not dm:
        return None
    try:
        sd = date(*map(int, dm.groups()))
    except Exception:
        return None
    if sd < date.today():
        return None

    # 場所
    venue = "セブンパーク天美"
    vm = re.search(r"場所\s*(.+?)(?:備考欄|所在地|時間|$)", text_body)
    if vm:
        v = vm.group(1).strip()
        if 2 <= len(v) <= 120:
            venue = "セブンパーク天美 " + v

    # 時間
    tm = re.search(r"時間\s*(.+?)(?:場所|備考欄|所在地|$)", text_body)
    times = tm.group(1).strip() if tm else ""

    desc_meta = (
        soup.find("meta", attrs={"name":"description"})
        or soup.find("meta", property="og:description")
    )
    desc = desc_meta.get("content", "").strip() if desc_meta else ""
    if not desc:
        desc = text_body[:220]

    full = f"{title} {venue} {desc}"
    cat = classify(full)
    image_url = extract_meta_image(soup)

    return {
        "title": title[:110],
        "start_date": sd.isoformat(),
        "end_date": sd.isoformat(),
        "area": "大阪",
        "venue": venue,
        "category": cat,
        "score": min(99, score(full, cat) + 15),
        "tags": make_tags(full, cat),
        "description": ((times + " " + desc).strip())[:180],
        "image_url": image_url,
        "source": "セブンパーク天美",
        "source_url": url,
    }

def dedicated_sevenpark(html, source):
    soup = BeautifulSoup(html, "html.parser")
    urls = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not re.search(r"/event/\d+/?", href):
            continue
        u = urljoin(source["base"], href)
        if u not in seen:
            seen.add(u)
            urls.append(u)

    events = []
    # 一覧から見つかった詳細を並列取得
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = [ex.submit(parse_sevenpark_detail, u) for u in urls[:160]]
        for fut in as_completed(futs):
            try:
                ev = fut.result()
                if ev:
                    events.append(ev)
            except Exception as e:
                print(f"[SevenPark] detail error: {e}", file=sys.stderr)

    return events

# -------------------------
# 大阪主要サイト専用パーサー
# -------------------------
def clean_event_title(s):
    s = re.sub(r"\s+", " ", s or "").strip()
    s = re.sub(r"^(開催中|開催予定|予告|〖予告〗|【予告】)\s*", "", s)
    s = re.sub(r"\s+(お気に入りに追加|詳細を見る|詳しくはこちら).*$", "", s)
    return s.strip(" ・｜|")[:110]

def dedicated_atc(html, source):
    soup = BeautifulSoup(html, "html.parser")
    events = []
    seen = set()

    for h in soup.find_all(["h2","h3"]):
        title = clean_event_title(h.get_text(" ", strip=True))
        if not title or title in ("イベント", "イベント検索"):
            continue

        node = h
        block = None
        for _ in range(5):
            node = getattr(node, "parent", None)
            if not node:
                break
            t = re.sub(r"\s+", " ", node.get_text(" ", strip=True))
            if re.search(r"20\d{2}[./]\d{1,2}[./]\d{1,2}", t) and len(t) < 1800:
                block = node
                break
        if not block:
            continue

        txt = re.sub(r"\s+", " ", block.get_text(" ", strip=True))
        sd, ed = extract_dates_from_html(block, txt)
        if not sd or (ed or sd) < date.today().isoformat():
            continue

        m = re.search(r"開催場所\s*([^料金開催時間]{2,120})", txt)
        venue = m.group(1).strip() if m else "ATC"
        desc = re.sub(r"^.*?" + re.escape(title), "", txt, count=1).strip()[:170]
        key = (normalize_title(title), sd)
        if key in seen:
            continue
        seen.add(key)
        full = f"{title} {venue} {desc}"
        cat = classify(full)

        link = h.find("a", href=True) or block.find("a", href=True)
        url = urljoin(source["base"], link["href"]) if link else source["url"]

        events.append({
            "title": title, "start_date": sd, "end_date": ed or sd,
            "area": "大阪", "venue": venue, "category": cat,
            "score": score(full, cat), "tags": make_tags(full, cat),
            "description": desc or "詳しくはATC公式サイトをご確認ください。",
            "image_url": img_from_node(block, source["base"]),
            "source": "ATC", "source_url": url,
        })
    return events

def dedicated_lucua(html, source):
    soup = BeautifulSoup(html, "html.parser")
    events = []
    seen = set()

    for a in soup.find_all("a", href=True):
        txt = re.sub(r"\s+", " ", a.get_text(" ", strip=True))
        if not re.search(r"\d{1,2}/\d{1,2}", txt):
            continue
        sd, ed = extract_dates_from_html(a, txt)
        if not sd or (ed or sd) < date.today().isoformat():
            continue

        title = re.sub(
            r"\s+\d{1,2}/\d{1,2}.*$",
            "",
            txt
        ).strip()
        title = clean_event_title(title)
        if not title or len(title) < 3:
            continue
        if "毎日、服の回収" in title:
            continue

        key = (normalize_title(title), sd)
        if key in seen:
            continue
        seen.add(key)

        parent = a.parent
        block = parent.parent if parent and parent.parent else parent
        desc = re.sub(r"\s+", " ", block.get_text(" ", strip=True)) if block else txt
        full = f"{title} LUCUA大阪 {desc}"
        cat = classify(full)

        events.append({
            "title": title, "start_date": sd, "end_date": ed or sd,
            "area": "大阪", "venue": "LUCUA大阪", "category": cat,
            "score": score(full, cat), "tags": make_tags(full, cat),
            "description": desc[:170],
            "image_url": img_from_node(block, source["base"]) if block else None,
            "source": "LUCUA大阪", "source_url": urljoin(source["base"], a["href"]),
        })
    return events

def dedicated_hankyu(html, source):
    soup = BeautifulSoup(html, "html.parser")
    lines = [re.sub(r"\s+", " ", x).strip() for x in soup.stripped_strings]
    events = []
    seen = set()

    for i, line in enumerate(lines):
        if not re.match(r"^◎\s*\d{1,2}月\s*\d{1,2}日", line):
            continue

        sd, ed = extract_dates_from_html(soup, line)
        if not sd or (ed or sd) < date.today().isoformat():
            continue

        # 直前からタイトル候補を探す
        title = ""
        for j in range(i-1, max(-1, i-7), -1):
            cand = clean_event_title(lines[j])
            if not cand:
                continue
            if re.search(r"※|〈|主催|オンライン|午後|午前", cand):
                continue
            if re.match(r"^\d+月\d+日", cand):
                continue
            if 4 <= len(cand) <= 120:
                title = cand
                break
        if not title:
            continue

        venue = "阪急うめだ本店"
        if i+1 < len(lines) and lines[i+1].startswith("◎"):
            venue = lines[i+1].lstrip("◎").strip()

        key = (normalize_title(title), sd, venue)
        if key in seen:
            continue
        seen.add(key)

        context = " ".join(lines[max(0,i-5):min(len(lines),i+5)])
        full = f"{title} {venue} {context}"
        cat = classify(full)
        events.append({
            "title": title, "start_date": sd, "end_date": ed or sd,
            "area": "大阪", "venue": venue, "category": cat,
            "score": score(full, cat), "tags": make_tags(full, cat),
            "description": context[:170],
            "image_url": None, "source": "阪急うめだ本店",
            "source_url": source["url"],
        })
    return events

def dedicated_harukas(html, source):
    soup = BeautifulSoup(html, "html.parser")
    lines = [re.sub(r"\s+", " ", x).strip() for x in soup.stripped_strings]
    events = []
    seen = set()

    for i, line in enumerate(lines):
        if not re.search(r"[［\[]\s*\d{1,2}月\s*\d{1,2}日", line):
            continue
        sd, ed = extract_dates_from_html(soup, line)
        if not sd or (ed or sd) < date.today().isoformat():
            continue

        title = ""
        for j in range(i-1, max(-1,i-5), -1):
            cand = clean_event_title(lines[j])
            if 3 <= len(cand) <= 120 and not re.search(r"最終日|催会場|アートギャラリー|美術画廊", cand):
                title = cand
                break
        if not title:
            continue

        key = (normalize_title(title), sd)
        if key in seen:
            continue
        seen.add(key)

        context = " ".join(lines[max(0,i-3):min(len(lines),i+4)])
        venue = "あべのハルカス近鉄本店"
        full = f"{title} {venue} {context}"
        cat = classify(full)
        events.append({
            "title": title, "start_date": sd, "end_date": ed or sd,
            "area": "大阪", "venue": venue, "category": cat,
            "score": score(full, cat), "tags": make_tags(full, cat),
            "description": context[:170],
            "image_url": None, "source": "あべのハルカス近鉄本店",
            "source_url": source["url"],
        })
    return events

def collect_dedicated_listing_events(html, source):
    name = source["name"]
    if name == "ATCトップ":
        return dedicated_atc_home(html, source)
    if name.startswith("ATC"):
        # event検索ページは0件になることがあるので汎用専用は使わない
        return []
    if name == "LUCUA大阪":
        return dedicated_lucua(html, source)
    if name == "阪急うめだ本店":
        return dedicated_hankyu(html, source)
    if name == "あべのハルカス近鉄本店":
        return dedicated_harukas_v3(html, source)
    if name == "セブンパーク天美":
        return dedicated_sevenpark(html, source)
    return []

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
    """
    JSON-LDがないページ向け。
    time/meta/本文の日付・OG画像・会場を解析する。
    """
    html = fetch(url).text
    soup = BeautifulSoup(html, "html.parser")
    text_body = soup.get_text("\n", strip=True)

    h1 = soup.find("h1")
    title = h1.get_text(" ", strip=True) if h1 else ""
    if not title:
        ogt = soup.find("meta", property="og:title")
        title = ogt.get("content", "").strip() if ogt else ""
    if not title and soup.title:
        title = soup.title.get_text(" ", strip=True)
    if not title:
        return []

    # 一覧/カテゴリ/店舗トップなどを弾く
    if not page_looks_like_event(title, text_body):
        return []

    sd, ed = extract_dates_from_html(soup, text_body)
    if not sd:
        return []

    # 過去だけのページは早期除外
    if (ed or sd) < date.today().isoformat():
        return []

    desc_meta = (
        soup.find("meta", attrs={"name":"description"})
        or soup.find("meta", property="og:description")
    )
    desc = desc_meta.get("content", "").strip() if desc_meta else ""
    if not desc:
        # 冒頭のナビ文字列を避け、イベント語を含む段落を優先
        paragraphs = [
            p.get_text(" ", strip=True)
            for p in soup.find_all(["p","div"])
            if 30 <= len(p.get_text(" ", strip=True)) <= 500
        ]
        desc = next((p for p in paragraphs if page_looks_like_event("", p)), "")
    if not desc:
        desc = re.sub(r"\s+", " ", text_body)[:180]

    image_url = extract_meta_image(soup)
    venue = extract_venue_from_html(soup, text_body, forced_area)
    full = " ".join([title, desc, venue, text_body[:5000]])

    # 関西でないページを弾く。ただし大阪固定ソースは採用
    area = area_from_text(full)
    if area == "関西" and forced_area:
        area = forced_area
    if forced_area == "関西" and area == "関西":
        return []

    cat = classify(full)

    return [{
        "title": re.sub(r"\s*[|｜]\s*[^|｜]{3,50}$", "", title)[:110],
        "start_date": sd,
        "end_date": ed or sd,
        "area": area,
        "venue": venue,
        "category": cat,
        "score": score(full, cat),
        "tags": make_tags(full, cat),
        "description": desc[:170],
        "image_url": image_url,
        "source": source_name,
        "source_url": url,
    }]

def collect_generic_sources():
    events = []

    for source in MULTI_SOURCES:
        source_name = source["name"]
        try:
            list_html = fetch(source["url"]).text
        except Exception as e:
            diag(source_name, errors=1, note=f"list: {e}")
            print(f"[{source_name}] list error: {source['url']}: {e}", file=sys.stderr)
            list_html = ""

        # まず一覧ページを専用 + 汎用で解析
        listing_events = []
        if list_html:
            try:
                dedicated = collect_dedicated_listing_events(list_html, source)
                if dedicated:
                    listing_events.extend(dedicated)
                    diag(source_name, note=f"dedicated: {len(dedicated)}")
            except Exception as e:
                diag(source_name, note=f"dedicated-error: {e}")

            try:
                listing_events.extend(collect_events_from_listing_cards(list_html, source))
            except Exception as e:
                diag(source_name, note=f"listing-card: {e}")

            if source_name in ("大丸梅田店",):
                try:
                    listing_events.extend(collect_department_store_text(list_html, source))
                except Exception as e:
                    diag(source_name, note=f"department-list: {e}")

        if listing_events:
            diag(source_name, parsed=len(listing_events), note=f"listing fallback: {len(listing_events)}")
            events.extend(listing_events)

        # 詳細URLも従来どおり探索
        urls = discover_source_urls(list_html, source)
        print(f"[{source_name}] candidates: {len(urls)} / listing: {len(listing_events)}")

        def parse_one(u):
            try:
                parsed = parse_event_jsonld_page(u, source_name, source.get("area"))
                if not parsed:
                    parsed = parse_simple_event_page(u, source_name, source.get("area"))
                return u, parsed, None
            except Exception as e:
                return u, [], e

        workers = min(8, max(2, int(source.get("workers", 6))))
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = [ex.submit(parse_one, u) for u in urls]
            for fut in as_completed(futures):
                u, parsed, err = fut.result()
                if err:
                    diag(source_name, errors=1)
                    continue
                if parsed:
                    diag(source_name, parsed=len(parsed))
                    events.extend(parsed)

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
# 天王寺周辺・大阪南部優先
# -------------------------
def apply_local_priority(events):
    source_bonus = {
        "あべのハルカス近鉄本店": 16,
        "セブンパーク天美": 16,
        "ATC": 10,
        "ATCトップ": 10,
        "インテックス大阪": 8,
        "インテックス大阪関連": 8,
        "なんばパークス": 8,
        "大阪観光局": 6,
        "LUCUA大阪": 4,
    }
    place_bonus_words = {
        "天王寺": 18,
        "阿倍野": 18,
        "あべの": 18,
        "松原": 15,
        "天美": 18,
        "河内天美": 18,
        "なんば": 8,
        "難波": 8,
        "南港": 6,
    }

    for e in events:
        bonus = source_bonus.get(e.get("source",""), 0)
        merged = " ".join([
            e.get("title",""), e.get("venue",""), e.get("description","")
        ])
        for word, b in place_bonus_words.items():
            if word in merged:
                bonus = max(bonus, b)
        e["score"] = min(99, int(e.get("score", 50)) + bonus)
    return events




def detect_categories(text):
    """
    1イベントを複数カテゴリへ所属可能にする。
    例:
      京阪電車×アニメのコラボカフェ
        -> rail + anime + food
      自動車イベントのキッチンカー
        -> car（キッチンカーだけではfoodにしない）
    """
    t = text or ""
    cats = []

    def add(cat):
        if cat not in cats:
            cats.append(cat)

    # 鉄道
    if re.search(
        r"鉄道|電車|列車|新幹線|鉄道模型|駅弁|京阪電車|阪急電鉄|近鉄|JR西日本|南海電鉄|阪神電車",
        t, re.I
    ):
        add("rail")

    # AI・IT
    if re.search(
        r"生成AI|人工知能|ChatGPT|LLM|DX|ガジェット|パソコン|スマートフォン|"
        r"(?<![A-Za-z])AI(?![A-Za-z])|(?<![A-Za-z])IT(?![A-Za-z])|"
        r"(?<![A-Za-z])XR(?![A-Za-z])|(?<![A-Za-z])VR(?![A-Za-z])|"
        r"(?<![A-Za-z])AR(?![A-Za-z])|(?<![A-Za-z])PC(?![A-Za-z])",
        t, re.I
    ):
        add("tech")

    # アニメ・ゲーム
    if re.search(
        r"アニメ|マンガ|漫画|声優|コスプレ|コミック|キャラクター|"
        r"ゲーム(?:大会|イベント|フェス|体験|展示)?|eスポーツ|アニメイト|"
        r"オンリーショップ|コラボカフェ|キャラクターカフェ",
        t, re.I
    ):
        add("anime")

    # クルマ
    if re.search(
        r"モーターショー|オートメッセ|オートショー|カスタムカー|チューニングカー|"
        r"旧車|クラシックカー|スーパーカー|スポーツカー|電気自動車|EV車|"
        r"モータースポーツ|サーキット|ラリー|ドリフト|試乗会|カーイベント|"
        r"カーミーティング|自動車展示",
        t, re.I
    ):
        add("car")

    # 食・グルメ
    # 「食」単独や「キッチンカー」単独は誤爆が多いため使わない。
    if re.search(
        r"コラボカフェ|キャラクターカフェ|期間限定カフェ|カフェイベント|"
        r"グルメ(?:フェス|イベント|フェア)?|フード(?:フェス|イベント|フェア)?|"
        r"食フェス|食の祭典|ラーメン(?:祭|フェス|博|イベント|フェア)?|"
        r"カレー(?:祭|フェス|博|イベント|フェア)?|"
        r"スイーツ(?:フェア|フェス|イベント|博)?|"
        r"パン(?:祭|フェス|マルシェ|イベント|フェア)?|"
        r"肉フェス|日本酒(?:祭|フェス|イベント|フェア)?|"
        r"ビール(?:祭|フェス|イベント|フェア)?|"
        r"ワイン(?:祭|フェス|イベント|フェア)?|"
        r"物産展|北海道展|駅弁大会|駅弁フェア|"
        r"アフタヌーンティー|ビュッフェ|ブッフェ|デザートフェア|"
        r"チョコレート(?:博|フェア|イベント)|ショコラ(?:フェア|イベント)|"
        r"アイスクリーム(?:万博|フェア|イベント)",
        t, re.I
    ):
        add("food")

    # 展示
    if re.search(
        r"展覧会|企画展|特別展|美術展|写真展|博物館|美術館|アート展|原画展|展示会",
        t, re.I
    ):
        add("exhibition")

    if not cats:
        cats.append("tourism")
    return cats


# -------------------------
# カテゴリ・タグ最終正規化
# -------------------------
def normalize_event_categories_and_tags(events):
    for e in events:
        title = e.get("title","") or ""
        desc = e.get("description","") or ""
        venue = e.get("venue","") or ""

        # タイトルを重視しつつ、複数カテゴリ判定
        evidence = " ".join([title, title, title, desc, venue])
        cats = detect_categories(evidence)

        # 既存の主カテゴリ候補が複数カテゴリに含まれるなら維持。
        # それ以外は最初の高信頼カテゴリを主カテゴリにする。
        old_cat = e.get("category")
        if old_cat in cats:
            primary = old_cat
        else:
            primary = cats[0]

        e["category"] = primary
        e["categories"] = cats

        # 主タグに加えて、複数カテゴリの場合はカテゴリタグも最大3個まで反映
        tags = make_tags(evidence, primary)
        cat_label = {
            "rail": "鉄道",
            "tech": "AI・IT",
            "anime": "アニメ・ゲーム",
            "car": "クルマ",
            "food": "食・グルメ",
            "exhibition": "展示",
            "tourism": "イベント",
        }
        for c in cats:
            label = cat_label.get(c)
            if label and label not in tags:
                tags.append(label)
        e["tags"] = tags[:3]

    return events


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

    intex_events = collect_intex_events()
    if intex_events:
        diag("インテックス大阪専用", parsed=len(intex_events), note=f"dedicated total: {len(intex_events)}")
        events.extend(intex_events)

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
    events = normalize_event_categories_and_tags(events)
    events = apply_local_priority(events)
    events = filter_noise_events(events)
    events = dedupe(events)[:int(CONFIG.get("max_events", 100))]
    events = localize_images(events)

    if not events:
        print("イベント取得結果が0件のため既存events.jsonを保持します。", file=sys.stderr)
        sys.exit(2)

    # 収集状況をGitHub上で確認できるよう保存
    DIAGNOSTICS["TOTAL"] = {
        "final_events": len(events),
        "generated_at": datetime.now(JP_TZ).isoformat()
    }
    DIAGNOSTICS_PATH.write_text(
        json.dumps(DIAGNOSTICS, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    json_text = json.dumps(events, ensure_ascii=False, indent=2)

    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(json_text, encoding="utf-8")
    tmp.replace(OUT)

    DATA_JS.write_text(
        "window.EVENT_DATA = " + json_text + ";\n",
        encoding="utf-8"
    )

    print(f"{len(events)}件を events.json / events-data.js に保存しました。")
    print("Walkerplus / 公式サイト / X 統合。画像ローカル保存。")

if __name__ == "__main__":
    main()
