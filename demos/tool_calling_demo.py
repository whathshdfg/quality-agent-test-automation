from app.tool_agent.agent_loop import run_tool_agent


if __name__ == "__main__":
    user_question = input("请输入问题：")
    print(run_tool_agent(user_question))
