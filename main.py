"""
Main FastAPI application for the voice sales training system.
Handles Twilio webhooks for incoming calls and voice interactions.
"""
from fastapi import FastAPI, Form, Request, Response
from fastapi.responses import PlainTextResponse
import logging
from typing import Optional, Dict

from config import get_settings
from agents.persona import SarahPersona
from agents.coach import SalesCoach
from services.twilio_handler import TwilioVoiceHandler
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
twilio_handler = TwilioVoiceHandler(base_url=settings.base_url)
storage = TranscriptStorage(storage_dir=settings.transcripts_dir)
coach = SalesCoach(api_key=settings.anthropic_api_key, model=settings.claude_model)

# Store active call sessions (in production, use Redis or database)
# Key: call_sid, Value: SarahPersona instance
active_calls: Dict[str, SarahPersona] = {}


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
        # Create new Sarah persona for this call. Prefer OpenRouter key if provided.
        api_key_to_use = settings.openrouter_api_key or settings.anthropic_api_key
        use_openrouter = bool(settings.openrouter_api_key)

        sarah = SarahPersona(
            api_key=api_key_to_use,
            model=settings.claude_model,
            use_openrouter=use_openrouter
        )

        # Store in active calls
        active_calls[CallSid] = sarah

        # Get Sarah's greeting
        greeting = sarah.get_greeting()
        logger.info(f"Sarah greeting: {greeting}")

        # Generate TwiML response
        twiml = twilio_handler.create_greeting_response(greeting)

        return PlainTextResponse(content=twiml, media_type="application/xml")

    except Exception as e:
        logger.error(f"Error handling incoming call: {e}", exc_info=True)
        twiml = twilio_handler.create_error_response()
        return PlainTextResponse(content=twiml, media_type="application/xml")


@app.post("/voice/respond", response_class=PlainTextResponse)
async def handle_voice_response(
    request: Request,
    CallSid: str = Form(...),
    SpeechResult: Optional[str] = Form(None),
    Confidence: Optional[float] = Form(None)
):
    """
    Handle user's voice input and generate Sarah's response.
    This is called after Twilio captures the user's speech.

    Args:
        request: FastAPI request object
        CallSid: Twilio call identifier
        SpeechResult: User's speech transcribed to text
        Confidence: Confidence score of speech recognition (0.0-1.0)

    Returns:
        TwiML response with Sarah's reply
    """
    logger.info(f"Voice response for call {CallSid}: '{SpeechResult}' (confidence: {Confidence})")

    try:
        # Get Sarah persona for this call
        sarah = active_calls.get(CallSid)

        if not sarah:
            logger.error(f"No active call found for {CallSid}")
            twiml = twilio_handler.create_error_response(
                "I'm sorry, there was an error with your call. Please call back."
            )
            return PlainTextResponse(content=twiml, media_type="application/xml")

        # Handle case where no speech was detected
        if not SpeechResult:
            logger.warning(f"No speech detected for call {CallSid}")
            twiml = twilio_handler.create_conversation_response(
                "I didn't catch that. Could you repeat?",
                is_final=False
            )
            return PlainTextResponse(content=twiml, media_type="application/xml")

        # Check if confidence is too low (optional threshold)
        if Confidence is not None and Confidence < 0.5:
            logger.warning(f"Low confidence ({Confidence}) for call {CallSid}")
            # Still process it, but could add special handling

        # Get Sarah's response
        sarah_response = sarah.respond(SpeechResult)
        logger.info(f"Sarah response: {sarah_response}")

        # Check if call should end
        should_end = twilio_handler.should_end_call(SpeechResult)

        # Generate TwiML response
        twiml = twilio_handler.create_conversation_response(
            sarah_response,
            is_final=should_end
        )

        # If call is ending, save transcript and cleanup
        if should_end:
            await cleanup_call(CallSid, sarah)

        return PlainTextResponse(content=twiml, media_type="application/xml")

    except Exception as e:
        logger.error(f"Error handling voice response: {e}", exc_info=True)
        twiml = twilio_handler.create_error_response()

        # Cleanup call on error
        if CallSid in active_calls:
            await cleanup_call(CallSid, active_calls[CallSid])

        return PlainTextResponse(content=twiml, media_type="application/xml")


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
        sarah = active_calls.get(CallSid)
        if sarah:
            await cleanup_call(CallSid, sarah)

    return {"status": "ok"}


async def cleanup_call(call_sid: str, sarah: SarahPersona):
    """
    Cleanup call session and save transcript.

    Args:
        call_sid: Twilio call identifier
        sarah: Sarah persona instance
    """
    try:
        # Get conversation history
        conversation = sarah.get_conversation_history()

        # Save transcript
        if conversation:
            filepath = storage.save_transcript(
                call_sid=call_sid,
                conversation_history=conversation,
                metadata={"persona": "Sarah Chen, VP of Operations"}
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
