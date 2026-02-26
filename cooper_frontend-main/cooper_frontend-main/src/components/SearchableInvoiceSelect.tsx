import React, { useState, useEffect, useRef } from 'react';
import { invoiceService } from '../services/invoiceService';
import type { InvoiceItem } from '../services/apiService';
import { Search, ChevronDown, Check, X } from 'lucide-react';

interface SearchableInvoiceSelectProps {
    selectedInvoiceId: number | null;
    onSelect: (invoice: InvoiceItem | null) => void;
    placeholder?: string;
}

const SearchableInvoiceSelect: React.FC<SearchableInvoiceSelectProps> = ({
    selectedInvoiceId,
    onSelect,
    placeholder = "Search Invoice Number..."
}) => {
    const [isOpen, setIsOpen] = useState(false);
    const [searchTerm, setSearchTerm] = useState('');
    const [invoices, setInvoices] = useState<InvoiceItem[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [selectedInvoice, setSelectedInvoice] = useState<InvoiceItem | null>(null);
    const wrapperRef = useRef<HTMLDivElement>(null);

    // Initial fetch to get selected invoice details if ID is provided but object is missing
    useEffect(() => {
        if (selectedInvoiceId && !selectedInvoice) {
            const fetchSelected = async () => {
                try {
                    // We might need a getInvoiceById endpoint, assuming likely user has one or we search for it
                    // optimizing: just search for it or fetch by ID if available
                    const response = await invoiceService.getInvoiceById(selectedInvoiceId.toString());
                    setSelectedInvoice(response);
                    setSearchTerm(response.invoice_number); // Prefill search with selected
                } catch (e) {
                    console.error("Failed to fetch selected invoice", e);
                }
            };
            fetchSelected();
        } else if (!selectedInvoiceId) {
            setSelectedInvoice(null);
            setSearchTerm('');
        }
    }, [selectedInvoiceId]);

    // Debounced search
    useEffect(() => {
        const timer = setTimeout(() => {
            if (isOpen || searchTerm) {
                fetchInvoices(searchTerm);
            }
        }, 500);

        return () => clearTimeout(timer);
    }, [searchTerm, isOpen]);

    const fetchInvoices = async (search: string) => {
        setIsLoading(true);
        try {
            const response = await invoiceService.getInvoices({
                invoiceNumber: search,
                limit: 10 // Limit results for dropdown
            });

            // Handle different generic response structures
            const results = response.results || response.data || [];
            setInvoices(results);
        } catch (error) {
            console.error('Error fetching invoices:', error);
            setInvoices([]);
        } finally {
            setIsLoading(false);
        }
    };

    // Close dropdown when clicking outside
    useEffect(() => {
        function handleClickOutside(event: MouseEvent) {
            if (wrapperRef.current && !wrapperRef.current.contains(event.target as Node)) {
                setIsOpen(false);
            }
        }
        document.addEventListener("mousedown", handleClickOutside);
        return () => document.removeEventListener("mousedown", handleClickOutside);
    }, [wrapperRef]);

    const handleSelect = (invoice: InvoiceItem) => {
        setSelectedInvoice(invoice);
        setSearchTerm(invoice.invoice_number);
        onSelect(invoice);
        setIsOpen(false);
    };

    const clearSelection = (e: React.MouseEvent) => {
        e.stopPropagation();
        setSelectedInvoice(null);
        setSearchTerm('');
        onSelect(null);
        setInvoices([]); // Clear previous results
        // Refresh list
        fetchInvoices('');
    };

    return (
        <div className="relative w-full" ref={wrapperRef}>
            <div
                className="flex items-center border border-slate-300 rounded-md px-3 py-2 bg-white focus-within:ring-2 focus-within:ring-blue-500 cursor-text"
                onClick={() => setIsOpen(true)}
            >
                <Search className="w-4 h-4 text-slate-400 mr-2" />
                <input
                    type="text"
                    className="flex-1 outline-none text-sm text-slate-700 placeholder-slate-400"
                    placeholder={placeholder}
                    value={searchTerm}
                    onChange={(e) => {
                        setSearchTerm(e.target.value);
                        setIsOpen(true);
                        if (!e.target.value) {
                            setSelectedInvoice(null);
                        }
                    }}
                    onFocus={() => setIsOpen(true)}
                />

                {selectedInvoice ? (
                    <button
                        onClick={clearSelection}
                        className="p-1 hover:bg-slate-100 rounded-full text-slate-400 hover:text-red-500 transition-colors"
                    >
                        <X className="w-4 h-4" />
                    </button>
                ) : (
                    <ChevronDown className={`w-4 h-4 text-slate-400 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
                )}
            </div>

            {isOpen && (
                <div className="absolute z-50 w-full mt-1 bg-white border border-slate-200 rounded-md shadow-lg max-h-60 overflow-y-auto">
                    {isLoading ? (
                        <div className="p-4 text-center text-xs text-slate-500">Loading...</div>
                    ) : invoices.length > 0 ? (
                        <ul>
                            {invoices.map((invoice) => (
                                <li
                                    key={invoice.id}
                                    className={`px-4 py-2 text-sm cursor-pointer hover:bg-slate-50 flex justify-between items-center ${selectedInvoiceId === invoice.id ? 'bg-blue-50 text-blue-700' : 'text-slate-700'}`}
                                    onClick={() => handleSelect(invoice)}
                                >
                                    <div className="flex flex-col">
                                        <span className="font-medium">{invoice.invoice_number}</span>
                                        <span className="text-xs text-slate-400">Qty: {invoice.qty} | Date: {invoice.date}</span>
                                    </div>
                                    {selectedInvoiceId === invoice.id && <Check className="w-4 h-4 text-blue-600" />}
                                </li>
                            ))}
                        </ul>
                    ) : (
                        <div className="p-4 text-center text-xs text-slate-500">No invoices found.</div>
                    )}
                </div>
            )}
        </div>
    );
};

export default SearchableInvoiceSelect;
