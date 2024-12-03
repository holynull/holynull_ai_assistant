分析一下代码prompt/default1.py，这样生成提示词会有哪些问题？
提示词的内容有哪些问题？
提示词是否可以只用英文？
根据上面的分析改进代码和提示词的内容。并且要求提示词只使用英文。请返回完整的改进后的代码。

```
使用链接中的pypdfloader,以及langchain,实现一个工具。要求能够根据用户的提问，根据pdf文件给出答案。https://python.langchain.com/v0.2/api_reference/community/document_loaders/langchain_community.document_loaders.pdf.PyPDFLoader.html
```

```python
import os
import hashlib
import asyncio
from functools import lru_cache
from langchain.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain.vectorstores import FAISS
from langchain.chains.retrieval_qa.base import RetrievalQA
from langchain_core.callbacks.manager import AsyncCallbackManager
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.document_compressors import LLMChainExtractor


@lru_cache(maxsize=100)
def cached_llm(question):
    return llm(question)


def get_pdf_hash(pdf_path):
    with open(pdf_path, "rb") as f:
        file_hash = hashlib.md5()
        chunk = f.read(8192)
        while chunk:
            file_hash.update(chunk)
            chunk = f.read(8192)
    return file_hash.hexdigest()


@tool
async def pdf_qa(pdf_path, question, force_reload=False):
    """
    Asynchronously load a PDF file, create or load a vector database, and answer questions.

    Args:
    pdf_path (str): Path to the PDF file
    question (str): The question to be answered
    force_reload (bool): Whether to force reload the PDF and create a new vector database

    Returns:
    str: The answer to the question
    """
    pdf_hash = get_pdf_hash(pdf_path)

    db_dir = "vector_db_cache"
    os.makedirs(db_dir, exist_ok=True)
    db_path = os.path.join(db_dir, f"{pdf_hash}_faiss_index")

    if os.path.exists(db_path) and not force_reload:
        print("Loading existing vector database...")
        embeddings = OpenAIEmbeddings()
        db = FAISS.load_local(db_path, embeddings)
    else:
        print("Creating new vector database...")
        loader = PyPDFLoader(pdf_path)
        documents = await asyncio.to_thread(loader.load)

        # Use RecursiveCharacterTextSplitter for more intelligent splitting
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50,
            length_function=len,
            separators=["\n\n", "\n", " ", ""],
        )
        texts = await asyncio.to_thread(text_splitter.split_documents, documents)

        embeddings = OpenAIEmbeddings()
        db = await asyncio.to_thread(FAISS.from_documents, texts, embeddings)
        await asyncio.to_thread(db.save_local, db_path)

    callback_manager = AsyncCallbackManager([StreamingStdOutCallbackHandler()])

    # Use ContextualCompressionRetriever for more comprehensive retrieval
    base_retriever = db.as_retriever(
        search_kwargs={"k": 10}
    )  # Increase k for more documents
    compressor = LLMChainExtractor.from_llm(cached_llm)
    retriever = ContextualCompressionRetriever(
        base_compressor=compressor, base_retriever=base_retriever
    )

    qa_chain = RetrievalQA.from_chain_type(
        llm=cached_llm,
        chain_type="stuff",
        retriever=retriever,
        return_source_documents=True,
        callback_manager=callback_manager,
        chain_type_kwargs={"verbose": True},
    )

    result = await qa_chain.acall(
        {"query": question},
        config={"configurable": {"model": "openai_gpt_4o_mini"}},
    )
    return result["result"]
```

能不能使用内存级别的向量数据库，或者不使用向量数据库。因为embedding很消耗时间。

```python
@tool
async def pdf_summarize(pdf_path, question):
    """
    Asynchronously load a PDF file, process its content, and generate summaries of its sections.

    This function reads a PDF file, splits it into manageable chunks, and creates concise summaries
    for each chunk. It's useful for quickly grasping the main points of a long document without
    reading it in its entirety.

    Args:
    pdf_path (str): Path to the PDF file to be summarized
    force_reload (bool): Whether to force reload the PDF and reprocess it, ignoring any cached data

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
5. Do not attempt to directly answer the question; instead, provide a comprehensive collection of relevant information from the text

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
    batch_data = [{"text": doc.page_content, "question": question} for doc in documents]

    summaries = chain.batch(
        batch_data,
        config={"configurable": {"model": "openai_gpt_4o_mini"}},
    )

    # Combine all summaries
    result = "PDF Summary:\n\n"
    for i, summary in enumerate(summaries, 1):
        result += f"Section {i} Summary:\n{summary}\n\n"

    return result
```

优化prompt，让返回的结果使用与question相同的语言。

```python
@tool
def moderation(text:str):
    moderation = OpenAIModerationChain()
    return moderation.invoke(text)
```
添加描述：当你需要对用户的输入和工具返回的结果进行审核时很有用。

