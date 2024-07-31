import re
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import os
from dune_client.client import DuneClient
from dune_client.types import QueryParameter
from dune_client.query import QueryBase
from langchain.agents import tool
import json
from decimal import Decimal
import requests
from web3 import Web3
import numpy as np
from langchain_anthropic import ChatAnthropic
from langchain_cohere import ChatCohere
from langchain_mistralai import ChatMistralAI
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.runnables import ConfigurableField

from langchain_core.output_parsers import StrOutputParser
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
import concurrent.futures
from langchain_community.document_loaders import SpiderLoader
import swifter

load_dotenv(".env")

DUNE_API_KEY = os.getenv("DUNE_API_KEY")
dune = DuneClient(api_key=DUNE_API_KEY,performance="large")


@tool
def get_ethereum_symbol_info(symbol: str) -> str:
    """
    Useful when you need to get the contract's address and decimals from a cryptocurrency symbol on Ethereum. The input for this should be complete symbol of a cryptocurrency.
    """
    query = QueryBase(
        name="ethereum_get_info_from_symbol",
        query_id=3893389,
        params=[
            QueryParameter.text_type(name="symbol", value=symbol),
        ],
    )
    results_df = dune.run_query_dataframe(query)
    return results_df.to_json(orient="records")


@tool
def get_ethereum_erc20_info(contract_address: list[str]) -> str:
    """
    Useful when you need to get the contract's address and decimals from a cryptocurrency symbol on Ethereum. The input for this should be complete address of a ERC20 contract.
    """
    query = QueryBase(
        name="ethereum_get_info_from_contract_address",
        query_id=3912799,
        params=[
            QueryParameter.text_type(
                name="contract_address", value=",".join(contract_address)
            ),
        ],
    )
    results_df = dune.run_query_dataframe(query)
    return results_df.to_json(orient="records")


@tool
def top_10_eth_transaction(min_amount: float, min_block_time: str) -> str:
    """
    Useful when you need to get the top 10 transactions by eth transaction amount.
    The parameter `min_amout` must be an integer representing the minimum transaction amount in ETH.
    The `min_block_time` parameter must be a time string in the format of yyyy-mm-dd hh:mm:ss, indicating that block_time must exceed this time.
    """
    query = QueryBase(
        name="ethereum_top_eth_transactions",
        query_id=3912752,
        params=[
            QueryParameter.text_type(name="min_amount", value=min_amount),
            QueryParameter.text_type(
                name="min_block_time", value=min_block_time
            ),  # yyyy-MM-dd HH:mm:ss
        ],
    )
    results_df = dune.run_query_dataframe(query)
    return results_df.to_json(orient="records")


@tool
def top_10_erc20_transaction(
    token_contract_address: str, min_amout: float, min_block_time: str
) -> str:
    """
    Useful when you need to get the top 10 volume transactions in the entire Ethereum network.
    The parameter `token_contract_address` is the token contract's address.
    The parameter `min_amout` must be an integer representing the minimum transaction amount in the token.
    The `min_block_time` parameter must be a time string in the format of yyyy-mm-dd hh:mm:ss, indicating that block_time must exceed this time.
    """
    contract_info = json.loads(
        get_ethereum_erc20_info.invoke({"contract_address": [token_contract_address]})
    )
    query = QueryBase(
        name="ethereum_top_erc20_token_transaction",
        query_id=3912780,
        params=[
            QueryParameter.text_type(
                name="contract_address", value=token_contract_address
            ),
            QueryParameter.number_type(
                name="min_amount",
                value=min_amout * (10 ** contract_info[0]["decimals"]),
            ),
            QueryParameter.text_type(
                name="min_block_time", value=min_block_time
            ),  # yyyy-MM-dd HH:mm:ss
        ],
    )
    results_df = dune.run_query_dataframe(query)
    results_df["amount"] = results_df["amount"].apply(lambda a: Decimal(a))
    results_df["amount"] = results_df["amount"].apply(
        lambda a: a / (Decimal(10) ** contract_info[0]["decimals"])
    )
    return results_df.to_json(orient="records")


ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY")
ETHERSCAN_URL = "https://api.etherscan.io/api"


