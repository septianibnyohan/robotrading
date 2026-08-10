import React, { useState } from 'react';

const HistoryTable = ({ history }) => {
  const [activeFilter, setActiveFilter] = useState('today');

  // Filter out initial/setup records, sort in reverse-chronological order (most recent first)
  const transactions = history
    ? history.filter((h) => h.reason !== 'Initial' && h.symbol !== '').slice().reverse()
    : [];

  const filterTransactions = (txs, range) => {
    const now = new Date();
    const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const startOfYesterday = new Date(startOfToday.getTime() - 24 * 60 * 60 * 1000);
    const startOfLastWeek = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
    const startOfLastMonth = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
    const startOfLastYear = new Date(now.getTime() - 365 * 24 * 60 * 60 * 1000);

    return txs.filter((tx) => {
      const txDate = new Date(tx.time);
      switch (range) {
        case 'today':
          return txDate >= startOfToday;
        case 'yesterday':
          return txDate >= startOfYesterday && txDate < startOfToday;
        case 'last_week':
          return txDate >= startOfLastWeek;
        case 'last_month':
          return txDate >= startOfLastMonth;
        case 'last_year':
          return txDate >= startOfLastYear;
        case 'all':
        default:
          return true;
      }
    });
  };

  const filteredTransactions = filterTransactions(transactions, activeFilter);

  // Sum realized profit for filtered transactions
  const totalProfit = filteredTransactions.reduce((sum, tx) => sum + (tx.profit || 0), 0);

  const formatTime = (isoStr) => {
    if (!isoStr) return '';
    try {
      const d = new Date(isoStr);
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) + ' ' + d.toLocaleDateString([], { month: 'short', day: 'numeric' });
    } catch {
      return isoStr;
    }
  };

  const filterOptions = [
    { value: 'all', label: 'All Time' },
    { value: 'today', label: 'Today' },
    { value: 'yesterday', label: 'Yesterday' },
    { value: 'last_week', label: '7 Days' },
    { value: 'last_month', label: '30 Days' },
    { value: 'last_year', label: '1 Year' }
  ];

  return (
    <div className="table-card">
      <div className="table-title-row" style={{ flexWrap: 'wrap', gap: '12px' }}>
        <h2 className="table-title">
          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ color: 'var(--warning)' }}>
            <circle cx="12" cy="12" r="10"/>
            <polyline points="12 6 12 12 16 14"/>
          </svg>
          <span>Transaction History ({filteredTransactions.length})</span>
        </h2>
        
        {/* Dynamic Total Profit summary indicator */}
        <div style={{ 
          fontSize: '0.95rem', 
          fontWeight: 'bold', 
          color: 'var(--text-main)',
          background: 'rgba(255, 255, 255, 0.02)',
          border: '1px solid var(--border)',
          padding: '0.4rem 0.85rem',
          borderRadius: '6px',
          display: 'flex',
          gap: '8px',
          alignItems: 'center'
        }}>
          <span>Filtered PnL:</span>
          <span 
            className={totalProfit >= 0 ? 'text-green' : 'text-red'}
            style={{ 
              fontWeight: '800',
              textShadow: totalProfit !== 0 ? `0 0 10px ${totalProfit >= 0 ? 'rgba(0, 230, 118, 0.3)' : 'rgba(255, 51, 102, 0.3)'}` : 'none'
            }}
          >
            ${totalProfit >= 0 ? '+' : ''}{totalProfit.toFixed(2)}
          </span>
        </div>
      </div>

      {/* Pill filter button bar row */}
      <div style={{ 
        display: 'flex', 
        gap: '6px', 
        overflowX: 'auto', 
        paddingBottom: '6px', 
        marginBottom: '1.25rem', 
        borderBottom: '1px solid rgba(255, 255, 255, 0.04)',
        scrollbarWidth: 'none'
      }}>
        {filterOptions.map((opt) => (
          <button
            key={opt.value}
            className="btn"
            style={{
              padding: '0.3rem 0.75rem',
              fontSize: '0.75rem',
              background: activeFilter === opt.value ? 'var(--primary)' : 'rgba(255,255,255,0.03)',
              color: activeFilter === opt.value ? 'var(--text-white)' : 'var(--text-muted)',
              border: `1px solid ${activeFilter === opt.value ? 'var(--primary)' : 'var(--border)'}`,
              borderRadius: '4px',
              cursor: 'pointer',
              whiteSpace: 'nowrap',
              fontWeight: activeFilter === opt.value ? '700' : '500',
              boxShadow: activeFilter === opt.value ? '0 2px 8px var(--primary-glow)' : 'none',
              minHeight: '28px',
              transition: 'var(--transition)'
            }}
            onClick={() => setActiveFilter(opt.value)}
          >
            {opt.label}
          </button>
        ))}
      </div>

      {filteredTransactions.length === 0 ? (
        <div style={{
          padding: '2.5rem',
          textAlign: 'center',
          color: 'var(--text-muted)',
          fontSize: '0.9rem',
          background: 'rgba(0, 0, 0, 0.15)',
          borderRadius: '8px',
          border: '1px dashed var(--border)'
        }}>
          No closed transactions found for the selected time range.
        </div>
      ) : (
        <div className="table-responsive" style={{ maxHeight: '350px', overflowY: 'auto' }}>
          <table className="custom-table">
            <thead>
              <tr>
                <th>Ticket</th>
                <th>Symbol</th>
                <th>Realized PnL (USD)</th>
                <th>Closing Reason</th>
                <th>Close Time</th>
              </tr>
            </thead>
            <tbody>
              {filteredTransactions.map((tx, idx) => (
                <tr key={tx.ticket || idx}>
                  <td className="font-mono" style={{ color: 'var(--text-white)' }}>
                    {tx.ticket ? `#${tx.ticket}` : 'N/A'}
                  </td>
                  <td style={{ fontWeight: '600' }}>{tx.symbol}</td>
                  <td className={`font-mono ${tx.profit >= 0 ? 'text-green' : 'text-red'}`} style={{ fontWeight: '700' }}>
                    ${tx.profit >= 0 ? '+' : ''}{tx.profit.toFixed(2)}
                  </td>
                  <td>
                    <span style={{ 
                      fontSize: '0.8rem', 
                      color: tx.profit > 0 ? 'var(--green)' : 'var(--warning)', 
                      fontWeight: '600',
                      background: tx.profit > 0 ? 'rgba(0, 230, 118, 0.05)' : 'rgba(255, 170, 0, 0.05)',
                      padding: '2px 8px',
                      borderRadius: '4px',
                      border: `1px solid ${tx.profit > 0 ? 'rgba(0, 230, 118, 0.1)' : 'rgba(255, 170, 0, 0.1)'}`
                    }}>
                      {tx.reason || 'Closed'}
                    </span>
                  </td>
                  <td style={{ fontSize: '0.85rem' }}>{formatTime(tx.time)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export default HistoryTable;
