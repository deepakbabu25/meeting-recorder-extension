import React, { useState } from 'react';
import { loginWithGoogle, importGuestMeetingToBackend } from '../utils/auth';
import { deleteGuestMeeting } from '../utils/indexedDB';
import './LoginDialog.css';

export default function LoginDialog({ onClose, currentMeetingData }) {
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState(null);

    const handleLoginAndSave = async () => {
        setIsLoading(true);
        setError(null);
        try {
            // 1. Get token
            const token = await loginWithGoogle();

            // 2. Import meeting
            if (currentMeetingData) {
                await importGuestMeetingToBackend(currentMeetingData, token);
                await deleteGuestMeeting(currentMeetingData.meeting_id);
            }

            // Close dialog, everything saved!
            onClose(true); // true = logged in
        } catch (err) {
            console.error(err);
            setError("Login failed. Please try again.");
            setIsLoading(false);
        }
    };

    return (
        <div className="login-dialog-overlay">
            <div className="login-dialog-card">
                {isLoading ? (
                    <div className="login-loading">
                        <div className="spinner"></div>
                        <h3>Saving to Cloud...</h3>
                        <p>Migrating your meeting transcript and AI insights to your account.</p>
                    </div>
                ) : (
                    <>
                        <h3>Your meeting is ready!</h3>
                        <p className="login-dialog-subtitle">
                            Login to save this meeting and access it later from your history.
                        </p>

                        {error && <div className="login-error">{error}</div>}

                        <div className="login-dialog-actions">
                            <button className="btn-google" onClick={handleLoginAndSave}>
                                <svg viewBox="0 0 24 24" width="18" height="18" xmlns="http://www.w3.org/2000/svg">
                                    <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4" />
                                    <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
                                    <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05" />
                                    <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" />
                                </svg>
                                Sign in with Google
                            </button>
                            <button className="btn-secondary" onClick={() => onClose(false)}>
                                Continue without saving
                            </button>
                        </div>

                        <div className="login-dialog-footer">
                            If you don't save, this meeting will be lost when you close the panel.
                        </div>
                    </>
                )}
            </div>
        </div>
    );
}
