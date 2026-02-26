import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { apiService } from '@/services/apiService';
import type { InputtedEntry } from '@/services/apiService';
import './InputtedEntriesPage.css';
import Modal from '@/components/ui/modal';
import Loading from '@/components/ui/loading';
import Footer from '@/components/Footer';

interface SortConfig {
  key: keyof InputtedEntry | null;
  direction: 'asc' | 'desc';
}

interface Filters {
  id: string;
  part_number: string;
  date: string;
  qty: string;
  usd_rate: string;
  usd_total: string;
  inr_rate: string;
  inr_total: string;
  conversion_rate: string;
}

// Typed helper for various possible paginated response shapes that the API might return.
type PaginatedInputtedEntries = {
  next?: string | null;
  previous?: string | null;
  count?: number;
  total?: number;
  data?: InputtedEntry[];
  results?: InputtedEntry[];
  items?: InputtedEntry[];
  entries?: InputtedEntry[];
};

const InputtedEntriesPage: React.FC = () => {
  const navigate = useNavigate();
  const [entries, setEntries] = useState<InputtedEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pagination, setPagination] = useState({
    next: null as string | null,
    previous: null as string | null,
    count: 0
  });

  // Filter and sort state
  const [filters, setFilters] = useState<Filters>({
    id: '',
    part_number: '',
    date: '',
    qty: '',
    usd_rate: '',
    usd_total: '',
    inr_rate: '',
    inr_total: '',
    conversion_rate: ''
  });
  const [sortConfig, setSortConfig] = useState<SortConfig>({
    key: null,
    direction: 'asc'
  });
  const [isFilterModalOpen, setIsFilterModalOpen] = useState(false);

  // Filter and sort the entries
  const filteredAndSortedEntries = useMemo(() => {
    const filtered = entries.filter(entry => {
      return (
        entry.id.toString().includes(filters.id) &&
        entry.part_number.toLowerCase().includes(filters.part_number.toLowerCase()) &&
        entry.date.toLowerCase().includes(filters.date.toLowerCase()) &&
        entry.qty.toString().includes(filters.qty) &&
        entry.usd_rate.toString().includes(filters.usd_rate) &&
        entry.usd_total.toString().includes(filters.usd_total) &&
        entry.inr_rate.toString().includes(filters.inr_rate) &&
        entry.inr_total.toString().includes(filters.inr_total) &&
        entry.conversion_rate.toString().includes(filters.conversion_rate)
      );
    });

    // Sort the filtered data
    if (sortConfig.key) {
      filtered.sort((a, b) => {
        const aValue = a[sortConfig.key!];
        const bValue = b[sortConfig.key!];
        
        let comparison = 0;
        
        if (typeof aValue === 'string' && typeof bValue === 'string') {
          comparison = aValue.localeCompare(bValue);
        } else if (typeof aValue === 'number' && typeof bValue === 'number') {
          comparison = aValue - bValue;
        } else {
          // Convert to string for comparison
          comparison = String(aValue).localeCompare(String(bValue));
        }
        
        return sortConfig.direction === 'asc' ? comparison : -comparison;
      });
    }

    return filtered;
  }, [entries, filters, sortConfig]);

  const handleSort = (key: keyof InputtedEntry) => {
    setSortConfig(prevConfig => ({
      key,
      direction: prevConfig.key === key && prevConfig.direction === 'asc' ? 'desc' : 'asc'
    }));
  };

  const handleFilterChange = (key: keyof Filters, value: string) => {
    setFilters(prev => ({
      ...prev,
      [key]: value
    }));
  };

  const clearFilters = () => {
    setFilters({
      id: '',
      part_number: '',
      date: '',
      qty: '',
      usd_rate: '',
      usd_total: '',
      inr_rate: '',
      inr_total: '',
      conversion_rate: ''
    });
  };

  const clearSort = () => {
    setSortConfig({
      key: null,
      direction: 'asc'
    });
  };

  const getSortIcon = (key: keyof InputtedEntry) => {
    if (sortConfig.key !== key) {
      return '↕️';
    }
    return sortConfig.direction === 'asc' ? '↑' : '↓';
  };

  // Fetch inputted entries from API
  const fetchInputtedEntries = async (pageUrl?: string) => {
    try {
      setLoading(true);
      setError(null);    
      
      // Use the central API service with pagination support
      const data = await apiService.getInputtedEntries(pageUrl);
      
      // Handle paginated response format (multiple shapes supported)
      if (
        data &&
        typeof data === 'object' &&
        'data' in (data as PaginatedInputtedEntries) &&
        Array.isArray((data as PaginatedInputtedEntries).data)
      ) {
        const paginatedData = data as PaginatedInputtedEntries;
        setEntries(paginatedData.data ?? []);
        setPagination({
          next: paginatedData.next ?? null,
          previous: paginatedData.previous ?? null,
          count: paginatedData.count ?? paginatedData.data?.length ?? 0
        });
      } else if (
        data &&
        typeof data === 'object' &&
        'results' in (data as PaginatedInputtedEntries) &&
        Array.isArray((data as PaginatedInputtedEntries).results)
      ) {
        // Handle Django REST framework pagination format
        const paginatedData = data as PaginatedInputtedEntries;
        setEntries(paginatedData.results ?? []);
        setPagination({
          next: paginatedData.next ?? null,
          previous: paginatedData.previous ?? null,
          count: paginatedData.count ?? paginatedData.results?.length ?? 0
        });
      } else if (Array.isArray(data)) {
        // Fallback for non-paginated response
        setEntries(data);
        setPagination({
          next: null,
          previous: null,
          count: data.length
        });
      } else if (data && typeof data === 'object') {
        // Try to extract data from various possible structures
        const possibleDataKeys = ['data', 'results', 'items', 'entries'] as const;
        let foundData: InputtedEntry[] | null = null;
        
        for (const key of possibleDataKeys) {
          if (
            key in (data as PaginatedInputtedEntries) &&
            Array.isArray((data as PaginatedInputtedEntries)[key])
          ) {
            foundData = (data as PaginatedInputtedEntries)[key] as InputtedEntry[];
            break;
          }
        }
        
        if (foundData) {
          setEntries(foundData);
          setPagination({
            next: (data as PaginatedInputtedEntries).next ?? null,
            previous: (data as PaginatedInputtedEntries).previous ?? null,
            count: (data as PaginatedInputtedEntries).count ?? (data as PaginatedInputtedEntries).total ?? foundData.length
          });
        } else {
          console.error('Unexpected response format:', data);
          setError('Invalid response format from server');
          setEntries([]);
          setPagination({
            next: null,
            previous: null,
            count: 0
          });
        }
      } else {
        console.error('Unexpected response format:', data);
        setError('Invalid response format from server');
        setEntries([]);
        setPagination({
          next: null,
          previous: null,
          count: 0
        });
      }
    } catch (err) {
      console.error('Error fetching inputted entries:', err);
      
      // Check if it's a network/server error
      if (err instanceof Error && (
        err.message.includes('404') || 
        err.message.includes('Failed to fetch') ||
        err.message.includes('CORS') ||
        err.message.includes('NetworkError')
      )) {
        setError('Unable to connect to the server. This may be due to CORS policy or network issues. Please check your connection and try again.');
      } else {
        setError(err instanceof Error ? err.message : 'Failed to fetch inputted entries');
      }
      
      setEntries([]);
      setPagination({
        next: null,
        previous: null,
        count: 0
      });
    } finally {
      setLoading(false);
    }
  };

  const handleNextPage = () => {
    if (pagination.next) {
      fetchInputtedEntries(pagination.next);
    }
  };

  const handlePreviousPage = () => {
    if (pagination.previous) {
      fetchInputtedEntries(pagination.previous);
    }
  };

  const getCurrentPageNumber = (): number => {
    if (pagination.next) {
      // Extract page number from next URL
      const match = pagination.next.match(/[?&]page=(\d+)/);
      if (match) {
        return parseInt(match[1]) - 1; // Next page - 1 = current page
      }
    }
    if (pagination.previous) {
      // Extract page number from previous URL
      const match = pagination.previous.match(/[?&]page=(\d+)/);
      if (match) {
        return parseInt(match[1]) + 1; // Previous page + 1 = current page
      }
    }
    return 1; // Default to page 1
  };

  useEffect(() => {
    fetchInputtedEntries();
  }, []);

  const handleBackToDashboard = () => {
    navigate('/dashboard');
  };

  const handleRefresh = () => {
    fetchInputtedEntries();
  };

  const formatCurrency = (amount: string, currency: string) => {
    const num = parseFloat(amount) || 0;
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency === 'USD' ? 'USD' : 'INR',
      minimumFractionDigits: 2
    }).format(num);
  };

  const formatDateOnly = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    });
  };

  // Calculate summary statistics
  const stats = {
    total: pagination.count || entries.length,
    totalQty: entries.reduce((sum, entry) => sum + entry.qty, 0),
    totalUsdValue: entries.reduce((sum, entry) => sum + parseFloat(entry.usd_total || '0'), 0),
    totalInrValue: entries.reduce((sum, entry) => sum + parseFloat(entry.inr_total || '0'), 0)
  };

  // Toggle to display/hide top statistics row
  const showStats = false;

  const currentPage = getCurrentPageNumber();

  return (
    <div className="inputted-entries-container">
      <header className="inputted-entries-header">
        <div className="header-content">
          <h1>Inputted Entries</h1>
          <div className="header-actions">
            <Button onClick={handleRefresh} variant="outline" size="sm" disabled={loading}>
              Refresh
            </Button>
            <Button onClick={handleBackToDashboard} variant="outline" size="sm">
              Back to Dashboard
            </Button>
          </div>
        </div>
      </header>

      <main className="inputted-entries-main">
        <div className="inputted-entries-content">
          {loading ? (
            <Loading message="Loading inputted entries..." />
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
              {/* Summary Statistics (hidden via showStats flag) */}
              {showStats && (
                <div className="stats-overview">
                  <div className="stat-card">
                    <div className="stat-icon">📄</div>
                    <div className="stat-content">
                      <div className="stat-value">{stats.total}</div>
                      <div className="stat-label">Total Entries</div>
                    </div>
                  </div>
                  
                  <div className="stat-card">
                    <div className="stat-icon">📦</div>
                    <div className="stat-content">
                      <div className="stat-value">{stats.totalQty}</div>
                      <div className="stat-label">Total Quantity</div>
                    </div>
                  </div>
                  
                  <div className="stat-card">
                    <div className="stat-icon">💵</div>
                    <div className="stat-content">
                      <div className="stat-value">{formatCurrency(stats.totalUsdValue.toString(), 'USD')}</div>
                      <div className="stat-label">Total USD Value</div>
                    </div>
                  </div>
                  
                  <div className="stat-card">
                    <div className="stat-icon">₹</div>
                    <div className="stat-content">
                      <div className="stat-value">{formatCurrency(stats.totalInrValue.toString(), 'INR')}</div>
                      <div className="stat-label">Total INR Value</div>
                    </div>
                  </div>
                </div>
              )}

              {/* Header row with label on left and filters button on right */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                <h2 style={{ margin: 0 }}>All Inputted Entries</h2>
                <Button onClick={() => setIsFilterModalOpen(true)} variant="outline" size="sm">
                  🔍 Filters
                </Button>
              </div>

              {/* Entries List */}
              <div className="entries-list">
                {filteredAndSortedEntries.length === 0 ? (
                  <div className="no-entries">
                    <div className="no-entries-icon">📝</div>
                    <div className="no-entries-text">
                      {entries.length === 0 ? 'No inputted entries found' : 'No entries match your filters'}
                    </div>
                    <Button onClick={clearFilters} variant="outline" size="sm">
                      Clear Filters
                    </Button>
                  </div>
                ) : (
                  <>
                    <div className="entries-table-container">
                      <table className="entries-table">
                        <thead>
                          <tr>
                            <th 
                              className="sortable-header"
                              onClick={() => handleSort('id')}
                            >
                              ID {getSortIcon('id')}
                            </th>
                            <th 
                              className="sortable-header"
                              onClick={() => handleSort('part_number')}
                            >
                              Part Number {getSortIcon('part_number')}
                            </th>
                            <th 
                              className="sortable-header"
                              onClick={() => handleSort('date')}
                            >
                              Date {getSortIcon('date')}
                            </th>
                            <th 
                              className="sortable-header"
                              onClick={() => handleSort('qty')}
                            >
                              Quantity {getSortIcon('qty')}
                            </th>
                            <th 
                              className="sortable-header"
                              onClick={() => handleSort('usd_rate')}
                            >
                              USD Rate {getSortIcon('usd_rate')}
                            </th>
                            <th 
                              className="sortable-header"
                              onClick={() => handleSort('inr_rate')}
                            >
                              INR Rate {getSortIcon('inr_rate')}
                            </th>
                            <th 
                              className="sortable-header"
                              onClick={() => handleSort('conversion_rate')}
                            >
                              Conversion Rate {getSortIcon('conversion_rate')}
                            </th>
                            <th 
                              className="sortable-header"
                              onClick={() => handleSort('usd_total')}
                            >
                              USD Total {getSortIcon('usd_total')}
                            </th>
                            <th 
                              className="sortable-header"
                              onClick={() => handleSort('inr_total')}
                            >
                              INR Total {getSortIcon('inr_total')}
                            </th>
                          </tr>
                        </thead>
                        <tbody>
                          {filteredAndSortedEntries.map((entry) => (
                            <tr key={entry.id} className="entry-row">
                              <td className="entry-id">{entry.id}</td>
                              <td className="part-number">{entry.part_number}</td>
                              <td className="entry-date">{formatDateOnly(entry.date)}</td>
                              <td className="quantity">{entry.qty}</td>
                              <td className="usd-rate">{formatCurrency(entry.usd_rate, 'USD')}</td>
                              <td className="inr-rate">{formatCurrency(entry.inr_rate, 'INR')}</td>
                              <td className="conversion-rate">{parseFloat(entry.conversion_rate).toFixed(4)}</td>
                              <td className="usd-total">{formatCurrency(entry.usd_total, 'USD')}</td>
                              <td className="inr-total">{formatCurrency(entry.inr_total, 'INR')}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    
                    {/* Pagination Controls */}
                    <div className="pagination-controls">
                      <div className="pagination-info">
                        <span>Page {currentPage}</span>
                        <span>•</span>
                        <span>{filteredAndSortedEntries.length} of {pagination.count} entries</span>
                      </div>
                      <div className="pagination-buttons">
                        <Button
                          onClick={handlePreviousPage}
                          variant="outline"
                          size="sm"
                          disabled={!pagination.previous || loading}
                        >
                          ← Previous
                        </Button>
                        <Button
                          onClick={handleNextPage}
                          variant="outline"
                          size="sm"
                          disabled={!pagination.next || loading}
                        >
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
      <Modal isOpen={isFilterModalOpen} onClose={() => setIsFilterModalOpen(false)} title="Filters">
        <div className="filter-actions" style={{ marginBottom: '1rem', display: 'flex', gap: '0.5rem' }}>
          <Button onClick={clearFilters} variant="outline" size="sm">
            Clear Filters
          </Button>
          <Button onClick={clearSort} variant="outline" size="sm">
            Clear Sort
          </Button>
        </div>
        <div className="filter-grid">
          <div className="filter-item">
            <Label htmlFor="id-filter">ID</Label>
            <Input
              id="id-filter"
              value={filters.id}
              onChange={(e) => handleFilterChange('id', e.target.value)}
              placeholder="Filter by ID..."
            />
          </div>
          <div className="filter-item">
            <Label htmlFor="part-filter">Part Number</Label>
            <Input
              id="part-filter"
              value={filters.part_number}
              onChange={(e) => handleFilterChange('part_number', e.target.value)}
              placeholder="Filter by part number..."
            />
          </div>
          <div className="filter-item">
            <Label htmlFor="date-filter">Date</Label>
            <Input
              id="date-filter"
              value={filters.date}
              onChange={(e) => handleFilterChange('date', e.target.value)}
              placeholder="Filter by date..."
            />
          </div>
          <div className="filter-item">
            <Label htmlFor="qty-filter">Quantity</Label>
            <Input
              id="qty-filter"
              value={filters.qty}
              onChange={(e) => handleFilterChange('qty', e.target.value)}
              placeholder="Filter by quantity..."
            />
          </div>
          <div className="filter-item">
            <Label htmlFor="usd-rate-filter">USD Rate</Label>
            <Input
              id="usd-rate-filter"
              value={filters.usd_rate}
              onChange={(e) => handleFilterChange('usd_rate', e.target.value)}
              placeholder="Filter by USD rate..."
            />
          </div>
          <div className="filter-item">
            <Label htmlFor="usd-total-filter">USD Total</Label>
            <Input
              id="usd-total-filter"
              value={filters.usd_total}
              onChange={(e) => handleFilterChange('usd_total', e.target.value)}
              placeholder="Filter by USD total..."
            />
          </div>
          <div className="filter-item">
            <Label htmlFor="inr-rate-filter">INR Rate</Label>
            <Input
              id="inr-rate-filter"
              value={filters.inr_rate}
              onChange={(e) => handleFilterChange('inr_rate', e.target.value)}
              placeholder="Filter by INR rate..."
            />
          </div>
          <div className="filter-item">
            <Label htmlFor="inr-total-filter">INR Total</Label>
            <Input
              id="inr-total-filter"
              value={filters.inr_total}
              onChange={(e) => handleFilterChange('inr_total', e.target.value)}
              placeholder="Filter by INR total..."
            />
          </div>
          <div className="filter-item">
            <Label htmlFor="conversion-rate-filter">Conversion Rate</Label>
            <Input
              id="conversion-rate-filter"
              value={filters.conversion_rate}
              onChange={(e) => handleFilterChange('conversion_rate', e.target.value)}
              placeholder="Filter by conversion rate..."
            />
          </div>
        </div>
        <div className="filter-summary" style={{ marginTop: '1rem' }}>
          <span>Showing {filteredAndSortedEntries.length} of {entries.length} entries</span>
          {sortConfig.key && (
            <span>• Sorted by {sortConfig.key} ({sortConfig.direction})</span>
          )}
        </div>
      </Modal>

      <Footer />
    </div>
  );
};

export default InputtedEntriesPage; 