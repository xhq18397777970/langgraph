import os
from langchain_openai import ChatOpenAI


def get_deepseek_model(temperature=0.2):
    """
    配置并返回 DeepSeek 模型实例
    
    Returns:
        ChatOpenAI: 配置好的 DeepSeek 模型实例
    """
    model = ChatOpenAI(
        model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        temperature=temperature,
    )
    return model


def get_glm_model(temperature=0.4):
    """
    配置并返回 GLM-4.6 模型实例
    
    Returns:
        ChatOpenAI: 配置好的 GLM-4.6 模型实例
    """
    model = ChatOpenAI(
        model="glm-4.6",
        api_key="5664839384444eb5a1bfdb6c9f7269b3.iBSzYXqjTBqTqZzm",
        base_url="https://open.bigmodel.cn/api/coding/paas/v4",
        temperature=temperature,
    )
    return model
