import re
from typing import Dict, Any, Tuple, Optional
from rouge_score import rouge_scorer
from nltk.translate.bleu_score import sentence_bleu, SmoothingFunction


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
        elif dataset_upper == "GSM8K":
            return Evaluator._evaluate_math(predicted, gold)
        elif dataset_upper == "HUMANEVAL":
            return Evaluator._evaluate_code(predicted, gold)
        elif dataset_upper == "CNNDAILYMAIL":
            return Evaluator._evaluate_summarization(predicted, gold)
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

        # Create detailed explanation
        explanation = {
            "Accuracy": {
                "description": "Measures whether the predicted answer exactly matches the correct answer",
                "calculation": "Accuracy = 1 if predicted_letter == correct_letter else 0",
                "how_it_works": "The model's response is parsed to extract the choice letter (A, B, C, or D). This is compared against the gold/correct answer. Only exact matches receive a score of 1.0 (100%), all other predictions score 0.0 (0%).",
                "score": score,
                "interpretation": "✓ Correct answer!" if score == 1.0 else "✗ Incorrect answer",
                "predicted_letter": predicted_clean,
                "correct_letter": gold_clean,
                "is_valid_choice": is_valid,
                "note": "Multiple choice evaluation is binary - either completely correct (100%) or incorrect (0%). There are no partial credits."
            }
        }

        details = {
            "extracted_answer": predicted_clean,
            "is_valid_choice": is_valid,
            "valid_choices": valid_choices,
            "explanation": explanation
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

            explanation = {
                "String Match": {
                    "description": "Evaluates math answers by exact string matching when numeric extraction fails",
                    "calculation": "Accuracy = 1 if predicted_text == gold_text else 0",
                    "how_it_works": "When the answer cannot be parsed as a number (e.g., contains LaTeX or special formatting), the system falls back to exact string matching. Both strings are normalized (lowercased and trimmed) before comparison.",
                    "score": score,
                    "interpretation": "✓ Exact match!" if score == 1.0 else "✗ Strings don't match",
                    "predicted_value": predicted_clean,
                    "gold_value": gold_clean,
                    "method": "string_match",
                    "note": "For LaTeX answers (e.g., \\boxed{...}), the content inside \\boxed{} is extracted first before comparison."
                }
            }

            details = {
                "extracted_prediction": predicted_clean,
                "extracted_gold": gold_clean,
                "method": "string_match",
                "explanation": explanation
            }
        else:
            # Numeric comparison with tolerance
            tolerance = abs(gold_num) * 0.01 if gold_num != 0 else 0.01
            difference = abs(predicted_num - gold_num)
            score = 1.0 if difference <= tolerance else 0.0

            explanation = {
                "Numeric Match with Tolerance": {
                    "description": "Evaluates math answers by comparing numeric values with a small tolerance for rounding errors",
                    "calculation": f"Accuracy = 1 if |predicted - gold| ≤ tolerance else 0\nTolerance = |gold| × 0.01 (1% of gold value)",
                    "how_it_works": "Numbers are extracted from both the prediction and gold answer using regex patterns. A 1% tolerance is applied to account for rounding differences. If the absolute difference is within tolerance, the answer is considered correct.",
                    "score": score,
                    "interpretation": "✓ Within tolerance!" if score == 1.0 else f"✗ Difference ({difference:.4f}) exceeds tolerance ({tolerance:.4f})",
                    "predicted_value": predicted_num,
                    "gold_value": gold_num,
                    "absolute_difference": round(difference, 4),
                    "tolerance": round(tolerance, 4),
                    "method": "numeric_match",
                    "note": "The 1% tolerance allows for minor rounding differences while still ensuring accuracy. For example, if the gold answer is 100, any value between 99 and 101 is accepted."
                }
            }

            details = {
                "extracted_prediction": predicted_num,
                "extracted_gold": gold_num,
                "method": "numeric_match",
                "tolerance": tolerance,
                "explanation": explanation
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

        # Tokenize for additional metrics
        pred_tokens = set(Evaluator._tokenize_code(predicted_clean))
        gold_tokens = set(Evaluator._tokenize_code(gold_clean))
        common_tokens = pred_tokens & gold_tokens

        explanation = {
            "Jaccard Similarity (Simplified)": {
                "description": "Measures code similarity by comparing the overlap of tokens (keywords, identifiers, operators) between predicted and reference code",
                "calculation": "Jaccard = |intersection(tokens)| / |union(tokens)|\nScore = 1 if Jaccard > 0.7 else 0",
                "how_it_works": "The code is tokenized into words (identifiers, keywords, operators). The Jaccard similarity coefficient is calculated as the ratio of common tokens to total unique tokens. A threshold of 0.7 (70% similarity) is used to determine pass/fail.",
                "score": score,
                "similarity": round(similarity, 4),
                "interpretation": f"{'✓ Pass' if score == 1.0 else '✗ Fail'} (similarity: {similarity:.1%}, threshold: 70%)",
                "common_tokens": len(common_tokens),
                "predicted_tokens": len(pred_tokens),
                "gold_tokens": len(gold_tokens),
                "predicted_length": len(predicted_clean),
                "gold_length": len(gold_clean),
                "note": "⚠️ This is a simplified evaluation for demonstration. Production HumanEval uses actual unit test execution to verify functional correctness, not just similarity."
            },
            "Production Method (Reference)": {
                "description": "How HumanEval is actually evaluated in research",
                "method": "Unit Test Execution",
                "how_it_works": "In production evaluation:\n1. The generated code is executed with test cases\n2. Each test case checks if the function produces correct outputs\n3. Pass@k metric: Probability that at least 1 of k samples passes all tests\n4. This validates functional correctness, not just syntactic similarity",
                "why_different": "Unit test execution requires sandboxed code execution which is complex and potentially dangerous. This demo uses similarity as a safe approximation.",
                "metric": "pass@k (typically pass@1, pass@10, pass@100)"
            }
        }

        details = {
            "similarity": similarity,
            "note": "This is a simplified evaluation. Real HumanEval uses unit test execution.",
            "predicted_length": len(predicted_clean),
            "gold_length": len(gold_clean),
            "explanation": explanation
        }

        return score, "pass@1", details

    @staticmethod
    def _tokenize_code(code: str) -> list[str]:
        """Tokenize code into words for similarity comparison"""
        import re
        return re.findall(r'\w+', code.lower())

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

    @staticmethod
    def _evaluate_summarization(predicted: str, gold: str) -> Tuple[float, str, Dict[str, Any]]:
        """
        Evaluate summarization using ROUGE and BLEU scores
        Returns average score and detailed metrics with explanations
        """
        predicted = predicted.strip()
        gold = gold.strip()

        # Calculate ROUGE scores
        scorer = rouge_scorer.RougeScorer(['rouge1', 'rouge2', 'rougeL'], use_stemmer=True)
        rouge_scores = scorer.score(gold, predicted)

        # Calculate BLEU score
        smoothing = SmoothingFunction().method1
        # Tokenize for BLEU
        reference = [gold.split()]
        candidate = predicted.split()
        bleu_score = sentence_bleu(reference, candidate, smoothing_function=smoothing)

        # Extract F1 scores from ROUGE
        rouge1_f1 = rouge_scores['rouge1'].fmeasure
        rouge2_f1 = rouge_scores['rouge2'].fmeasure
        rougeL_f1 = rouge_scores['rougeL'].fmeasure

        # Average ROUGE F1 score as primary metric
        avg_rouge = (rouge1_f1 + rouge2_f1 + rougeL_f1) / 3

        # Create detailed explanation
        explanation = {
            "ROUGE-1": {
                "description": "Measures unigram (single word) overlap between predicted and reference summary",
                "calculation": "ROUGE-1 = (Number of overlapping unigrams) / (Total unigrams in reference)",
                "precision": round(rouge_scores['rouge1'].precision, 4),
                "recall": round(rouge_scores['rouge1'].recall, 4),
                "f1": round(rouge1_f1, 4),
                "interpretation": f"{'Excellent' if rouge1_f1 > 0.5 else 'Good' if rouge1_f1 > 0.3 else 'Needs improvement'} unigram overlap"
            },
            "ROUGE-2": {
                "description": "Measures bigram (two consecutive words) overlap between predicted and reference",
                "calculation": "ROUGE-2 = (Number of overlapping bigrams) / (Total bigrams in reference)",
                "precision": round(rouge_scores['rouge2'].precision, 4),
                "recall": round(rouge_scores['rouge2'].recall, 4),
                "f1": round(rouge2_f1, 4),
                "interpretation": f"{'Excellent' if rouge2_f1 > 0.4 else 'Good' if rouge2_f1 > 0.2 else 'Needs improvement'} bigram overlap (phrase similarity)"
            },
            "ROUGE-L": {
                "description": "Measures longest common subsequence (LCS) between predicted and reference",
                "calculation": "ROUGE-L = LCS(predicted, reference) / length(reference)",
                "precision": round(rouge_scores['rougeL'].precision, 4),
                "recall": round(rouge_scores['rougeL'].recall, 4),
                "f1": round(rougeL_f1, 4),
                "interpretation": f"{'Excellent' if rougeL_f1 > 0.5 else 'Good' if rougeL_f1 > 0.3 else 'Needs improvement'} sentence structure similarity"
            },
            "BLEU": {
                "description": "Measures n-gram precision with brevity penalty for translation/summarization quality",
                "calculation": "BLEU = BP × exp(Σ(wₙ × log(pₙ))) where pₙ is n-gram precision and BP is brevity penalty",
                "score": round(bleu_score, 4),
                "interpretation": f"{'Excellent' if bleu_score > 0.5 else 'Good' if bleu_score > 0.3 else 'Needs improvement'} overall quality",
                "note": "BLEU ranges from 0 (no overlap) to 1 (perfect match). Scores > 0.3 are generally good for summarization."
            },
            "summary_statistics": {
                "predicted_length": len(predicted.split()),
                "reference_length": len(gold.split()),
                "length_ratio": round(len(predicted.split()) / max(len(gold.split()), 1), 2)
            }
        }

        details = {
            "rouge1_f1": round(rouge1_f1, 4),
            "rouge2_f1": round(rouge2_f1, 4),
            "rougeL_f1": round(rougeL_f1, 4),
            "bleu": round(bleu_score, 4),
            "average_rouge": round(avg_rouge, 4),
            "explanation": explanation
        }

        # Use average ROUGE as the primary score
        return avg_rouge, "ROUGE-Avg", details
