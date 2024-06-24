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

    def test_market_order_execution(self):
        # Create Djordje with 10k in cash
        djordje_response = self.client.post("/shareholders", params={"name": "Djordje", "initial_cash": 10000})
        djordje_id = djordje_response.json()["id"]
        self.assertEqual(djordje_response.status_code, 200)

        # Create Sara with 0 in cash
        sara_response = self.client.post("/shareholders", params={"name": "Sara", "initial_cash": 0})
        sara_id = sara_response.json()["id"]
        self.assertEqual(sara_response.status_code, 200)

        # Create company_sara with 200 shares and 100 price
        company_response = self.client.post("/companies", params={
            "name": "Sara Corp",
            "initial_stock_price": 100,
            "initial_shares": 200,
            "founder_id": sara_id
        })
        company_id = company_response.json()["id"]
        self.assertEqual(company_response.status_code, 200)

        # Sara makes sell order 100 shares at 120
        sell_order_response = self.client.post("/orders", params={
            "shareholder_id": sara_id,
            "company_id": company_id,
            "order_type": "sell",
            "order_subtype": "limit",
            "shares": 100,
            "price": 120
        })
        self.assertEqual(sell_order_response.status_code, 200)

        # Djordje makes market buy at 100 shares (should fail)
        failed_market_order_response = self.client.post("/orders", params={
            "shareholder_id": djordje_id,
            "company_id": company_id,
            "order_type": "buy",
            "order_subtype": "market",
            "shares": 100
        })
        self.assertEqual(failed_market_order_response.status_code, 400)
        self.assertIn("Insufficient funds", failed_market_order_response.json()["detail"])

        # Calculate how many shares Djordje can afford
        affordable_shares = 10000 // 120  # 83 shares

        # Djordje makes market buy for affordable shares
        successful_market_order_response = self.client.post("/orders", params={
            "shareholder_id": djordje_id,
            "company_id": company_id,
            "order_type": "buy",
            "order_subtype": "market",
            "shares": affordable_shares
        })
        self.assertEqual(successful_market_order_response.status_code, 200)
        
        # Check if the order is executed
        order_result = successful_market_order_response.json()
        self.assertEqual(order_result["message"], f"Market order executed: {affordable_shares}/{affordable_shares} shares")
        self.assertIsNone(order_result["remaining_order"])

        # Check the order book
        order_book_response = self.client.get(f"/order_book/{company_id}")
        order_book = order_book_response.json()
        
        # Check if there's a remaining sell order for Sara
        remaining_shares = 100 - affordable_shares
        self.assertEqual(len(order_book["sell"]), 1)
        self.assertEqual(order_book["sell"][0]["shares"], remaining_shares)
        self.assertEqual(order_book["sell"][0]["price"], 120)

        # Check Djordje's portfolio
        djordje_portfolio_response = self.client.get(f"/portfolios/{djordje_id}")
        djordje_portfolio = djordje_portfolio_response.json()
        self.assertEqual(djordje_portfolio["holdings"].get(company_id, 0), affordable_shares)

        # Check Sara's portfolio
        sara_portfolio_response = self.client.get(f"/portfolios/{sara_id}")
        sara_portfolio = sara_portfolio_response.json()
        self.assertEqual(sara_portfolio["holdings"].get(company_id, 0), 200 - affordable_shares)

        # Check Djordje's remaining cash
        djordje_response = self.client.get(f"/shareholders/{djordje_id}")
        djordje_data = djordje_response.json()
        self.assertAlmostEqual(djordje_data["cash"], 10000 - (affordable_shares * 120), places=2)

        # Check Sara's cash
        sara_response = self.client.get(f"/shareholders/{sara_id}")
        sara_data = sara_response.json()
        self.assertAlmostEqual(sara_data["cash"], affordable_shares * 120, places=2)

if __name__ == '__main__':
    unittest.main()