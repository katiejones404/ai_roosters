import pytest
from unittest.mock import Mock, MagicMock, patch
from decimal import Decimal
from uuid import UUID, uuid4
from datetime import datetime

import sys
sys.path.insert(0, '/app')

from app.services.portfolio import (
    get_user_portfolio,
    get_portfolio_item_by_ticker,
    add_or_update_position,
    update_portfolio_item,
    remove_from_portfolio,
    get_portfolio_summary
)
from app.schema.schemas import (
    PortfolioCreateItem,
    PortfolioUpdateItem
)

class TestGetUserPortfolio:
    """Test cases for get_user_portfolio function"""
    def test_get_portfolio_retruns_empty_for_no_positions(self):
        mock_db = Mock()
        mock_db.execute.return_value.fetchall.return_value = []
        user_id = uuid4()

        result = get_user_portfolio(mock_db, user_id)
        assert result == []
        assert isinstance(result, list)

    def test_get_portfolio_returns_single_item(self):
        mock_db = Mock()
        test_id = uuid4()
        user_id = uuid4()
        test_date = datetime(2026, 1, 15, 10, 30, 0)

        mock_db.execute.return_value.fetchall.return_value = [
            {
                "id": test_id,
                "user_id": user_id,
                "ticker": "APPL",
                "quantity": Decimal("10.0"),
                "avg_price": Decimal("150.50"),
                "added_at": test_date 
            }
        ]
        result = get_user_portfolio(mock_db, user_id)
        assert len(result) == 1
        assert result[0].ticker == "APPL"
        assert result[0].quantity == 10.0
        assert result[0].avg_price == 150.50

def test_get_portfolio_returns_multiple_items_by_date(self):
    mock_db = Mock()
    user_id = uuid4()

    mock_db.execute.return_value.fetchall.return_value = [
            {
                "id": uuid4(),
                "user_id": user_id,
                "ticker": "TSLA",
                "quantity": Decimal("5.0"),
                "avg_price": Decimal("200.00"),
                "added_at": datetime(2025, 1, 20)
            },
            {
                "id": uuid4(),
                "user_id": user_id,
                "ticker": "AAPL",
                "quantity": Decimal("10.0"),
                "avg_price": Decimal("150.50"),
                "added_at": datetime(2025, 1, 15)
            }
        ]
    result = get_user_portfolio(mock_db, user_id)
    assert len(result) == 2
    assert result[0].ticker == "TSLA"
    assert result[1].ticker == "APPL"

    def test_get_portfolio_handles_null_added_at(self):
        mock_db = Mock()
        user_id = uuid4()

        mock_db.execute.return_value.fetchall.return_value = [
                {
                    "id": uuid4(),
                    "user_id": user_id,
                    "ticker": "GOOGL",
                    "quantity": Decimal("3.0"),
                    "avg_price": Decimal("100.00"),
                    "added_at": None
                }
        ]
        result = get_user_portfolio(mock_db, user_id)
        assert len(result) == 1
        assert result[0].added_at is None

    def test_get_portfolio_converts_dec_to_float(self):
        mock_db = Mock()
        user_id = uuid4()

        mock_db.execute.return_value.fetchall.return_value = [
                {
                    "id": uuid4(),
                    "user_id": user_id,
                    "ticker": "TSLA",
                    "quantity": Decimal("5.0"),
                    "avg_price": Decimal("200.00"),
                    "added_at": datetime.now()
                }
        ]
        result = get_user_portfolio(mock_db, user_id)
        assert isinstance(result[0].quantity, float)
        assert isinstance(result[0].avg_price, float)
        assert result[0].quantity == 5.0
        assert result[0].avg_price == 200.00

class TestGetPortfolioItemByTicker:
    """Test cases for get_portfolio_item_by_ticker funciton"""
    def test_return_none_when_ticker_not_found(self):
        mock_db = Mock()
        mock_db.execute.return_value.fetchone.return_value = None
        user_id = uuid4()

        result = get_portfolio_item_by_ticker(mock_db, user_id, "NOTFOUND")
        assert result is None

    def test_returns_portfolio_item_when_found(self):
        mock_db = Mock()
        user_id = uuid4()
        test_id = uuid4()

        mock_db.execute.return_value.fetchall.return_value = {
            "id": test_id,
            "user_id": user_id,
            "ticker": "NVDA",
            "quantity": Decimal("15.0"),
            "avg_price": Decimal("500.00"),
            "added_at": datetime(2025, 1, 10)
        }
        result = get_portfolio_item_by_ticker(mock_db, user_id, "NVDA")
        assert result is not None
        assert result.ticker == "NVDA"
        assert result.quantity == 15.0
        assert result.avg_price == 500.00

    def test_query_uses_correct_userid_and_ticker(self):
        mock_db = Mock()
        user_id = uuid4()
        ticker = "AMD"

        mock_db.execute.return_value.fetchone.return_value = None
        get_portfolio_item_by_ticker(mock_db, user_id, ticker)

        call_args = mock_db.execute.call_args
        assert call_args[0][1]["user_id"] == str(user_id)
        assert call_args[0][1]["ticker"] == ticker

