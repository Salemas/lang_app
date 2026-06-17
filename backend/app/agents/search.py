from langchain_openai import ChatOpenAI
from langchain_tavily import TavilySearch
from langgraph.prebuilt import create_react_agent

from app.config import get_model


def get_search_subgraph():
    model = ChatOpenAI(model=get_model())
    tools = [TavilySearch(max_results=3)]
    return create_react_agent(model, tools)
