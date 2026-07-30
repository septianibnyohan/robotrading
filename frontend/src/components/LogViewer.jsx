import React, { useState, useEffect, useRef } from 'react';

const LogViewer = () => {
  const [logs, setLogs] = useState([]);
  const [autoScroll, setAutoScroll] = useState(true);
  const terminalRef = useRef(null);

  const fetchLogs = async () => {
    try {
      const res = await fetch('http://127.0.0.1:8000/api/logs');
      if (res.ok) {
        const data = await res.json();
        setLogs(data.logs || []);
      }
    } catch (err) {
      logger.error('Error fetching logs:', err);
    }
  };

  useEffect(() => {
    fetchLogs();
    const interval = setInterval(fetchLogs, 2500);
    return () => clearInterval(interval);
  }, []);

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
      <div className="terminal-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ width: '12px', height: '12px', borderRadius: '50%', background: 'var(--red)', boxShadow: '0 0 6px var(--red)' }}></span>
          <span style={{ width: '12px', height: '12px', borderRadius: '50%', background: 'var(--warning)', boxShadow: '0 0 6px var(--warning)' }}></span>
          <span style={{ width: '12px', height: '12px', borderRadius: '50%', background: 'var(--green)', boxShadow: '0 0 6px var(--green)' }}></span>
          <span style={{ marginLeft: '8px', fontSize: '0.85rem', fontWeight: 'bold', color: 'var(--text-muted)' }}>bash - btc_layer_bot.log</span>
        </div>
        <div style={{ display: 'flex', gap: '10px' }}>
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
          <div style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>Terminal offline or waiting for logs...</div>
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
