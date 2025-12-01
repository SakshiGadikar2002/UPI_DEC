import React from 'react';
import './ResultsDisplay.css';

function ResultsDisplay({ results, onDownload }) {
  if (!results) return null;

  return (
    <div className="results-container">
      <h2>Processing Results</h2>

      <div className="results-summary">
        <div className="summary-card success">
          <h3>✓ Success</h3>
          <p>Pipeline completed successfully</p>
        </div>

        <div className="summary-card">
          <h3>Rows Processed</h3>
          <p className="big-number">{results.rows_processed}</p>
        </div>

        <div className="summary-card">
          <h3>Output File</h3>
          <p>{results.output_file}</p>
        </div>
      </div>

      {results.results && results.results.steps && (
        <div className="pipeline-steps">
          <h3>Pipeline Steps</h3>
          <div className="steps-list">
            {Object.entries(results.results.steps).map(([step, data]) => (
              <div key={step} className="step-item">
                <div className="step-header">
                  <span className="step-name">{step.replace('_', ' ').toUpperCase()}</span>
                  <span className={`step-status ${data.status}`}>
                    {data.status === 'success' ? '✓' : data.status === 'failed' ? '✗' : '○'}
                  </span>
                </div>
                {data.data_size && (
                  <p className="step-details">Size: {data.data_size}</p>
                )}
                {data.transformer && (
                  <p className="step-details">Transformer: {data.transformer}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {results.preview && results.preview.length > 0 && (
        <div className="results-preview">
          <h3>Output Preview (First 10 rows)</h3>
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  {results.columns.map((col) => (
                    <th key={col}>{col}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {results.preview.map((row, idx) => (
                  <tr key={idx}>
                    {results.columns.map((col) => (
                      <td key={col}>{row[col]?.toString() || ''}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <button className="download-btn" onClick={onDownload}>
        Download Processed File
      </button>
    </div>
  );
}

export default ResultsDisplay;

