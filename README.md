# Voice Sales Training System

A two-agent AI system for practicing and improving sales calls:

- **Agent 1 (Persona)**: Sarah Chen, VP of Operations - a realistic prospect you can call and pitch to
- **Agent 2 (Coach)**: analyzes transcripts and provides feedback

## Features

- **Phone-based training**: Call in and practice your pitch on a real phone
- **Realistic AI prospect**: Powered by OpenAI GPT-5 Chat, responds naturally with questions and objections
- **Automatic transcription**: Twilio handles speech-to-text and text-to-speech
- **Conversation history**: All calls are saved for later review

## Tech Stack

- **Backend**: Python + FastAPI
- **Voice**: Twilio (phone, speech recognition, text-to-speech)
- **AI**: OpenAI GPT-5 Chat API
- **Storage**: JSON files (easily upgradeable to SQLite/PostgreSQL)

## Prerequisites

1. **Python 3.9+**
2. **Twilio Account**: Sign up at https://www.twilio.com
   - Purchase a phone number with voice capabilities
   - Get your Account SID and Auth Token
3. **OpenAI API Key**: Get from https://platform.openai.com/
4. **ngrok** (for development): Download from https://ngrok.com

## Installation

### 1. Clone and Setup

```bash
# Clone the repository
git clone <your-repo-url>
cd sales-practice-agent

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env with your credentials
nano .env  # or use your preferred editor
```

Fill in your `.env` file:

```env
# Twilio Configuration
TWILIO_ACCOUNT_SID=your_account_sid_here
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_PHONE_NUMBER=+1234567890

# OpenAI API Configuration
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-5.1-chat-latest

# Application Configuration
HOST=0.0.0.0
PORT=8000
BASE_URL=https://your-ngrok-url.ngrok.io  # Update after starting ngrok

# Storage Configuration
TRANSCRIPTS_DIR=data/transcripts
```

### 3. Start ngrok (Development)

In a separate terminal:

```bash
ngrok http 8000
```

Copy the HTTPS forwarding URL (e.g., `https://abc123.ngrok.io`) and update `BASE_URL` in your `.env` file.

### 4. Configure Twilio Webhook

1. Go to [Twilio Console](https://console.twilio.com)
2. Navigate to Phone Numbers → Manage → Active Numbers
3. Click on your phone number
4. Under "Voice Configuration":
   - **A Call Comes In**: Webhook, `https://your-ngrok-url.ngrok.io/voice/incoming`, HTTP POST
   - **Call Status Changes**: Webhook, `https://your-ngrok-url.ngrok.io/voice/status`, HTTP POST
5. Save

### 5. Run the Application

```bash
python main.py
```

You should see:
```
INFO:     Started server process
INFO:     Uvicorn running on http://0.0.0.0:8000
```

## Usage

### Making a Call

1. Call your Twilio phone number
2. Sarah will answer and greet you
3. Start your sales pitch!
4. Have a natural conversation
5. End the call by saying "goodbye" or hanging up

### Viewing Transcripts

List recent calls:
```bash
curl http://localhost:8000/transcripts
```

Get specific transcript:
```bash
curl http://localhost:8000/transcripts/{call_sid}
```

Or visit in your browser:
- http://localhost:8000/transcripts

## Project Structure

```
sales-practice-agent/
├── main.py                   # FastAPI application + Twilio webhooks
├── config.py                 # Configuration management
├── requirements.txt          # Python dependencies
├── .env                      # Environment variables (create from .env.example)
├── agents/
│   ├── __init__.py
│   └── persona.py           # Sarah persona + OpenAI integration
├── services/
│   ├── __init__.py
│   ├── twilio_handler.py    # TwiML response generation
│   └── storage.py           # Transcript storage
├── prompts/
│   └── sarah_persona.txt    # Sarah's character definition
└── data/
    └── transcripts/         # Saved call transcripts (JSON)
```

## How It Works

### Call Flow

1. **You call** your Twilio number
2. **Twilio** sends webhook to `/voice/incoming`
3. **Server** creates a new Sarah persona instance
4. **Sarah** generates a greeting via OpenAI GPT-5 Chat
5. **Twilio** converts text to speech and plays it
6. **Twilio** captures your speech and converts to text
7. **Server** sends your message to Sarah (OpenAI GPT-5 Chat)
8. **Sarah** responds naturally based on her persona
9. **Repeat** steps 6-8 until call ends
10. **Server** saves full transcript

### Sarah's Persona

Sarah Chen is a VP of Operations at a mid-sized manufacturing company. She:

- Has realistic business challenges (inventory, costs, efficiency)
- Responds naturally to sales pitches
- Asks clarifying questions when needed
- Raises realistic objections
- Rewards good discovery questions
- Becomes more resistant to pushy tactics

You can customize her persona by editing `prompts/sarah_persona.txt`.

## API Endpoints

### Voice Webhooks (Twilio)

- `POST /voice/incoming` - Handle incoming calls
- `POST /voice/respond` - Handle conversation turns
- `POST /voice/status` - Handle call status updates

### Transcript API

- `GET /` - Health check
- `GET /transcripts` - List recent transcripts
- `GET /transcripts/{call_sid}` - Get specific transcript

## Development

### Running in Development Mode

The application runs in development mode by default with auto-reload:

```bash
python main.py
```

### Testing Locally

1. Make sure ngrok is running
2. Update `.env` with your ngrok URL
3. Configure Twilio webhooks
4. Call your Twilio number

### Logs

The application logs all interactions to stdout:

```
INFO: Incoming call: CA123... from +1234567890
INFO: Sarah greeting: Hello, this is Sarah Chen...
INFO: Voice response for call CA123...: 'Hi Sarah, ...'
INFO: Sarah response: Thanks for calling. What can I help you with?
```

## Coming Soon

- **Coach Agent**: Analyzes transcripts and provides structured feedback
- **Web Dashboard**: View transcripts and feedback in a UI
- **Multiple Personas**: Different prospects with varying challenges
- **Performance Metrics**: Track improvement over time
- **SQLite/PostgreSQL**: Upgrade from JSON file storage

## Troubleshooting

### Call connects but no audio

- Check that your ngrok URL is correct in `.env`
- Verify Twilio webhook is configured correctly
- Check server logs for errors

### Sarah doesn't respond

- Verify `OPENAI_API_KEY` is correct
- Check OpenAI API quota/limits
- Look for errors in server logs

### Speech recognition issues

- Speak clearly and at a moderate pace
- Ensure good phone connection
- Check Twilio console for transcription logs

### "No active call found" error

- Server may have restarted (in-memory session lost)
- Hang up and call again

## Production Deployment

For production:

1. Deploy to a cloud provider (AWS, GCP, Heroku, etc.)
2. Use a production-grade ASGI server (Gunicorn + Uvicorn)
3. Replace in-memory `active_calls` dict with Redis
4. Upgrade storage from JSON to PostgreSQL
5. Add authentication for transcript API endpoints
6. Set up monitoring and error tracking
7. Configure HTTPS (required for Twilio webhooks)

## Cost Considerations

- **Twilio**: ~$1/month for phone number + $0.0140/min for calls
- **OpenAI API**: Pricing varies by model usage (see OpenAI pricing page)
- **Infrastructure**: Free tier on most cloud providers for low usage

A 5-minute practice call typically costs less than $0.10.

## License

MIT License - see LICENSE file

## Contributing

Contributions welcome! Please open an issue or PR.

## Questions?

Open an issue or reach out!
