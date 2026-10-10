from __future__ import annotations

import sqlite3
from typing import Any, Dict, List, Tuple
from pydantic import BaseModel


class SqlTestCase(BaseModel):
    id: str
    prompt: str
    canonical_sql: str
    difficulty: str  # "easy" | "medium" | "hard"


def init_benchmark_database(db: sqlite3.Connection):
    """Initializes schema and seeds realistic relational benchmark data."""
    cursor = db.cursor()
    cursor.executescript("""
        DROP TABLE IF EXISTS order_items;
        DROP TABLE IF EXISTS orders;
        DROP TABLE IF EXISTS customers;

        CREATE TABLE customers (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            tier TEXT NOT NULL CHECK (tier IN ('standard', 'gold', 'platinum')),
            created_at TEXT NOT NULL
        );

        CREATE TABLE orders (
            id INTEGER PRIMARY KEY,
            customer_id INTEGER NOT NULL REFERENCES customers(id),
            total_amount REAL NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('pending', 'completed', 'cancelled')),
            created_at TEXT NOT NULL
        );

        CREATE TABLE order_items (
            id INTEGER PRIMARY KEY,
            order_id INTEGER NOT NULL REFERENCES orders(id),
            product_name TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            price REAL NOT NULL
        );

        -- Seed Customers
        INSERT INTO customers VALUES (1, 'Alice Smith', 'platinum', '2026-01-10');
        INSERT INTO customers VALUES (2, 'Bob Jones', 'gold', '2026-01-15');
        INSERT INTO customers VALUES (3, 'Charlie Brown', 'standard', '2026-02-01');
        INSERT INTO customers VALUES (4, 'Diana Prince', 'platinum', '2026-02-20');
        INSERT INTO customers VALUES (5, 'Evan Wright', 'standard', '2026-03-05');

        -- Seed Orders
        INSERT INTO orders VALUES (101, 1, 450.00, 'completed', '2026-02-01');
        INSERT INTO orders VALUES (102, 1, 120.00, 'completed', '2026-02-15');
        INSERT INTO orders VALUES (103, 2, 85.50, 'cancelled', '2026-02-18');
        INSERT INTO orders VALUES (104, 3, 310.00, 'completed', '2026-03-01');
        INSERT INTO orders VALUES (105, 4, 1250.00, 'completed', '2026-03-10');
        INSERT INTO orders VALUES (106, 5, 45.00, 'pending', '2026-03-12');

        -- Seed Order Items
        INSERT INTO order_items VALUES (1, 101, 'Mechanical Keyboard', 2, 150.00);
        INSERT INTO order_items VALUES (2, 101, 'USB-C Hub', 3, 50.00);
        INSERT INTO order_items VALUES (3, 102, 'Wireless Mouse', 1, 120.00);
        INSERT INTO order_items VALUES (4, 104, '4K Monitor', 1, 310.00);
        INSERT INTO order_items VALUES (5, 105, 'GPU Acceleration Rig', 1, 1250.00);
    """)
    db.commit()


BENCHMARK_TASKS: List[SqlTestCase] = [
  SqlTestCase(
    id="task_01",
    prompt="Retrieve all platinum tier customers sorted by name alphabetically.",
    canonical_sql="SELECT id, name, tier FROM customers WHERE tier = 'platinum' ORDER BY name ASC;",
    difficulty="easy",
  ),
  SqlTestCase(
    id="task_02",
    prompt="Count the number of completed orders in the system.",
    canonical_sql="SELECT COUNT(*) as count FROM orders WHERE status = 'completed';",
    difficulty="easy",
  ),
  SqlTestCase(
    id="task_03",
    prompt="Calculate the total revenue from all completed orders.",
    canonical_sql="SELECT SUM(total_amount) as total_revenue FROM orders WHERE status = 'completed';",
    difficulty="medium",
  ),
  SqlTestCase(
    id="task_04",
    prompt="Find the names of customers who have at least one completed order with total amount greater than 400.",
    canonical_sql="""
      SELECT DISTINCT c.name
      FROM customers c
      JOIN orders o ON c.id = o.customer_id
      WHERE o.status = 'completed' AND o.total_amount > 400
      ORDER BY c.name ASC;
    """,
    difficulty="medium",
  ),
  SqlTestCase(
    id="task_05",
    prompt="Find the top customer by total completed spending.",
    canonical_sql="""
      SELECT c.name, SUM(o.total_amount) as total_spent
      FROM customers c
      JOIN orders o ON c.id = o.customer_id
      WHERE o.status = 'completed'
      GROUP BY c.id, c.name
      ORDER BY total_spent DESC
      LIMIT 1;
    """,
    difficulty="hard",
  ),
]
