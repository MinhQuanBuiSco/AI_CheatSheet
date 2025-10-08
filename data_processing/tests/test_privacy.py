"""Tests for privacy features."""

import polars as pl

from data_processing.privacy import AnonymizationConfig, Anonymizer, PIIDetector, PIIType


def test_pii_detector_email():
    """Test email detection."""
    config = AnonymizationConfig()
    detector = PIIDetector(config)

    text = "Contact me at john.doe@example.com for more info"
    findings = detector.detect(text)

    assert len(findings) > 0
    assert findings[0][0] == PIIType.EMAIL
    assert "john.doe@example.com" in findings[0][1]


def test_pii_detector_phone():
    """Test phone number detection."""
    config = AnonymizationConfig()
    detector = PIIDetector(config)

    text = "Call me at 555-123-4567"
    findings = detector.detect(text)

    assert len(findings) > 0
    assert findings[0][0] == PIIType.PHONE


def test_anonymizer_hash():
    """Test hash anonymization."""
    config = AnonymizationConfig(anonymization_method="hash")
    anonymizer = Anonymizer(config)

    text = "Email me at test@example.com"
    anonymized, count = anonymizer.anonymize_text(text)

    assert count == 1
    assert "test@example.com" not in anonymized
    assert len(anonymized) > 0


def test_anonymizer_mask():
    """Test mask anonymization."""
    config = AnonymizationConfig(anonymization_method="mask")
    anonymizer = Anonymizer(config)

    text = "My email is test@example.com"
    anonymized, count = anonymizer.anonymize_text(text)

    assert count == 1
    assert "*" in anonymized
    assert "@example.com" in anonymized or "example.com" in anonymized


def test_anonymizer_dataframe():
    """Test DataFrame anonymization."""
    config = AnonymizationConfig()
    anonymizer = Anonymizer(config)

    df = pl.DataFrame(
        {
            "name": ["John Doe", "Jane Smith"],
            "email": ["john@example.com", "jane@example.com"],
            "message": [
                "Contact me at john@example.com",
                "My phone is 555-1234",
            ],
        }
    )

    anonymized_df, stats = anonymizer.anonymize_dataframe(df, ["email", "message"])

    assert anonymized_df.shape == df.shape
    assert sum(stats.values()) >= 3  # At least 3 PII instances
