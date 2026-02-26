import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { invoiceService } from '@/services/invoiceService';
import type { UploadResponse } from '@/services/apiService';
import Footer from '@/components/Footer';

import './UploadInvoicesPage.css';

type UploadType = 'invoices' | 'part-mapping';

const UploadInvoicesPage: React.FC = () => {
  const navigate = useNavigate();
  const [uploadType, setUploadType] = useState<UploadType | null>(null);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState<'idle' | 'success' | 'error'>('idle');
  const [uploadMessage, setUploadMessage] = useState('');
  const [uploadedFiles, setUploadedFiles] = useState<string[]>([]);
  const [failedFiles, setFailedFiles] = useState<string[]>([]);
  const [uploadedData, setUploadedData] = useState<UploadResponse['data']>([]);



  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    
    // Validate file types based on upload type
    const getValidTypes = (type: UploadType | null) => {
      if (type === 'part-mapping') {
        return [
          'text/csv',
          'application/vnd.ms-excel',
          'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        ];
      }
      // Default for invoices
      return [
        'text/csv',
        'application/vnd.ms-excel',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'application/pdf'
      ];
    };
    
    const validTypes = getValidTypes(uploadType);
    const supportedFormats = uploadType === 'part-mapping' ? 'CSV or Excel' : 'CSV, Excel, or PDF';
    
    const validFiles = files.filter(file => {
      if (!validTypes.includes(file.type)) {
        alert(`File "${file.name}" is not a supported format. Please upload ${supportedFormats} files only.`);
        return false;
      }
      
      if (file.size > 10 * 1024 * 1024) { // 10MB limit
        alert(`File "${file.name}" is too large. Maximum file size is 10MB.`);
        return false;
      }
      
      return true;
    });
    
    setSelectedFiles(validFiles);
    setUploadStatus('idle');
    setUploadMessage('');
    setUploadedData([]);
  };

  const handleRemoveFile = (index: number) => {
    setSelectedFiles(prev => prev.filter((_, i) => i !== index));
    setUploadStatus('idle');
    setUploadMessage('');
    setUploadedData([]);
  };

  const handleUpload = async () => {
    if (selectedFiles.length === 0) return;

    setIsUploading(true);
    setUploadProgress(0);
    setUploadStatus('idle');
    setUploadMessage('');
    setUploadedFiles([]);
    setFailedFiles([]);
    setUploadedData([]);

    try {
      // Simulate progress for better UX
      const progressInterval = setInterval(() => {
        setUploadProgress(prev => {
          if (prev >= 90) {
            clearInterval(progressInterval);
            return 90;
          }
          return prev + 10;
        });
      }, 200);

      // Upload files using the appropriate service based on upload type
      const response: UploadResponse = uploadType === 'part-mapping' 
        ? await invoiceService.uploadPartMap(selectedFiles)
        : await invoiceService.uploadInvoices(selectedFiles);
      
      clearInterval(progressInterval);
      setUploadProgress(100);

      // Handle successful upload
      setUploadStatus('success');
      setUploadMessage(response.message || 'Files uploaded successfully!');
      setUploadedFiles(selectedFiles.map(file => file.name));
      setUploadedData(response.data || []);
      
      // Clear selected files after successful upload
      setTimeout(() => {
        setSelectedFiles([]);
        setUploadProgress(0);
        setUploadStatus('idle');
        setUploadMessage('');
        setUploadedData([]);
      }, 5000); // Show success message for 5 seconds
      
    } catch (error) {
      console.error('Upload error:', error);
      setUploadStatus('error');
      setUploadMessage(error instanceof Error ? error.message : 'Upload failed. Please try again.');
      setFailedFiles(selectedFiles.map(file => file.name));
      
      // If it's an authentication error, redirect to login
      if (error instanceof Error && error.message.includes('Session expired')) {
        navigate('/');
        return;
      }
    } finally {
      setIsUploading(false);
    }
  };

  const handleBackToDashboard = () => {
    navigate('/dashboard');
  };

  const handleUploadTypeSelect = (type: UploadType) => {
    setUploadType(type);
    setSelectedFiles([]);
    setUploadStatus('idle');
    setUploadMessage('');
    setUploadedData([]);
  };

  const handleResetSelection = () => {
    setUploadType(null);
    setSelectedFiles([]);
    setUploadStatus('idle');
    setUploadMessage('');
    setUploadedData([]);
  };

  const handleViewInvoices = () => {
    navigate('/invoice-details');
  };

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const formatNumber = (num: string | number | undefined | null) => {
    if (num === undefined || num === null) return '0.00';
    const numValue = typeof num === 'string' ? parseFloat(num) : num;
    if (isNaN(numValue)) return '0.00';
    return numValue.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  };



  return (
    <div className="upload-invoices-container">
      <header className="upload-header">
        <div className="header-content">
          <h1>Upload Files</h1>
          <div className="header-actions">
            {uploadType && (
              <Button onClick={handleResetSelection} variant="outline" size="sm">
                Change Upload Type
              </Button>
            )}
            <Button onClick={handleBackToDashboard} variant="outline" size="sm">
              Back to Dashboard
            </Button>
          </div>
        </div>
      </header>

      <main className="upload-main">
        <div className="upload-content">
          {!uploadType ? (
            <div className="upload-type-selection">
              <h2>Select Upload Type</h2>
              <p className="upload-description">
                Choose the type of files you want to upload:
              </p>
              
              <div className="upload-type-options">
                <div 
                  className="upload-type-option" 
                  onClick={() => handleUploadTypeSelect('invoices')}
                >
                  <div className="option-icon">📄</div>
                  <h3>Upload Invoices</h3>
                  <p>Upload invoice files in CSV, Excel, or PDF format</p>
                  <div className="option-formats">
                    Supported: .csv, .xlsx, .xls, .pdf
                  </div>
                </div>
                
                <div 
                  className="upload-type-option" 
                  onClick={() => handleUploadTypeSelect('part-mapping')}
                >
                  <div className="option-icon">🔗</div>
                  <h3>Upload Part Number Mapping</h3>
                  <p>Upload part number mapping files in CSV or Excel format</p>
                  <div className="option-formats">
                    Supported: .csv, .xlsx, .xls
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="upload-section">
              <h2>
                {uploadType === 'part-mapping' ? 'Upload Part Number Mapping Files' : 'Upload Invoice Files'}
              </h2>
              <p className="upload-description">
                {uploadType === 'part-mapping' 
                  ? 'Upload your part number mapping files in CSV or Excel format. Supported formats: .csv, .xlsx, .xls'
                  : 'Upload your invoice files in CSV, Excel, or PDF format. Supported formats: .csv, .xlsx, .xls, .pdf'
                }
              </p>

              {/* Upload Status Messages */}
              {uploadStatus === 'success' && (
                <div className="upload-success">
                  <div className="success-icon">✅</div>
                  <div className="success-content">
                    <h3>Upload Successful!</h3>
                    <p>{uploadMessage}</p>
                    {uploadedFiles.length > 0 && (
                      <div className="uploaded-files">
                        <strong>Uploaded files:</strong>
                        <ul>
                          {uploadedFiles.map((fileName, index) => (
                            <li key={index}>{fileName}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {uploadedData.length > 0 && (
                      <div className="uploaded-data">
                        <strong>Imported {uploadedData.length} records:</strong>
                        <div className="data-preview">
                                                      {uploadedData.slice(0, 3).map((item, index) => (
                              <div key={index} className="data-item">
                                {uploadType === 'part-mapping' ? (
                                  <>
                                    <span className="part-number">{item.part_number || 'N/A'}</span>
                                    <span className="mapping-info">
                                      {String((item as Record<string, unknown>)['mapped_part_number'] || 
                                       (item as Record<string, unknown>)['description'] || 
                                       'Mapping data')}
                                    </span>
                                  </>
                                ) : (
                                  <>
                                    <span className="invoice-number">#{item.invoice_number}</span>
                                    <span className="part-number">{item.part_number}</span>
                                    <span className="amount">${formatNumber(item.dollar_total)}</span>
                                  </>
                                )}
                              </div>
                            ))}
                          {uploadedData.length > 3 && (
                            <div className="more-items">
                              ... and {uploadedData.length - 3} more records
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                    <div className="success-actions">
                      <Button onClick={handleViewInvoices} variant="outline" size="sm">
                        View All Invoices
                      </Button>
                    </div>
                  </div>
                </div>
              )}

              {uploadStatus === 'error' && (
                <div className="upload-error">
                  <div className="error-icon">❌</div>
                  <div className="error-content">
                    <h3>Upload Failed</h3>
                    <p>{uploadMessage}</p>
                    {failedFiles.length > 0 && (
                      <div className="failed-files">
                        <strong>Failed files:</strong>
                        <ul>
                          {failedFiles.map((fileName, index) => (
                            <li key={index}>{fileName}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                    <Button onClick={() => setUploadStatus('idle')} variant="outline" size="sm">
                      Try Again
                    </Button>
                  </div>
                </div>
              )}

              <div className="upload-main-content">
                <div className="upload-left">
                  <div className="upload-area">
                    <input
                      type="file"
                      id="file-upload"
                      multiple
                      accept={uploadType === 'part-mapping' ? '.csv,.xlsx,.xls' : '.csv,.xlsx,.xls,.pdf'}
                      onChange={handleFileSelect}
                      className="file-input"
                      disabled={isUploading}
                    />
                    <label htmlFor="file-upload" className="upload-label">
                      <div className="upload-icon">📁</div>
                      <div className="upload-text">
                        <span className="upload-title">Choose files or drag and drop</span>
                        <span className="upload-subtitle">
                          {uploadType === 'part-mapping' ? 'CSV or Excel files up to 10MB each' : 'CSV, Excel, or PDF files up to 10MB each'}
                        </span>
                      </div>
                    </label>
                  </div>

                  {selectedFiles.length > 0 && (
                    <div className="selected-files">
                      <h3>Selected Files ({selectedFiles.length})</h3>
                      <div className="file-list">
                        {selectedFiles.map((file, index) => (
                          <div key={index} className="file-item">
                            <div className="file-info">
                              <div className="file-icon">
                                {file.type.includes('pdf') ? '📄' : 
                                 file.type.includes('csv') ? '📊' : '📈'}
                              </div>
                              <div className="file-details">
                                <div className="file-name">{file.name}</div>
                                <div className="file-size">{formatFileSize(file.size)}</div>
                              </div>
                            </div>
                            <Button
                              onClick={() => handleRemoveFile(index)}
                              variant="outline"
                              size="sm"
                              className="remove-file-btn"
                              disabled={isUploading}
                            >
                              Remove
                            </Button>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {isUploading && (
                    <div className="upload-progress">
                      <div className="progress-bar">
                        <div 
                          className="progress-fill" 
                          style={{ width: `${uploadProgress}%` }}
                        ></div>
                      </div>
                      <div className="progress-text">
                        Uploading... {uploadProgress}%
                      </div>
                    </div>
                  )}

                  <div className="upload-actions">
                    <Button
                      onClick={handleUpload}
                      disabled={selectedFiles.length === 0 || isUploading}
                      className="upload-button"
                      size="lg"
                    >
                      {isUploading ? 'Uploading...' : 'Upload Files'}
                    </Button>
                  </div>
                </div>

                <div className="upload-right">
                  <div className="upload-info">
                    <h3>Upload Guidelines</h3>
                    <div className="guidelines">
                      <div className="guideline-item">
                        <div className="guideline-icon">✅</div>
                        <div className="guideline-text">
                          <strong>Supported Formats:</strong> {uploadType === 'part-mapping' ? 'CSV, Excel (.xlsx, .xls)' : 'CSV, Excel (.xlsx, .xls), PDF'}
                        </div>
                      </div>
                      <div className="guideline-item">
                        <div className="guideline-icon">📏</div>
                        <div className="guideline-text">
                          <strong>File Size:</strong> Maximum 10MB per file
                        </div>
                      </div>
                      <div className="guideline-item">
                        <div className="guideline-icon">📊</div>
                        <div className="guideline-text">
                          <strong>Required Fields:</strong> {uploadType === 'part-mapping' ? 'Part number, mapping data' : 'Invoice number, date, amount, currency'}
                        </div>
                      </div>
                      <div className="guideline-item">
                        <div className="guideline-icon">🔄</div>
                        <div className="guideline-text">
                          <strong>Processing:</strong> Files will be processed automatically
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </main>

      <Footer />
    </div>
  );
};

export default UploadInvoicesPage; 