class TestAndOrUpdatePosition:
    """Test cases for and_or_update_position function"""
    def test_add_new_position_with_no_ticker(self):
        mock_db = Mock()
        user_id = uuid4()
        new_id = uuid4()

        mock_result = Mock()
        mock_result.fetchone.side_effect = [
            None,
            {
                "id": new_id,
                "user_id": user_id,
                "ticker": "AMZN",
                "quantity": Decimal("5.0"),
                "avg_price": Decimal("180.00"),
                "added_at": datetime.now()
            }
        ]
        mock_db.execute.return_value = mock_result
        item = PortfolioCreateItem(ticker="AMZN", quantity=5.0, avg_price=180.00)
        
        result = add_or_update_position(mock_db, user_id, item)
        assert result.ticker == "AMZN"
        assert result.quantity == 5.0
        assert result.avg_price == 180.00
        mock_db.commit.assert_called_one()

    def test_updates_existing_position_with_avg_price(self):
        mock_db = Mock()
        user_id = uuid4()
        existing_id = uuid4()

        # Query returns existing position
        mock_result = Mock()
        mock_result.fetchone.side_effect = [
            {  # Existing position
                "id": existing_id,
                "quantity": Decimal("10.0"),
                "avg_price": Decimal("100.00")
            },
            {  # Update query result
                "id": existing_id,
                "user_id": user_id,
                "ticker": "AAPL",
                "quantity": Decimal("15.0"),
                "avg_price": Decimal("106.67"),  
                "added_at": datetime.now()
            }
        ]
        mock_db.execute.return_value = mock_result

        item = PortfolioCreateItem(ticker="AAPL", quantity=5.0, avg_price=120.00)
        result = add_or_update_position(mock_db, user_id, item)
        assert result.quantity == 15.0
        # New avg
        assert result.avg_price == pytest.approx(106.67, rel=0.01)

    def tet_averaging_up_increases_avg_price(self):
        mock_db = Mock()
        user_id = uuid4()
        existing_id = uuid4()
        
        mock_result = Mock()
        mock_result.fetchone.side_effect = [
            {"id": existing_id,
                "quantity": Decimal("100.0"),
                "avg_price": Decimal("50.00")
            },
            {
                "id": existing_id,
                "user_id": user_id,
                "ticker": "GME",
                "quantity": Decimal("150.0"),
                "avg_price": Decimal("83.33"),  # (100*50 + 50*150) / 150
                "added_at": datetime.now()
            }
        ]
        mock_db.execute.return_value = mock_result
        item = PortfolioCreateItem(ticker="GME", quantity=50.0, avg_price=150.00)
        result = add_or_update_position(mock_db, user_id, item)
        assert result.avg_price == pytest.approx(83.33, rel=0.01)

    def test_averaging_down_decreases_avg_price(self):
        mock_db = Mock()
        user_id = uuid4()
        existing_id = uuid4()
        
        mock_result = Mock()
        mock_result.fetchone.side_effect = [
            {
                "id": existing_id,
                "quantity": Decimal("50.0"),
                "avg_price": Decimal("200.00")
            },
            {
                "id": existing_id,
                "user_id": user_id,
                "ticker": "TSLA",
                "quantity": Decimal("100.0"),
                "avg_price": Decimal("150.0"),  # (50*200 + 50*100) / 100
                "added_at": datetime.now()
            }
        ]
        mock_db.execute.return_value = mock_result
        item = PortfolioCreateItem(ticker="TSLA", quantity=50.0, avg_price=100.00)
        result = add_or_update_position(mock_db, user_id, item)
        assert result.avg_price == 150.0

