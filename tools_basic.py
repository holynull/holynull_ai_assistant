from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
import re
from langchain.agents import tool
from langchain_openai import ChatOpenAI
from langchain_core.prompts import (
    ChatPromptTemplate,
    PromptTemplate,
)
from langchain_core.output_parsers import StrOutputParser
from openai_assistant_tools import GoogleSerperAPIWrapper
import openai_assistant_api_docs
import json
from openai_assistant_tools import TradingviewWrapper
from html import unescape
from typing import List
import asyncio
import os
from langchain.agents import Tool
from langchain.chains.qa_with_sources.retrieval import RetrievalQAWithSourcesChain
from rebyte_langchain.rebyte_langchain import RebyteEndpoint
from pydantic import BaseModel, Field
from langchain.output_parsers import (
    PydanticToolsParser,
    StructuredOutputParser,
    ResponseSchema,
    PydanticOutputParser,
)
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import ConfigurableField
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_community.chat_models import ChatPerplexity
from langchain_mistralai.chat_models import ChatMistralAI
from langchain_cohere import ChatCohere
from pathlib import Path
import sys

from langchain.agents import load_tools
from dotenv import load_dotenv

if getattr(sys, "frozen", False):
    script_location = Path(sys.executable).parent.resolve()
else:
    script_location = Path(__file__).parent.resolve()
load_dotenv(dotenv_path=script_location / ".env")

headers = {
    "Accepts": "application/json",
    "X-CMC_PRO_API_KEY": os.getenv("CMC_API_KEY"),
}