INFURA_API_KEY = os.getenv("INFURA_API_KEY")
# 连接到Infura的以太坊节点
INFURA_URL = f"https://mainnet.infura.io/v3/{INFURA_API_KEY}"

ethers = Web3(Web3.HTTPProvider(INFURA_URL))


@tool
def is_contract_address(address):
    """
    Useful when you need to check if an address is a contract address.
    """
    code = ethers.eth.get_code(Web3.to_checksum_address(address))
    return code != b"" and code != b"0x"


address_info_cache = {}


@tool
def get_token_symbol(contract_address) -> str:
    """
    Get the token symbol for a given Ethereum contract address using Web3.py.

    :param contract_address: Contract address of the token.
    :return: Token symbol or None if not found.
    """
    if not is_contract_address.invoke({"address": contract_address}):
        return ""
    erc20_abi = [
        {
            "constant": True,
            "inputs": [],
            "name": "symbol",
            "outputs": [{"name": "", "type": "string"}],
            "payable": False,
            "stateMutability": "view",
            "type": "function",
        }
    ]

    contract = ethers.eth.contract(
        address=Web3.to_checksum_address(contract_address), abi=erc20_abi
    )
    try:
        symbol = contract.functions.symbol().call()
        return symbol
    except Exception as e:
        print(f"Error: {e}")
        return None


@tool
def get_address_labels(addresses: list[str]) -> str:
    """
    Useful when you need to get a label for some addresses.
    """
    query = QueryBase(
        name="ethereum_get_labels_of_address",
        query_id=3912735,
        params=[
            QueryParameter.text_type(name="addresses", value=",".join(addresses)),
        ],
    )
    results_df = dune.run_query_dataframe(query=query)
    if results_df.empty:
        results_df = pd.DataFrame([{"address": ad, "labels": ""} for ad in addresses])
    tag_df = pd.DataFrame(get_multiple_address_tags.invoke({"addresses": addresses}))
    results_df = results_df.merge(tag_df, on="address", how="left")

    # 定义合并函数
    def merge_labels_and_tags(row):
        if pd.notna(row["tag"]):
            return row["labels"] + "[" + row["tag"] + "]"
        else:
            return row["labels"]

    # 应用合并函数
    results_df["labels"] = results_df.apply(merge_labels_and_tags, axis=1)

    # 删除 tag 列
    results_df.drop(columns=["tag"], inplace=True)
    return results_df.to_json(orient="records")


