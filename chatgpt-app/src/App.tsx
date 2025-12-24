/**
 * Unredactor Widget - Main Application
 *
 * ChatGPT widget for PDF redaction detection and replacement.
 */

import { useEffect, useRef } from 'react';
import { createRoot } from 'react-dom/client';
import { useToolOutput, useWidgetState, useTheme, useCallTool } from './hooks/useOpenAi';
import type { ToolOutput, WidgetState } from './types/openai.d';

// ============================================================================
// Main App Component
// ============================================================================

function App() {
  const theme = useTheme();
  const output = useToolOutput() as ToolOutput;
  const callTool = useCallTool();
  const [state, setState] = useWidgetState<WidgetState>({
    phase: 'upload',
  });
  const containerRef = useRef<HTMLDivElement>(null);

  // Report height changes to ChatGPT
  useEffect(() => {
    const updateHeight = () => {
      if (containerRef.current) {
        window.openai?.notifyIntrinsicHeight(containerRef.current.scrollHeight);
      }
    };

    updateHeight();

    const observer = new ResizeObserver(updateHeight);
    if (containerRef.current) {
      observer.observe(containerRef.current);
    }

    return () => observer.disconnect();
  }, [output, state]);

  // Update state based on tool output
  useEffect(() => {
    if (output?.file_id) {
      setState((prev) => ({
        ...prev,
        originalFileId: output.file_id,
        pageCount: output.page_count,
      }));
    }

    if (output?.boxes) {
      setState((prev) => ({
        ...prev,
        phase: 'results',
        detectedBoxes: output.boxes,
      }));
    }

    if (output?.processed_file_id) {
      setState((prev) => ({
        ...prev,
        phase: 'compare',
        processedFileId: output.processed_file_id,
      }));
    }
  }, [output, setState]);

  // Handle box size selection
  const handleSelectBoxSize = async (width: number, height: number) => {
    setState((prev) => ({ ...prev, selectedBoxSize: { width, height } }));
  };

  // Handle replacement
  const handleReplace = async (text: string) => {
    if (!state.originalFileId || !state.selectedBoxSize) return;

    try {
      await callTool('replace_redaction_boxes', {
        file_id: state.originalFileId,
        box_width: state.selectedBoxSize.width,
        box_height: state.selectedBoxSize.height,
        replacement_text: text,
      });
    } catch (error) {
      console.error('Failed to replace boxes:', error);
    }
  };

  // Render phases
  if (state.phase === 'upload' || !output) {
    return (
      <div ref={containerRef} className={`widget-container ${theme === 'dark' ? 'dark-mode' : ''}`}>
        <div className="empty-state">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
            <line x1="12" y1="18" x2="12" y2="12" />
            <line x1="9" y1="15" x2="15" y2="15" />
          </svg>
          <p>Upload a PDF to detect redactions</p>
          <button
            className="btn-primary"
            onClick={() => window.openai?.sendFollowUpMessage({ prompt: 'Upload a PDF with redactions' })}
          >
            Get Started
          </button>
        </div>
      </div>
    );
  }

  if (output?.error) {
    return (
      <div ref={containerRef} className={`widget-container ${theme === 'dark' ? 'dark-mode' : ''}`}>
        <div className="error-state">
          <p>{output.error || 'Something went wrong. Please try again.'}</p>
        </div>
      </div>
    );
  }

  if (state.phase === 'results' && output?.boxes) {
    const totalBoxes = output.total_boxes || 0;
    const boxesBySize = new Map<string, { width: number; height: number; count: number }>();

    output.boxes.forEach((box) => {
      const key = `${box.width}x${box.height}`;
      const existing = boxesBySize.get(key);
      if (existing) {
        existing.count++;
      } else {
        boxesBySize.set(key, { width: box.width, height: box.height, count: 1 });
      }
    });

    return (
      <div ref={containerRef} className={`widget-container ${theme === 'dark' ? 'dark-mode' : ''}`}>
        <div className="results-card">
          <h3>Redaction Detection Results</h3>
          <p className="subtitle">Found {totalBoxes} redaction box{totalBoxes !== 1 ? 'es' : ''}</p>

          <div className="box-groups">
            <p className="section-label">Select box size to replace:</p>
            {Array.from(boxesBySize.values()).map((group, index) => (
              <button
                key={index}
                className={`box-group-item ${
                  state.selectedBoxSize?.width === group.width &&
                  state.selectedBoxSize?.height === group.height
                    ? 'selected'
                    : ''
                }`}
                onClick={() => handleSelectBoxSize(group.width, group.height)}
              >
                <div className="box-size">
                  {group.width.toFixed(1)} × {group.height.toFixed(1)} pt
                </div>
                <div className="box-count">{group.count} box{group.count !== 1 ? 'es' : ''}</div>
              </button>
            ))}
          </div>

          {state.selectedBoxSize && (
            <div className="replacement-input">
              <input
                type="text"
                placeholder="Enter replacement text..."
                defaultValue={state.replacementText || '[REDACTED]'}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    handleReplace(e.currentTarget.value);
                  }
                }}
              />
              <button
                className="btn-primary"
                onClick={(e) => {
                  const input = e.currentTarget.previousElementSibling as HTMLInputElement;
                  handleReplace(input.value);
                }}
              >
                Replace
              </button>
            </div>
          )}
        </div>
      </div>
    );
  }

  if (state.phase === 'compare' && output?.processed_file_id) {
    return (
      <div ref={containerRef} className={`widget-container ${theme === 'dark' ? 'dark-mode' : ''}`}>
        <div className="compare-card">
          <h3>Replacement Complete</h3>
          <p className="subtitle">
            Replaced {output.replaced_count || 0} redaction box{(output.replaced_count || 0) !== 1 ? 'es' : ''}
          </p>
          <div className="actions">
            <button
              className="btn-primary"
              onClick={() =>
                window.openai?.sendFollowUpMessage({
                  prompt: `Download the unredacted PDF (file ID: ${output.processed_file_id})`,
                })
              }
            >
              Download Result
            </button>
            <button
              className="btn-secondary"
              onClick={() => setState((prev) => ({ ...prev, phase: 'upload' }))}
            >
              Process Another
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div ref={containerRef} className={`widget-container ${theme === 'dark' ? 'dark-mode' : ''}`}>
      <div className="loading">
        <div className="spinner" />
        <p>Processing...</p>
      </div>
    </div>
  );
}

