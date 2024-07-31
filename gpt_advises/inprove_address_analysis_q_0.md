```python
def analysis_address_on_ethereum(address: str) -> str:
    """
    Useful when you need analysis an address of Ethereum.
    The parameter `address` should be a complete address on Ethereum.
    """
    labels = get_address_labels.invoke({"addresses": [address]})
    tags = get_address_tag.invoke({"address": address})
    llm = ChatAnthropic(
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
        mistral_large=ChatMistralAI(
            model="mistral-large-latest", temperature=0.1, verbose=True, streaming=True
        ),
        command_r_plus=ChatCohere(
            model="command-r-plus", temperature=0.9, verbose=True, streaming=True
        ),
    )
    llm_chain = llm.with_config({"configurable": {"llm": "openai_gpt_4o"}})
    prompt_template = """
    Address: {address}
    Labels from Dune: 
    ```json
    {labels}
    ```json
    Tags from Etherscan.io: {tags}
    
    Please provide a detailed analysis of the address, explaining what organization or project it represents and giving as much information as possible. If there are any risks associated with this address, please highlight them.
    """
    _chain = (
        PromptTemplate.from_template(prompt_template) | llm_chain | StrOutputParser()
    )
    return _chain.invoke({"address": address, "labels": labels, "tags": tags})
```

我们之前用上面的方法实现了分析ethereum地址。现在我们能够获取地址上各种token的余额数据如下：

```json
[
			{
		"blockchain": "ethereum",
		"day": "2024-07-15 00:00:00",
		"address": "0xdfd5293d8e347dfe59e90efd55b2956a1343963d",
		"token_symbol": "GAL",
		"token_address": "0x1c0f8c46987752e563e7a0d86d543610aedd88ca",
		"token_standard": "erc20",
		"token_id": "<nil>",
		"balance": 578492034.1254432201,
		"balance_usd": "<nil>"
	},
	{
		"blockchain": "ethereum",
		"day": "2024-07-15 00:00:00",
		"address": "0xdfd5293d8e347dfe59e90efd55b2956a1343963d",
		"token_symbol": "ANT",
		"token_address": "0xa117000000f279d81a1d3cc75430faa017fa5a2e",
		"token_standard": "erc20",
		"token_id": "<nil>",
		"balance": 67.25226339,
		"balance_usd": "552.1410824319"
	},
	{
		"blockchain": "ethereum",
		"day": "2024-07-15 00:00:00",
		"address": "0xdfd5293d8e347dfe59e90efd55b2956a1343963d",
		"token_symbol": "OGN",
		"token_address": "0x8207c1ffc5b6804f6024322ccf34f29c3541ae26",
		"token_standard": "erc20",
		"token_id": "<nil>",
		"balance": 1007244.2445606299,
		"balance_usd": "94717.21978150339"
	},
	{
		"blockchain": "ethereum",
		"day": "2024-07-15 00:00:00",
		"address": "0xdfd5293d8e347dfe59e90efd55b2956a1343963d",
		"token_symbol": "DUSK",
		"token_address": "0x940a2db1b7008b6c776d4faaca729d6d4a4aa551",
		"token_standard": "erc20",
		"token_id": "<nil>",
		"balance": 564756.1190339499,
		"balance_usd": "143860.89095763708"
	},
	{
		"blockchain": "ethereum",
		"day": "2024-07-15 00:00:00",
		"address": "0xdfd5293d8e347dfe59e90efd55b2956a1343963d",
		"token_symbol": "LUN",
		"token_address": "0xfa05a73ffe78ef8f1a739473e462c54bae6567d9",
		"token_standard": "erc20",
		"token_id": "<nil>",
		"balance": 0.19505303,
		"balance_usd": "<nil>"
	}
]
```

请问如何改进分析方法（增加从地址上token余额角度分析），使分析对于用户来说更有用，更具有价值，以及对用户产生粘性。