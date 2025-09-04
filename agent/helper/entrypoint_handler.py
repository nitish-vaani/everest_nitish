"""
Main entrypoint handler for the Mysyara agent.
Contains all the orchestration logic moved from the main file.
"""

import asyncio
import json
import os
from datetime import datetime
from typing import Any

from livekit import rtc
from livekit.agents import JobContext
from utils.hungup_idle_call import idle_call_watcher

from .config_manager import config_manager
from .logging_config import setup_logging, get_logger
from .call_handlers import CallState, handle_outbound_sip_call, handle_inbound_call, get_disconnect_reason
from .database_helpers import insert_call_end_async
from .session_helpers import (create_agent_session, setup_background_audio, 
                             setup_audio_recording, get_room_input_options)
from .transcript_manager import transcript_manager
# from .agent_class import create_mysyara_agent, MysyaraAgent
from .everest_fleet import create_agent, GreeterAgent

# Import data entities
from .data_entities import UserData

# Initialize logging
logger, transcript_logger = setup_logging()

# Constants
OUTBOUND_AGENT_NAME = "Mysyara Outbound Agent"
INBOUND_AGENT_NAME = "Mysyara Inbound Agent"
CALLING_NUMBER = 00000000000

# Load configuration
config = config_manager.config

async def setup_event_handlers(ctx: JobContext, call_state: CallState, agent, task_refs: dict):
    """Setup event handlers with cleaner logging"""
    
    async def record_call_end_once(end_reason: str):
        """Ensure call end is only recorded once"""
        if not call_state.call_end_recorded and call_state.call_started:
            await agent.record_call_end(end_reason)

    @ctx.room.on("participant_disconnected") 
    def on_participant_disconnected(participant_obj: rtc.RemoteParticipant):
        if participant_obj.identity == call_state.participant_identity:
            if participant_obj.disconnect_reason != rtc.DisconnectReason.CLIENT_INITIATED:
                logger.info(f"Participant disconnected: {participant_obj.disconnect_reason}")
            
            if task_refs["idle_watcher"] and not task_refs["idle_watcher"].done():
                task_refs["idle_watcher"].cancel()
            
            disconnect_reason = get_disconnect_reason(participant_obj, call_state)
            asyncio.create_task(record_call_end_once(disconnect_reason))

    @ctx.room.on("disconnected")
    def on_room_disconnected():
        logger.info("Room disconnected")
        if task_refs["idle_watcher"] and not task_refs["idle_watcher"].done():
            task_refs["idle_watcher"].cancel()
        asyncio.create_task(record_call_end_once("Room disconnected"))

async def setup_cleanup_callback(ctx: JobContext, call_state: CallState, task_refs: dict):
    """Setup cleanup callback for shutdown"""
    async def cleanup_on_shutdown():
        logger.info("Cleanup on shutdown triggered")
        
        # Cancel idle watcher task first
        if task_refs["idle_watcher"] and not task_refs["idle_watcher"].done():
            logger.info("Cancelling idle call watcher")
            task_refs["idle_watcher"].cancel()
            try:
                await task_refs["idle_watcher"]
            except asyncio.CancelledError:
                logger.debug("Idle watcher cancelled successfully")
            except Exception as e:
                logger.warning(f"Error cancelling idle watcher: {e}")
        
        if call_state.call_started and not call_state.call_end_recorded:
            logger.info("Recording call end during shutdown")
            try:
                call_state.call_end_recorded = True
                operation_id = await insert_call_end_async(
                    call_state.room_name,
                    "System shutdown"
                )
                logger.info(f"Queued shutdown call end: {operation_id}")
            except Exception as e:
                logger.error(f"Failed to queue call end during shutdown: {e}")

    ctx.add_shutdown_callback(cleanup_on_shutdown)

async def handle_sip_mode(ctx: JobContext, dial_info: dict, agent_name: str, call_state: CallState, 
                         required_fields: list = None) -> rtc.RemoteParticipant:
    """Handle SIP mode calls (both inbound and outbound)"""
    if required_fields:  # Outbound call
        phone_number = dial_info["phone"]
        participant_identity = phone_number
        call_state.participant_identity = participant_identity
        
        participant = await handle_outbound_sip_call(
            ctx, phone_number, participant_identity, 
            dial_info, agent_name, call_state
        )
        
        if not participant:  # Call failed
            return None
    else:  # Inbound call
        participant = await handle_inbound_call(ctx, agent_name, call_state)
    
    return participant

async def handle_console_mode(call_state: CallState):
    """Handle console mode for testing"""
    call_state.call_started = True
    call_state.start_time = datetime.now()

