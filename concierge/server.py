"""FastAPI server for handling Twilio Media Streams and OpenAI Realtime API and agent orchestration."""

import logging
import os
from contextlib import asynccontextmanager, suppress
from concierge.config import setup_logging
import uuid
import uvicorn
from agents import Agent, Runner, SQLiteSession
from fastapi import (
    FastAPI,
    WebSocket,
    WebSocketDisconnect,
    Response,
    Query,
    Request,
    Depends,
)
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from concierge.agents import (
    OrchestratorAgent,
    ReservationAgent,
    format_reservation_result,
)
from concierge.agents.cancellation_agent import CancellationAgent
from concierge.agents.search_agent import SearchAgent
from concierge.agents.tools import (
    find_restaurant,
    search_restaurants_llm,
    lookup_reservation_from_history,
    initiate_cancellation_call,
)
from concierge.config import get_config
from concierge.guardrails import (
    input_validation_guardrail,
    party_size_guardrail,
    output_validation_guardrail,
    rate_limit_guardrail,
)
from concierge.services.call_manager import get_call_manager

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Application lifespan manager."""
    config = get_config()
    logger.info(
        f"Starting AI Concierge Voice Server on {config.server_host}:{config.server_port}"
    )
    logger.info(f"Public domain: {config.public_domain or 'NOT CONFIGURED'}")

    # Ensure OpenAI API key is available to the SDK via environment variable
    if config.openai_api_key and "OPENAI_API_KEY" not in os.environ:
        os.environ["OPENAI_API_KEY"] = config.openai_api_key
        logger.info("✓ OpenAI API key loaded into environment")

    # Initialize agents
    logger.info("Initializing AI agents...")

    # Tier 2: Specialized Agents

    # 1. Reservation Agent (handles reservation logic + voice calls)
    reservation_agent_instance = ReservationAgent(find_restaurant)
    reservation_agent = reservation_agent_instance.create()
    logger.info("✓ Reservation Agent initialized")

    # 2. Cancellation Agent (handles cancellations + voice calls)
    cancellation_agent_instance = CancellationAgent(
        lookup_reservation_from_history, initiate_cancellation_call
    )
    cancellation_agent = cancellation_agent_instance.create()
    logger.info("✓ Cancellation Agent initialized")

    # 3. Search Agent (LLM-powered restaurant search)
    search_agent_instance = SearchAgent(search_restaurants_llm)
    search_agent = search_agent_instance.create()
    logger.info("✓ Search Agent initialized")

    # Tier 1: Orchestrator (routes requests to specialized agents)
    orchestrator_instance = OrchestratorAgent(
        reservation_agent=reservation_agent,
        cancellation_agent=cancellation_agent,
        search_agent=search_agent,
    )
    orchestrator_agent = orchestrator_instance.create()

    # Add guardrails to the orchestrator
    orchestrator_agent.guardrails = [
        rate_limit_guardrail,  # Rate limiting (5/hour, 20/day)
        input_validation_guardrail,  # Input validation
        party_size_guardrail,  # Party size validation
        output_validation_guardrail,  # Output validation
    ]

    # Store agent in app state for dependency injection
    _app.state.orchestrator_agent = orchestrator_agent

    yield

    logger.info("Shutting down AI Concierge Voice Server")


app = FastAPI(
    title="AI Concierge API",
    description="API for AI Concierge",
    version="0.1.0",
    lifespan=lifespan,
)

# Add CORS middleware to allow WebSocket connections from browsers
# This is needed for testing with test_websocket.html and for Twilio webhooks
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development/testing
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_orchestrator_agent(request: Request) -> Agent:
    """Dependency to get the orchestrator agent from app state.

    Args:
        request: FastAPI request object

    Returns:
        The orchestrator agent instance

    Raises:
        HTTPException: If agent is not initialized
    """
    agent = getattr(request.app.state, "orchestrator_agent", None)
    if agent is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=503, detail="Agents not initialized yet")
    return agent


@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    return {"status": "healthy", "service": "ai-concierge-api"}


@app.post("/process-request")
async def process_request(
    request: Request,
    orchestrator_agent: Agent = Depends(get_orchestrator_agent),
):
    """Process a reservation request through the agent pipeline.

    This endpoint accepts user input text, runs it through the orchestrator
    and reservation agents, and returns the result.

    Request body:
        {
            "user_input": "Book a table at Demo Restaurant for 4 people tomorrow at 7pm",
            "session_id": "optional-session-id"  # Optional: for conversation memory
        }

    Returns:
        {
            "success": true,
            "message": "Reservation confirmed at Demo Restaurant...",
            "final_output": "...",
            "formatted_result": "...",
            "session_id": "session-123"  # Returned for client to reuse
        }
    """
    try:
        data = await request.json()
        user_input = data.get("user_input")
        session_id = data.get("session_id")

        if not user_input:
            return JSONResponse(
                status_code=400,
                content={"error": "Missing user_input field"},
            )

        # Generate session_id if not provided (for conversation memory)
        if not session_id:
            session_id = f"session-{uuid.uuid4().hex[:12]}"
            logger.debug(f"Generated session: {session_id}")
        else:
            logger.debug(f"Using session: {session_id}")

        # Create session for conversation memory (SDK feature)
        session = SQLiteSession(session_id, "conversations.db")

        logger.info(f"Processing: {user_input[:80]}...")

        # Run the orchestrator using the SDK Runner (async version)
        # Pass session to enable conversation memory across turns
        runner = Runner()
        result = await runner.run(
            starting_agent=orchestrator_agent, input=user_input, session=session
        )

        # Extract the final output
        final_output = ""
        if hasattr(result, "final_output"):
            final_output = result.final_output
        else:
            final_output = str(result)

        # Format the result
        formatted_result = format_reservation_result(result)

        logger.info("Request processed successfully")

        return {
            "success": True,
            "message": "Request processed successfully",
            "final_output": final_output,
            "formatted_result": formatted_result,
            "session_id": session_id,  # Return session_id for client to reuse
        }

    except Exception as e:
        logger.exception("Error processing request")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(e),
                "message": f"Error processing request: {e}",
            },
        )


@app.post("/twiml")
async def generate_twiml(call_id: str = Query(..., description="Unique call ID")):
    """Generate TwiML to route Twilio call to Media Stream WebSocket.

    Args:
        call_id: Unique identifier for this call
        test_mode: If True, return simple test TwiML without WebSocket

    Returns:
        TwiML XML response
    """
    config = get_config()

    if not config.public_domain:
        logger.error("PUBLIC_DOMAIN not configured - cannot generate TwiML")
        return Response(
            content="Error: Server not configured",
            media_type="text/plain",
            status_code=500,
        )

    # Get reservation details from CallManager to pass as custom parameters
    call_manager = get_call_manager()
    call_state = call_manager.get_call(call_id)

    # Prepare custom parameters to send to WebSocket handler
    # These will be available in the 'start' event
    custom_params = {"call_id": call_id}  # Always include call_id
    if call_state:
        reservation_details = call_state.reservation_details
        custom_params.update(
            {
                "restaurant_name": reservation_details.get("restaurant_name", ""),
                "party_size": str(reservation_details.get("party_size", "")),
                "date": reservation_details.get("date", ""),
                "time": reservation_details.get("time", ""),
                "customer_name": reservation_details.get("customer_name", ""),
                "confirmation_number": reservation_details.get(
                    "confirmation_number", ""
                ),
                "call_type": reservation_details.get("call_type", "reservation"),
            }
        )

    # Build parameter string for TwiML
    " ".join([f'{k}="{v}"' for k, v in custom_params.items() if v])

    # Use wss:// for secure WebSocket connection
    websocket_url = f"wss://{config.public_domain}/media-stream"

    # TwiML with Stream parameters:
    # - track="inbound_track" is the only valid value for <Connect> verb
    # - Custom parameters are sent in the 'start' event to the WebSocket
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>Connecting you to our reservation system.</Say>
    <Connect>
        <Stream url="{websocket_url}" track="inbound_track">
            <Parameter name="call_id" value="{custom_params.get('call_id', '')}" />
            <Parameter name="restaurant_name" value="{custom_params.get('restaurant_name', '')}" />
            <Parameter name="party_size" value="{custom_params.get('party_size', '')}" />
            <Parameter name="date" value="{custom_params.get('date', '')}" />
            <Parameter name="time" value="{custom_params.get('time', '')}" />
            <Parameter name="customer_name" value="{custom_params.get('customer_name', '')}" />
            <Parameter name="confirmation_number" value="{custom_params.get('confirmation_number', '')}" />
            <Parameter name="call_type" value="{custom_params.get('call_type', 'reservation')}" />
        </Stream>
    </Connect>
</Response>"""

    logger.info(f"Generated TwiML for call {call_id}")
    return Response(content=twiml, media_type="text/xml")


