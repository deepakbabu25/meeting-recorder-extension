const API_BASE = 'https://debroah-prehazard-candance.ngrok-free.dev';

export async function loginWithGoogle() {
    return new Promise((resolve, reject) => {
        chrome.identity.getAuthToken({ interactive: true }, async function (token) {
            if (chrome.runtime.lastError || !token) {
                console.error("Chrome Identity Error:", chrome.runtime.lastError);
                return reject(chrome.runtime.lastError);
            }

            // Send Google token to backend to get back WebEnoid JWT
            try {
                const res = await fetch(`${API_BASE}/api/auth/google`, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "ngrok-skip-browser-warning": "true",
                    },
                    body: JSON.stringify({ token: token }),
                });

                if (!res.ok) {
                    throw new Error("Failed to authenticate with backend.");
                }

                const data = await res.json();

                // Store the returned JWT
                await chrome.storage.local.set({ auth_token: data.access_token, user_name: data.name });
                console.log("Logged in successfully as", data.name);
                resolve(data.access_token);

            } catch (err) {
                console.error("Backend Auth Error:", err);
                reject(err);
            }
        });
    });
}

export async function importGuestMeetingToBackend(meetingData, authToken) {
    if (!meetingData || !authToken) return;

    try {
        const res = await fetch(`${API_BASE}/api/meetings/import`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${authToken}`,
                "ngrok-skip-browser-warning": "true",
            },
            body: JSON.stringify({
                title: "Recorded Meeting",
                transcript_chunks: meetingData.transcript_chunks || [],
                summary: meetingData.summary || {},
                qa_history: meetingData.qa_history || []
            }),
        });

        if (!res.ok) throw new Error("Import failed");
        const data = await res.json();
        return data.meeting_id;
    } catch (err) {
        console.error("Import error:", err);
        throw err;
    }
}
