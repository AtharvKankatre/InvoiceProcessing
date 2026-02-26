from django.test import TestCase
from django.utils import timezone
from datetime import date, timedelta
from sales.models import Invoice
from sales.services.transaction_merger import TransactionMerger


class TransactionMergerTestCase(TestCase):
    """Test cases for TransactionMerger service class."""

    def setUp(self):
        """Set up test data."""
        self.merger = TransactionMerger()
        self.part_number = "TEST-PART-001"
        
        # Create test invoices
        self.invoice1 = Invoice.objects.create(
            invoice_number="INV-001",
            part_number=self.part_number,
            date=date(2024, 1, 15),
            qty=100,
            customer_name="Test Customer",
            created_at=timezone.now()
        )
        
        self.invoice2 = Invoice.objects.create(
            invoice_number="INV-002",
            part_number=self.part_number,
            date=date(2024, 2, 20),
            qty=200,
            customer_name="",  # Empty customer name
            created_at=timezone.now()
        )
        
        self.invoice3 = Invoice.objects.create(
            invoice_number="INV-003",
            part_number=self.part_number,
            date=date(2024, 3, 10),
            qty=150,
            customer_name=None,  # Null customer name
            created_at=timezone.now()
        )
        
        # Create invoice for different part number
        self.invoice4 = Invoice.objects.create(
            invoice_number="INV-004",
            part_number="OTHER-PART",
            date=date(2024, 1, 20),
            qty=50,
            customer_name="Other Customer",
            created_at=timezone.now()
        )

    def test_get_incoming_transactions_basic(self):
        """Test basic retrieval of incoming transactions."""
        transactions = self.merger.get_incoming_transactions(self.part_number)
        
        # Should return 3 transactions for TEST-PART-001
        self.assertEqual(len(transactions), 3)
        
        # Check that all transactions have required fields
        for txn in transactions:
            self.assertIn('date', txn)
            self.assertIn('invoice_number', txn)
            self.assertIn('qty', txn)
            self.assertIn('type', txn)
            self.assertIn('created_at', txn)
            self.assertIn('customer_name', txn)
            self.assertEqual(txn['type'], 'INCOMING')

    def test_get_incoming_transactions_customer_name_handling(self):
        """Test that customer_name defaults to COOPER when blank or null."""
        transactions = self.merger.get_incoming_transactions(self.part_number)
        
        # Find transactions by invoice number
        txn1 = next(t for t in transactions if t['invoice_number'] == 'INV-001')
        txn2 = next(t for t in transactions if t['invoice_number'] == 'INV-002')
        txn3 = next(t for t in transactions if t['invoice_number'] == 'INV-003')
        
        # Check customer names
        self.assertEqual(txn1['customer_name'], 'Test Customer')
        self.assertEqual(txn2['customer_name'], 'COOPER')  # Empty string
        self.assertEqual(txn3['customer_name'], 'COOPER')  # Null

    def test_get_incoming_transactions_with_from_date(self):
        """Test filtering with from_date."""
        from_date = date(2024, 2, 1)
        transactions = self.merger.get_incoming_transactions(
            self.part_number, 
            from_date=from_date
        )
        
        # Should return 2 transactions (INV-002 and INV-003)
        self.assertEqual(len(transactions), 2)
        
        # All transactions should be on or after from_date
        for txn in transactions:
            self.assertGreaterEqual(txn['date'], from_date)

    def test_get_incoming_transactions_with_to_date(self):
        """Test filtering with to_date."""
        to_date = date(2024, 2, 28)
        transactions = self.merger.get_incoming_transactions(
            self.part_number, 
            to_date=to_date
        )
        
        # Should return 2 transactions (INV-001 and INV-002)
        self.assertEqual(len(transactions), 2)
        
        # All transactions should be on or before to_date
        for txn in transactions:
            self.assertLessEqual(txn['date'], to_date)

    def test_get_incoming_transactions_with_date_range(self):
        """Test filtering with both from_date and to_date."""
        from_date = date(2024, 2, 1)
        to_date = date(2024, 2, 28)
        transactions = self.merger.get_incoming_transactions(
            self.part_number,
            from_date=from_date,
            to_date=to_date
        )
        
        # Should return 1 transaction (INV-002)
        self.assertEqual(len(transactions), 1)
        self.assertEqual(transactions[0]['invoice_number'], 'INV-002')

    def test_get_incoming_transactions_nonexistent_part(self):
        """Test with non-existent part number."""
        transactions = self.merger.get_incoming_transactions("NONEXISTENT")
        
        # Should return empty list
        self.assertEqual(len(transactions), 0)

    def test_get_incoming_transactions_positive_qty(self):
        """Test that all quantities are positive."""
        transactions = self.merger.get_incoming_transactions(self.part_number)
        
        # All quantities should be positive
        for txn in transactions:
            self.assertGreater(txn['qty'], 0)