class TestUpdatePortfolioItem:
    """Test cases for update_portfolio_item function"""
    def test_update_quantity(self):
        mock_db = Mock()
        user_id = uuid4()
        
        mock_db.execute.return_value.fetchone.return_value = {
            "id": uuid4(),
            "user_id": user_id,
            "ticker": "META",
            "quantity": Decimal("20.0"),
            "avg_price": Decimal("350.00"),
            "added_at": datetime.now()
        }
        update_item = PortfolioUpdateItem(quantity=20.0, avg_price=None)
        result = update_portfolio_item(mock_db, user_id, "META", update_item)
        
        assert result is not None
        assert result.quantity == 20.0
        mock_db.commit.assert_called_once()

    def test_update_avg_price(self):
        mock_db = Mock()
        user_id = uuid4()
        
        mock_db.execute.return_value.fetchone.return_value = {
            "id": uuid4(),
            "user_id": user_id,
            "ticker": "NFLX",
            "quantity": Decimal("10.0"),
            "avg_price": Decimal("400.00"),
            "added_at": datetime.now()
        }
        update_item = PortfolioUpdateItem(quantity=None, avg_price=400.00)
        result = update_portfolio_item(mock_db, user_id, "NFLX", update_item)
        
        assert result is not None
        assert result.avg_price == 400.00

    def test_update_quantity_and_avg_price(self):
        mock_db = Mock()
        user_id = uuid4()
        
        mock_db.execute.return_value.fetchone.return_value = {
            "id": uuid4(),
            "user_id": user_id,
            "ticker": "GOOG",
            "quantity": Decimal("8.0"),
            "avg_price": Decimal("140.00"),
            "added_at": datetime.now()
        }
        update_item = PortfolioUpdateItem(quantity=8.0, avg_price=140.00)
        result = update_portfolio_item(mock_db, user_id, "GOOG", update_item)
        
        assert result is not None
        assert result.quantity == 8.0
        assert result.avg_price == 140.00

    def test_returns_none_when_ticker_not_found(self):
        mock_db = Mock()
        mock_db.execute.return_value.fetchone.return_value = None
        user_id = uuid4()
        
        update_item = PortfolioUpdateItem(quantity=5.0, avg_price=None)
        result = update_portfolio_item(mock_db, user_id, "NOTFOUND", update_item)
        assert result is None

class TestRemoveFromPortfolio:
    """Test cases for remove_from_portfolio function"""
    def test_returns_true_when_item_deleted(self):
        mock_db = Mock()
        mock_result = Mock()
        mock_result.rowcount = 1
        mock_db.execute.return_value = mock_result
        user_id = uuid4()
        
        result = remove_from_portfolio(mock_db, user_id, "AAPL")
        assert result is True
        mock_db.commit.assert_called_once()

    def test_returns_false_when_item_not_found(self):
        mock_db = Mock()
        mock_result = Mock()
        mock_result.rowcount = 0
        mock_db.execute.return_value = mock_result
        user_id = uuid4()
        
        result = remove_from_portfolio(mock_db, user_id, "NOTFOUND")
        assert result is False
        mock_db.commit.assert_called_once()

    def test_calls_delete_with_correct_params(self):
        mock_db = Mock()
        mock_result = Mock()
        mock_result.rowcount = 1
        mock_db.execute.return_value = mock_result
        user_id = uuid4()
        ticker = "TSLA"
        
        remove_from_portfolio(mock_db, user_id, ticker)
        call_args = mock_db.execute.call_args
        assert call_args[0][1]["user_id"] == str(user_id)
        assert call_args[0][1]["ticker"] == ticker

