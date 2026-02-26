/**
 * TypeScript interfaces for Part-wise Transaction History feature
 */

/**
 * Response structure from the part history API endpoint
 */
export interface PartHistoryResponse {
  part_number: string;
  history: TransactionHistoryEntry[];
}

/**
 * Individual transaction entry in the history
 */
export interface TransactionHistoryEntry {
  date: string;           // ISO 8601 format (YYYY-MM-DD)
  invoice_number: string;
  qty: number;
  on_hand: number;
  type: 'INCOMING' | 'OUTGOING';
  name?: string;
  customer_code?: string;
}

/**
 * Filter parameters for querying part history
 */
export interface PartHistoryFilters {
  partNumber: string;
  fromDate?: string;      // Optional ISO 8601 format (YYYY-MM-DD)
  toDate?: string;        // Optional ISO 8601 format (YYYY-MM-DD)
}
