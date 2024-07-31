left join (
    SELECT
      token_address,
      SUM(amount_usd) AS total_liquidity_usd
    FROM
      (
        SELECT
          block_time,
          token_bought_address AS token_address,
          amount_usd
        FROM
          dex.trades
        WHERE
          block_time > CAST('{{three_month_ago}}' AS timestamp)
          AND blockchain = 'ethereum'
        UNION ALL
        SELECT
          block_time,
          token_sold_address AS token_address,
          amount_usd
        FROM
          dex.trades
        WHERE
          block_time > CAST('{{three_month_ago}}' AS timestamp)
          AND blockchain = 'ethereum'
      ) AS combined_trades
    GROUP BY
      token_address
    ORDER BY
      total_liquidity_usd DESC
  ) as dex_volume on lb.token_address = dex_volume.token_address