async def parse_job_metadata(ctx: JobContext):
    """Parse and validate job metadata with cleaner logging"""
    try:
        # Only log once at debug level
        logger.debug(f"Processing job metadata: {ctx.job.metadata}")
        
        if ctx.job.metadata is None or ctx.job.metadata == "":
            logger.info("Handling inbound call (no metadata)")
            return {
                "dial_info": {"phone": "unknown"}, 
                "required_fields": None,
                "agent_name": INBOUND_AGENT_NAME,
                "metadata": {}
            }
        else:
            metadata = json.loads(ctx.job.metadata)
            
            # Check if this is an inbound call with metadata
            if metadata.get("call_type") == "inbound" or metadata.get("direction") == "inbound":
                logger.info("Handling inbound call with metadata")
                caller_phone = metadata.get("phone", "unknown")
                return {
                    "dial_info": {"phone": caller_phone},
                    "required_fields": None,
                    "agent_name": INBOUND_AGENT_NAME,
                    "metadata": metadata
                }
            else:
                # Outbound call - only log essential info
                phone = metadata.get("phone", "unknown")
                name = metadata.get("name", "unknown")
                logger.info(f"Handling outbound call to {phone} ({name})")
                
                dial_info = metadata
                required_fields = ["phone"]
                
                missing_fields = [field for field in required_fields if field not in dial_info]
                if missing_fields:
                    raise ValueError(f"Missing required fields: {missing_fields}")
                    
                return {
                    "dial_info": dial_info,
                    "required_fields": required_fields,
                    "agent_name": OUTBOUND_AGENT_NAME,
                    "metadata": dial_info
                }
                
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in job metadata: {e}")
        raise ValueError(f"Invalid JSON in job metadata: {e}")
    except Exception as e:
        logger.error(f"Error processing job metadata: {e}")
        raise

async def handle_entrypoint(ctx: JobContext):
    """Handle the main entrypoint logic with cleaner logging"""
    await ctx.connect()
    
    call_state = CallState()
    call_state.room_name = ctx.room.name
    
    task_refs = {"idle_watcher": None}


    job_data = await parse_job_metadata(ctx)
    required_fields = job_data["required_fields"]
    agent_name = job_data["agent_name"]
    metadata = job_data["metadata"]
    dial_info = job_data["dial_info"]
    
    
    logger.info(f"Job initialized: {agent_name}, Phone: {metadata.get('phone', 'unknown')}")
    
    dial_info["phone"] = metadata["phone"]
    dial_info["name"] = metadata["name"]


    userdata = UserData(ctx=ctx)
    session = create_agent_session(userdata, config)

    
    prompt_path = os.path.join(os.path.dirname(__file__), "..", "prompts", "mysyara.yaml")
    agent = create_agent(
        dial_info=dial_info,
        call_state=call_state
    )

    await setup_event_handlers(ctx, call_state, agent, task_refs)
    await setup_cleanup_callback(ctx, call_state, task_refs)


    if config["store_transcription"]['switch']:
        finish_queue = transcript_manager.setup_transcript_persistence(
            session, ctx.room.name, config
        )
        if finish_queue:
            ctx.add_shutdown_callback(finish_queue)


    if config["mode"] == "SIP":
        participant = await handle_sip_mode(ctx, dial_info, agent_name, call_state, required_fields)
        if not participant and required_fields:  # Outbound call failed
            return

  
        room_input_options = get_room_input_options(config["mode"])
        await session.start(
            agent=agent,
            room=ctx.room,
            room_input_options=room_input_options,
        )
        
        if participant:
            agent.set_participant(participant)
            logger.info("Session started successfully")

    elif config["mode"] == 'CONSOLE':
        # Console mode for testing
        await handle_console_mode(call_state)
        room_input_options = get_room_input_options(config["mode"])
        await session.start(
            room=ctx.room,
            agent=agent,
            room_input_options=room_input_options,
        )
        logger.info("Console session started")
    
    # Setup background audio if enabled
    userdata.bg_player = await setup_background_audio(config, ctx.room, session)

    # Setup audio recording if enabled
    await setup_audio_recording(config, ctx.room.name)

    # Setup idle call monitoring if enabled - AFTER session is started
    if config.get("idle_call_hungup", False):
        task_refs["idle_watcher"] = asyncio.create_task(idle_call_watcher(session, config["idle_call_watcher_msg"]))
        logger.debug("Idle call watcher started")

    # Setup conversation tracking
    conversation_handler = transcript_manager.create_conversation_handler()
    session.on("conversation_item_added", conversation_handler)


