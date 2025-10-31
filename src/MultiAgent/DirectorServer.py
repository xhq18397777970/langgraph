from Director import graph
import random
from langchain_core.messages import HumanMessage,AIMessage
config = {
    "configurable": 
        {
            "thread_id": random.randint(1,10000)
        }
    }
input_data = {
        "messages": [HumanMessage(content="今天天气如何")]
    }
    
print("开始执行多Agent流程...")
    
    # 方式1：使用 invoke
res = graph.invoke(
        input_data,
        config=config,
        stream_mode="values"
    )
print("最终结果:", res["messages"][-1].content)