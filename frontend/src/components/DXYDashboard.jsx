import React, { useState, useEffect } from 'react';
import DXYChart from './DXYChart';
import { API_BASE } from '../config';

const DXYDashboard = ({ dxyData }) => {
  const [dxyHistory, setDxyHistory] = useState([]);
  const [dxyRange, setDxyRange] = useState('7d');
  const [loading, setLoading] = useState(false);
  const [harvesting, setHarvesting] = useState(false);

  // EMA calculation utility
  const calculateEMA = (data, period) => {
    if (data.length < period) return new Array(data.length).fill(null);
    
    const k = 2 / (period + 1);
    const ema = [];
    
    // Calculate simple moving average of first 'period' elements for initial EMA seed
    let sum = 0;
    for (let i = 0; i < period; i++) {
      sum += data[i].value;
    }
    let currentEma = sum / period;
    
    for (let i = 0; i < data.length; i++) {
      if (i < period - 1) {
        ema.push(null);
      } else if (i === period - 1) {
        ema.push(currentEma);
      } else {
        currentEma = data[i].value * k + currentEma * (1 - k);
        ema.push(currentEma);
      }
    }
    return ema;
  };

  const fetchDxyHistory = async (rangeVal) => {
    try {
      setLoading(true);
      
      // Determine display size
      let displayLength = 168; // default to 7d (7 * 24 hours)
      if (rangeVal === '1d') displayLength = 24;
      else if (rangeVal === '30d') displayLength = 720;
      else if (rangeVal === '3y') displayLength = 30000;

      // Request display length + 200 extra points to calculate EMA 200 accurately
      const limit = displayLength + 200;

      const res = await fetch(`${API_BASE}/api/dxy/historical?limit=${limit}`);
      if (res.ok) {
        const rawData = await res.json();
        
        // Format to DXYChart format: { time, value }
        const formatted = rawData.map((d) => ({
          time: d.time,
          value: d.close
        }));

        // Calculate EMA 200 over the entire fetched set
        const emaValues = calculateEMA(formatted, 200);

        // Combine
        const combined = formatted.map((pt, idx) => ({
          ...pt,
          ema: emaValues[idx]
        }));

        // Slice to only show the requested display range to the user
        const finalData = combined.slice(-displayLength);
        setDxyHistory(finalData);
      }
    } catch (err) {
      console.error("Error fetching DXY history:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDxyHistory(dxyRange);
  }, [dxyRange]);

  const handleHarvest = async () => {
    try {
      setHarvesting(true);
      const res = await fetch(`${API_BASE}/api/dxy/harvest`, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        alert(`Harvest complete! Inserted ${data.inserted || 0} new historical records.`);
        fetchDxyHistory(dxyRange);
      } else {
        alert("Harvest request failed.");
      }
    } catch (err) {
      alert("Error contacting DXY harvester service.");
    } finally {
      setHarvesting(false);
    }
  };

  const price = dxyData?.close ?? 100.0;
  const open = dxyData?.open ?? 100.0;
  const change = dxyData ? (price - open) : 0.0;
  const changePct = dxyData ? (change / open) * 100 : 0.0;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      
      {/* Real-time DXY Stats Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1.5rem' }}>
        
        {/* Card 1: DXY Quote */}
        <div className="kpi-card kpi-primary">
          <div className="kpi-label">US Dollar Index (DXY)</div>
          <div className="kpi-value font-mono">
            {price.toFixed(3)}
          </div>
          <div className="kpi-subtext">
            Source: <span style={{ color: 'var(--text-white)' }}>Rust dxy_service</span>
          </div>
        </div>

        {/* Card 2: Daily Change Value */}
        <div className="kpi-card kpi-secondary">
          <div className="kpi-label">Net Daily Change</div>
          <div className="kpi-value font-mono" style={{ color: change >= 0 ? 'var(--green)' : 'var(--red)' }}>
            {change >= 0 ? '+' : ''}{change.toFixed(3)}
          </div>
          <div className="kpi-subtext">
            Abs Value fluctuation (H1 Open vs Close)
          </div>
        </div>

        {/* Card 3: Daily Change Percent */}
        <div className="kpi-card kpi-secondary" style={{
          borderColor: change >= 0 ? 'rgba(0,230,118,0.1)' : 'rgba(255,51,102,0.1)',
          background: change >= 0 ? 'rgba(0,230,118,0.01)' : 'rgba(255,51,102,0.01)'
        }}>
          <div className="kpi-label">Daily Performance</div>
          <div className="kpi-value font-mono" style={{ color: change >= 0 ? 'var(--green)' : 'var(--red)', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span>{change >= 0 ? '▲' : '▼'}</span>
            <span>{Math.abs(changePct).toFixed(2)}%</span>
          </div>
          <div className="kpi-subtext">
            Relative percent shift
          </div>
        </div>

      </div>

      {/* Standalone DXY Line Chart Workspace */}
      <div className="chart-card">
        <div className="chart-header" style={{ flexWrap: 'wrap', gap: '12px' }}>
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <h3 className="chart-title">
              <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ color: 'var(--warning)' }}>
                <line x1="18" y1="20" x2="18" y2="10"></line>
                <line x1="12" y1="20" x2="12" y2="4"></line>
                <line x1="6" y1="20" x2="6" y2="14"></line>
              </svg>
              <span>US Dollar Index (DXY) Value Chart</span>
            </h3>
            
            {/* Legend badges row */}
            <div style={{ display: 'flex', gap: '12px', alignItems: 'center', marginTop: '6px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '5px', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: 'var(--warning)' }}></span>
                <span>DXY Price</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '5px', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: 'var(--secondary)' }}></span>
                <span>EMA 200 (Hours)</span>
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', gap: '8px', marginLeft: 'auto', flexWrap: 'wrap', alignItems: 'center' }}>
            {/* Range Selectors */}
            <div style={{ display: 'flex', gap: '4px' }}>
              {['1d', '7d', '30d', '3y'].map((range) => (
                <button
                  key={range}
                  className="btn"
                  style={{
                    padding: '0.3rem 0.8rem',
                    fontSize: '0.75rem',
                    background: dxyRange === range ? 'var(--warning)' : 'rgba(255,255,255,0.03)',
                    color: dxyRange === range ? '#000' : 'var(--text-muted)',
                    border: `1px solid ${dxyRange === range ? 'var(--warning)' : 'var(--border)'}`,
                    borderRadius: '4px',
                    fontWeight: 'bold',
                    cursor: 'pointer',
                    minHeight: '28px',
                    boxShadow: dxyRange === range ? '0 2px 8px rgba(255, 170, 0, 0.2)' : 'none',
                    transition: 'var(--transition)'
                  }}
                  onClick={() => setDxyRange(range)}
                >
                  {range.toUpperCase()}
                </button>
              ))}
            </div>

            {/* Manual harvest button */}
            <button
              className="btn btn-secondary"
              style={{
                padding: '0.3rem 0.8rem',
                fontSize: '0.75rem',
                minHeight: '28px',
                borderColor: 'var(--warning)',
                color: 'var(--warning)',
                fontWeight: 'bold'
              }}
              onClick={handleHarvest}
              disabled={harvesting}
            >
              {harvesting ? 'Harvesting...' : 'Harvest Now'}
            </button>
          </div>
        </div>

        <div className="chart-wrapper">
          {loading ? (
            <div style={{
              height: '250px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--text-muted)',
              fontSize: '0.9rem'
            }}>
              Loading Dollar Index chart data...
            </div>
          ) : (
            <DXYChart data={dxyHistory} />
          )}
        </div>
      </div>

    </div>
  );
};

export default DXYDashboard;
