from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from typing import Any

from .commerce_models import DataOrigin, PROTECTED_FACTS, Product, ProductFact


class CommerceDatabase:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.execute("""CREATE TABLE IF NOT EXISTS products (
            product_id TEXT PRIMARY KEY, sku TEXT NOT NULL UNIQUE, payload TEXT NOT NULL)""")
        self.db.execute("""CREATE TABLE IF NOT EXISTS product_facts (
            product_id TEXT NOT NULL, field TEXT NOT NULL, value TEXT NOT NULL,
            origin TEXT NOT NULL, source TEXT NOT NULL DEFAULT '', verified INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY(product_id, field, origin, source))""")
        self.db.commit()

    def close(self) -> None:
        self.db.close()

    def upsert_product(self, product: Product) -> None:
        self.db.execute(
            "INSERT INTO products(product_id,sku,payload) VALUES(?,?,?) "
            "ON CONFLICT(product_id) DO UPDATE SET sku=excluded.sku,payload=excluded.payload",
            (product.product_id, product.sku, json.dumps(product.to_dict(), ensure_ascii=False)),
        )
        self.db.commit()

    def get_product(self, product_id: str) -> Product | None:
        row = self.db.execute("SELECT payload FROM products WHERE product_id=?", (product_id,)).fetchone()
        return Product(**json.loads(row["payload"])) if row else None

    def add_fact(self, fact: ProductFact) -> None:
        if fact.field in PROTECTED_FACTS and fact.origin == DataOrigin.AI_COPY:
            raise ValueError(f"AI-generated data cannot set protected commercial fact: {fact.field}")
        self.db.execute(
            "INSERT OR REPLACE INTO product_facts(product_id,field,value,origin,source,verified) "
            "VALUES(?,?,?,?,?,?)",
            (fact.product_id, fact.field, json.dumps(fact.value, ensure_ascii=False),
             fact.origin.value, fact.source, int(fact.verified)),
        )
        self.db.commit()

    def grounded_value(self, product_id: str, field: str) -> Any | None:
        product = self.get_product(product_id)
        if product and hasattr(product, field):
            value = getattr(product, field)
            if value not in (None, "", [], {}):
                return value
        row = self.db.execute(
            "SELECT value FROM product_facts WHERE product_id=? AND field=? "
            "AND origin!='ai_copy' ORDER BY verified DESC, "
            "CASE origin WHEN 'verified' THEN 0 WHEN 'manufacturer' THEN 1 ELSE 2 END LIMIT 1",
            (product_id, field),
        ).fetchone()
        return json.loads(row["value"]) if row else None
