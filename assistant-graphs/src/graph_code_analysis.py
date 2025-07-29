import json
from typing import Annotated, cast
from typing_extensions import TypedDict

from langchain_anthropic import ChatAnthropic

from langchain_core.runnables import (
    RunnableConfig,
)
from langchain_core.runnables import ConfigurableField
from langchain_core.language_models import BaseChatModel

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages


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


class GraphState(TypedDict):
    messages: Annotated[list, add_messages]
    llm: str


graph_builder = StateGraph(GraphState)

from tools_code_analysis import (
    tools,
)

from langchain_core.prompts import (
    SystemMessagePromptTemplate,
)

from langchain_core.messages import AIMessage
from langgraph.utils.runnable import RunnableCallable

from prompt_code_analysis import system_prompt

system_template = SystemMessagePromptTemplate.from_template(system_prompt)


def call_model_swap(state: GraphState, config: RunnableConfig) -> GraphState:
    model_key = state.get("llm", "anthropic_claude_4_sonnet")
    llm = _getModel(model_key)
    llm_configed = cast(BaseChatModel, llm).bind_tools(tools)
    system_message = system_template.format_messages()
    response = cast(
        AIMessage, llm_configed.invoke(system_message + state["messages"], config)
    )

    return {"messages": [response]}


async def acall_model_swap(state: GraphState, config: RunnableConfig) -> GraphState:
    model_key = state.get("llm", "anthropic_claude_4_sonnet")
    llm = _getModel(model_key)
    llm_configed = cast(BaseChatModel, llm).bind_tools(tools)
    system_message = system_template.format_messages()
    response = cast(
        AIMessage,
        await llm_configed.ainvoke(system_message + state["messages"], config),
    )

    return {"messages": [response]}


from langgraph.prebuilt import ToolNode, tools_condition

tool_node = ToolNode(tools=tools, name="node_tools_code_analysis")

from langgraph.utils.runnable import RunnableCallable

node_llm = RunnableCallable(
    call_model_swap, acall_model_swap, name="node_llm_code_analysis"
)

graph_builder.add_node(node_llm.get_name(), node_llm)
graph_builder.add_node(tool_node.get_name(), tool_node)

graph_builder.add_conditional_edges(
    node_llm.get_name(),
    tools_condition,
    {"tools": tool_node.get_name(), END: END},
)

graph_builder.add_edge(tool_node.get_name(), node_llm.get_name())
graph_builder.add_edge(START, node_llm.get_name())

graph = graph_builder.compile()
graph.name = "graph_code_analysis"
