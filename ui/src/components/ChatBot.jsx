import { useState, useRef, useEffect } from 'react'
import './ChatBot.css'

const STATUS_MESSAGES = {
    idle: { icon: '⏳', text: 'Waiting for a meeting to start…' },
    recording: { icon: '●', text: 'Recording in progress — chat unlocks after summary.' },
    processing: { icon: '⟳', text: 'Analyzing your meeting…' },
    error: { icon: '⚠️', text: 'Could not load meeting summary. Chat unavailable.' },
}

export default function ChatBot({ onSend, disabled, status }) {
    const [messages, setMessages] = useState([])
    const [input, setInput] = useState('')
    const [thinking, setThinking] = useState(false)
    const bottomRef = useRef(null)

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    }, [messages, thinking])

    async function handleSend() {
        const q = input.trim()
        if (!q || disabled || thinking) return

        setMessages(prev => [...prev, { role: 'user', text: q }])
        setInput('')
        setThinking(true)

        try {
            const answer = await onSend(q)
            setMessages(prev => [...prev, { role: 'bot', text: answer }])
        } catch {
            setMessages(prev => [...prev, { role: 'bot', text: 'Error answering question.', error: true }])
        } finally {
            setThinking(false)
        }
    }

    function handleKey(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault()
            handleSend()
        }
    }

    return (
        <div className="chatbot">
            {/* ── Messages area ── */}
            <div className="chat-messages">
                {messages.length === 0 && (
                    <div className="chat-empty">
                        {disabled ? (
                            <>
                                <div className="chat-empty-icon">
                                    {STATUS_MESSAGES[status]?.icon ?? '⏳'}
                                </div>
                                <p>{STATUS_MESSAGES[status]?.text ?? 'Please wait…'}</p>
                            </>
                        ) : (
                            <>
                                <div className="chat-empty-icon">💬</div>
                                <p>Ask anything about your meeting</p>
                            </>
                        )}
                    </div>
                )}

                {messages.map((msg, i) => (
                    <div key={i} className={`chat-bubble ${msg.role} ${msg.error ? 'error' : ''}`}>
                        <span className="bubble-label">{msg.role === 'user' ? 'You' : 'WebEnoid'}</span>
                        <p className="bubble-text">{msg.text}</p>
                    </div>
                ))}

                {thinking && (
                    <div className="chat-bubble bot">
                        <span className="bubble-label">WebEnoid</span>
                        <div className="thinking-dots">
                            <span /><span /><span />
                        </div>
                    </div>
                )}

                <div ref={bottomRef} />
            </div>

            {/* ── Input bar ── */}
            <div className={`chat-inputbar ${disabled ? 'chat-disabled' : ''}`}>
                <input
                    className="chat-input"
                    value={input}
                    onChange={e => setInput(e.target.value)}
                    onKeyDown={handleKey}
                    placeholder={disabled ? 'Waiting for summary…' : 'Ask about this meeting…'}
                    disabled={disabled || thinking}
                />
                <button
                    className="chat-send"
                    onClick={handleSend}
                    disabled={disabled || thinking || !input.trim()}
                    aria-label="Send"
                >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                        <line x1="22" y1="2" x2="11" y2="13" /><polygon points="22 2 15 22 11 13 2 9 22 2" />
                    </svg>
                </button>
            </div>
        </div>
    )
}
