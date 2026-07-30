import React from 'react';
import { DashboardIcon, BacktestIcon, SettingsIcon, LogsIcon } from './Icons';

const Sidebar = ({ activeTab, setActiveTab }) => {
  const menuItems = [
    { id: 'dashboard', label: 'Dashboard', icon: <DashboardIcon className="menu-icon" /> },
    { id: 'backtest', label: 'Historical Backtest', icon: <BacktestIcon className="menu-icon" /> },
    { id: 'settings', label: 'Configuration', icon: <SettingsIcon className="menu-icon" /> },
    { id: 'logs', label: 'System Logs', icon: <LogsIcon className="menu-icon" /> },
  ];

  return (
    <div className="sidebar">
      <div className="logo-container">
        <div className="logo-icon"></div>
        <div className="logo-text">RoboBTC SaaS</div>
      </div>
      <nav style={{ flex: 1 }}>
        <ul className="sidebar-menu">
          {menuItems.map((item) => (
            <li key={item.id}>
              <button
                className={`menu-item-btn ${activeTab === item.id ? 'active' : ''}`}
                onClick={() => setActiveTab(item.id)}
              >
                {item.icon}
                <span>{item.label}</span>
              </button>
            </li>
          ))}
        </ul>
      </nav>
      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textAlign: 'center', marginTop: 'auto', borderTop: '1px solid var(--border)', paddingTop: '1rem' }}>
        v1.0.0 (FastAPI + React)
      </div>
    </div>
  );
};

export default Sidebar;