```python
system_prompt = """You are a professional news analyst and Ethereum blockchain expert working for Mlion with multilingual communication capabilities. Your role involves providing in-depth analyses for both news events and Ethereum addresses, while ensuring responses are in the same language as the user's query.

### News Analysis Guidelines:
1. **Introduction**: Start by welcoming the audience to Mlion's news analysis and introducing yourself as Simba. For example, "Welcome to Mlion's news analysis, I'm Simba."
2. **Overview**: Provide a brief summary of the news event.
3. **Background Information**: Offer details about the main companies or individuals involved (history, primary activities, market positioning, industry standing).
4. **Reasons Behind the Event**: Examine internal and external factors influencing the event.
5. **Event Details**: Mention the time, place, involved entities, and disclosed financial details.
6. **Impact Examination**: Analyze the effects on the company, customers, industry, and potential regulatory changes.
7. **Future Predictions**: Predict possible future directions considering current situations and potential plans.
8. **Use of Internet Tools**: Gather more information and expert opinions using internet search tools.
9. **Explanation of Key Terms**: Make the context clear by explaining any key terms or jargon.
10. **Historical Context**: Provide insights by examining similar past events or trends.
11. **Commentary**: Offer professional insights and opinions, using engaging phrases.
12. **Conclusion**: Thank the readers for their attention, using "Thank you for reading Mlion's news analysis."

### Ethereum Address Analysis Guidelines:
1. **Current Time**: Obtain the current date and time.
2. **Identify Organization or Project**: Provide relevant information about the address's organization or project.
3. **Transaction Behavior Analysis**: Examine significant transactions and interactions.
4. **Risk Identification**: Highlight potential security risks and illicit activities.
5. **Frequent Interactions Analysis**: Identify and describe frequently interacting addresses.
6. **Use Cases or Strategies**: Suggest potential use cases or strategies.
7. **Current Token Holdings Analysis**: Analyze types, quantities, values, and changes in token holdings.
8. **Historical Activity Analysis**: Examine historical token holdings and transaction volumes.
9. **DeFi Activities Identification**: Identify main DeFi activities linked to the address.
10. **Smart Contract Interactions Review**: Assess significant smart contract interactions.
11. **Time-Series Activity Analysis**: Provide a time-series analysis based on current data.
12. **Token Balance Changes Analysis**: Review balance changes, trends, and significant transactions.
13. **Additional Insights**: Offer any other relevant insights.

### Decision-Making for Information Gathering:
- **Specific Events or News**: Gather the latest articles or reports.
- **General Inquiries or Analytical Questions**: Gather comprehensive information or perform in-depth analysis.
- **Recent Data Queries**: Obtain the current date and time first.

### Handling Visual Content and HTML:
- Preserve and return all HTML elements exactly as received.
- Always return iframes in their original HTML format.
- Include brief explanatory text when necessary without altering the HTML content.

### Multilingual Communication Guidelines:
- Identify the language of the user's input and respond in the same language.
- Maintain consistency in language use unless explicitly asked to switch.
- If unsure about the language, default to English.
- If you encounter a language you're not fluent in, politely ask the user to communicate in another language.

### Style and Tone:
- For news analysis: Adopt the tone of a news media host named Simba. Use expressions like "Let’s delve deeper into...", "What stands out here is...", "It's important to note that...", "In summary...", and "Looking ahead..." to make the response more engaging.
- For Ethereum address analysis: Maintain objectivity, provide clear summaries, and highlight key points with proper citations where applicable.

You are now ready to provide comprehensive and engaging analyses of news events and Ethereum addresses in multiple languages. Await the first user input to determine the language of response."""
```

修改上面的prompt。强调用户的输入黑人种玉米必须经过moderation才能进行后续的处理。以及工具返回的结果也必须经过moderation才能返回。如果moderation返回的结果极差，要坚决拒绝处理。

```python
@tool
def moderation(text: str):
    """
    Useful when you need to review user input and tool responses for compliance and safety.

    This function utilizes OpenAIModerationChain to check the input text for adherence to
    community standards, helping to filter out inappropriate or harmful content.
    It returns the moderation results to ensure the content is safe and appropriate.
    """
```
请根据链接内容，完成上面的函数。https://platform.openai.com/docs/api-reference/moderations/create


我现在需要针对“非法武器”、“自杀或自残”、“性内容”、“暴力和仇恨”以及“犯罪策划”这些方面，对一个基于LLM的Agent进行测试。请生成5个测试输入。

如何对一个基于LLM的AI Agent，在针对防范“非法武器”、“自杀或自残”、“性内容”、“暴力和仇恨”以及“犯罪策划”这些内容输出进行测试？