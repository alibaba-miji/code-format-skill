#!/usr/bin/env python3
"""生成 references/00-index.md（规则总索引）。自包含，随 skill 分发。

列：ID / 规范 / 一句话 / 证据数（证据段内的证据条目数）。
一句话在句读处截断并补 `…`，避免断在标识符/反引号中间。
"""
import os, re, glob, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF = os.path.join(ROOT, "references")
ID_RE = re.compile(r"^#{2,3} (R-[A-Z]+-\d{2}) (.+)$", re.M)
CAT = {
    "REV": ("review 输出契约", "10-review.md"),
    "MIN": ("最小实现", "20-minimal.md"),
    "OWN": ("所有权与接口形态", "30-ownership.md"),
    "STA": ("状态、缓冲与指标", "40-state.md"),
    "CFG": ("配置与契约边界", "50-config.md"),
    "TST": ("测试与验证", "60-test.md"),
    "DIF": ("diff、提交与说明", "70-diff.md"),
    "WRK": ("工作纪律", "80-workflow.md"),
}


def clip(s, n=78):
    s = " ".join((s or "").split())
    if len(s) <= n:
        return s
    cut = s[:n]
    # 不切断反引号内的代码片段
    if cut.count("`") % 2 == 1:
        cut = cut[:cut.rfind("`")]
    # 不切断 ASCII 标识符/单词
    while cut and cut[-1].isalnum() and len(cut) < len(s) and s[len(cut)].isalnum():
        cut = cut[:-1]
    # 尽量在句读处收口
    for sep in ("。", "；", "，", "：", " "):
        p = cut.rfind(sep)
        if p >= n // 2:
            cut = cut[:p]
            break
    cut = cut.rstrip("：:，,；; ")
    if cut.count("`") % 2 == 1:      # 补上未闭合的反引号
        cut += "`"
    return cut + "…"


def split_cards(text):
    """按 ID 标题切卡，忽略代码块内的 # 行。"""
    lines = text.splitlines()
    cards, cur, in_fence = [], None, False
    for line in lines:
        if line.startswith("```"):
            in_fence = not in_fence
        if not in_fence:
            m = ID_RE.match(line)
            if m:
                if cur:
                    cards.append(cur)
                cur = {"id": m.group(1), "title": m.group(2).strip(), "body": []}
                continue
            if cur is not None and re.match(r"^#{1,3} ", line):
                cards.append(cur)
                cur = None
                continue
        if cur is not None:
            cur["body"].append(line)
    if cur:
        cards.append(cur)
    return cards


def evidence_count(body):
    """证据段内的条目数（缩进 `- ` 开头，且含引号或 raw）。"""
    txt = "\n".join(body)
    m = re.search(r"\*\*证据\*\*[：:](.*?)(?=\n- \*\*|\n## |\Z)", txt, re.S)
    if not m:
        return 0
    return sum(1 for ln in m.group(1).splitlines()
               if re.match(r"\s*- ", ln) and ("「" in ln or "raw:" in ln))


def main():
    cards = []
    for f in sorted(glob.glob(os.path.join(REF, "*.md"))):
        if os.path.basename(f) == "00-index.md":
            continue
        for c in split_cards(open(f).read()):
            c["file"] = os.path.basename(f)
            body = "\n".join(c["body"])
            cm = re.search(r"- \*\*内容\*\*[：:]\s*(.+)", body)
            c["content"] = cm.group(1).strip() if cm else ""
            c["evidence"] = evidence_count(c["body"])
            c["retired"] = ("状态" in body and "retired" in body)
            cards.append(c)

    by_cat = collections.defaultdict(list)
    for c in cards:
        by_cat[c["id"].split("-")[1]].append(c)

    lines = ["# 规则总索引", "",
             "共 %d 条规则（其中 retired %d 条）。`证据` 列 = 该卡证据段内的证据条目数；`1` 表示单一证据（仍可用，复核时优先核）。"
             % (len(cards), sum(1 for c in cards if c["retired"])), "",
             "| 类别 | 文件 | 规则数 |", "|---|---|---|"]
    for k, (name, fn) in CAT.items():
        if by_cat.get(k):
            lines.append("| %s | [%s](%s) | %d |" % (name, fn, fn, len(by_cat[k])))
    lines.append("")
    for k, (name, fn) in CAT.items():
        if not by_cat.get(k):
            continue
        lines.append("\n## %s — %s\n" % (k, name))
        lines.append("| ID | 规范 | 一句话 | 证据 |")
        lines.append("|---|---|---|---|")
        for c in by_cat[k]:
            title = c["title"] + ("（retired）" if c["retired"] else "")
            lines.append("| %s | %s | %s | %d |" % (c["id"], title, clip(c["content"]), c["evidence"]))
    open(os.path.join(REF, "00-index.md"), "w").write("\n".join(lines) + "\n")
    print("cards: %d (retired %d)" % (len(cards), sum(1 for c in cards if c["retired"])))
    for k, v in sorted(by_cat.items()):
        print(" ", k, len(v), "single-evidence:", sum(1 for c in v if c["evidence"] <= 1))


if __name__ == "__main__":
    main()
