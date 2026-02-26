# Balance calculator service


class BalanceCalculator:
    """
    Service class for calculating running balance across transactions.
    
    This class takes a list of transactions and annotates each with an 
    on_hand balance field, representing the cumulative quantity after 
    each transaction.
    """
    
    def calculate_running_balance(self, transactions):
        """
        Calculate on_hand balance for each transaction.
        
        Args:
            transactions: List of transaction dictionaries, each containing:
                - date: Transaction date
                - invoice_number: Invoice or retail invoice number
                - qty: Transaction quantity (positive for incoming, negative for outgoing)
                - type: Transaction type ('INCOMING' or 'OUTGOING')
                - created_at: Timestamp for secondary sorting
        
        Returns:
            List of transactions with on_hand field added to each transaction.
            The on_hand field represents the cumulative balance after that transaction.
        
        Example:
            >>> calculator = BalanceCalculator()
            >>> transactions = [
            ...     {'qty': 1350, 'type': 'INCOMING', ...},
            ...     {'qty': -500, 'type': 'OUTGOING', ...},
            ...     {'qty': 200, 'type': 'INCOMING', ...},
            ... ]
            >>> result = calculator.calculate_running_balance(transactions)
            >>> [t['on_hand'] for t in result]
            [1350, 850, 1050]
        """
        balance = 0
        
        for transaction in transactions:
            balance = balance + transaction['qty']
            transaction['on_hand'] = balance
        
        return transactions
