
-- ==================================================
-- Workload 1: Initial Database Workload
-- Adaptive Workload-Aware Index Tuning
-- Total: 50 SELECT queries
-- ==================================================


-- Q1: Search orders by customer
SELECT *
FROM Orders
WHERE customer_id = 5000;


-- Q2: Search orders by status
SELECT *
FROM Orders
WHERE status = 'Pending';


-- Q3: Search orders by date
SELECT *
FROM Orders
WHERE order_date > '2026-01-01';


-- Q4: Search products by category
SELECT *
FROM Product
WHERE category = 'Electronics';


-- Q5: Search products by price
SELECT *
FROM Product
WHERE price > 5000;


-- Q6: Customer and order JOIN
SELECT
    o.order_id,
    c.name,
    o.order_date,
    o.status
FROM Orders o
JOIN Customer c
    ON o.customer_id = c.customer_id
WHERE c.city = 'City 5';


-- Q7: Order items for a particular order
SELECT *
FROM OrderItem
WHERE order_id = 50000;


-- Q8: Products in a particular order
SELECT
    oi.order_id,
    p.product_name,
    oi.quantity,
    oi.price
FROM OrderItem oi
JOIN Product p
    ON oi.product_id = p.product_id
WHERE oi.order_id = 50000;


-- Q9: Group orders by status
SELECT
    status,
    COUNT(*)
FROM Orders
GROUP BY status;


-- Q10: Group products by category
SELECT
    category,
    COUNT(*)
FROM Product
GROUP BY category;


-- Q11: Sort orders by amount
SELECT *
FROM Orders
ORDER BY total_amount DESC
LIMIT 100;


-- Q12: Sort products by price
SELECT *
FROM Product
ORDER BY price DESC
LIMIT 100;


-- Q13: Customer + date filtering
SELECT *
FROM Orders
WHERE customer_id = 5000
AND order_date > '2026-01-01';


-- Q14: Status + date filtering
SELECT *
FROM Orders
WHERE status = 'Pending'
AND order_date > '2026-01-01';


-- Q15: Product category + price filtering
SELECT *
FROM Product
WHERE category = 'Electronics'
AND price > 5000;


-- ==================================================
-- Additional Queries
-- ==================================================


-- Q16: Search customers by city
SELECT *
FROM Customer
WHERE city = 'City 10';


-- Q17: Search suppliers by city
SELECT *
FROM Supplier
WHERE city = 'City 5';


-- Q18: Search products by supplier
SELECT *
FROM Product
WHERE supplier_id = 10;


-- Q19: Search orders within a date range
SELECT *
FROM Orders
WHERE order_date BETWEEN '2026-01-01' AND '2026-06-30';


-- Q20: Search orders by minimum amount
SELECT *
FROM Orders
WHERE total_amount > 10000;


-- Q21: Search orders by status and amount
SELECT *
FROM Orders
WHERE status = 'Delivered'
AND total_amount > 5000;


-- Q22: Search products by category and supplier
SELECT *
FROM Product
WHERE category = 'Electronics'
AND supplier_id = 10;


-- Q23: Search products within a price range
SELECT *
FROM Product
WHERE price BETWEEN 1000 AND 10000;


-- Q24: Search order items by product and quantity
SELECT *
FROM OrderItem
WHERE product_id = 500
AND quantity > 2;


-- Q25: Search order items by price
SELECT *
FROM OrderItem
WHERE price > 2000;


-- Q26: Join customers and orders with status filtering
SELECT
    c.customer_id,
    c.name,
    o.order_id,
    o.status
FROM Customer c
JOIN Orders o
    ON c.customer_id = o.customer_id
WHERE o.status = 'Delivered';


-- Q27: Join products and suppliers
SELECT
    p.product_id,
    p.product_name,
    s.supplier_name,
    s.city
FROM Product p
JOIN Supplier s
    ON p.supplier_id = s.supplier_id
WHERE s.city = 'City 5';


-- Q28: Join orders and order items
SELECT
    o.order_id,
    o.status,
    oi.product_id,
    oi.quantity
