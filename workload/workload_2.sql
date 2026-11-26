
-- ==================================================
-- Workload 2: Changed Database Workload
-- Adaptive Workload-Aware Index Tuning
-- Total: 30 SELECT queries
-- ==================================================


-- Q1: Search orders by status and date
SELECT *
FROM Orders
WHERE status = 'Delivered'
AND order_date > '2026-02-01';


-- Q2: Search orders by customer
SELECT *
FROM Orders
WHERE customer_id = 7000;


-- Q3: Search products by category and price
SELECT *
FROM Product
WHERE category = 'Electronics'
AND price > 8000;


-- Q4: Search customers by city
SELECT *
FROM Customer
WHERE city = 'City 10';


-- Q5: Search order items by product
SELECT *
FROM OrderItem
WHERE product_id = 500;


-- Q6: Join orders and customers
SELECT
    o.order_id,
    c.name,
    o.order_date
FROM Orders o
JOIN Customer c
    ON o.customer_id = c.customer_id
WHERE c.city = 'City 5';


-- Q7: Sort orders by date
SELECT *
FROM Orders
ORDER BY order_date DESC
LIMIT 100;


-- Q8: Group order items by product
SELECT
    product_id,
    COUNT(*)
FROM OrderItem
GROUP BY product_id;


-- ==================================================
-- Additional Changed Queries
-- ==================================================


-- Q9: Search orders by amount and status
SELECT *
FROM Orders
WHERE total_amount > 15000
AND status = 'Delivered';


-- Q10: Search orders within a date range
SELECT *
FROM Orders
WHERE order_date BETWEEN '2026-03-01' AND '2026-09-30';


-- Q11: Search orders by customer and status
SELECT *
FROM Orders
WHERE customer_id = 10000
AND status = 'Pending';


-- Q12: Search orders by date and amount
SELECT *
FROM Orders
WHERE order_date > '2026-04-01'
AND total_amount > 5000;


-- Q13: Search products by supplier
SELECT *
FROM Product
WHERE supplier_id = 20;


-- Q14: Search products by price and category
SELECT *
FROM Product
WHERE price BETWEEN 3000 AND 12000
AND category = 'Electronics';


-- Q15: Search order items by quantity
SELECT *
FROM OrderItem
WHERE quantity > 5;


-- Q16: Search order items by order and quantity
SELECT *
FROM OrderItem
WHERE order_id = 75000
AND quantity > 2;


-- Q17: Search suppliers by city
SELECT *
FROM Supplier
WHERE city = 'City 10';


-- Q18: Join products and suppliers
SELECT
    p.product_name,
    p.price,
    s.supplier_name
FROM Product p
JOIN Supplier s
    ON p.supplier_id = s.supplier_id
WHERE s.city = 'City 10';


-- Q19: Join orders and order items
SELECT
    o.order_id,
    o.order_date,
    oi.product_id,
    oi.quantity
FROM Orders o
JOIN OrderItem oi
    ON o.order_id = oi.order_id
WHERE o.order_date > '2026-05-01';


-- Q20: Join order items and products
SELECT
    oi.order_id,
    p.product_name,
    oi.quantity,
    oi.price
FROM OrderItem oi
JOIN Product p
    ON oi.product_id = p.product_id
WHERE p.supplier_id = 20;


-- Q21: Three-table customer order analysis
SELECT
    c.city,
    o.status,
    COUNT(*) AS total_orders
FROM Customer c
JOIN Orders o
    ON c.customer_id = o.customer_id
GROUP BY c.city, o.status;


-- Q22: Total sales by order status
SELECT
    status,
    SUM(total_amount) AS total_sales
FROM Orders
GROUP BY status;


-- Q23: Average quantity by product
SELECT
    product_id,
    AVG(quantity) AS average_quantity
FROM OrderItem
GROUP BY product_id;


-- Q24: Product count by supplier
SELECT
    supplier_id,
    COUNT(*) AS total_products
FROM Product
GROUP BY supplier_id;


-- Q25: Sort orders by amount
SELECT *
FROM Orders
ORDER BY total_amount DESC
LIMIT 200;


-- Q26: Sort products by price
SELECT *
FROM Product
ORDER BY price ASC
LIMIT 200;


-- Q27: Find latest delivered orders
SELECT *
FROM Orders
WHERE status = 'Delivered'
ORDER BY order_date DESC
LIMIT 50;


-- Q28: Customer order details
SELECT
    c.customer_id,
    c.name,
    o.order_date,
    o.total_amount
FROM Customer c
JOIN Orders o
    ON c.customer_id = o.customer_id
WHERE c.city = 'City 15'
AND o.status = 'Delivered';


-- Q29: Products in a particular category from a supplier
SELECT *
FROM Product
WHERE category = 'Electronics'
AND supplier_id = 30
ORDER BY price DESC;


-- Q30: Search order items by product and price
SELECT *
FROM OrderItem
WHERE product_id = 1000
AND price > 1000;
