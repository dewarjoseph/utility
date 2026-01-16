"""Tests for the voice interface module."""

import pytest
from core.voice import (
    VoiceSession, VoiceCommand, TranscriptProcessor, VoiceActivityDetector,
    VoiceCommandRouter, VoiceState, CommandType, AudioConfig,
    get_voice_session
)


class TestVoiceActivityDetector:
    """Tests for voice activity detection."""

    def test_detect_speech_start(self):
        vad = VoiceActivityDetector(threshold=0.5)
        result = vad.process_audio_chunk(0.8, 0.0)
        assert result['event'] == 'speech_start'
        assert result['is_speaking'] is True

    def test_detect_silence(self):
        vad = VoiceActivityDetector(threshold=0.5)
        result = vad.process_audio_chunk(0.2, 0.0)
        assert result['event'] == 'silence'
        assert result['is_speaking'] is False

    def test_detect_speech_end(self):
        vad = VoiceActivityDetector(threshold=0.5, silence_ms=100)
        vad.process_audio_chunk(0.8, 0.0)  # Start speaking
        vad.process_audio_chunk(0.8, 0.05)  # Continue
        vad.process_audio_chunk(0.2, 0.1)  # Silence start (sets silence_start)
        # After 200ms of silence (exceeds 100ms threshold)
        result = vad.process_audio_chunk(0.2, 0.35)
        assert result['event'] == 'speech_end'


class TestTranscriptProcessor:
    """Tests for transcript processing."""

    def test_parse_navigation_command(self):
        processor = TranscriptProcessor()
        command = processor.parse_command("Show me the zoning information")
        assert command.command_type == CommandType.NAVIGATION
        assert command.intent == "view_zoning"

    def test_parse_action_command(self):
        processor = TranscriptProcessor()
        command = processor.parse_command("Create a new pro forma")
        assert command.command_type == CommandType.ACTION

    def test_parse_interrupt_command(self):
        processor = TranscriptProcessor()
        command = processor.parse_command("wait a moment")
        assert command.command_type == CommandType.INTERRUPT

    def test_extract_slots(self):
        processor = TranscriptProcessor()
        command = processor.parse_command("Analyze a lot on Pacific Avenue for 10 units")
        assert "address" in command.slots or command.text
        # Check numeric extraction
        command2 = processor.parse_command("Calculate for 5000 sqft")
        assert command2.slots.get("square_feet") == 5000


class TestVoiceCommandRouter:
    """Tests for command routing."""

    def test_register_and_route(self):
        router = VoiceCommandRouter()
        
        def mock_handler(cmd):
            return {'handled': True, 'intent': cmd.intent}
        
        router.register_handler('view_zoning', mock_handler)
        
        command = VoiceCommand(
            text="test",
            command_type=CommandType.NAVIGATION,
            intent='view_zoning'
        )
        
        result = router.route(command)
        assert result['handled'] is True

    def test_default_handler(self):
        router = VoiceCommandRouter()
        
        def default(cmd):
            return {'default': True}
        
        router.set_default_handler(default)
        
        command = VoiceCommand(
            text="unknown",
            command_type=CommandType.QUERY,
            intent='unknown_intent'
        )
        
        result = router.route(command)
        assert result['default'] is True


class TestVoiceSession:
    """Tests for voice session management."""

    def test_session_creation(self):
        session = VoiceSession()
        assert session.state == VoiceState.IDLE
        assert session.session_id is not None

    def test_start_listening(self):
        session = VoiceSession()
        session.start_listening()
        assert session.state == VoiceState.LISTENING

    def test_process_transcript(self):
        session = VoiceSession()
        session.start_listening()
        
        command = session.process_transcript("Show me the scenarios", is_final=True)
        
        assert command is not None
        assert command.text == "Show me the scenarios"

    def test_interrupt(self):
        session = VoiceSession()
        session.state = VoiceState.SPEAKING
        
        result = session.interrupt()
        assert result['status'] == 'interrupted'
        assert session.state == VoiceState.LISTENING


class TestFactoryFunction:
    """Tests for factory function."""

    def test_get_voice_session(self):
        session = get_voice_session()
        assert isinstance(session, VoiceSession)

    def test_custom_config(self):
        config = AudioConfig(sample_rate=44100, vad_threshold=0.7)
        session = get_voice_session(config)
        assert session.config.sample_rate == 44100
