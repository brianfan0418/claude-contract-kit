#!/usr/bin/env python3
"""從全國法規資料庫下載法規；公布與施行狀態分別保存。"""

import argparse
import datetime as dt
import io
import json
import re
import sys
import tempfile
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path

BASE = "https://law.moj.gov.tw"
DEFAULT_CACHE = Path(__file__).resolve().parents[1] / "law-cache"
CODE = re.compile(r"[A-Z][0-9]{7}\Z")
MAX_DOWNLOAD = 96 * 1024 * 1024
MAX_JSON = 512 * 1024 * 1024


def official_url(url):
    parts = urllib.parse.urlsplit(url)
    if (parts.scheme != "https" or parts.netloc != "law.moj.gov.tw"
            or parts.username or parts.password):
        raise ValueError("來源及重新導向只接受 https://law.moj.gov.tw/")
    return url


class OfficialRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        official_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download(url):
    official_url(url)
    request = urllib.request.Request(url, headers={"User-Agent": "contract-kit-law-cache/1.0"})
    opener = urllib.request.build_opener(OfficialRedirect())
    with opener.open(request, timeout=45) as response:
        official_url(response.geturl())
        data = response.read(MAX_DOWNLOAD + 1)
    if len(data) > MAX_DOWNLOAD:
        raise ValueError("下載資料超過工具上限，未寫入快取")
    return data


def resolve_name(name, fetch=download, category=None):
    """官方批次 API 只用於精確名稱查找，不將其公布版本逕認為已施行。"""
    for kind in ([category] if category else ["law", "order"]):
        url = f"{BASE}/api/ch/{kind}/json"
        raw = fetch(url)
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            filename = "ChLaw.json" if kind == "law" else "ChOrder.json"
            member = archive.getinfo(filename)
            if member.file_size > MAX_JSON:
                raise ValueError("解壓資料超過工具上限")
            document = json.loads(archive.read(member).decode("utf-8-sig"))
        matches = [law for law in document["Laws"] if law["LawName"] == name]
        if len(matches) > 1:
            raise ValueError("同名法規不唯一，請核對官方網址後使用 --code")
        if matches:
            law = matches[0]
            if str(law.get("LawAbandonNote", "")).strip():
                raise ValueError("官方資料標示廢止，不能作為現行法規")
            parts = urllib.parse.urlsplit(official_url(law["LawURL"]))
            codes = urllib.parse.parse_qs(parts.query).get("pcode", [])
            if len(codes) != 1 or not CODE.fullmatch(codes[0]):
                raise ValueError("官方資料缺少有效法規代碼")
            return codes[0], url, str(document.get("UpdateDate", ""))
    raise ValueError("查不到完全相符的法規名稱；請核對全名或使用 --code")


@dataclass
class Node:
    tag: str
    attrs: dict = field(default_factory=dict)
    children: list = field(default_factory=list)

    def walk(self):
        yield self
        for child in self.children:
            if isinstance(child, Node):
                yield from child.walk()

    def text(self):
        result = []
        for child in self.children:
            if isinstance(child, str):
                result.append(child)
            elif child.tag == "br":
                result.append("\n")
            else:
                result.append(child.text())
                if child.tag in {"div", "p", "li"}:
                    result.append("\n")
        return "".join(result).replace("\xa0", " ").strip()

    def has_class(self, name):
        return name in self.attrs.get("class", "").split()


class Document(HTMLParser):
    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.root = Node("root")
        self.stack = [self.root]
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        node = Node(tag, dict(attrs))
        self.stack[-1].children.append(node)
        if tag not in self.VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def metadata(root, label):
    for node in root.walk():
        if node.tag == "tr":
            headers = [c for c in node.children if isinstance(c, Node) and c.tag == "th"]
            values = [c for c in node.children if isinstance(c, Node) and c.tag == "td"]
            if headers and values and headers[0].text().rstrip("：: ") == label:
                return values[0].text()
    return ""


def parse_page(raw):
    root = Document(raw.decode("utf-8-sig")).root
    name = metadata(root, "法規名稱")
    # EN 為網站的英譯導覽，不是法規名稱。
    named = next((n for n in root.walk() if n.attrs.get("id") == "hlLawName"), None)
    law_code = ""
    if named:
        name = named.text()
        codes = urllib.parse.parse_qs(urllib.parse.urlsplit(named.attrs.get("href", "")).query).get("pcode", [])
        if len(codes) == 1:
            law_code = codes[0].upper()
    date_text = metadata(root, "修正日期") or metadata(root, "公布日期")
    date = re.search(r"民國\s*(\d+)\s*年\s*(\d+)\s*月\s*(\d+)\s*日", date_text)
    if not name or not date:
        raise ValueError("官方頁面缺少法規名稱／修正或公布日期；未寫入快取")
    modified = dt.date(int(date[1]) + 1911, int(date[2]), int(date[3])).isoformat()
    if metadata(root, "廢止日期") or metadata(root, "廢止註記"):
        raise ValueError("官方頁面標示廢止，不能作為現行法規")
    articles = []
    for node in root.walk():
        if node.has_class("row"):
            numbers = [n for n in node.children if isinstance(n, Node) and n.has_class("col-no")]
            texts = [n for n in node.children if isinstance(n, Node) and n.has_class("col-data")]
            if numbers and texts:
                number, text = numbers[0].text(), texts[0].text()
                if not re.fullmatch(r"第\s*\d+(?:-\d+)?\s*條", number) or not text:
                    raise ValueError("條號或條文格式不符；未寫入快取")
                articles.append((number, text))
    if not articles or len({n for n, _ in articles}) != len(articles):
        raise ValueError("官方頁面無完整且不重複的條文；未寫入快取")
    state = metadata(root, "生效狀態")
    old_link = next((n.attrs.get("href") for n in root.walk()
                     if n.tag == "a" and n.attrs.get("id") == "hyLawCon"), None)
    return {"name": name, "code": law_code, "modified": modified, "articles": articles,
            "state": state, "old_link": old_link}


