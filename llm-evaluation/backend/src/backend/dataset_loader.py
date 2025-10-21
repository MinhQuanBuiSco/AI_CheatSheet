import random
from typing import Dict, Any, Optional
from datasets import load_dataset
from backend.models import DatasetInfo, Example


class DatasetLoader:
    """Handles loading and sampling from various benchmark datasets"""

    DATASETS = {
        "MMLU": DatasetInfo(
            name="MMLU",
            description="Massive Multitask Language Understanding - Multiple choice questions across 57 subjects",
            task_type="multiple_choice"
        ),
        "GSM8K": DatasetInfo(
            name="GSM8K",
            description="Grade School Math 8K - Math word problems requiring multi-step reasoning",
            task_type="math"
        ),
        "HumanEval": DatasetInfo(
            name="HumanEval",
            description="Hand-written programming problems for code generation",
            task_type="code_generation"
        ),
        "HellaSwag": DatasetInfo(
            name="HellaSwag",
            description="Commonsense reasoning - Complete a sentence with the most plausible continuation",
            task_type="multiple_choice"
        ),
        "TruthfulQA": DatasetInfo(
            name="TruthfulQA",
            description="Questions designed to test truthfulness and resistance to falsehoods",
            task_type="multiple_choice"
        ),
        "MATH": DatasetInfo(
            name="MATH-500",
            description="Competition mathematics problems (500 sample subset)",
            task_type="math"
        ),
        "GPQA": DatasetInfo(
            name="GPQA",
            description="Graduate-level science questions written by domain experts",
            task_type="multiple_choice"
        ),
    }

    # Default system prompts for each dataset
    SYSTEM_PROMPTS = {
        "MMLU": """You are taking a multiple choice test. You must respond with ONLY a single letter: A, B, C, or D.

Examples:
Question: What is 2+2? A. 3 B. 4 C. 5 D. 6
Answer: B

Question: Capital of France? A. London B. Paris C. Berlin D. Rome
Answer: B

Your response MUST be exactly one letter. Do not explain. Do not add any other text.""",

        "GSM8K": """You are solving a math word problem. Provide ONLY the final numerical answer as a number. Do not include units, explanations, or any other text.

Example:
Question: If John has 5 apples and buys 3 more, how many does he have?
Answer: 8

Your response must be ONLY the number.""",

        "HumanEval": """You are completing a Python function. Return ONLY the code implementation without any explanation, comments, or markdown formatting.""",

        "HellaSwag": """You must choose the most likely continuation. Respond with ONLY a single letter: A, B, C, or D.

Your response MUST be exactly one letter. Do not explain.""",

        "TruthfulQA": """You are answering a question truthfully. Respond with ONLY a single letter: A, B, C, or D.

Your response MUST be exactly one letter. Do not explain or justify your answer.""",

        "MATH-500": """You are solving a competition math problem. Provide your final answer in LaTeX format using \\boxed{answer}. You may show your work, but the final answer MUST be in \\boxed{}.""",

        "GPQA": """You are answering a graduate-level science question. Respond with ONLY a single letter: A, B, C, or D.

Your response MUST be exactly one letter. Do not provide explanations.""",
    }

    def __init__(self):
        self.cached_datasets: Dict[str, Any] = {}

    def list_datasets(self) -> list[DatasetInfo]:
        """Return list of available datasets"""
        return list(self.DATASETS.values())

    def get_example(self, dataset_name: str) -> Example:
        """Get a random example from the specified dataset"""
        if dataset_name not in self.DATASETS:
            raise ValueError(f"Dataset {dataset_name} not supported")

        method_name = f"_load_{dataset_name.lower().replace('-', '_')}"
        if hasattr(self, method_name):
            return getattr(self, method_name)()
        else:
            raise NotImplementedError(f"Loader for {dataset_name} not implemented")

    def _load_mmlu(self) -> Example:
        """Load random MMLU example"""
        if "mmlu" not in self.cached_datasets:
            # Load a subset for faster loading
            ds = load_dataset("cais/mmlu", "all", split="test", streaming=True)
            self.cached_datasets["mmlu"] = list(ds.take(100))

        sample = random.choice(self.cached_datasets["mmlu"])
        choices = sample["choices"]
        correct_idx = sample["answer"]

        prompt = f"Question: {sample['question']}\n\n"
        for i, choice in enumerate(choices):
            prompt += f"{chr(65+i)}. {choice}\n"
        prompt += "\nAnswer:"

        return Example(
            dataset="MMLU",
            prompt=prompt,
            system_prompt=self.SYSTEM_PROMPTS["MMLU"],
            choices=choices,
            gold_answer=chr(65 + correct_idx),
            metadata={"subject": sample.get("subject", "unknown")}
        )

    def _load_gsm8k(self) -> Example:
        """Load random GSM8K example"""
        if "gsm8k" not in self.cached_datasets:
            ds = load_dataset("gsm8k", "main", split="test", streaming=True)
            self.cached_datasets["gsm8k"] = list(ds.take(100))

        sample = random.choice(self.cached_datasets["gsm8k"])
        # Extract numeric answer from the format "#### 42"
        answer_text = sample["answer"].split("####")[-1].strip()

        prompt = f"Question: {sample['question']}\n\nProvide your answer as a number."

        return Example(
            dataset="GSM8K",
            prompt=prompt,
            system_prompt=self.SYSTEM_PROMPTS["GSM8K"],
            choices=None,
            gold_answer=answer_text,
            metadata={"full_solution": sample["answer"]}
        )

    def _load_humaneval(self) -> Example:
        """Load random HumanEval example"""
        if "humaneval" not in self.cached_datasets:
            ds = load_dataset("openai_humaneval", split="test")
            self.cached_datasets["humaneval"] = ds

        sample = random.choice(self.cached_datasets["humaneval"])

        return Example(
            dataset="HumanEval",
            prompt=sample["prompt"],
            system_prompt=self.SYSTEM_PROMPTS["HumanEval"],
            choices=None,
            gold_answer=sample["canonical_solution"],
            metadata={
                "task_id": sample["task_id"],
                "test": sample["test"],
                "entry_point": sample["entry_point"]
            }
        )

    def _load_hellaswag(self) -> Example:
        """Load random HellaSwag example"""
        if "hellaswag" not in self.cached_datasets:
            ds = load_dataset("Rowan/hellaswag", split="validation", streaming=True)
            self.cached_datasets["hellaswag"] = list(ds.take(100))

        sample = random.choice(self.cached_datasets["hellaswag"])

        prompt = f"Context: {sample['ctx']}\n\n"
        for i, ending in enumerate(sample["endings"]):
            prompt += f"{chr(65+i)}. {ending}\n"
        prompt += "\nAnswer:"

        return Example(
            dataset="HellaSwag",
            prompt=prompt,
            system_prompt=self.SYSTEM_PROMPTS["HellaSwag"],
            choices=sample["endings"],
            gold_answer=chr(65 + int(sample["label"])),
            metadata={"activity_label": sample.get("activity_label", "")}
        )

    def _load_truthfulqa(self) -> Example:
        """Load random TruthfulQA example"""
        if "truthfulqa" not in self.cached_datasets:
            ds = load_dataset("truthful_qa", "multiple_choice", split="validation")
            self.cached_datasets["truthfulqa"] = ds

        sample = random.choice(self.cached_datasets["truthfulqa"])

        # Combine correct and incorrect answers
        mc1_targets = sample["mc1_targets"]
        choices = mc1_targets["choices"]
        labels = mc1_targets["labels"]

        # Find the correct answer
        correct_idx = labels.index(1) if 1 in labels else 0

        prompt = f"Question: {sample['question']}\n\n"
        for i, choice in enumerate(choices):
            prompt += f"{chr(65+i)}. {choice}\n"
        prompt += "\nAnswer:"

        return Example(
            dataset="TruthfulQA",
            prompt=prompt,
            system_prompt=self.SYSTEM_PROMPTS["TruthfulQA"],
            choices=choices,
            gold_answer=chr(65 + correct_idx),
            metadata={"category": sample.get("category", "unknown")}
        )

    def _load_math(self) -> Example:
        """Load random MATH-500 example"""
        if "math" not in self.cached_datasets:
            ds = load_dataset("hendrycks/competition_math", split="test", streaming=True)
            self.cached_datasets["math"] = list(ds.take(500))

        sample = random.choice(self.cached_datasets["math"])

        prompt = f"Problem: {sample['problem']}\n\nProvide your final answer in LaTeX format using \\boxed{{}}."

        return Example(
            dataset="MATH-500",
            prompt=prompt,
            system_prompt=self.SYSTEM_PROMPTS["MATH-500"],
            choices=None,
            gold_answer=sample["solution"],
            metadata={
                "level": sample["level"],
                "type": sample["type"]
            }
        )

    def _load_gpqa(self) -> Example:
        """Load random GPQA example"""
        if "gpqa" not in self.cached_datasets:
            ds = load_dataset("Idavidrein/gpqa", "gpqa_main", split="train")
            self.cached_datasets["gpqa"] = ds

        sample = random.choice(self.cached_datasets["gpqa"])

        choices = [
            sample["Incorrect Answer 1"],
            sample["Incorrect Answer 2"],
            sample["Incorrect Answer 3"],
            sample["Correct Answer"]
        ]
        random.shuffle(choices)
        correct_idx = choices.index(sample["Correct Answer"])

        prompt = f"Question: {sample['Question']}\n\n"
        for i, choice in enumerate(choices):
            prompt += f"{chr(65+i)}. {choice}\n"
        prompt += "\nAnswer:"

        return Example(
            dataset="GPQA",
            prompt=prompt,
            system_prompt=self.SYSTEM_PROMPTS["GPQA"],
            choices=choices,
            gold_answer=chr(65 + correct_idx),
            metadata={"subdomain": sample.get("Subdomain", "unknown")}
        )
