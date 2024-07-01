# Deeponomics

## Personal Stock Market Simulation Project

Deeponomics is an ambitious, personal project aimed at creating a sophisticated and realistic stock market simulation. This project serves as a platform for learning, experimentation, and pushing the boundaries of what's possible in financial market simulation.

### Project Vision

The long-term vision for Deeponomics is to create the most comprehensive and realistic economic simulation possible, including:

- Complex market dynamics with multiple asset classes
- Diverse market participants (individual traders, hedge funds, market makers)
- Sophisticated trading mechanisms (dark pools, high-frequency trading)
- Comprehensive economic modeling (central banks, interest rates, inflation)
- Global market interactions and geopolitical influences

### Current State

As of now, Deeponomics has completed the following major components:

1. Basic market structure with companies and shareholders
2. Simple trading mechanisms and order matching
3. Fundamental company simulation with basic financial statements
4. GUI with market data display, trading interface, and portfolio view
5. CEO dashboard for basic company management

### Tech Stack

- Backend: Python with FastAPI
- Frontend: PySide6 (Qt for Python)
- Database: SQLite (with SQLAlchemy ORM)
- Additional libraries: (list any other significant libraries you're using)

### Project Structure

deeponomics/
├── src/
│ ├── main.py
│ ├── models.py
│ ├── crud.py
│ ├── schemas.py
│ ├── database.py
│ └── gui/
│ ├── main_window.py
│ ├── market_data_widget.py
│ ├── trading_widget.py
│ ├── portfolio_widget.py
│ ├── ceo_widget.py
│ └── financials_widget.py
├── tests/
├── requirements.txt
├── README.md
└── iterations.txt

### Setup and Running

1. Clone the repository:
2. Create and activate a virtual environment:
3. Install dependencies:
4. Run the application:

### Development Roadmap

Deeponomics is being developed in iterations. Here's an overview of completed and planned iterations:

#### Completed Iterations

1. Project Setup and Basic Structure
2. Single Transaction Simulation
3. Multiple Transactions and Order Book
4. Market Participants
5. Basic Market Simulation
6. Basic GUI
7. Enhanced Company Simulation

#### Current Iteration (8): Enhanced Market Dynamics

- [ ] Implement basic market sectors
- [ ] Create a simple news system
- [ ] Add support for stock splits and dividends
- [ ] Implement a basic market sentiment indicator

#### Upcoming Iterations

9. Improved Trader Simulation
10. Economic Factors
11. Advanced Order Types and Trading Mechanisms
12. Data Analysis and Reporting

For full details on iterations, see `iterations.txt`.

### Current Focus

The current focus is on completing Iteration 8, which involves enhancing market dynamics to create a more realistic and engaging simulation.

### Personal Notes

- Idea: Implement a simple AI trader for testing market dynamics
- Research: Look into financial modeling techniques for more accurate company simulations
- TODO: Refactor order matching algorithm for better performance

### Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [PySide6 Documentation](https://doc.qt.io/qtforpython-6/)
- "Algorithmic Trading with Python" by Chris Conlan
- [Investopedia](https://www.investopedia.com/) for financial concepts and terminology

### Disclaimer

This project is for personal use and learning purposes only. It is not intended for real trading or financial advice.

---

Last Updated: 2024-07-01
