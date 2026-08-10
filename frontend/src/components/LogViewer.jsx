import React, { useState, useEffect, useRef } from 'react';
import { API_BASE } from '../config';

const LogViewer = ({ accounts }) => {
  const [mode, setMode] = useState('forward_test'); // 'forward_test' | 'live'
  const [selectedLogin, setSelectedLogin] = useState(null);
  const [logs, setLogs] = useState([]);
  const [autoScroll, setAutoScroll] = useState(true);
  const terminalRef = useRef(null);

  // Initialize selected login
  useEffect(() => {
    if (accounts && accounts.length > 0 && !selectedLogin) {
      setSelectedLogin(accounts[0].login);
    }
  }, [accounts, selectedLogin]);

  const fetchLogs = async () => {
    try {
      let url = `${API_BASE}/api/logs?mode=${mode}`;
      if (mode === 'live' && selectedLogin) {
        url += `&login=${selectedLogin}`;
      }
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        setLogs(data.logs || []);
      }
    } catch (err) {
      console.error('Error fetching logs:', err);
    }
  };

  useEffect(() => {
    fetchLogs();
  }, [mode, selectedLogin]);

  useEffect(() => {
    const interval = setInterval(fetchLogs, 2500);
    return () => clearInterval(interval);
  }, [mode, selectedLogin]);

  useEffect(() => {
    if (autoScroll && terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  }, [logs, autoScroll]);

  const getLogClass = (line) => {
    if (line.includes('[ERROR]')) return 'terminal-line error';
    if (line.includes('[WARNING]')) return 'terminal-line warning';
    if (line.includes('[DEBUG]')) return 'terminal-line debug';
    return 'terminal-line info';
  };

  return (
    <div className="terminal-card">
      <div className="terminal-header" style={{ flexWrap: 'wrap', gap: '12px' }}>
        {/* Terminal Window dots & Mode Label */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ width: '12px', height: '12px', borderRadius: '50%', background: 'var(--red)', boxShadow: '0 0 6px var(--red)' }}></span>
          <span style={{ width: '12px', height: '12px', borderRadius: '50%', background: 'var(--warning)', boxShadow: '0 0 6px var(--warning)' }}></span>
          <span style={{ width: '12px', height: '12px', borderRadius: '50%', background: 'var(--green)', boxShadow: '0 0 6px var(--green)' }}></span>
          <span style={{ marginLeft: '8px', fontSize: '0.85rem', fontWeight: 'bold', color: 'var(--text-muted)' }}>
            bash - btc_layer_bot_{mode === 'live' ? `live_${selectedLogin || ''}` : 'sim'}.log
          </span>
        </div>

        {/* Action button bar */}
        <div style={{ display: 'flex', gap: '10px', alignItems: 'center', marginLeft: 'auto', flexWrap: 'wrap' }}>
          {/* Account Log Selector for Live mode */}
          {mode === 'live' && accounts && accounts.length > 0 && (
            <select
              className="form-select font-mono"
              style={{
                background: 'rgba(0,0,0,0.3)',
                color: 'var(--text-white)',
                border: '1px solid var(--border)',
                borderRadius: '6px',
                padding: '0.25rem 2rem 0.25rem 0.75rem',
                fontSize: '0.75rem',
                fontWeight: '600'
              }}
              value={selectedLogin || ''}
              onChange={(e) => setSelectedLogin(parseInt(e.target.value))}
            >
              {accounts.map((a) => (
                <option key={a.login} value={a.login}>
                  {a.name} ({a.login})
                </option>
              ))}
            </select>
          )}

          {/* Mode Selector */}
          <div style={{ display: 'flex', background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border)', borderRadius: '6px', padding: '2px' }}>
            <button
              className={`btn`}
              style={{
                padding: '0.25rem 0.65rem',
                fontSize: '0.75rem',
                background: mode === 'forward_test' ? 'var(--secondary)' : 'transparent',
                color: mode === 'forward_test' ? '#000' : 'var(--text-muted)',
                fontWeight: mode === 'forward_test' ? 'bold' : 'normal',
                boxShadow: mode === 'forward_test' ? '0 0 8px rgba(0, 240, 255, 0.3)' : 'none',
                border: 'none',
                borderRadius: '4px'
              }}
              onClick={() => setMode('forward_test')}
            >
              Simulated Logs
            </button>
            <button
              className={`btn`}
              style={{
                padding: '0.25rem 0.65rem',
                fontSize: '0.75rem',
                background: mode === 'live' ? 'var(--warning)' : 'transparent',
                color: mode === 'live' ? '#000' : 'var(--text-muted)',
                fontWeight: mode === 'live' ? 'bold' : 'normal',
                boxShadow: mode === 'live' ? '0 0 8px rgba(255, 170, 0, 0.3)' : 'none',
                border: 'none',
                borderRadius: '4px'
              }}
              onClick={() => setMode('live')}
            >
              Live Logs
            </button>
          </div>

          <button
            className="btn btn-secondary"
            style={{ padding: '0.35rem 0.75rem', fontSize: '0.75rem' }}
            onClick={() => setAutoScroll(!autoScroll)}
          >
            {autoScroll ? '✓ Auto-Scroll ON' : 'Auto-Scroll OFF'}
          </button>
          <button
            className="btn btn-secondary"
            style={{ padding: '0.35rem 0.75rem', fontSize: '0.75rem' }}
            onClick={fetchLogs}
          >
            Refresh
          </button>
        </div>
      </div>
      <div className="terminal-screen" ref={terminalRef}>
        {logs.length === 0 ? (
          <div style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>
            Terminal offline or waiting for logs in {mode === 'live' ? 'LIVE' : 'SIMULATED'} channel...
          </div>
        ) : (
          logs.map((line, idx) => (
            <div key={idx} className={getLogClass(line)}>
              {line}
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default LogViewer;
