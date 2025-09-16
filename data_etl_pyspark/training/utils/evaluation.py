"""
Advanced Model Evaluation and Testing Suite
Production-ready evaluation with comprehensive metrics, benchmarking, and quality assessment.
"""

import os
import json
import time
import logging
from typing import Dict, List, Optional, Tuple, Any, Union
from pathlib import Path
from dataclasses import dataclass
from collections import defaultdict
import numpy as np
import pandas as pd

import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader
from transformers import (
    AutoModelForCausalLM, 
    AutoTokenizer,
    pipeline,
    TextGenerationPipeline
)
from datasets import Dataset, load_dataset
import evaluate
from nltk.translate.bleu_score import sentence_bleu
from rouge_score import rouge_scorer
import sacrebleu
from bert_score import score as bert_score

# Ensure NLTK data is available
try:
    import nltk
    nltk.download('punkt', quiet=True)
except:
    pass


@dataclass
class EvaluationConfig:
    """Configuration for model evaluation."""
    
    # Model paths
    model_path: str
    tokenizer_path: Optional[str] = None
    
    # Evaluation datasets
    eval_datasets: List[str] = None  # List of dataset names or paths
    test_data_path: Optional[str] = None
    
    # Generation settings
    max_new_tokens: int = 128
    temperature: float = 0.7
    do_sample: bool = True
    top_k: int = 50
    top_p: float = 0.9
    repetition_penalty: float = 1.1
    
    # Evaluation settings
    batch_size: int = 8
    max_samples: int = 1000  # Limit for faster evaluation
    seed: int = 42
    
    # Metrics to compute
    compute_perplexity: bool = True
    compute_bleu: bool = True
    compute_rouge: bool = True
    compute_bert_score: bool = True
    compute_diversity: bool = True
    compute_coherence: bool = True
    
    # Output settings
    output_dir: str = "./evaluation_results"
    save_generations: bool = True
    save_detailed_metrics: bool = True


