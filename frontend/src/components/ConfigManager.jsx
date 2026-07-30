import React, { useState, useEffect } from 'react';

const ConfigManager = ({ config, onSaveConfig }) => {
  const [selectedSymbol, setSelectedSymbol] = useState('');
  const [formData, setFormData] = useState(null);
  const [statusMessage, setStatusMessage] = useState({ text: '', type: '' });

  const symbols = config ? Object.keys(config) : [];

  useEffect(() => {
    if (symbols.length > 0 && !selectedSymbol) {
      setSelectedSymbol(symbols[0]);
    }
  }, [symbols, selectedSymbol]);

  useEffect(() => {
    if (selectedSymbol && config?.[selectedSymbol]) {
      setFormData(JSON.parse(JSON.stringify(config[selectedSymbol])));
    }
  }, [selectedSymbol, config]);

  if (!config || !formData) {
    return (
      <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
        Loading strategy configuration settings...
      </div>
    );
  }

  const handleInputChange = (field, value, isNested = null) => {
    setFormData((prev) => {
      const updated = { ...prev };
      if (isNested) {
        updated[isNested] = {
          ...updated[isNested],
          [field]: value
        };
      } else {
        updated[field] = value;
      }
      return updated;
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setStatusMessage({ text: 'Saving configuration...', type: 'info' });
    
    // Clean up numeric inputs
    const cleaned = { ...formData };
    cleaned.LOT_SIZE = parseFloat(cleaned.LOT_SIZE);
    cleaned.MAX_SPREAD_USD = parseFloat(cleaned.MAX_SPREAD_USD);
    cleaned.LAYERING_STEP_USD = parseFloat(cleaned.LAYERING_STEP_USD);
    cleaned.LAYERING_STEP_ATR_MULT = parseFloat(cleaned.LAYERING_STEP_ATR_MULT);
    cleaned.TAKE_PROFIT_PER_LAYER_USD = parseFloat(cleaned.TAKE_PROFIT_PER_LAYER_USD);
    cleaned.MAX_LAYERS = cleaned.MAX_LAYERS === '' || cleaned.MAX_LAYERS === null ? null : parseInt(cleaned.MAX_LAYERS);
    
    if (cleaned.LOW_RISK_OVERRIDES) {
      if (cleaned.LOW_RISK_OVERRIDES.LOT_SIZE !== undefined) cleaned.LOW_RISK_OVERRIDES.LOT_SIZE = parseFloat(cleaned.LOW_RISK_OVERRIDES.LOT_SIZE);
      if (cleaned.LOW_RISK_OVERRIDES.LAYERING_STEP_ATR_MULT !== undefined) cleaned.LOW_RISK_OVERRIDES.LAYERING_STEP_ATR_MULT = parseFloat(cleaned.LOW_RISK_OVERRIDES.LAYERING_STEP_ATR_MULT);
      if (cleaned.LOW_RISK_OVERRIDES.TAKE_PROFIT_PER_LAYER_USD !== undefined) cleaned.LOW_RISK_OVERRIDES.TAKE_PROFIT_PER_LAYER_USD = parseFloat(cleaned.LOW_RISK_OVERRIDES.TAKE_PROFIT_PER_LAYER_USD);
    }
    
    if (cleaned.MODERATE_RISK_OVERRIDES) {
      if (cleaned.MODERATE_RISK_OVERRIDES.LOT_SIZE !== undefined) cleaned.MODERATE_RISK_OVERRIDES.LOT_SIZE = parseFloat(cleaned.MODERATE_RISK_OVERRIDES.LOT_SIZE);
      if (cleaned.MODERATE_RISK_OVERRIDES.LAYERING_STEP_ATR_MULT !== undefined) cleaned.MODERATE_RISK_OVERRIDES.LAYERING_STEP_ATR_MULT = parseFloat(cleaned.MODERATE_RISK_OVERRIDES.LAYERING_STEP_ATR_MULT);
      if (cleaned.MODERATE_RISK_OVERRIDES.TAKE_PROFIT_PER_LAYER_USD !== undefined) cleaned.MODERATE_RISK_OVERRIDES.TAKE_PROFIT_PER_LAYER_USD = parseFloat(cleaned.MODERATE_RISK_OVERRIDES.TAKE_PROFIT_PER_LAYER_USD);
    }

    const success = await onSaveConfig(selectedSymbol, cleaned);
    if (success) {
      setStatusMessage({ text: `Configuration for ${selectedSymbol} updated successfully!`, type: 'success' });
      setTimeout(() => setStatusMessage({ text: '', type: '' }), 4000);
    } else {
      setStatusMessage({ text: 'Failed to update configuration.', type: 'error' });
    }
  };

  return (
    <div className="config-layout">
      {/* Symbols Tabs */}
      <div className="config-nav">
        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 'bold', textTransform: 'uppercase', letterSpacing: '0.5px', padding: '0.5rem 1rem' }}>
          Trading Symbols
        </div>
        {symbols.map((sym) => (
          <button
            key={sym}
            className={`config-nav-btn ${selectedSymbol === sym ? 'active' : ''}`}
            onClick={() => setSelectedSymbol(sym)}
          >
            {sym}
          </button>
        ))}
      </div>

      {/* Configuration Form */}
      <form className="config-form" onSubmit={handleSubmit}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h2 style={{ fontSize: '1.25rem', fontWeight: '800', color: 'var(--text-white)' }}>
            Grid Strategy Parameters: <span style={{ color: 'var(--secondary)' }}>{selectedSymbol}</span>
          </h2>
          {statusMessage.text && (
            <div style={{
              fontSize: '0.85rem',
              fontWeight: '600',
              padding: '0.5rem 1rem',
              borderRadius: '6px',
              background: statusMessage.type === 'success' ? 'rgba(0, 230, 118, 0.15)' : statusMessage.type === 'error' ? 'rgba(255, 51, 102, 0.15)' : 'rgba(0, 240, 255, 0.15)',
              color: statusMessage.type === 'success' ? 'var(--green)' : statusMessage.type === 'error' ? 'var(--red)' : 'var(--secondary)',
              border: `1px solid ${statusMessage.type === 'success' ? 'rgba(0, 230, 118, 0.25)' : statusMessage.type === 'error' ? 'rgba(255, 51, 102, 0.25)' : 'rgba(0, 240, 255, 0.25)'}`
            }}>
              {statusMessage.text}
            </div>
          )}
        </div>

        {/* Section 1: Core Parameters */}
        <div className="config-form-section">
          <h3 className="config-section-title">Execution Parameters</h3>
          <div className="form-row-grid">
            <div className="form-group">
              <label className="form-label">Base Lot Size</label>
              <input
                type="number"
                step="0.01"
                className="form-input"
                value={formData.LOT_SIZE}
                onChange={(e) => handleInputChange('LOT_SIZE', e.target.value)}
                required
              />
            </div>
            <div className="form-group">
              <label className="form-label">Max Spread (USD)</label>
              <input
                type="number"
                step="0.1"
                className="form-input"
                value={formData.MAX_SPREAD_USD}
                onChange={(e) => handleInputChange('MAX_SPREAD_USD', e.target.value)}
                required
              />
            </div>
            <div className="form-group">
              <label className="form-label">Take Profit Per Layer (USD)</label>
              <input
                type="number"
                step="0.01"
                className="form-input"
                value={formData.TAKE_PROFIT_PER_LAYER_USD}
                onChange={(e) => handleInputChange('TAKE_PROFIT_PER_LAYER_USD', e.target.value)}
                required
              />
            </div>
            <div className="form-group">
              <label className="form-label">Max Grid Layers (None for Unlimited)</label>
              <input
                type="number"
                className="form-input"
                value={formData.MAX_LAYERS !== null ? formData.MAX_LAYERS : ''}
                placeholder="Unlimited"
                onChange={(e) => handleInputChange('MAX_LAYERS', e.target.value)}
              />
            </div>
          </div>
        </div>

        {/* Section 2: Spacing Strategy */}
        <div className="config-form-section">
          <h3 className="config-section-title">Grid Layering Spacing</h3>
          <div className="form-row-grid">
            <div className="form-group">
              <label className="form-label">Layer Spacing Mode</label>
              <select
                className="form-input form-select"
                value={formData.LAYERING_MODE}
                onChange={(e) => handleInputChange('LAYERING_MODE', e.target.value)}
              >
                <option value="USD">Fixed USD Spacing</option>
                <option value="ATR">Volatility (ATR) Spacing</option>
              </select>
            </div>
            {formData.LAYERING_MODE === 'USD' ? (
              <div className="form-group">
                <label className="form-label">Fixed Grid Step (USD)</label>
                <input
                  type="number"
                  step="1"
                  className="form-input"
                  value={formData.LAYERING_STEP_USD}
                  onChange={(e) => handleInputChange('LAYERING_STEP_USD', e.target.value)}
                  required
                />
              </div>
            ) : (
              <div className="form-group">
                <label className="form-label">ATR Step Multiplier</label>
                <input
                  type="number"
                  step="0.1"
                  className="form-input"
                  value={formData.LAYERING_STEP_ATR_MULT}
                  onChange={(e) => handleInputChange('LAYERING_STEP_ATR_MULT', e.target.value)}
                  required
                />
              </div>
            )}
          </div>
        </div>

        {/* Section 3: Timing Risk Overrides */}
        <div className="config-form-section">
          <h3 className="config-section-title">Low Risk Session Overrides</h3>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '-0.5rem', marginBottom: '0.5rem' }}>
            Applied automatically during low-risk WIB timezone windows (e.g. night / weekend gaps).
          </div>
          <div className="form-row-grid">
            <div className="form-group">
              <label className="form-label">Override Lot Size</label>
              <input
                type="number"
                step="0.01"
                className="form-input"
                value={formData.LOW_RISK_OVERRIDES?.LOT_SIZE || ''}
                onChange={(e) => handleInputChange('LOT_SIZE', e.target.value, 'LOW_RISK_OVERRIDES')}
              />
            </div>
            <div className="form-group">
              <label className="form-label">Override ATR Spacing Mult</label>
              <input
                type="number"
                step="0.1"
                className="form-input"
                value={formData.LOW_RISK_OVERRIDES?.LAYERING_STEP_ATR_MULT || ''}
                onChange={(e) => handleInputChange('LAYERING_STEP_ATR_MULT', e.target.value, 'LOW_RISK_OVERRIDES')}
              />
            </div>
            <div className="form-group">
              <label className="form-label">Override Take Profit (USD)</label>
              <input
                type="number"
                step="0.01"
                className="form-input"
                value={formData.LOW_RISK_OVERRIDES?.TAKE_PROFIT_PER_LAYER_USD || ''}
                onChange={(e) => handleInputChange('TAKE_PROFIT_PER_LAYER_USD', e.target.value, 'LOW_RISK_OVERRIDES')}
              />
            </div>
          </div>
        </div>

        <div className="config-form-section">
          <h3 className="config-section-title">Moderate Risk Session Overrides</h3>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '-0.5rem', marginBottom: '0.5rem' }}>
            Applied automatically during daytime trading sessions.
          </div>
          <div className="form-row-grid">
            <div className="form-group">
              <label className="form-label">Override Lot Size</label>
              <input
                type="number"
                step="0.01"
                className="form-input"
                value={formData.MODERATE_RISK_OVERRIDES?.LOT_SIZE || ''}
                onChange={(e) => handleInputChange('LOT_SIZE', e.target.value, 'MODERATE_RISK_OVERRIDES')}
              />
            </div>
            <div className="form-group">
              <label className="form-label">Override ATR Spacing Mult</label>
              <input
                type="number"
                step="0.1"
                className="form-input"
                value={formData.MODERATE_RISK_OVERRIDES?.LAYERING_STEP_ATR_MULT || ''}
                onChange={(e) => handleInputChange('LAYERING_STEP_ATR_MULT', e.target.value, 'MODERATE_RISK_OVERRIDES')}
              />
            </div>
            <div className="form-group">
              <label className="form-label">Override Take Profit (USD)</label>
              <input
                type="number"
                step="0.01"
                className="form-input"
                value={formData.MODERATE_RISK_OVERRIDES?.TAKE_PROFIT_PER_LAYER_USD || ''}
                onChange={(e) => handleInputChange('TAKE_PROFIT_PER_LAYER_USD', e.target.value, 'MODERATE_RISK_OVERRIDES')}
              />
            </div>
          </div>
        </div>

        {/* Submit Actions */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '1rem', marginTop: '1rem' }}>
          <button type="submit" className="btn btn-primary" style={{ padding: '0.85rem 2rem' }}>
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/>
              <polyline points="17 21 17 13 7 13 7 21"/>
              <polyline points="7 3 7 8 15 8"/>
            </svg>
            <span>Save Configuration Settings</span>
          </button>
        </div>
      </form>
    </div>
  );
};

export default ConfigManager;