def render_articles(articles, source_url, fetched_date):
    lines = []
    for number, text in articles:
        lines.extend([f"### {number}", "", text, "",
                      f"出處：[{source_url}]({source_url})；抓取日期：{fetched_date}。", ""])
    return lines


def fetch_law(code, cache_dir=DEFAULT_CACHE, fetch=download, clock=None,
              lookup_url="", dataset_updated=""):
    code = code.upper()
    if not CODE.fullmatch(code):
        raise ValueError("法規代碼格式須為一個英文字母及七個數字")
    source = f"{BASE}/LawClass/LawAll.aspx?pcode={code}"
    page = parse_page(fetch(source))
    if page["code"] != code:
        raise ValueError("官方頁面法規代碼缺失或與請求不符；未寫入快取")
    fetched = (clock or dt.datetime.now(dt.timezone(dt.timedelta(hours=8)))).isoformat(timespec="seconds")
    fetched_date = fetched[:10]
    pending = "尚未生效" in page["state"]
    history = None
    history_url = ""
    if pending:
        if not page["old_link"]:
            raise ValueError("有未生效註記但無官方舊法連結；未寫入快取")
        history_url = official_url(urllib.parse.urljoin(source, page["old_link"]))
        previous_codes = urllib.parse.parse_qs(urllib.parse.urlsplit(history_url).query).get("pcode", [])
        if previous_codes != [code]:
            raise ValueError("官方舊法連結代碼與請求不符；未寫入快取")
        history = parse_page(fetch(history_url))
        if history["name"] != page["name"]:
            raise ValueError("官方舊法名稱不符；未寫入快取")
    status = "部分或全部尚未生效，須逐條核對" if pending else "官方頁面未標示尚未生效，仍須法務核對"
    front = {"law_name": page["name"], "law_code": code, "source_url": source,
             "law_modified_date": page["modified"], "fetched_date": fetched_date,
             "fetched_at": fetched, "effective_status": status,
             "current_text_verified": False,
             "lookup_source_url": lookup_url, "dataset_updated_at": dataset_updated}
    if history:
        front.update({"previous_source_url": history_url, "previous_modified_date": history["modified"]})
    lines = ["---"] + [f"{key}: {json.dumps(value, ensure_ascii=False)}" for key, value in front.items()]
    lines.extend(["---", "", f"# {page['name']}", "",
                  "以全國法規資料庫現行條文為準。須法務核對現行條文及施行狀態。", "",
                  "引用格式：法規名稱、第 X 條、版本來源網址、抓取日期 YYYY-MM-DD。", "",
                  f"生效狀態：{status}。本快取不自動認定條文已施行。", ""])
    if page["state"]:
        lines.extend(["## 官方生效註記", "", page["state"], ""])
    lines.extend(["## 官方所有條文頁版本", ""])
    lines.extend(render_articles(page["articles"], source, fetched_date))
    if history:
        lines.extend(["## 官方連結舊法版本（供施行狀態對照）", "",
                      "本節為網站指定的舊版本，不表示每條舊法均仍適用；引用前依生效註記逐條核對。", ""])
        lines.extend(render_articles(history["articles"], history_url, fetched_date))
    safe_name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", page["name"]).strip(". ")
    if not safe_name:
        raise ValueError("法規名稱不能形成安全檔名")
    folder = Path(cache_dir)
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{safe_name}.md"
    # 全部下載及檢查成功後才原子替換，失敗保留既有快取。
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=folder,
                                     suffix=".tmp", delete=False) as handle:
        handle.write("\n".join(lines))
        temp = Path(handle.name)
    temp.replace(target)
    return target, pending


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    query = parser.add_mutually_exclusive_group(required=True)
    query.add_argument("--name", help="官方完整法規名稱，例如民法；民法債編請用民法")
    query.add_argument("--code", help="官方 pcode，例如 B0000001")
    parser.add_argument("--category", choices=["law", "order"], help="名稱查找只下載法律或命令索引")
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE)
    args = parser.parse_args(argv)
    try:
        lookup, updated = "", ""
        if args.name:
            code, lookup, updated = resolve_name(args.name, category=args.category)
        else:
            code = args.code
        path, pending = fetch_law(code, args.cache_dir, lookup_url=lookup, dataset_updated=updated)
        print(path)
        if pending:
            print("官方有尚未生效註記；已附舊法版本，引用前須逐條核對。", file=sys.stderr)
        return 0
    except (ValueError, KeyError, OSError, zipfile.BadZipFile) as exc:
        print(f"抓取失敗：{exc}。既有快取不能當作本次現抓結果。", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
