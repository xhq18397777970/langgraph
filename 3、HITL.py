

import os
from dotenv import load_dotenv

from config.model_config import get_deepseek_model

from langchain_core.messages import AnyMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import StateGraph
from langgraph.constants import START,END

from typing import Literal ,TypedDict, Annotated
from langgraph.types import interrupt ,Command
from langgraph.graph import add_messages


# 加载环境变量
load_dotenv()
# 配置 DeepSeek 模型
llm = get_deepseek_model()

class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]

def human_approval(state: State) -> Command[Literal["call_llm",END]]:
    is_approval = interrupt(
        {
            "question":"是否同意问大模型？"
        }
    )
    if is_approval:
        return Command(goto="call_llm")
    else:
        return Command(goto=END)


def call_llm(state:State):
    response= llm.invoke(state["messages"])
    return {"messages":response}


builder = StateGraph(State)
builder.add_node("human_approval",human_approval)
builder.add_node("call_llm",call_llm)
builder.add_edge(START,"human_approval")

checkpointer=InMemorySaver()

graph = builder.compile(checkpointer=checkpointer)



from langchain_core.messages import HumanMessage
thread_config={"configurable":{"thread_id":"1"}}
graph.invoke({"messages":[HumanMessage("湖南的省会在哪")]},config=thread_config)


final_result = graph.invoke(Command(resume=True),config=thread_config)
print(final_result)