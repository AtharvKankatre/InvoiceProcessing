import React, { useState, useEffect, useRef } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import InvoiceSelectionModal from './InvoiceSelectionModal';
import apiService from '@/services/apiService';
import type {
    BulkPreviewResponse,
    BulkPreviewRow,
    SelectedInvoice,
    AvailableInvoice
} from '@/services/apiService';
import './BulkUploadStaging.css';

interface BulkUploadStagingProps {
    file: File;
    onClose: () => void;
    onSuccess: (result: any) => void;
}

export type UiPreviewRow = BulkPreviewRow & {
    dynamic_avail?: number | string;
};

const BulkUploadStaging: React.FC<BulkUploadStagingProps> = ({ file, onClose, onSuccess }) => {
    const [isLoading, setIsLoading] = useState(true);
    const [isCommitting, setIsCommitting] = useState(false);
    const [isAutoFilling, setIsAutoFilling] = useState(false);
    const [error, setError] = useState('');

    const [inventory, setInventory] = useState<BulkPreviewResponse['part_inventory']>({});
    const [rows, setRows] = useState<UiPreviewRow[]>([]);

    const [modalRowId, setModalRowId] = useState<number | null>(null);

    useEffect(() => {
        const fetchPreview = async () => {
            setIsLoading(true);
            try {
                const res = await apiService.previewBulkUpload(file);
                setInventory(res.part_inventory);
                // Re-validate through frontend logic so backend-only error keys
                // (like "format") are replaced with field-specific errors the UI shows
                setRows(validateRows(res.rows, res.part_inventory));
            } catch (err: any) {
                setError(err.message || 'Failed to preview file.');
            } finally {
                setIsLoading(false);
            }
        };
        fetchPreview();
    }, [file]);

    const validateRows = (currentRows: UiPreviewRow[], currentInventory: typeof inventory) => {
        const seen = new Set<string>();

        // ═══════════════════════════════════════════════════════
        // PASS 1: Validate each row's fields & total consumption
        // ═══════════════════════════════════════════════════════
        const totalConsumedByPart: Record<string, number> = {};

        const validated = currentRows.map(row => {
            const newRow: UiPreviewRow = { ...row, errors: {}, is_valid: true, dynamic_avail: '?' };

            // ── Required field checks ──
            if (!newRow.data.part_number) newRow.errors.part_number = 'Required';
            if (!newRow.data.date) newRow.errors.date = 'Required';

            const qtyNum = Number(newRow.data.qty);
            if (isNaN(qtyNum) || qtyNum <= 0) {
                newRow.errors.qty = 'Must be > 0';
            } else if (!Number.isInteger(qtyNum)) {
                newRow.errors.qty = 'Must be a whole number';
            }

            const usdVal = Number(newRow.data.usd_rate);
            if (!newRow.data.usd_rate || isNaN(usdVal)) {
                newRow.errors.usd_rate = 'Required (number)';
            } else if (usdVal <= 0) {
                newRow.errors.usd_rate = 'Must be > 0';
            }

            const convVal = Number(newRow.data.conversion_rate);
            if (!newRow.data.conversion_rate || isNaN(convVal)) {
                newRow.errors.conversion_rate = 'Required (number)';
            } else if (convVal <= 0) {
                newRow.errors.conversion_rate = 'Must be > 0';
            }


            // ── Retail Invoice Number: duplicate check ──
            const invNum = String(newRow.data.retail_invoice_number || '').trim();
            if (!invNum) {
                newRow.errors.retail_invoice_number = 'Required';
            } else if (seen.has(invNum)) {
                newRow.errors.retail_invoice_number = 'Duplicate in file';
            } else {
                seen.add(invNum);
            }

            // ── Manual selection mismatch check ──
            if (newRow.selected_invoices && newRow.selected_invoices.length > 0 && !newRow.errors.qty) {
                const selQty = newRow.selected_invoices.reduce((sum: number, s: any) => sum + s.qty, 0);
                if (selQty !== qtyNum) {
                    newRow.errors.qty = `Selected ${selQty} \u2260 Requested ${qtyNum}`;
                }
            }

            // ── Accumulate consumption per part (only for valid qty rows) ──
            const part = String(newRow.data.part_number || '').trim();
            const searchPart = part.toLowerCase();
            const foundKey = Object.keys(currentInventory).find(k => k.toLowerCase() === searchPart);

            if (!newRow.errors.part_number && part) {
                if (foundKey && currentInventory[foundKey]) {
                    if (!newRow.errors.qty && qtyNum > 0) {
                        totalConsumedByPart[foundKey] = (totalConsumedByPart[foundKey] || 0) + qtyNum;
                    }
                } else {
                    newRow.errors.part_number = 'Part not found or no stock';
                    newRow.dynamic_avail = 0;
                }
            }

            // Store the foundKey for pass 2
            (newRow as any)._foundKey = foundKey;

            newRow.is_valid = Object.keys(newRow.errors).length === 0;
            return newRow;
        });

        // ═══════════════════════════════════════════════════════
        // PASS 2: Set remaining & individual stock checks
        // ═══════════════════════════════════════════════════════
        const result = validated.map(row => {
            const foundKey = (row as any)._foundKey as string | undefined;
            delete (row as any)._foundKey;

            if (foundKey && currentInventory[foundKey]) {
                const totalAvail = currentInventory[foundKey].available_qty;
                const totalConsumed = totalConsumedByPart[foundKey] || 0;
                const globalRemaining = Math.max(0, totalAvail - totalConsumed);

                row.dynamic_avail = globalRemaining;

                // Individual check: does THIS row's qty alone exceed total stock?
                const rowQty = Number(row.data.qty);
                if (!row.errors.qty && !row.errors.part_number && rowQty > 0) {
                    if (rowQty > totalAvail) {
                        row.errors.qty = `Exceeds total stock (${totalAvail} available)`;
                        row.is_valid = false;
                    } else if (totalConsumed > totalAvail) {
                        // Batch is over-consumed but this row alone is OK.
                        // Only warn — don't block (the excessive row above will be blocked).
                        // Check: if removing THIS row's qty still exceeds, it's not the culprit.
                        const consumedByOthers = totalConsumed - rowQty;
                        if (consumedByOthers >= totalAvail) {
                            // Others already exceed — this row is NOT the problem
                            // Just show warning, don't block
                        } else {
                            // This row pushes it over — it IS partly the culprit
                            // But only if removing it would fix the issue
                        }
                    }
                }
            }

            return row;
        });

        return result;
    };

    const handleCellChange = (rowId: number, field: keyof BulkPreviewRow['data'], value: string) => {
        setRows(prev => {
            const newRows = prev.map(r => {
                if (r.row_id === rowId) {
                    return {
                        ...r,
                        data: { ...r.data, [field]: value }
                    };
                }
                return r;
            });
            // Re-validate after change
            return validateRows(newRows, inventory);
        });
    };

    const handleSelectInvoices = (rowId: number) => {
        setModalRowId(rowId);
    };

    const handleConfirmSelection = (selectedInvoices: SelectedInvoice[]) => {
        if (modalRowId === null) return;
        setRows(prev => {
            const newRows = prev.map(r => {
                if (r.row_id === modalRowId) {
                    return { ...r, selected_invoices: selectedInvoices };
                }
                return r;
            });
            return validateRows(newRows, inventory);
        });
        setModalRowId(null);
    };

    const handleRemoveRow = (rowId: number) => {
        setRows(prev => {
            const newRows = prev.filter(r => r.row_id !== rowId);
            return validateRows(newRows, inventory);
        });
    };

    const commitGuard = useRef(false);

    const handleCommit = async () => {
        if (commitGuard.current) return; // Prevent double-click
        if (rows.some(r => !r.is_valid)) {
            alert("Please fix all errors (red rows) before committing.");
            return;
        }

        // Confirmation dialog
        const validCount = rows.filter(r => r.is_valid).length;
        if (!window.confirm(`Are you sure you want to commit ${validCount} row(s) to the database? This action cannot be undone.`)) {
            return;
        }

        commitGuard.current = true;
        setIsCommitting(true);
        setError('');
        try {
            const payload = { rows };
            const res = await apiService.commitBulkUpload(payload);
            onSuccess(res);
        } catch (err: any) {
            const errMsg = err.message || 'Failed to commit batch.';
            setError(errMsg);

            // Try to parse "Row X:" from the error and mark that row red
            const rowMatch = errMsg.match(/Row\s+(\d+)/i);
            if (rowMatch) {
                const failedRowId = parseInt(rowMatch[1]);
                setRows(prev => prev.map(r => {
                    if (r.row_id === failedRowId) {
                        return {
                            ...r,
                            errors: { ...r.errors, _commit: errMsg },
                            is_valid: false
                        };
                    }
                    return r;
                }));
            }
        } finally {
            setIsCommitting(false);
            commitGuard.current = false;
        }
    };

    const activeRowForModal = modalRowId ? rows.find(r => r.row_id === modalRowId) : null;
    const availableInvoicesForModal = (): AvailableInvoice[] => {
        if (!activeRowForModal || !activeRowForModal.data.part_number) return [];

        // Find by case-insensitive and trimmed match
        const searchPart = String(activeRowForModal.data.part_number).trim().toLowerCase();
        const foundKey = Object.keys(inventory).find(k => k.toLowerCase() === searchPart);

        if (!foundKey) return [];
        const partData = inventory[foundKey];
        if (!partData) return [];

        return partData.invoices.map(inv => ({
            id: inv.id,
            invoice_number: inv.invoice_number,
            available_qty: inv.available_qty,
            dollar_rate: inv.dollar_rate,
            conversion_rate: inv.conversion_rate,
            date: inv.date,
            inr_rate: inv.dollar_rate * inv.conversion_rate,
            original_qty: inv.available_qty,
            part_number: partData.sale_part_number,
            customer_code: ''
        }));
    };

    // Row summary counts
    const validCount = rows.filter(r => r.is_valid).length;
    const invalidCount = rows.length - validCount;

    const handleRemoveAllInvalid = () => {
        if (!window.confirm(`Remove ${invalidCount} invalid row(s)? This cannot be undone.`)) return;
        setRows(prev => {
            const validOnly = prev.filter(r => r.is_valid);
            return validateRows(validOnly, inventory);
        });
    };

    // ═══════════════════════════════════════════════════════
    // Auto-Fill All Rows with FIFO Invoice Selection
    // ═══════════════════════════════════════════════════════
    const handleAutoFillAll = () => {
        setIsAutoFilling(true);
        try {
            // Track how much we've consumed from each invoice across ALL rows
            const invoiceRemainingMap: Record<number, number> = {};

            // Initialize remaining qty for every invoice across all parts
            Object.values(inventory).forEach(partData => {
                partData.invoices.forEach(inv => {
                    invoiceRemainingMap[inv.id] = inv.available_qty;
                });
            });

            // Process each row in order (FIFO)
            const updatedRows = rows.map(row => {
                const part = String(row.data.part_number || '').trim().toLowerCase();
                const foundKey = Object.keys(inventory).find(k => k.toLowerCase() === part);
                const qtyNeeded = Number(row.data.qty);

                // Skip rows that have errors in part_number or qty, or already have manual selections
                if (!foundKey || !inventory[foundKey] || isNaN(qtyNeeded) || qtyNeeded <= 0) {
                    return row;
                }

                // If user already manually selected invoices, keep their selection
                if (row.selected_invoices && row.selected_invoices.length > 0) {
                    return row;
                }

                // Apply FIFO across the available invoices for this part
                const partInvoices = inventory[foundKey].invoices;
                let remaining = qtyNeeded;
                const selections: SelectedInvoice[] = [];

                for (const inv of partInvoices) {
                    if (remaining <= 0) break;
                    const availableInThisInvoice = invoiceRemainingMap[inv.id] || 0;
                    if (availableInThisInvoice <= 0) continue;

                    const toTake = Math.min(remaining, availableInThisInvoice);
                    if (toTake > 0) {
                        selections.push({ invoice_id: inv.id, qty: toTake });
                        invoiceRemainingMap[inv.id] -= toTake;
                        remaining -= toTake;
                    }
                }

                // Only assign if we could fully satisfy the required qty
                if (remaining === 0) {
                    return { ...row, selected_invoices: selections };
                }
                return row; // Couldn't fully fill — leave unselected
            });

            setRows(validateRows(updatedRows, inventory));
        } finally {
            setIsAutoFilling(false);
        }
    };

    if (isLoading) {
        return <div className="staging-container loading">Loading preview data and stock levels...</div>;
    }

    if (error && rows.length === 0) {
        return (
            <div className="staging-container error">
                <h3>Error reading file</h3>
                <p>{error}</p>
                <Button onClick={onClose}>Go Back</Button>
            </div>
        );
    }

    const allValid = rows.every(r => r.is_valid);

    return (
        <div className="staging-container">
            <div className="staging-header">
                <h2>Bulk Upload Preview ({rows.length} rows)</h2>
                <div className="staging-actions">
                    <Button variant="outline" onClick={onClose} disabled={isCommitting}>Cancel</Button>
                    <Button
                        className={allValid && rows.length > 0 ? "commit-btn confirm" : "commit-btn"}
                        onClick={handleCommit}
                        disabled={isCommitting || !allValid || rows.length === 0}
                    >
                        {isCommitting ? 'Committing...' : 'Commit to Database'}
                    </Button>
                </div>
            </div>

            {error && <div className="staging-global-error">{error}</div>}

            {/* Row summary banner */}
            <div className={`staging-summary ${allValid ? 'all-valid' : 'has-errors'}`}>
                <span className="summary-label">
                    <span><span className="summary-count">{validCount}</span> valid</span>
                    <span>|</span>
                    <span><span className="summary-count">{invalidCount}</span> invalid</span>
                    <span>|</span>
                    <span>Total: <span className="summary-count">{rows.length}</span></span>
                </span>
                <div className="summary-actions">
                    <button
                        className="btn-auto-fill-all"
                        onClick={handleAutoFillAll}
                        disabled={isAutoFilling || rows.length === 0}
                        title="Automatically assign invoices to all rows using FIFO (First In, First Out) logic"
                    >
                        {isAutoFilling ? 'Auto-Filling...' : 'Auto-Fill All (FIFO)'}
                    </button>
                    {invalidCount > 0 && (
                        <button className="btn-remove-all-invalid" onClick={handleRemoveAllInvalid}>
                            Remove All Invalid ({invalidCount})
                        </button>
                    )}
                </div>
            </div>

            <div className="staging-grid-wrapper">
                <table className="staging-table">
                    <thead>
                        <tr>
                            <th>Status</th>
                            <th>Row</th>
                            <th>Retail Part #</th>
                            <th>Date</th>
                            <th>Quantity</th>
                            <th>$ Rate</th>
                            <th>Conv Rate</th>
                            <th>Retail Inv Number</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows.map(row => {
                            const partData = inventory[row.data.part_number];
                            const availQty = partData ? partData.available_qty : '?';

                            return (
                                <tr key={row.row_id} className={row.is_valid ? 'valid-row' : 'invalid-row'}>
                                    <td className="status-cell">
                                        <span className={`status-indicator ${row.is_valid ? 'valid' : 'invalid'}`}>
                                            {row.is_valid ? '✓' : '!'}
                                        </span>
                                        {(row.errors as any)._commit && (
                                            <div className="cell-error-msg" style={{ textAlign: 'left' }}>
                                                {(row.errors as any)._commit}
                                            </div>
                                        )}
                                    </td>
                                    <td>{row.row_id}</td>
                                    <td>
                                        <Input
                                            value={row.data.part_number || ''}
                                            onChange={(e) => handleCellChange(row.row_id, 'part_number', e.target.value)}
                                            className={row.errors.part_number ? 'input-error' : ''}
                                            title={row.errors.part_number}
                                        />
                                        {row.errors.part_number && <div className="cell-error-msg">{row.errors.part_number}</div>}
                                    </td>
                                    <td>
                                        <Input
                                            type="date"
                                            value={row.data.date || ''}
                                            onChange={(e) => handleCellChange(row.row_id, 'date', e.target.value)}
                                            className={row.errors.date ? 'input-error' : ''}
                                            title={row.errors.date}
                                        />
                                        {row.errors.date && <div className="cell-error-msg">{row.errors.date}</div>}
                                    </td>
                                    <td>
                                        <div className="qty-cell">
                                            <Input
                                                type="number"
                                                value={row.data.qty || ''}
                                                onChange={(e) => handleCellChange(row.row_id, 'qty', e.target.value)}
                                                className={row.errors.qty ? 'input-error' : ''}
                                                title={row.errors.qty}
                                            />
                                            <span className="avail-badge" title="Stock remaining after this row">
                                                ({row.dynamic_avail ?? availQty} remaining)
                                            </span>
                                        </div>
                                        {row.errors.qty && <div className="cell-error-msg">{row.errors.qty}</div>}
                                    </td>
                                    <td>
                                        <Input
                                            type="number" step="0.01"
                                            value={row.data.usd_rate || ''}
                                            onChange={(e) => handleCellChange(row.row_id, 'usd_rate', e.target.value)}
                                            className={row.errors.usd_rate ? 'input-error' : ''}
                                            title={row.errors.usd_rate}
                                        />
                                        {row.errors.usd_rate && <div className="cell-error-msg">{row.errors.usd_rate}</div>}
                                    </td>
                                    <td>
                                        <Input
                                            type="number" step="0.01"
                                            value={row.data.conversion_rate || ''}
                                            onChange={(e) => handleCellChange(row.row_id, 'conversion_rate', e.target.value)}
                                            className={row.errors.conversion_rate ? 'input-error' : ''}
                                            title={row.errors.conversion_rate}
                                        />
                                        {row.errors.conversion_rate && <div className="cell-error-msg">{row.errors.conversion_rate}</div>}
                                    </td>
                                    <td>
                                        <Input
                                            value={row.data.retail_invoice_number || ''}
                                            onChange={(e) => handleCellChange(row.row_id, 'retail_invoice_number', e.target.value)}
                                            className={row.errors.retail_invoice_number ? 'input-error' : ''}
                                            title={row.errors.retail_invoice_number}
                                        />
                                        {row.errors.retail_invoice_number && <div className="cell-error-msg">{row.errors.retail_invoice_number}</div>}
                                    </td>
                                    <td>
                                        <div className="action-buttons-cell">
                                            <button
                                                className={`btn-select-invoices ${row.selected_invoices?.length ? 'selected' : ''}`}
                                                onClick={() => handleSelectInvoices(row.row_id)}
                                                title="Manually select wholesale invoices"
                                            >
                                                {row.selected_invoices?.length ? 'Invoices Selected' : 'Select Invoices'}
                                            </button>
                                            <button
                                                className="btn-remove-row"
                                                onClick={() => handleRemoveRow(row.row_id)}
                                                title="Remove this row from the upload batch"
                                            >
                                                Remove
                                            </button>
                                        </div>
                                    </td>
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            </div>

            {modalRowId && activeRowForModal && (
                <InvoiceSelectionModal
                    isOpen={true}
                    onClose={() => setModalRowId(null)}
                    onConfirm={handleConfirmSelection}
                    availableInvoices={availableInvoicesForModal()}
                    requiredQty={Number(activeRowForModal.data.qty)}
                    partNumber={activeRowForModal.data.part_number || ''}
                    initialSelections={activeRowForModal.selected_invoices}
                />
            )}
        </div>
    );
};

export default BulkUploadStaging;
