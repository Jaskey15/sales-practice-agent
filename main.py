"""
Main FastAPI application for the voice sales training system.
Handles Twilio webhooks for incoming calls and voice interactions.
"""
from fastapi import FastAPI, Form, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import PlainTextResponse
import logging
import json
from typing import Optional, Dict

from config import get_settings
from agents.persona import SarahPersona
from agents.coach import SalesCoach
from services.twilio_handler import TwilioVoiceHandler, ConversationRelayConfig
from services.storage import TranscriptStorage

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Voice Sales Training System",
    description="AI-powered sales training with persona and coach agents",
    version="1.0.0"
)

# Load configuration
settings = get_settings()

# Initialize services
twilio_handler = TwilioVoiceHandler(
    base_url=settings.base_url,
    voice_id=settings.conversation_relay_voice_id
)
storage = TranscriptStorage(storage_dir=settings.transcripts_dir)
coach = SalesCoach(api_key=settings.openai_api_key, model=settings.openai_model)

# Store active call sessions (in production, use Redis or database)
# Key: call_sid, Value: SarahPersona instance
active_calls: Dict[str, SarahPersona] = {}

CONVERSATION_RELAY_PATH = "/voice/relay"


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "Voice Sales Training System",
        "version": "1.0.0"
    }


@app.post("/voice/incoming", response_class=PlainTextResponse)
async def handle_incoming_call(
    request: Request,
    CallSid: str = Form(...),
    From: str = Form(...),
    To: str = Form(...)
):
    """
    Handle incoming phone call from Twilio.
    This is the webhook Twilio calls when someone calls your number.

    Args:
        request: FastAPI request object
        CallSid: Twilio call identifier
        From: Caller's phone number
        To: Your Twilio phone number

    Returns:
        TwiML response to greet the caller
    """
    logger.info(f"Incoming call: {CallSid} from {From}")

    try:
        sarah = SarahPersona(
            api_key=settings.openai_api_key,
            model=settings.openai_model
        )

        # Store in active calls
        active_calls[CallSid] = sarah

        # Get Sarah's greeting for the welcome prompt
        greeting = sarah.get_greeting()
        logger.info(f"Sarah greeting: {greeting}")

        relay_config = ConversationRelayConfig(
            voice_id=twilio_handler.voice_id,
            welcome_greeting=greeting,
            text_normalization=settings.conversation_relay_text_normalization,
            language=settings.conversation_relay_language,
        )

        twiml = twilio_handler.create_conversationrelay_response(
            config=relay_config,
            relay_path=CONVERSATION_RELAY_PATH,
        )

        return PlainTextResponse(content=twiml, media_type="application/xml")

    except Exception as e:
        logger.error(f"Error handling incoming call: {e}", exc_info=True)
        twiml = twilio_handler.create_error_response()
        return PlainTextResponse(content=twiml, media_type="application/xml")


@app.websocket(CONVERSATION_RELAY_PATH)
async def conversation_relay_socket(websocket: WebSocket):
    """Handle Twilio ConversationRelay websocket connections."""
    await websocket.accept()

    call_sid: Optional[str] = None

    try:
        while True:
            payload = await websocket.receive_text()
            message = json.loads(payload)
            message_type = message.get("type")

            if message_type == "setup":
                call_sid = message.get("callSid")
                if not call_sid:
                    logger.error("ConversationRelay setup message missing callSid")
                    continue

                sarah = active_calls.get(call_sid)
                if sarah:
                    logger.info("ConversationRelay setup for existing call %s", call_sid)
                else:
                    logger.info("ConversationRelay setup for new call %s", call_sid)
                    sarah = SarahPersona(
                        api_key=settings.openai_api_key,
                        model=settings.openai_model,
                    )
                    active_calls[call_sid] = sarah

            elif message_type == "prompt":
                call_sid = message.get("callSid") or call_sid
                if not call_sid:
                    logger.error("Received ConversationRelay prompt without callSid")
                    continue

                sarah = active_calls.get(call_sid)
                if not sarah:
                    logger.warning(
                        "No active Sarah persona for call %s; creating a new session", call_sid
                    )
                    sarah = SarahPersona(
                        api_key=settings.openai_api_key,
                        model=settings.openai_model,
                    )
                    active_calls[call_sid] = sarah

                user_text = (message.get("voicePrompt") or "").strip()
                if not user_text:
                    logger.info("Empty prompt received for call %s; ignoring", call_sid)
                    continue

                logger.info("ConversationRelay prompt for %s: %s", call_sid, user_text)

                sarah_response = sarah.respond(user_text)
                logger.info("Sarah response for %s: %s", call_sid, sarah_response)

                reply = {
                    "type": "text",
                    "token": sarah_response,
                    "last": True,
                }

                await websocket.send_text(json.dumps(reply))

                if twilio_handler.should_end_call(user_text):
                    logger.info("Detected end of call intent for %s", call_sid)

            elif message_type == "interrupt":
                call_sid = message.get("callSid") or call_sid
                logger.info(
                    "ConversationRelay interrupt for %s: %s",
                    call_sid,
                    message.get("reason"),
                )

            else:
                logger.debug("ConversationRelay received unhandled message: %s", message)

    except WebSocketDisconnect:
        logger.info("ConversationRelay websocket disconnected for call %s", call_sid)
    except Exception as e:
        logger.error(f"Error handling ConversationRelay websocket: {e}", exc_info=True)
    finally:
        if call_sid:
            await cleanup_call(call_sid)


