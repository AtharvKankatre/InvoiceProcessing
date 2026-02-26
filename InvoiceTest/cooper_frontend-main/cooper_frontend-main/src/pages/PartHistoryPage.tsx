import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiService } from '../services/apiService';
import type { TransactionHistoryEntry } from '../types/partHistory';
import './PartHistoryPage.css';
import { ArrowLeft, Search, Package, Loader2, FileDown } from 'lucide-react';
import Footer from '../components/Footer';

const PartHistoryPage: React.FC = () => {
    const navigate = useNavigate();
    const [partNumber, setPartNumber] = useState<string>('');
    const [fromDate, setFromDate] = useState<string>('');
    const [toDate, setToDate] = useState<string>('');
    const [transactions, setTransactions] = useState<TransactionHistoryEntry[]>([]);
    const [loading, setLoading] = useState<boolean>(false);
    const [error, setError] = useState<string | null>(null);
    const [hasSearched, setHasSearched] = useState<boolean>(false);

    const handleSearch = async () => {
        if (!partNumber.trim()) {
            setError('Please enter a part number');
            return;
        }

        setLoading(true);
        setError(null);
        setHasSearched(true);

        try {
            const response = await apiService.getPartHistory(
                partNumber.trim(),
                fromDate || undefined,
                toDate || undefined
            );

            setTransactions(response.history);

            if (response.history.length === 0) {
                setError('No transactions found for this part number.');
            }
        } catch (err) {
            console.error('Error fetching part history:', err);
            if (err instanceof Error) {
                if (err.message.includes('Session expired') || err.message.includes('Authentication')) {
                    setError('Session expired. Redirecting to login...');
                    setTimeout(() => navigate('/login'), 2000);
                } else if (err.message.includes('Network') || err.message.includes('fetch')) {
                    setError('Network error. Please check your connection.');
                } else {
                    setError(err.message || 'Failed to load transaction history. Please try again.');
                }
            } else {
                setError('Failed to load transaction history. Please try again.');
            }
        } finally {
            setLoading(false);
        }
    };



    const handleExportAll = async () => {
        try {
            setLoading(true);
            const blob = await apiService.exportAllPartHistory(
                fromDate || undefined,
                toDate || undefined
            );

            // Create download link
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `All_Parts_History_${new Date().toISOString().split('T')[0]}.xlsx`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
        } catch (err) {
            console.error('Export ALL failed:', err);
            setError('Failed to export all history. Please try again.');
        } finally {
            setLoading(false);
        }
    };

    const handleKeyPress = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter') {
            handleSearch();
        }
    };

    const formatDate = (dateString: string) => {
        const date = new Date(dateString);
        return date.toLocaleDateString(undefined, {
            year: 'numeric',
            month: 'short',
            day: 'numeric'
        });
    };

    const formatQuantity = (qty: number, type: 'INCOMING' | 'OUTGOING') => {
        if (type === 'INCOMING') {
            return `+${qty}`;
        }
        return qty.toString();
    };

    return (
        <div className="part-history-container">
            <header className="part-history-header">
                <div className="header-title-group">
                    <button
                        onClick={() => navigate('/dashboard')}
                        className="header-back-button"
                        aria-label="Back to Dashboard"
                    >
                        <ArrowLeft size={24} color="#64748b" />
                    </button>
                    <h1>Part Transaction History</h1>
                </div>
                <div className="header-actions">

                    <button
                        onClick={() => navigate('/dashboard')}
                        className="header-action-button dashboard-button"
                    >
                        Dashboard
                    </button>
                    <button
                        onClick={handleExportAll}
                        disabled={loading}
                        className="header-action-button export-button"
                        style={{ backgroundColor: '#10b981', color: 'white', borderColor: '#10b981' }}
                    >
                        <FileDown size={18} />
                        Export All Parts
                    </button>
                </div>
            </header>

            <main className="part-history-main">
                <div className="part-history-content">
                    <div className="search-section">
                        <p className="search-description">
                            View complete transaction history for any part number, including incoming stock from Cooper
                            and outgoing shipments to Retail customers.
                        </p>

                        {/* Part Number Search */}
                        <div className="search-input-group">
                            <label className="search-label">Part Number</label>
                            <div className="search-input-wrapper">
                                <input
                                    type="text"
                                    value={partNumber}
                                    onChange={(e) => setPartNumber(e.target.value)}
                                    onKeyPress={handleKeyPress}
                                    placeholder="Enter part number..."
                                    className="search-input"
                                />
                                <button
                                    onClick={handleSearch}
                                    disabled={loading}
                                    className="search-button"
                                >
                                    {loading ? (
                                        <Loader2 className="animate-spin" size={20} />
                                    ) : (
                                        <Search size={20} />
                                    )}
                                    <span>Search</span>
                                </button>
                            </div>
                        </div>

                        {/* Date Range Filters */}
                        <div className="date-filters">
                            <div className="date-input-group">
                                <label className="date-label">From Date (Optional)</label>
                                <input
                                    type="date"
                                    value={fromDate}
                                    onChange={(e) => setFromDate(e.target.value)}
                                    className="date-input"
                                />
                            </div>
                            <div className="date-input-group">
                                <label className="date-label">To Date (Optional)</label>
                                <input
                                    type="date"
                                    value={toDate}
                                    onChange={(e) => setToDate(e.target.value)}
                                    className="date-input"
                                />
                            </div>
                        </div>
                    </div>

                    {/* Loading State */}
                    {loading && (
                        <div className="loading-state">
                            <Loader2 className="animate-spin" size={48} />
                            <p>Loading transaction history...</p>
                        </div>
                    )}

                    {/* Error State */}
                    {error && !loading && (
                        <div className="error-state">
                            <p>{error}</p>
                        </div>
                    )}

                    {/* Empty State - Before Search */}
                    {!loading && !error && !hasSearched && (
                        <div className="empty-state">
                            <Package size={64} style={{ opacity: 0.5 }} />
                            <h3>No Search Performed</h3>
                            <p>Enter a part number above and click Search to view transaction history.</p>
                        </div>
                    )}

                    {/* Transaction Table */}
                    {!loading && !error && hasSearched && transactions.length > 0 && (
                        <div className="transactions-section">
                            <h2 className="transactions-title">
                                Transaction History for {partNumber}
                            </h2>
                            <div className="table-container">
                                <table className="transactions-table">
                                    <thead>
                                        <tr>
                                            <th>Date</th>
                                            <th>Invoice No</th>
                                            <th>Customer Name</th>
                                            <th>Code</th>
                                            <th>Qty</th>
                                            <th>On Hand</th>
                                            <th>Type</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {transactions.map((transaction, index) => (
                                            <tr key={index} className={`transaction-row ${transaction.type.toLowerCase()}`}>
                                                <td>{formatDate(transaction.date)}</td>
                                                <td>{transaction.invoice_number}</td>
                                                <td>{transaction.name || "-"}</td>
                                                <td>{transaction.customer_code || "-"}</td>
                                                <td className={`qty-cell ${transaction.type.toLowerCase()}`}>
                                                    {formatQuantity(transaction.qty, transaction.type)}
                                                </td>
                                                <td className="on-hand-cell">{transaction.on_hand}</td>
                                                <td>
                                                    <span className={`type-badge ${transaction.type.toLowerCase()}`}>
                                                        {transaction.type}
                                                    </span>
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    )}
                </div>
            </main>

            <Footer />
        </div>
    );
};

export default PartHistoryPage;
