from operator import add
from dotenv import load_dotenv
from typing import TypedDict, Annotated
from langchain_core.messages import AnyMessage
from langgraph.graph import START, END
from langgraph.graph import StateGraph
from langchain_core.messages import HumanMessage,AIMessage
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

#这里的 add 操作符意味着：
#新返回的 messages 会追加到现有的消息列表中
#必须返回标准的消息对象（BaseMessage 对象，如AIMessage、HumanMessage），不能是纯字符串
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
    
    # 如果已有type属性且不是第一次执行，使用大模型判断是否完成
    if "type" in state and state["type"] in ["travel", "joke", "couplet", "other"]:
        # 使用大模型判断任务是否完成
        completion_prompt = f"""
        请判断当前对话是否已经完成用户的任务需求。
        
        用户原始请求：
        {state['messages'][0].content if state['messages'] else '无'}
        
        当前对话历史：
        {[msg.content for msg in state['messages']]}
        
        当前任务类型：{state['type']}
        
        请仔细检查用户原始请求中是否包含多个任务要求，然后回答"完成"或"未完成"：
        - 如果用户的所有任务要求都已经满足，回答"完成"
        - 如果用户还有未完成的任务要求，回答"未完成"
        
        特别注意：用户可能在一个请求中要求多个任务。
        """
        
        completion_messages = [
            {"role": "system", "content": completion_prompt}
        ]
        
        completion_response = llm.invoke(completion_messages)
        completion_result = completion_response.content.strip()
        
        writer({"supervisor_step": f"任务完成状态判断: {completion_result}"})
        
        if "完成" in completion_result:
            writer({"supervisor_step": f"任务已完成，流程结束"})
            return {"type": END}
        else:
            # 判断下一步执行哪个节点
            next_step_prompt = f"""
            根据用户原始请求和当前进展，决定下一步应该执行哪个处理节点。
            
            用户原始请求：
            {state['messages'][0].content if state['messages'] else '无'}
            
            当前对话历史：
            {[msg.content for msg in state['messages']]}
            
            当前已完成的任务：{state['type']}
            可用节点：travel, joke, couplet, other
            
            请分析用户还有哪些任务没有完成，选择最合适的下一个节点。
            只返回节点名称（travel/joke/couplet/other）
            """
            
            next_step_messages = [
                {"role": "system", "content": next_step_prompt}
            ]
            
            next_step_response = llm.invoke(next_step_messages)
            next_node = next_step_response.content.strip().lower()
            
            #打印信息调试
            writer({"supervisor_step": f"大模型建议的下一个节点: {next_node}"})
            # 确保返回的节点在预定义节点中
            if next_node not in nodes:
                next_node = state["type"]  # 默认继续当前任务
            
            writer({"supervisor_step": f"继续执行: {next_node}"})
            return {"type": next_node}
    
    # 首次执行，进行任务分类
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
    return {"messages": [AIMessage(content=travel_response)], "type": "travel"}

def joke_node(state: State):
    print(">>> joke_node")
    writer = get_stream_writer()
    writer({"node": "joke_node"})
    
    # 更详细的提示词
    system_prompt = """你是一个专业的喜剧编剧和笑话生成器。请根据用户的要求创作一个精彩的笑话。
    
    创作指南：
    1. 结构完整：有铺垫、转折和笑点
    2. 语言生动：使用形象的语言和适当的夸张
    3. 贴近生活：从日常生活中寻找灵感
    4. 积极向上：避免低俗、歧视性内容
    5. 适度创新：可以结合时事热点或流行文化
    
    如果用户指定了笑话类型（如冷笑话、相声段子、谐音梗等），请按照要求创作。
    如果用户提到了具体的喜剧演员风格（如郭德纲、周立波等），请模仿相应的风格。"""
    
    # 获取用户输入
    #state["messages"] 存储了整个对话历史
    #state["messages"][-1] 获取最后一条消息（通常是用户的输入）
    #通过 .content 属性提取消息的文本内容
    
    if state["messages"] and hasattr(state["messages"][-1], 'content'):
        user_input = state["messages"][-1].content
        user_prompt = f"用户请求：{user_input}\n\n请根据以上要求创作一个合适的笑话。"
    else:
        user_prompt = "请创作一个有趣的笑话，主题不限。"
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    writer({"joke_generation": "大模型正在创作笑话..."})
    
    try:
        response = llm.invoke(messages)
        joke_content = response.content.strip()
        
        # 确保笑话内容不为空
        if not joke_content:
            joke_content = "为什么程序员总是分不清万圣节和圣诞节？因为 Oct 31 == Dec 25！"
            
        writer({"generated_joke": joke_content})
        
    except Exception as e:
        writer({"error": f"笑话生成失败: {e}"})
        # 备用笑话
        joke_content = "听说有个程序员去钓鱼，钓了一天都没钓到。后来他发现，原来他一直在调的是 debug。。。"
    
    #拿到大模型思考结果后，更新state状态
    #必须要HumanMessage方式返回，不可以直接返回字符串
    #langchain中有不同消息类型：
    return {"messages": [AIMessage(content=joke_content)], "type": "joke"}

def couplet_node(state: State):
    print(">>> couplet_node")
    writer = get_stream_writer()
    writer({"node": "couplet_node"})
    # 实际应该调用对联生成API
    
    system_prompt="""
    你是一个专业的对联生成器。请根据用户的要求创作一个精彩的对联
    """
    if state["messages"] and hasattr(state["messages"][-1], 'content'):
        user_input = state["messages"][-1].content
        user_prompt = f"用户请求：{user_input}\n\n请根据以上要求创作一个精彩的对联。"
    else:
        user_prompt = "请创作一个有趣的对联，主题不限。"
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    writer({"joke_generation": "大模型正在创作对联..."})
    
    try:
        response = llm.invoke(messages)
        couplet_content = response.content.strip()
        
        # 确保对联内容不为空
        if not couplet_content:
            couplet_content = "默认对联"
            
        writer({"generated_joke": couplet_content})
        
    except Exception as e:
        writer({"error": f"对联生成失败: {e}"})
        # 备用笑话
        couplet_content = "准备好的对联"
    
    #拿到大模型思考结果后，更新state状态
    #必须要HumanMessage方式返回，不可以直接返回字符串
    #langchain中有不同消息类型：
    return {"messages": [AIMessage(content=couplet_content)], "type": "couplet"}


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
        "messages": [HumanMessage(content="今天天气如何")]
    }
    
    print("开始执行多Agent流程...")
    # try:
    #     for chunk in graph.stream(
    #         input_data,
    #         config=config,
    #         stream_mode="values"
    #     ):
    #         node_name = list(chunk.keys())[0] if chunk else "unknown"
    #         print(f"=== 节点 {node_name} 输出 ===")
    #         print(chunk)
    #         print("=" * 50)
    # except Exception as e:
    #     print(f"执行出错: {e}")
    #     import traceback
    #     traceback.print_exc()
    res = graph.invoke({"message":["说个笑话"]}
                       ,config
                       ,stream_mode="values")
    print(res["messages"][-1].content)
    