from sales.services.balance_calculator import BalanceCalculator


class BalanceCalculatorTestCase(TestCase):
    """Test cases for BalanceCalculator service class."""

    def setUp(self):
        """Set up test data."""
        self.calculator = BalanceCalculator()

    def test_calculate_running_balance_basic(self):
        """Test basic running balance calculation."""
        transactions = [
            {'qty': 1350, 'type': 'INCOMING', 'invoice_number': 'INV-001'},
            {'qty': -500, 'type': 'OUTGOING', 'invoice_number': 'RET-001'},
            {'qty': 200, 'type': 'INCOMING', 'invoice_number': 'INV-002'},
        ]
        
        result = self.calculator.calculate_running_balance(transactions)
        
        # Check that on_hand field is added to each transaction
        self.assertEqual(result[0]['on_hand'], 1350)
        self.assertEqual(result[1]['on_hand'], 850)
        self.assertEqual(result[2]['on_hand'], 1050)

    def test_calculate_running_balance_starts_from_zero(self):
        """Test that balance starts from zero."""
        transactions = [
            {'qty': 100, 'type': 'INCOMING', 'invoice_number': 'INV-001'},
        ]
        
        result = self.calculator.calculate_running_balance(transactions)
        
        # First transaction should have on_hand equal to its qty
        self.assertEqual(result[0]['on_hand'], 100)

    def test_calculate_running_balance_only_incoming(self):
        """Test balance calculation with only incoming transactions."""
        transactions = [
            {'qty': 100, 'type': 'INCOMING', 'invoice_number': 'INV-001'},
            {'qty': 200, 'type': 'INCOMING', 'invoice_number': 'INV-002'},
            {'qty': 150, 'type': 'INCOMING', 'invoice_number': 'INV-003'},
        ]
        
        result = self.calculator.calculate_running_balance(transactions)
        
        # Check cumulative balance
        self.assertEqual(result[0]['on_hand'], 100)
        self.assertEqual(result[1]['on_hand'], 300)
        self.assertEqual(result[2]['on_hand'], 450)

    def test_calculate_running_balance_only_outgoing(self):
        """Test balance calculation with only outgoing transactions."""
        transactions = [
            {'qty': -100, 'type': 'OUTGOING', 'invoice_number': 'RET-001'},
            {'qty': -200, 'type': 'OUTGOING', 'invoice_number': 'RET-002'},
        ]
        
        result = self.calculator.calculate_running_balance(transactions)
        
        # Balance should go negative
        self.assertEqual(result[0]['on_hand'], -100)
        self.assertEqual(result[1]['on_hand'], -300)

    def test_calculate_running_balance_going_negative(self):
        """Test balance calculation when balance goes negative."""
        transactions = [
            {'qty': 100, 'type': 'INCOMING', 'invoice_number': 'INV-001'},
            {'qty': -150, 'type': 'OUTGOING', 'invoice_number': 'RET-001'},
            {'qty': 200, 'type': 'INCOMING', 'invoice_number': 'INV-002'},
        ]
        
        result = self.calculator.calculate_running_balance(transactions)
        
        # Check that negative balance is handled correctly
        self.assertEqual(result[0]['on_hand'], 100)
        self.assertEqual(result[1]['on_hand'], -50)  # Goes negative
        self.assertEqual(result[2]['on_hand'], 150)  # Recovers

    def test_calculate_running_balance_empty_list(self):
        """Test with empty transaction list."""
        transactions = []
        
        result = self.calculator.calculate_running_balance(transactions)
        
        # Should return empty list
        self.assertEqual(len(result), 0)

    def test_calculate_running_balance_preserves_original_fields(self):
        """Test that original transaction fields are preserved."""
        transactions = [
            {
                'qty': 100,
                'type': 'INCOMING',
                'invoice_number': 'INV-001',
                'date': date(2024, 1, 15),
                'customer_name': 'Test Customer'
            },
        ]
        
        result = self.calculator.calculate_running_balance(transactions)
        
        # Check that all original fields are preserved
        self.assertEqual(result[0]['qty'], 100)
        self.assertEqual(result[0]['type'], 'INCOMING')
        self.assertEqual(result[0]['invoice_number'], 'INV-001')
        self.assertEqual(result[0]['date'], date(2024, 1, 15))
        self.assertEqual(result[0]['customer_name'], 'Test Customer')
        # And on_hand is added
        self.assertEqual(result[0]['on_hand'], 100)



