import re
from typing import Dict, Any, Tuple, Optional


class Evaluator:
    """Handles evaluation of model predictions against gold answers"""

    @staticmethod
    def evaluate(dataset: str, predicted: str, gold: str, choices: Optional[list[str]] = None) -> Tuple[float, str, Dict[str, Any]]:
        """
        Evaluate prediction based on dataset type
        Returns: (score, metric_name, details)
        """
        dataset_upper = dataset.upper()

        if dataset_upper in ["MMLU", "HELLASWAG", "TRUTHFULQA", "GPQA"]:
            return Evaluator._evaluate_multiple_choice(predicted, gold, choices)
        elif dataset_upper in ["GSM8K", "MATH-500"]:
            return Evaluator._evaluate_math(predicted, gold)
        elif dataset_upper == "HUMANEVAL":
            return Evaluator._evaluate_code(predicted, gold)
        else:
            return Evaluator._evaluate_exact_match(predicted, gold)

    @staticmethod
    def _evaluate_multiple_choice(predicted: str, gold: str, choices: Optional[list[str]] = None) -> Tuple[float, str, Dict[str, Any]]:
        """Evaluate multiple choice answers"""
        # Extract the letter from prediction (A, B, C, D)
        predicted_clean = Evaluator._extract_answer_letter(predicted)
        gold_clean = gold.strip().upper()

        # Check if prediction matches gold
        exact_match = predicted_clean == gold_clean

        # Also check if the predicted letter is valid
        valid_choices = [chr(65 + i) for i in range(len(choices))] if choices else ["A", "B", "C", "D"]
        is_valid = predicted_clean in valid_choices

        score = 1.0 if exact_match else 0.0

        details = {
            "extracted_answer": predicted_clean,
            "is_valid_choice": is_valid,
            "valid_choices": valid_choices
        }

        return score, "accuracy", details

    @staticmethod
    def _evaluate_math(predicted: str, gold: str) -> Tuple[float, str, Dict[str, Any]]:
        """Evaluate mathematical answers"""
        # Try to extract numeric answer from prediction
        predicted_num = Evaluator._extract_number(predicted)
        gold_num = Evaluator._extract_number(gold)

        if predicted_num is None or gold_num is None:
            # Try string matching as fallback
            predicted_clean = predicted.strip().lower()
            gold_clean = gold.strip().lower()
            score = 1.0 if predicted_clean == gold_clean else 0.0
            details = {
                "extracted_prediction": predicted_clean,
                "extracted_gold": gold_clean,
                "method": "string_match"
            }
        else:
            # Numeric comparison with tolerance
            tolerance = abs(gold_num) * 0.01 if gold_num != 0 else 0.01
            score = 1.0 if abs(predicted_num - gold_num) <= tolerance else 0.0
            details = {
                "extracted_prediction": predicted_num,
                "extracted_gold": gold_num,
                "method": "numeric_match",
                "tolerance": tolerance
            }

        return score, "accuracy", details

    @staticmethod
    def _evaluate_code(predicted: str, gold: str) -> Tuple[float, str, Dict[str, Any]]:
        """Evaluate code generation - simplified version"""
        # In production, you would execute tests here
        # For now, we'll do a simple string similarity check
        predicted_clean = predicted.strip()
        gold_clean = gold.strip()

        # Simple metric: check if key elements are present
        # This is a placeholder - real HumanEval uses unit test execution
        similarity = Evaluator._simple_code_similarity(predicted_clean, gold_clean)
        score = 1.0 if similarity > 0.7 else 0.0

        details = {
            "similarity": similarity,
            "note": "This is a simplified evaluation. Real HumanEval uses unit test execution.",
            "predicted_length": len(predicted_clean),
            "gold_length": len(gold_clean)
        }

        return score, "pass@1", details

    @staticmethod
    def _evaluate_exact_match(predicted: str, gold: str) -> Tuple[float, str, Dict[str, Any]]:
        """Fallback exact match evaluation"""
        predicted_clean = predicted.strip().lower()
        gold_clean = gold.strip().lower()

        score = 1.0 if predicted_clean == gold_clean else 0.0

        details = {
            "method": "exact_match"
        }

        return score, "exact_match", details

    @staticmethod
    def _extract_answer_letter(text: str) -> str:
        """Extract answer letter (A, B, C, D) from text"""
        text = text.strip().upper()

        # Pattern 1: Just the letter
        if len(text) == 1 and text in "ABCDEFGH":
            return text

        # Pattern 2: "Answer: A" or "A)" or "(A)"
        patterns = [
            r'(?:ANSWER|CHOICE)?\s*[:\-]?\s*\(?([A-H])\)?',
            r'\(([A-H])\)',
            r'^([A-H])[\.:\)]',
            r'\b([A-H])\b'
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)

        # If no pattern matches, take the first capital letter
        for char in text:
            if char in "ABCDEFGH":
                return char

        return text[:1] if text else "A"

    @staticmethod
    def _extract_number(text: str) -> float:
        """Extract numeric answer from text"""
        if not text:
            return None

        # Remove common text and extract numbers
        text = text.strip()

        # Try to find boxed answer (for MATH dataset)
        boxed_match = re.search(r'\\boxed\{([^}]+)\}', text)
        if boxed_match:
            text = boxed_match.group(1)

        # Extract number with optional comma separators and decimals
        number_match = re.search(r'-?\d+(?:,\d{3})*(?:\.\d+)?', text.replace(',', ''))
        if number_match:
            try:
                return float(number_match.group(0))
            except ValueError:
                return None

        return None

    @staticmethod
    def _simple_code_similarity(code1: str, code2: str) -> float:
        """Simple code similarity metric based on common tokens"""
        # Tokenize code
        tokens1 = set(re.findall(r'\w+', code1.lower()))
        tokens2 = set(re.findall(r'\w+', code2.lower()))

        if not tokens1 or not tokens2:
            return 0.0

        # Jaccard similarity
        intersection = len(tokens1 & tokens2)
        union = len(tokens1 | tokens2)

        return intersection / union if union > 0 else 0.0