@tool
def get_funds_transfer_status_in_transaction(tx_hash: str) -> str:
    """
    Useful when you need get funds transfer status in a Ethereum's transaction. Input for this should be a complete transaction's hash.
    """

    result = {}

    # transaction
    transaction = ethers.eth.get_transaction(tx_hash)
    # RPC请求获取交易的trace
    trace_call = {
        "jsonrpc": "2.0",
        "method": "trace_transaction",
        "params": [tx_hash],
        "id": 1,
    }

    response = ethers.manager.request_blocking(
        trace_call["method"], trace_call["params"]
    )
    data = json.loads(ethers.to_json(response))
    _action = [d["action"] for d in data if d["action"]["callType"] == "call"]
    eth_transfer_action = []
    for act in _action:
        act["value"] = int(act["value"], 16)
        act["gas"] = int(act["gas"], 16)
        act["inpu"] = ""  # 去掉input节省token
        if act["value"] > 0:
            act["value"] = Web3.from_wei(act["value"], "ether").to_eng_string()
            eth_transfer_action.append(act)
    # logs
    event_signature_hash = ethers.keccak(text="Transfer(address,address,uint256)").hex()
    receipt = ethers.eth.get_transaction_receipt(tx_hash)
    if receipt and receipt["logs"]:
        logs = [
            log
            for log in receipt["logs"]
            if log["topics"][0].hex() == event_signature_hash
        ]
        contract_addresses = [log["address"] for log in logs]
        contract_addresses = np.unique(contract_addresses)
        erc20_info = json.loads(
            get_ethereum_erc20_info.invoke(
                {"contract_address": contract_addresses.tolist()}
            )
        )
        decoded_logs = []
        for log in logs:
            if log["topics"][0].hex() == event_signature_hash:
                # 解析 Transfer 事件
                from_address = Web3.to_checksum_address(
                    "0x" + log["topics"][1].hex()[-40:]
                )
                to_address = Web3.to_checksum_address(
                    "0x" + log["topics"][2].hex()[-40:]
                )
                value = int(log["data"].hex(), 16)
                ei = [
                    ei for ei in erc20_info if ei["contract_address"] == log["address"]
                ]
                decimals = ei[0]["decimals"] if len(ei) > 0 else 1
                decoded_logs.append(
                    {
                        "from": from_address,
                        "to": to_address,
                        "value": (value / 10**decimals),
                        "token_contract_address": log["address"],
                        # "token_symbol": get_token_symbol(log["address"]),
                    }
                )
            transaction = json.loads(ethers.to_json(transaction))
            transaction["input"] = ""  # 节省token
            result = {
                "transaction": transaction,
                "eth_transfer_action": eth_transfer_action,
                "token_transfer_action": decoded_logs,
            }
    else:
        result = {
            "transaction": json.loads(ethers.to_json(transaction)),
            "eth_transfer_action": eth_transfer_action,
        }
    address_list = (
        [result["transaction"]["from"]]
        + [result["transaction"]["to"]]
        + [t["from"] for t in result["eth_transfer_action"]]
        + [t["to"] for t in result["eth_transfer_action"]]
        + [t["from"] for t in result["token_transfer_action"]]
        + [t["to"] for t in result["token_transfer_action"]]
    )
    unique_addresses = np.unique(address_list)
    no_cached_address = [ad for ad in unique_addresses if ad not in address_info_cache]
    if len(no_cached_address) > 0:
        labels = json.loads(get_address_labels.invoke({"addresses": no_cached_address}))
    for ad in no_cached_address:
        ad_info = {
            "address": ad,
            "symbol": get_token_symbol.invoke({"contract_address": ad}),
            "labels": (
                [l["labels"] for l in labels if l["address"] == ad][0]
                if len([l["labels"] for l in labels if l["address"] == ad]) > 0
                else ""
            ),
        }
        address_info_cache[ad] = ad_info
    ad_info = [address_info_cache[ad] for ad in unique_addresses]
    result["address_info"] = ad_info
    return json.dumps(result)


@tool
def get_address_tag_from_etherscan(address) -> str:
    """
    Useful when you need get the tag of an address.
    """
    url = f"https://etherscan.io/address/{address}"
    loader = SpiderLoader(
        url=url,
        mode="scrape",  # if no API key is provided it looks for SPIDER_API_KEY in env
    )
    try:
        html = loader.load()

        def extract_tag(s):
            # 定义正则表达式模式
            pattern = r"^(.*?)\s*\|\s*Address"

            # 使用re.search找到匹配的部分
            match = re.search(pattern, s)

            if match:
                # 返回匹配的组1，即我们感兴趣的标签部分
                tag = match.group(1).strip()
                if tag:  # 检查tag是否为空
                    return tag
                else:
                    return "No tag found"
            return "No tag found"

        return extract_tag(html[0].page_content.split("\n", 1)[0])
    except Exception as e:
        print(e)
        return "No tag found"


@tool
def get_multiple_address_tags(addresses: list[str]):
    """
    Get tags for multiple Ethereum addresses.
    """
    address_tags = []

    with ThreadPoolExecutor(max_workers=10) as executor:
        results = executor.map(get_address_tag_from_etherscan, addresses)

    for address, tag in zip(addresses, results):
        a_tag = {"address": address, "tag": tag}
        address_tags.append(a_tag)

    return address_tags


@tool
def get_transactions_history_from_dune(address: str) -> str:
    """
    Useful when you need to get the transactions history of an address on Ethereum.
    The parameter `address` must be the contract address of the token.
    """
    query = QueryBase(
        name="get_token_usd_price",
        query_id=3924844,
        params=[
            QueryParameter.text_type(name="address", value=address),
            QueryParameter.text_type(name="N", value=100),
        ],
    )
    results_df = dune.run_query_dataframe(query)
    return results_df.to_json(orient="records")


