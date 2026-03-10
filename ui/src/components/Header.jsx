import { useState, useRef, useEffect } from 'react'
import './Header.css'

export default function Header({ meetingId, onOpenHistory }) {
    const [menuOpen, setMenuOpen] = useState(false)
    const menuRef = useRef(null)

    // Close menu on outside click
    useEffect(() => {
        function handler(e) {
            if (menuRef.current && !menuRef.current.contains(e.target)) {
                setMenuOpen(false)
            }
        }
        document.addEventListener('mousedown', handler)
        return () => document.removeEventListener('mousedown', handler)
    }, [])

    function handleHistory() {
        setMenuOpen(false)
        if (onOpenHistory) onOpenHistory()
    }

    return (
        <header className="header">
            <div className="header-left">
                <div className="header-logo">
                    <img src="./logo.png" alt="Webenoid" className="logo-img" />
                    <div className="header-titles">
                        {meetingId && (
                            <span className="meeting-id" title={meetingId}>
                                #{meetingId.slice(0, 8)}…
                            </span>
                        )}
                    </div>
                </div>
                {meetingId && <span className="badge live-badge">● Live</span>}
            </div>

            <div className="header-right" ref={menuRef}>
                <button
                    className="dots-btn"
                    onClick={() => setMenuOpen(v => !v)}
                    aria-label="Menu"
                >
                    <span /><span /><span />
                </button>

                {menuOpen && (
                    <div className="dropdown">
                        <button className="dropdown-item" onClick={handleHistory}>
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" />
                            </svg>
                            History
                        </button>
                    </div>
                )}
            </div>
        </header>
    )
}
