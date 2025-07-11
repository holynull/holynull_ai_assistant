from hashlib import sha1
import json
import logging
from typing import Annotated, cast
from typing_extensions import TypedDict

from langchain_anthropic import ChatAnthropic

from langchain_core.runnables import (
    RunnableConfig,
)

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.types import Command
import copy

_llm = ChatAnthropic(
    model="claude-sonnet-4-20250514",
    max_tokens=4096,
    temperature=0.9,
    # anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", "not_provided"),
    streaming=True,
    stream_usage=True,
    verbose=True,
)


class GraphState(TypedDict):
    messages: Annotated[list, add_messages]
    time_zone: str


graph_builder = StateGraph(GraphState)

from tools_programmer import (
    tools,
    generate_new_version_file,
    generate_git_patch_and_apply,
    run_one_step,
)

from tools_code_analysis import tools as analysis_tools, get_file_contents

from langchain_core.prompts import (
    SystemMessagePromptTemplate,
)
from langchain_core.messages import ToolMessage, HumanMessage, BaseMessage

from langchain_core.messages import AIMessage
from langgraph.utils.runnable import RunnableCallable

from prompt_grogrammer import system_prompt

system_template = SystemMessagePromptTemplate.from_template(system_prompt)


def call_model(state: GraphState, config: RunnableConfig) -> GraphState:
    logging.info(f"recursion_limit:{config['recursion_limit']}")
    llm_with_tools = _llm.bind_tools(tools + analysis_tools)
    system_message = system_template.format_messages(
        time_zone=state["time_zone"],
    )
    response = cast(
        AIMessage, llm_with_tools.invoke(system_message + state["messages"], config)
    )
    return {"messages": [response]}


async def acall_model(state: GraphState, config: RunnableConfig) -> GraphState:
    logging.info(f"recursion_limit:{config['recursion_limit']}")
    llm_with_tools = _llm.bind_tools(tools + analysis_tools)
    system_message = system_template.format_messages(
        time_zone=state["time_zone"],
    )
    response = cast(
        AIMessage,
        await llm_with_tools.ainvoke(system_message + state["messages"], config),
    )
    return {"messages": [response]}


from langgraph.prebuilt import ToolNode, tools_condition

tool_node = ToolNode(tools=tools + analysis_tools, name="node_tools_programmer")

from langgraph.utils.runnable import RunnableCallable

node_llm = RunnableCallable(call_model, acall_model, name="node_llm_programmer")


class ChangeDataState(TypedDict):
    messages: Annotated[list, add_messages]
    change_list: list
    file_path: str


MAX_RETRIES_GENERATE_CHANGE_LIST = 5


def find_last_success_step(messages: list[BaseMessage]):
    for message in reversed(messages):
        try:
            content = json.loads(message.content)
        except Exception:
            continue
        if (
            isinstance(message, ToolMessage)
            and message.name == run_one_step.get_name()
            and "success" in content
            and content["success"]
        ):
            return message
    return None


def call_model_1(state: GraphState, config: RunnableConfig):
    raise NotImplementedError()