@tool
def get_address_interact_with(address: str) -> str:
    """
    This is useful when you need to obtain which addresses the address interacted with within 1 months and the transaction behavior of the address.
    The parameter `address` must be complete a address.
    """
    # 1. 获取当前时间
    now = datetime.now()

    # 2. 计算前一天的时间
    yesterday = now - relativedelta(months=1)

    # 4. 将时间格式化为 'yyyy-MM-dd HH:mm:ss' 格式的字符串
    formatted_time = yesterday.strftime("%Y-%m-%d %H:%M:%S")
    query = QueryBase(
        name="eddie_get_erc20_transfer_of_address",
        query_id=3924884,
        params=[
            QueryParameter.text_type(name="address", value=address),
            QueryParameter.text_type(name="min_time", value=formatted_time),
            QueryParameter.text_type(name="N", value=500),
        ],
    )
    results_df = dune.run_query_dataframe(query)
    if not results_df.empty:
        r_arr = results_df.apply(
            lambda row: f"Transfer {row['amount']} {row['symbol']} to {row['to']} at {row['block_time']}.",
            axis=1,
        ).tolist()
        # return results_df.to_json(orient="records")
        return "\n".join(r_arr)
    else:
        return ""


@tool
def get_addres_funds_movements_of(address: str, contract_address: str) -> str:
    """
    This is useful when you need to get the token transfer of an address within 1 months.
    The parameter `address` must be complete a address.
    The parameter `contract_address` must be the erc20 token's contract address as the fund.
    """
    # 1. 获取当前时间
    now = datetime.now()

    # 2. 计算前一天的时间
    yesterday = now - relativedelta(months=1)

    # 4. 将时间格式化为 'yyyy-MM-dd HH:mm:ss' 格式的字符串
    formatted_time = yesterday.strftime("%Y-%m-%d %H:%M:%S")
    query = QueryBase(
        name="eddie_get_some_erc20_transfer_of_address",
        query_id=3940668,
        params=[
            QueryParameter.text_type(name="address", value=address),
            QueryParameter.text_type(name="contract_address", value=contract_address),
            QueryParameter.text_type(name="min_time", value=formatted_time),
            QueryParameter.text_type(name="N", value=500),
        ],
    )
    results_df = dune.run_query_dataframe(query)
    if not results_df.empty:
        r_arr = results_df.apply(
            lambda row: ("Recieve " if row["to"] == address else "Transfer ")
            + f"{row['amount']} {row['symbol']} "
            + ("from " + row["from"] if row["to"] == address else "to " + row["to"])
            + f" at {row['block_time']}. Transation hash: {row['hash']}",
            axis=1,
        ).tolist()
        # return results_df.to_json(orient="records")
        return "\n".join(r_arr)
    else:
        return ""


@tool
def get_eth_movements_of(address: str) -> str:
    """
    This is useful when you need to get the ETH changes of an address within 1 months.
    """
    # 1. 获取当前时间
    now = datetime.now()

    # 2. 计算前一天的时间
    yesterday = now - relativedelta(months=1)

    # 4. 将时间格式化为 'yyyy-MM-dd HH:mm:ss' 格式的字符串
    formatted_time = yesterday.strftime("%Y-%m-%d %H:%M:%S")
    query = QueryBase(
        name="eddie_get_eth_transfer_of_address",
        query_id=3924889,
        params=[
            QueryParameter.text_type(name="address", value=address),
            QueryParameter.text_type(name="min_time", value=formatted_time),
            QueryParameter.text_type(name="N", value=500),
        ],
    )
    results_df = dune.run_query_dataframe(query)
    if not results_df.empty:
        r_arr = results_df.apply(
            lambda row: ("Recieve " if row["to"] == address else "Transfer ")
            + f"{row['eth_value']} ETH "
            + ("from " + row["from"] if row["to"] == address else "to " + row["to"])
            + f" at {row['block_time']}. Transation hash: {row['hash']}",
            axis=1,
        ).tolist()
        # return results_df.to_json(orient="records")
        return "\n".join(r_arr)
    else:
        return ""