from rest_framework.test import APITestCase, APIRequestFactory
from rest_framework import status
from sales.views import PartHistoryViewSet


class PartHistoryViewSetTestCase(APITestCase):
    """Test cases for PartHistoryViewSet."""

    def setUp(self):
        """Set up test data."""
        self.factory = APIRequestFactory()
        self.viewset = PartHistoryViewSet.as_view({'get': 'list'})
        self.part_number = "TEST-PART-001"

    def test_list_returns_200_with_valid_part_number(self):
        """Test that list endpoint returns HTTP 200 for valid part number."""
        request = self.factory.get(f'/api/parts/{self.part_number}/history/')
        response = self.viewset(request, part_number=self.part_number)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('part_number', response.data)
        self.assertIn('history', response.data)
        self.assertEqual(response.data['part_number'], self.part_number)

    def test_list_returns_empty_history_for_nonexistent_part(self):
        """Test that list endpoint returns empty history for non-existent part."""
        request = self.factory.get('/api/parts/NONEXISTENT/history/')
        response = self.viewset(request, part_number='NONEXISTENT')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['part_number'], 'NONEXISTENT')
        self.assertEqual(len(response.data['history']), 0)

    def test_list_with_valid_from_date(self):
        """Test that list endpoint accepts valid from_date parameter."""
        request = self.factory.get(
            f'/api/parts/{self.part_number}/history/',
            {'from_date': '2024-01-01'}
        )
        response = self.viewset(request, part_number=self.part_number)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_list_with_valid_to_date(self):
        """Test that list endpoint accepts valid to_date parameter."""
        request = self.factory.get(
            f'/api/parts/{self.part_number}/history/',
            {'to_date': '2024-12-31'}
        )
        response = self.viewset(request, part_number=self.part_number)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_list_with_valid_date_range(self):
        """Test that list endpoint accepts both from_date and to_date."""
        request = self.factory.get(
            f'/api/parts/{self.part_number}/history/',
            {'from_date': '2024-01-01', 'to_date': '2024-12-31'}
        )
        response = self.viewset(request, part_number=self.part_number)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_list_with_invalid_from_date_format(self):
        """Test that list endpoint returns HTTP 400 for invalid from_date format."""
        request = self.factory.get(
            f'/api/parts/{self.part_number}/history/',
            {'from_date': '01-01-2024'}  # Invalid format
        )
        response = self.viewset(request, part_number=self.part_number)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        self.assertIn('from_date', response.data['error'])

    def test_list_with_invalid_to_date_format(self):
        """Test that list endpoint returns HTTP 400 for invalid to_date format."""
        request = self.factory.get(
            f'/api/parts/{self.part_number}/history/',
            {'to_date': '2024/12/31'}  # Invalid format
        )
        response = self.viewset(request, part_number=self.part_number)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        self.assertIn('to_date', response.data['error'])

    def test_list_with_malformed_date(self):
        """Test that list endpoint returns HTTP 400 for malformed dates."""
        request = self.factory.get(
            f'/api/parts/{self.part_number}/history/',
            {'from_date': 'invalid-date'}
        )
        response = self.viewset(request, part_number=self.part_number)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_list_response_structure(self):
        """Test that response has correct structure."""
        request = self.factory.get(f'/api/parts/{self.part_number}/history/')
        response = self.viewset(request, part_number=self.part_number)
        
        # Check response structure
        self.assertIsInstance(response.data, dict)
        self.assertIn('part_number', response.data)
        self.assertIn('history', response.data)
        self.assertIsInstance(response.data['history'], list)


