"""Audit logging for data access and processing."""

from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

import orjson


class AuditEventType(Enum):
    """Types of audit events."""

    DATA_ACCESS = "data_access"
    DATA_PROCESSING = "data_processing"
    PII_DETECTED = "pii_detected"
    PII_ANONYMIZED = "pii_anonymized"
    ENCRYPTION = "encryption"
    DECRYPTION = "decryption"
    EXPORT = "export"
    ERROR = "error"


@dataclass
class AuditEvent:
    """Represents an auditable event."""

    timestamp: str
    event_type: AuditEventType
    user: str
    action: str
    resource: str
    details: dict[str, Any]
    success: bool = True
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation
        """
        data = asdict(self)
        data["event_type"] = self.event_type.value
        return data


class AuditLogger:
    """Logs audit events for compliance and security."""

    def __init__(self, log_path: str | Path, user: str = "system"):
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.user = user
        self._event_count = 0

    def log_event(
        self,
        event_type: AuditEventType,
        action: str,
        resource: str,
        details: dict[str, Any] | None = None,
        success: bool = True,
        error_message: str | None = None,
    ) -> None:
        """Log an audit event.

        Args:
            event_type: Type of event
            action: Action performed
            resource: Resource affected
            details: Additional details
            success: Whether action succeeded
            error_message: Error message if failed
        """
        event = AuditEvent(
            timestamp=datetime.utcnow().isoformat(),
            event_type=event_type,
            user=self.user,
            action=action,
            resource=resource,
            details=details or {},
            success=success,
            error_message=error_message,
        )

        # Append to log file
        with open(self.log_path, "ab") as f:
            f.write(orjson.dumps(event.to_dict()))
            f.write(b"\n")

        self._event_count += 1

    def log_data_access(self, resource: str, **kwargs: Any) -> None:
        """Log data access event."""
        self.log_event(
            AuditEventType.DATA_ACCESS,
            "access",
            resource,
            kwargs,
        )

    def log_data_processing(self, resource: str, records_processed: int, **kwargs: Any) -> None:
        """Log data processing event."""
        details = {"records_processed": records_processed, **kwargs}
        self.log_event(
            AuditEventType.DATA_PROCESSING,
            "process",
            resource,
            details,
        )

    def log_pii_detection(self, resource: str, pii_count: int, pii_types: list) -> None:
        """Log PII detection event."""
        self.log_event(
            AuditEventType.PII_DETECTED,
            "detect_pii",
            resource,
            {"pii_count": pii_count, "pii_types": pii_types},
        )

    def log_pii_anonymization(self, resource: str, anonymization_count: int) -> None:
        """Log PII anonymization event."""
        self.log_event(
            AuditEventType.PII_ANONYMIZED,
            "anonymize_pii",
            resource,
            {"anonymization_count": anonymization_count},
        )

    def log_encryption(self, resource: str, **kwargs: Any) -> None:
        """Log encryption event."""
        self.log_event(
            AuditEventType.ENCRYPTION,
            "encrypt",
            resource,
            kwargs,
        )

    def log_decryption(self, resource: str, **kwargs: Any) -> None:
        """Log decryption event."""
        self.log_event(
            AuditEventType.DECRYPTION,
            "decrypt",
            resource,
            kwargs,
        )

    def log_export(self, resource: str, destination: str, **kwargs: Any) -> None:
        """Log data export event."""
        details = {"destination": destination, **kwargs}
        self.log_event(
            AuditEventType.EXPORT,
            "export",
            resource,
            details,
        )

    def log_error(self, resource: str, error: Exception) -> None:
        """Log error event."""
        self.log_event(
            AuditEventType.ERROR,
            "error",
            resource,
            {"error_type": type(error).__name__},
            success=False,
            error_message=str(error),
        )

    def get_event_count(self) -> int:
        """Get total event count.

        Returns:
            Number of logged events
        """
        return self._event_count

    def query_events(
        self,
        event_type: AuditEventType | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
    ) -> list[AuditEvent]:
        """Query audit events.

        Args:
            event_type: Filter by event type
            start_time: Filter by start time (ISO format)
            end_time: Filter by end time (ISO format)

        Returns:
            List of matching events
        """
        events: list[AuditEvent] = []

        if not self.log_path.exists():
            return events

        with open(self.log_path, "rb") as f:
            for line in f:
                if not line.strip():
                    continue

                data = orjson.loads(line)

                # Apply filters
                if event_type and data["event_type"] != event_type.value:
                    continue

                if start_time and data["timestamp"] < start_time:
                    continue

                if end_time and data["timestamp"] > end_time:
                    continue

                # Reconstruct event
                event = AuditEvent(
                    timestamp=data["timestamp"],
                    event_type=AuditEventType(data["event_type"]),
                    user=data["user"],
                    action=data["action"],
                    resource=data["resource"],
                    details=data["details"],
                    success=data["success"],
                    error_message=data.get("error_message"),
                )
                events.append(event)

        return events
