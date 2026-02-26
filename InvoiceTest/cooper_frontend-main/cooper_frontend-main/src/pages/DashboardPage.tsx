import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { invoiceService } from '@/services/invoiceService';
import type { RetailInvoiceResponse, AvailableInvoice, SelectedInvoice, RetailInvoiceRequestWithSelection } from '@/services/apiService';
import { apiService } from '@/services/apiService';
import { authService } from '@/services/authService';
import { Menu, X } from 'lucide-react';
import DashboardStats from '@/components/DashboardStats';
import Footer from '@/components/Footer';
import InvoiceSelectionModal from '@/components/InvoiceSelectionModal';
import BulkUploadStaging from '@/components/BulkUploadStaging';
import './DashboardPage.css';

const DashboardPage: React.FC = () => {
  const navigate = useNavigate();
  const [formData, setFormData] = useState({
    partNumber: '',
    date: '',
    documentQty: '',
    documentUnitRate: '',
    documentTotal: '',
    documentCurrency: '$',
    retailInvoiceNumber: '',
    reportingRate: '',
    reportingTotal: '',
    reportingCurrency: 'INR',
    conversionRate: ''
  });

  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitStatus, setSubmitStatus] = useState<'idle' | 'success' | 'error'>('idle');
  const [submitMessage, setSubmitMessage] = useState('');
  const [createdInvoice, setCreatedInvoice] = useState<RetailInvoiceResponse | null>(null);

  // Invoice selection modal state
  const [showSelectionModal, setShowSelectionModal] = useState(false);
  const [availableInvoices, setAvailableInvoices] = useState<AvailableInvoice[]>([]);
  const [isLoadingInvoices, setIsLoadingInvoices] = useState(false);

  /* New State for Stock Ledger Modal */
  const [isLedgerModalOpen, setIsLedgerModalOpen] = useState(false);
  const [ledgerStartDate, setLedgerStartDate] = useState('');
  const [ledgerEndDate, setLedgerEndDate] = useState('');

  const [bulkUploadFile, setBulkUploadFile] = useState<File | null>(null);
  const bulkFileRef = React.useRef<HTMLInputElement>(null);



  // Calculate document total when quantity or unit rate changes
  useEffect(() => {
    const qty = parseFloat(formData.documentQty) || 0;
    const unitRate = parseFloat(formData.documentUnitRate) || 0;
    const total = qty * unitRate;
    setFormData(prev => ({
      ...prev,
      documentTotal: total.toFixed(2)
    }));
  }, [formData.documentQty, formData.documentUnitRate]);

  // Calculate reporting rate when document unit rate or conversion rate changes
  useEffect(() => {
    const unitRate = parseFloat(formData.documentUnitRate) || 0;
    const conversionRate = parseFloat(formData.conversionRate) || 0;
    const reportingRate = unitRate * conversionRate;
    setFormData(prev => ({
      ...prev,
      reportingRate: reportingRate.toFixed(2)
    }));
  }, [formData.documentUnitRate, formData.conversionRate]);

  // Calculate reporting total when reporting rate or quantity changes
  useEffect(() => {
    const qty = parseFloat(formData.documentQty) || 0;
    const reportingRate = parseFloat(formData.reportingRate) || 0;
    const reportingTotal = qty * reportingRate;
    setFormData(prev => ({
      ...prev,
      reportingTotal: reportingTotal.toFixed(2)
    }));
  }, [formData.reportingRate, formData.documentQty]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    const { name } = e.currentTarget;

    // Allow: backspace, delete, tab, escape, enter, home, end, left, right arrows
    if ([8, 9, 27, 13, 46, 35, 36, 37, 39].indexOf(e.keyCode) !== -1 ||
      // Allow: Ctrl+A, Ctrl+C, Ctrl+V, Ctrl+X, Ctrl+Z
      (e.keyCode === 65 && e.ctrlKey === true) ||
      (e.keyCode === 67 && e.ctrlKey === true) ||
      (e.keyCode === 86 && e.ctrlKey === true) ||
      (e.keyCode === 88 && e.ctrlKey === true) ||
      (e.keyCode === 90 && e.ctrlKey === true)) {
      return;
    }

    // For Document Qty - ONLY allow digits (0-9)
    if (name === 'documentQty') {
      // Block all special characters, letters, symbols, and shift key combinations
      if (e.shiftKey ||
        !((e.keyCode >= 48 && e.keyCode <= 57) || (e.keyCode >= 96 && e.keyCode <= 105))) {
        e.preventDefault();
      }
    }
    // For Document Unit Rate and Conversion Rate - ONLY allow digits and decimal point
    else if (name === 'documentUnitRate' || name === 'conversionRate') {
      const currentValue = e.currentTarget.value;

      // Block shift key combinations (which create special characters)
      if (e.shiftKey) {
        e.preventDefault();
        return;
      }

      // Allow digits from main keyboard (48-57) and numpad (96-105)
      if ((e.keyCode >= 48 && e.keyCode <= 57) || (e.keyCode >= 96 && e.keyCode <= 105)) {
        return;
      }

      // Allow decimal point ONLY if there isn't one already
      // 190 = main keyboard period, 110 = numpad decimal
      if ((e.keyCode === 190 || e.keyCode === 110)) {
        // Check if decimal point already exists
        const decimalCount = (currentValue.match(/\./g) || []).length;
        if (decimalCount === 0) {
          return; // Allow first decimal point
        } else {
          e.preventDefault(); // Block additional decimal points
          return;
        }
      }

      // Block ALL other keys including:
      // - Letters (A-Z)
      // - Special characters (!@#$%^&*()_+-=[]{}|;:'"<>?,/)
      // - Function keys
      // - Any other symbols
      e.preventDefault();
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;

    // Final validation layer - block ALL special characters except decimal point
    if (name === 'documentQty') {
      // Only allow positive integers (digits only, NO special characters)
      if (value !== '' && (!/^\d+$/.test(value) || parseInt(value) <= 0)) {
        return;
      }
    } else if (name === 'documentUnitRate' || name === 'conversionRate') {
      // Only allow positive decimal numbers (digits and ONE decimal point only)
      // Block ALL special characters except decimal point
      const decimalCount = (value.match(/\./g) || []).length;
      if (value !== '' &&
        (!/^\d*\.?\d*$/.test(value) ||
          (value !== '.' && parseFloat(value) <= 0) ||
          decimalCount > 1)) {
        return;
      }
    }

    setFormData(prev => ({
      ...prev,
      [name]: value
    }));

    // Auto-close date picker when date is selected
    if (name === 'date' && value) {
      // Small delay to ensure the date is set before blurring
      setTimeout(() => {
        e.target.blur();
      }, 100);
    }

    // Clear status when user starts typing
    if (submitStatus !== 'idle') {
      setSubmitStatus('idle');
      setSubmitMessage('');
      setCreatedInvoice(null);
    }
  };

  const handlePaste = (e: React.ClipboardEvent<HTMLInputElement>) => {
    const { name } = e.currentTarget;
    const pastedText = e.clipboardData.getData('text');

    // Validate pasted content - block ALL special characters except decimal point
    if (name === 'documentQty') {
      // Only allow positive integers (digits only, no special characters)
      if (!/^\d+$/.test(pastedText) || parseInt(pastedText) <= 0) {
        e.preventDefault();
      }
    } else if (name === 'documentUnitRate' || name === 'conversionRate') {
      // Only allow positive decimal numbers (digits and ONE decimal point only)
      // Block ALL special characters except decimal point
      const pastedDecimalCount = (pastedText.match(/\./g) || []).length;
      if (!/^\d*\.?\d*$/.test(pastedText) ||
        (pastedText !== '' && pastedText !== '.' && parseFloat(pastedText) <= 0) ||
        pastedDecimalCount > 1) { // Block multiple decimal points
        e.preventDefault();
      }
    }
  };

  const handleLogout = async () => {
    try {
      await authService.logout();
      navigate('/');
    } catch (error) {
      console.error('Logout error:', error);
      // Force logout by clearing storage
      authService.clearAuth();
      navigate('/');
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // Validate required fields
    if (!formData.partNumber || !formData.date || !formData.documentQty ||
      !formData.documentUnitRate || !formData.conversionRate || !formData.retailInvoiceNumber) {
      setSubmitStatus('error');
      setSubmitMessage('Please fill in all required fields.');
      return;
    }

    // Fetch available invoices and open selection modal
    setIsLoadingInvoices(true);
    try {
      const response = await invoiceService.getAvailableInvoices(formData.partNumber);
      setAvailableInvoices(response.invoices);
      setShowSelectionModal(true);
    } catch (error) {
      console.error('Error fetching available invoices:', error);
      setSubmitStatus('error');
      setSubmitMessage(error instanceof Error ? error.message : 'Failed to fetch available invoices.');
    } finally {
      setIsLoadingInvoices(false);
    }
  };

  // Handle invoice selection confirmation
  const handleInvoiceSelectionConfirm = async (selectedInvoices: SelectedInvoice[]) => {
    setShowSelectionModal(false);
    setIsSubmitting(true);
    setSubmitStatus('idle');
    setSubmitMessage('');
    setCreatedInvoice(null);

    try {
      // Format date to YYYY-MM-DD
      const dateObj = new Date(formData.date);
      const formattedDate = dateObj.toISOString().split('T')[0];

      // Prepare request data with selected invoices
      const requestData: RetailInvoiceRequestWithSelection = {
        part_number: formData.partNumber,
        date: formattedDate,
        qty: formData.documentQty,
        usd_rate: formData.documentUnitRate,
        inr_rate: formData.reportingRate,
        conversion_rate: formData.conversionRate,
        retail_invoice_number: formData.retailInvoiceNumber,
        selected_invoices: selectedInvoices,
      };
      console.log('requestData with selection', requestData);
      const response = await invoiceService.createRetailInvoiceWithSelection(requestData);

      // Handle successful response
      setSubmitStatus('success');
      setSubmitMessage('Invoice created successfully!');
      setCreatedInvoice(response);
    } catch (error) {
      console.error('Form submission error:', error);
      setSubmitStatus('error');
      setSubmitMessage(error instanceof Error ? error.message : 'Failed to create invoice. Please try again.');

      // If it's an authentication error, redirect to login
      if (error instanceof Error && error.message.includes('Session expired')) {
        navigate('/');
        return;
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCreateNew = () => {
    setFormData({
      partNumber: '',
      date: '',
      documentQty: '',
      documentUnitRate: '',
      documentTotal: '',
      documentCurrency: '$',
      retailInvoiceNumber: '',
      reportingRate: '',
      reportingTotal: '',
      reportingCurrency: 'INR',
      conversionRate: ''
    });
    setSubmitStatus('idle');
    setSubmitMessage('');
    setCreatedInvoice(null);
  };

  const handleViewInvoices = () => {
    navigate('/invoice-details');
  };

  const handleUploadInvoices = () => {
    navigate('/upload-invoices');
  };

  const handleViewReconciliations = () => {
    navigate('/reconciliations');
  };

  const handleViewInputtedEntries = () => {
    navigate('/inputted-entries');
  };

  const handleViewBalanceHistory = () => {
    navigate('/balance-history');
  };

  const handleViewPartHistory = () => {
    navigate('/part-history');
  };

  const handleExportStockLedgerClick = () => {
    setIsLedgerModalOpen(true);
    // Set default to current month
    const now = new Date();
    const toLocalISO = (date: Date) => {
      const adjusted = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
      return adjusted.toISOString().split('T')[0];
    };
    setLedgerStartDate(toLocalISO(new Date(now.getFullYear(), now.getMonth(), 1)));
    setLedgerEndDate(toLocalISO(new Date(now.getFullYear(), now.getMonth() + 1, 0)));
  };

  const confirmExportLedger = async () => {
    setIsLedgerModalOpen(false);
    try {
      const blob = await apiService.exportStockLedger(
        ledgerStartDate || undefined,
        ledgerEndDate || undefined
      );
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const dateTag = ledgerStartDate && ledgerEndDate
        ? `${ledgerStartDate}_to_${ledgerEndDate}`
        : 'all_time';
      a.download = `stock_report_${dateTag}.xlsx`;
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Export failed:', err);
      alert('Export failed. Please try again.');
    }
  };

  // ── Bulk Upload Handlers ──
  const handleDownloadTemplate = async () => {
    try {
      const blob = await apiService.downloadBulkTemplate();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'fx_bulk_upload_template.xlsx';
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Template download failed:', err);
      alert('Template download failed. Please try again.');
    }
  };

  const handleBulkFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Use Staging UI instead of direct upload
    setBulkUploadFile(file);
    if (bulkFileRef.current) bulkFileRef.current.value = '';
  };





  if (bulkUploadFile) {
    return (
      <BulkUploadStaging
        file={bulkUploadFile}
        onClose={() => setBulkUploadFile(null)}
        onSuccess={(result: any) => {
          setBulkUploadFile(null);
          const msg = result?.message || `Successfully committed ${result?.successful || 0} row(s)!`;
          alert(`✅ ${msg}`);
          // Refresh the dashboard data
          window.location.reload();
        }}
      />
    );
  }

  return (
    <div className="dashboard-container">
      <header className="dashboard-header">
        <div className="header-content">
          <h1>Cooper FX Dashboard</h1>

          {/* Desktop Navigation */}
          <div className="header-navigation desktop-only">
            <button onClick={handleUploadInvoices} className="nav-link">
              Upload Files
            </button>
            <button onClick={handleViewInvoices} className="nav-link">
              Invoices
            </button>
            <button onClick={handleViewReconciliations} className="nav-link">
              Reconciliations
            </button>
            <button onClick={handleViewInputtedEntries} className="nav-link">
              Entries
            </button>
            <button onClick={handleViewBalanceHistory} className="nav-link">
              Balance History
            </button>
            <button onClick={handleViewPartHistory} className="nav-link">
              Part History
            </button>
            <button onClick={handleExportStockLedgerClick} className="nav-link highlight-btn" style={{ backgroundColor: '#e6f7ff', color: '#0066cc', border: '1px solid #1890ff' }}>
              Export Stock Report
            </button>
          </div>

          <div className="user-info desktop-only">
            <span>Welcome, {authService.getUserInfo()?.username || 'User'}</span>
            <Button onClick={handleLogout} variant="ghost" size="sm" className="logout-btn">
              Logout
            </Button>
          </div>

          {/* Mobile Menu Toggle */}
          <button
            className="mobile-menu-toggle"
            onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
            aria-label="Toggle menu"
          >
            {isMobileMenuOpen ? <X size={24} /> : <Menu size={24} />}
          </button>
        </div>

        {/* Mobile Navigation Drawer */}
        <div className={`mobile-nav-overlay ${isMobileMenuOpen ? 'open' : ''}`}>
          <div className="mobile-nav-content">
            <div className="mobile-user-info">
              <span>Welcome, {authService.getUserInfo()?.username || 'User'}</span>
            </div>
            <nav className="mobile-nav-links">
              <button onClick={() => { handleUploadInvoices(); setIsMobileMenuOpen(false); }}>
                Upload Files
              </button>
              <button onClick={() => { handleViewInvoices(); setIsMobileMenuOpen(false); }}>
                View Invoices
              </button>
              <button onClick={() => { handleViewReconciliations(); setIsMobileMenuOpen(false); }}>
                View Reconciliations
              </button>
              <button onClick={() => { handleViewInputtedEntries(); setIsMobileMenuOpen(false); }}>
                View Inputted Entries
              </button>
              <button onClick={() => { handleViewBalanceHistory(); setIsMobileMenuOpen(false); }}>
                Balance History
              </button>
              <button onClick={() => { handleViewPartHistory(); setIsMobileMenuOpen(false); }}>
                Part History
              </button>
              <button onClick={() => { handleExportStockLedgerClick(); setIsMobileMenuOpen(false); }}>
                Export Stock Report
              </button>
              <button onClick={handleLogout} className="mobile-logout">
                Logout
              </button>
            </nav>
          </div>
        </div>
      </header>

      <main className="dashboard-main">
        <div className="dashboard-content">
          {/* Statistics Section - Top Row */}
          <DashboardStats />

          {/* Form Section - Full Width Below Statistics */}
          <div className="form-section">
            <form onSubmit={handleSubmit} className="calculation-form">
              <h2>FX Calculation Form</h2>

              {/* Status Messages */}
              {submitStatus === 'success' && (
                <div className="form-success">
                  <div className="success-icon">✅</div>
                  <div className="success-content">
                    <h3>Invoice Created Successfully!</h3>
                    <p>{submitMessage}</p>
                    {createdInvoice && (
                      <div className="created-invoice">
                        <strong>Invoice Details:</strong>
                        <div className="invoice-details">
                          <span>Customer Name: {createdInvoice.customer_name || "-"}</span>
                          <span>Customer Code: {createdInvoice.customer_code || "-"}</span>
                          <span>Part Number: {createdInvoice.part_number}</span>
                          <span>Date: {createdInvoice.date}</span>
                          <span>Quantity: {createdInvoice.qty}</span>
                          <span>USD Total: ${createdInvoice.usd_total}</span>
                          <span>INR Total: ₹{createdInvoice.inr_total}</span>
                        </div>
                        {createdInvoice.consumed_invoices && createdInvoice.consumed_invoices.length > 0 && (
                          <div className="consumed-invoices">
                            <strong>Consumed Invoices:</strong>
                            <div className="consumed-invoices-list">
                              {createdInvoice.consumed_invoices.map((invoice, index) => (
                                <div key={index} className="consumed-invoice-item">
                                  <span>Invoice #{invoice.invoice_number}</span>
                                  <span>Qty: {invoice.consumed_qty}</span>
                                  <span>USD Rate: ${invoice.usd_rate}</span>
                                  <span>INR Rate: ₹{invoice.inr_rate}</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                    <Button onClick={handleCreateNew} variant="outline" size="sm" className="create-new-button">
                      Create New Invoice
                    </Button>
                  </div>
                </div>
              )}

              {submitStatus === 'error' && (
                <div className="form-error">
                  <div className="error-icon">❌</div>
                  <div className="error-content">
                    <h3>Submission Failed</h3>
                    <p>{submitMessage}</p>
                    <Button onClick={() => setSubmitStatus('idle')} variant="outline" size="sm">
                      Try Again
                    </Button>
                  </div>
                </div>
              )}

              {submitStatus === 'idle' && (
                <>
                  <div className="form-row">
                    <div className="form-group">
                      <Label htmlFor="partNumber">Part Number *</Label>
                      <Input
                        type="text"
                        id="partNumber"
                        name="partNumber"
                        value={formData.partNumber}
                        onChange={handleInputChange}
                        placeholder="Enter part number"
                        required
                        disabled={isSubmitting}
                      />
                    </div>

                    <div className="form-group">
                      <Label htmlFor="date">Date *</Label>
                      <Input
                        type="date"
                        id="date"
                        name="date"
                        value={formData.date}
                        onChange={handleInputChange}
                        required
                        disabled={isSubmitting}
                      />
                    </div>

                    <div className="form-group">
                      <Label htmlFor="retailInvoiceNumber">Retail Invoice Number *</Label>
                      <Input
                        type="text"
                        id="retailInvoiceNumber"
                        name="retailInvoiceNumber"
                        value={formData.retailInvoiceNumber}
                        onChange={handleInputChange}
                        placeholder="Enter retail invoice number"
                        required
                        disabled={isSubmitting}
                      />
                    </div>

                    <div className="form-group">
                      <Label htmlFor="documentQty">Document Qty *</Label>
                      <Input
                        type="number"
                        id="documentQty"
                        name="documentQty"
                        value={formData.documentQty}
                        onChange={handleInputChange}
                        onKeyDown={handleKeyDown}
                        onPaste={handlePaste}
                        placeholder="Enter quantity"
                        min="1"
                        step="1"
                        pattern="[1-9][0-9]*"
                        title="Please enter a positive integer"
                        required
                        disabled={isSubmitting}
                      />
                    </div>
                  </div>

                  <div className="form-row">
                    <div className="form-group">
                      <Label htmlFor="documentUnitRate">Document Unit Rate (USD) *</Label>
                      <Input
                        type="number"
                        id="documentUnitRate"
                        name="documentUnitRate"
                        value={formData.documentUnitRate}
                        onChange={handleInputChange}
                        onKeyDown={handleKeyDown}
                        onPaste={handlePaste}
                        placeholder="Enter unit rate"
                        step="any"
                        min="0.01"
                        title="Please enter a positive decimal number"
                        required
                        disabled={isSubmitting}
                      />
                    </div>

                    <div className="form-group">
                      <Label htmlFor="documentTotal">Document Total (USD)</Label>
                      <Input
                        type="number"
                        id="documentTotal"
                        name="documentTotal"
                        value={formData.documentTotal}
                        placeholder="Calculated automatically"
                        readOnly
                        className="readonly-input"
                        disabled={isSubmitting}
                      />
                    </div>

                    <div className="form-group">
                      <Label htmlFor="documentCurrency">Document Currency</Label>
                      <Input
                        type="text"
                        id="documentCurrency"
                        name="documentCurrency"
                        value={formData.documentCurrency}
                        onChange={handleInputChange}
                        placeholder="$"
                        required
                        readOnly
                        className="readonly-input"
                        disabled={isSubmitting}
                      />
                    </div>
                  </div>

                  <div className="form-row">
                    <div className="form-group">
                      <Label htmlFor="conversionRate">Conversion Rate *</Label>
                      <Input
                        type="number"
                        id="conversionRate"
                        name="conversionRate"
                        value={formData.conversionRate}
                        onChange={handleInputChange}
                        onKeyDown={handleKeyDown}
                        onPaste={handlePaste}
                        placeholder="Enter conversion rate"
                        step="any"
                        min="0.0001"
                        title="Please enter a positive decimal number"
                        required
                        disabled={isSubmitting}
                      />
                    </div>

                    <div className="form-group">
                      <Label htmlFor="reportingRate">Reporting Rate (INR)</Label>
                      <Input
                        type="number"
                        id="reportingRate"
                        name="reportingRate"
                        value={formData.reportingRate}
                        placeholder="Calculated automatically"
                        readOnly
                        className="readonly-input"
                        disabled={isSubmitting}
                      />
                    </div>

                    <div className="form-group">
                      <Label htmlFor="reportingTotal">Reporting Total (INR)</Label>
                      <Input
                        type="number"
                        id="reportingTotal"
                        name="reportingTotal"
                        value={formData.reportingTotal}
                        placeholder="Calculated automatically"
                        readOnly
                        className="readonly-input"
                        disabled={isSubmitting}
                      />
                    </div>
                  </div>

                  <div className="form-row">
                    <div className="form-group">
                      <Label htmlFor="reportingCurrency">Reporting Currency</Label>
                      <Input
                        type="text"
                        id="reportingCurrency"
                        name="reportingCurrency"
                        value={formData.reportingCurrency}
                        onChange={handleInputChange}
                        placeholder="INR"
                        required
                        readOnly
                        className="readonly-input"
                        disabled={isSubmitting}
                      />
                    </div>

                    <div className="form-group submit-group">
                      <Button
                        type="submit"
                        className="submit-button"
                        disabled={isSubmitting}
                      >
                        {isSubmitting ? 'Creating Invoice...' : 'Calculate FX & Create Invoice'}
                      </Button>
                    </div>
                  </div>
                </>
              )}
            </form>

            {/* Bulk Upload Section */}
            <div className="bulk-upload-section">
              <h3>Bulk FX Upload</h3>
              <p className="bulk-upload-description">
                Upload an Excel file to process multiple FX entries at once using FIFO auto-selection.
                For manual invoice selection, use the form above.
              </p>
              <div className="bulk-upload-actions">
                <button
                  onClick={handleDownloadTemplate}
                  className="bulk-btn template-btn"
                  type="button"
                >
                  📥 Download Template
                </button>
                <button
                  onClick={() => bulkFileRef.current?.click()}
                  className="bulk-btn upload-btn"
                  type="button"
                >
                  📤 Upload Excel
                </button>
                <input
                  ref={bulkFileRef}
                  type="file"
                  accept=".xlsx,.xls"
                  onChange={handleBulkFileSelect}
                  style={{ display: 'none' }}
                />
              </div>
            </div>
          </div>
        </div>
      </main>

      <Footer />

      {/* Invoice Selection Modal */}
      <InvoiceSelectionModal
        isOpen={showSelectionModal}
        onClose={() => setShowSelectionModal(false)}
        onConfirm={handleInvoiceSelectionConfirm}
        availableInvoices={availableInvoices}
        requiredQty={parseInt(formData.documentQty) || 0}
        partNumber={formData.partNumber}
        isLoading={isLoadingInvoices}
      />
      {/* Stock Ledger Date Selection Modal */}
      {isLedgerModalOpen && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '1rem', zIndex: 9999 }}>
          <div style={{ background: 'white', borderRadius: '12px', padding: '1.5rem', maxWidth: '380px', width: '100%', boxShadow: '0 20px 60px rgba(0,0,0,0.3)' }}>
            <h3 style={{ margin: '0 0 4px', fontSize: '1.1rem', fontWeight: 600 }}>Export Stock Report</h3>
            <p style={{ margin: '0 0 16px', fontSize: '0.85rem', color: '#666' }}>Choose a period or set a custom date range.</p>

            {/* Quick Presets */}
            <div style={{ display: 'flex', gap: '8px', marginBottom: '16px', flexWrap: 'wrap' }}>
              {[
                {
                  label: 'This Month', action: () => {
                    const now = new Date();
                    const toLocalISO = (d: Date) => new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().split('T')[0];
                    setLedgerStartDate(toLocalISO(new Date(now.getFullYear(), now.getMonth(), 1)));
                    setLedgerEndDate(toLocalISO(new Date(now.getFullYear(), now.getMonth() + 1, 0)));
                  }
                },
                {
                  label: 'This Year', action: () => {
                    const y = new Date().getFullYear();
                    setLedgerStartDate(`${y}-01-01`);
                    setLedgerEndDate(`${y}-12-31`);
                  }
                },
                {
                  label: 'All Time', action: () => {
                    setLedgerStartDate('');
                    setLedgerEndDate('');
                  }
                },
              ].map(preset => (
                <button
                  key={preset.label}
                  onClick={preset.action}
                  style={{ padding: '6px 12px', fontSize: '0.78rem', border: '1px solid #d1d5db', borderRadius: '6px', background: '#f9fafb', cursor: 'pointer', fontWeight: 500 }}
                >
                  {preset.label}
                </button>
              ))}
            </div>

            {/* Custom Date Inputs */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', marginBottom: '16px' }}>
              <div>
                <Label htmlFor="ledger-start" style={{ fontSize: '0.75rem', marginBottom: '4px', display: 'block', color: '#555' }}>From Date</Label>
                <input
                  type="date"
                  id="ledger-start"
                  value={ledgerStartDate}
                  onChange={(e) => setLedgerStartDate(e.target.value)}
                  style={{ width: '100%', border: '1px solid #d1d5db', borderRadius: '6px', padding: '7px 8px', fontSize: '0.85rem', boxSizing: 'border-box' }}
                />
              </div>
              <div>
                <Label htmlFor="ledger-end" style={{ fontSize: '0.75rem', marginBottom: '4px', display: 'block', color: '#555' }}>To Date</Label>
                <input
                  type="date"
                  id="ledger-end"
                  value={ledgerEndDate}
                  onChange={(e) => setLedgerEndDate(e.target.value)}
                  style={{ width: '100%', border: '1px solid #d1d5db', borderRadius: '6px', padding: '7px 8px', fontSize: '0.85rem', boxSizing: 'border-box' }}
                />
              </div>
            </div>

            {/* Info note when All Time */}
            {!ledgerStartDate && !ledgerEndDate && (
              <p style={{ fontSize: '0.78rem', color: '#888', background: '#f0f9ff', border: '1px solid #bae6fd', borderRadius: '6px', padding: '8px 10px', marginBottom: '16px' }}>
                ℹ️ <strong>All Time</strong>: Opening Stock will be 0 (no prior period). All transactions will appear under Shipment/Despatch columns.
              </p>
            )}

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
              <button
                onClick={() => setIsLedgerModalOpen(false)}
                style={{ padding: '8px 16px', fontSize: '0.875rem', color: '#555', background: '#f3f4f6', border: 'none', borderRadius: '6px', cursor: 'pointer' }}
              >
                Cancel
              </button>
              <button
                onClick={confirmExportLedger}
                style={{ padding: '8px 16px', fontSize: '0.875rem', color: 'white', background: '#2563eb', border: 'none', borderRadius: '6px', cursor: 'pointer', fontWeight: 500 }}
              >
                Export Excel
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
};

export default DashboardPage;