import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { apiService } from '@/services/apiService';
import type { ReconciledInvoice } from '@/services/apiService';
import Modal from '@/components/ui/modal';
import Loading from '@/components/ui/loading';
import DownloadExcelButton from '@/components/DownloadExcelButton';
import Footer from '@/components/Footer';
import './ReconciliationsPage.css';

interface ReconciliationMatch {
  supplierSaleId: string;
  supplierSaleQty: number;
  invoiceId: string;
  invoiceNumber: string;
  partNumber: string;
  invoiceQty: number;
  reconciledQty: number;
  remainingQty: number;
  status: 'full' | 'partial' | 'pending';
  date: string;
  profitAbsolute: string;
  profitSellingRate: string;
  profitFxRate: string;
  sellingPriceInr: string;
}

interface InvoiceGroup {
  invoiceId: string;
  invoiceNumber: string;
  date: string;
  partNumbers: ReconciliationMatch[];
  totalProfitAbsolute: number;
  totalProfitSellingRate: number;
  totalProfitFxRate: number;
}

const ReconciliationsPage: React.FC = () => {
  const navigate = useNavigate();

  const [filterStatus, setFilterStatus] = useState<'all' | 'full' | 'partial' | 'pending'>('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [reconciliationMatches, setReconciliationMatches] = useState<ReconciliationMatch[]>([]);
  const [invoiceGroups, setInvoiceGroups] = useState<InvoiceGroup[]>([]);
  const [reconciledInvoices, setReconciledInvoices] = useState<ReconciledInvoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedInvoices, setExpandedInvoices] = useState<Set<string>>(new Set());
  const [isFilterModalOpen, setIsFilterModalOpen] = useState(false);

  // Fetch reconciled invoices from API
  const fetchReconciledInvoices = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const data = await apiService.getReconciliations();
      console.log('data', data);
      setReconciledInvoices(data);
    } catch (err) {
      console.error('Error fetching reconciled invoices:', err);
      setError(err instanceof Error ? err.message : 'Failed to fetch reconciled invoices');
    } finally {
      setLoading(false);
    }
  };

  // Transform API data to match the existing interface
  const transformReconciledData = (invoices: ReconciledInvoice[]): ReconciliationMatch[] => {
    const matches: ReconciliationMatch[] = [];
    
    invoices.forEach((reconciledInvoice) => {
      matches.push({
        supplierSaleId: reconciledInvoice.invoice_entry.toString(),
        supplierSaleQty: reconciledInvoice.consumed_qty,
        invoiceId: reconciledInvoice.invoice.id.toString(),
        invoiceNumber: reconciledInvoice.invoice.invoice_number,
        partNumber: reconciledInvoice.invoice.part_number,
        invoiceQty: reconciledInvoice.invoice.invoice_qty,
        reconciledQty: reconciledInvoice.consumed_qty,
        remainingQty: reconciledInvoice.invoice.invoice_qty - reconciledInvoice.consumed_qty,
        status: reconciledInvoice.consumed_qty === reconciledInvoice.invoice.qty ? 'full' : 'partial',
        date: reconciledInvoice.invoice.date,
        profitAbsolute: reconciledInvoice.profit_absolute,
        profitSellingRate: reconciledInvoice.profit_selling_rate,
        profitFxRate: reconciledInvoice.profit_fx_rate,
        sellingPriceInr: reconciledInvoice.selling_price_inr
      });
    });
    
    return matches;
  };

  // Group reconciliations by invoice
  const groupByInvoice = (matches: ReconciliationMatch[]): InvoiceGroup[] => {
    const groups: { [key: string]: InvoiceGroup } = {};
    
    matches.forEach(match => {
      if (!groups[match.invoiceId]) {
        groups[match.invoiceId] = {
          invoiceId: match.invoiceId,
          invoiceNumber: match.invoiceNumber,
          date: match.date,
          partNumbers: [],
          totalProfitAbsolute: 0,
          totalProfitSellingRate: 0,
          totalProfitFxRate: 0
        };
      }
      
      groups[match.invoiceId].partNumbers.push(match);
      
      const profitAbsolute = parseFloat(match.profitAbsolute) || 0;
      const profitSellingRate = parseFloat(match.profitSellingRate) || 0;
      const profitFxRate = parseFloat(match.profitFxRate) || 0;
      
      groups[match.invoiceId].totalProfitAbsolute += profitAbsolute;
      groups[match.invoiceId].totalProfitSellingRate += profitSellingRate;
      groups[match.invoiceId].totalProfitFxRate += profitFxRate;
    });
    
    const result = Object.values(groups).sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());
    
    return result;
  };

  useEffect(() => {
    fetchReconciledInvoices();
  }, []);

  useEffect(() => {
    if (reconciledInvoices.length > 0) {
      const transformedMatches = transformReconciledData(reconciledInvoices);
      setReconciliationMatches(transformedMatches);
      const grouped = groupByInvoice(transformedMatches);
      setInvoiceGroups(grouped);
    }
  }, [reconciledInvoices]);

  const handleBackToDashboard = () => {
    navigate('/dashboard');
  };

  const handleRefresh = () => {
    fetchReconciledInvoices();
  };

  const toggleInvoiceExpansion = (invoiceId: string) => {
    const newExpanded = new Set(expandedInvoices);
    if (newExpanded.has(invoiceId)) {
      newExpanded.delete(invoiceId);
    } else {
      newExpanded.add(invoiceId);
    }
    setExpandedInvoices(newExpanded);
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'full':
        return '#10b981';
      case 'partial':
        return '#f59e0b';
      case 'pending':
        return '#6b7280';
      default:
        return '#6b7280';
    }
  };

  const getStatusText = (status: string) => {
    switch (status) {
      case 'full':
        return 'Fully Reconciled';
      case 'partial':
        return 'Partially Reconciled';
      case 'pending':
        return 'Pending';
      default:
        return 'Unknown';
    }
  };

  const formatINR = (amount: string) => {
    const num = parseFloat(amount) || 0;
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      minimumFractionDigits: 2
    }).format(num);
  };



  const filteredGroups = invoiceGroups.filter(group => {
    const matchesStatus = filterStatus === 'all' || 
      group.partNumbers.some(part => part.status === filterStatus);
    const matchesSearch = group.invoiceNumber.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         group.partNumbers.some(part => part.partNumber.toLowerCase().includes(searchTerm.toLowerCase()));
    return matchesStatus && matchesSearch;
  });

  const stats = {
    total: reconciliationMatches.length,
    fullyReconciled: reconciliationMatches.filter(match => match.status === 'full').length,
    partiallyReconciled: reconciliationMatches.filter(match => match.status === 'partial').length,
    pending: reconciliationMatches.filter(match => match.status === 'pending').length
  };



  

  return (
    <div className="reconciliations-container">
      <header className="inputted-entries-header">
        <div className="header-content">
          <h1>Reconciliation Overview</h1>
          <div className="header-actions">
            <DownloadExcelButton disabled={loading} />
            <Button onClick={handleRefresh} variant="outline" size="sm" disabled={loading}>
              Refresh
            </Button>
            <Button onClick={handleBackToDashboard} variant="outline" size="sm">
              Back to Dashboard
            </Button>
          </div>
        </div>
      </header>

      <main className="reconciliations-main">
        <div className="reconciliations-content">
          {loading ? (
            <Loading message="Loading reconciled invoices..." />
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
              <div className="stats-overview">
                <div className="stat-card">
                  <div className="stat-icon">📊</div>
                  <div className="stat-content">
                    <div className="stat-value">{stats.total}</div>
                    <div className="stat-label">Total Reconciliations</div>
                  </div>
                </div>
                
                <div className="stat-card">
                  <div className="stat-icon">✅</div>
                  <div className="stat-content">
                    <div className="stat-value">{stats.fullyReconciled}</div>
                    <div className="stat-label">Fully Reconciled</div>
                  </div>
                </div>
                
                <div className="stat-card">
                  <div className="stat-icon">🔄</div>
                  <div className="stat-content">
                    <div className="stat-value">{stats.partiallyReconciled}</div>
                    <div className="stat-label">Partially Reconciled</div>
                  </div>
                </div>
                
                <div className="stat-card">
                  <div className="stat-icon">⏳</div>
                  <div className="stat-content">
                    <div className="stat-value">{stats.pending}</div>
                    <div className="stat-label">Pending</div>
                  </div>
                </div>
              </div>

              <div className="filter-summary" style={{ marginBottom: '1.5rem', display:'flex',alignItems:'center',gap:'0.75rem' }}>
                <Button onClick={()=>setIsFilterModalOpen(true)} variant="outline" size="sm">🔍 Filters</Button>
                <span>Showing {invoiceGroups.length} invoices</span>
              </div>

              <div className="reconciliations-cards">
                {filteredGroups.map((group) => (
                  <div key={group.invoiceId} className="invoice-card">
                    {/* Invoice Header Card */}
                    <div className="invoice-header-card" onClick={() => toggleInvoiceExpansion(group.invoiceId)}>
                      <div className="invoice-header-content">
                        <div className="invoice-main-info">
                          <div className="invoice-details">
                            <h3 className="invoice-number">{group.invoiceNumber}</h3>
                            <p className="invoice-date">{group.date}</p>
                            <span className="part-count">{group.partNumbers.length} part{group.partNumbers.length !== 1 ? 's' : ''}</span>
                          </div>
                        </div>
                        
                        <div className="invoice-metrics">
                          <div className="metric-group">
                            <div className="metric-item">
                              <span className="metric-label">Qty</span>
                              <span className="metric-value">
                                {group.partNumbers.reduce((sum, part) => sum + part.invoiceQty, 0)}
                              </span>
                            </div>
                            <div className="metric-item">
                              <span className="metric-label">Reconciled</span>
                              <span className="metric-value">
                                {group.partNumbers.reduce((sum, part) => sum + part.reconciledQty, 0)}
                              </span>
                            </div>
                            <div className="metric-item">
                              <span className="metric-label">Remaining</span>
                              <span className="metric-value">
                                {group.partNumbers.reduce((sum, part) => sum + part.remainingQty, 0)}
                              </span>
                            </div>
                          </div>
                          
                          <div className="profit-summary">
                            <div className="total-profit">
                              <span className="profit-label">Total Profit</span>
                              <span className="profit-amount">
                                {formatINR(group.totalProfitAbsolute.toString())}
                              </span>
                            </div>
                            <div className="profit-breakdown">
                              <span className="breakdown-item selling">
                                Selling: {formatINR(group.totalProfitSellingRate.toString())}
                              </span>
                              <span className="breakdown-item fx">
                                FX: {formatINR(group.totalProfitFxRate.toString())}
                              </span>
                            </div>
                          </div>
                        </div>
                        
                        <div className="invoice-status-badge">
                          {group.partNumbers.every(part => part.status === 'full') ? 'Fully Reconciled' : 
                           group.partNumbers.some(part => part.status === 'partial') ? 'Partially Reconciled' : 'Pending'}
                        </div>
                        
                        <div className="expand-icon">
                          {expandedInvoices.has(group.invoiceId) ? (
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                              <path d="M7 14L12 9L17 14" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                            </svg>
                          ) : (
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                              <path d="M7 10L12 15L17 10" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                            </svg>
                          )}
                        </div>
                      </div>
                    </div>
                    
                    {/* Part Number Cards */}
                    <div className={`parts-container ${expandedInvoices.has(group.invoiceId) ? 'expanded' : ''}`}>
                      {expandedInvoices.has(group.invoiceId) && group.partNumbers.map((part, partIndex) => (
                        <div key={`${group.invoiceId}-${partIndex}`} className="part-card">
                          <div className="part-header">
                            <div className="part-info">
                              <div className="part-number-label">Part Number: {part.partNumber}</div>
                              <div className="part-date-label">Date: {part.date}</div>
                            </div>
                            <div 
                              className="status-badge"
                              style={{ backgroundColor: getStatusColor(part.status) }}
                            >
                              {getStatusText(part.status)}
                            </div>
                          </div>
                          
                          <div className="part-details">
                            <div className="detail-row">
                              <div className="detail-group">
                                <div className="detail-item">
                                  <span className="detail-label">Invoice Qty</span>
                                  <span className="detail-value">{part.invoiceQty}</span>
                                </div>
                                <div className="detail-item">
                                  <span className="detail-label">Reconciled</span>
                                  <span className="detail-value">{part.reconciledQty}</span>
                                </div>
                                <div className="detail-item">
                                  <span className="detail-label">Remaining</span>
                                  <span className="detail-value">{part.remainingQty}</span>
                                </div>
                              </div>
                              
                              <div className="detail-group">
                                <div className="detail-item">
                                  <span className="detail-label">Selling Price</span>
                                  <span className="detail-value price">{formatINR(part.sellingPriceInr)}</span>
                                </div>
                                <div className="detail-item">
                                  <span className="detail-label">Profit Absolute</span>
                                  <span className="detail-value profit">{formatINR(part.profitAbsolute)}</span>
                                </div>
                                <div className="detail-item">
                                  <span className="detail-label">Profit Selling</span>
                                  <span className="detail-value profit">{formatINR(part.profitSellingRate)}</span>
                                </div>
                                <div className="detail-item">
                                  <span className="detail-label">Profit FX</span>
                                  <span className="detail-value profit">{formatINR(part.profitFxRate)}</span>
                                </div>
                              </div>
                            </div>
                          </div>
                          
                          <div className="part-actions">
                            <Button 
                              onClick={() => {
                                // Navigate to the part reconciliations page with filters
                                navigate(`/part-reconciliations?partNumber=${encodeURIComponent(part.partNumber)}&invoiceNumber=${encodeURIComponent(part.invoiceNumber)}&date=${encodeURIComponent(part.date)}`);
                              }} 
                              variant="outline" 
                              size="sm"
                            >
                              View Reconciliations
                            </Button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>

              {filteredGroups.length === 0 && (
                <div className="no-results">
                  <div className="no-results-icon">🔍</div>
                  <div className="no-results-text">
                    No reconciliation matches found
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </main>

      <Footer />

      <Modal isOpen={isFilterModalOpen} onClose={()=>setIsFilterModalOpen(false)} title="Filters">
        <div style={{marginBottom:'1rem',display:'flex',gap:'0.5rem'}}>
          {(['all','full','partial','pending'] as const).map(status=> (
            <Button key={status} onClick={()=>setFilterStatus(status)} variant={filterStatus===status?'default':'outline'} size="sm">{status}</Button>
          ))}
        </div>
        <div className="filter-grid">
          <div className="filter-item" style={{width:'100%'}}>
            <Label htmlFor="search-filter">Search</Label>
            <Input id="search-filter" value={searchTerm} onChange={(e: React.ChangeEvent<HTMLInputElement>)=>setSearchTerm(e.target.value)} placeholder="Search by invoice number or part number..." />
          </div>
        </div>
      </Modal>
    </div>
  );
};

export default ReconciliationsPage; 