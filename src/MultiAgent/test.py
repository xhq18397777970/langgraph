    # 从响应中提取内容
    try:
        # 模型可能会在JSON前后加上```json ```标记，我们尝试清理它
        content = response.content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.endswith("```"):
            content = content[:-3]
        
        # 解析JSON
        response_dict = json.loads(content)
        
        # 确保字段存在
        goto = response_dict.get("next")
        reason = response_dict.get("reason", "未提供理由")
 
        if goto not in ["domain", "joke", "deeplog"]:
            raise ValueError(f"无效的路由决策: {goto}")
 
        print(f"--- 工作流转移: Supervisor → {goto.upper()} ---")
        
        return Command(
            update={
                "messages": [
                    HumanMessage(content=reason, name="supervisor")
                ]
            },
            goto=goto,  
        )
    except (json.JSONDecodeError, AttributeError, ValueError) as e:
        # 如果解析失败，打印错误信息并抛出异常
        print("--- 模型输出解析失败 ---")
        print(f"模型原始回复: {response.content}")
        print(f"错误信息: {e}")
        raise ValueError("模型未能返回有效的JSON格式决策。") from e