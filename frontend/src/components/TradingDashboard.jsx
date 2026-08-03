import React, { useState, useEffect } from 'react';
import KPIWidget from './KPIWidget';
import LayerChart from './LayerChart';
import EquityChart from './EquityChart';
import PositionsTable from './PositionsTable';
import { PlayIcon, StopIcon, InfoIcon, AlertIcon } from './Icons';

const TradingDashboard = ({
  mode,
  status,
  positions,
  history,
  config,
  symbolsData,
  onStartBot,
  onStopBot,
  onEmergencyClose
}) => {
  const [selectedSymbols, setSelectedSymbols] = useState([]);
  const [actionLoading, setActionLoading] = useState(false);

  const isLive = mode === 'live';

  // Initialize selected symbols from active symbol configurations
  useEffect(() => {
    if (symbolsData?.active?.length > 0 && selectedSymbols.length === 0) {
      setSelectedSymbols([symbolsData.active[0]]);
    }
  }, [symbolsData]);

  const toggleSymbolSelection = (sym) => {
    setSelectedSymbols((prev) =>
      prev.includes(sym) ? prev.filter((s) => s !== sym) : [...prev, sym]
    );
  };

  const handleStart = async () => {
    if (selectedSymbols.length === 0) {
      alert("Please select at least one symbol to trade.");
      return;
    }
    setActionLoading(true);
    await onStartBot(selectedSymbols, mode);
    setActionLoading(false);
  };

  const handleStop = async () => {
    setActionLoading(true);
    await onStopBot(mode);
    setActionLoading(false);
  };

  const handleEmergency = async () => {
    setActionLoading(true);
    await onEmergencyClose(mode);
    setActionLoading(false);
  };

  const activeSession = status?.active_sessions?.[0] || null;
  const currentPrice = activeSession ? activeSession.current_price : null;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
      {/* Top statistics summary cards */}
      <KPIWidget account={status?.account} positions={positions} activeSession={activeSession} />

      {/* Execution panel and grid chart */}
      <div className="charts-grid">
        {/* Controls Card */}
        <div className="control-card">
          <div className="control-card-title">
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ color: isLive ? 'var(--warning)' : 'var(--secondary)' }}>
              <rect x="2" y="2" width="20" height="8" rx="2" ry="2" />
              <rect x="2" y="14" width="20" height="8" rx="2" ry="2" />
              <line x1="6" y1="6" x2="6.01" y2="6" />
              <line x1="6" y1="18" x2="6.01" y2="18" />
            </svg>
            <span>{isLive ? 'Live Trading Account Control' : 'Simulated Sandbox Control'}</span>
          </div>

          {status?.bot_running ? (
            <div className="control-row">
              <div style={{
                padding: '1.25rem',
                background: isLive ? 'rgba(255, 170, 0, 0.05)' : 'rgba(0, 240, 255, 0.05)',
                border: `1px solid ${isLive ? 'rgba(255, 170, 0, 0.15)' : 'rgba(0, 240, 255, 0.15)'}`,
                borderRadius: '8px',
                display: 'flex',
                gap: '10px'
              }}>
                <InfoIcon style={{ color: isLive ? 'var(--warning)' : 'var(--secondary)', flexShrink: 0, marginTop: '2px' }} />
                <div style={{ fontSize: '0.9rem', lineHeight: '1.4' }}>
                  <strong>Bot Engine running</strong> for <strong>{status.running_symbols.join(", ")}</strong> in <strong>{isLive ? 'LIVE ACCOUNT' : 'SIMULATED SANDBOX'}</strong>. Grid monitoring threads are actively listening.
                </div>
              </div>
              <div className="control-actions-row">
                <button className="btn btn-danger" style={{ flex: 1 }} onClick={handleStop} disabled={actionLoading}>
                  <StopIcon />
                  <span>Stop Bot Loops</span>
                </button>
                <button className="btn btn-secondary" onClick={handleEmergency} disabled={actionLoading}>
                  <span>Emergency Close All</span>
                </button>
              </div>
            </div>
          ) : (
            <div className="control-row">
              <div className="control-item">
                <div className="control-label">Select Trading Instruments</div>
                <div className="symbol-check-grid" style={{ marginTop: '0.5rem' }}>
                  {symbolsData?.active?.map((sym) => (
                    <div
                      key={sym}
                      className={`symbol-check-item ${selectedSymbols.includes(sym) ? 'selected' : ''}`}
                      onClick={() => toggleSymbolSelection(sym)}
                    >
                      <span className="symbol-check-label">{sym}</span>
                      <div className="checkbox-custom"></div>
                    </div>
                  ))}
                </div>
              </div>

              {isLive && (
                <div style={{
                  padding: '0.85rem 1rem',
                  background: 'rgba(255, 51, 102, 0.1)',
                  border: '1px solid rgba(255, 51, 102, 0.25)',
                  borderRadius: '8px',
                  display: 'flex',
                  gap: '8px'
                }}>
                  <AlertIcon style={{ color: 'var(--red)', flexShrink: 0, marginTop: '2px' }} />
                  <span style={{ fontSize: '0.8rem', color: 'var(--red)', lineHeight: '1.35', fontWeight: '500' }}>
                    CAUTION: Starting this loop places real trades on your live broker account. Verify your settings page overrides before running!
                  </span>
                </div>
              )}

              <button
                className="btn"
                style={{
                  background: isLive ? 'linear-gradient(135deg, var(--warning), #E67E22)' : 'linear-gradient(135deg, var(--primary), #6A11CB)',
                  color: isLive ? '#000' : 'var(--text-white)',
                  boxShadow: isLive ? '0 4px 15px rgba(255, 170, 0, 0.2)' : '0 4px 15px var(--primary-glow)',
                  fontWeight: '700',
                  marginTop: '0.5rem'
                }}
                onClick={handleStart}
                disabled={actionLoading}
              >
                <PlayIcon />
                <span>Start {isLive ? 'Live Trading' : 'Forward Tester'}</span>
              </button>
            </div>
          )}
        </div>

        {/* Spatial Grid visualizer card */}
        <div className="chart-card">
          <div className="chart-header">
            <h3 className="chart-title">
              <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ color: isLive ? 'var(--warning)' : 'var(--secondary)' }}>
                <line x1="4" y1="21" x2="4" y2="14" />
                <line x1="4" y1="10" x2="4" y2="3" />
                <line x1="12" y1="21" x2="12" y2="12" />
                <line x1="12" y1="8" x2="12" y2="3" />
                <line x1="20" y1="21" x2="20" y2="16" />
                <line x1="20" y1="12" x2="20" y2="3" />
              </svg>
              <span>{isLive ? 'Live Grid Visualizer' : 'Simulated Grid Visualizer'} {activeSession ? `(${activeSession.symbol})` : ''}</span>
            </h3>
          </div>
          <div className="chart-wrapper">
            <LayerChart activeSession={activeSession} currentPrice={currentPrice} config={config} />
          </div>
        </div>
      </div>

      {/* Account Equity line chart */}
      <div className="chart-card">
        <div className="chart-header">
          <h3 className="chart-title">
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ color: isLive ? 'var(--warning)' : 'var(--secondary)' }}>
              <path d="M12 20V10M18 20V4M6 20v-4" />
            </svg>
            <span>{isLive ? 'Live Account Equity Curve' : 'Simulated Account Equity Curve'}</span>
          </h3>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Realized returns over past 30 days</span>
        </div>
        <div className="chart-wrapper">
          <EquityChart data={history} />
        </div>
      </div>

      {/* Active Position Grid Table */}
      <PositionsTable positions={positions} onEmergencyClose={handleEmergency} />
    </div>
  );
};

export default TradingDashboard;
