# Quality Agent Test Automation
"""
需求输入
→ RAG 知识库检索
→ 测试用例生成
→ 测试覆盖率分析
→ 接口测试执行
→ 缺陷分析
→ 测试报告生成
"""
## 项目背景
##  Project Background
传统测试流程中，测试人员需要人工阅读需求文档、编写测试用例、执行接口测试、分析失败日志并整理
测试报告。该流程存在重复性高、依赖人工经验、问题定位效率低等问题。
本项目面向网约车订单业务场景，构建一个测试智能化 AI Agent 系统。系统能够根据业务需求自动完成
知识检索、测试用例生成、测试覆盖率分析、测试用例自动补充、真实接口测试执行、缺陷分析和测试报
告生成，提升测试流程自动化和质量效能。

## 核心功能
##  Core Workflow
1. 根据业务需求自动生成测试用例
2. 基于测试规范、接口文档、历史 Bug 进行知识检索
3. 调用接口测试工具执行自动化测试
4. 根据错误日志分析失败原因
5. 自动生成 Markdown 测试报告
6. 通过 FastAPI 提供 Agent 服务接口
7. 使用 Promptfoo 进行 Agent 输出评测

## Project Structure
quality-agent-test-automation/
├── app/
│   ├── __init__.py
│   ├── api_server.py
│   ├── agent_graph.py
│   ├── mock_business_api.py
│   ├── rag_retriever.py
│   ├── data/
│   │   ├── requirements.md
│   │   ├── api_spec.md
│   │   ├── bug_history.md
│   │   └── test_standard.md
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── case_generator.py
│   │   ├── case_generator_rule.py
│   │   ├── coverage_tool.py
│   │   ├── case_enhancer.py
│   │   ├── api_test_tool.py
│   │   ├── log_analysis_tool.py
│   │   ├── report_tool.py
│   │   ├── trace_tool.py
│   │   └── metrics_tool.py
│   ├── eval/
│   │   ├── __init__.py
│   │   ├── eval_cases.json
│   │   └── evaluate_agent.py
│   └── outputs/
│       └── .gitkeep
├── docs/
│   ├── architecture.md
│   ├── interview_notes.md
│   └── demo_examples.md
├── .env.example
├── .gitignore
├── requirements.txt
├── README.md
└── LICENSE

## 技术栈
## Tech stack
Python、FastAPI、LangGraph、RAG、Promptfoo

## 项目流程
## Project flow
用户输入需求
→ RAG 知识检索
→ 测试用例生成
→ 接口测试执行
→ 缺陷分析
→ 测试报告生成

## 运行方式
## Operating mode
安装依赖：
Install dependencies
```bash
pip install -r requirements.txt