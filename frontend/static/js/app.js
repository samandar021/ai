/**
 * Computer Use Agent Backend Frontend Demo
 * 
 * This JavaScript application provides a complete frontend interface
 * for the Computer Use Agent Backend, featuring:
 * - Session management
 * - Real-time chat interface
 * - WebSocket communication
 * - Agent status monitoring
 * - File management
 */

class ComputerUseApp {
    constructor() {
        this.apiBaseUrl = 'http://localhost:8000';
        this.wsBaseUrl = 'ws://localhost:8000';
        this.currentSession = null;
        this.websocket = null;
        this.sessions = [];
        
        this.init();
    }

    async init() {
        console.log('Initializing Computer Use Agent Frontend...');
        
        // Setup event listeners
        this.setupEventListeners();
        
        // Check API status
        await this.checkApiStatus();
        
        // Load existing sessions
        await this.loadSessions();
        
        // Setup periodic status checks
        setInterval(() => this.updateStatus(), 5000);
        
        console.log('Application initialized successfully');
    }

    setupEventListeners() {
        // Enter key in message input
        document.getElementById('messageInput').addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        // File input change
        document.getElementById('fileInput').addEventListener('change', (e) => {
            this.displaySelectedFiles(e.target.files);
        });
    }

    async checkApiStatus() {
        try {
            const response = await fetch(`${this.apiBaseUrl}/health`);
            const data = await response.json();
            
            document.getElementById('apiStatus').textContent = 'Connected';
            document.getElementById('apiStatus').className = 'value connected';
            
            console.log('API Status:', data);
        } catch (error) {
            document.getElementById('apiStatus').textContent = 'Disconnected';
            document.getElementById('apiStatus').className = 'value disconnected';
            console.error('API Status Check Failed:', error);
        }
    }

    async loadSessions() {
        try {
            const response = await fetch(`${this.apiBaseUrl}/api/v1/sessions/`);
            const data = await response.json();
            
            this.sessions = data.sessions || [];
            this.renderSessionList();
            
            console.log('Loaded sessions:', this.sessions.length);
        } catch (error) {
            console.error('Failed to load sessions:', error);
            this.addSystemMessage('Failed to load session history');
        }
    }

    renderSessionList() {
        const sessionList = document.getElementById('sessionList');
        sessionList.innerHTML = '';

        if (this.sessions.length === 0) {
            sessionList.innerHTML = '<div class="no-sessions">No sessions yet</div>';
            return;
        }

        this.sessions.forEach(session => {
            const sessionElement = document.createElement('div');
            sessionElement.className = `session-item ${session.status}`;
            sessionElement.onclick = () => this.selectSession(session.id);
            
            sessionElement.innerHTML = `
                <div class="session-title">${session.title}</div>
                <div class="session-meta">
                    <span class="status">${session.status}</span>
                    <span class="date">${new Date(session.created_at).toLocaleDateString()}</span>
                </div>
                <div class="session-stats">
                    <span>${session.message_count || 0} messages</span>
                </div>
            `;
            
            sessionList.appendChild(sessionElement);
        });
    }

    async selectSession(sessionId) {
        if (this.currentSession?.id === sessionId) return;

        console.log('Selecting session:', sessionId);
        
        // Disconnect existing WebSocket
        if (this.websocket) {
            this.websocket.close();
        }

        // Load session details
        try {
            const response = await fetch(`${this.apiBaseUrl}/api/v1/sessions/${sessionId}`);
            const session = await response.json();
            
            this.currentSession = session;
            document.getElementById('activeSession').textContent = session.title;
            
            // Load session messages
            await this.loadSessionMessages(sessionId);
            
            // Connect WebSocket
            this.connectWebSocket(sessionId);
            
            // Enable chat input
            document.getElementById('messageInput').disabled = false;
            document.getElementById('sendButton').disabled = false;
            
            // Update UI
            this.updateSessionSelection(sessionId);
            
        } catch (error) {
            console.error('Failed to select session:', error);
            this.addSystemMessage('Failed to load session');
        }
    }

