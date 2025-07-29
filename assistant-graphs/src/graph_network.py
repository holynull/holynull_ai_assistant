import os
from typing import Annotated, Optional, cast
from typing_extensions import TypedDict
from langchain_anthropic import ChatAnthropic
from langchain_core.runnables import (
    RunnableConfig,
)
from langchain_core.language_models import BaseChatModel
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.prompts import (
    SystemMessagePromptTemplate,
)
from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    BaseMessage,
    SystemMessage,
    ToolMessage,
)
from langgraph.utils.runnable import RunnableCallable
from langgraph.types import Command
from tools_agent_router import tools as tools_router
from agent_config import ROUTE_MAPPING
from loggers import logger

from prompt_chatbot import system_prompt

# import subgraph
from graph_search import graph as search_webpage_graph
from graph_code_analysis import graph as code_analysis_graph
from graph_image import graph as image_graph

GRAPH_NAME = "graph_network"

subgraphs = [
    search_webpage_graph,
    code_analysis_graph,
    image_graph,
]


def _getModel(key: str):
    if key == "anthropic_claude_4_sonnet":
        return ChatAnthropic(
            model="claude-sonnet-4-20250514",
            # max_tokens=,
            temperature=0.9,
            # anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", "not_provided"),
            streaming=True,
            verbose=True,
        )
    elif key == "anthropic_claude_4_opus":
        return ChatAnthropic(
            model="claude-opus-4-20250514",
            # max_tokens=,
            temperature=0.9,
            # anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", "not_provided"),
            streaming=True,
            verbose=True,
        )
    elif key == "anthropic_claude_3_7_sonnet":
        return ChatAnthropic(
            model="claude-3-7-sonnet-20250219",
            # max_tokens=,
            temperature=0.9,
            # anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", "not_provided"),
            streaming=True,
            verbose=True,
        )
    else:
        raise Exception("Unsupported model key")


class State(TypedDict):
    # Messages have the type "list". The `add_messages` function
    # in the annotation defines how this state key should be updated
    # (in this case, it appends messages to the list, rather than overwriting them)
    messages: Annotated[list, add_messages]
    time_zone: str
    llm: str


graph_builder = StateGraph(State)

system_template = SystemMessagePromptTemplate.from_template(system_prompt)


async def acall_model(state: State, config: RunnableConfig):
    model_key = state.get("llm", "anthropic_claude_3_7_sonnet")
    llm = _getModel(model_key)
    last_message = state["messages"][-1]
    if isinstance(last_message, ToolMessage) and last_message.name in ROUTE_MAPPING:
        next_node = ROUTE_MAPPING[last_message.name]
        logger.info(f"Node: {GRAPH_NAME}, goto {next_node}")
        return Command(goto=next_node, update=state)
    elif isinstance(last_message, AIMessage):
        return Command(goto=END, update=state)

    llm_configed = cast(BaseChatModel, llm).bind_tools(tools_router)
    system_message = system_template.format_messages(
        wallet_is_connected=state["wallet_is_connected"],
        chain_id=state["chain_id"],
        wallet_address=state["wallet_address"],
        time_zone=state["time_zone"],
    )
    response = await llm_configed.ainvoke(system_message + state["messages"])
    ai_message = cast(AIMessage, response)
    next_node = END
    if len(ai_message.tool_calls) > 0:
        tool_call = ai_message.tool_calls[0]
        tool_name = tool_call.get("name")
        next_node = ROUTE_MAPPING[tool_name]
    else:
        state["messages"] += [ai_message]
    logger.info(f"Node: {GRAPH_NAME}, goto {next_node}, after llm handling.")
    return Command(
        goto=next_node,
        update=state,
    )


def call_model(state: State, config: RunnableConfig):
    raise NotImplementedError()


node_router = RunnableCallable(call_model, acall_model, name="node_router")
graph_builder.add_node(node_router)


for graph in subgraphs:
    graph_builder.add_node(graph, graph.get_name())

# add edge
graph_builder.add_edge(START, node_router.get_name())
for graph in subgraphs:
    graph_builder.add_edge(graph.get_name(), node_router.get_name())

graph = graph_builder.compile()
graph.name = GRAPH_NAME
