from __future__ import annotations
from .commerce_db import CommerceDatabase
from .orders import OrderStore


class GroundedOrderService:
    def __init__(self,db:CommerceDatabase,orders:OrderStore): self.db=db; self.orders=orders
    def create(self,customer_id,product_id,quantity=1,channel="",campaign_id=""):
        price=self.db.grounded_value(product_id,"selling_price")
        currency=self.db.grounded_value(product_id,"currency")
        availability=self.db.grounded_value(product_id,"availability")
        stock=self.db.grounded_value(product_id,"stock_quantity")
        if price is None or not currency: raise ValueError("Verified price and currency required")
        if availability and str(availability).lower() in {"unavailable","out_of_stock","نفذ"}: raise ValueError("Product unavailable")
        if stock is not None and int(stock)<int(quantity): raise ValueError("Insufficient stock")
        return self.orders.create(customer_id,product_id,quantity,price,currency,channel,campaign_id)
