"""
Chat Interface Module - Conversational Project Creation

Provides AI-powered conversational interface for natural language project creation
with intent classification and slot-filling state machine.
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any, List, Callable


class Intent(Enum):
    """User intent classifications."""
    CREATE_PROJECT = "create_project"
    ANALYZE_ZONING = "analyze_zoning"
    CALCULATE_PROFORMA = "calculate_proforma"
    GET_HELP = "get_help"
    UNKNOWN = "unknown"


class SlotStatus(Enum):
    """Status of slot-filling process."""
    EMPTY = "empty"
    PARTIAL = "partial"
    COMPLETE = "complete"


@dataclass
class Slot:
    """A single data slot that needs to be filled."""
    name: str
    description: str
    required: bool = True
    value: Any = None
    validator: Optional[Callable[[Any], bool]] = None
    prompt: str = ""
    
    @property
    def is_filled(self) -> bool:
        return self.value is not None
    
    def validate(self, value: Any) -> bool:
        """Validate a value for this slot."""
        if self.validator:
            return self.validator(value)
        return value is not None


@dataclass
class SlotSchema:
    """Schema defining the slots needed for a particular intent."""
    intent: Intent
    slots: Dict[str, Slot] = field(default_factory=dict)
    
    @property
    def status(self) -> SlotStatus:
        """Get overall status of slot filling."""
        filled = sum(1 for s in self.slots.values() if s.is_filled)
        required = sum(1 for s in self.slots.values() if s.required)
        required_filled = sum(1 for s in self.slots.values() if s.required and s.is_filled)
        
        if required_filled == required:
            return SlotStatus.COMPLETE
        elif filled > 0:
            return SlotStatus.PARTIAL
        return SlotStatus.EMPTY
    
    def get_next_empty_slot(self) -> Optional[Slot]:
        """Get the next required slot that needs filling."""
        for slot in self.slots.values():
            if slot.required and not slot.is_filled:
                return slot
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert filled slots to dictionary."""
        return {name: slot.value for name, slot in self.slots.items() if slot.is_filled}


class IntentClassifier:
    """Classifies user intent from natural language input."""
    
    # Keywords mapped to intents - ORDER MATTERS! More specific patterns first
    INTENT_PATTERNS = {
        Intent.ANALYZE_ZONING: [
            r'\b(zoning|zone|zoned)\b',
            r'\b(what can|allowed|permitted)\b.*\b(build|use)\b',
            r'\b(setback|height limit|coverage|FAR)\b',
        ],
        Intent.CALCULATE_PROFORMA: [
            r'\b(cost|price|budget|money|financial)\b',
            r'\b(pro ?forma|investment|return|ROI|yield)\b',
            r'\b(how much|estimate|calculate)\b.*\b(cost|worth|value)\b',
        ],
        Intent.CREATE_PROJECT: [
            r'\b(create|new|start|make|build)\b.*\b(project|analysis|scan)\b',
            r'\b(analyze|check|look at)\b.*\b(lot|property|land|site|parcel)\b',
            r'\b(want to|would like to)\b.*\b(develop|build|analyze)\b',
        ],
        Intent.GET_HELP: [
            r'^help\b',
            r'\b(getting started|tutorial|guide)\b',
            r'\bhow do I\b',
        ],
    }

    
    def classify(self, text: str) -> Intent:
        """Classify user intent from text."""
        text_lower = text.lower()
        
        for intent, patterns in self.INTENT_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text_lower, re.IGNORECASE):
                    return intent
        
        return Intent.UNKNOWN



