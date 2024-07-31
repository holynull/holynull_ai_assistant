from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_community.chat_models import ChatPerplexity
from langchain_mistralai import ChatMistralAI
from langchain_cohere import ChatCohere

from datetime import datetime



from langchain.agents import AgentExecutor
from langchain_core.prompts import (
    ChatPromptTemplate,
    MessagesPlaceholder,
)
from datetime import datetime

from langchain_core.runnables import ConfigurableField
from langchain_core.runnables import Runnable
from custom_agent_excutor import  CustomToolCallingAgentExecutor


from dune_tools import dune_tools as tools

def create_agent_executor(llm_agent: Runnable) -> AgentExecutor:

    date = datetime.now().strftime("%b %d %Y")
    system_message = (
        f"Today is {date}.\n\n"
        + """You are an expert in Ethereum blockchain.
When answering users' questions, please use the user's language.

When asked to analyze an Ethereum address, please provide a detailed analysis of the address, explaining the following:
    1. What organization or project this address represents, and give as much information as possible.
    2. Analyze the transaction behavior and fund movements of this address, including significant transactions and interactions with other addresses.
    3. Identify and highlight any potential risks associated with this address, such as security risks, fund freezing risks, and any involvement in illicit activities.
    4. Provide information on other addresses this address interacts with frequently. Utilize address labeling tools to identify and explain the labels of these addresses, providing background information on the projects, organizations, or individuals these labels belong to. Specific requirements include:
        a. Obtain a list of addresses that interact frequently with this address.
        b. Use address labeling tools to get label information for these addresses (such as project, organization, individual).
        c. Analyze these labels, describing which projects, organizations, or individuals these interacting addresses represent.
    5. Suggest potential use cases or strategies involving this address.
    6. Perform a detailed analysis of the current token holdings of this address, including:
        a. The types of tokens held.
        b. The quantity of each token.
        c. The current value of these holdings.
        d. Any significant changes in holdings over time.
        e. The potential risks and benefits associated with holding these tokens.
    7. Analyze the historical token holdings and transaction volume of this address.
    8. Identify the main DeFi activities of this address.
    9. Review any smart contract interactions and assess their significance.
    10. Provide a time-series analysis of the address’s activity.
    11. Offer any additional relevant insights based on the available data.
When analyzing other related addresses, ensure to use address labeling tools to identify and explain the labels of these addresses, providing context on the relevant projects, organizations, or individuals. 
Ensure the analysis is deep and comprehensive, covering all relevant aspects.

"""
    )

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_message),
            MessagesPlaceholder(variable_name="chat_history"),
            # SystemMessagePromptTemplate.from_template(
            #     "If using the search tool, prefix the string parameter with [S]."
            # ),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
    )



    executor = CustomToolCallingAgentExecutor(
        llm=llm_agent, prompts=prompt, tools=tools
    )
    return executor


llm_agent = ChatAnthropic(
    model="claude-3-opus-20240229",
    # max_tokens=,
    temperature=0.9,
    # anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", "not_provided"),
    streaming=True,
    verbose=True,
).configurable_alternatives(  # This gives this field an id
    # When configuring the end runnable, we can then use this id to configure this field
    ConfigurableField(id="llm"),
    # default_key="openai_gpt_4_turbo_preview",
    default_key="anthropic_claude_3_opus",
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
    pplx_sonar_medium_chat=ChatPerplexity(
        model="sonar-medium-chat", temperature=0.9, verbose=True, streaming=True
    ),
    mistral_large=ChatMistralAI(
        model="mistral-large-latest", temperature=0.1, verbose=True, streaming=True
    ),
    command_r_plus=ChatCohere(
        model="command-r-plus", temperature=0.9, verbose=True, streaming=True
    ),
)
"""
Example:

```python
import pprint
from ethereum_address_analysis_agent import ethereum_address_analysis_agent_executor

# 同步调用方法
ethereum_address_analysis_agent_executor.invoke(
    {
        "input": "请帮我分析一下地址0xdfd5293d8e347dfe59e90efd55b2956a1343963d",
        "chat_history": [],
    },
    config={
        "configurable": {"llm": "openai_gpt_4o"},
    },
)

# 异步调用方法
chunks = []
async for chunk in ethereum_address_analysis_agent_executor.astream_events(
    {
        "input": "请帮我分析一下地址0xdfd5293d8e347dfe59e90efd55b2956a1343963d",
        "chat_history": [],
    },
    version="v1",
    config={
        "configurable": {"llm": "openai_gpt_4o"},
    },
):
    chunks.append(chunk)
    print("------")
    pprint.pprint(chunk, depth=1)
```
"""
ethereum_address_analysis_agent_executor = create_agent_executor(llm_agent=llm_agent)