    async loadSessionMessages(sessionId) {
        try {
            const response = await fetch(`${this.apiBaseUrl}/api/v1/sessions/${sessionId}/messages/`);
            const data = await response.json();
            
            const chatMessages = document.getElementById('chatMessages');
            chatMessages.innerHTML = '';
            
            if (data.messages && data.messages.length > 0) {
                data.messages.forEach(message => {
                    this.addMessageToChat(message);
                });
            } else {
                chatMessages.innerHTML = '<div class="welcome-message"><p>Session started. Send a message to begin!</p></div>';
            }
            
            this.scrollToBottom();
            
        } catch (error) {
            console.error('Failed to load messages:', error);
            this.addSystemMessage('Failed to load message history');
        }
    }

    updateSessionSelection(selectedId) {
        document.querySelectorAll('.session-item').forEach(item => {
            item.classList.remove('selected');
        });
        
        document.querySelectorAll('.session-item').forEach(item => {
            if (item.onclick.toString().includes(selectedId)) {
                item.classList.add('selected');
            }
        });
    }

    connectWebSocket(sessionId) {
        const wsUrl = `${this.wsBaseUrl}/api/v1/sessions/${sessionId}/ws`;
        console.log('Connecting WebSocket:', wsUrl);
        
        this.websocket = new WebSocket(wsUrl);
        
        this.websocket.onopen = () => {
            console.log('WebSocket connected');
            document.getElementById('wsStatus').textContent = 'Connected';
            document.getElementById('wsStatus').className = 'value connected';
        };
        
        this.websocket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleWebSocketMessage(data);
        };
        
        this.websocket.onclose = () => {
            console.log('WebSocket disconnected');
            document.getElementById('wsStatus').textContent = 'Disconnected';
            document.getElementById('wsStatus').className = 'value disconnected';
        };
        
