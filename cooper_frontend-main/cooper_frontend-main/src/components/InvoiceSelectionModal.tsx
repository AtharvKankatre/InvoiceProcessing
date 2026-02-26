import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import type { AvailableInvoice, SelectedInvoice } from '@/services/apiService';
import './InvoiceSelectionModal.css';

interface InvoiceSelectionModalProps {
    isOpen: boolean;
    onClose: () => void;
    onConfirm: (selectedInvoices: SelectedInvoice[]) => void;
    availableInvoices: AvailableInvoice[];
    requiredQty: number;
    partNumber: string;
    isLoading?: boolean;
    initialSelections?: SelectedInvoice[];
}

const InvoiceSelectionModal: React.FC<InvoiceSelectionModalProps> = ({
    isOpen,
    onClose,
    onConfirm,
    availableInvoices,
    requiredQty,
    partNumber,
    isLoading = false,
    initialSelections = [],
}) => {
    // State to track selected quantities for each invoice
    const [selections, setSelections] = useState<Record<number, number>>({});

    // Calculate total selected quantity
    const totalSelectedQty = Object.values(selections).reduce((sum, qty) => sum + qty, 0);
    const remainingQty = requiredQty - totalSelectedQty;
    const isValid = totalSelectedQty === requiredQty;

    // Reset or populate selections when modal opens
    useEffect(() => {
        if (isOpen) {
            if (initialSelections && initialSelections.length > 0) {
                const initialMap: Record<number, number> = {};
                initialSelections.forEach(inv => {
                    initialMap[inv.invoice_id] = inv.qty;
                });
                setSelections(initialMap);
            } else {
                setSelections({});
            }
        }
    }, [isOpen]);

    const handleQtyChange = (invoiceId: number, value: string) => {
        const qty = parseInt(value) || 0;
        const invoice = availableInvoices.find(inv => inv.id === invoiceId);

        if (!invoice) return;

        // Calculate current selection for other invoices (excluding this one)
        const otherSelectionsTotal = Object.entries(selections)
            .filter(([id]) => parseInt(id) !== invoiceId)
            .reduce((sum, [, q]) => sum + q, 0);

        // Maximum allowed for this invoice: minimum of available qty and remaining needed
        const maxAllowedForRemaining = requiredQty - otherSelectionsTotal;
        const maxAllowed = Math.min(invoice.available_qty, Math.max(0, maxAllowedForRemaining));

        // Clamp value between 0 and max allowed
        const clampedQty = Math.max(0, Math.min(qty, maxAllowed));

        setSelections(prev => {
            if (clampedQty === 0) {
                const updatedSelections = { ...prev };
                delete updatedSelections[invoiceId];
                return updatedSelections;
            }
            return { ...prev, [invoiceId]: clampedQty };
        });
    };

    const handleAutoFill = () => {
        // Auto-fill using FIFO logic
        let remaining = requiredQty;
        const newSelections: Record<number, number> = {};

        for (const invoice of availableInvoices) {
            if (remaining <= 0) break;
            const toTake = Math.min(remaining, invoice.available_qty);
            if (toTake > 0) {
                newSelections[invoice.id] = toTake;
                remaining -= toTake;
            }
        }

        setSelections(newSelections);
    };

    const handleConfirm = () => {
        const selectedInvoices: SelectedInvoice[] = Object.entries(selections)
            .filter(([, qty]) => qty > 0)
            .map(([id, qty]) => ({
                invoice_id: parseInt(id),
                qty,
            }));

        onConfirm(selectedInvoices);
    };

    if (!isOpen) return null;

    return (
        <div className="modal-overlay">
            <div className="modal-container">
                <div className="modal-header">
                    <h2>Select Cooper Invoices</h2>
                    <button className="modal-close" onClick={onClose}>×</button>
                </div>

                <div className="modal-info">
                    <div className="info-row">
                        <span className="info-label">Part Number:</span>
                        <span className="info-value">{partNumber}</span>
                    </div>

                    <div className="info-row">
                        <span className="info-label">Required Qty:</span>
                        <span className="info-value">{requiredQty}</span>
                    </div>
                </div>

                <div className="selection-summary">
                    <div className={`summary-item ${isValid ? 'valid' : 'invalid'}`}>
                        <span>Selected: {totalSelectedQty}</span>
                        <span>Remaining: {remainingQty}</span>
                    </div>
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={handleAutoFill}
                        disabled={isLoading}
                    >
                        Auto-Fill (FIFO)
                    </Button>
                </div>

                {isLoading ? (
                    <div className="loading-state">Loading invoices...</div>
                ) : availableInvoices.length === 0 ? (
                    <div className="empty-state">No available invoices found for this part number.</div>
                ) : (
                    <div className="invoices-table-container">
                        <table className="invoices-table">
                            <thead>
                                <tr>
                                    <th>Invoice #</th>
                                    <th>Date</th>
                                    <th>Available</th>
                                    <th>$ Rate</th>
                                    <th>Conv. Rate</th>
                                    <th>Select Qty</th>
                                </tr>
                            </thead>
                            <tbody>
                                {availableInvoices.map((invoice) => (
                                    <tr
                                        key={invoice.id}
                                        className={selections[invoice.id] ? 'selected-row' : ''}
                                    >
                                        <td>{invoice.invoice_number}</td>
                                        <td>{invoice.date}</td>
                                        <td>{invoice.available_qty}</td>
                                        <td>${invoice.dollar_rate.toFixed(2)}</td>
                                        <td>{invoice.conversion_rate.toFixed(2)}</td>
                                        <td>
                                            <Input
                                                type="number"
                                                min="0"
                                                max={invoice.available_qty}
                                                value={selections[invoice.id] || ''}
                                                onChange={(e) => handleQtyChange(invoice.id, e.target.value)}
                                                placeholder="0"
                                                className="qty-input"
                                            />
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}

                <div className="modal-footer">
                    <Button variant="outline" onClick={onClose} disabled={isLoading}>
                        Cancel
                    </Button>
                    <Button
                        onClick={handleConfirm}
                        disabled={!isValid || isLoading}
                        className={isValid ? 'confirm-btn' : ''}
                    >
                        Confirm Selection
                    </Button>
                </div>
            </div>
        </div>
    );
};

export default InvoiceSelectionModal;
