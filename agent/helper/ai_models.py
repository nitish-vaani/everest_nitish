"""
AI model configuration and initialization.
Handles LLM, TTS, and other AI model setup.
"""

import os
from typing import Dict, Any
from dataclasses import dataclass
from livekit.plugins import elevenlabs, deepgram, openai, cartesia, aws, silero
from .config_manager import config_manager
from .logging_config import get_logger

logger = get_logger(__name__)

def get_openai_llm():
    """Get properly configured OpenAI LLM"""
    api_key = config_manager.get_openai_api_key()
    
    try:
        
        if api_key.startswith("sk-proj-"):
            logger.info("Using project-specific OpenAI API key")
        
        llm_instance = openai.LLM(
            # model="gpt-3.5-turbo",  
            model="gpt-4o",  
            api_key=api_key
        )
        
        logger.info("Successfully created OpenAI LLM instance")
        return llm_instance
        
    except Exception as e:
        logger.error(f"Failed to create OpenAI LLM: {e}")
        raise

def get_tts(config: Dict[str, Any]):
    """Get configured TTS instance based on config"""
    which_tts = config["TTS"]

    if which_tts == "cartesia":
        language = "hi"
        david = "da69d796-4603-4419-8a95-293bfc5679eb"
        female_indian = "56e35e2d-6eb6-4226-ab8b-9776515a7094"
        return cartesia.TTS(
            model="sonic-2-2025-03-07",
            voice=female_indian,
            speed=0,
            language="hi",
            emotion=["positivity:highest", "curiosity:highest"],
        )
    
    if which_tts == "aws":
        return aws.TTS()

    if which_tts == "elevenlabs":
        @dataclass
        class VoiceSettings:
            stability: float
            similarity_boost: float
            style: float | None = None
            speed: float | None = 1.0
            use_speaker_boost: bool | None = False

        voice_setting = VoiceSettings(
            stability=0.5,
            speed=1.05,
            similarity_boost=0.6,
            style=0.0,
            use_speaker_boost=True,
        )
        eric_voice_id = "9T9vSqRrPPxIs5wpyZfK"  
        return elevenlabs.TTS(
            model="eleven_flash_v2_5", 
            voice_settings=voice_setting, 
            voice_id=eric_voice_id
        )
    
    if which_tts == "deepgram":
        return deepgram.TTS()

def get_stt_instance():
    """Get configured STT instance"""
    from ..prompts.boosted_keywords import keywords_to_boost
    
    return deepgram.STT(
        model="nova-3",  
        language="multi", 
        # keyterms=keywords_to_boost
    )

def get_vad_instance():
    """Get configured VAD instance"""
    return silero.VAD.load()