-- INSERT workload
INSERT INTO Orders (customer_id, order_date, status, total_amount)
VALUES (100, '2026-11-20', 'Pending', 2500);

INSERT INTO Product (product_name, category, price, supplier_id)
VALUES ('Test Product', 'Electronics', 7500, 10);

-- UPDATE workload
UPDATE Orders
SET status = 'Delivered'
WHERE customer_id = 5000;

UPDATE Product
SET price = 8500
WHERE category = 'Electronics';

-- DELETE workload
DELETE FROM OrderItem
WHERE order_id = 50000;

DELETE FROM Orders
WHERE status = 'Cancelled';