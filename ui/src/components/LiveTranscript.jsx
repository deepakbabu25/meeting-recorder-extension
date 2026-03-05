import { useState, useEffect, useRef } from 'react'
import './LiveTranscript.css'

export default function LiveTranscript({ lines, status }) {
    const [open, setOpen] = useState(true)
    const bottomRef = useRef(null)

    // Auto-scroll to bottom when new lines arrive
    useEffect(() => {
        if (open && bottomRef.current) {
            bottomRef.current.scrollIntoView({ behavior: 'smooth' })
        }
    }, [lines, open])

    // Show whenever there are transcript lines (persists after meeting ends)
    if (lines.length === 0 && status !== 'recording') return null

    return (
        <div className={`transcript-panel ${open ? 'expanded' : ''}`}>
            {/* ── Header ── */}
            <button className="transcript-toggle" onClick={() => setOpen(v => !v)}>
                <div className="transcript-toggle-left">
                    <span className={`toggle-icon ${open ? 'rotated' : ''}`}>
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                            <polyline points="6 9 12 15 18 9" />
                        </svg>
                    </span>
                    <div className="transcript-label">
                        <span className="transcript-title">Transcript</span>
                        {status === 'recording' && <span className="transcript-dot" />}
                    </div>
                </div>
                {status === 'recording'
                    ? <span className="badge transcript-badge">● Live</span>
                    : lines.length > 0 && <span className="badge" style={{ color: '#aaaaaa', borderColor: 'rgba(170,170,170,0.3)', background: 'rgba(170,170,170,0.08)' }}>{lines.length} lines</span>
                }
            </button>

            {/* ── Body ── */}
            <div className="transcript-body">
                {lines.length === 0 ? (
                    <p className="transcript-empty">Listening… speak to see the live transcript</p>
                ) : (
                    <div className="transcript-content">
                        {lines.map((line, i) => {
                            // Each line may contain multiple speaker segments separated by \n
                            const segments = line.split('\n').filter(Boolean)
                            return segments.map((seg, j) => {
                                const match = seg.match(/^(Speaker \d+):\s*(.*)$/)
                                const isLatest = i === lines.length - 1 && j === segments.length - 1
                                if (match) {
                                    const spkNum = parseInt(match[1].replace('Speaker ', ''), 10)
                                    return (
                                        <div key={`${i}-${j}`} className={`transcript-line ${isLatest ? 'latest' : ''}`}>
                                            <span className={`speaker-tag spk-${(spkNum - 1) % 5}`}>{match[1]}</span>
                                            <span className="speaker-text">{match[2]}</span>
                                        </div>
                                    )
                                }
                                return (
                                    <div key={`${i}-${j}`} className={`transcript-line ${isLatest ? 'latest' : ''}`}>
                                        <span className="speaker-text">{seg}</span>
                                    </div>
                                )
                            })
                        })}
                        <div ref={bottomRef} />
                    </div>
                )}
            </div>
        </div>
    )
}