class SlotExtractor:
    """Extracts slot values from natural language input."""
    
    # Patterns for extracting common slot values
    EXTRACTORS = {
        'address': [
            r'(\d+\s+\w+(?:\s+\w+)*(?:\s+(?:st|street|ave|avenue|rd|road|blvd|boulevard|dr|drive|ln|lane|ct|court|way|pl|place)))',
            r'((?:on|at)\s+(\w+(?:\s+\w+)*(?:\s+(?:st|street|ave|avenue|rd|road))))',
        ],
        'use_case': {
            'desalination_plant': [r'\b(desalination|desal|water treatment)\b'],
            'silicon_wafer_fab': [r'\b(silicon|wafer|fab|semiconductor|chip)\b'],
            'warehouse_distribution': [r'\b(warehouse|distribution|logistics|storage)\b'],
            'light_manufacturing': [r'\b(manufacturing|factory|industrial)\b'],
            'food_coop': [r'\b(food|grocery|coop|cooperative|co-op|community)\b'],
            'housing': [r'\b(housing|residential|apartments|homes|units)\b'],
        },
        'radius_km': [
            r'(\d+(?:\.\d+)?)\s*(?:km|kilometer)',
            r'(\d+(?:\.\d+)?)\s*(?:mile)',  # Convert to km
        ],
        'budget': [
            r'\$\s*(\d+(?:,\d{3})*(?:\.\d{2})?)\s*(?:k|K|m|M|million|thousand)?',
            r'(\d+(?:,\d{3})*)\s*(?:dollars?)',
        ],
    }
    
    def extract(self, text: str, slot_name: str) -> Optional[Any]:
        """Extract a slot value from text."""
        text_lower = text.lower()
        
        if slot_name == 'use_case':
            return self._extract_use_case(text_lower)
        elif slot_name == 'address':
            return self._extract_address(text)
        elif slot_name == 'radius_km':
            return self._extract_radius(text_lower)
        elif slot_name == 'budget':
            return self._extract_budget(text)
        elif slot_name == 'project_name':
            return self._extract_project_name(text)
        
        return None
    
    def _extract_use_case(self, text: str) -> Optional[str]:
        """Extract use case from text."""
        for use_case, patterns in self.EXTRACTORS['use_case'].items():
            for pattern in patterns:
                if re.search(pattern, text):
                    return use_case
        return None
    
    def _extract_address(self, text: str) -> Optional[str]:
        """Extract address from text."""
        for pattern in self.EXTRACTORS['address']:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None
    
    def _extract_radius(self, text: str) -> Optional[float]:
        """Extract radius in km from text."""
        for pattern in self.EXTRACTORS['radius_km']:
            match = re.search(pattern, text)
            if match:
                value = float(match.group(1))
                if 'mile' in text:
                    value *= 1.60934  # Convert miles to km
                return value
        return None
    
    def _extract_budget(self, text: str) -> Optional[float]:
        """Extract budget amount from text."""
        for pattern in self.EXTRACTORS['budget']:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                value = float(match.group(1).replace(',', ''))
                if 'm' in text.lower() or 'million' in text.lower():
                    value *= 1_000_000
                elif 'k' in text.lower() or 'thousand' in text.lower():
                    value *= 1_000
                return value
        return None
    
    def _extract_project_name(self, text: str) -> Optional[str]:
        """Extract or generate project name from text."""
        # Look for explicit name patterns
        patterns = [
            r'(?:called?|named?)\s+"([^"]+)"',
            r'(?:called?|named?)\s+(\w+(?:\s+\w+)?)',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        return None


def get_create_project_schema() -> SlotSchema:
    """Get the slot schema for project creation."""
    return SlotSchema(
        intent=Intent.CREATE_PROJECT,
        slots={
            'address': Slot(
                name='address',
                description='Location or address to analyze',
                required=True,
                prompt="What's the address or location you'd like to analyze?"
            ),
            'project_name': Slot(
                name='project_name',
                description='Name for this project',
                required=True,
                prompt="What would you like to name this project?"
            ),
            'use_case': Slot(
                name='use_case',
                description='Type of development or use case',
                required=False,
                prompt="What type of development are you considering? (e.g., housing, commercial, industrial)"
            ),
            'radius_km': Slot(
                name='radius_km',
                description='Analysis radius in kilometers',
                required=False,
                prompt="How large an area should we analyze? (default: 2 km radius)"
            ),
        }
    )


@dataclass
class ChatMessage:
    """A message in the chat conversation."""
    role: str  # 'user' or 'assistant'
    content: str
    component: Optional[str] = None  # GenUI component to render
    component_data: Optional[Dict[str, Any]] = None


class ChatSession:
    """Manages a conversational chat session with slot-filling."""
    
    def __init__(self):
        self.messages: List[ChatMessage] = []
        self.classifier = IntentClassifier()
        self.extractor = SlotExtractor()
        self.current_schema: Optional[SlotSchema] = None
        self.current_intent: Optional[Intent] = None
    
    def process_message(self, user_input: str) -> ChatMessage:
        """Process a user message and generate a response."""
        # Add user message to history
        self.messages.append(ChatMessage(role='user', content=user_input))
        
        # If we're in the middle of slot filling, try to extract values
        if self.current_schema and self.current_schema.status != SlotStatus.COMPLETE:
            return self._continue_slot_filling(user_input)
        
        # Otherwise, classify intent and start new flow
        intent = self.classifier.classify(user_input)
        self.current_intent = intent
        
        if intent == Intent.CREATE_PROJECT:
            return self._start_create_project(user_input)
        elif intent == Intent.ANALYZE_ZONING:
            return self._handle_zoning_query(user_input)
        elif intent == Intent.CALCULATE_PROFORMA:
            return self._handle_proforma_query(user_input)
        elif intent == Intent.GET_HELP:
            return self._handle_help()
        else:
            return self._handle_unknown()
    
    def _start_create_project(self, user_input: str) -> ChatMessage:
        """Start the project creation flow."""
        self.current_schema = get_create_project_schema()
        
        # Try to extract any values from the initial message
        for slot_name, slot in self.current_schema.slots.items():
            value = self.extractor.extract(user_input, slot_name)
            if value:
                slot.value = value
        
        # Check if we have everything we need
        if self.current_schema.status == SlotStatus.COMPLETE:
            return self._complete_project_creation()
        
        # Otherwise, ask for the next missing slot
        next_slot = self.current_schema.get_next_empty_slot()
        if next_slot:
            response = ChatMessage(
                role='assistant',
                content=f"Great! I'd love to help you create a new project. {next_slot.prompt}"
            )
            self.messages.append(response)
            return response
        
        return self._complete_project_creation()
    
    def _continue_slot_filling(self, user_input: str) -> ChatMessage:
        """Continue filling slots from user input."""
        # Try to extract value for the current empty slot
        next_slot = self.current_schema.get_next_empty_slot()
        if next_slot:
            value = self.extractor.extract(user_input, next_slot.name)
            if value:
                next_slot.value = value
            else:
                # Use the raw input as the value for simple slots
                if next_slot.name in ['project_name', 'address']:
                    next_slot.value = user_input.strip()
        
        # Check if complete
        if self.current_schema.status == SlotStatus.COMPLETE:
            return self._complete_project_creation()
        
        # Ask for next slot
        next_slot = self.current_schema.get_next_empty_slot()
        if next_slot:
            response = ChatMessage(
                role='assistant',
                content=next_slot.prompt
            )
            self.messages.append(response)
            return response
        
        return self._complete_project_creation()
    
    def _complete_project_creation(self) -> ChatMessage:
        """Complete the project creation with collected data."""
        data = self.current_schema.to_dict()
        
        response = ChatMessage(
            role='assistant',
            content=f"I've gathered everything I need to create your project:\n\n"
                   f"📍 **Location**: {data.get('address', 'Not specified')}\n"
                   f"📝 **Name**: {data.get('project_name', 'Untitled')}\n"
                   f"🏭 **Use Case**: {data.get('use_case', 'General')}\n"
                   f"📐 **Radius**: {data.get('radius_km', 2.0)} km\n\n"
                   f"Ready to create this project?",
            component='ProjectCreationCard',
            component_data=data
        )
        self.messages.append(response)
        
        # Reset for next interaction
        self.current_schema = None
        return response
    
    def _handle_zoning_query(self, user_input: str) -> ChatMessage:
        """Handle zoning-related queries."""
        address = self.extractor.extract(user_input, 'address')
        
        response = ChatMessage(
            role='assistant',
            content="I'll analyze the zoning for that location. Let me fetch the zoning data...",
            component='ZoningMapCard',
            component_data={'address': address}
        )
        self.messages.append(response)
        return response
    
    def _handle_proforma_query(self, user_input: str) -> ChatMessage:
        """Handle pro forma related queries."""
        response = ChatMessage(
            role='assistant',
            content="I can help you build a financial pro forma. Let me set up the analysis...",
            component='ProFormaWidget',
            component_data={}
        )
        self.messages.append(response)
        return response
    
    def _handle_help(self) -> ChatMessage:
        """Provide help information."""
        response = ChatMessage(
            role='assistant',
            content="👋 **Welcome to the Gross Utility App!**\n\n"
                   "I can help you with:\n\n"
                   "🏗️ **Create a Project** - Analyze a location for development potential\n"
                   "📍 **Check Zoning** - Look up zoning restrictions and allowances\n"
                   "💰 **Build Pro Forma** - Create financial projections\n\n"
                   "Just tell me what you'd like to do in plain language!\n\n"
                   "*Example: \"I want to analyze a vacant lot on Pacific Avenue for a community food co-op\"*"
        )
        self.messages.append(response)
        return response
    
    def _handle_unknown(self) -> ChatMessage:
        """Handle unknown intent."""
        response = ChatMessage(
            role='assistant',
            content="I'm not quite sure what you're looking for. Could you tell me more about what you'd like to do?\n\n"
                   "I can help with:\n"
                   "- Creating analysis projects\n"
                   "- Checking zoning information\n"
                   "- Building financial pro formas"
        )
        self.messages.append(response)
        return response


def get_chat_session() -> ChatSession:
    """Factory function to get a chat session."""
    return ChatSession()
