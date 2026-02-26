import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { apiService } from '@/services/apiService';
import type { ReconciledInvoice } from '@/services/apiService';
import Footer from '@/components/Footer';
import './PartReconciliationsPage.css';

const PartReconciliationsPage: React.FC = () => {
    const navigate = useNavigate();
    const [searchParams] = useSearchParams();
    const [reconciliations, setReconciliations] = useState<ReconciledInvoice[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // Get filter parameters from URL
    const partNumber = searchParams.get('partNumber');
    const invoiceNumber = searchParams.get('invoiceNumber');
    const date = searchParams.get('date');

    // Fetch reconciliations for this specific part
    const fetchPartReconciliations = useCallback(async () => {
        try {
            setLoading(true);
            setError(null);

            const filters = {
                partNumber: partNumber || undefined,
                invoiceNumber: invoiceNumber || undefined,
                date: date || undefined,
                page: 1
            };

            const data = await apiService.getReconciliations(filters);
            setReconciliations(data);
        } catch (err) {
            console.error('Error fetching part reconciliations:', err);
            setError(err instanceof Error ? err.message : 'Failed to fetch reconciliations');
        } finally {
            setLoading(false);
        }
    }, [partNumber, invoiceNumber, date]);

    useEffect(() => {
        if (partNumber) {
            fetchPartReconciliations();
        }
    }, [partNumber, fetchPartReconciliations]);

    const handleBackToReconciliations = () => {
        navigate('/reconciliations');
    };

    const handleRefresh = () => {
        fetchPartReconciliations();
    };

    const formatINR = (amount: string) => {
        const num = parseFloat(amount) || 0;
        return new Intl.NumberFormat('en-IN', {
            style: 'currency',
            currency: 'INR',
            minimumFractionDigits: 2
        }).format(num);
    };

    const formatDate = (dateString: string) => {
        return new Date(dateString).toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric'
        });
    };

    return (
        <div className="part-reconciliations-container">
            <header className="part-reconciliations-header">
                <div className="header-content">
                    <div className="header-info">
                        <h1>Part Reconciliations</h1>
                    </div>
                    <div className="header-actions">
                        <Button onClick={handleRefresh} variant="outline" size="sm" disabled={loading}>
                            Refresh
                        </Button>
                        <Button onClick={handleBackToReconciliations} variant="outline" size="sm">
                            Back to Reconciliations
                        </Button>
                    </div>
                </div>
            </header>

            <main className="part-reconciliations-main">
                <div className="part-reconciliations-content">
                    {loading ? (
                        <div className="loading-container">
                            <div className="loading-spinner"></div>
                            <div className="loading-text">Loading reconciliations...</div>
                        </div>
                    ) : error ? (
                        <div className="error-container">
                            <div className="error-icon">⚠️</div>
                            <div className="error-text">{error}</div>
                            <Button onClick={handleRefresh} variant="outline" size="sm">
                                Try Again
                            </Button>
                        </div>
                    ) : (
                        <div className="reconciliations-list">
                            <h2>Reconciliation Details</h2>

                            {partNumber && (
                                <div className="part-details-container">
                                    <div className="part-details">
                                        {invoiceNumber && <span className="invoice-number">Invoice: {invoiceNumber}</span>}
                                        <span className="part-number">Part Number: {partNumber}</span>
                                        {date && <span className="date">Invoice Date: {formatDate(date)}</span>}
                                    </div>
                                </div>
                            )}

                            <div className="summary-section">
                                <div className="summary-card">
                                    <div className="summary-icon">📊</div>
                                    <div className="summary-content">
                                        <div className="summary-value">{reconciliations.length}</div>
                                        <div className="summary-label">Total Reconciliations</div>
                                    </div>
                                </div>

                                <div className="summary-card">
                                    <div className="summary-icon">💰</div>
                                    <div className="summary-content">
                                        <div className="summary-value">
                                            {formatINR(reconciliations.reduce((sum, rec) => sum + parseFloat(rec.profit_absolute || '0'), 0).toString())}
                                        </div>
                                        <div className="summary-label">Total Profit</div>
                                    </div>
                                </div>

                                <div className="summary-card">
                                    <div className="summary-icon">📦</div>
                                    <div className="summary-content">
                                        <div className="summary-value">
                                            {reconciliations.reduce((sum, rec) => sum + rec.consumed_qty, 0)}
                                        </div>
                                        <div className="summary-label">Total Consumed Qty</div>
                                    </div>
                                </div>
                            </div>

                            {reconciliations.length === 0 ? (
                                <div className="no-reconciliations">
                                    <div className="no-reconciliations-icon">🔍</div>
                                    <div className="no-reconciliations-text">
                                        No reconciliations found for this part
                                    </div>
                                </div>
                            ) : (
                                <div className="reconciliations-table-container">
                                    <table className="reconciliations-table">
                                        <thead>
                                            <tr>
                                                <th>ID</th>
                                                <th>Original Qty</th>
                                                <th>Consumed Qty</th>
                                                <th>Remaining Qty</th>
                                                <th>Selling Price</th>
                                                <th>Profit Absolute</th>
                                                <th>Profit Selling Rate</th>
                                                <th>Profit FX Rate</th>
                                                <th>Dollar Rate</th>
                                                <th>Conversion Rate</th>
                                                <th>INR Rate</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {reconciliations.map((reconciliation) => (
                                                <tr key={reconciliation.id} className="reconciliation-row">
                                                    <td className="reconciliation-id">{reconciliation.invoice_entry}</td>
                                                    <td className="original-qty">{reconciliation.invoice.invoice_qty}</td>
                                                    <td className="consumed-qty">{reconciliation.consumed_qty}</td>
                                                    <td className="remaining-qty">{reconciliation.invoice.qty}</td>
                                                    <td className="selling-price">{formatINR(reconciliation.selling_price_inr)}</td>
                                                    <td className="profit-absolute">{formatINR(reconciliation.profit_absolute)}</td>
                                                    <td className="profit-selling-rate">{formatINR(reconciliation.profit_selling_rate)}</td>
                                                    <td className="profit-fx-rate">{formatINR(reconciliation.profit_fx_rate)}</td>
                                                    <td className="dollar-rate">${reconciliation.invoice.dollar_rate}</td>
                                                    <td className="conversion-rate">{reconciliation.invoice.conversion_rate}</td>
                                                    <td className="inr-rate">₹{reconciliation.invoice.inr_rate}</td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            )}
                        </div>
                    )}
                </div>
            </main>

            <Footer />
        </div>
    );
};

export default PartReconciliationsPage;