// ============================================================================
// Styles
// ============================================================================

const styles = `
/* Reset */
*, *::before, *::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

/* CSS Variables */
:root {
  --bg-primary: #ffffff;
  --bg-secondary: #f5f5f5;
  --text-primary: #1a1a1a;
  --text-secondary: #666666;
  --border-color: #e0e0e0;
  --accent-color: #0066cc;
  --accent-hover: #0052a3;
  --success-color: #28a745;
  --error-color: #dc3545;
  --radius-md: 8px;
  --radius-lg: 12px;
}

.dark-mode {
  --bg-primary: #1a1a1a;
  --bg-secondary: #2d2d2d;
  --text-primary: #ffffff;
  --text-secondary: #a0a0a0;
  --border-color: #404040;
  --accent-color: #4da6ff;
  --accent-hover: #80bfff;
}

/* Container */
.widget-container {
  padding: 16px;
  min-height: 100px;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  font-size: 14px;
  line-height: 1.5;
  color: var(--text-primary);
}

/* Cards */
.results-card, .compare-card {
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: 16px;
}

.results-card h3, .compare-card h3 {
  font-size: 1.25rem;
  font-weight: 600;
  margin-bottom: 4px;
}

.subtitle {
  color: var(--text-secondary);
  font-size: 0.875rem;
  margin-bottom: 16px;
}

.section-label {
  font-weight: 500;
  margin-bottom: 8px;
  font-size: 0.875rem;
}

/* Box Groups */
.box-groups {
  margin-bottom: 16px;
}

.box-group-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px;
  margin-bottom: 8px;
  background: var(--bg-secondary);
  border: 2px solid var(--border-color);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all 0.15s ease;
  font-family: inherit;
}

.box-group-item:hover {
  border-color: var(--accent-color);
}

.box-group-item.selected {
  background: var(--accent-color);
  border-color: var(--accent-color);
  color: white;
}

.box-size {
  font-weight: 500;
  font-family: 'Courier New', monospace;
}

.box-count {
  font-size: 0.875rem;
  opacity: 0.8;
}

/* Replacement Input */
.replacement-input {
  display: flex;
  gap: 8px;
}

.replacement-input input {
  flex: 1;
  padding: 10px 12px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  background: var(--bg-primary);
  color: var(--text-primary);
  font-family: inherit;
  font-size: 14px;
}

.replacement-input input:focus {
  outline: none;
  border-color: var(--accent-color);
}

/* Buttons */
button {
  font-family: inherit;
  font-size: 14px;
  font-weight: 500;
  padding: 10px 16px;
  border-radius: var(--radius-md);
  border: none;
  cursor: pointer;
  transition: all 0.15s ease;
}

.btn-primary {
  background: var(--accent-color);
  color: white;
}

.btn-primary:hover {
  background: var(--accent-hover);
}

.btn-secondary {
  background: transparent;
  color: var(--accent-color);
  border: 1px solid var(--accent-color);
}

.btn-secondary:hover {
  background: var(--accent-color);
  color: white;
}

/* Actions */
.actions {
  display: flex;
  gap: 8px;
  margin-top: 16px;
}

/* Loading */
.loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 32px;
  color: var(--text-secondary);
  gap: 12px;
}

.spinner {
  width: 24px;
  height: 24px;
  border: 2px solid var(--border-color);
  border-top-color: var(--accent-color);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Empty State */
.empty-state {
  text-align: center;
  padding: 32px 16px;
  color: var(--text-secondary);
}

.empty-state svg {
  margin-bottom: 16px;
  opacity: 0.5;
}

.empty-state p {
  margin-bottom: 16px;
}

/* Error State */
.error-state {
  text-align: center;
  padding: 24px 16px;
  color: var(--error-color);
  background: #fef2f2;
  border-radius: var(--radius-md);
}

.dark-mode .error-state {
  background: rgba(220, 53, 69, 0.1);
}

/* Responsive */
@media (max-width: 480px) {
  .widget-container {
    padding: 12px;
  }

  .actions {
    flex-direction: column;
  }

  .actions button {
    width: 100%;
  }
}
`;

// ============================================================================
// Mount
// ============================================================================

// Inject styles
const styleEl = document.createElement('style');
styleEl.textContent = styles;
document.head.appendChild(styleEl);

// Mount React app
const root = document.getElementById('root');
if (root) {
  createRoot(root).render(<App />);
}
