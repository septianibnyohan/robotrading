import React, { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import TradingDashboard from './components/TradingDashboard';
import ConfigManager from './components/ConfigManager';
import BacktestManager from './components/BacktestManager';
import LogViewer from './components/LogViewer';
import AccountsManager from './components/AccountsManager';
import DXYDashboard from './components/DXYDashboard';
import { API_BASE } from './config';

const App = () => {
  const [activeTab, setActiveTab] = useState('forward_test'); // 'forward_test' | 'live' | 'backtest' | 'accounts' | 'settings' | 'logs'
  const [status, setStatus] = useState(null);
  
  // Accounts settings and selection
  const [accounts, setAccounts] = useState([]);
  const [selectedLiveLogin, setSelectedLiveLogin] = useState(null);
  
  // Dual-state management
  const [livePositions, setLivePositions] = useState([]);
  const [simPositions, setSimPositions] = useState([]);
  const [liveHistory, setLiveHistory] = useState([]);
  const [simHistory, setSimHistory] = useState([]);
  
  const [config, setConfig] = useState(null);
  const [symbolsData, setSymbolsData] = useState({ active: [], available: [] });
  const [dxyData, setDxyData] = useState(null);

  const fetchAccounts = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/accounts`);
      if (res.ok) {
        const data = await res.json();
        setAccounts(data);
        if (data.length > 0 && !selectedLiveLogin) {
          setSelectedLiveLogin(data[0].login);
        }
      }
    } catch (err) {
      console.error("Error fetching accounts:", err);
    }
  };

  const fetchData = async () => {
    try {
      // 1. Poll Status
      const statusRes = await fetch(`${API_BASE}/api/status`);
      if (statusRes.ok) {
        const statusData = await statusRes.json();
        setStatus(statusData);
      }

      // 2. Poll Positions (Live)
      if (selectedLiveLogin) {
        const livePosRes = await fetch(`${API_BASE}/api/positions?mode=live&login=${selectedLiveLogin}`);
        if (livePosRes.ok) {
          const livePosData = await livePosRes.json();
          setLivePositions(livePosData);
        }
      } else {
        setLivePositions([]);
      }

      // 3. Poll Positions (Simulated)
      const simPosRes = await fetch(`${API_BASE}/api/positions?mode=forward_test`);
      if (simPosRes.ok) {
        const simPosData = await simPosRes.json();
        setSimPositions(simPosData);
      }

      // 4. Poll Dollar Index (DXY)
      const dxyRes = await fetch(`${API_BASE}/api/dxy/latest`);
      if (dxyRes.ok) {
        const dxyVal = await dxyRes.json();
        setDxyData(dxyVal);
      }
    } catch (err) {
      console.error("Error polling dynamic trading states:", err);
    }
  };

  const fetchStaticAndHistory = async () => {
    try {
      // Refresh accounts list
      await fetchAccounts();

      // 1. Configs
      const configRes = await fetch(`${API_BASE}/api/config`);
      if (configRes.ok) {
        const configData = await configRes.json();
        setConfig(configData);
      }

      // 2. Symbols
      const symbolsRes = await fetch(`${API_BASE}/api/symbols`);
      if (symbolsRes.ok) {
        const data = await symbolsRes.json();
        setSymbolsData(data);
      }

      // 3. History (Live)
      if (selectedLiveLogin) {
        const liveHistRes = await fetch(`${API_BASE}/api/history?mode=live&login=${selectedLiveLogin}`);
        if (liveHistRes.ok) {
          const data = await liveHistRes.json();
          setLiveHistory(data);
        }
      } else {
        setLiveHistory([]);
      }

      // 4. History (Simulated)
      const simHistRes = await fetch(`${API_BASE}/api/history?mode=forward_test`);
      if (simHistRes.ok) {
        const data = await simHistRes.json();
        setSimHistory(data);
      }
    } catch (err) {
      console.error("Error fetching trading history or configurations:", err);
    }
  };

  // Initial load and status polling setup
  useEffect(() => {
    fetchStaticAndHistory();
    fetchData();
    const interval = setInterval(fetchData, 1500);
    return () => clearInterval(interval);
  }, []);

  // Poll live positions and history immediately when selected login changes
  useEffect(() => {
    if (selectedLiveLogin) {
      const fetchLiveAccountDetails = async () => {
        try {
          const posRes = await fetch(`${API_BASE}/api/positions?mode=live&login=${selectedLiveLogin}`);
          if (posRes.ok) setLivePositions(await posRes.json());
          
          const histRes = await fetch(`${API_BASE}/api/history?mode=live&login=${selectedLiveLogin}`);
          if (histRes.ok) setLiveHistory(await histRes.json());
        } catch (err) {
          console.error("Error fetching live account details:", err);
        }
      };
      fetchLiveAccountDetails();
    } else {
      setLivePositions([]);
      setLiveHistory([]);
    }
  }, [selectedLiveLogin]);

  // Actions
  const handleStartBot = async (symbols, mode, login = null) => {
    try {
      const bodyData = { symbols, mode };
      if (mode === 'live') bodyData.login = login;
      
      const res = await fetch(`${API_BASE}/api/control`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(bodyData)
      });
      if (res.ok) {
        await fetchData();
        setTimeout(fetchStaticAndHistory, 1000);
      } else {
        const err = await res.json();
        alert(`Failed to start bot: ${err.detail}`);
      }
    } catch (err) {
      alert("Failed to communicate with API web server.");
    }
  };

  const handleStopBot = async (mode, login = null) => {
    try {
      const bodyData = { mode };
      if (mode === 'live') bodyData.login = login;
      
      const res = await fetch(`${API_BASE}/api/control/stop`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(bodyData)
      });
      if (res.ok) {
        await fetchData();
      } else {
        alert("Failed to stop bot loops.");
      }
    } catch (err) {
      alert("Communication error.");
    }
  };

  const handleEmergencyClose = async (mode, login = null) => {
    const targetLabel = mode === 'live' ? `LIVE account #${login}` : 'SIMULATED';
    if (!window.confirm(`Are you sure you want to CLOSE ALL open positions for active ${targetLabel} sessions?`)) {
      return;
    }
    try {
      const bodyData = { mode };
      if (mode === 'live') bodyData.login = login;
      
      const res = await fetch(`${API_BASE}/api/control/close-all`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(bodyData)
      });
      if (res.ok) {
        await fetchData();
      } else {
        alert("Emergency close request failed.");
      }
    } catch (err) {
      alert("Communication error.");
    }
  };

  const handleAddAccount = async (accountData) => {
    try {
      const res = await fetch(`${API_BASE}/api/accounts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(accountData)
      });
      if (res.ok) {
        await fetchAccounts();
        if (!selectedLiveLogin) {
          setSelectedLiveLogin(accountData.login);
        }
        return true;
      } else {
        const err = await res.json();
        alert(`Failed to add account: ${err.detail}`);
      }
    } catch (err) {
      alert("Error adding account configuration.");
    }
    return false;
  };

  const handleDeleteAccount = async (login) => {
    try {
      const res = await fetch(`${API_BASE}/api/accounts/${login}`, {
        method: 'DELETE'
      });
      if (res.ok) {
        await fetchAccounts();
        if (selectedLiveLogin === login) {
          setSelectedLiveLogin(null);
        }
      } else {
        alert("Failed to delete account configuration.");
      }
    } catch (err) {
      alert("Communication error.");
    }
  };

  const handleSaveConfig = async (symbol, updatedConfig) => {
    try {
      const res = await fetch(`${API_BASE}/api/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbol, config: updatedConfig })
      });
      if (res.ok) {
        const configRes = await fetch(`${API_BASE}/api/config`);
        const configData = await configRes.json();
        setConfig(configData);
        return true;
      }
    } catch (err) {
      console.error("Save config error:", err);
    }
    return false;
  };

  const selectedAccountStatus = status?.live?.accounts?.find((a) => a.login === selectedLiveLogin) || null;

  return (
    <div className="app-container">
      {/* Sidebar navigation */}
      <Sidebar activeTab={activeTab} setActiveTab={setActiveTab} />

      {/* Main dashboard body */}
      <main className="main-content">
        
        {/* Header indicator panels */}
        <header className="main-header">
          <div className="header-title-container">
            <h1>
              {activeTab === 'live' && 'Live Trading Dashboard'}
              {activeTab === 'forward_test' && 'Simulated Sandbox'}
              {activeTab === 'backtest' && 'Historical Backtest'}
              {activeTab === 'dxy' && 'Dollar Index (DXY) Dashboard'}
              {activeTab === 'accounts' && 'Accounts Manager'}
              {activeTab === 'settings' && 'Strategy Configuration'}
              {activeTab === 'logs' && 'System Log Viewer'}
            </h1>
            <p>
              {activeTab === 'live' && 'Monitor and execute active trading baskets on your live broker account'}
              {activeTab === 'forward_test' && 'Test bot layering grid parameters with real-time paper trading'}
              {activeTab === 'backtest' && 'Run historical simulations and inspect risk distribution'}
              {activeTab === 'dxy' && 'Track real-time index metrics and long-term historical chart fluctuations'}
              {activeTab === 'accounts' && 'Configure and launch concurrent MetaTrader 5 terminal processes'}
              {activeTab === 'settings' && 'Modify lot size parameters, ATR coefficients, and override timings'}
              {activeTab === 'logs' && 'Console tail output of active strategy log files'}
            </p>
          </div>

          {/* Connection badge status */}
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
          </div>
        </header>

        {/* Tab Routing */}
        
        {activeTab === 'live' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            <div className="control-card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '1rem 1.5rem', flexWrap: 'wrap', gap: '12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <span style={{ fontSize: '0.9rem', color: 'var(--text-muted)', fontWeight: '600' }}>Selected Live Account:</span>
                <select
                  className="form-select font-mono"
                  style={{ 
                    background: 'rgba(0,0,0,0.3)', 
                    color: 'var(--text-white)', 
                    border: '1px solid var(--border)',
                    borderRadius: '6px',
                    padding: '0.4rem 2rem 0.4rem 0.75rem',
                    fontSize: '0.85rem',
                    fontWeight: '600',
                    width: '240px'
                  }}
                  value={selectedLiveLogin || ''}
                  onChange={(e) => setSelectedLiveLogin(parseInt(e.target.value))}
                >
                  {accounts.map((a) => (
                    <option key={a.login} value={a.login}>
                      {a.name} ({a.login})
                    </option>
                  ))}
                </select>
              </div>
              {selectedAccountStatus && (
                <span className={`badge ${selectedAccountStatus.bot_running ? 'badge-connected' : 'badge-disconnected'}`}>
                  <span className="badge-dot"></span>
                  {selectedAccountStatus.bot_running ? 'Trading Loop Active' : 'Offline'}
                </span>
              )}
            </div>

            {selectedLiveLogin ? (
              <TradingDashboard
                mode="live"
                status={selectedAccountStatus}
                positions={livePositions}
                history={liveHistory}
                config={config}
                symbolsData={symbolsData}
                onStartBot={(syms, m) => handleStartBot(syms, m, selectedLiveLogin)}
                onStopBot={(m) => handleStopBot(m, selectedLiveLogin)}
                onEmergencyClose={(m) => handleEmergencyClose(m, selectedLiveLogin)}
              />
            ) : (
              <div className="control-card" style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                No live MT5 accounts configured. Please add an account in the Accounts Manager tab first.
              </div>
            )}
          </div>
        )}

        {activeTab === 'forward_test' && (
          <TradingDashboard
            mode="forward_test"
            status={status?.forward_test}
            positions={simPositions}
            history={simHistory}
            config={config}
            symbolsData={symbolsData}
            onStartBot={handleStartBot}
            onStopBot={handleStopBot}
            onEmergencyClose={handleEmergencyClose}
          />
        )}

        {activeTab === 'backtest' && (
          <BacktestManager config={config} />
        )}

        {activeTab === 'dxy' && (
          <DXYDashboard dxyData={dxyData} />
        )}

        {activeTab === 'accounts' && (
          <AccountsManager
            accounts={accounts}
            status={status}
            symbolsData={symbolsData}
            onAddAccount={handleAddAccount}
            onDeleteAccount={handleDeleteAccount}
            onStartAccount={(login) => handleStartBot(null, 'live', login)}
            onStopAccount={(login) => handleStopBot('live', login)}
          />
        )}

        {activeTab === 'settings' && (
          <ConfigManager config={config} onSaveConfig={handleSaveConfig} />
        )}

        {activeTab === 'logs' && (
          <LogViewer accounts={accounts} />
        )}

      </main>
    </div>
  );
};

export default App;
