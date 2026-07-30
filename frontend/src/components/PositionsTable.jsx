import React from 'react';

const PositionsTable = ({ positions, onEmergencyClose }) => {
  const formatTime = (ts) => {
    if (!ts) return '';
    try {
      const d = new Date(ts * 1000);
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) + ' ' + d.toLocaleDateString([], { month: 'short', day: 'numeric' });
    } catch {
      return ts;
    }
  };

  const getPositionTypeClass = (type) => {
    return type === 'BUY' ? 'badge-connected' : 'badge-disconnected';
  };

  return (
    <div className="table-card">
      <div className="table-title-row">
        <h2 className="table-title">
          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ color: 'var(--secondary)' }}>
            <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
          </svg>
          <span>Active Layer Positions ({positions?.length || 0})</span>
        </h2>
        {positions && positions.length > 0 && (
          <button className="btn btn-danger" onClick={onEmergencyClose}>
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10"/>
              <line x1="15" y1="9" x2="9" y2="15"/>
              <line x1="9" y1="9" x2="15" y2="15"/>
            </svg>
            <span>Close Basket (Close All)</span>
          </button>
        )}
      </div>

      {!positions || positions.length === 0 ? (
        <div style={{
          padding: '2rem',
          textAlign: 'center',
          color: 'var(--text-muted)',
          fontSize: '0.95rem',
          background: 'rgba(0, 0, 0, 0.1)',
          borderRadius: '8px',
          border: '1px solid var(--border)'
        }}>
          No active positions in current trading session.
        </div>
      ) : (
        <div className="table-responsive">
          <table className="custom-table">
            <thead>
              <tr>
                <th>Ticket</th>
                <th>Symbol</th>
                <th>Type</th>
                <th>Volume</th>
                <th>Open Price</th>
                <th>Current Price</th>
                <th>Swap</th>
                <th>Profit (USD)</th>
                <th>Time (WIB)</th>
                <th>Magic</th>
              </tr>
            </thead>
            <tbody>
              {positions.map((pos) => (
                <tr key={pos.ticket}>
                  <td className="font-mono" style={{ color: 'var(--text-white)' }}>#{pos.ticket}</td>
                  <td style={{ fontWeight: '600' }}>{pos.symbol}</td>
                  <td>
                    <span className={`badge ${getPositionTypeClass(pos.type)}`}>
                      {pos.type}
                    </span>
                  </td>
                  <td className="font-mono">{pos.volume.toFixed(2)}</td>
                  <td className="font-mono">${pos.price_open.toFixed(2)}</td>
                  <td className="font-mono">${(pos.price_open + (pos.profit / (pos.volume * 100))).toFixed(2)}</td>
                  <td className="font-mono text-red" style={{ color: pos.swap < 0 ? 'var(--red)' : pos.swap > 0 ? 'var(--green)' : 'inherit' }}>
                    ${pos.swap.toFixed(2)}
                  </td>
                  <td className={`font-mono ${pos.profit >= 0 ? 'text-green' : 'text-red'}`} style={{ fontWeight: '700' }}>
                    ${pos.profit >= 0 ? '+' : ''}{pos.profit.toFixed(2)}
                  </td>
                  <td>{formatTime(pos.time)}</td>
                  <td className="font-mono" style={{ fontSize: '0.75rem', opacity: 0.6 }}>{pos.magic}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export default PositionsTable;
