from flask import Flask, request, jsonify, render_template_string
from openai import AzureOpenAI
import os
import time
import json

app = Flask(__name__)

# Configuration - These should be in Application Settings in Azure
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "https://azureopenai-mcloud-be.openai.azure.com/")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")  # Add your full API key in Azure App Settings
ASSISTANT_ID = os.getenv("ASSISTANT_ID", "asst_UQvaabCLwN4tYdmOd2YmpU7f")
API_VERSION = "2024-02-15-preview"

# Initialize the client
client = AzureOpenAI(
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
    api_key=AZURE_OPENAI_API_KEY,
    api_version=API_VERSION
)

# Simple HTML interface
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Fabric Data Agent</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            max-width: 800px;
            margin: 50px auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            background: white;
            border-radius: 10px;
            padding: 30px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 {
            color: #0078d4;
            border-bottom: 2px solid #0078d4;
            padding-bottom: 10px;
        }
        .chat-box {
            border: 1px solid #ddd;
            border-radius: 5px;
            padding: 20px;
            height: 400px;
            overflow-y: auto;
            margin-bottom: 20px;
            background-color: #fafafa;
        }
        .message {
            margin: 10px 0;
            padding: 10px;
            border-radius: 5px;
        }
        .user-message {
            background-color: #0078d4;
            color: white;
            text-align: right;
            margin-left: 20%;
        }
        .agent-message {
            background-color: #e8e8e8;
            margin-right: 20%;
        }
        .input-group {
            display: flex;
            gap: 10px;
        }
        input[type="text"] {
            flex: 1;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 5px;
            font-size: 16px;
        }
        button {
            padding: 10px 20px;
            background-color: #0078d4;
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 16px;
        }
        button:hover {
            background-color: #106ebe;
        }
        button:disabled {
            background-color: #ccc;
            cursor: not-allowed;
        }
        .loading {
            text-align: center;
            color: #666;
            font-style: italic;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Fabric Data Agent Assistant</h1>
        <p>Ask questions about analyzing data from The MS Fabric lakehouse</p>
        <div id="chat-box" class="chat-box"></div>
        <div class="input-group">
            <input type="text" id="user-input" placeholder="Type your message here..." onkeypress="handleKeyPress(event)">
            <button onclick="sendMessage()" id="send-btn">Send</button>
        </div>
    </div>

    <script>
        let isProcessing = false;

        function handleKeyPress(event) {
            if (event.key === 'Enter' && !isProcessing) {
                sendMessage();
            }
        }

        async function sendMessage() {
            const input = document.getElementById('user-input');
            const message = input.value.trim();
            
            if (!message || isProcessing) return;
            
            isProcessing = true;
            const sendBtn = document.getElementById('send-btn');
            sendBtn.disabled = true;
            
            // Add user message to chat
            addMessage(message, 'user');
            input.value = '';
            
            // Show loading
            const loadingId = 'loading-' + Date.now();
            addLoadingMessage(loadingId);
            
            try {
                const response = await fetch('/chat', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ message: message })
                });
                
                const data = await response.json();
                
                // Remove loading message
                removeLoadingMessage(loadingId);
                
                if (data.error) {
                    addMessage('Error: ' + data.error, 'agent');
                } else {
                    addMessage(data.response, 'agent');
                }
            } catch (error) {
                removeLoadingMessage(loadingId);
                addMessage('Error: Failed to connect to the agent', 'agent');
            } finally {
                isProcessing = false;
                sendBtn.disabled = false;
                input.focus();
            }
        }

        function addMessage(message, sender) {
            const chatBox = document.getElementById('chat-box');
            const messageDiv = document.createElement('div');
            messageDiv.className = 'message ' + (sender === 'user' ? 'user-message' : 'agent-message');
            messageDiv.textContent = message;
            chatBox.appendChild(messageDiv);
            chatBox.scrollTop = chatBox.scrollHeight;
        }

        function addLoadingMessage(id) {
            const chatBox = document.getElementById('chat-box');
            const loadingDiv = document.createElement('div');
            loadingDiv.id = id;
            loadingDiv.className = 'loading';
            loadingDiv.textContent = 'Agent is thinking...';
            chatBox.appendChild(loadingDiv);
            chatBox.scrollTop = chatBox.scrollHeight;
        }

        function removeLoadingMessage(id) {
            const element = document.getElementById(id);
            if (element) {
                element.remove();
            }
        }
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    """Serve the chat interface"""
    return render_template_string(HTML_TEMPLATE)

@app.route('/chat', methods=['POST'])
def chat():
    """Handle chat requests"""
    try:
        user_message = request.json.get('message')
        
        if not user_message:
            return jsonify({"error": "No message provided"}), 400
        
        # Create a new thread for this conversation
        thread = client.beta.threads.create()
        
        # Add the user's message to the thread
        message = client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=user_message
        )
        
        # Run the assistant on the thread
        run = client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=ASSISTANT_ID
        )
        
        # Wait for the run to complete
        max_attempts = 30  # Maximum 30 seconds wait
        attempts = 0
        
        while attempts < max_attempts:
            run_status = client.beta.threads.runs.retrieve(
                thread_id=thread.id,
                run_id=run.id
            )
            
            if run_status.status == 'completed':
                break
            elif run_status.status in ['failed', 'cancelled', 'expired']:
                return jsonify({"error": f"Run {run_status.status}"}), 500
            
            time.sleep(1)
            attempts += 1
        
        if attempts >= max_attempts:
            return jsonify({"error": "Request timeout"}), 500
        
        # Get the assistant's response
        messages = client.beta.threads.messages.list(thread_id=thread.id)
        
        # Get the latest assistant message
        assistant_response = None
        for msg in messages.data:
            if msg.role == "assistant":
                # Extract text from the message content
                if msg.content and len(msg.content) > 0:
                    content = msg.content[0]
                    if hasattr(content, 'text') and hasattr(content.text, 'value'):
                        assistant_response = content.text.value
                        break
        
        if assistant_response:
            return jsonify({"response": assistant_response})
        else:
            return jsonify({"error": "No response from assistant"}), 500
            
    except Exception as e:
        app.logger.error(f"Error in chat endpoint: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "assistant_id": ASSISTANT_ID})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=False)