# @tool
# def analysis_address_on_ethereum(question: str) -> str:
#     """
#     Useful when you need answer user's question about a Ethereum address. Input for this should be a complete question about some Ethereum address.
#     """
#     llm = ChatAnthropic(
#         model="claude-3-opus-20240229",
#         # max_tokens=,
#         temperature=0.9,
#         # anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", "not_provided"),
#         streaming=True,
#         verbose=True,
#     ).configurable_alternatives(  # This gives this field an id
#         # When configuring the end runnable, we can then use this id to configure this field
#         ConfigurableField(id="llm"),
#         # default_key="openai_gpt_4_turbo_preview",
#         default_key="anthropic_claude_3_opus",
#         openai_gpt_3_5_turbo_1106=ChatOpenAI(
#             model="gpt-3.5-turbo-1106",
#             verbose=True,
#             streaming=True,
#             temperature=0.1,
#         ),
#         openai_gpt_4_turbo_preview=ChatOpenAI(
#             temperature=0.9,
#             model="gpt-4-turbo-preview",
#             verbose=True,
#             streaming=True,
#         ),
#         openai_gpt_4o=ChatOpenAI(
#             temperature=0.9,
#             model="gpt-4o",
#             verbose=True,
#             streaming=True,
#         ),
#         mistral_large=ChatMistralAI(
#             model="mistral-large-latest", temperature=0.1, verbose=True, streaming=True
#         ),
#         command_r_plus=ChatCohere(
#             model="command-r-plus", temperature=0.9, verbose=True, streaming=True
#         ),
#     )
#     llm_extract_address_chain = llm.with_config(
#         {"configurable": {"llm": "openai_gpt_3_5_turbo_1106"}}
#     )
#     prompt_template = """
#     Context:
#     {context}

#     We need extract the Ethereum address from the context above, please extract the address.

#     The Ethereum address in above context is:
#     """
#     _chain_extract_address = (
#         PromptTemplate.from_template(prompt_template)
#         | llm_extract_address_chain
#         | StrOutputParser()
#     )
#     address = _chain_extract_address.invoke({"context": question})
#     address = Web3.to_checksum_address(address)
#     if address == "None":
#         raise Exception(f"Can't extract any address from question:{question}")

#     with concurrent.futures.ThreadPoolExecutor() as executor:
#         future_labels = executor.submit(get_address_labels, {"addresses": [address]})
#         future_token_balances = executor.submit(
#             get_token_balances_of_address, {"address": address}
#         )
#         future_erc20_transfers = executor.submit(
#             get_erc20_transfer_of, {"address": address}
#         )
#         future_eth_transfers = executor.submit(
#             get_eth_transfer_of, {"address": address}
#         )

#         labels = future_labels.result()
#         token_balances_str = future_token_balances.result()
#         erc20_transfer = future_erc20_transfers.result()
#         eth_transfer = future_eth_transfers.result()

#     labels_df = pd.DataFrame(json.loads(labels))
#     if not labels_df.empty:
#         labels = "\n".join(
#             labels_df.apply(
#                 lambda row: row["labels"] + "[" + row["tag"] + "]", axis=1
#             ).tolist()
#         )
#     else:
#         labels = ""

#     token_balances = json.loads(token_balances_str)
#     #

#     # 生成Token余额分析报表
#     token_balance_report = []
#     for token in token_balances:
#         balance_usd = token.get("balance_usd", "N/A")
#         token_balance_report.append(
#             f"Token: {token['token_symbol']} (Contract: {token['token_address']}, Liquidity on DEX in 3 months:${token['total_liquidity_usd']})\n"
#             f"Balance: {token['balance']} (USD: {balance_usd} Price:${token['price_usd']})"
#         )

#     # Token余额分析部分
#     token_analysis = "\n".join(token_balance_report)

#     is_contract = is_contract_address.invoke({"address": address})

#     erc20_transfer_df = pd.DataFrame(json.loads(erc20_transfer))
#     eth_transfer_df = pd.DataFrame(json.loads(eth_transfer))

#     unique_to_addresses = []
#     if not erc20_transfer_df.empty:
#         unique_to_addresses = erc20_transfer_df["to"].unique().tolist()

#     if not eth_transfer_df.empty:
#         unique_to_addresses = np.unique(
#             unique_to_addresses + eth_transfer_df["to"].unique().tolist()
#         ).tolist()

