from typing import Annotated, Literal, cast
from typing_extensions import TypedDict

from langchain_anthropic import ChatAnthropic

from langchain_core.runnables import ConfigurableField
from langchain_core.runnables import (
    RunnableConfig,
)

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.prompts import (
    SystemMessagePromptTemplate,
)
from langchain_core.messages import ToolMessage
from langchain_core.language_models import BaseChatModel

from langchain_core.messages import AIMessage
from langgraph.utils.runnable import RunnableCallable
from langgraph.types import Command
from langgraph.prebuilt import ToolNode, tools_condition

from tools_agent_router import tools as tools_router, get_next_node


from graph_search import graph as search_webpage_graph

# from graph_programmer import graph as programmer_graph
from graph_code_analysis import graph as code_analysis_graph
from graph_image import graph as image_graph


llm=ChatAnthropic(
            model="claude-sonnet-4-20250514",
            # max_tokens=,
            temperature=0.9,
            # anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", "not_provided"),
            streaming=True,
            verbose=True,
        )

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


from prompt_chatbot import system_prompt

system_template = SystemMessagePromptTemplate.from_template(system_prompt)


def call_model(state: State, config: RunnableConfig):
    model_key = state.get("llm", "anthropic_claude_3_7_sonnet")
    llm = _getModel(model_key)
    llm_configed = cast(BaseChatModel, llm).bind_tools(tools_router)
    system_message = system_template.format_messages(
        time_zone=state["time_zone"],
    )
    response = cast(
        AIMessage, llm_configed.invoke(system_message + state["messages"], config)
    )
    return {
        "messages": [response],
        "llm": state["llm"],
        "time_zone": state["time_zone"],
    }


async def acall_model(state: State, config: RunnableConfig):
    model_key = state.get("llm", "anthropic_claude_3_7_sonnet")
    llm = _getModel(model_key)
    llm_configed = cast(BaseChatModel, llm).bind_tools(tools_router)
    system_message = system_template.format_messages(
        time_zone=state["time_zone"],
    )
    response = cast(
        AIMessage,
        await llm_configed.ainvoke(system_message + state["messages"], config),
    )
    return {
        "messages": [response],
        "llm": state["llm"],
        "time_zone": state["time_zone"],
    }


router_tools = ToolNode(tools=tools_router, name="router_tools")


def node_router(state: State):
    last_message = state["messages"][-1]
    if isinstance(last_message, ToolMessage):
        next_node = get_next_node(last_message.name)
        if next_node:
            return Command(
                goto=next_node,
                update={
                    "messages": state["messages"],
                    "time_zone": state["time_zone"],
                    "llm": state["llm"],
                },
            )
        else:
            return Command(
                goto=node_llm.get_name(),
                update={
                    "messages": state["messages"],
                    "time_zone": state["time_zone"],
                    "llm": state["llm"],
                },
            )
    else:
        return Command(
            goto=node_llm.get_name(),
            update={
                "messages": state["messages"],
                "time_zone": state["time_zone"],
                "llm": state["llm"],
            },
        )


node_llm = RunnableCallable(call_model, acall_model, name="node_llm_chatbot")
graph_builder.add_node(node_llm.get_name(), node_llm)
graph_builder.add_node(node_router)

graph_builder.add_node(search_webpage_graph.get_name(), search_webpage_graph)
# graph_builder.add_node(programmer_graph)
graph_builder.add_node(code_analysis_graph)
graph_builder.add_node(image_graph)

graph_builder.add_node(router_tools.get_name(), router_tools)
graph_builder.add_edge(START, node_llm.get_name())
graph_builder.add_conditional_edges(
    node_llm.get_name(),
    tools_condition,
    {"tools": router_tools.get_name(), END: END},
)
graph_builder.add_edge(router_tools.get_name(), node_router.__name__)
graph_builder.add_edge(search_webpage_graph.get_name(), node_llm.get_name())
# graph_builder.add_edge(programmer_graph.get_name(), node_llm.get_name())
graph_builder.add_edge(code_analysis_graph.get_name(), node_llm.get_name())
graph_builder.add_edge(image_graph.get_name(), node_llm.get_name())
graph = graph_builder.compile()
graph.name = "holynull_assistant"
