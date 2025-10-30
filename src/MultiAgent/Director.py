from operator import add
from dotenv import load_dotenv
from typing import TypedDict, Annotated
from langchain_core.messages import AnyMessage
from langgraph.graph import START, END
from langgraph.graph import StateGraph
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.model_config import get_deepseek_model

# 定义日志函数
def get_stream_writer():
    """简单的流式输出写入器"""
    def writer(data):
        if isinstance(data, dict):
            print(f"📊 {data}")
        else:
            print(f"🔔 {data}")
    return writer

load_dotenv()

# 修正：nodes 应该与模型返回的类型一致
nodes = ["travel", "joke", "couplet", "other"]
llm = get_deepseek_model()

class State(TypedDict):
    messages: Annotated[list[AnyMessage], add]
    type: str

def supervisor_node(state: State):
    print(">>> supervisor_node")
    writer = get_stream_writer()
    writer({"node": "supervisor_node"})
    
    prompt = """
        你是一个专业的客服助手，负责对用户的问题进行分类，并将任务分给其他Agent执行。
        如果用户的问题是和旅游路线规划相关的，那就返回travel。
        如果用户的问题是希望讲一个笑话，那就返回joke。
        如果用户的问题是希望对一个对联，那就返回couplet。
        如果是其他的问题，返回other。
        注意：只返回上述四个单词中的一个，不要返回任何其他的内容。
        """
    
    # 修正：正确处理消息内容
    if state["messages"] and hasattr(state["messages"][-1], 'content'):
        user_content = state["messages"][-1].content
    else:
        user_content = str(state["messages"])
    
    print(f"用户问题: {user_content}")
    
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": user_content}
    ]
    
    # 如果已有type属性且不是第一次执行，表示问题已经处理完成
    if "type" in state and state["type"] in ["travel", "joke", "couplet", "other"]:
        writer({"supervisor_step": f"已获得 {state['type']} 智能体处理结果，流程结束"})
        return {"type": END}
    
    response = llm.invoke(messages)
    typeRes = response.content.strip().lower()
    writer({"supervisor_step": f"问题分类结果: {typeRes}"})
    
    print(f"模型返回类型: '{typeRes}'")
    print(f"预定义节点: {nodes}")
    
    # 修正：检查类型是否在预定义节点中
    if typeRes in nodes:
        print(f"✅ 类型 '{typeRes}' 在预定义节点中")
        return {"type": typeRes}
    else:
        print(f"⚠️  类型 '{typeRes}' 不在预定义节点中，使用 'other'")
        return {"type": "other"}

def travel_node(state: State):
    print(">>> travel_node")
    writer = get_stream_writer()
    writer({"node": "travel_node"})
    # 实际应该调用旅游相关的API或处理逻辑
    travel_response = "为您推荐湖南旅游路线：长沙->张家界->凤凰古城，全程5天4晚。"
    return {"messages": [HumanMessage(content=travel_response)], "type": "travel"}

def joke_node(state: State):
    print(">>> joke_node")
    writer = get_stream_writer()
    writer({"node": "joke_node"})
    # 实际应该调用笑话生成API或从数据库获取笑话
    joke_content = "郭德纲说过：'我小学十年，中学十二年，我被评为全校最熟悉的面孔，新老师来了都跟我打听学校内幕。'"
    return {"messages": [HumanMessage(content=joke_content)], "type": "joke"}

def couplet_node(state: State):
    print(">>> couplet_node")
    writer = get_stream_writer()
    writer({"node": "couplet_node"})
    # 实际应该调用对联生成API
    couplet_response = "上联：春风得意马蹄疾，下联：旭日扬辉光照强"
    return {"messages": [HumanMessage(content=couplet_response)], "type": "couplet"}

def other_node(state: State):
    print(">>> other_node")
    writer = get_stream_writer()
    writer({"node": "other_node"})
    other_response = "我主要擅长旅游规划、讲笑话和对对联，您的问题暂时无法回答。"
    return {"messages": [HumanMessage(content=other_response)], "type": "other"}

def routing_func(state: State):
    print(f"路由函数接收到类型: {state['type']}")
    
    if state["type"] == "travel":
        return "travel_node"
    elif state["type"] == "joke":
        return "joke_node"
    elif state["type"] == "couplet":
        return "couplet_node"
    elif state["type"] == "other":
        return "other_node"
    elif state["type"] == END:
        return END
    else:
        print(f"❌ 未知类型: {state['type']}，路由到 other_node")
        return "other_node"

# 构建图
builder = StateGraph(State)
builder.add_node("supervisor_node", supervisor_node)
builder.add_node("travel_node", travel_node)
builder.add_node("joke_node", joke_node)
builder.add_node("couplet_node", couplet_node)
builder.add_node("other_node", other_node)

# 设置流程
builder.add_edge(START, "supervisor_node")

# 条件路由，langgraph执行引擎，如果返回值为joke_node则下一个执行任务的是joke_node
builder.add_conditional_edges(
    "supervisor_node",
    routing_func,
    {
        "travel_node": "travel_node",
        "joke_node": "joke_node", 
        "couplet_node": "couplet_node",
        "other_node": "other_node",
        END: END
    }
)

# 各个处理节点完成后回到 supervisor_node 进行结果确认
builder.add_edge("travel_node", "supervisor_node")
builder.add_edge("joke_node", "supervisor_node") 
builder.add_edge("couplet_node", "supervisor_node")
builder.add_edge("other_node", "supervisor_node")

checkpointer = MemorySaver()
graph = builder.compile(checkpointer=checkpointer)

if __name__ == "__main__":
    config = {"configurable": {"thread_id": "1"}}
    
    # 修正：输入应该是 HumanMessage 对象列表
    input_data = {
        "messages": [HumanMessage(content="给我讲一个郭德纲的笑话")]
    }
    
    print("开始执行多Agent流程...")
    try:
        for chunk in graph.stream(
            input_data,
            config=config,
            stream_mode="values"
        ):
            node_name = list(chunk.keys())[0] if chunk else "unknown"
            print(f"=== 节点 {node_name} 输出 ===")
            print(chunk)
            print("=" * 50)
    except Exception as e:
        print(f"执行出错: {e}")
        import traceback
        traceback.print_exc()