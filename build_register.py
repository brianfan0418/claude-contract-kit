#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""由合約 Markdown 的 YAML frontmatter 彙整產生 register.csv。

register.csv 是衍生資料，可隨時由 Markdown 重新產生；不要手改。
原始合約檔不由本程式讀寫（僅在給 --source-root 時讀取以核對 sha256）。

用法：
    python build_register.py --md-dir 合約庫/md --out 合約庫/register.csv
        [--source-root 合約庫/原檔] [--allow-unverified] [--fields schema/fields.json]

寫入條件（每份合約逐項檢查，任一項不符即不寫入，並列在報告中，結束碼為 1）：
    1. frontmatter 欄位型別、列舉值、必填欄位符合 fields.json。
    2. 須附出處的欄位（from_text）若有值且不是「未載明」，至少有一筆 citations，
       且每筆引用須有頁碼或條號；quote 逐字出現在本檔內文；有 page 者須出現在該頁區段內。
    3. verification_status 為「已驗證」（--allow-unverified 時放寬，僅供草稿檢視）。
    4. 給 --source-root 時，source_sha256 須與原檔相符。
    5. needs_review 不得為 true；掃描時排除所有 _history/ 目錄。

frontmatter 格式（YAML 子集）：
    key: "字串"            字串以 JSON 雙引號書寫，可含 \\n、\\"
    key: 123 / true / null
    citations:              之後每行一筆，以兩個空白縮排，內容為單行 JSON 物件
      - {"field":"end_date","page":3,"clause":"第5條","quote":"本合約有效期間至..."}
