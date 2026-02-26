import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { invoiceService } from '../services/invoiceService';
import type { BalanceHistoryEntry, PaginatedBalanceHistory, InvoiceItem, BalanceHistoryInvoice } from '../services/apiService';
import './BalanceHistoryPage.css';
import { ArrowLeft, Package, ArrowDown, CheckCircle, Loader2 } from 'lucide-react';
import Footer from '../components/Footer';
import SearchableInvoiceSelect from '../components/SearchableInvoiceSelect';

const BalanceHistoryPage: React.FC = () => {
    const navigate = useNavigate();
    const [selectedInvoiceId, setSelectedInvoiceId] = useState<number | null>(null);
    const [invoiceDetails, setInvoiceDetails] = useState<BalanceHistoryInvoice | null>(null);
    const [historyItems, setHistoryItems] = useState<BalanceHistoryEntry[]>([]);
    const [pagination, setPagination] = useState<PaginatedBalanceHistory | null>(null);
    const [isLoading, setIsLoading] = useState<boolean>(false);
    const [loadingMore, setLoadingMore] = useState<boolean>(false);
    const [error, setError] = useState<string | null>(null);

    // Fetch history when invoice is selected or page changes
    const fetchHistory = async (invoiceId: number, page: number = 1, append: boolean = false) => {
        if (!append) {
            setIsLoading(true);
            setHistoryItems([]);
        } else {
            setLoadingMore(true);
        }
        setError(null);

        try {
            // Fetch paginated balance history for the selected invoice
            const response = await invoiceService.getBalanceHistory(invoiceId, page, 10);

            if (response.invoice) {
                setInvoiceDetails(response.invoice);
            }

            let newItems: BalanceHistoryEntry[] = [];

            if (response.history && !Array.isArray(response.history)) {
                // It's paginated
                const paginated = response.history as PaginatedBalanceHistory;
                setPagination(paginated);
                newItems = paginated.results;
            } else if (Array.isArray(response.history)) {
                // Fallback for non-paginated
                newItems = response.history;
                setPagination(null);
            }

            setHistoryItems(prev => append ? [...prev, ...newItems] : newItems);

        } catch (err) {
            console.error('Error fetching balance history:', err);
            setError('Failed to load balance history data. Please try again.');
        } finally {
            setIsLoading(false);
            setLoadingMore(false);
        }
    };

    useEffect(() => {
        if (selectedInvoiceId) {
            fetchHistory(selectedInvoiceId, 1, false);
        } else {
            setInvoiceDetails(null);
            setHistoryItems([]);
            setPagination(null);
        }
    }, [selectedInvoiceId]);

    const handleLoadMore = () => {
        if (selectedInvoiceId && pagination?.has_next) {
            fetchHistory(selectedInvoiceId, pagination.current_page + 1, true);
        }
    };

    const handleInvoiceSelect = (invoice: InvoiceItem | null) => {
        setSelectedInvoiceId(invoice ? invoice.id : null);
    };

    // Helper to format currency
    const formatCurrency = (val: number | string | undefined, type: '$' | '₹') => {
        if (val === undefined || val === null) return '-';
        const num = Number(val);
        return type === '$'
            ? `$${num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
            : `₹${num.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    };

    const originalQty = invoiceDetails?.invoice_qty || 0;
    const remainingQty = invoiceDetails?.qty || 0;
    const consumedQty = originalQty - remainingQty;

    const dollarRate = Number(invoiceDetails?.dollar_rate || 0);
    const inrRate = Number(invoiceDetails?.inr_rate || 0);

    const originalDollar = originalQty * dollarRate;
    const originalInr = originalQty * inrRate;
    const remainingDollar = remainingQty * dollarRate;
    const remainingInr = remainingQty * inrRate;
    const consumedDollar = consumedQty * dollarRate;
    const consumedInr = consumedQty * inrRate;

    return (
        <div className="balance-history-container">
            <header className="balance-history-header">
                <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                    <button
                        onClick={() => navigate('/dashboard')}
                        style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '0.5rem', display: 'flex', alignItems: 'center' }}
                        aria-label="Back to Dashboard"
                    >
                        <ArrowLeft size={24} color="#64748b" />
                    </button>
                    <h1>Balance History</h1>
                </div>
                <div className="header-actions">
                    <button
                        onClick={() => navigate('/dashboard')}
                        style={{ padding: '0.5rem 1rem', background: '#3b82f6', color: 'white', border: 'none', borderRadius: '8px', cursor: 'pointer', fontWeight: 600 }}
                    >
                        Dashboard
                    </button>
                </div>
            </header>

            <main className="balance-history-main">
                <div className="balance-history-content">
                    {/* Invoice Selector */}
                    <div className="invoice-selector" style={{ marginBottom: '2rem' }}>
                        <label className="block text-sm font-medium text-slate-700 mb-2">Select Invoice to View Timeline</label>
                        <SearchableInvoiceSelect
                            selectedInvoiceId={selectedInvoiceId}
                            onSelect={handleInvoiceSelect}
                            placeholder="Search by Invoice Number..."
                        />
                    </div>

                    {isLoading && (
                        <div className="loading-state" style={{ textAlign: 'center', padding: '3rem', color: '#64748b' }}>
                            <div className="spinner" style={{ marginBottom: '1rem', fontSize: '2rem' }}>↻</div>
                            <p>Loading timeline...</p>
                        </div>
                    )}

                    {error && (
                        <div className="error-state" style={{ textAlign: 'center', padding: '2rem', color: '#e11d48', background: '#fff1f2', borderRadius: '12px', border: '1px solid #fecdd3' }}>
                            <p>{error}</p>
                        </div>
                    )}

                    {!isLoading && !selectedInvoiceId && !error && (
                        <div className="empty-state" style={{ textAlign: 'center', padding: '4rem', color: '#94a3b8' }}>
                            <Package size={64} style={{ marginBottom: '1rem', opacity: 0.5 }} />
                            <h3>No Invoice Selected</h3>
                            <p>Please select an invoice from the dropdown above to view its history timeline.</p>
                        </div>
                    )}

                    {!isLoading && !error && invoiceDetails && (
                        <>
                            {/* Summary Cards */}
                            <div className="summary-cards">
                                <div className="summary-card">
                                    <h3>Original Quantity</h3>
                                    <span className="value">{originalQty}</span>
                                    <div className="summary-card-footer">
                                        <span className="sub-value" style={{ color: '#059669' }}>{formatCurrency(originalDollar, '$')}</span>
                                        <span className="sub-value" style={{ color: '#059669' }}>{formatCurrency(originalInr, '₹')}</span>
                                    </div>
                                </div>
                                <div className={`summary-card ${consumedQty > 0 ? 'warning' : ''}`}>
                                    <h3>Consumed Quantity</h3>
                                    <span className="value">{consumedQty}</span>
                                    <div className="summary-card-footer">
                                        <span className="sub-value" style={{ color: '#e11d48' }}>{formatCurrency(consumedDollar, '$')}</span>
                                        <span className="sub-value" style={{ color: '#e11d48' }}>{formatCurrency(consumedInr, '₹')}</span>
                                    </div>
                                </div>
                                <div className={`summary-card ${remainingQty > 0 ? 'success' : ''}`}>
                                    <h3>Remaining Quantity</h3>
                                    <span className="value">{remainingQty}</span>
                                    <div className="summary-card-footer">
                                        <span className="sub-value" style={{ color: '#2563eb' }}>{formatCurrency(remainingDollar, '$')}</span>
                                        <span className="sub-value" style={{ color: '#2563eb' }}>{formatCurrency(remainingInr, '₹')}</span>
                                    </div>
                                </div>
                            </div>

                            {/* TIMELINE SECTION */}
                            <div className="timeline-section">
                                <h2 className="timeline-section-title">Timeline of Events</h2>

                                <div className="timeline-container">

                                    {/* Map History Items */}
                                    {historyItems.map((entry, index) => {
                                        // Determine type based on action
                                        const isCreation = entry.action.includes('Created');
                                        const isConsumption = entry.action.includes('Retail') || entry.change < 0;
                                        const date = new Date(entry.date).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });

                                        return (
                                            <div key={index} className="timeline-item">
                                                {/* Left: Date */}
                                                <div className="timeline-date-col">
                                                    <span className="timeline-date">{date}</span>
                                                    <span className="timeline-time">{isCreation ? 'Start' : 'Event'}</span>
                                                </div>

                                                {/* Center: Line & Utility Icon */}
                                                <div className="timeline-marker-col">
                                                    <div className="timeline-line"></div>
                                                    <div className={`timeline-icon-wrapper ${isCreation ? 'created' : 'consumption'}`}>
                                                        {isCreation ? <Package size={20} /> : <ArrowDown size={20} />}
                                                    </div>
                                                </div>

                                                {/* Right: Content Card */}
                                                <div className="timeline-content-col">
                                                    <div className="timeline-card">
                                                        <div className="timeline-card-header">
                                                            <h4 className="timeline-title">{entry.action}</h4>
                                                            <span className={`timeline-badge ${isCreation ? 'created' : 'consumption'}`}>
                                                                {isCreation ? 'Creation' : 'Deduction'}
                                                            </span>
                                                        </div>
                                                        <div className="timeline-details">
                                                            <div className={`detail-group ${isConsumption ? 'negative' : 'highlight'}`}>
                                                                <label>Change</label>
                                                                <span>{entry.change > 0 ? `+${entry.change}` : entry.change}</span>
                                                            </div>
                                                            <div className="detail-group highlight">
                                                                <label>Balance After</label>
                                                                <span>{entry.balance}</span>
                                                            </div>
                                                            {entry.retail_invoice && (
                                                                <div className="detail-group">
                                                                    <label>Retail Invoice</label>
                                                                    <span>{entry.retail_invoice}</span>
                                                                </div>
                                                            )}

                                                        </div>
                                                    </div>
                                                </div>
                                            </div>
                                        );
                                    })}

                                    {pagination?.has_next && (
                                        <div className="timeline-item">
                                            <div className="timeline-date-col"></div>
                                            <div className="timeline-marker-col">
                                                <div className="timeline-line"></div>
                                            </div>
                                            <div className="timeline-content-col">
                                                <button
                                                    onClick={handleLoadMore}
                                                    disabled={loadingMore}
                                                    className="w-full py-2 bg-blue-50 text-blue-600 font-medium rounded-lg hover:bg-blue-100 transition-colors flex justify-center items-center gap-2"
                                                >
                                                    {loadingMore ? <Loader2 className="animate-spin w-4 h-4" /> : 'Load More History'}
                                                </button>
                                            </div>
                                        </div>
                                    )}

                                    {/* Final Status Node (Only show if end reached) */}
                                    {pagination && !pagination.has_next && (
                                        <div className="timeline-item">
                                            <div className="timeline-date-col">
                                                <span className="timeline-date">Now</span>
                                            </div>
                                            <div className="timeline-marker-col">
                                                <div className="timeline-icon-wrapper status">
                                                    <CheckCircle size={20} />
                                                </div>
                                            </div>
                                            <div className="timeline-content-col">
                                                <div className="timeline-card">
                                                    <div className="timeline-card-header">
                                                        <h4 className="timeline-title">Current Status</h4>
                                                        <span className={`timeline-badge ${remainingQty > 0 ? 'active' : 'consumption'}`}>
                                                            {remainingQty > 0 ? 'Active' : 'Fully Consumed'}
                                                        </span>
                                                    </div>
                                                    <div className="timeline-details">
                                                        <div className="detail-group highlight">
                                                            <label>Final Balance</label>
                                                            <span>{remainingQty} Units</span>
                                                        </div>
                                                        <div className="detail-group">
                                                            <label>Valuation ($)</label>
                                                            <span>{formatCurrency(remainingDollar, '$')}</span>
                                                        </div>
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    )}

                                </div>
                            </div>
                        </>
                    )}
                </div>
            </main>

            <Footer />
        </div>
    );
};

export default BalanceHistoryPage;