class TestGetPortfolioSUmmary:
    """Test cases for get_portfolio_summary function"""
    def test_empty_portfolio_returns_none(self):
        mock_db = Mock()
        mock_db.execute.return_value.fetchall.return_value = []
        user_id = uuid4()
        result = get_portfolio_summary(mock_db, user_id)

        assert result.summary.total_cost_basis == 0.0
        assert result.summary.total_current_value == 0.0
        assert result.summary.total_gain_loss == 0.0
        assert result.summary.total_gain_loss_pct == 0.0
        assert result.summary.num_positions == 0
        assert len(result.portfolio_items) == 0

    def test_single_position_with_current_price(self):
        mock_db = Mock()
        user_id = uuid4()

        mock_db.execute.return_value.fetchall.return_value = [
            {
                "id": uuid4(),
                "ticker": "AAPL",
                "quantity": Decimal("10.0"),
                "avg_price": Decimal("150.00"),
                "current_price": Decimal("180.00"),
                "cost_basis": Decimal("1500.00"),
                "current_value": Decimal("1800.00"),
                "total_gain_loss": Decimal("300.00"),
                "gain_loss_pct": Decimal("20.00"),
                "return_1d": Decimal("1.5"),
                "return_30d": Decimal("10.0"),
                "return_120d": Decimal("25.0"),
                "return_360d": Decimal("50.0"),
                "price_date": datetime.now(),
                "added_at": datetime.now()
            }
        ]
        result = get_portfolio_summary(mock_db, user_id)

        assert result.summary.total_cost_basis == 1500.00
        assert result.summary.total_current_value == 1800.00
        assert result.summary.total_gain_loss == 300.00
        assert result.summary.total_gain_loss_pct == 20.00
        assert result.summary.num_positions == 1
        assert len(result.portfolio_items) == 1

    def test_multiple_positions_aggregates_correctly(self):
        mock_db = Mock()
        user_id = uuid4()

        mock_db.execute.return_value.fetchall.return_value = [
            {
                "id": uuid4(),
                "ticker": "AAPL",
                "quantity": Decimal("10.0"),
                "avg_price": Decimal("150.00"),
                "current_price": Decimal("180.00"),
                "cost_basis": Decimal("1500.00"),
                "current_value": Decimal("1800.00"),
                "total_gain_loss": Decimal("300.00"),
                "gain_loss_pct": Decimal("20.00"),
                "return_1d": Decimal("1.5"),
                "return_30d": Decimal("10.0"),
                "return_120d": Decimal("25.0"),
                "return_360d": Decimal("50.0"),
                "price_date": datetime.now(),
                "added_at": datetime.now()
            },
            {
                "id": uuid4(),
                "ticker": "TSLA",
                "quantity": Decimal("5.0"),
                "avg_price": Decimal("200.00"),
                "current_price": Decimal("250.00"),
                "cost_basis": Decimal("1000.00"),
                "current_value": Decimal("1250.00"),
                "total_gain_loss": Decimal("250.00"),
                "gain_loss_pct": Decimal("25.00"),
                "return_1d": Decimal("2.0"),
                "return_30d": Decimal("15.0"),
                "return_120d": Decimal("30.0"),
                "return_360d": Decimal("60.0"),
                "price_date": datetime.now(),
                "added_at": datetime.now()
            }
        ]
        result = get_portfolio_summary(mock_db, user_id)
        assert result.summary.total_cost_basis == 2500.00
        assert result.summary.total_current_value == 3050.00
        assert result.summary.total_gain_loss == 550.00
        assert result.summary.total_gain_loss_pct == 22.00
        assert result.summary.num_positions == 2
    
    def test_handles_null_current_price_using_avg_price(self):
        mock_db = Mock()
        user_id = uuid4()

        mock_db.execute.return_value.fetchall.return_value = [
            {
                "id": uuid4(),
                "ticker": "PRIVATE",
                "quantity": Decimal("100.0"),
                "avg_price": Decimal("10.00"),
                "current_price": None,
                "cost_basis": Decimal("1000.00"),
                "current_value": Decimal("1000.00"),  # Uses avg_price
                "total_gain_loss": Decimal("0.00"),
                "gain_loss_pct": Decimal("0.00"),
                "return_1d": None,
                "return_30d": None,
                "return_120d": None,
                "return_360d": None,
                "price_date": None,
                "added_at": datetime.now()
            }
        ] 
        result = get_portfolio_summary(mock_db, user_id)
        assert result.portfolio_items[0].current_price is None
        assert result.summary.total_current_value == 1000.00
        assert result.summary.total_gain_loss == 0.00

    def test_handles_negative_returns(self):
        mock_db = Mock()
        user_id = uuid4()

        mock_db.execute.return_value.fetchall.return_value = [
            {
                "id": uuid4(),
                "ticker": "LOSER",
                "quantity": Decimal("20.0"),
                "avg_price": Decimal("100.00"),
                "current_price": Decimal("50.00"),
                "cost_basis": Decimal("2000.00"),
                "current_value": Decimal("1000.00"),
                "total_gain_loss": Decimal("-1000.00"),
                "gain_loss_pct": Decimal("-50.00"),
                "return_1d": Decimal("-5.0"),
                "return_30d": Decimal("-30.0"),
                "return_120d": Decimal("-50.0"),
                "return_360d": Decimal("-60.0"),
                "price_date": datetime.now(),
                "added_at": datetime.now()
            }
        ]
        result = get_portfolio_summary(mock_db, user_id)
        assert result.summary.total_gain_loss == -1000.00
        assert result.summary.total_gain_loss_pct == -50.00
        assert result.portfolio_items[0].total_gain_loss == -1000.00

    def test_handles_none_return_values(self):
        mock_db = Mock()
        user_id = uuid4()

        mock_db.execute.return_value.fetchall.return_value = [
            {
                "id": uuid4(),
                "ticker": "NEWSTOCK",
                "quantity": Decimal("10.0"),
                "avg_price": Decimal("50.00"),
                "current_price": Decimal("55.00"),
                "cost_basis": Decimal("500.00"),
                "current_value": Decimal("550.00"),
                "total_gain_loss": Decimal("50.00"),
                "gain_loss_pct": Decimal("10.00"),
                "return_1d": None,
                "return_30d": None,
                "return_120d": None,
                "return_360d": None,
                "price_date": datetime.now(),
                "added_at": datetime.now()
            }
        ]
        result = get_portfolio_summary(mock_db, user_id)
        item = result.portfolio_items[0]
        assert item.return_1d is None
        assert item.return_30d is None
        assert item.return_120d is None
        assert item.return_360d is None

