"""
Voice Interface Module

Foundations for voice-first interaction with WebRTC prep,
voice activity detection, and transcript processing.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
from datetime import datetime
import asyncio


class VoiceState(Enum):
    """State of the voice session."""
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    ERROR = "error"


class CommandType(Enum):
    """Types of voice commands."""
    NAVIGATION = "navigation"
    QUERY = "query"
    ACTION = "action"
    INTERRUPT = "interrupt"
    CONFIRMATION = "confirmation"


@dataclass
class VoiceCommand:
    """A parsed voice command."""
    text: str
    command_type: CommandType
    intent: Optional[str] = None
    slots: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'text': self.text,
            'type': self.command_type.value,
            'intent': self.intent,
            'slots': self.slots,
            'confidence': self.confidence,
        }


@dataclass
class TranscriptSegment:
    """A segment of transcribed speech."""
    text: str
    start_time: float
    end_time: float
    is_final: bool = False
    speaker: str = "user"
    
    @property
    def duration(self) -> float:
        return self.end_time - self.start_time


@dataclass
class AudioConfig:
    """Configuration for audio processing."""
    sample_rate: int = 16000
    channels: int = 1
    chunk_duration_ms: int = 100
    vad_threshold: float = 0.5
    silence_duration_ms: int = 1000
    max_recording_seconds: int = 30


class VoiceActivityDetector:
    """Simple voice activity detection.
    
    In production, replace with WebRTC VAD or Silero VAD.
    """
    
    def __init__(self, threshold: float = 0.5, silence_ms: int = 1000):
        self.threshold = threshold
        self.silence_ms = silence_ms
        self.is_speaking = False
        self.silence_start: Optional[float] = None
    
    def process_audio_chunk(self, audio_level: float, timestamp: float) -> Dict[str, Any]:
        """Process an audio chunk and detect voice activity."""
        was_speaking = self.is_speaking
        
        if audio_level > self.threshold:
            self.is_speaking = True
            self.silence_start = None
            event = "speech_start" if not was_speaking else "speech_continue"
        else:
            if self.is_speaking:
                if self.silence_start is None:
                    self.silence_start = timestamp
                    event = "silence_start"
                elif (timestamp - self.silence_start) * 1000 > self.silence_ms:
                    self.is_speaking = False
                    event = "speech_end"
                else:
                    event = "silence"
            else:
                event = "silence"
        
        return {
            'event': event,
            'is_speaking': self.is_speaking,
            'audio_level': audio_level,
            'timestamp': timestamp,
        }
    
    def reset(self):
        """Reset the detector state."""
        self.is_speaking = False
        self.silence_start = None


class TranscriptProcessor:
    """Processes transcript segments into commands."""
    
    # Command patterns for routing
    NAVIGATION_PATTERNS = [
        "go to", "show me", "open", "navigate to", "switch to"
    ]
    
    ACTION_PATTERNS = [
        "create", "add", "delete", "save", "submit", "calculate", "run"
    ]
    
    QUERY_PATTERNS = [
        "what is", "how much", "tell me", "explain", "show"
    ]
    
    INTERRUPT_PATTERNS = [
        "wait", "stop", "cancel", "never mind", "hold on"
    ]
    
    CONFIRMATION_PATTERNS = [
        "yes", "yeah", "confirm", "do it", "proceed", "no", "cancel"
    ]
    
    def __init__(self):
        self.transcript_buffer: List[TranscriptSegment] = []
        self.command_history: List[VoiceCommand] = []
    
    def add_segment(self, segment: TranscriptSegment):
        """Add a transcript segment to the buffer."""
        self.transcript_buffer.append(segment)
    
    def get_full_transcript(self) -> str:
        """Get the full buffered transcript."""
        return " ".join(s.text for s in self.transcript_buffer if s.is_final)
    
    def parse_command(self, text: str) -> VoiceCommand:
        """Parse text into a structured command."""
        text_lower = text.lower().strip()
        
        # Detect command type
        command_type = CommandType.QUERY  # default
        
        if any(p in text_lower for p in self.INTERRUPT_PATTERNS):
            command_type = CommandType.INTERRUPT
        elif any(p in text_lower for p in self.CONFIRMATION_PATTERNS):
            command_type = CommandType.CONFIRMATION
        elif any(p in text_lower for p in self.NAVIGATION_PATTERNS):
            command_type = CommandType.NAVIGATION
        elif any(p in text_lower for p in self.ACTION_PATTERNS):
            command_type = CommandType.ACTION
        
        # Extract intent and slots
        intent, slots = self._extract_intent_and_slots(text_lower)
        
        command = VoiceCommand(
            text=text,
            command_type=command_type,
            intent=intent,
            slots=slots,
            confidence=0.85,  # Mock confidence
        )
        
        self.command_history.append(command)
        return command
    
    def _extract_intent_and_slots(self, text: str) -> tuple:
        """Extract intent and slots from text."""
        intent = None
        slots = {}
        
        # Navigation intents
        if "zoning" in text:
            intent = "view_zoning"
        elif "scenario" in text or "stress test" in text:
            intent = "run_scenarios"
        elif "governance" in text or "voting" in text:
            intent = "view_governance"
        elif "knowledge" in text or "search" in text:
            intent = "search_documents"
        elif "pro forma" in text or "financial" in text:
            intent = "calculate_proforma"
        elif "deal" in text or "investor" in text:
            intent = "view_deal_room"
        
        # Extract address mentions
        if "on " in text:
            parts = text.split("on ")
            if len(parts) > 1:
                slots["address"] = parts[1].split(" for")[0].strip()
        
        # Extract numeric values
        import re
        numbers = re.findall(r'\$?([\d,]+(?:\.\d+)?)\s*(sqft|square feet|units?|percent|%)?', text)
        for value, unit in numbers:
            clean_value = float(value.replace(',', ''))
            if unit in ['sqft', 'square feet']:
                slots["square_feet"] = clean_value
            elif unit in ['unit', 'units']:
                slots["units"] = int(clean_value)
            elif unit in ['percent', '%']:
                slots["percentage"] = clean_value
        
        return intent, slots
    
    def clear_buffer(self):
        """Clear the transcript buffer."""
        self.transcript_buffer = []


class VoiceCommandRouter:
    """Routes voice commands to appropriate handlers."""
    
    def __init__(self):
        self.handlers: Dict[str, Callable] = {}
        self.default_handler: Optional[Callable] = None
    
    def register_handler(self, intent: str, handler: Callable):
        """Register a handler for an intent."""
        self.handlers[intent] = handler
    
    def set_default_handler(self, handler: Callable):
        """Set the default handler for unrecognized intents."""
        self.default_handler = handler
    
    def route(self, command: VoiceCommand) -> Dict[str, Any]:
        """Route a command to its handler."""
        if command.intent and command.intent in self.handlers:
            handler = self.handlers[command.intent]
            return handler(command)
        elif self.default_handler:
            return self.default_handler(command)
        else:
            return {
                'status': 'unhandled',
                'message': f"No handler for intent: {command.intent}",
            }


class VoiceSession:
    """Manages a voice interaction session."""
    
    def __init__(self, config: Optional[AudioConfig] = None):
        self.config = config or AudioConfig()
        self.state = VoiceState.IDLE
        self.vad = VoiceActivityDetector(
            threshold=self.config.vad_threshold,
            silence_ms=self.config.silence_duration_ms
        )
        self.processor = TranscriptProcessor()
        self.router = VoiceCommandRouter()
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.created_at = datetime.now()
    
    def start_listening(self):
        """Start listening for voice input."""
        self.state = VoiceState.LISTENING
        self.vad.reset()
        self.processor.clear_buffer()
    
    def stop_listening(self):
        """Stop listening."""
        self.state = VoiceState.IDLE
    
    def process_transcript(self, text: str, is_final: bool = True) -> Optional[VoiceCommand]:
        """Process a transcript and potentially execute a command."""
        segment = TranscriptSegment(
            text=text,
            start_time=0,
            end_time=0,
            is_final=is_final
        )
        self.processor.add_segment(segment)
        
        if is_final and text.strip():
            self.state = VoiceState.PROCESSING
            command = self.processor.parse_command(text)
            return command
        
        return None
    
    def execute_command(self, command: VoiceCommand) -> Dict[str, Any]:
        """Execute a voice command."""
        result = self.router.route(command)
        self.state = VoiceState.IDLE
        return result
    
    def interrupt(self):
        """Handle an interrupt (barge-in)."""
        if self.state == VoiceState.SPEAKING:
            self.state = VoiceState.LISTENING
            return {'status': 'interrupted', 'message': 'Speech interrupted'}
        return {'status': 'no_op'}
    
    def get_state(self) -> Dict[str, Any]:
        """Get current session state."""
        return {
            'session_id': self.session_id,
            'state': self.state.value,
            'transcript': self.processor.get_full_transcript(),
            'command_count': len(self.processor.command_history),
        }


def get_voice_session(config: Optional[AudioConfig] = None) -> VoiceSession:
    """Factory function for voice session."""
    return VoiceSession(config)
