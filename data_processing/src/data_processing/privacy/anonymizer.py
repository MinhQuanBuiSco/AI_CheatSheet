"""PII detection and anonymization for privacy-preserving data processing."""
import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
from enum import Enum

import polars as pl


class PIIType(Enum):
    """Types of PII that can be detected."""
    EMAIL = "email"
    PHONE = "phone"
    SSN = "ssn"
    CREDIT_CARD = "credit_card"
    IP_ADDRESS = "ip_address"
    NAME = "name"
    ADDRESS = "address"
    DATE_OF_BIRTH = "date_of_birth"
    CUSTOM = "custom"


@dataclass
class AnonymizationConfig:
    """Configuration for data anonymization."""
    enabled_pii_types: Set[PIIType] = field(
        default_factory=lambda: {
            PIIType.EMAIL,
            PIIType.PHONE,
            PIIType.SSN,
            PIIType.CREDIT_CARD,
            PIIType.IP_ADDRESS,
        }
    )
    anonymization_method: str = "hash"  # hash, redact, mask, synthetic
    hash_salt: str = "anthropic-clio-salt"
    preserve_format: bool = True
    custom_patterns: Dict[str, str] = field(default_factory=dict)


class PIIDetector:
    """Detects personally identifiable information in text."""

    # Regex patterns for common PII types
    PATTERNS = {
        PIIType.EMAIL: r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        PIIType.PHONE: r'\b(?:\+?1[-.]?)?\(?([0-9]{3})\)?[-.]?([0-9]{3})[-.]?([0-9]{4})\b',
        PIIType.SSN: r'\b(?!000|666|9\d{2})\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b',
        PIIType.CREDIT_CARD: r'\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|3(?:0[0-5]|[68][0-9])[0-9]{11}|6(?:011|5[0-9]{2})[0-9]{12}|(?:2131|1800|35\d{3})\d{11})\b',
        PIIType.IP_ADDRESS: r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b',
        PIIType.DATE_OF_BIRTH: r'\b(?:0[1-9]|1[0-2])[/-](?:0[1-9]|[12][0-9]|3[01])[/-](?:19|20)\d{2}\b',
    }

    def __init__(self, config: AnonymizationConfig):
        self.config = config
        self._compiled_patterns = self._compile_patterns()

    def _compile_patterns(self) -> Dict[PIIType, re.Pattern]:
        """Compile regex patterns for enabled PII types."""
        patterns = {}
        for pii_type in self.config.enabled_pii_types:
            if pii_type in self.PATTERNS:
                patterns[pii_type] = re.compile(self.PATTERNS[pii_type])
            elif pii_type == PIIType.CUSTOM:
                for name, pattern in self.config.custom_patterns.items():
                    patterns[PIIType.CUSTOM] = re.compile(pattern)
        return patterns

    def detect(self, text: str) -> List[tuple[PIIType, str, int, int]]:
        """Detect PII in text.

        Args:
            text: Input text to scan

        Returns:
            List of (pii_type, matched_text, start_pos, end_pos) tuples
        """
        if not isinstance(text, str):
            return []

        findings = []
        for pii_type, pattern in self._compiled_patterns.items():
            for match in pattern.finditer(text):
                findings.append((
                    pii_type,
                    match.group(),
                    match.start(),
                    match.end(),
                ))

        return findings

    def has_pii(self, text: str) -> bool:
        """Check if text contains any PII.

        Args:
            text: Input text to scan

        Returns:
            True if PII detected, False otherwise
        """
        return len(self.detect(text)) > 0


class Anonymizer:
    """Anonymizes PII in data while preserving utility."""

    def __init__(self, config: AnonymizationConfig):
        self.config = config
        self.detector = PIIDetector(config)
        self._anonymization_cache: Dict[str, str] = {}

    def _hash_value(self, value: str) -> str:
        """Hash a value with salt.

        Args:
            value: Value to hash

        Returns:
            Hexadecimal hash string
        """
        salted = f"{self.config.hash_salt}{value}"
        return hashlib.sha256(salted.encode()).hexdigest()[:16]

    def _redact_value(self, value: str, pii_type: PIIType) -> str:
        """Redact a value.

        Args:
            value: Value to redact
            pii_type: Type of PII

        Returns:
            Redacted string
        """
        return f"[REDACTED_{pii_type.value.upper()}]"

    def _mask_value(self, value: str, pii_type: PIIType) -> str:
        """Mask a value while preserving format.

        Args:
            value: Value to mask
            pii_type: Type of PII

        Returns:
            Masked string
        """
        if pii_type == PIIType.EMAIL:
            parts = value.split('@')
            if len(parts) == 2:
                return f"{'*' * len(parts[0])}@{parts[1]}"
        elif pii_type == PIIType.PHONE:
            return re.sub(r'\d', '*', value[:-4]) + value[-4:]
        elif pii_type == PIIType.CREDIT_CARD:
            return '*' * (len(value) - 4) + value[-4:]

        # Default: mask all but last 4 characters
        if len(value) > 4:
            return '*' * (len(value) - 4) + value[-4:]
        return '*' * len(value)

    def anonymize_text(self, text: str) -> tuple[str, int]:
        """Anonymize PII in text.

        Args:
            text: Input text

        Returns:
            Tuple of (anonymized_text, num_replacements)
        """
        if not isinstance(text, str):
            return text, 0

        findings = self.detector.detect(text)
        if not findings:
            return text, 0

        # Sort findings by position (reverse) to replace from end to start
        findings.sort(key=lambda x: x[2], reverse=True)

        result = text
        num_replacements = 0

        for pii_type, matched_text, start, end in findings:
            # Choose anonymization method
            if self.config.anonymization_method == "hash":
                replacement = self._hash_value(matched_text)
            elif self.config.anonymization_method == "redact":
                replacement = self._redact_value(matched_text, pii_type)
            elif self.config.anonymization_method == "mask":
                replacement = self._mask_value(matched_text, pii_type)
            else:
                replacement = self._hash_value(matched_text)

            # Cache for consistency
            self._anonymization_cache[matched_text] = replacement

            # Replace in text
            result = result[:start] + replacement + result[end:]
            num_replacements += 1

        return result, num_replacements

    def anonymize_dataframe(self, df: pl.DataFrame, text_columns: Optional[List[str]] = None) -> tuple[pl.DataFrame, Dict[str, int]]:
        """Anonymize PII in DataFrame columns.

        Args:
            df: Input DataFrame
            text_columns: Columns to scan (all string columns if None)

        Returns:
            Tuple of (anonymized_df, replacement_stats)
        """
        if text_columns is None:
            # Auto-detect string columns
            text_columns = [col for col in df.columns if df[col].dtype == pl.Utf8]

        stats = {}
        result_df = df.clone()

        for col in text_columns:
            total_replacements = 0

            # Apply anonymization to each value
            anonymized_values = []
            for value in result_df[col]:
                if value is not None:
                    anon_value, num_replacements = self.anonymize_text(str(value))
                    anonymized_values.append(anon_value)
                    total_replacements += num_replacements
                else:
                    anonymized_values.append(None)

            result_df = result_df.with_columns(
                pl.Series(col, anonymized_values)
            )
            stats[col] = total_replacements

        return result_df, stats

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get anonymization cache statistics.

        Returns:
            Dictionary with cache stats
        """
        return {
            "cache_size": len(self._anonymization_cache),
            "unique_values_anonymized": len(self._anonymization_cache),
        }