        this.websocket.onerror = (error) => {
            console.error('WebSocket error:', error);
            document.getElementById('wsStatus').textContent = 'Error';
            document.getElementById('wsStatus').className = 'value error';
        };
    }

    handleWebSocketMessage(data) {
        console.log('WebSocket message:', data);
        
        switch (data.event_type) {
            case 'message':
                this.handleMessageEvent(data);
                break;
            case 'tool_call':
                this.handleToolCallEvent(data);
                break;
            case 'tool_result':
                this.handleToolResultEvent(data);
                break;
            case 'status_update':
                this.handleStatusUpdateEvent(data);
                break;
            case 'error':
                this.handleErrorEvent(data);
                break;
            case 'heartbeat':
                // Handle heartbeat silently
                break;
            default:
                console.log('Unknown WebSocket event:', data.event_type);
        }
    }

    handleMessageEvent(data) {
        if (data.data.type === 'start') {
            this.currentMessageElement = this.addStreamingMessage();
        } else if (data.data.type === 'delta') {
            if (this.currentMessageElement) {
                this.appendToStreamingMessage(data.data.content);
            }
        }
    }

    handleToolCallEvent(data) {
        this.addToolCallMessage(data.data);
    }

    handleToolResultEvent(data) {
        this.addToolResultMessage(data.data);
    }

    handleStatusUpdateEvent(data) {
        this.updateAgentStatus(data.data.status);
    }

    handleErrorEvent(data) {
        this.addErrorMessage(data.data.error);
    }

    async sendMessage() {
        const input = document.getElementById('messageInput');
        const message = input.value.trim();
        
        if (!message || !this.currentSession) return;
        
        // Add user message to chat
        this.addUserMessage(message);
        
        // Clear input
        input.value = '';
        
        // Start agent processing
        try {
            const response = await fetch(`${this.apiBaseUrl}/api/v1/sessions/${this.currentSession.id}/start`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    message: message,
                    stream: true
                })
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const result = await response.json();
            console.log('Agent session started:', result);
            
            this.updateAgentStatus('processing');
            
        } catch (error) {
            console.error('Failed to send message:', error);
            this.addErrorMessage('Failed to send message. Please try again.');
        }
    }

    addMessageToChat(message) {
        const chatMessages = document.getElementById('chatMessages');
        const messageElement = document.createElement('div');
        
        switch (message.message_type) {
            case 'user':
                messageElement.className = 'message user-message';
                messageElement.innerHTML = `
                    <div class="message-content">${this.escapeHtml(message.content)}</div>
                    <div class="message-time">${new Date(message.created_at).toLocaleTimeString()}</div>
                `;
                break;
            case 'assistant':
                messageElement.className = 'message assistant-message';
                messageElement.innerHTML = `
                    <div class="message-content">${this.escapeHtml(message.content)}</div>
                    <div class="message-time">${new Date(message.created_at).toLocaleTimeString()}</div>
                `;
                break;
            case 'tool_call':
                const toolData = JSON.parse(message.content);
                messageElement.className = 'message tool-call-message';
                messageElement.innerHTML = `
                    <div class="tool-header">🔧 Tool Call: ${toolData.name}</div>
                    <div class="tool-content">${this.escapeHtml(JSON.stringify(toolData.parameters, null, 2))}</div>
                    <div class="message-time">${new Date(message.created_at).toLocaleTimeString()}</div>
                `;
                break;
            case 'tool_result':
                messageElement.className = 'message tool-result-message';
                messageElement.innerHTML = `
                    <div class="tool-header">✅ Tool Result</div>
                    <div class="tool-content">${this.escapeHtml(message.content)}</div>
                    <div class="message-time">${new Date(message.created_at).toLocaleTimeString()}</div>
                `;
                break;
            case 'error':
                messageElement.className = 'message error-message';
                messageElement.innerHTML = `
                    <div class="error-content">❌ Error: ${this.escapeHtml(message.content)}</div>
                    <div class="message-time">${new Date(message.created_at).toLocaleTimeString()}</div>
                `;
                break;
        }
        
        chatMessages.appendChild(messageElement);
        this.scrollToBottom();
    }

    addUserMessage(content) {
        const chatMessages = document.getElementById('chatMessages');
        const messageElement = document.createElement('div');
        messageElement.className = 'message user-message';
        messageElement.innerHTML = `
            <div class="message-content">${this.escapeHtml(content)}</div>
            <div class="message-time">${new Date().toLocaleTimeString()}</div>
        `;
        chatMessages.appendChild(messageElement);
        this.scrollToBottom();
    }

    addStreamingMessage() {
        const chatMessages = document.getElementById('chatMessages');
        const messageElement = document.createElement('div');
        messageElement.className = 'message assistant-message streaming';
        messageElement.innerHTML = `
            <div class="message-content"></div>
            <div class="message-time">${new Date().toLocaleTimeString()}</div>
        `;
        chatMessages.appendChild(messageElement);
        this.scrollToBottom();
        return messageElement;
    }

    appendToStreamingMessage(content) {
        if (this.currentMessageElement) {
            const contentDiv = this.currentMessageElement.querySelector('.message-content');
            contentDiv.textContent += content;
            this.scrollToBottom();
        }
    }

    addToolCallMessage(toolData) {
        const chatMessages = document.getElementById('chatMessages');
        const messageElement = document.createElement('div');
        messageElement.className = 'message tool-call-message';
        messageElement.innerHTML = `
            <div class="tool-header">🔧 Tool Call: ${toolData.name}</div>
            <div class="tool-content">${this.escapeHtml(JSON.stringify(toolData.parameters, null, 2))}</div>
            <div class="message-time">${new Date().toLocaleTimeString()}</div>
        `;
        chatMessages.appendChild(messageElement);
        this.scrollToBottom();
    }

    addToolResultMessage(toolData) {
        const chatMessages = document.getElementById('chatMessages');
        const messageElement = document.createElement('div');
        messageElement.className = 'message tool-result-message';
        messageElement.innerHTML = `
            <div class="tool-header">✅ Tool Result: ${toolData.name}</div>
            <div class="tool-content">${this.escapeHtml(toolData.result)}</div>
            <div class="message-time">${new Date().toLocaleTimeString()}</div>
        `;
        chatMessages.appendChild(messageElement);
        this.scrollToBottom();
    }

    addErrorMessage(error) {
        const chatMessages = document.getElementById('chatMessages');
        const messageElement = document.createElement('div');
        messageElement.className = 'message error-message';
        messageElement.innerHTML = `
            <div class="error-content">❌ Error: ${this.escapeHtml(error)}</div>
            <div class="message-time">${new Date().toLocaleTimeString()}</div>
        `;
        chatMessages.appendChild(messageElement);
        this.scrollToBottom();
    }

    addSystemMessage(message) {
        const chatMessages = document.getElementById('chatMessages');
        const messageElement = document.createElement('div');
        messageElement.className = 'message system-message';
        messageElement.innerHTML = `
            <div class="system-content">ℹ️ ${this.escapeHtml(message)}</div>
            <div class="message-time">${new Date().toLocaleTimeString()}</div>
        `;
        chatMessages.appendChild(messageElement);
        this.scrollToBottom();
    }

    updateAgentStatus(status) {
        const statusElement = document.getElementById('agentStatus');
        const indicator = statusElement.querySelector('.status-indicator');
        const text = statusElement.querySelector('.status-text');
        
        // Remove all status classes
        indicator.className = 'status-indicator';
        
        // Add new status class and update text
        switch (status) {
            case 'idle':
                indicator.classList.add('idle');
                text.textContent = 'Ready';
                break;
            case 'processing':
                indicator.classList.add('processing');
                text.textContent = 'Processing...';
                break;
            case 'waiting_for_tool':
                indicator.classList.add('waiting');
                text.textContent = 'Using tools...';
                break;
            case 'completed':
                indicator.classList.add('completed');
                text.textContent = 'Completed';
                setTimeout(() => this.updateAgentStatus('idle'), 2000);
                break;
            case 'error':
                indicator.classList.add('error');
                text.textContent = 'Error';
                break;
            default:
                indicator.classList.add('idle');
                text.textContent = 'Ready';
        }
    }

    scrollToBottom() {
        const chatMessages = document.getElementById('chatMessages');
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    async updateStatus() {
        // Update API status
        await this.checkApiStatus();
    }

    // Modal functions
    createNewSession() {
        document.getElementById('newSessionModal').style.display = 'block';
        document.getElementById('sessionTitle').focus();
    }

    async createSession() {
        const title = document.getElementById('sessionTitle').value.trim();
        const maxToolCalls = parseInt(document.getElementById('maxToolCalls').value);
        
        if (!title) {
            alert('Please enter a session title');
            return;
        }
        
        try {
            const response = await fetch(`${this.apiBaseUrl}/api/v1/sessions/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    title: title,
                    max_tool_calls: maxToolCalls
                })
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const session = await response.json();
            console.log('Session created:', session);
            
            // Add to sessions list
            this.sessions.unshift(session);
            this.renderSessionList();
            
            // Select the new session
            await this.selectSession(session.id);
            
            // Close modal
            this.closeModal('newSessionModal');
            
            // Clear form
            document.getElementById('sessionTitle').value = '';
            document.getElementById('maxToolCalls').value = '50';
            
        } catch (error) {
            console.error('Failed to create session:', error);
            alert('Failed to create session. Please try again.');
        }
    }

    closeModal(modalId) {
        document.getElementById(modalId).style.display = 'none';
    }

    // File management functions
    displaySelectedFiles(files) {
        const fileList = document.getElementById('fileList');
        fileList.innerHTML = '';
        
        Array.from(files).forEach(file => {
            const fileItem = document.createElement('div');
            fileItem.className = 'file-item';
            fileItem.innerHTML = `
                <div class="file-name">${file.name}</div>
                <div class="file-size">${this.formatFileSize(file.size)}</div>
            `;
            fileList.appendChild(fileItem);
        });
    }

    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    async uploadFiles() {
        const fileInput = document.getElementById('fileInput');
        const files = fileInput.files;
        
        if (files.length === 0) {
            alert('Please select files to upload');
            return;
        }
        
        // TODO: Implement file upload to backend
        console.log('Files to upload:', files);
        alert('File upload functionality will be implemented in the backend');
    }
}

// Global functions for onclick handlers
let app;

function createNewSession() {
    app.createNewSession();
}

function createSession() {
    app.createSession();
}

function closeModal(modalId) {
    app.closeModal(modalId);
}

function sendMessage() {
    app.sendMessage();
}

function uploadFiles() {
    app.uploadFiles();
}

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    app = new ComputerUseApp();
});