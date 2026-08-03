import React, { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import TradingDashboard from './components/TradingDashboard';
import ConfigManager from './components/ConfigManager';
import BacktestManager from './components/BacktestManager';
import LogViewer from './components/LogViewer';
import { API_BASE } from './config';

const App = () => {
  const [activeTab, setActiveTab] = useState('forward_test'); // 'forward_test' | 'live' | 'backtest' | 'settings' | 'logs'
  const [status, setStatus] = useState(null);
  
  // Dual-state management
  const [livePositions, setLivePositions] = useState([]);
  const [simPositions, setSimPositions] = useState([]);
  const [liveHistory, setLiveHistory] = useState([]);
  const [simHistory, setSimHistory] = useState([]);
  
  const [config, setConfig] = useState(null);
  const [symbolsData, setSymbolsData] = useState({ active: [], available: [] });

  const fetchData = async () => {
    try {
      // 1. Poll Status
      const statusRes = await fetch(`${API_BASE}/api/status`);
      if (statusRes.ok) {
        const statusData = await statusRes.json();
        setStatus(statusData);
      }

      // 2. Poll Positions (Live)
      const livePosRes = await fetch(`${API_BASE}/api/positions?mode=live`);
      if (livePosRes.ok) {
        const livePosData = await livePosRes.json();
        setLivePositions(livePosData);
      }

      // 3. Poll Positions (Simulated)
      const simPosRes = await fetch(`${API_BASE}/api/positions?mode=forward_test`);
      if (simPosRes.ok) {
        const simPosData = await simPosRes.json();
        setSimPositions(simPosData);
      }
    } catch (err) {
      console.error("Error polling dynamic trading states:", err);
    }
  };

  const fetchStaticAndHistory = async () => {
    try {
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
      const liveHistRes = await fetch(`${API_BASE}/api/history?mode=live`);
      if (liveHistRes.ok) {
        const data = await liveHistRes.json();
        setLiveHistory(data);
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

  // Actions
  const handleStartBot = async (symbols, mode) => {
    try {
      const res = await fetch(`${API_BASE}/api/control`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbols, mode })
      });
      if (res.ok) {
        await fetchData();
        // Stagger history refresh slightly to load initial simulator balance state
        setTimeout(fetchStaticAndHistory, 1000);
      } else {
        const err = await res.json();
        alert(`Failed to start bot in ${mode} mode: ${err.detail}`);
      }
    } catch (err) {
      alert("Failed to communicate with API web server.");
    }
  };

  const handleStopBot = async (mode) => {
    try {
      const res = await fetch(`${API_BASE}/api/control/stop`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode })
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

  const handleEmergencyClose = async (mode) => {
    if (!window.confirm(`Are you sure you want to CLOSE ALL open positions for active ${mode === 'live' ? 'LIVE' : 'SIMULATED'} sessions?`)) {
      return;
    }
    try {
      const res = await fetch(`${API_BASE}/api/control/close-all`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode })
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

  const handleSaveConfig = async (symbol, updatedConfig) => {
    try {
      const res = await fetch(`${API_BASE}/api/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbol, config: updatedConfig })
      });
      if (res.ok) {
        // Refresh configuration state
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
              {activeTab === 'settings' && 'Strategy Configuration'}
              {activeTab === 'logs' && 'System Log Viewer'}
            </h1>
            <p>
              {activeTab === 'live' && 'Monitor and execute active trading baskets on your live broker account'}
              {activeTab === 'forward_test' && 'Test bot layering grid parameters with real-time paper trading'}
              {activeTab === 'backtest' && 'Run historical simulations and inspect risk distribution'}
              {activeTab === 'settings' && 'Modify lot size parameters, ATR coefficients, and override timings'}
              {activeTab === 'logs' && 'Console tail output of btc_layer_bot.log'}
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
          <TradingDashboard
            mode="live"
            status={status?.live}
            positions={livePositions}
            history={liveHistory}
            config={config}
            symbolsData={symbolsData}
            onStartBot={handleStartBot}
            onStopBot={handleStopBot}
            onEmergencyClose={handleEmergencyClose}
          />
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

        {activeTab === 'settings' && (
          <ConfigManager config={config} onSaveConfig={handleSaveConfig} />
        )}

        {activeTab === 'logs' && (
          <LogViewer />
        )}

      </main>
    </div>
  );
};

export default App;
