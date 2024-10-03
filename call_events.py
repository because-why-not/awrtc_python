from enum import Enum
from typing import Callable, Optional, Any, List

from aiortc.mediastreams import MediaStreamTrack
from websocket_network import ConnectionId

class CallEventType(Enum):
    INVALID = 0
    WAIT_FOR_INCOMING_CALL = 1
    CALL_ACCEPTED = 2
    CALL_ENDED = 3
    TRACK_UPDATE = 4
    MESSAGE = 5
    CONNECTION_FAILED = 6
    LISTENING_FAILED = 7
    CONFIGURATION_COMPLETE = 8
    CONFIGURATION_FAILED = 9
    DATA_MESSAGE = 10
    AUDIO_FRAMES = 11
    RTC_EVENT = 12

class CallEventArgs:
    def __init__(self, event_type: CallEventType):
        self.type = event_type



class CallAcceptedEventArgs(CallEventArgs):
    def __init__(self, connection_id: ConnectionId):
        super().__init__(CallEventType.CALL_ACCEPTED)
        self.connection_id = connection_id

class CallEndedEventArgs(CallEventArgs):
    def __init__(self, connection_id: ConnectionId):
        super().__init__(CallEventType.CALL_ENDED)
        self.connection_id: ConnectionId = connection_id

class TrackUpdateEventArgs(CallEventArgs):
    def __init__(self, connection_id: ConnectionId, track: MediaStreamTrack):
        super().__init__(CallEventType.TRACK_UPDATE)
        self.connection_id: ConnectionId = connection_id
        self.track = track

class ErrorInfo:
    def __init__(self, message: str):
        self.message = message

class ErrorEventArgs(CallEventArgs):
    def __init__(self, event_type: CallEventType, error_info: Optional[ErrorInfo] = None):
        super().__init__(event_type)
        self.info = error_info or ErrorInfo(self._guess_error())

    def _guess_error(self) -> str:
        if self.type == CallEventType.CONNECTION_FAILED:
            return "Connection failed."
        elif self.type == CallEventType.LISTENING_FAILED:
            return "Failed to allow incoming connections. Address already in use or server connection failed."
        else:
            return "Unknown error."

class WaitForIncomingCallEventArgs(CallEventArgs):
    def __init__(self, address: str):
        super().__init__(CallEventType.WAIT_FOR_INCOMING_CALL)
        self.address = address

class MessageEventArgs(CallEventArgs):
    def __init__(self, connection_id: ConnectionId, content: str, reliable: bool = True):
        super().__init__(CallEventType.MESSAGE)
        self.connection_id = connection_id
        self.content = content
        self.reliable = reliable

class DataMessageEventArgs(CallEventArgs):
    def __init__(self, connection_id, content: bytes, reliable: bool):
        super().__init__(CallEventType.DATA_MESSAGE)
        self.connection_id = connection_id
        self.content = content
        self.reliable = reliable


# Define a type for the event handler
CallEventHandler = Callable[[Any, CallEventArgs], None]