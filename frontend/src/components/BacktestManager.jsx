import React, { useState, useEffect } from 'react';
import EquityChart from './EquityChart';

const BacktestManager = ({ config }) => {
  const [selectedSymbol, setSelectedSymbol] = useState('');
  const [limit, setLimit] = useState(20000);
  const [useMt5, setUseMt5] = useState(false);
  const [status, setStatus] = useState('idle'); // 'idle' | 'running' | 'completed' | 'error'
  const [error, setError] = useState('');
  const [results, setResults] = useState(null);

  const symbols = config ? Object.keys(config) : [];

  useEffect(() => {
    if (symbols.length > 0 && !selectedSymbol) {
      setSelectedSymbol(symbols[0]);
    }
  }, [symbols, selectedSymbol]);

  // Poll status while running
  useEffect(() => {
    let interval;
    if (status === 'running') {
      interval = setInterval(async () => {
        try {
          const res = await fetch('http://127.0.0.1:8000/api/backtest/status');
          const data = await res.json();
          if (data.status === 'completed') {
            setStatus('completed');
            // Fetch results
            const resResults = await fetch('http://127.0.0.1:8000/api/backtest/results');
            const dataResults = await resResults.json();
            setResults(dataResults);
            clearInterval(interval);
          } else if (data.status === 'error') {
            setStatus('error');
            setError(data.error || 'Backtest failed.');
            clearInterval(interval);
          }
        } catch (err) {
          logger.error('Error polling backtest status:', err);
        }
      }, 2000);
    }
    return () => clearInterval(interval);
  }, [status]);

  const handleRunBacktest = async (e) => {
    e.preventDefault();
    if (status === 'running') return;

    setStatus('running');
    setError('');
    setResults(null);

    try {
      const res = await fetch('http://127.0.0.1:8000/api/backtest/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbol: selectedSymbol,
          limit: parseInt(limit),
          use_mt5: useMt5
        })
      });
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || 'Failed to start backtest.');
      }
    } catch (err) {
      setStatus('error');
      setError(err.message);
    }
  };

  const formatTime = (isoStr) => {
    if (!isoStr) return '';
    try {
      const d = new Date(isoStr);
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) + ' ' + d.toLocaleDateString([], { month: 'short', day: 'numeric' });
    } catch {
      return isoStr;
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
      {/* Parameters Panel */}
      <div className="control-card" style={{ width: '100%' }}>
        <div className="control-card-title">
          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ color: 'var(--secondary)' }}>
            <circle cx="12" cy="12" r="10" />
            <polygon points="10 8 16 12 10 16 10 8" />
          </svg>
          <span>Historical Backtest Run Settings</span>
        </div>
        <form className="form-row-grid" onSubmit={handleRunBacktest} style={{ alignItems: 'end' }}>
          <div className="form-group">
            <label className="form-label">Backtest Symbol</label>
            <select
              className="form-input form-select"
              value={selectedSymbol}
              onChange={(e) => setSelectedSymbol(e.target.value)}
              disabled={status === 'running'}
            >
              {symbols.map((sym) => (
                <option key={sym} value={sym}>{sym}</option>
              ))}
            </select>
          </div>
          <div className="form-group">
            <label className="form-label">Historical Bar Count (M1/M5)</label>
            <input
              type="number"
              className="form-input"
              value={limit}
              onChange={(e) => setLimit(e.target.value)}
              disabled={status === 'running'}
              required
            />
          </div>
          <div className="form-group">
            <label className="form-label">Data Source</label>
            <div className="mode-selector">
              <button
                type="button"
                className={`mode-option-btn ${!useMt5 ? 'selected' : ''}`}
                onClick={() => setUseMt5(false)}
                disabled={status === 'running'}
              >
                Local SQLite DB
              </button>
              <button
                type="button"
                className={`mode-option-btn ${useMt5 ? 'selected' : ''}`}
                onClick={() => setUseMt5(true)}
                disabled={status === 'running'}
              >
                MT5 Terminal
              </button>
            </div>
          </div>
          <button
            type="submit"
            className="btn btn-primary"
            style={{ height: '42px', width: '100%' }}
            disabled={status === 'running'}
          >
            {status === 'running' ? (
              <>
                <span className="badge-dot" style={{ background: 'var(--text-white)', animation: 'pulse-green 1s infinite' }}></span>
                <span>Simulating Strategy...</span>
              </>
            ) : (
              <>
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polygon points="5 3 19 12 5 21 5 3"/>
                </svg>
                <span>Run Historical Backtest</span>
              </>
            )}
          </button>
        </form>
      </div>

      {/* Error Message */}
      {status === 'error' && (
        <div style={{
          padding: '1.25rem',
          background: 'rgba(255, 51, 102, 0.12)',
          border: '1px solid rgba(255, 51, 102, 0.3)',
          borderRadius: '8px',
          color: 'var(--red)',
          fontSize: '0.95rem'
        }}>
          <strong>Backtest Error:</strong> {error}
        </div>
      )}

      {/* Running Overlay */}
      {status === 'running' && (
        <div style={{
          padding: '3rem',
          textAlign: 'center',
          background: 'var(--bg-card)',
          border: '1px solid var(--border)',
          borderRadius: '12px',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: '1rem',
          boxShadow: 'var(--box-shadow)'
        }}>
          <div style={{
            width: '40px',
            height: '40px',
            borderRadius: '50%',
            border: '3px solid rgba(0, 240, 255, 0.15)',
            borderTopColor: 'var(--secondary)',
            animation: 'spin 1s linear infinite'
          }}></div>
          <style>{`
            @keyframes spin {
              to { transform: rotate(360deg); }
            }
          `}</style>
          <div style={{ fontWeight: '600', color: 'var(--text-white)' }}>
            Processing historical minute-by-minute simulations...
          </div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            This can take up to 30 seconds depending on bar limit.
          </div>
        </div>
      )}

      {/* Results Panel */}
      {status === 'completed' && results && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
          {/* Metrics summary widgets */}
          <div className="backtest-metrics-grid">
            <div className="kpi-card kpi-secondary">
              <div className="kpi-label">Win Rate</div>
              <div className="kpi-value">{results.win_rate.toFixed(2)}%</div>
              <div className="kpi-subtext">Total Closed Trades: {results.total_trades}</div>
            </div>
            <div className="kpi-card kpi-success">
              <div className="kpi-label">Net Return</div>
              <div className="kpi-value" style={{ color: results.total_pnl >= 0 ? 'var(--green)' : 'var(--red)' }}>
                ${results.total_pnl >= 0 ? '+' : ''}{results.total_pnl.toFixed(2)} USD
              </div>
              <div className="kpi-subtext">Profit & Loss summary</div>
            </div>
            <div className="kpi-card kpi-primary">
              <div className="kpi-label">Max Drawdown</div>
              <div className="kpi-value">{results.max_dd.toFixed(2)}%</div>
              <div className="kpi-subtext">Peak-to-valley risk drop</div>
            </div>
            <div className="kpi-card kpi-secondary">
              <div className="kpi-label">Sharpe Ratio</div>
              <div className="kpi-value">{results.sharpe.toFixed(4)}</div>
              <div className="kpi-subtext">Risk-adjusted returns indicator</div>
            </div>
          </div>

          {/* Curve Chart and Distributions */}
          <div className="charts-grid">
            <div className="chart-card">
              <div className="chart-header">
                <h3 className="chart-title">
                  <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ color: 'var(--secondary)' }}>
                    <path d="M3 3v18h18" />
                    <path d="M18.7 8l-5.1 5.2-2.8-2.7L7 14.3" />
                  </svg>
                  <span>Simulation Equity Curve</span>
                </h3>
              </div>
              <div className="chart-wrapper">
                <EquityChart data={results.equity_curve} />
              </div>
            </div>

            <div className="chart-card">
              <div className="chart-header">
                <h3 className="chart-title">
                  <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ color: 'var(--warning)' }}>
                    <rect x="3" y="3" width="18" height="18" rx="2" />
                    <line x1="21" y1="9" x2="3" y2="9" />
                    <line x1="9" y1="21" x2="9" y2="9" />
                  </svg>
                  <span>Basket Size Distribution</span>
                </h3>
              </div>
              <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '0.75rem', justifyContent: 'center' }}>
                {Object.keys(results.layer_distribution).length === 0 ? (
                  <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem', textAlign: 'center' }}>
                    No baskets closed.
                  </div>
                ) : (
                  Object.entries(results.layer_distribution)
                    .sort(([k1], [k2]) => parseInt(k1) - parseInt(k2))
                    .map(([layers, count]) => {
                      const maxCount = Math.max(...Object.values(results.layer_distribution));
                      const pct = maxCount > 0 ? (count / maxCount) * 100 : 0;
                      return (
                        <div key={layers} style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', fontWeight: '500' }}>
                            <span>{layers} Layer(s) Basket</span>
                            <span style={{ color: 'var(--text-white)' }}>{count} closed</span>
                          </div>
                          <div style={{ height: '6px', background: 'rgba(255,255,255,0.05)', borderRadius: '4px', overflow: 'hidden' }}>
                            <div style={{ height: '100%', width: `${pct}%`, background: 'var(--secondary)', borderRadius: '4px', boxShadow: '0 0 5px var(--secondary-glow)' }}></div>
                          </div>
                        </div>
                      );
                    })
                )}
              </div>
            </div>
          </div>

          {/* Stats & Closed trades list */}
          <div className="control-grid">
            <div className="table-card" style={{ flex: 1 }}>
              <div className="table-title">Exit Reasons breakdown</div>
              <div className="table-responsive" style={{ marginTop: '1rem' }}>
                <table className="custom-table">
                  <thead>
                    <tr>
                      <th>Exit Reason</th>
                      <th>Baskets Closed</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(results.exit_reasons).map(([reason, count]) => (
                      <tr key={reason}>
                        <td style={{ fontWeight: '500' }}>{reason}</td>
                        <td className="font-mono" style={{ color: 'var(--text-white)' }}>{count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          <div className="table-card">
            <h3 className="table-title">Closed Simulation Trades List</h3>
            <div className="table-responsive" style={{ marginTop: '1rem', maxHeight: '400px', overflowY: 'auto' }}>
              <table className="custom-table">
                <thead>
                  <tr>
                    <th>Ticket</th>
                    <th>Type</th>
                    <th>Layers</th>
                    <th>Entry Price</th>
                    <th>Exit Price</th>
                    <th>Net Profit</th>
                    <th>Entry Time</th>
                    <th>Exit Time</th>
                    <th>Exit Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {results.trades.slice().reverse().map((trade) => (
                    <tr key={trade.ticket}>
                      <td className="font-mono">#{trade.ticket}</td>
                      <td>
                        <span className={`badge ${trade.type === 'BUY' ? 'badge-connected' : 'badge-disconnected'}`}>
                          {trade.type}
                        </span>
                      </td>
                      <td className="font-mono">{trade.basket_layers}</td>
                      <td className="font-mono">${trade.entry_price.toFixed(2)}</td>
                      <td className="font-mono">${trade.exit_price.toFixed(2)}</td>
                      <td className={`font-mono ${trade.pnl >= 0 ? 'text-green' : 'text-red'}`} style={{ fontWeight: '700' }}>
                        ${trade.pnl >= 0 ? '+' : ''}{trade.pnl.toFixed(2)}
                      </td>
                      <td style={{ fontSize: '0.8rem' }}>{formatTime(trade.entry_time)}</td>
                      <td style={{ fontSize: '0.8rem' }}>{formatTime(trade.exit_time)}</td>
                      <td>
                        <span style={{ fontSize: '0.8rem', color: 'var(--warning)', fontWeight: '600' }}>
                          {trade.exit_reason}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default BacktestManager;
