SELECT
  evt_block_time as block_time,
  evt_tx_hash as hash,
  erc20_ethereum.evt_transfer.contract_address,
  tokens.symbol,
  tokens.decimals,
  "from",
  to,
  value,
  value / POWER(10, tokens.decimals) as amount,
  to_labels.labels as to_address_labels
FROM
  erc20_ethereum.evt_transfer
  left join (
    SELECT
      address,
      array_agg(name) as labels
    FROM
      labels.addresses
    WHERE
      blockchain = 'ethereum'
    GROUP BY
      address
  ) as to_labels on to = to_labels.address
  left join tokens.erc20 tokens on erc20_ethereum.evt_transfer.contract_address = tokens.contract_address and tokens.blockchain='ethereum'
WHERE
  "from" = {{address}}
order by
  block_time desc
limit
  {{N}}