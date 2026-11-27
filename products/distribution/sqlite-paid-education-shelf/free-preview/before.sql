SELECT e.sku, e.quantity AS expected_quantity, c.quantity AS counted_quantity
FROM expected AS e LEFT JOIN counted AS c ON c.sku = e.sku
WHERE e.quantity <> c.quantity
ORDER BY e.sku;
