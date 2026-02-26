import { apiService } from './apiService';
import type {
  InvoiceItem,
  RetailInvoiceRequest,
  RetailInvoiceResponse,
  UploadResponse,
  PaginatedInvoiceResponse,
  AvailableInvoicesResponse,
  RetailInvoiceRequestWithSelection,
  BalanceHistoryResponse
} from './apiService';

export interface InvoiceFilters {
  startDate?: string;
  endDate?: string;
  invoiceNumber?: string;
  partNumber?: string;
  page?: number;
  limit?: number;
}

class InvoiceService {
  /**
   * Get all invoices
   */
  async getInvoices(pageUrlOrFilters?: string | InvoiceFilters): Promise<PaginatedInvoiceResponse> {
    return await apiService.getInvoices(pageUrlOrFilters);
  }

  /**
   * Get invoice by ID
   */
  async getInvoiceById(id: string): Promise<InvoiceItem> {
    return await apiService.getInvoiceById(id);
  }

  /**
   * Create retail invoice
   */
  async createRetailInvoice(invoiceData: RetailInvoiceRequest): Promise<RetailInvoiceResponse> {
    return await apiService.createRetailInvoice(invoiceData);
  }

  /**
   * Create retail invoice with manual invoice selection
   */
  async createRetailInvoiceWithSelection(
    invoiceData: RetailInvoiceRequestWithSelection
  ): Promise<RetailInvoiceResponse> {
    return await apiService.createRetailInvoiceWithSelection(invoiceData);
  }

  /**
   * Get available Cooper invoices for a retail part number
   */
  async getAvailableInvoices(partNumber: string): Promise<AvailableInvoicesResponse> {
    return await apiService.getAvailableInvoices(partNumber);
  }

  /**
   * Upload invoice files
   */
  async uploadInvoices(files: File[]): Promise<UploadResponse> {
    return await apiService.uploadInvoices(files);
  }

  /**
   * Upload part number mapping files
   */
  async uploadPartMap(files: File[]): Promise<UploadResponse> {
    return await apiService.uploadPartMap(files);
  }

  /**
   * Get balance history for an invoice
   */
  async getBalanceHistory(invoiceId?: number, page?: number, pageSize?: number): Promise<BalanceHistoryResponse> {
    return await apiService.getBalanceHistory(invoiceId, page, pageSize);
  }
}

export const invoiceService = new InvoiceService();
export default invoiceService;