@app.post("/voice/status")
async def handle_call_status(
    request: Request,
    CallSid: str = Form(...),
    CallStatus: str = Form(...)
):
    """
    Handle call status updates from Twilio.
    Called when call status changes (ringing, in-progress, completed, etc.)

    Args:
        request: FastAPI request object
        CallSid: Twilio call identifier
        CallStatus: Current call status

    Returns:
        Success response
    """
    logger.info(f"Call status update: {CallSid} - {CallStatus}")

    # If call completed or failed, cleanup
    if CallStatus in ["completed", "failed", "busy", "no-answer"]:
        await cleanup_call(CallSid)

    return {"status": "ok"}


async def cleanup_call(call_sid: str, sarah: Optional[SarahPersona] = None):
    """
    Cleanup call session and save transcript.

    Args:
        call_sid: Twilio call identifier
        sarah: Sarah persona instance
    """
    try:
        sarah_instance = sarah or active_calls.get(call_sid)
        if not sarah_instance:
            logger.debug("No Sarah persona found for cleanup of call %s", call_sid)
            return

        # Get conversation history
        conversation = sarah_instance.get_conversation_history()

        # Save transcript
        if conversation:
            filepath = storage.save_transcript(
                call_sid=call_sid,
                conversation_history=conversation,
                metadata={"persona": "Sarah Martinez, Operations Manager"}
            )
            logger.info(f"Transcript saved: {filepath}")

        # Remove from active calls
        if call_sid in active_calls:
            del active_calls[call_sid]

        logger.info(f"Call {call_sid} cleaned up")

    except Exception as e:
        logger.error(f"Error cleaning up call {call_sid}: {e}", exc_info=True)


@app.get("/transcripts")
async def list_transcripts(limit: int = 10):
    """
    List recent call transcripts.

    Args:
        limit: Maximum number of transcripts to return

    Returns:
        List of transcript metadata
    """
    try:
        transcripts = storage.list_transcripts(limit=limit)
        return {"transcripts": transcripts}
    except Exception as e:
        logger.error(f"Error listing transcripts: {e}", exc_info=True)
        return {"error": str(e)}, 500


@app.get("/transcripts/{call_sid}")
async def get_transcript(call_sid: str):
    """
    Get full transcript for a specific call.

    Args:
        call_sid: Twilio call identifier

    Returns:
        Full transcript data
    """
    try:
        transcript = storage.load_transcript(call_sid)
        if transcript:
            return transcript
        return {"error": "Transcript not found"}, 404
    except Exception as e:
        logger.error(f"Error loading transcript: {e}", exc_info=True)
        return {"error": str(e)}, 500


@app.post("/coach/analyze/{call_sid}")
async def analyze_call(call_sid: str):
    """
    Analyze a call transcript and generate coaching feedback.

    Args:
        call_sid: Twilio call identifier

    Returns:
        Coaching feedback and scores
    """
    try:
        # Load transcript
        transcript = storage.load_transcript(call_sid)
        if not transcript:
            return {"error": "Transcript not found"}, 404

        logger.info(f"Analyzing call {call_sid} with coach...")

        # Analyze with coach
        conversation = transcript.get("conversation", [])
        metadata = transcript.get("metadata", {})

        feedback = coach.analyze_call(conversation, metadata)

        # Save feedback
        feedback_path = storage.save_feedback(call_sid, feedback)
        logger.info(f"Feedback saved: {feedback_path}")

        return {
            "call_sid": call_sid,
            "analysis": feedback,
            "message": "Analysis complete"
        }

    except Exception as e:
        logger.error(f"Error analyzing call: {e}", exc_info=True)
        return {"error": str(e)}, 500


@app.get("/coach/feedback/{call_sid}")
async def get_feedback(call_sid: str):
    """
    Get saved coaching feedback for a call.

    Args:
        call_sid: Twilio call identifier

    Returns:
        Saved coaching feedback
    """
    try:
        feedback = storage.load_feedback(call_sid)
        if feedback:
            return feedback
        return {"error": "Feedback not found. Have you analyzed this call yet?"}, 404
    except Exception as e:
        logger.error(f"Error loading feedback: {e}", exc_info=True)
        return {"error": str(e)}, 500


@app.get("/coach/summary/{call_sid}")
async def get_call_summary(call_sid: str):
    """
    Get a quick summary of a call.

    Args:
        call_sid: Twilio call identifier

    Returns:
        Brief summary of the call
    """
    try:
        # Load transcript
        transcript = storage.load_transcript(call_sid)
        if not transcript:
            return {"error": "Transcript not found"}, 404

        conversation = transcript.get("conversation", [])
        summary = coach.quick_summary(conversation)

        return {
            "call_sid": call_sid,
            "summary": summary
        }

    except Exception as e:
        logger.error(f"Error generating summary: {e}", exc_info=True)
        return {"error": str(e)}, 500


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=True,  # Enable auto-reload during development
        log_level="info"
    )