from unittest.mock import patch, MagicMock
from django.db import OperationalError, DatabaseError
from rest_framework.exceptions import AuthenticationFailed, NotAuthenticated


class PartHistoryViewSetErrorHandlingTestCase(APITestCase):
    """Test cases for error handling in PartHistoryViewSet."""

    def setUp(self):
        """Set up test data."""
        self.factory = APIRequestFactory()
        self.viewset = PartHistoryViewSet.as_view({'get': 'list'})
        self.part_number = "TEST-PART-001"

    @patch('sales.views.TransactionMerger')
    def test_database_connection_error_returns_503(self, mock_merger_class):
        """Test that database connection errors return HTTP 503."""
        # Mock the TransactionMerger to raise OperationalError
        mock_merger = MagicMock()
        mock_merger.get_incoming_transactions.side_effect = OperationalError("Database connection failed")
        mock_merger_class.return_value = mock_merger
        
        request = self.factory.get(f'/api/parts/{self.part_number}/history/')
        response = self.viewset(request, part_number=self.part_number)
        
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertIn('error', response.data)
        self.assertIn('temporarily unavailable', response.data['error'].lower())

    @patch('sales.views.TransactionMerger')
    def test_database_error_returns_503(self, mock_merger_class):
        """Test that database errors return HTTP 503."""
        # Mock the TransactionMerger to raise DatabaseError
        mock_merger = MagicMock()
        mock_merger.get_incoming_transactions.side_effect = DatabaseError("Database error")
        mock_merger_class.return_value = mock_merger
        
        request = self.factory.get(f'/api/parts/{self.part_number}/history/')
        response = self.viewset(request, part_number=self.part_number)
        
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertIn('error', response.data)

    @patch('sales.views.TransactionMerger')
    def test_authentication_failed_returns_401(self, mock_merger_class):
        """Test that authentication failures return HTTP 401."""
        # Mock the TransactionMerger to raise AuthenticationFailed
        mock_merger = MagicMock()
        mock_merger.get_incoming_transactions.side_effect = AuthenticationFailed("Invalid token")
        mock_merger_class.return_value = mock_merger
        
        request = self.factory.get(f'/api/parts/{self.part_number}/history/')
        response = self.viewset(request, part_number=self.part_number)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('error', response.data)
        self.assertIn('authentication', response.data['error'].lower())

    @patch('sales.views.TransactionMerger')
    def test_not_authenticated_returns_401(self, mock_merger_class):
        """Test that NotAuthenticated exceptions return HTTP 401."""
        # Mock the TransactionMerger to raise NotAuthenticated
        mock_merger = MagicMock()
        mock_merger.get_incoming_transactions.side_effect = NotAuthenticated("Authentication required")
        mock_merger_class.return_value = mock_merger
        
        request = self.factory.get(f'/api/parts/{self.part_number}/history/')
        response = self.viewset(request, part_number=self.part_number)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('error', response.data)

    @patch('sales.views.TransactionMerger')
    def test_unexpected_exception_returns_500(self, mock_merger_class):
        """Test that unexpected exceptions return HTTP 500."""
        # Mock the TransactionMerger to raise a generic exception
        mock_merger = MagicMock()
        mock_merger.get_incoming_transactions.side_effect = ValueError("Unexpected error")
        mock_merger_class.return_value = mock_merger
        
        request = self.factory.get(f'/api/parts/{self.part_number}/history/')
        response = self.viewset(request, part_number=self.part_number)
        
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn('error', response.data)
        self.assertIn('unexpected', response.data['error'].lower())

    @patch('sales.views.BalanceCalculator')
    @patch('sales.views.TransactionMerger')
    def test_balance_calculator_error_returns_500(self, mock_merger_class, mock_calculator_class):
        """Test that errors in BalanceCalculator return HTTP 500."""
        # Mock successful merger but failing calculator
        mock_merger = MagicMock()
        mock_merger.get_incoming_transactions.return_value = []
        mock_merger.get_outgoing_transactions.return_value = []
        mock_merger.merge_and_sort.return_value = []
        mock_merger_class.return_value = mock_merger
        
        mock_calculator = MagicMock()
        mock_calculator.calculate_running_balance.side_effect = Exception("Calculation error")
        mock_calculator_class.return_value = mock_calculator
        
        request = self.factory.get(f'/api/parts/{self.part_number}/history/')
        response = self.viewset(request, part_number=self.part_number)
        
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn('error', response.data)

    @patch('sales.views.logger')
    @patch('sales.views.TransactionMerger')
    def test_database_error_is_logged(self, mock_merger_class, mock_logger):
        """Test that database errors are logged."""
        # Mock the TransactionMerger to raise DatabaseError
        mock_merger = MagicMock()
        mock_merger.get_incoming_transactions.side_effect = DatabaseError("Database error")
        mock_merger_class.return_value = mock_merger
        
        request = self.factory.get(f'/api/parts/{self.part_number}/history/')
        response = self.viewset(request, part_number=self.part_number)
        
        # Verify that logger.error was called
        mock_logger.error.assert_called_once()
        self.assertIn(self.part_number, str(mock_logger.error.call_args))

    @patch('sales.views.logger')
    @patch('sales.views.TransactionMerger')
    def test_unexpected_error_is_logged_with_traceback(self, mock_merger_class, mock_logger):
        """Test that unexpected errors are logged with full traceback."""
        # Mock the TransactionMerger to raise a generic exception
        mock_merger = MagicMock()
        mock_merger.get_incoming_transactions.side_effect = ValueError("Unexpected error")
        mock_merger_class.return_value = mock_merger
        
        request = self.factory.get(f'/api/parts/{self.part_number}/history/')
        response = self.viewset(request, part_number=self.part_number)
        
        # Verify that logger.error was called with exc_info=True
        mock_logger.error.assert_called_once()
        call_kwargs = mock_logger.error.call_args[1]
        self.assertTrue(call_kwargs.get('exc_info'))

    @patch('sales.views.logger')
    @patch('sales.views.TransactionMerger')
    def test_authentication_error_is_logged_as_warning(self, mock_merger_class, mock_logger):
        """Test that authentication errors are logged as warnings."""
        # Mock the TransactionMerger to raise AuthenticationFailed
        mock_merger = MagicMock()
        mock_merger.get_incoming_transactions.side_effect = AuthenticationFailed("Invalid token")
        mock_merger_class.return_value = mock_merger
        
        request = self.factory.get(f'/api/parts/{self.part_number}/history/')
        response = self.viewset(request, part_number=self.part_number)
        
        # Verify that logger.warning was called
        mock_logger.warning.assert_called_once()
        self.assertIn('Authentication error', str(mock_logger.warning.call_args))
