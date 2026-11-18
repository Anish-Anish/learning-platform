"""In-process event bus (§4.1). Every attempt is one `AttemptRecorded` event.

Handlers run synchronously in registration order inside the request's DB transaction:
learner model -> misconceptions -> gamification -> diagnosis trigger -> analytics.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from app.observability.logging import get_logger

log = get_logger(__name__)


@dataclass
class Event:
    name: str
    trace_id: str
    student_id: str
    payload: dict[str, Any] = field(default_factory=dict)


Handler = Callable[[Event, Any], None]


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[str, list[tuple[int, str, Handler]]] = defaultdict(list)

    def subscribe(self, event_name: str, handler: Handler, order: int = 100, name: str | None = None) -> None:
        self._handlers[event_name].append((order, name or handler.__name__, handler))
        self._handlers[event_name].sort(key=lambda h: h[0])

    def publish(self, event: Event, ctx: Any) -> None:
        for _order, name, handler in self._handlers.get(event.name, []):
            log.debug("event_handler", event_name=event.name, handler=name)
            handler(event, ctx)

    def handlers(self, event_name: str) -> list[str]:
        return [n for _, n, _ in self._handlers.get(event_name, [])]


bus = EventBus()
