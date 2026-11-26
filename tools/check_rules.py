#!/usr/bin/env python3
"""校验 references/ 下规则卡格式。

检查项：
  1. 六个必填字段齐全（retired 卡只需「状态」+「证据」）
  2. 坏例、好例各自至少 1 个代码块，且开栏带语言标注
  3. ID 唯一
  4. 索引 ID 与卡片一致（漏登记/悬挂）
  5. 索引「证据」列与卡片证据条目数一致
退出码：0 PASS；1 FAIL
"""
import os, re, sys, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF = os.path.join(ROOT, "references")
INDEX = os.path.join(REF, "00-index.md")

REQUIRED = ["内容", "为什么", "坏例", "好例", "判定", "证据"]
ID_RE = re.compile(r"^#{2,3} (R-[A-Z]+-\d{2}) (.+)$")
FIELD_RE = re.compile(r"^- \*\*(.+?)\*\*[：:]", re.M)


def cards(path):
    text = open(path).read().splitlines()
    out, cur, in_fence = [], None, False
    for i, line in enumerate(text, 1):
        if line.startswith("```"):
            in_fence = not in_fence
            if cur is not None:
                cur["body"].append(line)
            continue
        if not in_fence:
            m = ID_RE.match(line)
            if m:
                if cur:
                    out.append(cur)
                cur = {"id": m.group(1), "title": m.group(2).strip(), "line": i,
                       "body": [], "file": os.path.basename(path)}
                continue
            if cur is not None and re.match(r"^#{1,3} ", line):
                out.append(cur)
                cur = None
                continue
        if cur is not None:
            cur["body"].append(line)
    if cur:
        out.append(cur)
    return out


def fences_between(body, start_field, end_field):
    """返回 start_field 与 end_field 之间的开栏语言列表。"""
    txt = "\n".join(body)
    m = re.search(r"- \*\*%s\*\*[：:](.*?)(?=\n- \*\*%s\*\*)" % (start_field, end_field), txt, re.S)
    if not m:
        return []
    fences = re.findall(r"^```(\w*)", m.group(1), re.M)
    return fences[0::2]   # 只取开栏（奇偶成对）


def evidence_count(body):
    txt = "\n".join(body)
    m = re.search(r"\*\*证据\*\*[：:](.*?)(?=\n- \*\*|\n## |\Z)", txt, re.S)
    if not m:
        return 0
    return sum(1 for ln in m.group(1).splitlines()
               if re.match(r"\s*- ", ln) and ("「" in ln or "raw:" in ln))


def main():
    quiet = "--quiet" in sys.argv
    errors, warnings, all_cards = [], [], []
    for fn in sorted(os.listdir(REF)) if os.path.isdir(REF) else []:
        if not fn.endswith(".md") or fn == "00-index.md":
            continue
        for c in cards(os.path.join(REF, fn)):
            all_cards.append(c)

    ids = collections.Counter(c["id"] for c in all_cards)
    for cid, n in ids.items():
        if n > 1:
            errors.append("重复 ID %s（%d 处）" % (cid, n))

    actual_evidence = {}
    for c in all_cards:
        body = "\n".join(c["body"])
        retired = ("状态" in body and "retired" in body)
        fields = set(FIELD_RE.findall(body))
        if retired:
            if "状态" not in fields or "证据" not in fields:
                errors.append("%s %s: retired 卡需「状态」与「证据」" % (c["file"], c["id"]))
            actual_evidence[c["id"]] = evidence_count(c["body"])
            continue
        for f in REQUIRED:
            if f not in fields:
                errors.append("%s %s: 缺字段「%s」" % (c["file"], c["id"], f))
        bad = fences_between(c["body"], "坏例", "好例")
        good = fences_between(c["body"], "好例", "判定")
        if len(bad) < 1:
            errors.append("%s %s: 坏例段至少 1 个代码块" % (c["file"], c["id"]))
        if len(good) < 1:
            errors.append("%s %s: 好例段至少 1 个代码块" % (c["file"], c["id"]))
        for lang in bad + good:
            if not lang:
                errors.append("%s %s: 代码块缺语言标注" % (c["file"], c["id"]))
        if len(c["title"]) > 40:
            warnings.append("%s %s: 标题超过 40 字" % (c["file"], c["id"]))
        ev = body.split("**证据**")[1] if "**证据**" in body else ""
        if not re.search(r"(session|rollout|Turn|raw:|用户原话)", ev):
            warnings.append("%s %s: 证据段缺少可回查引用" % (c["file"], c["id"]))
        actual_evidence[c["id"]] = evidence_count(c["body"])

    if os.path.exists(INDEX):
        idx = open(INDEX).read()
        indexed = set(re.findall(r"R-[A-Z]+-\d{2}", idx))
        defined = set(c["id"] for c in all_cards)
        for missing in sorted(defined - indexed):
            errors.append("索引缺登记: %s" % missing)
        for dangling in sorted(indexed - defined):
            errors.append("索引指向不存在的规则: %s" % dangling)
        for line in idx.splitlines():
            m = re.match(r"\| (R-[A-Z]+-\d{2}) \|.*\| (\d+) \|$", line)
            if m and m.group(1) in actual_evidence and int(m.group(2)) != actual_evidence[m.group(1)]:
                errors.append("索引证据数不一致 %s: 索引 %s / 实际 %d"
                              % (m.group(1), m.group(2), actual_evidence[m.group(1)]))
    else:
        warnings.append("缺少 references/00-index.md，跳过索引一致性检查")

    if not quiet:
        retired = sum(1 for c in all_cards if ("状态" in "\n".join(c["body"]) and "retired" in "\n".join(c["body"])))
        print("规则卡总数: %d（retired %d）" % (len(all_cards), retired))
        for f, n in sorted(collections.Counter(c["file"] for c in all_cards).items()):
            print("  %-34s %d" % (f, n))
    for w in warnings:
        print("WARN  " + w)
    for e in errors:
        print("ERROR " + e)
    print("结果: %s（%d 错误 / %d 警告）" % ("PASS" if not errors else "FAIL", len(errors), len(warnings)))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
