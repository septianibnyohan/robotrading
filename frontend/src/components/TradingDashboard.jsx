import React, { useState, useEffect } from 'react';
import KPIWidget from './KPIWidget';
import LayerChart from './LayerChart';
import EquityChart from './EquityChart';
import PositionsTable from './PositionsTable';
import HistoryTable from './HistoryTable';
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
  const botRunning = status?.bot_running || false;
  const activeSymbols = status?.active_symbols || [];

  // Default select current active symbols if bot is already running
  useEffect(() => {
    if (botRunning && activeSymbols.length > 0) {
      setSelectedSymbols(activeSymbols);
    }
  }, [botRunning, activeSymbols]);

  const handleToggleSymbol = (sym) => {
    if (botRunning) return; // Prevent edits when loop is running
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
    await onEmergencyClose(mode);
  };

  // Safe checks for sessions
  const activeSessions = status?.active_sessions || [];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* KPI Info Cards */}
      <KPIWidget account={status?.account} positions={positions} activeSession={activeSessions[0]} />

      {/* Grid Monitor & Control cards row */}
      <div className="charts-grid">
        {/* Controls Card */}
        <div className="control-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
            <h3 style={{ color: 'var(--text-white)', fontSize: '1.1rem', fontWeight: '700' }}>Engine Controller</h3>
            <span className={`badge ${botRunning ? 'badge-connected' : 'badge-disconnected'}`}>
              <span className="badge-dot"></span>
              {botRunning ? 'Active' : 'Offline'}
            </span>
          </div>

          <div className="form-group" style={{ marginBottom: '1.5rem' }}>
            <label className="form-label">Configure Trading Symbols</label>
            <div className="symbol-check-grid" style={{ marginTop: '0.5rem' }}>
              {symbolsData?.active?.map((sym) => (
                <div
                  key={sym}
                  className={`symbol-check-item ${selectedSymbols.includes(sym) ? 'selected' : ''} ${botRunning ? 'disabled' : ''}`}
                  onClick={() => handleToggleSymbol(sym)}
                >
                  <span className="symbol-check-label">{sym}</span>
                  <div className="checkbox-custom"></div>
                </div>
              ))}
            </div>
            {botRunning && (
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'block', marginTop: '0.5rem' }}>
                * Stop the strategy engine to update trading symbols.
              </span>
            )}
          </div>

          <div style={{ display: 'flex', gap: '0.75rem', marginTop: 'auto' }}>
            {botRunning ? (
              <button
                className="btn btn-danger"
                style={{ flex: 1, padding: '0.75rem' }}
                onClick={handleStop}
                disabled={actionLoading}
              >
                <StopIcon />
                <span>Stop Engine</span>
              </button>
            ) : (
              <button
                className="btn btn-success"
                style={{ flex: 1, padding: '0.75rem' }}
                onClick={handleStart}
                disabled={actionLoading}
              >
                <PlayIcon />
                <span>Start Engine</span>
              </button>
            )}
          </div>
        </div>

        {/* Visualizers Container */}
        <div className="visualizer-card">
          <div style={{ 
            display: 'grid', 
            gridTemplateColumns: activeSessions.length > 1 ? '1fr 1fr' : '1fr', 
            gap: '1.5rem',
            alignItems: 'start'
          }}>
            {activeSessions.length === 0 ? (
              <LayerChart activeSession={null} config={config} />
            ) : (
              activeSessions.map((session) => (
                <div key={session.symbol} style={{ display: 'flex', flexDirection: 'column', gap: '8px', width: '100%' }}>
                  <div style={{ fontSize: '0.85rem', fontWeight: 'bold', color: 'var(--text-white)', display: 'flex', justifyContent: 'space-between', padding: '0 4px' }}>
                    <span>{session.symbol} Grid Monitor</span>
                    <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>
                      Price: <span style={{ color: isLive ? 'var(--warning)' : 'var(--secondary)', fontWeight: 'bold' }}>{session.current_price?.toFixed(2) || '0.00'}</span>
                    </span>
                  </div>
                  <LayerChart activeSession={session} currentPrice={session.current_price} config={config} />
                </div>
              ))
            )}
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

      {/* Realized Transaction History Table */}
      <HistoryTable history={history} />
    </div>
  );
};

export default TradingDashboard;
