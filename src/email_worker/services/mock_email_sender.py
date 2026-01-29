"""Mock email sender for testing and development."""

import json
import os
import structlog
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

logger = structlog.get_logger()


class MockEmailSender:
    """
    Mock email service for testing and development.

    Stores sent emails to filesystem for inspection instead of
    actually sending them. In production, replace with SendGrid,
    AWS SES, or another email provider.
    """

    def __init__(self, storage_path: str | None = None):
        """
        Initialize the mock email sender.

        Args:
            storage_path: Directory to store mock emails.
                         Defaults to /tmp/reemio_mock_emails
        """
        self.storage_path = Path(storage_path or "/tmp/reemio_mock_emails")
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.sent_emails: list[dict[str, Any]] = []

    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        from_email: str = "noreply@reemio.com",
        from_name: str = "Reemio",
        tracking_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Simulate sending an email.

        Instead of actually sending, stores the email to the filesystem
        for later inspection during testing.

        Args:
            to_email: Recipient email address
            subject: Email subject line
            html_content: HTML content of the email
            from_email: Sender email address
            from_name: Sender display name
            tracking_id: Optional tracking ID for the email
            metadata: Optional metadata to store with the email

        Returns:
            dict: Simulated send result with message_id and status
        """
        message_id = tracking_id or str(uuid4())
        timestamp = datetime.now(timezone.utc)

        email_record = {
            "message_id": message_id,
            "to_email": to_email,
            "from_email": from_email,
            "from_name": from_name,
            "subject": subject,
            "html_content": html_content,
            "metadata": metadata or {},
            "sent_at": timestamp.isoformat(),
            "status": "sent",
        }

        # Store in memory
        self.sent_emails.append(email_record)

        # Store to filesystem
        filename = f"{timestamp.strftime('%Y%m%d_%H%M%S')}_{message_id}.json"
        filepath = self.storage_path / filename

        with open(filepath, "w") as f:
            json.dump(email_record, f, indent=2)

        logger.info(
            "Mock email sent",
            message_id=message_id,
            to_email=to_email,
            subject=subject,
            stored_at=str(filepath),
        )

        return {
            "success": True,
            "message_id": message_id,
            "status": "sent",
            "stored_at": str(filepath),
        }

    def get_sent_emails(
        self,
        limit: int = 50,
        to_email: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Retrieve recently sent mock emails.

        Args:
            limit: Maximum number of emails to return
            to_email: Optional filter by recipient

        Returns:
            list: List of sent email records
        """
        emails = self.sent_emails

        if to_email:
            emails = [e for e in emails if e["to_email"] == to_email]

        return emails[-limit:]

    def get_all_stored_emails(self) -> list[dict[str, Any]]:
        """
        Retrieve all emails stored on filesystem.

        Returns:
            list: List of all stored email records
        """
        emails = []

        for filepath in sorted(self.storage_path.glob("*.json")):
            with open(filepath) as f:
                emails.append(json.load(f))

        return emails

    def clear_stored_emails(self) -> int:
        """
        Clear all stored mock emails.

        Returns:
            int: Number of emails deleted
        """
        count = 0
        for filepath in self.storage_path.glob("*.json"):
            filepath.unlink()
            count += 1

        self.sent_emails.clear()
        logger.info("Cleared mock emails", count=count)

        return count


# Singleton instance for the application
_mock_sender: MockEmailSender | None = None


def get_mock_email_sender() -> MockEmailSender:
    """Get the singleton mock email sender instance."""
    global _mock_sender
    if _mock_sender is None:
        _mock_sender = MockEmailSender()
    return _mock_sender
