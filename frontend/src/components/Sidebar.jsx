import React from 'react';
import { DashboardIcon, BacktestIcon, SettingsIcon, LogsIcon } from './Icons';

const Sidebar = ({ activeTab, setActiveTab }) => {
  const menuItems = [
    { 
      id: 'live', 
      label: 'Live Trading', 
      icon: <DashboardIcon className="menu-icon" />, 
      dotColor: 'var(--warning)',
      glowColor: 'rgba(255, 170, 0, 0.4)'
    },
    { 
      id: 'forward_test', 
      label: 'Simulated Sandbox', 
      icon: <DashboardIcon className="menu-icon" />, 
      dotColor: 'var(--secondary)',
      glowColor: 'rgba(0, 240, 255, 0.4)'
    },
    { id: 'backtest', label: 'Historical Backtest', icon: <BacktestIcon className="menu-icon" /> },
    { 
      id: 'dxy', 
      label: 'Dollar Index (DXY)', 
      icon: <DashboardIcon className="menu-icon" />, 
      dotColor: 'var(--warning)',
      glowColor: 'rgba(255, 170, 0, 0.4)' 
    },
    { 
      id: 'accounts', 
      label: 'Accounts Manager', 
      icon: <SettingsIcon className="menu-icon" />, 
      dotColor: 'var(--green)',
      glowColor: 'rgba(0, 230, 118, 0.4)' 
    },
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
                style={{
                  position: 'relative',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '1rem',
                  paddingRight: '2rem'
                }}
              >
                {item.icon}
                <span>{item.label}</span>
                {item.dotColor && (
                  <span className="menu-item-dot" style={{
                    position: 'absolute',
                    right: '1.25rem',
                    width: '8px',
                    height: '8px',
                    borderRadius: '50%',
                    background: item.dotColor,
                    boxShadow: `0 0 6px ${item.glowColor}`,
                    display: 'inline-block'
                  }}></span>
                )}
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
