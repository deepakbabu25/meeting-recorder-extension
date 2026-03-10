import React, { useState, useEffect } from 'react';
import './HistoryDashboard.css';

const API_BASE = 'https://debroah-prehazard-candance.ngrok-free.dev';

export default function HistoryDashboard({ authToken, onClose }) {
    const [meetings, setMeetings] = useState([]);
    const [selectedMeeting, setSelectedMeeting] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        fetchMeetings();
    }, [authToken]);

    async function fetchMeetings() {
        setLoading(true);
        setError(null);
        try {
            const res = await fetch(`${API_BASE}/api/meetings`, {
                headers: {
                    'Authorization': `Bearer ${authToken}`,
                    'ngrok-skip-browser-warning': 'true'
                }
            });
            if (!res.ok) throw new Error('Failed to fetch meetings');
            const data = await res.json();
            setMeetings(data);
        } catch (err) {
            console.error(err);
            setError('Could not load meeting history.');
        } finally {
            setLoading(false);
        }
    }

    async function fetchMeetingDetails(id) {
        setLoading(true);
        setError(null);
        try {
            const res = await fetch(`${API_BASE}/api/meetings/${id}`, {
                headers: {
                    'Authorization': `Bearer ${authToken}`,
                    'ngrok-skip-browser-warning': 'true'
                }
            });
            if (!res.ok) throw new Error('Failed to fetch meeting details');
            const data = await res.json();
            setSelectedMeeting(data);
        } catch (err) {
            console.error(err);
            setError('Could not load specific meeting.');
        } finally {
            setLoading(false);
        }
    }

    function handleBack() {
        setSelectedMeeting(null);
    }

    async function deleteMeeting(e, id) {
        e.stopPropagation(); // Prevent opening the meeting details
        const confirmDelete = window.confirm("Are you sure you want to delete this meeting?");
        if (!confirmDelete) return;

        try {
            const res = await fetch(`${API_BASE}/api/meetings/${id}`, {
                method: 'DELETE',
                headers: {
                    'Authorization': `Bearer ${authToken}`,
                    'ngrok-skip-browser-warning': 'true'
                }
            });
            if (!res.ok) throw new Error('Failed to delete meeting');

            // Remove the meeting from the UI list
            setMeetings(prev => prev.filter(m => m.id !== id));
            if (selectedMeeting && selectedMeeting.meeting.id === id) {
                setSelectedMeeting(null);
            }
        } catch (err) {
            console.error(err);
            alert("Failed to delete meeting.");
        }
    }

    return (
        <div className="history-dashboard">
            <div className="history-header">
                {selectedMeeting ? (
                    <button className="history-back-btn" onClick={handleBack}>
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <line x1="19" y1="12" x2="5" y2="12"></line>
                            <polyline points="12 19 5 12 12 5"></polyline>
                        </svg>
                        Back
                    </button>
                ) : (
                    <h2 className="history-title">Meeting History</h2>
                )}
                <button className="history-close-btn" onClick={onClose}>
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <line x1="18" y1="6" x2="6" y2="18"></line>
                        <line x1="6" y1="6" x2="18" y2="18"></line>
                    </svg>
                </button>
            </div>

            <div className="history-content">
                {loading && (
                    <div className="history-loading">
                        <div className="spinner"></div>
                        <p>Loading...</p>
                    </div>
                )}

                {error && !loading && (
                    <div className="history-error">{error}</div>
                )}

                {/* LIST VIEW */}
                {!selectedMeeting && !loading && !error && (
                    <div className="history-list-container">
                        {meetings.length === 0 ? (
                            <div className="history-empty">No meetings found. Start recording one!</div>
                        ) : (
                            <table className="history-table">
                                <thead>
                                    <tr>
                                        <th>Meeting ID</th>
                                        <th>Date</th>
                                        <th>Status</th>
                                        <th style={{ width: '60px', textAlign: 'center' }}></th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {meetings.map(m => (
                                        <tr key={m.id} onClick={() => fetchMeetingDetails(m.id)}>
                                            <td className="col-id" title={m.id}>{m.id}</td>
                                            <td className="col-date">{new Date(m.created_at + "Z").toLocaleString()}</td>
                                            <td className="col-status">
                                                <span className={`status-badge ${m.status.toLowerCase()}`}>{m.status}</span>
                                            </td>
                                            <td className="col-actions">
                                                <button className="history-delete-btn" onClick={(e) => deleteMeeting(e, m.id)} title="Delete Meeting">
                                                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                                        <polyline points="3 6 5 6 21 6"></polyline>
                                                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                                                        <line x1="10" y1="11" x2="10" y2="17"></line>
                                                        <line x1="14" y1="11" x2="14" y2="17"></line>
                                                    </svg>
                                                </button>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        )}
                    </div>
                )}

                {/* DETAILS VIEW */}
                {selectedMeeting && !loading && !error && (
                    <div className="history-details">
                        <div className="details-header">
                            <h3>{selectedMeeting.meeting?.title || "Meeting Details"}</h3>
                            <div className="details-meta">{new Date(selectedMeeting.meeting?.created_at + "Z").toLocaleString()}</div>
                        </div>

                        {selectedMeeting.summary && selectedMeeting.summary.summary_text ? (
                            <div className="details-section">
                                <h4>AI Summary</h4>
                                <p>{selectedMeeting.summary.summary_text}</p>

                                {selectedMeeting.summary.key_points?.length > 0 && (
                                    <>
                                        <h5>Key Points</h5>
                                        <ul>{selectedMeeting.summary.key_points.map((p, i) => <li key={i}>{p}</li>)}</ul>
                                    </>
                                )}
                                {selectedMeeting.summary.action_items?.length > 0 && (
                                    <>
                                        <h5>Action Items</h5>
                                        <ul>{selectedMeeting.summary.action_items.map((p, i) => <li key={i}>{p}</li>)}</ul>
                                    </>
                                )}
                            </div>
                        ) : (
                            <div className="details-section"><em>No summary available.</em></div>
                        )}

                        {selectedMeeting.qa_history?.length > 0 && (
                            <div className="details-section">
                                <h4>Chat History</h4>
                                <div className="chat-history-list">
                                    {selectedMeeting.qa_history.map((msg, i) => (
                                        <div key={i} className={`chat-history-msg ${msg.role}`}>
                                            <strong>{msg.role === 'user' ? 'You' : 'WebEnoid'}:</strong> {msg.content}
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        {selectedMeeting.transcripts?.length > 0 && (
                            <div className="details-section transcripts-section">
                                <h4>Full Transcript</h4>
                                <div className="transcript-box">
                                    {selectedMeeting.transcripts.map((t, i) => (
                                        <div key={i} className="transcript-line">
                                            <span className="transcript-speaker">{t.speaker || "Speaker"}:</span> {t.text}
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
}
