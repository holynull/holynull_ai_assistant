import json
from typing import Annotated, List, Literal, cast
from typing_extensions import TypedDict

from langchain_anthropic import ChatAnthropic

from langchain_core.runnables import (
    RunnableConfig,
)

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.utils.runnable import RunnableCallable

from langchain_core.messages import HumanMessage
from langchain_core.documents import Document
from langchain_community.document_loaders import SpiderLoader
from langchain_community.vectorstores.utils import filter_complex_metadata
from langchain_text_splitters import RecursiveCharacterTextSplitter
import re
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

_llm = ChatAnthropic(
    model="claude-3-7-sonnet-20250219",
    max_tokens=4096,
    temperature=0.9,
    # anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", "not_provided"),
    streaming=True,
    stream_usage=True,
    verbose=True,
)


class State(TypedDict):
    messages: Annotated[list, add_messages]


graph_builder = StateGraph(State)

from tools_search import tools, search_webpage, search_news, access_links_content

from langchain_core.prompts import SystemMessagePromptTemplate, ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from langchain_core.messages import AIMessage, ToolMessage
from langgraph.utils.runnable import RunnableCallable

from langchain_community.document_transformers import Html2TextTransformer


def format_messages(state: State):
    from prompt_search import system_prompt

    system_template = SystemMessagePromptTemplate.from_template(system_prompt)
    system_message = system_template.format_messages()
    return system_message + state["messages"]


system_message = RunnableCallable(format_messages)
from langgraph.types import Command, Send


def call_model(state: State, config: RunnableConfig) -> State | Command:
    llm_with_tools = _llm.bind_tools(tools)
    model_runnable = system_message | llm_with_tools
    response = cast(AIMessage, model_runnable.invoke(state, config))

    return {"messages": [response]}


async def acall_model(state: State, config: RunnableConfig) -> State:
    llm_with_tools = _llm.bind_tools(tools)
    model_runnable = system_message | llm_with_tools
    response = cast(AIMessage, await model_runnable.ainvoke(state, config))

    return {"messages": [response]}


class LinksContentState:
    links_content: list[dict]


message_id_map = {}


def edge_get_links_read_content(
    state: State,
) -> Literal["node_llm", "node_read_content"] | list[Send]:
    last_message = state["messages"][-1]
    if isinstance(last_message, ToolMessage) and (
        last_message.name == search_webpage.get_name()
        or last_message.name == search_news.get_name()
        or last_message.name == access_links_content.get_name()
    ):
        content = json.loads(last_message.content)
        search_result = content["search_result"]
        links = [
            {"link": sr["link"], "message_id": last_message.id} for sr in search_result
        ]
        return [
            Send(
                node_read_content.__name__,
                link,
            )
            for link in links
        ]
    else:
        return node_llm.get_name()


class LinkRelaventContentState:
    link: str
    question: str
    message_id: str


KEY_LINK_RELAVENT_CONTENT = "link_relavent_content"
KEY_LINK_CONTENT_SPLITS = "link_content_splits"

# driver_path = "chromedriver-linux64/chromedriver"
driver_path = "chromedriver-mac-x64/chromedriver"
service = Service(executable_path=driver_path)
# 创建ChromeOptions对象
chrome_options = Options()
# 添加无头模式参数
chrome_options.add_argument("--headless")


def getHTMLFromURL(url: str) -> str:
    """useful when you need get the HTML of URL. The input to this should be URL."""
    # response = requests.get(url)
    # soup = BeautifulSoup(response.text, "html.parser")
    # return soup.prettify()
    # driver_path = "chromedriver-mac-x64/chromedriver"
    # service = Service(executable_path=driver_path)
    # 创建ChromeOptions对象
    # chrome_options = Options()
    # 添加无头模式参数
    # chrome_options.add_argument("--headless")
    browser = webdriver.Chrome(service=service, options=chrome_options)

    # 获取网页内容
    browser.get(url=url)
    html_content = browser.page_source
    soup = BeautifulSoup(html_content, "html.parser")
    # if response.status_code == 200:
    # soup = BeautifulSoup(response.text, "html.parser")
    body = soup.find("body")
    for tag in body.find_all(
        [
            "link",
            "script",
            "style",
            "button",
            "input",
            "meta",
            "iframe",
            "img",
            "noscript",
            "svg",
        ]
    ):
        tag.decompose()
    for tag in body.findAll(True):
        tag.attrs = {
            key: value
            for key, value in tag.attrs.items()
            if key not in ["class", "style"]
        }

    # 可选：清理空白行
    clean_html = re.sub(r"(?m)^[\t ]+$", "", str(body))
    browser.quit()
    return clean_html


from langchain_community.document_loaders import WebBaseLoader


