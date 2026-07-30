import React from 'react';

const LayerChart = ({ activeSession, currentPrice, config }) => {
  if (!activeSession || !activeSession.first_entry_price) {
    return (
      <div style={{
        height: '280px',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'rgba(0, 0, 0, 0.2)',
        borderRadius: '8px',
        border: '1px dashed var(--border)',
        color: 'var(--text-muted)',
        fontSize: '0.9rem',
        gap: '0.5rem'
      }}>
        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{opacity: 0.5}}>
          <circle cx="12" cy="12" r="10"/>
          <line x1="8" y1="12" x2="16" y2="12"/>
        </svg>
        <span>No Active Session. Start the bot to visualize trading grid.</span>
      </div>
    );
  }

  const { symbol, direction, first_entry_price, layers, risk_level } = activeSession;
  
  // Resolve layering step size from config
  const symConfig = config?.[symbol] || {};
  let stepSize = parseFloat(symConfig.LAYERING_STEP_USD) || 100.0;
  
  // Handle ATR step if configured and active
  if (symConfig.LAYERING_MODE === "ATR" && currentPrice) {
    // Fallback ATR approximation for rendering if we don't have it directly from API
    stepSize = (currentPrice * 0.0015) * (parseFloat(symConfig.LAYERING_STEP_ATR_MULT) || 1.0);
  }
  
  const isBuy = direction === "BUY";
  const numGridLines = Math.max(layers + 2, 6);
  
  // Generate grid prices
  const gridLevels = [];
  for (let k = 0; k < numGridLines; k++) {
    const price = isBuy 
      ? first_entry_price - k * stepSize 
      : first_entry_price + k * stepSize;
    gridLevels.push({
      level: k,
      price: price,
      isActive: k < layers,
      isNextTrigger: k === layers
    });
  }

  // Find min and max prices to scale the SVG
  const prices = gridLevels.map(g => g.price).concat(currentPrice || first_entry_price);
  const maxPrice = Math.max(...prices) + (stepSize * 0.5);
  const minPrice = Math.min(...prices) - (stepSize * 0.5);
  const priceRange = maxPrice - minPrice;

  // SVG dimensions
  const height = 280;
  const width = 450;
  const paddingY = 25;
  const paddingX = 80;

  const getRelativeY = (price) => {
    if (priceRange === 0) return height / 2;
    // High prices at top (lower Y in SVG coordinates)
    const ratio = (price - minPrice) / priceRange;
    return height - paddingY - ratio * (height - 2 * paddingY);
  };

  const color = isBuy ? 'var(--green)' : 'var(--red)';
  const colorGlow = isBuy ? 'var(--green-glow)' : 'var(--red-glow)';

  return (
    <div style={{ position: 'relative' }}>
      <svg width="100%" height={height} className="chart-svg" style={{ background: 'rgba(0, 0, 0, 0.15)', borderRadius: '8px', border: '1px solid var(--border)' }}>
        {/* Gradients */}
        <defs>
          <linearGradient id="glowGrad" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor={color} stopOpacity="0.4" />
            <stop offset="100%" stopColor={color} stopOpacity="0" />
          </linearGradient>
        </defs>

        {/* Vertical Axis (Price Line) */}
        <line x1={paddingX} y1={paddingY} x2={paddingX} y2={height - paddingY} stroke="var(--border)" strokeWidth="2" />

        {/* Grid Levels */}
        {gridLevels.map((lvl) => {
          const y = getRelativeY(lvl.price);
          return (
            <g key={lvl.level}>
              {/* Level label */}
              <text x={15} y={y + 4} className="chart-axis-text" fill={lvl.isActive ? color : 'var(--text-muted)'} fontWeight={lvl.isActive ? '700' : 'normal'}>
                {lvl.level === 0 ? 'Entry' : `Layer ${lvl.level}`}
              </text>

              {/* Price text */}
              <text x={paddingX - 10} y={y + 4} className="chart-axis-text" textAnchor="end">
                {lvl.price.toFixed(2)}
              </text>

              {/* Grid Horizontal Line */}
              <line
                x1={paddingX}
                y1={y}
                x2={width - 20}
                y2={y}
                stroke={lvl.isActive ? color : 'rgba(255, 255, 255, 0.08)'}
                strokeWidth={lvl.isActive ? 2 : 1}
                strokeDasharray={lvl.isActive ? '0' : '4, 4'}
              />

              {/* Active Marker Dot */}
              {lvl.isActive && (
                <circle cx={paddingX} cy={y} r="5" fill={color} filter="drop-shadow(0 0 4px var(--primary-glow))" />
              )}

              {/* Next Trigger Alert Marker */}
              {lvl.isNextTrigger && (
                <g>
                  <circle cx={paddingX} cy={y} r="4" fill="none" stroke={color} strokeWidth="1.5" />
                  <circle cx={paddingX} cy={y} r="8" fill="none" stroke={color} strokeWidth="1" strokeDasharray="2, 2" style={{ transformOrigin: `${paddingX}px ${y}px`, animation: 'pulse-green 2s infinite' }} />
                  <text x={width - 25} y={y - 6} className="chart-axis-text" fill="var(--warning)" textAnchor="end" fontSize="9px">
                    Next Trigger Level
                  </text>
                </g>
              )}
            </g>
          );
        })}

        {/* Live Ticker Current Price Line */}
        {currentPrice && (
          <g>
            <line
              x1={paddingX}
              y1={getRelativeY(currentPrice)}
              x2={width - 20}
              y2={getRelativeY(currentPrice)}
              stroke="var(--secondary)"
              strokeWidth="2"
              strokeDasharray="none"
              filter="drop-shadow(0 0 5px var(--secondary-glow))"
            />
            {/* Pulsing live dot */}
            <circle cx={paddingX} cy={getRelativeY(currentPrice)} r="6" fill="var(--secondary)" />
            <circle cx={paddingX} cy={getRelativeY(currentPrice)} r="12" fill="none" stroke="var(--secondary)" strokeWidth="1" style={{ transformOrigin: `${paddingX}px ${getRelativeY(currentPrice)}px`, animation: 'pulse-green 1.5s infinite' }} />

            {/* Current Price Ticker Badge */}
            <g transform={`translate(${width - 110}, ${getRelativeY(currentPrice) - 12})`}>
              <rect width="90" height="24" rx="4" fill="#0A0B10" stroke="var(--secondary)" strokeWidth="1" />
              <text x="45" y="15" fill="var(--secondary)" fontSize="10px" fontWeight="700" textAnchor="middle">
                LIVE: {currentPrice.toFixed(2)}
              </text>
            </g>
          </g>
        )}
      </svg>
      {/* Absolute overlay elements */}
      <div style={{ position: 'absolute', right: '10px', top: '10px', display: 'flex', flexDirection: 'column', gap: '4px', fontSize: '0.75rem', background: 'rgba(0,0,0,0.6)', padding: '6px 10px', borderRadius: '4px', border: '1px solid var(--border)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: color }}></span>
          <span style={{ color: 'var(--text-white)' }}>{direction} Grid</span>
        </div>
        <div style={{ color: 'var(--text-muted)' }}>Risk: <span style={{ color: risk_level === 'low' ? 'var(--green)' : risk_level === 'moderate' ? 'var(--warning)' : 'var(--red)', fontWeight: 'bold' }}>{risk_level}</span></div>
      </div>
    </div>
  );
};

export default LayerChart;
