import { useState } from 'react'
import './SummaryPanel.css'

const STATUSES = {
    idle: { icon: '◎', text: 'Waiting for meeting to start…' },
    recording: { icon: '●', text: 'Recording meeting…' },
    processing: { icon: '⟳', text: 'Analyzing meeting, please wait…' },
    error: { icon: '✕', text: 'Meeting not found.' },
    ready: null,
}

export default function SummaryPanel({ summary, status }) {
    const [open, setOpen] = useState(false)

    const statusInfo = STATUSES[status]

    return (
        <div className={`summary-panel ${open ? 'expanded' : ''}`}>
            {/* ── Header row (always visible) ── */}
            <button className="summary-toggle" onClick={() => setOpen(v => !v)}>
                <div className="summary-toggle-left">
                    <span className={`toggle-icon ${open ? 'rotated' : ''}`}>
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                            <polyline points="6 9 12 15 18 9" />
                        </svg>
                    </span>
                    <div className="summary-label">
                        <span className="summary-title">Meeting Summary</span>
                        {status === 'processing' && (
                            <span className="processing-dot" />
                        )}
                    </div>
                </div>
                {status === 'ready' && summary && (
                    <span className="badge">Ready</span>
                )}
                {status === 'recording' && (
                    <span className="badge" style={{ color: '#f87171', borderColor: 'rgba(248,113,113,0.3)', background: 'rgba(248,113,113,0.08)' }}>
                        ● Rec
                    </span>
                )}
            </button>

            {/* ── Collapsible body ── */}
            <div className="summary-body">
                {statusInfo ? (
                    <div className="summary-status">
                        <span className={`status-icon ${status}`}>{statusInfo.icon}</span>
                        <span className="status-text">{statusInfo.text}</span>
                    </div>
                ) : summary ? (
                    <div className="summary-content">
                        {/* Overview paragraph */}
                        <section className="summary-section">
                            <h4 className="section-heading">
                                <span className="section-dot blue" />Overview
                            </h4>
                            <p className="section-para">{summary.summary}</p>
                        </section>

                        {/* Key Points */}
                        {summary.key_points?.length > 0 && (
                            <section className="summary-section">
                                <h4 className="section-heading">
                                    <span className="section-dot teal" />Key Points
                                </h4>
                                <ul className="section-list">
                                    {summary.key_points.map((p, i) => (
                                        <li key={i}>{p}</li>
                                    ))}
                                </ul>
                            </section>
                        )}

                        {/* Action Items */}
                        <section className="summary-section">
                            <h4 className="section-heading">
                                <span className="section-dot purple" />Action Items
                            </h4>
                            {summary.action_items?.length > 0 ? (
                                <ul className="section-list action">
                                    {summary.action_items.map((a, i) => (
                                        <li key={i}>
                                            <span className="checkbox">☐</span>{a}
                                        </li>
                                    ))}
                                </ul>
                            ) : (
                                <p className="section-empty">No action items recorded.</p>
                            )}
                        </section>

                        {/* Decisions */}
                        <section className="summary-section">
                            <h4 className="section-heading">
                                <span className="section-dot yellow" />Decisions
                            </h4>
                            {summary.decisions?.length > 0 ? (
                                <ul className="section-list">
                                    {summary.decisions.map((d, i) => (
                                        <li key={i}>{d}</li>
                                    ))}
                                </ul>
                            ) : (
                                <p className="section-empty">No decisions recorded.</p>
                            )}
                        </section>

                        <p className="summary-footer">
                            You can now ask questions about this meeting ↓
                        </p>
                    </div>
                ) : null}
            </div>
        </div>
    )
}