class TestEdgeCases:
    """Test edge cases and boundary conditions"""
    def test_fractional_shares_work(self):
        mock_db = Mock()
        user_id = uuid4()

        mock_result = Mock()
        mock_result.fetchone.side_effect = [
            None,
            {
                "id": uuid4(),
                "user_id": user_id,
                "ticker": "FRAC",
                "quantity": Decimal("2.5"),
                "avg_price": Decimal("100.00"),
                "added_at": datetime.now()
            }
        ]
        mock_db.execute.return_value = mock_result
        item = PortfolioCreateItem(ticker="FRAC", quantity=2.5, avg_price=100.00)
        result = add_or_update_position(mock_db, user_id, item)
        assert result.quantity == 2.5

    def test_very_small_prices(self):
        mock_db = Mock()
        user_id = uuid4()

        mock_result = Mock()
        mock_result.fetchone.side_effect = [
            None,
            {
                "id": uuid4(),
                "user_id": user_id,
                "ticker": "PENNY",
                "quantity": Decimal("10000.0"),
                "avg_price": Decimal("0.001"),
                "added_at": datetime.now()
            }
        ]
        mock_db.execute.return_value = mock_result
        item = PortfolioCreateItem(ticker="PENNY", quantity=10000.0, avg_price=0.001)
        result = add_or_update_position(mock_db, user_id, item)
        assert result.avg_price == 0.001
        assert result.quantity == 10000.0

    def test_very_large_quantities(self):
        mock_db = Mock()
        user_id = uuid4()

        mock_db.execute.return_value.fetchall.return_value = [
            {
                "id": uuid4(),
                "ticker": "WHALE",
                "quantity": Decimal("1000000.0"),
                "avg_price": Decimal("50.00"),
                "current_price": Decimal("60.00"),
                "cost_basis": Decimal("50000000.00"),
                "current_value": Decimal("60000000.00"),
                "total_gain_loss": Decimal("10000000.00"),
                "gain_loss_pct": Decimal("20.00"),
                "return_1d": Decimal("0.5"),
                "return_30d": Decimal("5.0"),
                "return_120d": Decimal("15.0"),
                "return_360d": Decimal("30.0"),
                "price_date": datetime.now(),
                "added_at": datetime.now()
            }
        ]
        result = get_portfolio_summary(mock_db, user_id)
        assert result.summary.total_current_value == 60000000.00
        assert result.summary.total_gain_loss == 10000000.00

    def test_zero_quantity_edge_case(self):
        mock_db = Mock()
        user_id = uuid4()

        mock_db.execute.return_value.fetchone.return_value = {
            "id": uuid4(),
            "user_id": user_id,
            "ticker": "ZERO",
            "quantity": Decimal("0.0"),
            "avg_price": Decimal("100.00"),
            "added_at": datetime.now()
        }
        update_item = PortfolioUpdateItem(quantity=0.0, avg_price=None)
        result = update_portfolio_item(mock_db, user_id, "ZERO", update_item)
        assert result.quantity == 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])