本檔只用 Python 標準庫，故不依賴完整 YAML 解析器；請依上列格式書寫。
"""

import argparse
import csv
import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_FIELDS = HERE / "schema" / "fields.json"
PAGE_RE = re.compile(r"<!--\s*page:\s*(\d+)\s*-->")
UNSTATED = "未載明"


def parse_scalar(text):
    text = text.strip()
    if text == "":
        return ""
    if text[0] in '"[{' or text in ("true", "false", "null") or re.fullmatch(r"-?\d+(\.\d+)?", text):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
    return text


def split_document(text):
    """回傳 (meta dict, body)。沒有 frontmatter 時 meta 為 None。"""
    lines = text.lstrip("﻿").splitlines()
    if not lines or lines[0].strip() != "---":
        return None, text
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        raise ValueError("frontmatter 沒有結尾的 ---")
    meta, current = {}, None
    for n, line in enumerate(lines[1:end], start=2):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith("  - ") and current is not None:
            if not isinstance(meta.get(current), list):
                meta[current] = []
            try:
                meta[current].append(json.loads(line[4:]))
            except json.JSONDecodeError as exc:
                raise ValueError(f"frontmatter 第 {n} 行不是單行 JSON：{exc}") from exc
            continue
        if ":" not in line or line.startswith(" "):
            raise ValueError(f"frontmatter 第 {n} 行格式不符：{line!r}")
        key, value = line.split(":", 1)
        current = key.strip()
        meta[current] = parse_scalar(value)
    return meta, "\n".join(lines[end + 1:])


def dump_frontmatter(meta):
    """把 meta 寫成 frontmatter 文字（含前後 ---），list 值逐行寫成單行 JSON。"""
    out = ["---"]
    for key, value in meta.items():
        if isinstance(value, list) and value:
            out.append(f"{key}:")
            out.extend("  - " + json.dumps(item, ensure_ascii=False) for item in value)
        else:
            out.append(f"{key}: {json.dumps(value, ensure_ascii=False)}")
    out.append("---")
    return "\n".join(out) + "\n"


def page_sections(body):
    """回傳 {頁碼: 該頁文字}；沒有頁標記時回傳空 dict。"""
    marks = list(PAGE_RE.finditer(body))
    sections = {}
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(body)
        sections[int(m.group(1))] = sections.get(int(m.group(1)), "") + body[m.end():end]
    return sections


def load_schema(path):
    schema = json.loads(Path(path).read_text(encoding="utf-8"))
    enums = {k: [e["label"] for e in v] for k, v in schema["enums"].items()}
    return schema["fields"], enums


def check_value(field, value, enums):
    """回傳錯誤訊息或 None。value 已轉成字串。"""
    if value == "":
        return None
    t = field["type"]
    if t == "date":
        try:
            dt.date.fromisoformat(value)
        except ValueError:
            return f"{field['name']}：日期須為 YYYY-MM-DD，實際為 {value!r}"
    elif t == "integer":
        if not re.fullmatch(r"-?\d+", value):
            return f"{field['name']}：須為整數，實際為 {value!r}"
    elif t == "number":
        try:
            float(value)
        except ValueError:
            return f"{field['name']}：須為數字，實際為 {value!r}"
    elif t == "enum" and value not in enums[field["enum"]]:
        return f"{field['name']}：{value!r} 不在列舉 {enums[field['enum']]} 中"
    return None


def check_citations(meta, body, fields):
    errors = []
    cites = meta.get("citations") or []
    if not isinstance(cites, list):
        return ["citations 須為清單"]
    sections = page_sections(body)
    flat = body
    for i, c in enumerate(cites, start=1):
        if (not isinstance(c, dict) or not c.get("field")
                or not isinstance(c.get("quote"), str) or not c["quote"].strip()):
            errors.append(f"citations 第 {i} 筆缺 field 或 quote")
            continue
        quote = str(c["quote"])
        page = c.get("page")
        clause = c.get("clause")
        if page in (None, "") and (not isinstance(clause, str) or not clause.strip()):
            errors.append(f"citations 第 {i} 筆（{c['field']}）：須有頁碼或條號")
            continue
        if page not in (None, ""):
            text = sections.get(int(page), "") if str(page).isdigit() else ""
            if not text:
                errors.append(f"citations 第 {i} 筆（{c['field']}）：內文沒有第 {page} 頁的頁標記或該頁無文字")
            elif quote not in text:
                errors.append(f"citations 第 {i} 筆（{c['field']}）：quote 不在第 {page} 頁原文中")
        elif quote not in flat:
            errors.append(f"citations 第 {i} 筆（{c['field']}）：quote 不在原文中")
    cited = {c.get("field") for c in cites if isinstance(c, dict)}
    for f in fields:
        v = str(meta.get(f["name"], "") if meta.get(f["name"]) is not None else "")
        if f.get("from_text") and v not in ("", UNSTATED) and f["name"] not in cited:
            errors.append(f"{f['name']}：有值但沒有 citations")
    return errors


def validate(meta, body, fields, enums, allow_unverified=False, source_root=None):
    errors = []
    for f in fields:
        raw = meta.get(f["name"])
        value = "" if raw is None else str(raw)
        if f["required"] and value == "":
            errors.append(f"{f['name']}：必填欄位為空")
        e = check_value(f, value, enums)
        if e:
            errors.append(e)
    status = meta.get("verification_status")
    verification = enums["verification_status"]
    if status not in verification:
        errors.append(f"verification_status 須為 {verification}")
    elif status != "已驗證" and not allow_unverified:
        errors.append(f"verification_status 為「{status}」，未通過驗證不寫入主檔")
    if meta.get("needs_review") is True:
        errors.append("needs_review 為 true，原檔更新後尚未複核，不寫入主檔")
    sha = str(meta.get("source_sha256", ""))
    if not re.fullmatch(r"[0-9a-f]{64}", sha):
        errors.append("source_sha256 須為 64 碼小寫十六進位")
    if not meta.get("source_path"):
        errors.append("source_path 為空")
    errors.extend(check_citations(meta, body, fields))
    if source_root and meta.get("source_path"):
        src = Path(source_root) / str(meta["source_path"])
        if not src.is_file():
            errors.append(f"找不到原檔 {src}")
        elif hashlib.sha256(src.read_bytes()).hexdigest() != sha:
            errors.append("原檔 sha256 與 frontmatter 不符（原檔被更動或已換版）")
    return errors


def build(md_dir, fields_path=DEFAULT_FIELDS, allow_unverified=False, source_root=None):
    """回傳 (rows, problems)；problems 為 [(檔名, [錯誤...])]。"""
    fields, enums = load_schema(fields_path)
    rows, problems, seen = [], [], {}
    for path in sorted(Path(md_dir).rglob("*.md")):
        if "_history" in path.relative_to(md_dir).parts[:-1]:
            continue
        try:
            meta, body = split_document(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, UnicodeDecodeError) as exc:
            problems.append((str(path), [str(exc)]))
            continue
        if meta is None:
            continue  # 沒有 frontmatter 的 Markdown 不是合約檔（例如說明檔）
        errors = validate(meta, body, fields, enums, allow_unverified, source_root)
        cid = str(meta.get("contract_id", ""))
        if cid in seen:
            errors.append(f"contract_id 與 {seen[cid]} 重複")
        seen.setdefault(cid, str(path))
        if errors:
            problems.append((str(path), errors))
            continue
        rows.append({f["name"]: ("" if meta.get(f["name"]) is None else str(meta[f["name"]])) for f in fields})
    rows.sort(key=lambda r: r["contract_id"])
    return rows, problems


def write_csv(rows, fields_path, out):
    fields, _ = load_schema(fields_path)
    with open(out, "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=[f["name"] for f in fields], lineterminator="\r\n")
        writer.writeheader()
        writer.writerows(rows)


def main(argv=None):
    p = argparse.ArgumentParser(description="由合約 Markdown frontmatter 產生 register.csv")
    p.add_argument("--md-dir", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--fields", default=str(DEFAULT_FIELDS))
    p.add_argument("--source-root")
    p.add_argument("--allow-unverified", action="store_true")
    a = p.parse_args(argv)
    rows, problems = build(a.md_dir, a.fields, a.allow_unverified, a.source_root)
    write_csv(rows, a.fields, a.out)
    print(f"已寫入 {a.out}：{len(rows)} 筆")
    for name, errs in problems:
        print(f"未寫入 {name}")
        for e in errs:
            print(f"  - {e}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
