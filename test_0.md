```sql
SELECT 
    address,
    array_agg(name) as labels
FROM labels.addresses WHERE address in ({{addresses}}) AND blockchain='ethereum'
GROUP BY address;
```

上面是一个dune上的查询，如何优化一下，提高查询速度？