#     if len(unique_to_addresses) > 0:
#         addresses_tags = get_multiple_address_tags.invoke(
#             {"addresses": unique_to_addresses}
#         )
#         tag_df = pd.DataFrame(addresses_tags)

#     if not erc20_transfer_df.empty and not tag_df.empty:
#         erc20_transfer_df = erc20_transfer_df.merge(
#             tag_df, left_on="to", right_on="address", how="left"
#         )
#         erc20_transfer_df.drop(columns=["address"], inplace=True)
#         erc20_transfer_df.rename(columns={"tag": "to_address_tag"}, inplace=True)
#         erc20_transfer = erc20_transfer_df.to_json(orient="records")

#     if not eth_transfer_df.empty and not tag_df.empty:
#         eth_transfer_df = eth_transfer_df.merge(
#             tag_df, left_on="to", right_on="address", how="left"
#         )
#         eth_transfer_df.drop(columns=["address"], inplace=True)
#         eth_transfer_df.rename(columns={"tag": "to_address_tag"}, inplace=True)
#         eth_transfer = eth_transfer_df.to_json(orient="records")

#     if not erc20_transfer_df.empty:
#         erc20_transfer_list = erc20_transfer_df.apply(
#             lambda row: f"{row['from_address']}({row['from_address_labels']}) transfer {row['amount']} USDT({row['contract_address']}) to address {row['to']} (Tags:{row['to_address_labels']}[{row['to_address_tag']}]) at {row['block_time']}.",
#             axis=1,
#         ).tolist()
#         erc20_transfer = "\n".join(erc20_transfer_list)
#     else:
#         erc20_transfer = ""

#     if not eth_transfer_df.empty:
#         eth_transfer_list = eth_transfer_df.apply(
#             lambda row: f"{row['from_address']}({row['from_address_labels']}) transfer {row['eth_value']} ETH to address {row['to']} (Labels:{row['to_address_labels']}[{row['to_address_tag']}]) at {row['block_time']}.",
#             axis=1,
#         ).tolist()
#         eth_transfer = "\n".join(eth_transfer_list)
#     else:
#         eth_transfer = ""

#     llm_chain = llm.with_config({"configurable": {"llm": "openai_gpt_4o"}})
#     prompt_template_1 = """
#     Address: {address}

#     Is a contract address?: {is_contract}

#     Labels:
#     {labels}

#     Token Balances:
#     {token_analysis}

#     Latest 100 ERC20 Transfers History:
#     {erc20_transfer}

#     Lastest 100 ETH Transfers History:
#     {eth_transfer}


#     Please answer the flowing question, and provide a detailed analysis of the address, explaining the following:
#     1. What organization or project this address represents, and give as much information as possible.
#     2. Analyze the transaction behavior and fund movements of this address, including significant transactions and interactions with other addresses.
#     3. Identify and highlight any potential risks associated with this address, such as security risks, fund freezing risks, and any involvement in illicit activities.
#     4. Provide information on other addresses this address interacts with frequently. As much as possible, inform users what project or organization these address data belong to, or who these addresses represent.
#     5. Suggest potential use cases or strategies involving this address.
#     6. Analyze the historical token holdings and transaction volume of this address.
#     7. Identify the main DeFi activities of this address.
#     8. Review any smart contract interactions and assess their significance.
#     9. Provide a time-series analysis of the address’s activity.
#     10. Offer any additional relevant insights based on the available data.

#     Ensure the analysis is deep and comprehensive, covering all relevant aspects.

#     Question: {question}

#     Answer:
#     """
#     _chain = (
#         PromptTemplate.from_template(prompt_template_1) | llm_chain | StrOutputParser()
#     )
#     return _chain.invoke(
#         {
#             "address": address,
#             "is_contract": is_contract,
#             "labels": labels,
#             "token_analysis": token_analysis,
#             "erc20_transfer": erc20_transfer,
#             "eth_transfer": eth_transfer,
#             "question": question,
#         }
#     )