async def acall_model_1(state: GraphState, config: RunnableConfig):
    last_success_step = find_last_success_step(state["messages"])
    if last_success_step:
        content = json.loads(last_success_step.content)
    else:
        last_content_message = [
            message
            for message in state["messages"]
            if isinstance(message, ToolMessage)
            and message.name == get_file_contents.get_name()
        ][0]
        content = json.loads(last_content_message.content)

    file_path = content["file_path"]
    file_content = get_file_contents.invoke({"file_path": file_path})

    last_content = json.loads(state["messages"][-1].content)
    new_content = (
        "File change data is required to complete the step."
        "Please generate file change data based on the name and description of the step."
        "The data format is as follows:"
        f"""
        ```json
            [
                {{
                    'line': int,       # Line number to modify
                    'old': str,        # Original content
                    'new': str,        # New content
                    'type': str        # Change type: 'modify', 'add', or 'delete'
                }},
                ...
            ]
        ```
        
        Step Name: {last_content['name']}
        Step Description: {last_content['description']}

        NOTE:
            - ONLY RETURN THE JSON CODE BLOCK!
            - `old` must be a single line in the original file, not multiple lines.

        Source file:
        ```json
        {file_content}
        ```
        """
    )
    new_messages = [HumanMessage(content=new_content)]
    _llm_0 = ChatAnthropic(
        model="claude-3-7-sonnet-20250219",
        max_tokens=4096,
        temperature=0.7,
        # anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", "not_provided"),
        streaming=True,
        stream_usage=True,
        verbose=True,
    )
    changes = []
    retry_count = 0
    json_content = ""
    while retry_count < MAX_RETRIES_GENERATE_CHANGE_LIST:
        try:
            response = cast(AIMessage, await _llm_0.ainvoke(new_messages))
            content = response.content
            # 提取JSON部分
            if "```json" in content:
                parts = content.split("```json")
                if len(parts) > 1:
                    json_content = parts[1]
                    if "```" in json_content:
                        json_content = json_content.split("```")[0].strip()
            else:
                json_content += content
                if "```" in json_content:
                    json_content = json_content.split("```")[0].strip()
            json_content.strip()

            if json_content:
                changes = json.loads(json_content)
                if retry_count > 0:
                    logging.warning(
                        f"Try generate change list in {retry_count+1} times."
                    )
                break
            new_messages.append(response)
            new_messages.append(
                HumanMessage("Please continue to return the complete code.")
            )
        except json.JSONDecodeError as e:
            logging.warning(f"JSON解析错误: {e}")
            retry_count += 1
    return {
        "change_list": changes,
        "file_path": file_path,
        "messages": state["messages"],
    }


node_generate_change_data = RunnableCallable(
    call_model, acall_model_1, name="node_generate_change_data"
)


from git_patch_generator import generate_and_apply_patch_safely


def node_generate_git_patch(state: ChangeDataState):
    last_message = state["messages"][-1]
    if len(state["change_list"]) > 0:
        change_str = json.dumps(state["change_list"])
        patch_hash = sha1(change_str.encode("utf-8")).hexdigest()[:8]
        result_file, preview = generate_and_apply_patch_safely(
            state["file_path"],
            state["change_list"],
            state["file_path"] + "." + patch_hash + ".patched",
            force=True,
            preview=True,
        )
        logging.info(preview.get_preview())
        with open(result_file, "r", encoding="utf-8") as f:
            file_content = f.read()
        result = {
            "success": True,
            "message": (
                f"Step completed successfully."
                # "Updated file content as follow:"
                # f"```{file_content}```"
            ),
            "file_path": result_file,
        }
    else:
        result = {
            "success": False,
            "message": "An exception occurred during the data generation process for the modified file, and no modified data was received.",
        }
    last_message.content = json.dumps(result)
    return {"messages": [last_message]}


def edge_tools_to_modification(state: GraphState):
    last_masseage = state["messages"][-1]
    if (
        not isinstance(last_masseage, ToolMessage)
        or last_masseage.name != run_one_step.get_name()
    ):
        return node_llm.get_name()
    else:
        return node_generate_change_data.get_name()


graph_builder.add_node(node_llm.name, node_llm)
graph_builder.add_node(tool_node.get_name(), tool_node)
graph_builder.add_node(node_generate_change_data.get_name(), node_generate_change_data)
graph_builder.add_node(node_generate_git_patch.__name__, node_generate_git_patch)

graph_builder.add_conditional_edges(
    node_llm.get_name(),
    tools_condition,
    {"tools": tool_node.get_name(), END: END},
)
graph_builder.add_conditional_edges(
    tool_node.get_name(),
    edge_tools_to_modification,
    {
        node_generate_change_data.get_name(): node_generate_change_data.get_name(),
        node_llm.get_name(): node_llm.get_name(),
    },
)
graph_builder.add_edge(
    node_generate_change_data.get_name(), node_generate_git_patch.__name__
)
graph_builder.add_edge(node_generate_git_patch.__name__, node_llm.get_name())

graph_builder.add_edge(START, node_llm.get_name())

graph = graph_builder.compile()
graph.name = "graph_programmer"
