import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import Modal from '@/components/ui/modal';
import Loading from '@/components/ui/loading';
import { invoiceService } from '@/services/invoiceService';
import type { InvoiceItem } from '@/services/apiService';
import Footer from '@/components/Footer';
import './InvoiceDetailsPage.css';

interface SortConfig {
  key: keyof InvoiceItem | null;
  direction: 'asc' | 'desc';
}

const InvoiceDetailsPage: React.FC = () => {
  const navigate = useNavigate();
  const [invoices, setInvoices] = useState<InvoiceItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string>('');
  const [pagination, setPagination] = useState({
    next: null as string | null,
    previous: null as string | null,
    count: 0
  });

  // Filter state

  // We need a separate state for the form values in the modal before applying
  const [tempFilters, setTempFilters] = useState({
    invoice_number: '',
    part_number: '',
    date: '',
    qty: '',
    dollar_rate: '',
    dollar_total: '',
    inr_rate: '',
    inr_total: '',
    conversion_rate: '',
    invoice_qty: '',
  });

  const [appliedFilters, setAppliedFilters] = useState(tempFilters);

  const [sortConfig, setSortConfig] = useState<SortConfig>({
    key: null,
    direction: 'asc'
  });
  const [isFilterModalOpen, setIsFilterModalOpen] = useState(false);

  // Client-side sort of the FETCHED page (since backend sorting isn't fully dynamic yet)
  const sortedInvoices = React.useMemo(() => {
    const sorted = [...invoices];
    if (sortConfig.key) {
      sorted.sort((a, b) => {
        const aValue = a[sortConfig.key!];
        const bValue = b[sortConfig.key!];
        let comparison = 0;
        if (typeof aValue === 'string' && typeof bValue === 'string') {
          comparison = aValue.localeCompare(bValue);
        } else if (typeof aValue === 'number' && typeof bValue === 'number') {
          comparison = aValue - bValue;
        } else {
          comparison = String(aValue).localeCompare(String(bValue));
        }
        return sortConfig.direction === 'asc' ? comparison : -comparison;
      });
    }
    return sorted;
  }, [invoices, sortConfig]);

  const handleSort = (key: keyof InvoiceItem) => {
    setSortConfig(prevConfig => ({
      key,
      direction: prevConfig.key === key && prevConfig.direction === 'asc' ? 'desc' : 'asc'
    }));
  };

  const handleFilterChange = (key: keyof typeof tempFilters, value: string) => {
    setTempFilters(prev => ({
      ...prev,
      [key]: value
    }));
  };

  const applyFilters = () => {
    setAppliedFilters(tempFilters);
    setIsFilterModalOpen(false);
    // Fetch will be triggered by useEffect on appliedFilters change or we call it here
    // Better to call it here to reset page to 1
    fetchInvoices(undefined, tempFilters);
  };

  const clearFilters = () => {
    const emptyFilters = {
      invoice_number: '',
      part_number: '',
      date: '',
      qty: '',
      dollar_rate: '',
      dollar_total: '',
      inr_rate: '',
      inr_total: '',
      conversion_rate: '',
      invoice_qty: ''
    };
    setTempFilters(emptyFilters);
    setAppliedFilters(emptyFilters);
    fetchInvoices(undefined, emptyFilters);
  };



  const getSortIcon = (key: keyof InvoiceItem) => {
    if (sortConfig.key !== key) {
      return '↕️';
    }
    return sortConfig.direction === 'asc' ? '↑' : '↓';
  };

  const fetchInvoices = useCallback(async (pageUrl?: string, activeFilters = appliedFilters) => {
    try {
      setIsLoading(true);
      setError('');

      // Build query params from active filters for server-side filtering
      let queryParams = new URLSearchParams();

      // If pageUrl is provided, it might already have params. But we usually use pageUrl for Next/Prev which has everything.
      // If pageUrl is NOT provided, we build from filters.

      if (!pageUrl) {
        if (activeFilters.invoice_number) queryParams.append('invoice_number', activeFilters.invoice_number);
        if (activeFilters.part_number) queryParams.append('part_number', activeFilters.part_number);
        if (activeFilters.date) queryParams.append('date', activeFilters.date);
        if (activeFilters.qty) queryParams.append('qty', activeFilters.qty);
        if (activeFilters.invoice_qty) queryParams.append('invoice_qty', activeFilters.invoice_qty);
        if (activeFilters.dollar_rate) queryParams.append('dollar_rate', activeFilters.dollar_rate);
        if (activeFilters.dollar_total) queryParams.append('dollar_total', activeFilters.dollar_total);
        if (activeFilters.inr_rate) queryParams.append('inr_rate', activeFilters.inr_rate);
        if (activeFilters.inr_total) queryParams.append('inr_total', activeFilters.inr_total);
        if (activeFilters.conversion_rate) queryParams.append('conversion_rate', activeFilters.conversion_rate);
      }

      const queryString = queryParams.toString();
      const dbArg = pageUrl ? pageUrl : (queryString ? `?${queryString}` : undefined);

      const data = await invoiceService.getInvoices(dbArg);

      // Handle paginated response format
      let results: InvoiceItem[] = [];
      let nextLink: string | null = null;
      let prevLink: string | null = null;
      let count = 0;

      if (data && typeof data === 'object') {
        // Standard DRF pagination
        if ('results' in data && Array.isArray((data as any).results)) {
          results = (data as any).results;
          nextLink = (data as any).next;
          prevLink = (data as any).previous;
          count = (data as any).count;
        } else if ('data' in data && Array.isArray((data as any).data)) {
          results = (data as any).data;
          nextLink = (data as any).next;
          prevLink = (data as any).previous;
          count = (data as any).count;
        } else if (Array.isArray(data)) {
          results = data as InvoiceItem[];
          count = results.length;
        }
      }

      setInvoices(results);
      setPagination({
        next: nextLink,
        previous: prevLink,
        count: count
      });

    } catch (error) {
      console.error('Error fetching invoices:', error);
      setError('Failed to fetch invoices. Please try again.');
      setInvoices([]);
    } finally {
      setIsLoading(false);
    }
  }, [appliedFilters, navigate]); // depend on appliedFilters so if it changes we can re-fetch? No, we call fetch manually on apply.

  // Initial fetch
  useEffect(() => {
    fetchInvoices();
  }, []); // Only mount

  const handleNextPage = () => {
    if (pagination.next) {
      // pagination.next is a full URL usually from DRF (http://localhost:8000/api/...?page=2)
      // getInvoices(string) expects a relative URL or full URL depending on implementation.
      // apiService.getInvoices handles "pageUrl.split('?')" logic so it expects the FULL url or at least the query selection.
      // We pass the full URL string, apiService logic will strip params.
      fetchInvoices(pagination.next);
    }
  };

  const handlePreviousPage = () => {
    if (pagination.previous) {
      fetchInvoices(pagination.previous);
    }
  };

  const getCurrentPageNumber = (): number => {
    if (pagination.next) {
      const match = pagination.next.match(/[?&]page=(\d+)/);
      if (match) return parseInt(match[1]) - 1;
    }
    if (pagination.previous) {
      const match = pagination.previous.match(/[?&]page=(\d+)/);
      if (match) return parseInt(match[1]) + 1;
    }
    return 1;
  };

  const handleRefresh = () => {
    fetchInvoices(undefined, appliedFilters);
  };

  const currentPage = getCurrentPageNumber();
  const formatNumber = (num: string | number) => {
    const numValue = typeof num === 'string' ? parseFloat(num) : num;
    return numValue.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  };

  return (
    <div className="invoice-details-container">
      <header className="invoice-details-header">
        <div className="header-content">
          <h1>Invoice Details</h1>
          <div className="header-actions">
            <Button onClick={handleRefresh} variant="outline" size="sm" disabled={isLoading}>
              Refresh
            </Button>
            <Button onClick={() => navigate('/dashboard')} variant="outline" size="sm">
              Back to Dashboard
            </Button>
          </div>
        </div>
      </header>

      <main className="invoice-details-main">
        <div className="invoice-details-content">
          {isLoading ? (
            <Loading message="Loading invoices..." />
          ) : error ? (
            <div className="error-container" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '400px' }}>
              <div className="error-icon">⚠️</div>
              <div className="error-text">{error}</div>
              <Button onClick={handleRefresh} variant="outline" size="sm">
                Try Again
              </Button>
            </div>
          ) : (
            <>
              {/* Header row with label on left and filters button on right */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                <h2 style={{ margin: 0 }}>All Invoice Details</h2>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  {(pagination.count > 0) && <span className="text-sm text-gray-500">Total: {pagination.count}</span>}
                  <Button onClick={() => setIsFilterModalOpen(true)} variant="outline" size="sm">
                    🔍 Filters
                  </Button>
                </div>
              </div>

              <div className="table-container">
                {sortedInvoices.length === 0 ? (
                  <div className="empty-state">
                    <p>No invoices found matching your filters.</p>
                    <Button onClick={clearFilters} variant="outline">
                      Clear Filters
                    </Button>
                  </div>
                ) : (
                  <>
                    <table className="invoice-table">
                      <thead>
                        <tr>
                          <th className="sortable-header" onClick={() => handleSort('invoice_number')}>Invoice # {getSortIcon('invoice_number')}</th>
                          <th className="sortable-header" onClick={() => handleSort('customer_name')}>Customer Name {getSortIcon('customer_name')}</th>
                          <th className="sortable-header" onClick={() => handleSort('customer_code')}>Customer Code {getSortIcon('customer_code')}</th>
                          <th className="sortable-header" onClick={() => handleSort('part_number')}>Part # {getSortIcon('part_number')}</th>
                          <th className="sortable-header" onClick={() => handleSort('date')}>Date {getSortIcon('date')}</th>
                          <th className="sortable-header" onClick={() => handleSort('invoice_qty')}>Inv Qty {getSortIcon('invoice_qty')}</th>
                          <th className="sortable-header" onClick={() => handleSort('qty')}>Rem Qty {getSortIcon('qty')}</th>
                          <th className="sortable-header" onClick={() => handleSort('dollar_rate')}>$ Rate {getSortIcon('dollar_rate')}</th>
                          <th className="sortable-header" onClick={() => handleSort('dollar_total')}>$ Total {getSortIcon('dollar_total')}</th>
                          <th className="sortable-header" onClick={() => handleSort('inr_rate')}>₹ Rate {getSortIcon('inr_rate')}</th>
                          <th className="sortable-header" onClick={() => handleSort('inr_total')}>₹ Total {getSortIcon('inr_total')}</th>
                          <th className="sortable-header">Bal $</th>
                          <th className="sortable-header">Bal ₹</th>
                          <th className="sortable-header" onClick={() => handleSort('conversion_rate')}>Conv. {getSortIcon('conversion_rate')}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {sortedInvoices.map((row) => (
                          <tr key={row.id}>
                            <td>{row.invoice_number}</td>
                            <td>{row.customer_name || "-"}</td>
                            <td>{row.customer_code || "-"}</td>
                            <td>{row.part_number}</td>
                            <td>{row.date}</td>
                            <td>{row.invoice_qty}</td>
                            <td>{row.qty}</td>
                            <td>${formatNumber(row.dollar_rate)}</td>
                            <td>${formatNumber(row.dollar_total)}</td>
                            <td>₹{formatNumber(row.inr_rate)}</td>
                            <td>₹{formatNumber(row.inr_total)}</td>
                            <td>${formatNumber(row.qty * parseFloat(String(row.dollar_rate)))}</td>
                            <td>₹{formatNumber(row.qty * parseFloat(String(row.inr_rate)))}</td>
                            <td>{formatNumber(row.conversion_rate)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>

                    {/* Pagination Controls */}
                    <div className="pagination-controls">
                      <div className="pagination-info">
                        <span>Page {currentPage}</span>
                        <span>•</span>
                        <span>{sortedInvoices.length} items</span>
                      </div>
                      <div className="pagination-buttons">
                        <Button onClick={handlePreviousPage} variant="outline" size="sm" disabled={!pagination.previous || isLoading}>
                          ← Previous
                        </Button>
                        <Button onClick={handleNextPage} variant="outline" size="sm" disabled={!pagination.next || isLoading}>
                          Next →
                        </Button>
                      </div>
                    </div>
                  </>
                )}
              </div>
            </>
          )}
        </div>
      </main>

      {/* Filters Modal */}
      <Modal isOpen={isFilterModalOpen} onClose={() => setIsFilterModalOpen(false)} title="Filter Invoices">
        <div className="filter-grid">
          <div className="filter-item">
            <Label htmlFor="invoice-filter">Invoice Number</Label>
            <Input id="invoice-filter" value={tempFilters.invoice_number} onChange={(e) => handleFilterChange('invoice_number', e.target.value)} placeholder="Contains..." />
          </div>
          <div className="filter-item">
            <Label htmlFor="part-filter">Part Number</Label>
            <Input id="part-filter" value={tempFilters.part_number} onChange={(e) => handleFilterChange('part_number', e.target.value)} placeholder="Contains..." />
          </div>
          <div className="filter-item">
            <Label htmlFor="date-filter">Date</Label>
            <Input id="date-filter" value={tempFilters.date} onChange={(e) => handleFilterChange('date', e.target.value)} placeholder="YYYY-MM-DD" />
          </div>
          <div className="filter-item">
            <Label htmlFor="qty-filter">Remaining Qty</Label>
            <Input id="qty-filter" value={tempFilters.qty} onChange={(e) => handleFilterChange('qty', e.target.value)} placeholder="Exact match..." />
          </div>
          <div className="filter-item">
            <Label htmlFor="dollar-rate-filter">$ Rate</Label>
            <Input id="dollar-rate-filter" value={tempFilters.dollar_rate} onChange={(e) => handleFilterChange('dollar_rate', e.target.value)} placeholder="Exact match..." />
          </div>
          <div className="filter-item">
            <Label htmlFor="dollar-total-filter">$ Total</Label>
            <Input id="dollar-total-filter" value={tempFilters.dollar_total} onChange={(e) => handleFilterChange('dollar_total', e.target.value)} placeholder="Exact match..." />
          </div>
          <div className="filter-item">
            <Label htmlFor="inr-rate-filter">INR Rate</Label>
            <Input id="inr-rate-filter" value={tempFilters.inr_rate} onChange={(e) => handleFilterChange('inr_rate', e.target.value)} placeholder="Exact match..." />
          </div>
          <div className="filter-item">
            <Label htmlFor="inr-total-filter">INR Total</Label>
            <Input id="inr-total-filter" value={tempFilters.inr_total} onChange={(e) => handleFilterChange('inr_total', e.target.value)} placeholder="Exact match..." />
          </div>
        </div>

        <div className="filter-actions" style={{ marginTop: '1.5rem', display: 'flex', justifyContent: 'flex-end', gap: '1rem' }}>
          <Button onClick={clearFilters} variant="outline">Reset All</Button>
          <Button onClick={applyFilters} style={{ backgroundColor: '#2563eb', color: 'white' }}>Apply Filters</Button>
        </div>
      </Modal>

      <Footer />
    </div>
  );
};

export default InvoiceDetailsPage; 