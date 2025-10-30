# pip install -qU "langchain[anthropic]" python-dotenv langchain-openai
import os
from dotenv import load_dotenv

from langgraph.prebuilt  import create_react_agent
from langchain_openai import ChatOpenAI
from tools.domain import *
from config.model_config import get_deepseek_model
from langchain_mcp_adapters.client import MultiServerMCPClient

# 加载环境变量
load_dotenv()

# 配置 DeepSeek 模型
model = get_deepseek_model()

async def main():
    client = MultiServerMCPClient(
        {
            "domain-info-service": {
                "url": "http://127.0.0.1:10025/sse",
                "transport": "sse",
            }
        }
    )

    tools = await client.get_tools()

    agent = create_react_agent(
        model=model,
        # tools=[query_domains_info,check_domain_status],
        tools=tools,
        prompt="你是一个问答机器人，会使用工具",
        # response_format=DomainCheckResponse,
    )


    for chunk in agent.stream(
        {"messages": [{"role": "user", "content": "查一下jd.com的所有者"}]},
        # stream_mode="messages"
    ):
        print(chunk)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())