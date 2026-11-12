#!/usr/bin/env python3
"""Evidence-led Chinese company and industry research report generator.

Uses Tavily for web search and an OpenAI-compatible chat-completions API for
synthesis. Financial growth calculations are performed locally from CSV data.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


QUESTIONS = [
    "行业未来五年是存量市场、中低增速市场，还是高增市场？请给出市场规模、增速区间、预测年份及口径，并区分名义增速与实际增速。",
    "行业或赛道海外和中国国内的CR5分别是多少？列出前五名及各自市占率，注明统计范围、年份、市场口径和来源；如果没有可靠数据，明确说明。",
    "公司过去五年的核心发展逻辑是什么？未来五年的发展逻辑是什么？分别梳理驱动因素、关键转折、战略/产���/产能变化、增长假设与风险。",
    "仔细梳理公司的供应商结构、客户结构和周期依赖度。关注披露的前五大供应商/客户占比、集中度变化、议价能力、上下游地域/行业暴露及库存/资本开支/价格周期。区分已披露事实与推断。",
    "公司的研发投入占比是多少？历年扣非归母净利润增速跟得上营业收入增速吗？请按年度比较，并解释基数、一次性因素或口径变化。优先使用年报/公告数据。",
]


def search_queries(company: str, industry: str) -> list[list[str]]:
    return [
        [f"{industry} 全球 中国 市场规模 未来五年 CAGR 预测", f"{industry} market size forecast 2030 CAGR China global"],
        [f"{industry} 中国 CR5 市占率 前五 市场份额", f"{industry} global market share top five CR5"],
        [f"{company} 年报 发展战略 过去五年 未来战略", f"{company} annual report strategy five year business outlook"],
        [f"{company} 年报 前五大客户 供应商 占比 周期", f"{company} annual report top customers suppliers concentration cyclicality"],
        [f"{company} 年报 研发费用 营收 扣非净利润", f"{company} R&D expense revenue adjusted net profit annual report"],
    ]


@dataclass
class Source:
    sid: str
    title: str
    url: str
    snippet: str
    query: str


def http_json(url: str, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json", **headers}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"API 请求失败 ({exc.code}): {detail[:1000]}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"无法连接 API: {exc}") from exc


def collect_sources(company: str, industry: str, tavily_key: str, max_results: int) -> list[list[Source]]:
    grouped: list[list[Source]] = []
    sid_num = 1
    for question_queries in search_queries(company, industry):
        group: list[Source] = []
        seen: set[str] = set()
        for query in question_queries:
            data = http_json(
                "https://api.tavily.com/search",
                {"api_key": tavily_key, "query": query, "search_depth": "advanced", "max_results": max_results, "include_answer": False},
                {},
            )
            for item in data.get("results", []):
                url = item.get("url", "")
                if not url or url in seen:
                    continue
                seen.add(url)
                group.append(Source(f"S{sid_num}", item.get("title", "未命名来源"), url,
                                    item.get("content", ""), query))
                sid_num += 1
        grouped.append(group)
    return grouped


def load_financials(path: str | None) -> tuple[list[dict[str, float]], list[str]]:
    if not path:
        return [], []
    records: list[dict[str, float]] = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        required = {"year", "revenue", "adjusted_net_profit"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"财务 CSV 缺少必需列: {', '.join(sorted(missing))}")
        for line, row in enumerate(reader, 2):
            try:
                rec = {"year": float(row["year"]), "revenue": float(row["revenue"]),
                       "adjusted_net_profit": float(row["adjusted_net_profit"])}
                rd = (row.get("rd_expense") or "").strip()
                if rd:
                    rec["rd_expense"] = float(rd)
                records.append(rec)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"财务 CSV 第 {line} 行有无效数值") from exc
    records.sort(key=lambda r: r["year"])
    return records, financial_summary(records)


def pct_change(current: float, previous: float) -> str:
    if previous == 0:
        return "不适用（上年为零）"
    if previous < 0 or current < 0:
        return "不宜直接比较（存在负值）"
    return f"{(current / previous - 1) * 100:.2f}%"


def financial_summary(records: list[dict[str, float]]) -> list[str]:
    if not records:
        return []
    out = ["| 年度 | 营业收入 | 营收同比 | 扣非净利润 | 扣非净利润同比 | 研发费用 | 研发费用率 |",
           "|---:|---:|---:|---:|---:|---:|---:|"]
    for i, row in enumerate(records):
        prev = records[i - 1] if i else None
        revenue_growth = pct_change(row["revenue"], prev["revenue"]) if prev else "—"
        profit_growth = pct_change(row["adjusted_net_profit"], prev["adjusted_net_profit"]) if prev else "—"
        rd = row.get("rd_expense")
        rd_value = f"{rd:,.2f}" if rd is not None else "未提供"
        rd_ratio = f"{rd / row['revenue'] * 100:.2f}%" if rd is not None and row["revenue"] else "未提供"
        out.append(f"| {int(row['year'])} | {row['revenue']:,.2f} | {revenue_growth} | {row['adjusted_net_profit']:,.2f} | {profit_growth} | {rd_value} | {rd_ratio} |")
    if len(records) > 1:
        out.append("")
        out.append("**增速对比提示：**逐年比较营收同比与扣非净利润同比；不能只看单一年份。负利润/零基数的增速不作常规百分比解释，需结合绝对额和年报说明。")
    return out


def source_text(groups: list[list[Source]]) -> str:
    blocks = []
    for i, group in enumerate(groups):
        blocks.append(f"### 问题 {i + 1} 的检索证据")
        if not group:
            blocks.append("本轮没有检索到结果。")
        for source in group:
            blocks.append(f"[{source.sid}] {source.title}\nURL: {source.url}\n检索词: {source.query}\n摘要: {source.snippet}")
    return "\n\n".join(blocks)


def render_template(company: str, industry: str, evidence: str = "", finances: list[str] | None = None) -> str:
    sections = [f"# {company}｜{industry} 研究报告", "", "> 研究日期：以运行日期为准。结论必须区分事实、估算与判断；每项关键事实应引用来源编号。", ""]
    for i, question in enumerate(QUESTIONS, 1):
        sections.extend([f"## {i}. {question}", "", "### 结论", "待研究。", "", "### 证据与分析", "待补充；没有可靠数据时请明确标注数据缺口。", ""])
    if finances:
        sections.extend(["## 财务数据计算（用户提供 CSV；请核对年报口径）", "", *finances, ""])
    if evidence:
        sections.extend(["## 检索证据", "", evidence, ""])
    sections.extend(["## 研究限制与待核实事项", "", "- 核对市场定义、币种、统计年份和合并报表口径。", "- 搜索摘要不等于原始披露；重要数据需回到年报、公告或行业报告原文验证。", "- 对预测、CR5、客户/供应商集中度等无可靠来源的数据，不得推测填数。", ""])
    return "\n".join(sections)


def synthesize(company: str, industry: str, evidence: str, finances: list[str], api_key: str,
               base_url: str, model: str) -> str:
    system = ("你是一位严谨的行业与公司研究助理。用中文回答五个指定问题。只能依据给定证据和财务表；不得编造数据、市场份额、预测或公司披露。"
              "每个重要事实后标注来源编号 [S#]，只在来源支持时引用。明确事实/估算/判断，注明年份、口径和单位。"
              "尤其对CR5和前五大客户/供应商，逐家公司列示来源可验证的数值；证据不足就明示未知，不要用搜索摘要冒充原始公告。"
              "未来判断要列出假设、驱动因素和风险。输出包含五个编号章节及简短研究限制。")
    user = f"公司：{company}\n行业/赛道：{industry}\n\n五个问题：\n" + "\n".join(f"{i}. {q}" for i, q in enumerate(QUESTIONS, 1))
    user += "\n\n财务计算表（如有）：\n" + ("\n".join(finances) if finances else "未提供结构化财务 CSV。请只引用检索到的财务证据，并注明年份。")
    user += "\n\n检索证据：\n" + evidence
    url = base_url.rstrip("/") + "/chat/completions"
    result = http_json(url, {"model": model, "temperature": 0.1,
                             "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]},
                       {"Authorization": f"Bearer {api_key}"})
    try:
        return result["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"模型 API 返回格式异常: {json.dumps(result, ensure_ascii=False)[:1000]}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description="自动检索并生成中文行业/公司研究报告")
    parser.add_argument("--company", required=True, help="公司名称")
    parser.add_argument("--industry", required=True, help="行业或赛道")
    parser.add_argument("--financials", help="财务 CSV：year,revenue,adjusted_net_profit[,rd_expense]")
    parser.add_argument("--output", default="research-report.md", help="报告文件路径")
    parser.add_argument("--template-only", action="store_true", help="只生成带研究问题的报告模板，不调用外部 API")
    parser.add_argument("--max-results", type=int, default=5, help="每条搜索词最多返回条数（1-10）")
    args = parser.parse_args()
    if not 1 <= args.max_results <= 10:
        parser.error("--max-results 必须在 1 到 10 之间")
    try:
        records, finance_lines = load_financials(args.financials)
        if args.template_only:
            report = render_template(args.company, args.industry, finances=finance_lines)
        else:
            tavily_key = os.getenv("TAVILY_API_KEY")
            llm_key = os.getenv("LLM_API_KEY")
            if not tavily_key or not llm_key:
                raise ValueError("请设置 TAVILY_API_KEY 和 LLM_API_KEY；或使用 --template-only 生成空白模板。")
            groups = collect_sources(args.company, args.industry, tavily_key, args.max_results)
            evidence = source_text(groups)
            base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
            model = os.getenv("LLM_MODEL", "gpt-4o-mini")
            answer = synthesize(args.company, args.industry, evidence, finance_lines, llm_key, base_url, model)
            report = f"# {args.company}｜{args.industry} 研究报告\n\n> 由自动化流程生成；关键结论须核对原始披露。\n\n{answer}\n\n## 财务数据计算（用户提供 CSV）\n\n" + ("\n".join(finance_lines) if finance_lines else "未提供结构化财务 CSV。") + f"\n\n## 来源清单\n\n{evidence}\n"
        Path(args.output).write_text(report, encoding="utf-8")
        print(f"报告已生成：{args.output}")
        return 0
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