@tool
def get_token_lastest_usd_price(addresses: list[str]) -> str:
    """
    Useful when you need to get the price of token.
    The parameter `address` must be the contract address of the token.
    """
    query = QueryBase(
        name="get_token_usd_price",
        query_id=3917050,
        params=[
            QueryParameter.text_type(
                name="contract_address", value=",".join(addresses)
            ),
        ],
    )
    results_df = dune.run_query_dataframe(query)
    return results_df.to_json(orient="records")


@tool
def get_token_dex_liquidity_in_3_month(addresses: list[str]) -> str:
    """
    Useful when you need to get the price of token.
    The parameter `address` must be the contract address of the token.
    """
    # 1. 获取当前时间
    now = datetime.now()

    # 2. 计算前一天的时间
    yesterday = now - relativedelta(months=7)
    formatted_time = yesterday.strftime("%Y-%m-%d %H:%M:%S")
    query = QueryBase(
        name="get_token_dex_volume",
        query_id=3922413,
        params=[
            QueryParameter.text_type(
                name="contract_address", value=",".join(addresses)
            ),
            QueryParameter.text_type(name="min_time", value=formatted_time),
        ],
    )
    results_df = dune.run_query_dataframe(query)
    return results_df.to_json(orient="records")


@tool
def get_token_balances_of_address(address: str):
    """
    Useful when you need to get the balance of all tokens on an address.
    """

    # 1. 获取当前时间
    now = datetime.now()

    # 2. 计算前一天的时间
    yesterday = now - relativedelta(weeks=1)

    # 4. 将时间格式化为 'yyyy-MM-dd HH:mm:ss' 格式的字符串
    formatted_time = yesterday.strftime("%Y-%m-%d %H:%M:%S")
    query = QueryBase(
        name="eddie_get_token_balance_of_address",
        query_id=3916915,
        params=[
            QueryParameter.text_type(name="min_time", value=formatted_time),
            QueryParameter.text_type(name="wallet_address", value=address),
        ],
    )
    results_df = dune.run_query_dataframe(query=query)
    if not results_df.empty:
        r_arr = results_df.apply(
            lambda row: f"Token: {row['token_symbol']}\nContract address: {row['token_address']}\n"
            + f"Balance: {row['balance']} (USD: {row['balance_usd']} Price:${row['price_usd']})",
            axis=1,
        ).tolist()
        # result["balances"] = f"## Balances of address {address}:\n" + "\n".join(r_arr)
        return f"## Balances of address {address}:\n" + "\n".join(r_arr)
    else:
        return "No balances."


# @tool
# def extract_main_token_of_balances(balances_json: str) -> str:
#     """
#     Useful when you need extract main token in the balances return from `get_token_balances_of_address`.
#     """
#     return json.dumps(extract_token_from_balances(balances_json))


def update_top_tokens(token_list, new_token, key, top_n=5):
    token_list.append(new_token)
    token_list.sort(key=lambda x: x[key], reverse=True)

    if len(token_list) > top_n:
        token_list.pop()


def extract_token_from_balances(data: str) -> dict:
    data = json.loads(data)
    top_value_tokens = []
    top_liquidity_tokens = []

    for token in data:
        balance_usd = token.get("balance_usd")
        total_liquidity_usd = token.get("total_liquidity_usd")

        if balance_usd is not None and balance_usd != "<nil>":
            balance_usd = float(balance_usd)
            update_top_tokens(top_value_tokens, token, "balance_usd")

        if total_liquidity_usd is not None and total_liquidity_usd != "<nil>":
            total_liquidity_usd = float(total_liquidity_usd)
            update_top_tokens(top_liquidity_tokens, token, "total_liquidity_usd")

    top_value_addresses = [
        {
            "address": token["token_address"],
            "symbol": token["token_symbol"],
        }
        for token in top_value_tokens
    ]
    top_liquidity_addresses = [
        {
            "address": token["token_address"],
            "symbol": token["token_symbol"],
        }
        for token in top_liquidity_tokens
    ]

    result = {
        "high_price_token": top_value_addresses,
        "high_liquidity_token": top_liquidity_addresses,
    }
    return result


dune_tools = [
    get_address_labels,
    get_token_balances_of_address,
    top_10_erc20_transaction,
    get_funds_transfer_status_in_transaction,
    get_address_interact_with,
    get_addres_funds_movements_of,
    get_eth_movements_of,
]
