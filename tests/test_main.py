import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

import unittest
from fastapi.testclient import TestClient
from main import app

class TestMarketSimulation(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_create_shareholder(self):
        response = self.client.post("/shareholders", params={"name": "John Doe", "initial_cash": 10000})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["name"], "John Doe")
        self.assertEqual(data["cash"], 10000)

    def test_create_company(self):
        # First, create a shareholder to be the founder
        shareholder_response = self.client.post("/shareholders", params={"name": "Founder", "initial_cash": 1000000})
        founder_id = shareholder_response.json()["id"]

        response = self.client.post("/companies", params={
            "name": "Test Corp",
            "initial_stock_price": 100,
            "initial_shares": 1000,
            "founder_id": founder_id
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["name"], "Test Corp")
        self.assertEqual(data["stock_price"], 100)
        self.assertEqual(data["outstanding_shares"], 1000)

    def test_create_limit_order(self):
        # Create a shareholder and a company first
        shareholder_response = self.client.post("/shareholders", params={"name": "Trader", "initial_cash": 10000})
        shareholder_id = shareholder_response.json()["id"]
        
        company_response = self.client.post("/companies", params={
            "name": "Order Corp",
            "initial_stock_price": 50,
            "initial_shares": 1000,
            "founder_id": shareholder_id
        })
        company_id = company_response.json()["id"]

        response = self.client.post("/orders", params={
            "shareholder_id": shareholder_id,
            "company_id": company_id,
            "order_type": "buy",
            "order_subtype": "limit",
            "shares": 10,
            "price": 55
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["order_type"], "buy")
        self.assertEqual(data["order_subtype"], "limit")
        self.assertEqual(data["shares"], 10)
        self.assertEqual(data["price"], 55)

if __name__ == '__main__':
    unittest.main()