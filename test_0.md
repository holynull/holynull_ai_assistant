```python
@tool
def get_addres_how_much_funds_transfered(
    address: str,
    contract_address: str,
    token_sybmol: str,
    sta_time: str,
    end_time: str,
) -> str:
    """
    This is useful when you need to get how much and where the token transfered from the address.
    The parameter `address` must be complete a address.
    The parameter `contract_address` must be the erc20 token's complete address.
    The parameters `sta_time` and `end_time` indicate the start time and end time in the format of yyyy-MM-dd HH:mm:ss.
    """
    with open("connections.json") as f:
        connection_parameters = json.load(f)
    session = Session.builder.configs(connection_parameters).create()
    sql = """SELECT
  "from",
  "to",
  sum(value) AS "amount"
FROM
  ETHEREUM_ONCHAIN_DATA.ERC20_ETHEREUM.EVT_TRANSFER transfers
WHERE
  "from" = ?
  AND transfers.contract_address = ?
  AND evt_block_time >= CAST(? AS timestamp)
  AND evt_block_time <= CAST(? AS timestamp)
group by
  "from",
  to
ORDER BY
  amount desc;"""
    results_df = session.sql(
        sql, parameter=[address, contract_address, sta_time, end_time]
    )
    session.close()
    if not results_df.empty:
        r_list = results_df.apply(
            lambda row: f"Transfer {row['amount']} {token_sybmol} to {row['to']}.",
            axis=1,
        ).tolist()
        return "\n".join(r_list)
    else:
        return "No data found."
```

OperationalError: 250001: 250001: Could not connect to Snowflake backend after 2 attempt(s).Aborting