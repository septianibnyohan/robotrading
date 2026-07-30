import React, { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import KPIWidget from './components/KPIWidget';
import LayerChart from './components/LayerChart';
import EquityChart from './components/EquityChart';
import PositionsTable from './components/PositionsTable';
import ConfigManager from './components/ConfigManager';
import BacktestManager from './components/BacktestManager';
import LogViewer from './components/LogViewer';
import { PlayIcon, StopIcon, InfoIcon, AlertIcon } from './components/Icons';

const App = () => {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [status, setStatus] = useState(null);
  const [positions, setPositions] = useState([]);
  const [history, setHistory] = useState([]);
  const [config, setConfig] = useState(null);
  const [symbolsData, setSymbolsData] = useState({ active: [], available: [] });
  
  // Selection state for starting the bot
  const [selectedSymbols, setSelectedSymbols] = useState([]);
  const [startMode, setStartMode] = useState('forward_test'); // 'forward_test' | 'live'
  const [actionLoading, setActionLoading] = useState(false);

  // Poll status & positions
  const fetchData = async () => {
    try {
      // 1. Status
      const statusRes = await fetch('http://127.0.0.1:8000/api/status');
      if (statusRes.ok) {
        const statusData = await statusRes.json();
        setStatus(statusData);
      }

      // 2. Positions
      const posRes = await fetch('http://127.0.0.1:8000/api/positions');
      if (posRes.ok) {
        const posData = await posRes.json();
        setPositions(posData);
      }
    } catch (err) {
      console.error("Error polling trading API data:", err);
    }
  };

  const fetchStaticData = async () => {
    try {
      // 1. Configs
      const configRes = await fetch('http://127.0.0.1:8000/api/config');
      if (configRes.ok) {
        const configData = await configRes.json();
        setConfig(configData);
      }

      // 2. Symbols
      const symbolsRes = await fetch('http://127.0.0.1:8000/api/symbols');
      if (symbolsRes.ok) {
        const symbolsData = await symbolsRes.json();
        setSymbolsData(symbolsData);
        // Default selected symbols to the active ones in config if none selected
        if (selectedSymbols.length === 0) {
          setSelectedSymbols(symbolsData.active.slice(0, 1));
        }
      }

      // 3. History
      const histRes = await fetch('http://127.0.0.1:8000/api/history');
      if (histRes.ok) {
        const histData = await histRes.json();
        setHistory(histData);
      }
    } catch (err) {
      console.error("Error fetching static configuration data:", err);
    }
  };

  // Initial load
  useEffect(() => {
    fetchStaticData();
    fetchData();
    const interval = setInterval(fetchData, 1500);
    return () => clearInterval(interval);
  }, []);

  // Sync selected symbols when active symbols list loads
  useEffect(() => {
    if (symbolsData.active.length > 0 && selectedSymbols.length === 0) {
      setSelectedSymbols([symbolsData.active[0]]);
    }
  }, [symbolsData]);

  // Actions
  const handleStartBot = async () => {
    if (selectedSymbols.length === 0) {
      alert("Please select at least one symbol to trade.");
      return;
    }
    setActionLoading(true);
    try {
      const res = await fetch('http://127.0.0.1:8000/api/control', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbols: selectedSymbols,
          mode: startMode
        })
      });
      if (res.ok) {
        await fetchData();
        // Refresh history to load simulated starting state
        setTimeout(fetchStaticData, 1000);
      } else {
        const err = await res.json();
        alert("Start Error: " + err.detail);
      }
    } catch (err) {
      alert("Failed to communicate with the web server API.");
    } finally {
      setActionLoading(false);
    }
  };

  const handleStopBot = async () => {
    setActionLoading(true);
    try {
      const res = await fetch('http://127.0.0.1:8000/api/control/stop', {
        method: 'POST'
      });
      if (res.ok) {
        await fetchData();
      } else {
        alert("Failed to stop bot.");
      }
    } catch (err) {
      alert("Connection failure.");
    } finally {
      setActionLoading(false);
    }
  };

  const handleEmergencyClose = async () => {
    if (!window.confirm("Are you sure you want to CLOSE ALL open positions for active symbols? This exits all layers immediately!")) {
      return;
    }
    setActionLoading(true);
    try {
      const res = await fetch('http://127.0.0.1:8000/api/control/close-all', {
        method: 'POST'
      });
      if (res.ok) {
        await fetchData();
      } else {
        alert("Emergency Close failed.");
      }
    } catch (err) {
      alert("Connection failure.");
    } finally {
      setActionLoading(false);
    }
  };

  const handleSaveConfig = async (symbol, updatedConfig) => {
    try {
      const res = await fetch('http://127.0.0.1:8000/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbol,
          config: updatedConfig
        })
      });
      if (res.ok) {
        // Refresh local config state
        const configRes = await fetch('http://127.0.0.1:8000/api/config');
        const configData = await configRes.json();
        setConfig(configData);
        return true;
      }
    } catch (err) {
      console.error("Save config error:", err);
    }
    return false;
  };

  const toggleSymbolSelection = (sym) => {
    setSelectedSymbols((prev) => 
      prev.includes(sym) ? prev.filter(s => s !== sym) : [...prev, sym]
    );
  };

  // Resolve active session details for dashboard visualizer (first active running symbol)
  const activeSession = status?.active_sessions?.[0] || null;
  const currentPrice = activeSession ? activeSession.current_price : null;

  return (
    <div className="app-container">
      {/* Sidebar Navigation */}
      <Sidebar activeTab={activeTab} setActiveTab={setActiveTab} />

      {/* Main Layout Area */}
      <main className="main-content">
        
        {/* Header Block */}
        <header className="main-header">
          <div className="header-title-container">
            <h1>
              {activeTab === 'dashboard' && 'Trading Dashboard'}
              {activeTab === 'backtest' && 'Historical Backtest'}
              {activeTab === 'settings' && 'Strategy Configuration'}
              {activeTab === 'logs' && 'System Log Viewer'}
            </h1>
            <p>
              {activeTab === 'dashboard' && 'Real-time layer grids tracking and execution status'}
              {activeTab === 'backtest' && 'Run historical simulations and inspect risk distribution'}
              {activeTab === 'settings' && 'Modify lot multipliers, ATR spacing coefficients, and overrides'}
              {activeTab === 'logs' && 'Console tail output of btc_layer_bot.log'}
            </p>
          </div>

          {/* Connection Indicators */}
          <div className="status-badges">
            {status?.mt5_connected ? (
              <span className="badge badge-connected">
                <span className="badge-dot"></span>
                <span>MT5 connected</span>
              </span>
            ) : (
              <span className="badge badge-disconnected">
                <span className="badge-dot"></span>
                <span>MT5 offline</span>
              </span>
            )}
            
            {status?.bot_running && (
              <span className={`badge ${status.mode === 'live' ? 'badge-mode-live' : 'badge-mode'}`}>
                <span className="badge-dot" style={{ background: 'currentColor' }}></span>
                <span>{status.mode === 'live' ? 'LIVE MODE' : 'FORWARD TEST'}</span>
              </span>
            )}
          </div>
        </header>

        {/* Content Tabs */}

        {/* TAB 1: DASHBOARD */}
        {activeTab === 'dashboard' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
            
            {/* KPI Cards */}
            <KPIWidget account={status?.account} positions={positions} activeSession={activeSession} />

            {/* Controls & Spatial Grid Chart */}
            <div className="charts-grid">
              
              {/* Bot Control Panel */}
              <div className="control-card">
                <div className="control-card-title">
                  <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ color: 'var(--secondary)' }}>
                    <rect x="2" y="2" width="20" height="8" rx="2" ry="2"/>
                    <rect x="2" y="14" width="20" height="8" rx="2" ry="2"/>
                    <line x1="6" y1="6" x2="6.01" y2="6"/>
                    <line x1="6" y1="18" x2="6.01" y2="18"/>
                  </svg>
                  <span>Trading Execution Control</span>
                </div>

                {status?.bot_running ? (
                  /* Running state controls */
                  <div className="control-row">
                    <div style={{ padding: '1.25rem', background: 'rgba(0, 240, 255, 0.05)', border: '1px solid rgba(0, 240, 255, 0.15)', borderRadius: '8px', display: 'flex', gap: '10px' }}>
                      <InfoIcon className="text-red" style={{ color: 'var(--secondary)', flexShrink: 0, marginTop: '2px' }} />
                      <div style={{ fontSize: '0.9rem', lineHeight: '1.4' }}>
                        <strong>Bot Engine running</strong> for <strong>{status.running_symbols.join(", ")}</strong> in <strong>{status.mode === 'live' ? 'LIVE TRADING' : 'FORWARD TEST'}</strong>. Grid monitoring threads are active.
                      </div>
                    </div>
                    <div className="control-actions-row">
                      <button className="btn btn-danger" style={{ flex: 1 }} onClick={handleStopBot} disabled={actionLoading}>
                        <StopIcon />
                        <span>Stop Trading Engine</span>
                      </button>
                      <button className="btn btn-secondary" onClick={handleEmergencyClose} disabled={actionLoading}>
                        <span>Emergency Close All</span>
                      </button>
                    </div>
                  </div>
                ) : (
                  /* Stopped state controls */
                  <div className="control-row">
                    <div className="control-item">
                      <div className="control-label">Execution Mode</div>
                      <div className="mode-selector">
                        <button
                          className={`mode-option-btn ${startMode === 'forward_test' ? 'selected' : ''}`}
                          onClick={() => setStartMode('forward_test')}
                        >
                          Simulated Forward Test
                        </button>
                        <button
                          className={`mode-option-btn ${startMode === 'live' ? 'selected live-mode' : ''}`}
                          onClick={() => setStartMode('live')}
                        >
                          Live Trading Account
                        </button>
                      </div>
                    </div>

                    <div className="control-item">
                      <div className="control-label">Select Trading Instruments</div>
                      <div className="symbol-check-grid">
                        {symbolsData.active.map((sym) => (
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

                    {startMode === 'live' && (
                      <div style={{ padding: '0.85rem 1rem', background: 'rgba(255, 170, 0, 0.1)', border: '1px solid rgba(255, 170, 0, 0.25)', borderRadius: '8px', display: 'flex', gap: '8px' }}>
                        <AlertIcon style={{ color: 'var(--warning)', flexShrink: 0, marginTop: '2px' }} />
                        <span style={{ fontSize: '0.8rem', color: 'var(--warning)', lineHeight: '1.3' }}>
                          Warning: Live mode places real trades with your MT5 terminal credentials! Ensure parameters are correct.
                        </span>
                      </div>
                    )}

                    <button className="btn btn-primary" onClick={handleStartBot} disabled={actionLoading} style={{ marginTop: '0.5rem' }}>
                      <PlayIcon />
                      <span>Start Trading Bot</span>
                    </button>
                  </div>
                )}
              </div>

              {/* Grid visualizer */}
              <div className="chart-card">
                <div className="chart-header">
                  <h3 className="chart-title">
                    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ color: 'var(--secondary)' }}>
                      <line x1="4" y1="21" x2="4" y2="14"/>
                      <line x1="4" y1="10" x2="4" y2="3"/>
                      <line x1="12" y1="21" x2="12" y2="12"/>
                      <line x1="12" y1="8" x2="12" y2="3"/>
                      <line x1="20" y1="21" x2="20" y2="16"/>
                      <line x1="20" y1="12" x2="20" y2="3"/>
                      <line x1="1" y1="14" x2="7" y2="14"/>
                      <line x1="9" y1="8" x2="15" y2="8"/>
                      <line x1="17" y1="16" x2="23" y2="16"/>
                    </svg>
                    <span>Spatial Grid Visualizer {activeSession ? `(${activeSession.symbol})` : ''}</span>
                  </h3>
                </div>
                <div className="chart-wrapper">
                  <LayerChart activeSession={activeSession} currentPrice={currentPrice} config={config} />
                </div>
              </div>
            </div>

            {/* Equity Curve Chart */}
            <div className="chart-card">
              <div className="chart-header">
                <h3 className="chart-title">
                  <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ color: 'var(--secondary)' }}>
                    <path d="M12 20V10M18 20V4M6 20v-4"/>
                  </svg>
                  <span>Historical Account Equity Curve</span>
                </h3>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Past 30 days closed baskets PnL</span>
              </div>
              <div className="chart-wrapper">
                <EquityChart data={history} />
              </div>
            </div>

            {/* Positions Table */}
            <PositionsTable positions={positions} onEmergencyClose={handleEmergencyClose} />

          </div>
        )}

        {/* TAB 2: HISTORICAL BACKTEST */}
        {activeTab === 'backtest' && (
          <BacktestManager config={config} />
        )}

        {/* TAB 3: CONFIGURATION SETTINGS */}
        {activeTab === 'settings' && (
          <ConfigManager config={config} onSaveConfig={handleSaveConfig} />
        )}

        {/* TAB 4: SYSTEM LOGS */}
        {activeTab === 'logs' && (
          <LogViewer />
        )}

      </main>
    </div>
  );
};

export default App;