class ComprehensiveEvaluator:
    """Advanced model evaluation system with multiple metrics and benchmarks."""
    
    def __init__(self, config: EvaluationConfig):
        self.config = config
        self.setup_logging()
        self.setup_output_dir()
        self.load_model_and_tokenizer()
        self.setup_metrics()
        
    def setup_logging(self):
        """Setup logging for evaluation."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
    def setup_output_dir(self):
        """Create output directory structure."""
        self.output_dir = Path(self.config.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories
        (self.output_dir / "generations").mkdir(exist_ok=True)
        (self.output_dir / "metrics").mkdir(exist_ok=True)
        (self.output_dir / "benchmarks").mkdir(exist_ok=True)
        
    def load_model_and_tokenizer(self):
        """Load the fine-tuned model and tokenizer."""
        self.logger.info(f"Loading model from {self.config.model_path}")
        
        # Load tokenizer
        tokenizer_path = self.config.tokenizer_path or self.config.model_path
        self.tokenizer = AutoTokenizer.from_pretrained(tokenizer_path)
        
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
            
        # Load model with appropriate device mapping
        device = "cuda" if torch.cuda.is_available() else "cpu"
        
        self.model = AutoModelForCausalLM.from_pretrained(
            self.config.model_path,
            torch_dtype=torch.float16 if device == "cuda" else torch.float32,
            device_map="auto" if torch.cuda.is_available() else None,
            low_cpu_mem_usage=True
        )
        
        self.model.eval()
        self.device = device
        
        self.logger.info(f"Model loaded on {device}")
        self.logger.info(f"Model parameters: {self.model.num_parameters():,}")
        
    def setup_metrics(self):
        """Initialize evaluation metrics."""
        self.rouge_scorer = rouge_scorer.RougeScorer(['rouge1', 'rouge2', 'rougeL'], use_stemmer=True)
        
        # Load standard metrics
        try:
            self.bleu_metric = evaluate.load("bleu")
            self.perplexity_metric = evaluate.load("perplexity", module_type="metric")
        except Exception as e:
            self.logger.warning(f"Could not load some metrics: {e}")
            
    def load_evaluation_data(self) -> List[Dataset]:
        """Load evaluation datasets."""
        datasets = []
        
        # Load test data if provided
        if self.config.test_data_path:
            if self.config.test_data_path.endswith('.parquet'):
                df = pd.read_parquet(self.config.test_data_path)
                dataset = Dataset.from_pandas(df)
            else:
                dataset = load_dataset(self.config.test_data_path)["test"]
            datasets.append(("test_data", dataset))
            
        # Load standard evaluation datasets
        if self.config.eval_datasets:
            for dataset_name in self.config.eval_datasets:
                try:
                    dataset = load_dataset(dataset_name, split="test")
                    datasets.append((dataset_name, dataset))
                    self.logger.info(f"Loaded {dataset_name}: {len(dataset)} samples")
                except Exception as e:
                    self.logger.warning(f"Could not load {dataset_name}: {e}")
                    
        return datasets
        
    def compute_perplexity(self, texts: List[str]) -> Dict[str, float]:
        """Compute perplexity on a list of texts."""
        self.logger.info("Computing perplexity...")
        
        total_log_likelihood = 0
        total_tokens = 0
        
        with torch.no_grad():
            for i in range(0, len(texts), self.config.batch_size):
                batch_texts = texts[i:i + self.config.batch_size]
                
                # Tokenize
                inputs = self.tokenizer(
                    batch_texts,
                    return_tensors="pt",
                    padding=True,
                    truncation=True,
                    max_length=512
                ).to(self.device)
                
                # Get model outputs
                outputs = self.model(**inputs, labels=inputs["input_ids"])
                
                # Calculate log likelihood
                shift_logits = outputs.logits[..., :-1, :].contiguous()
                shift_labels = inputs["input_ids"][..., 1:].contiguous()
                
                # Calculate loss (negative log likelihood)
                loss = F.cross_entropy(
                    shift_logits.view(-1, shift_logits.size(-1)),
                    shift_labels.view(-1),
                    ignore_index=self.tokenizer.pad_token_id,
                    reduction='sum'
                )
                
                # Count valid tokens
                valid_tokens = (shift_labels != self.tokenizer.pad_token_id).sum().item()
                
                total_log_likelihood += loss.item()
                total_tokens += valid_tokens
                
        perplexity = torch.exp(torch.tensor(total_log_likelihood / total_tokens)).item()
        
        return {
            "perplexity": perplexity,
            "total_tokens": total_tokens,
            "average_log_likelihood": total_log_likelihood / total_tokens
        }
        
    def generate_text(self, prompts: List[str]) -> List[str]:
        """Generate text from prompts."""
        self.logger.info(f"Generating text for {len(prompts)} prompts...")
        
        generations = []
        
        # Create generation pipeline
        generator = pipeline(
            "text-generation",
            model=self.model,
            tokenizer=self.tokenizer,
            device=0 if torch.cuda.is_available() else -1
        )
        
        for i in range(0, len(prompts), self.config.batch_size):
            batch_prompts = prompts[i:i + self.config.batch_size]
            
            batch_generations = generator(
                batch_prompts,
                max_new_tokens=self.config.max_new_tokens,
                temperature=self.config.temperature,
                do_sample=self.config.do_sample,
                top_k=self.config.top_k,
                top_p=self.config.top_p,
                repetition_penalty=self.config.repetition_penalty,
                pad_token_id=self.tokenizer.eos_token_id,
                return_full_text=False
            )
            
            for gen in batch_generations:
                generations.append(gen[0]["generated_text"])
                
        return generations
        
    def compute_text_quality_metrics(self, generated_texts: List[str], reference_texts: List[str] = None) -> Dict[str, Any]:
        """Compute comprehensive text quality metrics."""
        metrics = {}
        
        # Diversity metrics
        if self.config.compute_diversity:
            metrics.update(self.compute_diversity_metrics(generated_texts))
            
        # Reference-based metrics (if references available)
        if reference_texts and len(reference_texts) == len(generated_texts):
            if self.config.compute_bleu:
                metrics.update(self.compute_bleu_scores(generated_texts, reference_texts))
                
            if self.config.compute_rouge:
                metrics.update(self.compute_rouge_scores(generated_texts, reference_texts))
                
            if self.config.compute_bert_score:
                metrics.update(self.compute_bert_scores(generated_texts, reference_texts))
                
        # Text quality metrics
        metrics.update(self.compute_quality_metrics(generated_texts))
        
        return metrics
        
    def compute_diversity_metrics(self, texts: List[str]) -> Dict[str, float]:
        """Compute diversity metrics for generated texts."""
        
        # Tokenize all texts
        all_tokens = []
        for text in texts:
            tokens = self.tokenizer.tokenize(text.lower())
            all_tokens.extend(tokens)
            
        # Distinct-1 and Distinct-2
        distinct_1 = len(set(all_tokens)) / len(all_tokens) if all_tokens else 0
        
        bigrams = [(all_tokens[i], all_tokens[i+1]) for i in range(len(all_tokens)-1)]
        distinct_2 = len(set(bigrams)) / len(bigrams) if bigrams else 0
        
        # Self-BLEU (lower is more diverse)
        self_bleu_scores = []
        for i, text in enumerate(texts):
            others = texts[:i] + texts[i+1:]
            if others:
                bleu = sentence_bleu([self.tokenizer.tokenize(ref) for ref in others], 
                                   self.tokenizer.tokenize(text))
                self_bleu_scores.append(bleu)
                
        avg_self_bleu = np.mean(self_bleu_scores) if self_bleu_scores else 0
        
        return {
            "distinct_1": distinct_1,
            "distinct_2": distinct_2,
            "self_bleu": avg_self_bleu,
            "vocabulary_size": len(set(all_tokens)),
            "total_tokens": len(all_tokens)
        }
        
    def compute_bleu_scores(self, generated: List[str], references: List[str]) -> Dict[str, float]:
        """Compute BLEU scores."""
        
        # Tokenize
        gen_tokens = [self.tokenizer.tokenize(text) for text in generated]
        ref_tokens = [[self.tokenizer.tokenize(text)] for text in references]
        
        # BLEU scores
        bleu_1 = np.mean([sentence_bleu(ref, gen, weights=(1, 0, 0, 0)) 
                         for ref, gen in zip(ref_tokens, gen_tokens)])
        bleu_2 = np.mean([sentence_bleu(ref, gen, weights=(0.5, 0.5, 0, 0)) 
                         for ref, gen in zip(ref_tokens, gen_tokens)])
        bleu_4 = np.mean([sentence_bleu(ref, gen) for ref, gen in zip(ref_tokens, gen_tokens)])
        
        # SacreBLEU for comparison
        try:
            sacrebleu_score = sacrebleu.corpus_bleu(generated, [references]).score
        except:
            sacrebleu_score = 0
            
        return {
            "bleu_1": bleu_1,
            "bleu_2": bleu_2,
            "bleu_4": bleu_4,
            "sacrebleu": sacrebleu_score
        }
        
    def compute_rouge_scores(self, generated: List[str], references: List[str]) -> Dict[str, float]:
        """Compute ROUGE scores."""
        rouge_1_scores = []
        rouge_2_scores = []
        rouge_l_scores = []
        
        for gen, ref in zip(generated, references):
            scores = self.rouge_scorer.score(ref, gen)
            rouge_1_scores.append(scores['rouge1'].fmeasure)
            rouge_2_scores.append(scores['rouge2'].fmeasure)
            rouge_l_scores.append(scores['rougeL'].fmeasure)
            
        return {
            "rouge_1": np.mean(rouge_1_scores),
            "rouge_2": np.mean(rouge_2_scores),
            "rouge_l": np.mean(rouge_l_scores)
        }
        
    def compute_bert_scores(self, generated: List[str], references: List[str]) -> Dict[str, float]:
        """Compute BERTScore for semantic similarity."""
        try:
            P, R, F1 = bert_score(generated, references, lang="en", verbose=False)
            return {
                "bert_precision": P.mean().item(),
                "bert_recall": R.mean().item(),
                "bert_f1": F1.mean().item()
            }
        except Exception as e:
            self.logger.warning(f"Could not compute BERTScore: {e}")
            return {"bert_f1": 0, "bert_precision": 0, "bert_recall": 0}
            
    def compute_quality_metrics(self, texts: List[str]) -> Dict[str, float]:
        """Compute text quality metrics."""
        
        # Length statistics
        lengths = [len(text.split()) for text in texts]
        
        # Repetition analysis
        repetition_scores = []
        for text in texts:
            words = text.lower().split()
            if len(words) > 1:
                unique_words = len(set(words))
                repetition = 1 - (unique_words / len(words))
                repetition_scores.append(repetition)
                
        # Readability (simple heuristic)
        avg_word_length = np.mean([np.mean([len(word) for word in text.split()]) 
                                  for text in texts if text.split()])
        
        return {
            "avg_length": np.mean(lengths),
            "length_std": np.std(lengths),
            "avg_repetition": np.mean(repetition_scores) if repetition_scores else 0,
            "avg_word_length": avg_word_length,
        }
        
    def run_comprehensive_evaluation(self) -> Dict[str, Any]:
        """Run complete evaluation pipeline."""
        self.logger.info("=== Starting Comprehensive Model Evaluation ===")
        
        start_time = time.time()
        all_results = {}
        
        # Load evaluation datasets
        eval_datasets = self.load_evaluation_data()
        
        if not eval_datasets:
            self.logger.warning("No evaluation datasets loaded")
            return all_results
            
        for dataset_name, dataset in eval_datasets:
            self.logger.info(f"\n--- Evaluating on {dataset_name} ---")
            
            # Sample data if too large
            if len(dataset) > self.config.max_samples:
                dataset = dataset.select(range(self.config.max_samples))
                self.logger.info(f"Sampled {self.config.max_samples} examples for evaluation")
                
            # Prepare texts
            text_column = "text" if "text" in dataset.column_names else dataset.column_names[0]
            texts = dataset[text_column]
            
            results = {"dataset_name": dataset_name, "num_samples": len(texts)}
            
            # 1. Compute perplexity
            if self.config.compute_perplexity:
                ppl_results = self.compute_perplexity(texts)
                results.update(ppl_results)
                self.logger.info(f"Perplexity: {ppl_results['perplexity']:.2f}")
                
            # 2. Generate text samples for quality evaluation
            if any([self.config.compute_bleu, self.config.compute_rouge, 
                   self.config.compute_diversity, self.config.compute_bert_score]):
                
                # Use first part of text as prompt, rest as reference
                prompts = []
                references = []
                for text in texts[:min(100, len(texts))]:  # Limit for generation
                    words = text.split()
                    if len(words) > 20:  # Ensure enough content
                        prompt_len = len(words) // 3
                        prompt = " ".join(words[:prompt_len])
                        reference = " ".join(words[prompt_len:])
                        prompts.append(prompt)
                        references.append(reference)
                        
                if prompts:
                    # Generate completions
                    generated = self.generate_text(prompts)
                    
                    # Compute text quality metrics
                    quality_metrics = self.compute_text_quality_metrics(generated, references)
                    results.update(quality_metrics)
                    
                    self.logger.info(f"Generated {len(generated)} samples")
                    if 'distinct_1' in quality_metrics:
                        self.logger.info(f"Distinct-1: {quality_metrics['distinct_1']:.3f}")
                    if 'bleu_4' in quality_metrics:
                        self.logger.info(f"BLEU-4: {quality_metrics['bleu_4']:.3f}")
                        
                    # Save generations if requested
                    if self.config.save_generations:
                        gen_data = pd.DataFrame({
                            'prompt': prompts,
                            'reference': references,
                            'generated': generated
                        })
                        gen_file = self.output_dir / "generations" / f"{dataset_name}_generations.csv"
                        gen_data.to_csv(gen_file, index=False)
                        self.logger.info(f"Generations saved to {gen_file}")
                        
            all_results[dataset_name] = results
            
        # Compute overall statistics
        total_time = time.time() - start_time
        all_results["evaluation_summary"] = {
            "total_datasets": len(eval_datasets),
            "evaluation_time": total_time,
            "timestamp": pd.Timestamp.now().isoformat(),
            "model_path": self.config.model_path,
            "config": self.config.__dict__
        }
        
        # Save results
        self.save_evaluation_results(all_results)
        
        self.logger.info(f"\n=== Evaluation Complete ({total_time:.2f}s) ===")
        return all_results
        
    def save_evaluation_results(self, results: Dict[str, Any]):
        """Save evaluation results to files."""
        
        # Save detailed results as JSON
        results_file = self.output_dir / "evaluation_results.json"
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
            
        # Create summary report
        summary_data = []
        for dataset_name, dataset_results in results.items():
            if dataset_name == "evaluation_summary":
                continue
                
            summary_row = {"dataset": dataset_name}
            
            # Key metrics
            for metric in ["perplexity", "bleu_4", "rouge_l", "distinct_1", "bert_f1"]:
                if metric in dataset_results:
                    summary_row[metric] = dataset_results[metric]
                    
            summary_data.append(summary_row)
            
        # Save summary as CSV
        if summary_data:
            summary_df = pd.DataFrame(summary_data)
            summary_file = self.output_dir / "evaluation_summary.csv"
            summary_df.to_csv(summary_file, index=False)
            self.logger.info(f"Evaluation summary saved to {summary_file}")
            
        self.logger.info(f"Detailed results saved to {results_file}")


def main():
    """Main function for running model evaluation."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Comprehensive Model Evaluation")
    parser.add_argument("--model-path", type=str, required=True, help="Path to fine-tuned model")
    parser.add_argument("--test-data", type=str, help="Path to test dataset")
    parser.add_argument("--output-dir", type=str, default="./evaluation_results")
    parser.add_argument("--max-samples", type=int, default=1000, help="Maximum samples to evaluate")
    parser.add_argument("--batch-size", type=int, default=8, help="Evaluation batch size")
    
    args = parser.parse_args()
    
    # Create evaluation configuration
    config = EvaluationConfig(
        model_path=args.model_path,
        test_data_path=args.test_data,
        output_dir=args.output_dir,
        max_samples=args.max_samples,
        batch_size=args.batch_size
    )
    
    # Run evaluation
    evaluator = ComprehensiveEvaluator(config)
    results = evaluator.run_comprehensive_evaluation()
    
    print("\n=== Evaluation Summary ===")
    for dataset_name, dataset_results in results.items():
        if dataset_name == "evaluation_summary":
            continue
        print(f"\n{dataset_name}:")
        for metric in ["perplexity", "bleu_4", "rouge_l", "distinct_1"]:
            if metric in dataset_results:
                print(f"  {metric}: {dataset_results[metric]:.4f}")


if __name__ == "__main__":
    main()