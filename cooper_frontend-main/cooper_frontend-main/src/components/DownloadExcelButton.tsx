import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { apiService } from '@/services/apiService';

interface DownloadExcelButtonProps {
  disabled?: boolean;
  variant?: 'default' | 'outline' | 'secondary' | 'destructive' | 'ghost' | 'link';
  size?: 'default' | 'sm' | 'lg' | 'icon';
  className?: string;
  children?: React.ReactNode;
}

const DownloadExcelButton: React.FC<DownloadExcelButtonProps> = ({
  disabled = false,
  variant = 'outline',
  size = 'sm',
  className = '',
  children = '📊 Download Excel'
}) => {
  const [isDownloading, setIsDownloading] = useState(false);

  const handleDownload = async () => {
    try {
      setIsDownloading(true);
      
      // Call the export API endpoint
      const arrayBuffer = await apiService.exportReconciliations();
      
      // Create blob from response
      const blob = new Blob([arrayBuffer], {
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
      });
      
      // Create download link
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      
      // Generate filename with current date
      const now = new Date();
      const dateStr = now.toISOString().split('T')[0];
      const timeStr = now.toTimeString().split(' ')[0].replace(/:/g, '-');
      const filename = `reconciliations_export_${dateStr}_${timeStr}.xlsx`;
      
      link.download = filename;
      
      // Trigger download
      document.body.appendChild(link);
      link.click();
      
      // Cleanup
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
      
    } catch (error) {
      console.error('Download failed:', error);
      
      // Show user-friendly error message
      const errorMessage = error instanceof Error ? error.message : 'Download failed';
      alert(`Failed to download Excel file: ${errorMessage}`);
      
    } finally {
      setIsDownloading(false);
    }
  };

  return (
    <Button
      onClick={handleDownload}
      disabled={disabled || isDownloading}
      variant={variant}
      size={size}
      className={className}
    >
      {isDownloading ? '⏳ Downloading...' : children}
    </Button>
  );
};

export default DownloadExcelButton; 