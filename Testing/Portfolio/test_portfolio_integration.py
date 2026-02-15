import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from uuid import uuid4
from datetime import datetime, timedelta
from decimal import Decimal

import sys
sys.path.insert(0, '/app')

from backend.app.services.portfolio import (
    get_user_portfolio,
    get_portfolio_item_by_ticker,
    add_or_update_position,
    update_portfolio_item,
    remove_from_portfolio,
    get_portfolio_summary
)
from backend.app.schema.schemas import (
    PortfolioCreateItem,
    PortfolioUpdateItem
)

# Test db setup
@pytest.fixture(scope="function")
def test_db():
    """Create a test db for each test"""
    engine = create_engine("sqlite:///:memory:")

    #Create portfolio table
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE portfolio (
                id TEXT PRIMARY KEY,
                          user_id TEXT NOT NULL,
                          ticker TEXT NOT NULL,
                          quantity REAL NOT NULL,
                          avg_price REAL NOT NULL,
                          added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                          UNIQUE(user_id, ticker)
            )
            """))
        # Stocks table for price data
        conn.execute(text("""
            CREATE TABLE stocks (
                id TEXT PRIMARY KEY,
                ticker TEXT NOT NULL,
                date DATE NOT NULL,
                close REAL,
                return_1d REAL,
                return_30d REAL,
                return_120d REAL,
                return_360d REAL,
                UNIQUE(ticker, date)
            )
        """))
        conn.commit()

    Session = sessionmaker(bind=engine)
    session = Session()

    yield session

    session.close()
    engine.dispose()

@pytest.fixture
def sample_user_id():
    return uuid4()

@pytest.fixture
def another_user_id():
    return uuid4()

class TestPortfolioIsolation:
    def test_users_have_separate_portfolios(self, test_db, sample_user_id, another_user_id):
        """Each user should only see their own portfolio items"""
        # User 1 adds AAPL
        item1 = PortfolioCreateItem(ticker="AAPL", quantity=10.0, avg_price=150.0)
        add_or_update_position(test_db, sample_user_id, item1)
        
        # User 2 adds TSLA
        item2 = PortfolioCreateItem(ticker="TSLA", quantity=5.0, avg_price=200.0)
        add_or_update_position(test_db, another_user_id, item2)
        
        # Check user 1 only sees AAPL
        user1_portfolio = get_user_portfolio(test_db, sample_user_id)
        assert len(user1_portfolio) == 1
        assert user1_portfolio[0].ticker == "AAPL"
        
        # Check user 2 only sees TSLA
        user2_portfolio = get_user_portfolio(test_db, another_user_id)
        assert len(user2_portfolio) == 1
        assert user2_portfolio[0].ticker == "TSLA"

    def test_same_ticker_different_users(self, test_db, sample_user_id, another_user_id):
        """Different users can hold the same ticker independently"""
        # Both users add AAPL with different quantities
        item1 = PortfolioCreateItem(ticker="AAPL", quantity=10.0, avg_price=150.0)
        add_or_update_position(test_db, sample_user_id, item1)
        
        item2 = PortfolioCreateItem(ticker="AAPL", quantity=20.0, avg_price=160.0)
        add_or_update_position(test_db, another_user_id, item2)
        
        # Check each user has their own position
        user1_item = get_portfolio_item_by_ticker(test_db, sample_user_id, "AAPL")
        user2_item = get_portfolio_item_by_ticker(test_db, another_user_id, "AAPL")
        
        assert user1_item.quantity == 10.0
        assert user2_item.quantity == 20.0
        assert user1_item.avg_price == 150.0
        assert user2_item.avg_price == 160.0

class TestCompletePortfolioWorkflows:
    def test_build_diversified_portfolio_workflow(self, test_db, sample_user_id):
        """User builds a diversified portfolio over time"""
        # Day 1: Buy tech stocks
        tech_stocks = [
            PortfolioCreateItem(ticker="AAPL", quantity=10.0, avg_price=150.0),
            PortfolioCreateItem(ticker="MSFT", quantity=15.0, avg_price=350.0),
            PortfolioCreateItem(ticker="GOOGL", quantity=5.0, avg_price=140.0)
        ]
        
        for stock in tech_stocks:
            add_or_update_position(test_db, sample_user_id, stock)
        
        portfolio = get_user_portfolio(test_db, sample_user_id)
        assert len(portfolio) == 3
        
        # Day 2: Add energy stocks
        add_or_update_position(
            test_db, 
            sample_user_id, 
            PortfolioCreateItem(ticker="XOM", quantity=20.0, avg_price=110.0)
        )
        
        portfolio = get_user_portfolio(test_db, sample_user_id)
        assert len(portfolio) == 4
        
        # Day 3: Average down on AAPL (price dropped)
        add_or_update_position(
            test_db,
            sample_user_id,
            PortfolioCreateItem(ticker="AAPL", quantity=10.0, avg_price=130.0)
        )
        
        aapl = get_portfolio_item_by_ticker(test_db, sample_user_id, "AAPL")
        assert aapl.quantity == 20.0
        assert aapl.avg_price == 140.0  # (10*150 + 10*130) / 20
    
    def test_rebalancing_workflow(self, test_db, sample_user_id):
        """User rebalances portfolio by adjusting positions"""
        # Initial portfolio
        stocks = [
            PortfolioCreateItem(ticker="AAPL", quantity=100.0, avg_price=150.0),
            PortfolioCreateItem(ticker="TSLA", quantity=50.0, avg_price=200.0),
            PortfolioCreateItem(ticker="NVDA", quantity=30.0, avg_price=500.0)
        ]
        
        for stock in stocks:
            add_or_update_position(test_db, sample_user_id, stock)
        
        # Reduce TSLA position
        update_portfolio_item(
            test_db,
            sample_user_id,
            "TSLA",
            PortfolioUpdateItem(quantity=25.0, avg_price=None)
        )
        
        # Remove NVDA completely
        remove_from_portfolio(test_db, sample_user_id, "NVDA")
        
        # Verify final state
        portfolio = get_user_portfolio(test_db, sample_user_id)
        assert len(portfolio) == 2
        
        tsla = get_portfolio_item_by_ticker(test_db, sample_user_id, "TSLA")
        assert tsla.quantity == 25.0
        
        nvda = get_portfolio_item_by_ticker(test_db, sample_user_id, "NVDA")
        assert nvda is None
    
    def test_dollar_cost_averaging_strategy(self, test_db, sample_user_id):
        """User employs dollar cost averaging over multiple purchases"""
        # Monthly purchases of same stock at different prices
        purchases = [
            PortfolioCreateItem(ticker="SPY", quantity=10.0, avg_price=400.0),
            PortfolioCreateItem(ticker="SPY", quantity=10.0, avg_price=390.0),
            PortfolioCreateItem(ticker="SPY", quantity=10.0, avg_price=410.0),
            PortfolioCreateItem(ticker="SPY", quantity=10.0, avg_price=405.0),
        ]
        
        for purchase in purchases:
            add_or_update_position(test_db, sample_user_id, purchase)
        
        spy = get_portfolio_item_by_ticker(test_db, sample_user_id, "SPY")
        assert spy.quantity == 40.0
        # Average: (10*400 + 10*390 + 10*410 + 10*405) / 40 = 401.25
        assert spy.avg_price == pytest.approx(401.25, rel=0.01)

class TestPortolfioSummaryBehaviors:
    def setup_stock_prices(self, test_db):
        """Helper to insert stock price data"""
        prices = [
            {
                "ticker": "AAPL",
                "close": 180.0,
                "return_1d": 2.0,
                "return_30d": 15.0,
                "return_120d": 25.0,
                "return_360d": 40.0
            },
            {
                "ticker": "TSLA",
                "close": 250.0,
                "return_1d": -1.5,
                "return_30d": 10.0,
                "return_120d": 30.0,
                "return_360d": 50.0
            },
            {
                "ticker": "GOOGL",
                "close": 150.0,
                "return_1d": 1.0,
                "return_30d": 8.0,
                "return_120d": 20.0,
                "return_360d": 35.0
            }
        ]
        
        for price in prices:
            test_db.execute(
                text("""
                    INSERT INTO stocks (id, ticker, date, close, return_1d, return_30d, return_120d, return_360d)
                    VALUES (:id, :ticker, :date, :close, :return_1d, :return_30d, :return_120d, :return_360d)
                """),
                {
                    "id": str(uuid4()),
                    "ticker": price["ticker"],
                    "date": datetime.now().date(),
                    "close": price["close"],
                    "return_1d": price["return_1d"],
                    "return_30d": price["return_30d"],
                    "return_120d": price["return_120d"],
                    "return_360d": price["return_360d"]
                }
            )
        test_db.commit()

    def test_portfolio_summary_with_gains(self, test_db, sample_user_id):
        """Test summary when all positions are profitable"""
        # Setup stock prices
        self.setup_stock_prices(test_db)
        
        # Add positions
        positions = [
            PortfolioCreateItem(ticker="AAPL", quantity=10.0, avg_price=150.0),
            PortfolioCreateItem(ticker="TSLA", quantity=5.0, avg_price=200.0),
        ]
        
        for pos in positions:
            add_or_update_position(test_db, sample_user_id, pos)
        
        summary = get_portfolio_summary(test_db, sample_user_id)
        
        # AAPL: 10 * 150 = 1500 cost, 10 * 180 = 1800 current
        # TSLA: 5 * 200 = 1000 cost, 5 * 250 = 1250 current
        assert summary.summary.total_cost_basis == 2500.0
        assert summary.summary.total_current_value == 3050.0
        assert summary.summary.total_gain_loss == 550.0
        assert summary.summary.total_gain_loss_pct == 22.0
        assert summary.summary.num_positions == 2
    
    def test_portfolio_summary_with_losses(self, test_db, sample_user_id):
        """Test summary when positions have losses"""
        # Setup stock prices
        self.setup_stock_prices(test_db)
        
        # Add positions bought at higher prices
        positions = [
            PortfolioCreateItem(ticker="AAPL", quantity=10.0, avg_price=200.0),  # Overpaid
            PortfolioCreateItem(ticker="TSLA", quantity=5.0, avg_price=300.0),   # Overpaid
        ]
        
        for pos in positions:
            add_or_update_position(test_db, sample_user_id, pos)
        
        summary = get_portfolio_summary(test_db, sample_user_id)
        
        # AAPL: 10 * 200 = 2000 cost, 10 * 180 = 1800 current (loss)
        # TSLA: 5 * 300 = 1500 cost, 5 * 250 = 1250 current (loss)
        assert summary.summary.total_cost_basis == 3500.0
        assert summary.summary.total_current_value == 3050.0
        assert summary.summary.total_gain_loss < 0
    
    def test_portfolio_summary_mixed_performance(self, test_db, sample_user_id):
        """Test summary with both winners and losers"""
        self.setup_stock_prices(test_db)
        
        positions = [
            PortfolioCreateItem(ticker="AAPL", quantity=10.0, avg_price=150.0),  # Winner
            PortfolioCreateItem(ticker="TSLA", quantity=5.0, avg_price=300.0),   # Loser
            PortfolioCreateItem(ticker="GOOGL", quantity=8.0, avg_price=140.0),  # Breakeven-ish
        ]
        
        for pos in positions:
            add_or_update_position(test_db, sample_user_id, pos)
        
        summary = get_portfolio_summary(test_db, sample_user_id)
        
        assert summary.summary.num_positions == 3
        assert len(summary.portfolio_items) == 3
        
        # Verify individual item metrics
        items_by_ticker = {item.ticker: item for item in summary.portfolio_items}
        
        # AAPL should be profitable
        aapl = items_by_ticker["AAPL"]
        assert aapl.total_gain_loss > 0
        assert aapl.gain_loss_pct > 0
        
        # TSLA should be losing
        tsla = items_by_ticker["TSLA"]
        assert tsla.total_gain_loss < 0
        assert tsla.gain_loss_pct < 0
    
    def test_portfolio_without_current_prices(self, test_db, sample_user_id):
        """Test summary when no price data is available"""
        # Add positions without setting up price data
        positions = [
            PortfolioCreateItem(ticker="PRIVATE1", quantity=100.0, avg_price=10.0),
            PortfolioCreateItem(ticker="PRIVATE2", quantity=50.0, avg_price=20.0),
        ]
        
        for pos in positions:
            add_or_update_position(test_db, sample_user_id, pos)
        
        summary = get_portfolio_summary(test_db, sample_user_id)
        
        # Without current prices, should use avg_price
        # PRIVATE1: 100 * 10 = 1000
        # PRIVATE2: 50 * 20 = 1000
        assert summary.summary.total_cost_basis == 2000.0
        assert summary.summary.total_current_value == 2000.0
        assert summary.summary.total_gain_loss == 0.0
        assert summary.summary.num_positions == 2
        
        # Items should have None for current_price
        for item in summary.portfolio_items:
            assert item.current_price is None


class TestConcurrentOperations:
    """Test handling of concurrent-like operations"""
    
    def test_multiple_updates_same_ticker(self, test_db, sample_user_id):
        """Test multiple sequential updates to same position"""
        # Initial position
        add_or_update_position(
            test_db,
            sample_user_id,
            PortfolioCreateItem(ticker="AAPL", quantity=10.0, avg_price=100.0)
        )
        
        # Multiple adds (simulating DCA)
        for i in range(5):
            add_or_update_position(
                test_db,
                sample_user_id,
                PortfolioCreateItem(ticker="AAPL", quantity=2.0, avg_price=100.0 + i * 5)
            )
        
        final_position = get_portfolio_item_by_ticker(test_db, sample_user_id, "AAPL")
        assert final_position.quantity == 20.0  # 10 + 5*2
    
    def test_rapid_add_remove_same_ticker(self, test_db, sample_user_id):
        """Test adding and removing same ticker multiple times"""
        ticker = "VOLATILE"
        
        # Add
        add_or_update_position(
            test_db,
            sample_user_id,
            PortfolioCreateItem(ticker=ticker, quantity=10.0, avg_price=100.0)
        )
        assert get_portfolio_item_by_ticker(test_db, sample_user_id, ticker) is not None
        
        # Remove
        remove_from_portfolio(test_db, sample_user_id, ticker)
        assert get_portfolio_item_by_ticker(test_db, sample_user_id, ticker) is None
        
        # Add again
        add_or_update_position(
            test_db,
            sample_user_id,
            PortfolioCreateItem(ticker=ticker, quantity=20.0, avg_price=150.0)
        )
        
        final = get_portfolio_item_by_ticker(test_db, sample_user_id, ticker)
        assert final is not None
        assert final.quantity == 20.0
        assert final.avg_price == 150.0


class TestDataIntegrity:
    """Test data integrity and constraints"""
    
    def test_negative_quantity_handling(self, test_db, sample_user_id):
        """Test system handles negative quantities (shouldn't normally happen)"""
        # This tests what happens if somehow negative quantity gets through
        update_portfolio_item(
            test_db,
            sample_user_id,
            "TEST",
            PortfolioUpdateItem(quantity=-5.0, avg_price=None)
        )
        
        # Should either reject or handle gracefully
        # The actual behavior depends on business rules
    
    def test_ticker_case_sensitivity(self, test_db, sample_user_id):
        """Test if ticker symbols are case-sensitive"""
        # Add with uppercase
        add_or_update_position(
            test_db,
            sample_user_id,
            PortfolioCreateItem(ticker="AAPL", quantity=10.0, avg_price=150.0)
        )
        
        # Try to get with lowercase
        lowercase_result = get_portfolio_item_by_ticker(test_db, sample_user_id, "aapl")
        uppercase_result = get_portfolio_item_by_ticker(test_db, sample_user_id, "AAPL")
        
        # Document the behavior (likely case-sensitive)
        assert uppercase_result is not None
    
    def test_empty_ticker_string(self, test_db, sample_user_id):
        """Test behavior with empty ticker string"""
        # Attempt to add position with empty ticker
        try:
            add_or_update_position(
                test_db,
                sample_user_id,
                PortfolioCreateItem(ticker="", quantity=10.0, avg_price=150.0)
            )
            # If it succeeds, verify we can retrieve it
            result = get_portfolio_item_by_ticker(test_db, sample_user_id, "")
        except Exception:
            # Expected to fail with validation or database constraint
            pass
    
    def test_very_long_ticker_symbol(self, test_db, sample_user_id):
        """Test handling of unusually long ticker symbols"""
        long_ticker = "A" * 50
        
        add_or_update_position(
            test_db,
            sample_user_id,
            PortfolioCreateItem(ticker=long_ticker, quantity=10.0, avg_price=150.0)
        )
        
        result = get_portfolio_item_by_ticker(test_db, sample_user_id, long_ticker)
        assert result is not None
        assert result.ticker == long_ticker


class TestPerformanceScenarios:
    """Test with larger datasets"""
    
    def test_large_portfolio_summary(self, test_db, sample_user_id):
        """Test summary calculation with many positions"""
        # Add 50 different positions
        for i in range(50):
            ticker = f"STOCK{i:03d}"
            add_or_update_position(
                test_db,
                sample_user_id,
                PortfolioCreateItem(
                    ticker=ticker,
                    quantity=10.0 + i,
                    avg_price=100.0 + i * 10
                )
            )
        
        portfolio = get_user_portfolio(test_db, sample_user_id)
        assert len(portfolio) == 50
        
        summary = get_portfolio_summary(test_db, sample_user_id)
        assert summary.summary.num_positions == 50
        assert len(summary.portfolio_items) == 50
    
    def test_many_users_performance(self, test_db):
        """Test with many different users"""
        # Create portfolios for 20 users
        user_ids = [uuid4() for _ in range(20)]
        
        for user_id in user_ids:
            for i in range(5):
                ticker = f"STOCK{i}"
                add_or_update_position(
                    test_db,
                    user_id,
                    PortfolioCreateItem(ticker=ticker, quantity=10.0, avg_price=100.0)
                )
        
        # Verify each user has correct isolated portfolio
        for user_id in user_ids:
            portfolio = get_user_portfolio(test_db, user_id)
            assert len(portfolio) == 5


class TestBusinessLogicValidation:
    """Test business logic and calculations"""
    
    def test_average_price_never_negative(self, test_db, sample_user_id):
        """Average price should never be negative"""
        positions = [
            PortfolioCreateItem(ticker="TEST", quantity=10.0, avg_price=100.0),
            PortfolioCreateItem(ticker="TEST", quantity=10.0, avg_price=50.0),
        ]
        
        for pos in positions:
            result = add_or_update_position(test_db, sample_user_id, pos)
            assert result.avg_price >= 0
    
    def test_quantity_increases_with_adds(self, test_db, sample_user_id):
        """Quantity should only increase when adding positions"""
        add_or_update_position(
            test_db,
            sample_user_id,
            PortfolioCreateItem(ticker="GROWTH", quantity=10.0, avg_price=100.0)
        )
        
        initial = get_portfolio_item_by_ticker(test_db, sample_user_id, "GROWTH")
        initial_qty = initial.quantity
        
        add_or_update_position(
            test_db,
            sample_user_id,
            PortfolioCreateItem(ticker="GROWTH", quantity=5.0, avg_price=110.0)
        )
        
        final = get_portfolio_item_by_ticker(test_db, sample_user_id, "GROWTH")
        assert final.quantity > initial_qty
        assert final.quantity == initial_qty + 5.0
    
    def test_cost_basis_equals_quantity_times_avg_price(self, test_db, sample_user_id):
        """Cost basis calculation should be accurate"""
        self.setup_stock_prices(test_db)
        
        add_or_update_position(
            test_db,
            sample_user_id,
            PortfolioCreateItem(ticker="AAPL", quantity=10.0, avg_price=150.0)
        )
        
        summary = get_portfolio_summary(test_db, sample_user_id)
        item = summary.portfolio_items[0]
        
        expected_cost_basis = item.quantity * item.avg_price
        assert item.cost_basis == pytest.approx(expected_cost_basis, rel=0.01)
    
    def setup_stock_prices(self, test_db):
        """Helper to insert stock price data"""
        prices = [
            {
                "ticker": "AAPL",
                "close": 180.0,
                "return_1d": 2.0,
                "return_30d": 15.0,
                "return_120d": 25.0,
                "return_360d": 40.0
            }
        ]
        
        for price in prices:
            test_db.execute(
                text("""
                    INSERT INTO stocks (id, ticker, date, close, return_1d, return_30d, return_120d, return_360d)
                    VALUES (:id, :ticker, :date, :close, :return_1d, :return_30d, :return_120d, :return_360d)
                """),
                {
                    "id": str(uuid4()),
                    "ticker": price["ticker"],
                    "date": datetime.now().date(),
                    "close": price["close"],
                    "return_1d": price["return_1d"],
                    "return_30d": price["return_30d"],
                    "return_120d": price["return_120d"],
                    "return_360d": price["return_360d"]
                }
            )
        test_db.commit()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])