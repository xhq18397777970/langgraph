
import os
from dotenv import load_dotenv

from config.model_config import get_deepseek_model


from langgraph.graph import StateGraph,MessagesState ,START
from langgraph.checkpoint.memory import InMemorySaver


# 加载环境变量
load_dotenv()
# 配置 DeepSeek 模型
model = get_deepseek_model()

#node节点，功能：使用大语言模型对话
def call_model(state:MessagesState):
    response= model.invoke(state["messages"])
    return {"messages":response}



builder = StateGraph(MessagesState)
builder.add_node(call_model)
builder.add_edge(START,"call_model")

checkpointer=InMemorySaver()
graph = builder.compile(checkpointer=checkpointer)

config={
    "configurable":{
        "thread_id":"1"
    }
}
#以流式方式输出结果（一个个token方式）
for chunk in graph.stream(
    {"messages": [{"role": "user", "content": "请你非常简短的回答我的问题，湖南的省会在哪}],"}]},
    stream_mode="values",
    config=config,
):
    chunk["messages"][-1].pretty_print()

for chunk in graph.stream(
    {"messages": [{"role": "user", "content": "再说说广东"}]},
    stream_mode="values",
    config=config,
):
    chunk["messages"][-1].pretty_print()
        