FROM Orders o
JOIN OrderItem oi
    ON o.order_id = oi.order_id
WHERE o.status = 'Pending';


-- Q29: Join order items and products by category
SELECT
    oi.order_id,
    p.product_name,
    p.category,
    oi.quantity
FROM OrderItem oi
JOIN Product p
    ON oi.product_id = p.product_id
WHERE p.category = 'Electronics';


-- Q30: Three-table join for order details
SELECT
    c.name,
    o.order_id,
    p.product_name,
    oi.quantity
FROM Customer c
JOIN Orders o
    ON c.customer_id = o.customer_id
JOIN OrderItem oi
    ON o.order_id = oi.order_id
JOIN Product p
    ON oi.product_id = p.product_id
WHERE c.city = 'City 10';


-- Q31: Count orders for each customer
SELECT
    customer_id,
    COUNT(*) AS total_orders
FROM Orders
GROUP BY customer_id;


-- Q32: Average order amount by status
SELECT
    status,
    AVG(total_amount) AS average_amount
FROM Orders
GROUP BY status;


-- Q33: Total sales by customer
SELECT
    customer_id,
    SUM(total_amount) AS total_sales
FROM Orders
GROUP BY customer_id;


-- Q34: Average product price by category
SELECT
    category,
    AVG(price) AS average_price
FROM Product
GROUP BY category;


-- Q35: Total quantity sold for each product
SELECT
    product_id,
    SUM(quantity) AS total_quantity
FROM OrderItem
GROUP BY product_id;


-- Q36: Count products for each supplier
SELECT
    supplier_id,
    COUNT(*) AS product_count
FROM Product
GROUP BY supplier_id;


-- Q37: Sort customers by name
SELECT *
FROM Customer
ORDER BY name
LIMIT 100;


-- Q38: Sort orders by date and amount
SELECT *
FROM Orders
ORDER BY order_date DESC, total_amount DESC
LIMIT 100;


-- Q39: Sort order items by quantity
SELECT *
FROM OrderItem
ORDER BY quantity DESC
LIMIT 100;


-- Q40: Sort products by category and price
SELECT *
FROM Product
ORDER BY category, price DESC
LIMIT 100;


-- Q41: Find latest orders for a customer
SELECT *
FROM Orders
WHERE customer_id = 7000
ORDER BY order_date DESC
LIMIT 50;


-- Q42: Find high-value pending orders
SELECT *
FROM Orders
WHERE status = 'Pending'
AND total_amount > 10000
ORDER BY total_amount DESC;


-- Q43: Find products from a supplier within a price range
SELECT *
FROM Product
WHERE supplier_id = 20
AND price BETWEEN 2000 AND 15000;


-- Q44: Find customers from a city and their orders
SELECT
    c.customer_id,
    c.name,
    o.order_id,
    o.total_amount
FROM Customer c
JOIN Orders o
    ON c.customer_id = o.customer_id
WHERE c.city = 'City 15'
AND o.total_amount > 5000;


-- Q45: Find order items for expensive products
SELECT
    oi.order_id,
    oi.quantity,
    oi.price,
    p.product_name
FROM OrderItem oi
JOIN Product p
    ON oi.product_id = p.product_id
WHERE p.price > 5000;


-- Q46: Count orders by customer city
SELECT
    c.city,
    COUNT(o.order_id) AS order_count
FROM Customer c
JOIN Orders o
    ON c.customer_id = o.customer_id
GROUP BY c.city;


-- Q47: Total order item value by product
SELECT
    product_id,
    SUM(quantity * price) AS total_value
FROM OrderItem
GROUP BY product_id;


-- Q48: Search orders by customer and status
SELECT *
FROM Orders
WHERE customer_id = 10000
AND status = 'Delivered';


-- Q49: Search order items by order and product
SELECT *
FROM OrderItem
WHERE order_id = 75000
AND product_id = 500;


-- Q50: Search products by category and sort by price
SELECT *
FROM Product
WHERE category = 'Electronics'
ORDER BY price DESC
LIMIT 50;