def getDocumentFromLink(
    link: str, chunk_size: int, chunk_overlap: int
) -> List[Document]:
    """get documents from link."""

    loader = WebBaseLoader(web_paths=[link])
    try:
        html = loader.load()
    except Exception as e:
        print(e)
        try:
            loader = SpiderLoader(
                url=link,
                mode="scrape",  # if no API key is provided it looks for SPIDER_API_KEY in env
            )
            html = loader.load()
        except Exception as e:
            clean_html = getHTMLFromURL(link)
            html = [Document(clean_html)]
    # html = filter_complex_metadata(html)
    # html[0].metadata["source"] = ""
    # h2tTransformer = Html2TextTransformer()
    # docs_text = h2tTransformer.transform_documents(html)
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size, chunk_overlap=chunk_overlap
    )
    _split = text_splitter.split_documents(html)
    splits = []
    if len(splits) == 0:
        splits = _split
    else:
        splits = splits + _split
    return splits


async def node_read_content(state: LinkRelaventContentState):
    splits = getDocumentFromLink(state["link"], chunk_size=5000, chunk_overlap=1500)
    if state["message_id"] not in message_id_map:
        message_id_map[state["message_id"]] = {}
        message_id_map[state["message_id"]][KEY_LINK_CONTENT_SPLITS] = []
    else:
        message_id_map[state["message_id"]][KEY_LINK_CONTENT_SPLITS] += splits


def node_read_content_reduce(state: State):
    return state


def edge_read_content_extract_relevant_content(state: State):
    last_message = state["messages"][-1]
    for message in reversed(state["messages"]):
        if isinstance(message, HumanMessage):
            last_human_message = message
            break
    question = last_human_message.content
    splits = message_id_map[last_message.id][KEY_LINK_CONTENT_SPLITS]
    return [
        Send(
            "node_extranct_relevant_content",
            {
                "content": [s.page_content],
                "question": question,
                "message_id": last_message.id,
            },
        )
        for s in splits
    ]


class ContentInLink:
    content: str
    message_id: str
    question: str


async def node_extranct_relevant_content(state: ContentInLink):
    prompt_template = """Extract as much relevant content about the question as possible from the context below.

Question:{question}

Context:
```plaintext
{text}
```
"""
    chain = ChatPromptTemplate.from_template(prompt_template) | _llm | StrOutputParser()
    # text = "\n".join([remove_html_tags(getHTMLFromURL(link)) for link in links])
    contents = []

    # loader = AsyncChromiumLoader(links)
    # html = loader.load()

    contents = await chain.ainvoke(
        {
            "text": state["content"],
            "question": state["question"],
        }
    )
    relevant_content = (
        "The contents of the first three search results are extracted as follows:\n"
        + contents
    )

    if state["message_id"] not in message_id_map:
        message_id_map[state["message_id"]] = {}
        message_id_map[state["message_id"]][
            KEY_LINK_RELAVENT_CONTENT
        ] = relevant_content
    else:
        if KEY_LINK_RELAVENT_CONTENT not in message_id_map[state["message_id"]]:
            message_id_map[state["message_id"]][
                KEY_LINK_RELAVENT_CONTENT
            ] = relevant_content
        else:
            message_id_map[state["message_id"]][
                KEY_LINK_RELAVENT_CONTENT
            ] += relevant_content


def node_relevant_reduce(state: State):
    last_message = state["messages"][-1]
    last_message = cast(ToolMessage, last_message)
    content = json.loads(last_message.content)
    relevant_content = message_id_map[last_message.id][KEY_LINK_RELAVENT_CONTENT]
    content["content_from_search_result"] = relevant_content
    last_message.content = json.dumps(content)
    state["messages"][-1] = last_message
    message_id_map.pop(last_message.id)
    return state


node_llm = RunnableCallable(call_model, acall_model, name="node_llm")

graph_builder.add_node(node_llm)

from langgraph.prebuilt import ToolNode, tools_condition

tool_node = ToolNode(tools=tools, name="node_tools")
graph_builder.add_node(tool_node.get_name(), tool_node)
graph_builder.add_node(node_read_content.__name__, node_read_content)
graph_builder.add_node(node_read_content_reduce.__name__, node_read_content_reduce)
graph_builder.add_node(
    node_extranct_relevant_content.__name__, node_extranct_relevant_content
)
# graph_builder.add_node("node_get_link", node_get_link)
graph_builder.add_node(node_relevant_reduce.__name__, node_relevant_reduce)

graph_builder.add_edge(START, node_llm.get_name())
graph_builder.add_conditional_edges(
    node_llm.get_name(),
    tools_condition,
    {"tools": tool_node.get_name(), END: END},
)
graph_builder.add_conditional_edges(
    tool_node.get_name(),
    edge_get_links_read_content,
    {
        node_llm.get_name(): node_llm.get_name(),
        node_read_content.__name__: node_read_content.__name__,
    },
)
graph_builder.add_edge(node_read_content.__name__, node_read_content_reduce.__name__)
graph_builder.add_conditional_edges(
    node_read_content_reduce.__name__,
    edge_read_content_extract_relevant_content,
    [node_extranct_relevant_content.__name__],
)
graph_builder.add_edge(
    node_extranct_relevant_content.__name__, node_relevant_reduce.__name__
)
graph_builder.add_edge(node_relevant_reduce.__name__, node_llm.get_name())
graph = graph_builder.compile()
graph.name = "graph_search"
