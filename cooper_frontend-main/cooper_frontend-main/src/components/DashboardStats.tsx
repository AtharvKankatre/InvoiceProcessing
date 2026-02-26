import React, { useState, useEffect } from 'react';
import Loading from '@/components/ui/loading';
import { apiService } from '@/services/apiService';
import type { DashboardStatsResponse } from '@/services/apiService';

interface DashboardStatsProps {
  className?: string;
}

const DashboardStats: React.FC<DashboardStatsProps> = ({ className }) => {
  const [stats, setStats] = useState<DashboardStatsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchDashboardStats = async () => {
      try {
        setLoading(true);
        setError(null);
        const response = await apiService.getDashboardStats();
        setStats(response);
      } catch (err) {
        console.error('Failed to fetch dashboard stats:', err);
        setError(err instanceof Error ? err.message : 'Failed to load dashboard statistics');
      } finally {
        setLoading(false);
      }
    };

    fetchDashboardStats();
  }, []);

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2
    }).format(amount);
  };

  const formatQuantity = (qty: number) => {
    return new Intl.NumberFormat('en-US').format(qty);
  };

  if (loading) {
    return (
      <div className={`stats-section ${className || ''}`}>
        <h3>Dashboard Statistics</h3>
        <Loading message="Loading dashboard statistics..." minHeight="120px" />
      </div>
    );
  }

  if (error) {
    return (
      <div className={`stats-section ${className || ''}`}>
        <h3>Dashboard Statistics</h3>
        <div className="error-message" style={{
          padding: '2rem',
          textAlign: 'center',
          color: '#dc2626',
          background: 'rgba(248, 113, 113, 0.1)',
          borderRadius: '8px',
          border: '1px solid rgba(248, 113, 113, 0.2)'
        }}>
          <p>Failed to load dashboard statistics</p>
          <p style={{ fontSize: '0.875rem', marginTop: '0.5rem', opacity: 0.8 }}>
            {error}
          </p>
        </div>
      </div>
    );
  }

  if (!stats) {
    return (
      <div className={`stats-section ${className || ''}`}>
        <h3>Dashboard Statistics</h3>
        <div className="no-data-message" style={{
          padding: '2rem',
          textAlign: 'center',
          color: '#6b7280',
          background: 'rgba(156, 163, 175, 0.1)',
          borderRadius: '8px',
          border: '1px solid rgba(156, 163, 175, 0.2)'
        }}>
          <p>No dashboard statistics available</p>
        </div>
      </div>
    );
  }

  return (
    <div className={`stats-section ${className || ''}`}>
      <h3>Dashboard Statistics</h3>
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-icon">📄</div>
          <div className="stat-content">
            <div className="stat-value">{stats.total_distinct_invoices}</div>
            <div className="stat-label">Total Distinct Invoices</div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon">📦</div>
          <div className="stat-content">
            <div className="stat-value">{formatQuantity(stats.total_qty)}</div>
            <div className="stat-label">Total Quantity</div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon">💰</div>
          <div className="stat-content">
            <div className="stat-value">{formatCurrency(stats.total_dollar_total)}</div>
            <div className="stat-label">Total Dollar Amount</div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon">✅</div>
          <div className="stat-content">
            <div className="stat-value">{stats.reconciled_invoices}</div>
            <div className="stat-label">Reconciled Invoices</div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default DashboardStats; 