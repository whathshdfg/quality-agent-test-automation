from app.agent_graph import run_agent


if __name__ == "__main__":
    requirement = """
    用户主动取消未接单订单后，订单状态变为 cancelled。
    如果订单创建后 3 分钟内没有司机接单，系统自动取消订单。
    如果司机已接单，用户取消订单时必须记录取消原因。
    """

    report = run_agent(requirement)

    with open("app/outputs/test_report.md", "w", encoding="utf-8") as f:
        f.write(report)

    print("测试报告已生成：app/outputs/test_report.md")
