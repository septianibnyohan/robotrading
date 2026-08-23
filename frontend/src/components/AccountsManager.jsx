import React, { useState } from 'react';

const AccountsManager = ({
  accounts,
  status,
  symbolsData,
  onAddAccount,
  onDeleteAccount,
  onStartAccount,
  onStopAccount
}) => {
  const [formOpen, setFormOpen] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editingLogin, setEditingLogin] = useState(null);

  const [name, setName] = useState('');
  const [login, setLogin] = useState('');
  const [password, setPassword] = useState('');
  const [server, setServer] = useState('');
  const [path, setPath] = useState('');
  const [selectedSymbols, setSelectedSymbols] = useState([]);
  const [submitting, setSubmitting] = useState(false);

  const resetForm = () => {
    setName('');
    setLogin('');
    setPassword('');
    setServer('');
    setPath('');
    setSelectedSymbols([]);
    setIsEditing(false);
    setEditingLogin(null);
    setFormOpen(false);
  };

  const handleEditClick = (acct) => {
    setName(acct.name);
    setLogin(acct.login.toString());
    setPassword(acct.password || '');
    setServer(acct.server);
    setPath(acct.path);
    setSelectedSymbols(acct.symbols || []);
    setIsEditing(true);
    setEditingLogin(acct.login);
    setFormOpen(true);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!name || !login || !password || !server || !path) {
      alert("Please fill in all fields.");
      return;
    }
    if (selectedSymbols.length === 0) {
      alert("Please select at least one symbol for this account.");
      return;
    }

    setSubmitting(true);
    const success = await onAddAccount({
      name,
      login: parseInt(login),
      password,
      server,
      path,
      symbols: selectedSymbols
    });
    setSubmitting(false);

    if (success) {
      resetForm();
    }
  };

  const toggleSymbol = (sym) => {
    setSelectedSymbols((prev) =>
      prev.includes(sym) ? prev.filter((s) => s !== sym) : [...prev, sym]
    );
  };

  // Find dynamic details from state if account is running
  const getAccountStatus = (acctLogin) => {
    const liveAcct = status?.live?.accounts?.find((a) => a.login === acctLogin);
    return liveAcct || { bot_running: false, account: { server: "OFFLINE", balance: 0.0, equity: 0.0, profit: 0.0 } };
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
      <div className="main-header" style={{ paddingBottom: '1rem', borderBottom: '1px solid var(--border)' }}>
        <div className="header-title-container">
          <h1>MT5 Accounts Manager</h1>
          <p>Configure and launch concurrent MetaTrader 5 terminal processes</p>
        </div>
        <button 
          className="btn btn-primary"
          onClick={() => {
            if (formOpen) {
              resetForm();
            } else {
              setFormOpen(true);
            }
          }}
        >
          {formOpen ? 'Cancel' : 'Add MT5 Account'}
        </button>
      </div>

      {formOpen && (
        <form onSubmit={handleSubmit} className="config-form" style={{ maxWidth: '700px' }}>
          <div className="config-section-title">
            {isEditing ? 'Edit Live Account Configuration' : 'Configure New Live Account'}
          </div>
          
          <div className="form-row-grid">
            <div className="form-group">
              <label className="form-label">Friendly Name</label>
              <input 
                type="text" 
                className="form-input" 
                placeholder="e.g. IC Markets Live" 
                value={name} 
                onChange={(e) => setName(e.target.value)} 
              />
            </div>
            <div className="form-group">
              <label className="form-label">Login ID (Account Number)</label>
              <input 
                type="number" 
                className="form-input" 
                placeholder="e.g. 123456" 
                value={login} 
                onChange={(e) => setLogin(e.target.value)} 
                disabled={isEditing}
              />
            </div>
          </div>

          <div className="form-row-grid">
            <div className="form-group">
              <label className="form-label">Password</label>
              <input 
                type="password" 
                className="form-input" 
                placeholder="MT5 Password" 
                value={password} 
                onChange={(e) => setPassword(e.target.value)} 
              />
            </div>
            <div className="form-group">
              <label className="form-label">Server</label>
              <input 
                type="text" 
                className="form-input" 
                placeholder="e.g. Exness-MT5-Real" 
                value={server} 
                onChange={(e) => setServer(e.target.value)} 
              />
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">MetaTrader 5 Terminal Path (`terminal64.exe`)</label>
            <input 
              type="text" 
              className="form-input" 
              placeholder="e.g. C:\Program Files\MetaTrader 5\terminal64.exe" 
              value={path} 
              onChange={(e) => setPath(e.target.value)} 
            />
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              Note: Double-check that this path is absolute and points directly to the executable file of this specific broker setup.
            </span>
          </div>

          <div className="form-group">
            <label className="form-label">Instruments to Trade</label>
            <div className="symbol-check-grid" style={{ marginTop: '0.25rem' }}>
              {symbolsData?.active?.map((sym) => (
                <div
                  key={sym}
                  className={`symbol-check-item ${selectedSymbols.includes(sym) ? 'selected' : ''}`}
                  onClick={() => toggleSymbol(sym)}
                >
                  <span className="symbol-check-label">{sym}</span>
                  <div className="checkbox-custom"></div>
                </div>
              ))}
            </div>
          </div>

          <div style={{ display: 'flex', gap: '0.75rem' }}>
            <button 
              type="submit" 
              className="btn btn-success" 
              style={{ padding: '0.75rem 2rem', fontWeight: 'bold' }}
              disabled={submitting}
            >
              {submitting ? 'Saving Config...' : isEditing ? 'Save Changes' : 'Save Account Settings'}
            </button>
            {isEditing && (
              <button 
                type="button" 
                className="btn btn-secondary" 
                style={{ padding: '0.75rem 2rem', fontWeight: 'bold' }}
                onClick={resetForm}
              >
                Cancel Edit
              </button>
            )}
          </div>
        </form>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '1.5rem' }}>
        {accounts.length === 0 ? (
          <div className="control-card" style={{ gridColumn: '1 / -1', padding: '3rem', textAlign: 'center', color: 'var(--text-muted)' }}>
            No accounts configured yet. Click "Add MT5 Account" at the top to configure one.
          </div>
        ) : (
          accounts.map((acct) => {
            const liveState = getAccountStatus(acct.login);
            const isRunning = liveState.bot_running;
            
            return (
              <div key={acct.login} className="control-card" style={{ 
                borderLeft: `4px solid ${isRunning ? 'var(--green)' : 'var(--border)'}`,
                display: 'flex',
                flexDirection: 'column',
                gap: '1.25rem'
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
                  <div>
                    <h3 style={{ color: 'var(--text-white)', fontSize: '1.1rem', fontWeight: '700' }}>{acct.name}</h3>
                    <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Login: #{acct.login}</span>
                  </div>
                  <span className={`badge ${isRunning ? 'badge-connected' : 'badge-disconnected'}`}>
                    <span className="badge-dot"></span>
                    {isRunning ? 'Running' : 'Offline'}
                  </span>
                </div>

                <div style={{ 
                  background: 'rgba(0, 0, 0, 0.2)', 
                  padding: '0.85rem', 
                  borderRadius: '6px', 
                  fontSize: '0.85rem',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '0.5rem'
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: 'var(--text-muted)' }}>Broker Server:</span>
                    <span style={{ color: 'var(--text-white)', fontWeight: '500' }}>{acct.server}</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: 'var(--text-muted)' }}>Terminal:</span>
                    <span 
                      style={{ color: 'var(--text-muted)', fontSize: '0.75rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '180px' }}
                      title={acct.path}
                    >
                      {acct.path.split(/[\\/]/).pop()}
                    </span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: 'var(--text-muted)' }}>Active Symbols:</span>
                    <span style={{ color: 'var(--secondary)', fontWeight: '600' }}>{acct.symbols.join(', ')}</span>
                  </div>
                </div>

                {isRunning && (
                  <div style={{ 
                    display: 'grid', 
                    gridTemplateColumns: '1fr 1fr', 
                    gap: '0.75rem', 
                    background: 'rgba(0, 240, 255, 0.03)',
                    border: '1px solid rgba(0, 240, 255, 0.08)',
                    padding: '0.85rem', 
                    borderRadius: '6px',
                    fontSize: '0.85rem'
                  }}>
                    <div>
                      <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>Balance</div>
                      <div style={{ color: 'var(--text-white)', fontWeight: '700', fontSize: '1rem', marginTop: '2px' }}>
                        ${liveState.account?.balance?.toFixed(2) || '0.00'}
                      </div>
                    </div>
                    <div>
                      <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>Equity</div>
                      <div style={{ color: 'var(--text-white)', fontWeight: '700', fontSize: '1rem', marginTop: '2px' }}>
                        ${liveState.account?.equity?.toFixed(2) || '0.00'}
                      </div>
                    </div>
                  </div>
                )}

                <div style={{ display: 'flex', gap: '0.5rem', marginTop: 'auto' }}>
                  {isRunning ? (
                    <button 
                      className="btn btn-danger" 
                      style={{ flex: 1 }}
                      onClick={() => onStopAccount(acct.login)}
                    >
                      Stop Bot
                    </button>
                  ) : (
                    <button 
                      className="btn btn-success" 
                      style={{ flex: 1 }}
                      onClick={() => onStartAccount(acct.login)}
                    >
                      Start Bot
                    </button>
                  )}
                  
                  {/* Edit Account Action Button */}
                  <button 
                    className="btn btn-secondary btn-icon-only"
                    onClick={() => handleEditClick(acct)}
                    disabled={isRunning}
                    title={isRunning ? "Stop the bot process to edit account details" : "Edit Account Config"}
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M12 20h9"></path>
                      <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path>
                    </svg>
                  </button>

                  <button 
                    className="btn btn-secondary btn-icon-only"
                    onClick={() => {
                      if (window.confirm(`Are you sure you want to delete account ${acct.name} (${acct.login})?`)) {
                        onDeleteAccount(acct.login);
                      }
                    }}
                    title="Delete Account Config"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="3 6 5 6 21 6"></polyline>
                      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                      <line x1="10" y1="11" x2="10" y2="17"></line>
                      <line x1="14" y1="11" x2="14" y2="17"></line>
                    </svg>
                  </button>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};

export default AccountsManager;