@app.post("/twilio-status")
async def twilio_status_callback(request: Request):
    """Handle Twilio status callbacks for debugging.

    This endpoint receives updates about call status from Twilio.
    """
    # Get form data from POST request
    form_data = await request.form()
    data = dict(form_data)

    # Extract key fields
    call_sid = data.get("CallSid")
    call_status = data.get("CallStatus")
    error_code = data.get("ErrorCode")
    error_message = data.get("ErrorMessage")

    if call_sid and call_status:
        logger.debug(f"Call {call_sid}: {call_status}")

    if error_code:
        logger.error(f"Twilio error {error_code}: {error_message}")

    return Response(content="OK", media_type="text/plain")


@app.websocket("/media-stream")
async def handle_media_stream(websocket: WebSocket):
    """Handle Twilio Media Stream WebSocket connection.

    Based on the official OpenAI example:
    https://github.com/openai/openai-agents-python/tree/main/examples/realtime/twilio

    Reservation details are passed via Twilio custom parameters in the 'start' event.
    """
    logger.debug(f"WebSocket connection from {websocket.client}")

    try:
        # Import TwilioHandler
        from concierge.twilio_handler import TwilioHandler

        # Create handler - it will extract reservation details from 'start' event
        handler = TwilioHandler(websocket)

        # Start and wait for completion
        await handler.start()
        await handler.wait_until_done()

        logger.debug("Call completed")

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception:
        logger.exception("Error in media stream handler")
        with suppress(Exception):
            await websocket.close(code=1011, reason="Internal error")


def run_server():
    """Run the FastAPI server using uvicorn.

    This is the main entry point for the server.
    """

    # Setup logging
    setup_logging()

    # Get config
    config = get_config()

    # Ensure OpenAI API key is available to the SDK via environment variable
    # The SDK reads directly from os.environ, not from our Config
    import os

    if config.openai_api_key and "OPENAI_API_KEY" not in os.environ:
        os.environ["OPENAI_API_KEY"] = config.openai_api_key
        logger.info("✓ OpenAI API key loaded into environment")

    # Run server
    uvicorn.run(
        "concierge.server:app",
        host=config.server_host,
        port=config.server_port,
        log_level=config.log_level.lower(),
        reload=False,  # Set to True for development
    )


if __name__ == "__main__":
    run_server()
