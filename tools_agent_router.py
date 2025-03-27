import datetime
from langchain_core.tools import tool


@tool
def route_to_search_agent():
    """
    This tool will hand over the question to a Search Engine Expert.
    Expert capabilities include:
        - Performs a web search using Google search engine and returns formatted results.
        - Performs a news search using Google News and returns formatted results in JSON format.
        - Performs a place search using Google Places API and returns raw search results.
        - Performs an image search using Google Images and returns raw search results.
        - Access the links content
    """
    return "Now requesting a Search Engine Expert."


@tool
def route_to_programmer_agent():
    """
    This tool will hand over the question to a Programmer Expert.
    Expert capabilities include:
	   - Perform step-by-step tasks to complete programming requirements
    """
    return "Now requesting a Programmer Expert."


# @tool
# def route_to_code_analysis_agent():
#     """
#     This tool will hand over the question to a Code Analysis Expert.
#     Expert capabilities include:
#         - Analysis code
#         - Get the current workspace directory.
#         - Generate a tree-like string representation of the workspace directory structure, respecting .gitignore rules.
#     """
#     return "Now requesting a Programmer Expert."


@tool
def get_utc_time():
    """
    Useful when you need to get the current UTC time of the system.
    Returns the current UTC time in ISO format (YYYY-MM-DD HH:MM:SS.mmmmmm).
    """
    import pytz

    return datetime.datetime.now(tz=pytz.UTC).isoformat(" ")


from graph_search import graph as search_webpage_graph
from graph_programmer import graph as programmer_graph
from graph_code_analysis import graph as code_analysis_graph


def get_next_node(tool_name: str):
    if tool_name == route_to_search_agent.get_name():
        return search_webpage_graph.get_name()
    elif tool_name == route_to_programmer_agent.get_name():
        return programmer_graph.get_name()
    # elif tool_name == route_to_code_analysis_agent.get_name():
    #     return code_analysis_graph.get_name()
    else:
        return None


tools = [
    get_utc_time,
    route_to_search_agent,
    route_to_programmer_agent,
    # route_to_code_analysis_agent,
]
