import React, { useState } from 'react';

const EquityChart = ({ data }) => {
  const [hoverIndex, setHoverIndex] = useState(null);
  const [hoverPos, setHoverPos] = useState({ x: 0, y: 0 });

  if (!data || data.length < 2) {
    return (
      <div style={{
        height: '250px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'rgba(0, 0, 0, 0.2)',
        borderRadius: '8px',
        border: '1px dashed var(--border)',
        color: 'var(--text-muted)',
        fontSize: '0.9rem'
      }}>
        No equity history available yet.
      </div>
    );
  }

  // Dimensions
  const svgWidth = 600;
  const svgHeight = 250;
  const paddingLeft = 50;
  const paddingRight = 20;
  const paddingTop = 20;
  const paddingBottom = 30;

  const chartWidth = svgWidth - paddingLeft - paddingRight;
  const chartHeight = svgHeight - paddingTop - paddingBottom;

  // Find min and max
  const balances = data.map((d) => d.balance);
  let maxBal = Math.max(...balances);
  let minBal = Math.min(...balances);
  
  // Pad the range slightly so the curve doesn't clip
  const range = maxBal - minBal;
  const padding = range === 0 ? 100 : range * 0.1;
  maxBal += padding;
  minBal -= padding;
  const adjustedRange = maxBal - minBal;

  const getX = (index) => {
    return paddingLeft + (index / (data.length - 1)) * chartWidth;
  };

  const getY = (balance) => {
    if (adjustedRange === 0) return paddingTop + chartHeight / 2;
    const ratio = (balance - minBal) / adjustedRange;
    return svgHeight - paddingBottom - ratio * chartHeight;
  };

  // Build the path coordinates
  const points = data.map((d, idx) => ({
    x: getX(idx),
    y: getY(d.balance),
    data: d
  }));

  const linePath = points.map((p, idx) => `${idx === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ');
  const areaPath = `${linePath} L ${points[points.length - 1].x} ${svgHeight - paddingBottom} L ${points[0].x} ${svgHeight - paddingBottom} Z`;

  // Draw grid lines
  const gridLines = [];
  const numGridLines = 4;
  for (let i = 0; i <= numGridLines; i++) {
    const val = minBal + (i / numGridLines) * adjustedRange;
    gridLines.push({
      value: val,
      y: getY(val)
    });
  }

  // Handle SVG hovering
  const handleMouseMove = (e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * svgWidth;
    
    // Find closest point by X coordinate
    let closestIdx = 0;
    let minDiff = Infinity;
    points.forEach((p, idx) => {
      const diff = Math.abs(p.x - x);
      if (diff < minDiff) {
        minDiff = diff;
        closestIdx = idx;
      }
    });

    setHoverIndex(closestIdx);
    setHoverPos({
      x: points[closestIdx].x,
      y: points[closestIdx].y
    });
  };

  const handleMouseLeave = () => {
    setHoverIndex(null);
  };

  const formatDate = (isoStr) => {
    if (!isoStr) return '';
    try {
      const d = new Date(isoStr);
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) + ' ' + d.toLocaleDateString([], { month: 'short', day: 'numeric' });
    } catch {
      return isoStr;
    }
  };

  return (
    <div style={{ position: 'relative' }}>
      <svg
        viewBox={`0 0 ${svgWidth} ${svgHeight}`}
        width="100%"
        height="100%"
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
        style={{ overflow: 'visible', pointerEvents: 'auto' }}
      >
        <defs>
          {/* Equity Gradient Area Fill */}
          <linearGradient id="equityGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--secondary)" stopOpacity="0.25" />
            <stop offset="100%" stopColor="var(--secondary)" stopOpacity="0" />
          </linearGradient>
          {/* Neon Glow Drop Shadow */}
          <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
          </filter>
        </defs>

        {/* Grid lines and horizontal labels */}
        {gridLines.map((line, idx) => (
          <g key={idx}>
            <line
              x1={paddingLeft}
              y1={line.y}
              x2={svgWidth - paddingRight}
              y2={line.y}
              className="chart-grid-line"
            />
            <text
              x={paddingLeft - 8}
              y={line.y + 4}
              textAnchor="end"
              className="chart-axis-text"
            >
              ${line.value.toFixed(0)}
            </text>
          </g>
        ))}

        {/* Gradient Area Fill */}
        <path d={areaPath} fill="url(#equityGradient)" />

        {/* Equity Curve Line */}
        <path d={linePath} className="chart-line-equity" filter="url(#glow)" />

        {/* Hover elements (Vertical Line + Point highlight) */}
        {hoverIndex !== null && (
          <g className="chart-tooltip">
            {/* Vertical dashed line */}
            <line
              x1={hoverPos.x}
              y1={paddingTop}
              x2={hoverPos.x}
              y2={svgHeight - paddingBottom}
              stroke="rgba(0, 240, 255, 0.4)"
              strokeWidth="1.5"
              strokeDasharray="4, 4"
            />
            {/* Point glow ring */}
            <circle cx={hoverPos.x} cy={hoverPos.y} r="8" fill="none" stroke="var(--secondary)" strokeWidth="1.5" />
            {/* Active Point dot */}
            <circle cx={hoverPos.x} cy={hoverPos.y} r="4" fill="var(--text-white)" />
          </g>
        )}
      </svg>

      {/* Floating Tooltip Box */}
      {hoverIndex !== null && (
        <div style={{
          position: 'absolute',
          left: `${(hoverPos.x / svgWidth) * 100}%`,
          top: `${(hoverPos.y / svgHeight) * 100 - 90}%`,
          transform: 'translateX(-50%)',
          background: 'rgba(7, 8, 14, 0.95)',
          border: '1px solid var(--secondary)',
          borderRadius: '6px',
          padding: '8px 12px',
          fontSize: '0.8rem',
          boxShadow: '0 4px 15px rgba(0,0,0,0.5), 0 0 10px rgba(0, 240, 255, 0.1)',
          pointerEvents: 'none',
          zIndex: 5,
          minWidth: '140px'
        }}>
          <div style={{ color: 'var(--text-muted)', marginBottom: '4px', fontSize: '0.7rem' }}>
            {formatDate(data[hoverIndex].time)}
          </div>
          <div style={{ fontWeight: 'bold', color: 'var(--text-white)' }}>
            Equity: ${data[hoverIndex].balance.toFixed(2)}
          </div>
          {data[hoverIndex].profit !== 0 && (
            <div style={{ color: data[hoverIndex].profit > 0 ? 'var(--green)' : 'var(--red)', marginTop: '2px', fontWeight: '500' }}>
              PnL: {data[hoverIndex].profit > 0 ? '+' : ''}${data[hoverIndex].profit.toFixed(2)}
              {data[hoverIndex].symbol && ` (${data[hoverIndex].symbol})`}
            </div>
          )}
          {data[hoverIndex].reason && (
            <div style={{ color: 'var(--warning)', fontSize: '0.7rem', marginTop: '2px' }}>
              {data[hoverIndex].reason}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default EquityChart;
