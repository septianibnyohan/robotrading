import React from 'react';

const KPIWidget = ({ account, positions, activeSession }) => {
  const balance = account?.balance ?? 10000.0;
  const equity = account?.equity ?? 10000.0;
  const marginFree = account?.margin_free ?? 10000.0;
  const profit = account?.profit ?? 0.0;
  const currency = account?.currency ?? 'USD';
  const server = account?.server ?? 'OFFLINE';

  const positionCount = positions?.length ?? 0;
  const layers = activeSession?.layers ?? 0;
  const symbol = activeSession?.symbol ?? '';
  const direction = activeSession?.direction ?? '';

  return (
    <div className="kpi-grid">
      {/* 1. Account Balance */}
      <div className="kpi-card kpi-secondary">
        <div className="kpi-label">Account Balance</div>
        <div className="kpi-value">
          <span style={{ fontSize: '1rem', opacity: 0.5, marginRight: '2px' }}>$</span>
          {balance.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
        </div>
        <div className="kpi-subtext" style={{ fontSize: '0.75rem' }}>
          Server: <span style={{ color: 'var(--text-white)' }}>{server}</span>
        </div>
      </div>

      {/* 2. Equity */}
      <div className="kpi-card kpi-primary">
        <div className="kpi-label">Equity</div>
        <div className="kpi-value">
          <span style={{ fontSize: '1rem', opacity: 0.5, marginRight: '2px' }}>$</span>
          {equity.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
        </div>
        <div className="kpi-subtext" style={{ fontSize: '0.75rem' }}>
          Margin security level
        </div>
      </div>

      {/* 3. Free Margin */}
      <div className="kpi-card kpi-secondary">
        <div className="kpi-label">Free Margin</div>
        <div className="kpi-value">
          <span style={{ fontSize: '1rem', opacity: 0.5, marginRight: '2px' }}>$</span>
          {marginFree.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
        </div>
        <div className="kpi-subtext" style={{ fontSize: '0.75rem' }}>
          Available buying power
        </div>
      </div>

      {/* 4. Floating PnL */}
      <div className="kpi-card kpi-success" style={{
        borderColor: profit > 0 ? 'rgba(0,230,118,0.2)' : profit < 0 ? 'rgba(255,51,102,0.2)' : 'var(--border)',
        background: profit > 0 ? 'rgba(0,230,118,0.02)' : profit < 0 ? 'rgba(255,51,102,0.02)' : 'var(--bg-card)'
      }}>
        <div className="kpi-label">Floating Profit</div>
        <div className="kpi-value" style={{ color: profit > 0 ? 'var(--green)' : profit < 0 ? 'var(--red)' : 'var(--text-white)' }}>
          {profit > 0 ? '+' : ''}${profit.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
        </div>
        <div className="kpi-subtext">
          {positionCount} active {positionCount === 1 ? 'position' : 'positions'} open
        </div>
      </div>

      {/* 5. Grid Status */}
      <div className="kpi-card kpi-secondary">
        <div className="kpi-label">Grid Session</div>
        <div className="kpi-value" style={{ fontSize: '1.25rem', height: '38px', display: 'flex', alignItems: 'center' }}>
          {layers > 0 ? (
            <span style={{ color: 'var(--text-white)', fontWeight: 'bold' }}>
              {symbol} <span style={{ color: direction === 'BUY' ? 'var(--green)' : 'var(--red)' }}>{direction}</span> ({layers} L)
            </span>
          ) : (
            <span style={{ color: 'var(--text-muted)' }}>Idle</span>
          )}
        </div>
        <div className="kpi-subtext">
          {layers > 0 ? 'Layering basket active' : 'Awaiting entry signal'}
        </div>
      </div>
    </div>
  );
};

export default KPIWidget;
