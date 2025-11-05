# pip install -qU "langchain[anthropic]" python-dotenv langchain-openai
import os
from dotenv import load_dotenv
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from tools.domain import *
from config.model_config import get_deepseek_model
# 加载环境变量
load_dotenv()

checkpointer = InMemorySaver()

    
def get_weather(city: str) -> str:
    """Get weather for a given city."""
    return f"It's always sunny in {city}!"

# 配置 DeepSeek 模型
model = get_deepseek_model()

agent = create_react_agent(
    model=model,
    tools=[query_domains_info,check_domain_status],
    prompt="你是一个运维专家，你对域名相关的任务非常熟悉",
    # response_format=DomainCheckResponse,
    checkpointer=checkpointer
)

config={
    "configurable":{
        "thread_id":"1"
    }
}

if __name__ == "__main__":
    # 普通调用方式（注释掉）
    cs_result = agent.invoke(
        {"messages": [{"role": "user", "content": "检查一下jd.com的域名状态，再看看该域名的负责人信息和项目信息"}]},
        config
    )
    print(cs_result)
    
    bj_result = agent.invoke(
        {"messages": [{"role": "user", "content": "还有这个graycluster-bind-check.jd.local"}]},
        config
    )
    print(bj_result)