llm = ChatAnthropic(
    model="claude-3-opus-20240229",
    # max_tokens=,
    temperature=0.9,
    # anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", "not_provided"),
    streaming=True,
    verbose=True,
).configurable_alternatives(  # This gives this field an id
    # When configuring the end runnable, we can then use this id to configure this field
    ConfigurableField(id="model"),
    # default_key="openai_gpt_4_turbo_preview",
    default_key="anthropic_claude_3_opus",
    anthropic_claude_3_5_sonnet=ChatAnthropic(
        model="claude-3-5-sonnet-20240620",
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
        model="gpt-4-turbo-2024-04-09",
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
    mistral_large=ChatMistralAI(
        model="mistral-large-latest", temperature=0.9, verbose=True, streaming=True
    ),
    command_r_plus=ChatCohere(
        model="command-r-plus", temperature=0.9, verbose=True, streaming=True
    ),
)


@tool
def getTokenMetadata(symbol: str) -> str:
    """
    Useful when you need get the metadata of a token.
    """
    url = f"https://pro-api.coinmarketcap.com/v2/cryptocurrency/info?symbol={symbol}"
    response = requests.get(url, headers=headers)
    return json.dumps(response.json())


@tool
def get_multiple_token_prices(addresses: list[str]):
    """
    Useful when you need get some cryptocurrency's latest price.
    """
    # url = 'https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest'
    # parameters = {
    #     'symbol': ','.join(symbols),
    #     'convert': 'USD'
    # }

    # response = requests.get(url, headers=headers, params=parameters)

    # if response.status_code == 200:
    #     data = response.json()
    #     prices = {}
    #     for symbol in symbols:
    #         if symbol in data['data']:
    #             price = data['data'][symbol]['quote']['USD']['price']
    #             prices[symbol] = price
    #         else:
    #             print(f"Symbol {symbol} not found in response.")
    #             prices[symbol] = None
    #     return prices
    # else:
    #     print(f"Error {response.status_code}: {response.json()['status']['error_message']}")
    #     return None
    _addresses = ",".join(addresses)
    url = f"https://api.coingecko.com/api/v3/simple/token_price/ethereum?contract_addresses={_addresses}&vs_currencies=usd"
    response = requests.get(url)
    data = response.json()
    price_info = []
    for address in addresses:
        price = data.get(address, {}).get("usd")
        if price:
            price_info.append({"contract_address": address, "price": price})
        else:
            print(f"Address: {address}, Price information not available.")
    return data


tradingview = TradingviewWrapper(llm=llm)


# @tool
# def googleSerperSearch(query: str, search_type: str = None) -> str:
#     """Search for a webpage with Google based on the query.
#     Set the optional search_type (str) parameter to specify whether to search news (search_type='news') or web pages (search_type=None).
#     """
#     if search_type == "news":
#         newsSearch = GoogleSerperAPIWrapper(type=search_type, tbs="qdr:h")
#         return json.dumps(
#             [
#                {
#                     "title": r["title"],
#                     "link": r["link"] if "link" in r else "",
#                     "snippet": r["snippet"],
#                     "imageUrl": r["imageUrl"] if "imageUrl" in r else "",
#                 }
#                 for r in newsSearch.results(query=query)["news"]
#             ]
#         )
#     else:
#         searchWebpage = GoogleSerperAPIWrapper()
#         return json.dumps(
#             [
#                 {
#                     "title": r["title"],
#                     "link": r["link"],
#                     "snippet": r["snippet"],
#                 }
#                 for r in searchWebpage.results(query=query)["organic"]
#             ]
#         )


class GoogleSearchEngineQuery(BaseModel):
    """Search over Google Search."""

    terms: str = Field(
        ...,
        description="The keywords to search.",
    )

    tbs: str = Field(..., description="")


class GoogleSearchEngineQueryTerms(BaseModel):
    """Search over Google Search."""

    terms: str = Field(
        ...,
        description="The keywords to search.",
    )


class GoogleSearchEngineResult(BaseModel):
    """Search over Google Search."""

    # title: str
    link: str
    # snippet: str
    # imageUrl: str


@tool
def searchNewsToAnswer(question: str) -> str:
    """Useful when you need answer questions use news. Input for this should be a complete question or request.
    After executing this tool, you need to execute `summarizeRelevantContentsNews`.
    """

    outParser = PydanticOutputParser(pydantic_object=GoogleSearchEngineQuery)
    prompt_template_0 = """{format_instructions}

Generate news search parameters `terms` and `tbs`  based on the question. 
Search engines only search for news, so do not include words like news in terms.

Use `tbs` to set the time range and do not generate time-related terms.
`tbs` is required.
The `tbs` parameter of the Google Search API is a very useful tool that allows you to refine and filter search results. Its primary use is to filter search results by time range, but it can also be utilized for other purposes. When using the `tbs` parameter, you can specify a time range for the search results (e.g., past 24 hours, past week, etc.), or filter results by specific dates.

### Some common examples of using the `tbs` parameter:

1. **Time Range**:
   - `tbs=qdr:w`: Content from the past week.
   - `tbs=qdr:m`: Content from the past month.
   - `tbs=qdr:y`: Content from the past year.

2. **Specific Dates**:
   - Combine `cd_min` and `cd_max` to specify a specific date range, format as `mm/dd/yyyy`. For example, `tbs=cdr:1,cd_min:01/01/2022,cd_max:12/31/2022` would search for all content within the year 2022.

3. **Custom Time Range**:
   - You can also use specific syntax to define a custom time range. For example, `tbs=qdr:n10` to search for content from the past 10 minutes.

### Points to Note When Using the `tbs` Parameter:

- The `tbs` parameter is flexible but needs to be used correctly to achieve the desired filtering effect.
- Besides time filtering, the `tbs` parameter can be used for other advanced search features, though these are generally less discussed and documented.
- When using the Google Search API, ensure you comply with its terms of use, including but not limited to rate limits, restrictions on commercial usage, etc.

Return Example:
```json
{{
	"terms":"Hello World Keywords",
    "tbs":"qdr:w"
}}
```

Question:{question}
"""
    chain_0 = (
        PromptTemplate(
            template=prompt_template_0,
            input_variables=["question"],
            partial_variables={
                "format_instructions": outParser.get_format_instructions()
            },
        )
        | llm
        | outParser
    )
    query = chain_0.invoke(
        {"question": question},
        config={"configurable": {"model": "anthropic_claude_3_5_sonnet"}},
    )
    print(query)
    newsSearch = GoogleSerperAPIWrapper(type="news", tbs=query.tbs, k=20)
    results = newsSearch.results(query=query.terms)
    if "news" in results:
        results = results["news"]
    elif "organic" in results:
        results = results["organic"]
    elif "images" in results:
        results = results["images"]
    elif "places" in results:
        results = results["places"]
    else:
        return "There is no result return."
    search_result = [
        {
            "title": r["title"],
            "link": r["link"] if "link" in r else "",
            # "snippet": r["snippet"],
            "imageUrl": r["imageUrl"] if "imageUrl" in r else "",
        }
        for r in results
    ]
    result_str = json.dumps(search_result)
    return result_str


@tool
def searchWebPageToAnswer(question: str) -> str:
    """Useful when you need answer questions use web page. Input for this should be a complete question or request.
    After executing this tool, you need to execute `summarizeRelevantContents`.
    """

    outParser = PydanticOutputParser(pydantic_object=GoogleSearchEngineQueryTerms)
    prompt_template_0 = """{format_instructions}

Generate Google search parameters `terms` based on the question. 
Extract the keywords required for search from the question.

Return Example:
```json
{{
	"terms":"Hello World Keywords"
}}
```

Question:{question}
"""
    chain_0 = (
        PromptTemplate(
            template=prompt_template_0,
            input_variables=["question"],
            partial_variables={
                "format_instructions": outParser.get_format_instructions()
            },
        )
        | llm
        | outParser
    )
    query = chain_0.invoke(
        {"question": question},
        config={"configurable": {"model": "anthropic_claude_3_5_sonnet"}},
    )
    print(query)
    newsSearch = GoogleSerperAPIWrapper(type="search", k=20)
    results = newsSearch.results(query=query.terms)
    if "news" in results:
        results = results["news"]
    elif "organic" in results:
        results = results["organic"]
    elif "images" in results:
        results = results["images"]
    elif "places" in results:
        results = results["places"]
    else:
        return "There is no result return."
    search_result = [
        {
            "title": r["title"],
            "link": r["link"] if "link" in r else "",
            # "snippet": r["snippet"],
            "imageUrl": r["imageUrl"] if "imageUrl" in r else "",
        }
        for r in results
    ]
    result_str = json.dumps(search_result)
    return result_str


@tool
def searchPlacesToAnswer(question: str) -> str:
    """Useful when you need search some places to answer question. Input for this should be a complete question."""

    outParser = PydanticOutputParser(pydantic_object=GoogleSearchEngineQueryTerms)
    prompt_template_0 = """{format_instructions}

Generate Google search parameters `terms`  based on the question. 
`terms` are search terms generated based on question.

Question:{question}
"""
    chain_0 = (
        PromptTemplate(
            template=prompt_template_0,
            input_variables=["question"],
            partial_variables={
                "format_instructions": outParser.get_format_instructions()
            },
        )
        | llm
        | outParser
    )
    query = chain_0.invoke(
        {"question": question},
        config={"configurable": {"model": "anthropic_claude_3_5_sonnet"}},
    )
    print(query)
    newsSearch = GoogleSerperAPIWrapper(type="places")
    results = newsSearch.results(query=query.terms)
    if "news" in results:
        results = results["news"]
    elif "organic" in results:
        results = results["organic"]
    elif "images" in results:
        results = results["images"]
    elif "places" in results:
        results = results["places"]
    else:
        return "There is no result return."
    search_result = results
    result_str = json.dumps(search_result)
    return result_str


@tool
def searchImagesToAnswer(question: str) -> str:
    """Useful when you need search some images to answer question. Input for this should be a complete question."""

    outParser = PydanticOutputParser(pydantic_object=GoogleSearchEngineQueryTerms)
    prompt_template_0 = """{format_instructions}

Generate Google search parameters `terms` based on the question. 
`terms` are search terms generated based on question.

Question:{question}
"""
    chain_0 = (
        PromptTemplate(
            template=prompt_template_0,
            input_variables=["question"],
            partial_variables={
                "format_instructions": outParser.get_format_instructions()
            },
        )
        | llm
        | outParser
    )
    query = chain_0.invoke(
        {"question": question},
        config={"configurable": {"model": "anthropic_claude_3_5_sonnet"}},
    )
    print(query)
    newsSearch = GoogleSerperAPIWrapper(type="images")
    results = newsSearch.results(query=query.terms)
    if "news" in results:
        results = results["news"]
    elif "organic" in results:
        results = results["organic"]
    elif "images" in results:
        results = results["images"]
    elif "places" in results:
        results = results["places"]
    else:
        return "There is no result return."
    search_result = results
    result_str = json.dumps(search_result)
    return result_str


from langchain_community.document_loaders import SpiderLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_transformers import Html2TextTransformer
from langchain_community.vectorstores.utils import filter_complex_metadata
from langchain_core.documents import Document

h2tTransformer = Html2TextTransformer()


# @tool
def getDocumentFromLink(
    link: str, chunk_size: int, chunk_overlap: int
) -> List[Document]:
    """get documents from link."""
    loader = SpiderLoader(
        url=link,
        mode="scrape",  # if no API key is provided it looks for SPIDER_API_KEY in env
    )
    try:
        html = loader.load()
    except Exception as e:
        print(e)
        clean_html = getHTMLFromURL(link)
        html = [Document(clean_html)]
    html = filter_complex_metadata(html)
    html[0].metadata["source"] = ""
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


@tool
def summarizeRelevantContents(links: List[str], question: str) -> str:
    """
    Get relevant content from returned by `searchWebPageToAnswer`.
    The parameter `links` should be links returned by `searchWebPageToAnswer`.
    The parameter `question` is the same as the input question of `searchWebPageToAnswer`.
    """
    prompt_template = """Extract as much relevant content about the question as possible from the context below.

Question:{question}

Context:
```plaintext
{text}
```
"""
    chain = ChatPromptTemplate.from_template(prompt_template) | llm | StrOutputParser()
    # text = "\n".join([remove_html_tags(getHTMLFromURL(link)) for link in links])
    contents = []

    # loader = AsyncChromiumLoader(links)
    # html = loader.load()

    splits = []
    for link in links:
        _s = getDocumentFromLink(link, chunk_size=10000, chunk_overlap=1500)
        if _s is not None and len(splits) == 0:
            splits = _s
        elif _s is not None and len(splits) > 0:
            splits = splits + _s
        else:
            continue

    contents = chain.batch(
        [
            {
                "text": _split.page_content,
                "question": question,
            }
            for _split in splits
        ],
        config={"configurable": {"model": "anthropic_claude_3_5_sonnet"}},
    )
    return (
        "The contents of the first three search results are extracted as follows:\n"
        + "\n".join(contents)
    )


@tool
def answerQuestionFromLinks(link: str, question: str) -> str:
    """
    Useful when the question that needs to be answered points to a specific link.
    The parameter `links` should be complete url links.
    The parameter `question` should be a complete question about `links`.
    """
    prompt_template = """Context is the content fragment extracted from the link.  Please organize the context clearly. And answer questions based on the collation results.

The format of the returned result is as follows:

```
Final Fragment: xxxxxx

Answer: xxxxxx
```

Link:{link}

Question: {question}

Context:
```plaintext
{text}
```
"""
    chain = ChatPromptTemplate.from_template(prompt_template) | llm | StrOutputParser()
    splits = getDocumentFromLink(link, chunk_size=1000, chunk_overlap=200)
    contents = chain.batch(
        [
            {
                "link": link,
                "text": _split.page_content,
                "question": question,
            }
            for _split in splits
        ],
        config={"configurable": {"model": "anthropic_claude_3_5_sonnet"}},
    )
    return "The content snippet obtained from the link is as follows:\n" + (
        "\n" + "#" * 70 + "\n"
    ).join(contents)


@tool
def summarizeRelevantContentsNews(links: List[str], question: str) -> str:
    """
    Get relevant content from returned by `searchNewsToAnswer`.
    The parameter `links` should be links returned by `searchNewsToAnswer`.
    The parameter `question` is the same as the input question of `searchNewsToAnswer`.
    """
    prompt_template = """Extract as much relevant content about the question as possible from the context below.

Question:{question}

Context:
```plaintext
{text}
```
"""
    chain = ChatPromptTemplate.from_template(prompt_template) | llm | StrOutputParser()
    # text = "\n".join([remove_html_tags(getHTMLFromURL(link)) for link in links])
    contents = []

    # loader = AsyncChromiumLoader(links)
    # html = loader.load()

    splits = []
    for link in links:
        _s = getDocumentFromLink(link, chunk_size=10000, chunk_overlap=1500)
        if _s is not None and len(splits) == 0:
            splits = _s
        elif _s is not None and len(splits) > 0:
            splits = splits + _s
        else:
            continue

    contents = chain.batch(
        [
            {
                "text": _split.page_content,
                "question": question,
            }
            for _split in splits
        ],
        config={"configurable": {"model": "anthropic_claude_3_5_sonnet"}},
    )
    return (
        "The contents of the first three search results are extracted as follows:\n"
        + "\n".join(contents)
    )


def remove_html_tags(text):
    """Remove html tags from a string"""
    clean = re.compile("<.*?>")
    text = re.sub(clean, "", text)  # Remove HTML tags
    text = unescape(text)  # Unescape HTML entities
    text = re.sub(r"(?m)^[\t ]+$", "", text)
    text = re.sub(r"\n+", "", text)
    return text


from pyppeteer import launch


async def fetch_page(url):
    browser = await launch()
    page = await browser.newPage()
    await page.goto(url)
    html_content = await page.content()
    await browser.close()
    return html_content


# from langchain_community.tools.arxiv.tool import ArxivQueryRun
from arxiv_wrapper import ArxivAPIWrapper

# arxiv = ArxivQueryRun()


@tool
def arxiv_search(query: str):
    """A wrapper around Arxiv.org
    Useful for when you need to answer questions about Physics, Mathematics,
    Computer Science, Quantitative Biology, Quantitative Finance, Statistics,
    Electrical Engineering, and Economics
    from scientific articles on arxiv.org.
    Input should be a search query."""
    api_wrapper = ArxivAPIWrapper(doc_content_chars_max=10000)
    return api_wrapper.run(query=query)


@tool
def arxiv_load(entry_id: str):
    """Useful for when your need to know the content of some paper on Arxiv.org.
    Input should be the entry_id return from `arxiv_search`."""
    api_wrapper = ArxivAPIWrapper(doc_content_chars_max=10000)
    return api_wrapper.load(query=entry_id)


import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

driver_path = "chromedriver-mac-x64/chromedriver"
service = Service(executable_path=driver_path)
# 创建ChromeOptions对象
chrome_options = Options()
# 添加无头模式参数
chrome_options.add_argument("--headless")


@tool
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
    # else:
    #     return f"Failed to retrieve the webpage from {url}. status: {response.status_code}"


@tool
def getContentFromURL(url: str, tag: str, class_: str) -> str:
    """Useful when you need to get the text content of the html tag in the URL page.
    The parameter `url` is the URL link of the page you need to read.
    The parameters `tag` and `class_` represent extracting the text content of `tag` whose classes attribute is equal to `class_`.
    """
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")
    html = soup.find(tag, class_=class_)
    return remove_html_tags(str(html))


@tool
async def getHTMLFromURLs(urls: list[str]) -> str:
    """useful when you need get the HTML of URLs. The input to this should be URL list."""
    req_tasks = []
    for url in urls:
        req_tasks.append(fetch_page(url=url))
    contents = await asyncio.gather(*req_tasks)
    result = ""
    for c in contents:
        soup = BeautifulSoup(c, "html.parser")
        result += "\n" + remove_html_tags(soup.prettify())
    return result


from langchain.document_loaders import PyPDFLoader


@tool
async def pdf_summarize(pdf_path, question):
    """
    Asynchronously load a PDF file, process its content, and generate summaries of its sections.

    This function reads a PDF file, splits it into manageable chunks, and creates concise summaries
    for each chunk. It's useful for quickly grasping the main points of a long document without
    reading it in its entirety.

    Args:
    pdf_path (str): Path to the PDF file to be summarized
    question (str): User's question about the PDF file, and in user's language.

    Returns:
    str: A compilation of summaries from different sections of the PDF, providing an overview
         of the entire document's content
    """
    prompt_template = """
Please carefully analyze the following text excerpt in relation to the given question. Your task is to extract and present as much relevant information as possible that could be useful in addressing the question. Your response should:

1. Focus on identifying and extracting all pieces of information from the text that are relevant to the question
2. Include any facts, data, examples, or context that could be helpful in formulating an answer to the question
3. Present the information in a structured and detailed manner
4. If the text contains technical terms or concepts related to the question, include explanations of these
5. Match the language of your output to the language used in the question

Text excerpt:
{text}

Question: {question}

Relevant information extracted from the text:
"""
    chain = ChatPromptTemplate.from_template(prompt_template) | llm | StrOutputParser()
    loader = PyPDFLoader(pdf_path)
    documents = loader.load()
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    documents = text_splitter.split_documents(documents=documents)
    # for doc in documents:
    #     negtive, text = moderation(doc.page_content)
    #     if negtive:
    #         return text
    batch_data = [{"text": doc.page_content, "question": question} for doc in documents]

    summaries = chain.batch(
        batch_data,
        config={"configurable": {"model": "anthropic_claude_3_5_sonnet"}},
    )

    # Combine all summaries
    result = "PDF Summary:\n\n"
    for i, summary in enumerate(summaries, 1):
        result += f"Section {i} Summary:\n{summary}\n\n"

    return result


from langchain.chains.moderation import OpenAIModerationChain


import requests
import json
from typing import Dict, Any


def moderation(text: str) -> Dict[str, Any]:
    """
    Use OpenAI's Moderation API to check if the input text complies with community standards,
    filtering out inappropriate or harmful content.

    Args:
    text (str): The text to be moderated

    Returns:
    Dict[str, Any]: A dictionary containing the moderation results
    """
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}",
    }
    data = {"input": text, "model": "omni-moderation-latest"}

    response = requests.post(
        "https://api.openai.com/v1/moderations", headers=headers, data=json.dumps(data)
    )

    if response.status_code != 200:
        raise Exception(f"API request failed with status code: {response.status_code}")

    result = response.json()
    print(text)
    print(result)
    if result["results"][0]["flagged"]:
        return True, "Result was found that violates Mlion's content policy."
    else:
        return False, None
    # return {
    #     "flagged": result["results"][0]["flagged"],
    #     "categories": result["results"][0]["categories"],
    #     "category_scores": result["results"][0]["category_scores"]
    # }


from tools_file import tools as file_tools

tools = [
    searchWebPageToAnswer,
    searchNewsToAnswer,
    searchPlacesToAnswer,
    searchImagesToAnswer,
    summarizeRelevantContents,
    summarizeRelevantContentsNews,
    answerQuestionFromLinks,
    arxiv_search,
    arxiv_load,
    pdf_summarize,
] + file_tools
