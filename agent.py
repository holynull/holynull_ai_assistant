from pathlib import Path
import sys
from fastapi import FastAPI
from dotenv import load_dotenv

from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_community.chat_models import ChatPerplexity
from langchain_mistralai import ChatMistralAI
from langchain_cohere import ChatCohere

# from callback import AgentCallbackHandler
# from langchain.callbacks.manager import AsyncCallbackManager
from datetime import datetime


# from langsmith import Client
from fastapi.middleware.cors import CORSMiddleware

from langchain.agents import AgentExecutor
from langchain_core.prompts import (
    ChatPromptTemplate,
    MessagesPlaceholder,
)
from datetime import datetime
from langchain_core.utils.function_calling import convert_to_openai_function
from langchain_core.utils.function_calling import convert_to_openai_tool
from langchain.agents.format_scratchpad.openai_tools import (
    format_to_openai_tool_messages,
)
from anthropic_tools import (
    AnthropicToolsAgentOutputParser,
    format_to_anthropic_tool_messages,
)
from langchain.agents.output_parsers.openai_tools import OpenAIToolsAgentOutputParser

# from langchain.agents.output_parsers import JSONAgentOutputParser
from langchain_core.runnables import ConfigurableField
from langchain_core.runnables import Runnable


from langchain import hub
from custom_agent_excutor import CustomToolCallingAgentExecutor
from tools_basic import tools
from eddie_tools import getHTMLOfURL
from langchain.memory.chat_memory import BaseMemory

if getattr(sys, "frozen", False):
    script_location = Path(sys.executable).parent.resolve()
else:
    script_location = Path(__file__).parent.resolve()
load_dotenv(dotenv_path=script_location / ".env")

from langsmith import Client

langsmith_client = Client()

# client = Client()

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

from langchain.prompts import load_prompt


def create_agent_executor(
    llm_agent: Runnable,
    memory: BaseMemory,
    image_urls: list[str],
    is_multimodal: bool = False,
) -> AgentExecutor:

    from system_prompt_4 import system_prompt

    if is_multimodal:
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt),
                MessagesPlaceholder(variable_name="chat_history"),
                # SystemMessagePromptTemplate.from_template(
                #     "If using the search tool, prefix the string parameter with [S]."
                # ),
                (
                    "human",
                    [
                        *[
                            {
                                "type": "image_url",
                                "image_url": {"url": f"{url}"},
                            }
                            for url in image_urls
                        ],
                        {
                            "type": "text",
                            "text": "{input}",
                        },
                    ],
                ),
                MessagesPlaceholder(variable_name="agent_scratchpad"),
            ],
        )
    else:
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt),
                MessagesPlaceholder(variable_name="chat_history"),
                # SystemMessagePromptTemplate.from_template(
                #     "If using the search tool, prefix the string parameter with [S]."
                # ),
                (
                    "human",
                    "{input}",
                ),
                MessagesPlaceholder(variable_name="agent_scratchpad"),
            ]
        )

    executor = CustomToolCallingAgentExecutor(
        llm=llm_agent,
        prompts=prompt,
        tools=tools,
        memory=memory,
        max_iterations=20,  # 设置最大迭代次数
        max_execution_time=600,  # 设置最大执行时间（秒）
    )
    return executor


llm_agent = ChatAnthropic(
    model="claude-3-opus-20240229",
    max_tokens=2000,
    temperature=0.9,
    # anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", "not_provided"),
    streaming=True,
    verbose=True,
).configurable_alternatives(  # This gives this field an id
    # When configuring the end runnable, we can then use this id to configure this field
    ConfigurableField(id="llm"),
    # default_key="openai_gpt_4_turbo_preview",
    default_key="anthropic_claude_3_opus",
    anthropic_claude_3_5_sonnet=ChatAnthropic(
        model="claude-3-5-sonnet-20241022",
        max_tokens=2000,
        temperature=0.9,
        # anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", "not_provided"),
        streaming=True,
        stream_usage=True,
        verbose=True,
    ),
    openai_gpt_3_5_turbo_1106=ChatOpenAI(
        model="gpt-3.5-turbo-1106",
        verbose=True,
        streaming=True,
        temperature=0.9,
    ),
    openai_gpt_4_turbo_preview=ChatOpenAI(
        temperature=0.9,
        model="gpt-4-turbo-preview",
        verbose=True,
        streaming=True,
    ),
    openai_gpt_4o=ChatOpenAI(
        temperature=0.9,
        model="gpt-4o",
        verbose=True,
        streaming=True,
    ),
    openai_gpt_4o_mini=ChatOpenAI(
        temperature=0.9,
        model="gpt-4o-mini",
        verbose=True,
        streaming=True,
    ),
    pplx_sonar_medium_chat=ChatPerplexity(
        model="sonar-medium-chat", temperature=0.9, verbose=True, streaming=True
    ),
    pplx_sonar_large_chat=ChatPerplexity(
        model="llama-3.1-sonar-large-128k-online",
        temperature=0.9,
        verbose=True,
        streaming=True,
    ),
    mistral_large=ChatMistralAI(
        model="mistral-large-latest", temperature=0.1, verbose=True, streaming=True
    ),
    command_r_plus=ChatCohere(
        model="command-r-plus", temperature=0.9, verbose=True, streaming=True
    ),
)
