import React, { useState } from 'react';

const DXYChart = ({ data }) => {
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
        No Dollar Index history available yet.
      </div>
    );
  }

  // Dimensions
  const svgWidth = 600;
  const svgHeight = 250;
  const paddingLeft = 60;
  const paddingRight = 20;
  const paddingTop = 20;
  const paddingBottom = 35; // slightly more padding for dates

  const chartWidth = svgWidth - paddingLeft - paddingRight;
  const chartHeight = svgHeight - paddingTop - paddingBottom;

  // Find min and max considering both DXY prices and calculated EMA 200 points
  const values = data.map((d) => d.value);
  const emaValues = data.filter((d) => d.ema !== null && d.ema !== undefined).map((d) => d.ema);
  const allPoints = [...values, ...emaValues];

  let maxVal = Math.max(...allPoints);
  let minVal = Math.min(...allPoints);
  
  // Pad the range slightly
  const range = maxVal - minVal;
  const padding = range === 0 ? 0.5 : range * 0.1;
  maxVal += padding;
  minVal -= padding;
  const adjustedRange = maxVal - minVal;

  const getX = (index) => {
    return paddingLeft + (index / (data.length - 1)) * chartWidth;
  };

  const getY = (val) => {
    if (adjustedRange === 0) return paddingTop + chartHeight / 2;
    const ratio = (val - minVal) / adjustedRange;
    return svgHeight - paddingBottom - ratio * chartHeight;
  };

  // Build DXY path coordinates
  const points = data.map((d, idx) => ({
    x: getX(idx),
    y: getY(d.value),
    data: d
  }));

  const linePath = points.map((p, idx) => `${idx === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ');
  const areaPath = `${linePath} L ${points[points.length - 1].x} ${svgHeight - paddingBottom} L ${points[0].x} ${svgHeight - paddingBottom} Z`;

  // Build EMA 200 path coordinates (filtering out null initial values)
  const emaPoints = data
    .map((d, idx) => ({
      x: getX(idx),
      y: d.ema !== null && d.ema !== undefined ? getY(d.ema) : null
    }))
    .filter((p) => p.y !== null);

  const emaLinePath = emaPoints.map((p, idx) => `${idx === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ');

  // Draw grid lines
  const gridLines = [];
  const numGridLines = 4;
  for (let i = 0; i <= numGridLines; i++) {
    const val = minVal + (i / numGridLines) * adjustedRange;
    gridLines.push({
      value: val,
      y: getY(val)
    });
  }

  // Handle SVG hovering
  const handleMouseMove = (e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * svgWidth;
    
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
      const d = new Date(isoStr.replace(' ', 'T'));
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
          <linearGradient id="dxyGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--warning)" stopOpacity="0.2" />
            <stop offset="100%" stopColor="var(--warning)" stopOpacity="0" />
          </linearGradient>
          <filter id="dxyGlow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
          </filter>
          <filter id="emaGlow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="1.5" result="blur" />
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
              className="chart-axis-text font-mono"
            >
              {line.value.toFixed(3)}
            </text>
          </g>
        ))}

        {/* Gradient Area Fill */}
        <path d={areaPath} fill="url(#dxyGradient)" />

        {/* DXY Curve Line */}
        <path d={linePath} className="chart-line" style={{ stroke: 'var(--warning)', strokeWidth: 2, fill: 'none' }} filter="url(#dxyGlow)" />

        {/* EMA 200 Line Overlay */}
        {emaLinePath && (
          <path 
            d={emaLinePath} 
            style={{ stroke: 'var(--secondary)', strokeWidth: 1.5, fill: 'none' }} 
            filter="url(#emaGlow)" 
          />
        )}

        {/* Hover elements */}
        {hoverIndex !== null && (
          <g className="chart-tooltip">
            <line
              x1={hoverPos.x}
              y1={paddingTop}
              x2={hoverPos.x}
              y2={svgHeight - paddingBottom}
              stroke="rgba(255, 170, 0, 0.4)"
              strokeWidth="1.5"
              strokeDasharray="4, 4"
            />
            <circle cx={hoverPos.x} cy={hoverPos.y} r="8" fill="none" stroke="var(--warning)" strokeWidth="1.5" />
            <circle cx={hoverPos.x} cy={hoverPos.y} r="4" fill="var(--text-white)" />
            {data[hoverIndex].ema !== null && data[hoverIndex].ema !== undefined && (
              <circle 
                cx={hoverPos.x} 
                cy={getY(data[hoverIndex].ema)} 
                r="4" 
                fill="var(--secondary)" 
              />
            )}
          </g>
        )}
      </svg>

      {/* Floating Tooltip Box */}
      {hoverIndex !== null && (
        <div style={{
          position: 'absolute',
          left: `${(hoverPos.x / svgWidth) * 100}%`,
          top: `${(hoverPos.y / svgHeight) * 100 - 95}%`,
          transform: 'translateX(-50%)',
          background: 'rgba(7, 8, 14, 0.95)',
          border: '1px solid var(--warning)',
          borderRadius: '6px',
          padding: '8px 12px',
          fontSize: '0.8rem',
          boxShadow: '0 4px 15px rgba(0,0,0,0.5), 0 0 10px rgba(255, 170, 0, 0.1)',
          pointerEvents: 'none',
          zIndex: 5,
          minWidth: '150px'
        }}>
          <div style={{ color: 'var(--text-muted)', marginBottom: '4px', fontSize: '0.7rem' }}>
            {formatDate(data[hoverIndex].time)}
          </div>
          <div style={{ fontWeight: 'bold', color: 'var(--text-white)' }}>
            DXY Close: {data[hoverIndex].value.toFixed(3)}
          </div>
          {data[hoverIndex].ema !== null && data[hoverIndex].ema !== undefined && (
            <div style={{ color: 'var(--secondary)', marginTop: '2px', fontWeight: '700' }}>
              EMA 200: {data[hoverIndex].ema.toFixed(3)}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default DXYChart;
