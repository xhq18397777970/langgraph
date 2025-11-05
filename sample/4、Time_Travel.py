
#时间回溯，如果执行后得到不符合预期的结果，可以回溯到某个步骤、
# 每个node执行完毕都会返回一个checkpoint_id，当要回溯时候，即指定该thread_id（哪个窗口）、checkpoint_id（哪个步骤）、回溯
import os
from dotenv import load_dotenv

from config.model_config import get_deepseek_model

from langchain_core.messages import AnyMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import StateGraph
from langgraph.constants import START,END

from typing import Literal, TypedDict, Annotated
from langgraph.types import interrupt ,Command
from langgraph.graph import add_messages


# 加载环境变量
load_dotenv()
# 配置 DeepSeek 模型
llm = get_deepseek_model()


class State(TypedDict):
    author: str
    joke: str

def author_node(state:State):
    prompt="帮我推荐一位受人欢迎的作家，只需要给出作家的名字即可"
    author = llm.invoke(prompt)
    
    return {"author":author}
def joke_node(state:State):
    prompt= f"用作家{state['author']}的风格，写一个100字以内的笑话"
    joke = llm.invoke(prompt)
    return {"joke":joke}



builder = StateGraph(State)
builder.add_node("author_node",author_node)
builder.add_node("joke_node",joke_node)

builder.add_edge(START,"author_node")
builder.add_edge("author_node","joke_node")
builder.add_edge("joke_node",END)

checkpointer=InMemorySaver()

graph = builder.compile(checkpointer=checkpointer)

import uuid

config={"configurable":{"thread_id":uuid.uuid4()}}

state= graph.invoke({},config)
print(state["author"].content)
print()
print(state["joke"].content)

#查看所有checkpoint检查点，即在每个node中执行时，state的版本号（checkpoint_id）
states= list(graph.get_state_history(config))
for state in states:
    print(state.next)
    print(state.config["configurable"]["checkpoint_id"])
    print()
    
    
#如果说llm给的作家你不满意，你可以设置他的checkpointe_id
selected_state = states[1]
print(selected_state.next)
print(selected_state.values)

#进行重演
new_config = graph.update_state(selected_state.config,values={"author":"鲁迅"})
print(new_config)

#重新，在该位置（thread_id、checkpoint_id位置，重新更新state的状态（即其中的author变量，我指定为鲁迅
result = graph.invoke(None,new_config)
print(result)