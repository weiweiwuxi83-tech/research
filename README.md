# 自动化行业与公司研究流程

此仓库提供一个可运行的中文研究报告生成器，围绕以下五项问题搜集公开网页证据并生成初稿：

1. 行业未来五年的市场属性与增速；
2. 海外/国内市场 CR5 与前五名市占率；
3. 公司过去五年及未来五年的发展逻辑；
4. 供应商、客户结构与周期依赖度；
5. 研发投入占比，以及扣非净利润增速与营收增速的对比。

报告严格要求模型标注来源编号。数据没有可靠依据时，应标为未知/待核实，而不是编造。自动检索结果和模型归纳是研究起点，不代替年报、公告及行业报告原文核验。

## 快速开始

需要 Python 3.10+，不依赖额外 Python 包。完整检索需要 Tavily 搜索 API 和 OpenAI 兼容的聊天补全 API：

```bash
export TAVILY_API_KEY="..."
export LLM_API_KEY="..."
# 可选：切换到其他兼容服务
export LLM_BASE_URL="https://api.openai.com/v1"
export LLM_MODEL="gpt-4o-mini"
python research_workflow.py --company "示例公司" --industry "示例行业" --output report.md
```

脚本按五类问题构造中英文搜索词，检索公开网页，按主题整理来源，再调用模型生成中文报告。默认每条搜索词最多取 5 条结果，可通过 `--max-results` 调整（1–10）。API 密钥只从环境变量读取，不要提交到仓库。

不配置 API 时，可先创建问题模板：

```bash
python research_workflow.py --company "示例公司" --industry "示例行业" --template-only --output report.md
```

## 财务数据

可通过 CSV 提供逐年数据，程序本地计算营收同比、扣非净利润同比和研发费用率。单位必须一致；缺少研发费用时留空即可。

```csv
 year,revenue,adjusted_net_profit,rd_expense
 2021,1000,80,40
 2022,1200,95,52
```

使用时去掉示例中字段名前的空格，避免表头不匹配：

```bash
python research_workflow.py --company "示例公司" --industry "示例行业" --financials financials.csv --output report.md
```

字段定义：`year` 年度，`revenue` 营业收入，`adjusted_net_profit` 扣非归母净利润，`rd_expense` 研发费用。财务数据要从同一合并报表口径的年报/公告中整理，并保留原始来源。负数或零基数不按普通同比百分比解读，脚本会提示不可直接比较。

## 研究质量控制

- 市场规模、增速、CR5 和市占率须注明年份、地域、定义、计量口径与来源；不同市场口径不可直接拼接。
- 客户/供应商集中度通常是公司年报披露；不可把未披露的名单或占比当作事实。
- 区分披露事实、第三方估算和分析判断；预测写清假设及风险。
- 搜索摘要不是原始文件。关键数据应打开原始年报、公告或可信行业报告复核，并留存访问日期。
- 可将财务 CSV 与相应年报页码/公告链接一起归档，方便复核和更新。

## 文件

- `research_workflow.py`：命令行研究生成器、检索调用和本地财务增速计算。
- `tests/test_research_workflow.py`：财务计算及模板的基础测试。
