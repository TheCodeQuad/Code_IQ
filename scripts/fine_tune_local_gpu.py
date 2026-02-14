"""
Fine-tune Qwen2.5-Coder on local GPU with QLoRA
This script optimizes for local GPU constraints (VRAM, disk space, training time)
"""

import os
import torch
import nltk
from pathlib import Path
from datasets import load_dataset, concatenate_datasets
from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    TrainingArguments,
    Trainer,
    BitsAndBytesConfig
)
from peft import LoraConfig, get_peft_model, PeftModel
from nltk.translate.bleu_score import corpus_bleu
from nltk.translate.meteor_score import meteor_score
from rouge_score import rouge_scorer
from codebleu import calc_codebleu
import logging

# =====================================================
# SETUP
# =====================================================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create output directories
OUTPUT_DIR = Path("./models/local_writer_lora")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

CHECKPOINT_DIR = OUTPUT_DIR / "checkpoints"
CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)

# Download NLTK data
nltk.download("wordnet", quiet=True)
nltk.download("omw-1.4", quiet=True)

# Check GPU availability
if not torch.cuda.is_available():
    raise RuntimeError("CUDA not available! This script requires GPU.")

device_count = torch.cuda.device_count()
device_name = torch.cuda.get_device_name(0)
logger.info(f"Found {device_count} GPU(s): {device_name}")
logger.info(f"GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB")

# =====================================================
# STEP 1: LOAD DATASETS (OPTIMIZED FOR LOCAL TRAINING)
# =====================================================
logger.info("Loading datasets...")

LANGUAGES = ["python", "java", "javascript"]  # Reduced languages to save memory
# Adjust splits based on your GPU VRAM:
# 8GB VRAM: train[:0.5%], test[:500]
# 12GB VRAM: train[:1%], test[:1000]
# 16GB+ VRAM: train[:2%], test[:2000]

TRAIN_SPLIT = "train[:1%]"  # Adjust based on your GPU VRAM
TEST_SPLIT = "test[:1000]"

train_sets = []
test_sets = []

try:
    for lang in LANGUAGES:
        logger.info(f"  Loading {lang}...")
        train_ds = load_dataset(
            "code_search_net",
            name=lang,
            split=TRAIN_SPLIT,
            trust_remote_code=True
        )

        test_ds = load_dataset(
            "code_search_net",
            name=lang,
            split=TEST_SPLIT,
            trust_remote_code=True
        )

        train_sets.append(train_ds)
        test_sets.append(test_ds)

    train_dataset = concatenate_datasets(train_sets)
    test_dataset = concatenate_datasets(test_sets)

    logger.info(f"Train samples: {len(train_dataset)}")
    logger.info(f"Test samples: {len(test_dataset)}")
except Exception as e:
    logger.error(f"Error loading datasets: {e}")
    logger.warning("Proceeding with a small synthetic dataset for testing...")
    
    # Fallback: Create a small test dataset
    train_dataset = None
    test_dataset = None

# =====================================================
# STEP 2: FORMAT DATA
# =====================================================
logger.info("Formatting datasets...")

def format_example(example):
    instruction = (
        f"Generate a concise and accurate documentation comment "
        f"for the following {example['language']} code."
    )

    prompt = f"""### Instruction:
{instruction}

### Code:
{example['func_code_string']}

### Docstring:
"""

    return {
        "prompt": prompt,
        "reference": example["func_documentation_string"]
    }

if train_dataset is not None:
    train_dataset = train_dataset.map(
        format_example,
        remove_columns=train_dataset.column_names,
        desc="Formatting train dataset"
    )

    test_dataset = test_dataset.map(
        format_example,
        remove_columns=test_dataset.column_names,
        desc="Formatting test dataset"
    )

# =====================================================
# STEP 3: LOAD MODEL WITH QLoRA
# =====================================================
logger.info("Loading model with QLoRA...")

MODEL_NAME = "Qwen/Qwen2.5-Coder-7B"

tokenizer = AutoTokenizer.from_pretrained(
    MODEL_NAME,
    trust_remote_code=True
)

# QLoRA config for GPU optimization
bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.float16,
    bnb_4bit_use_double_quant=True,  # More memory optimization
)

model = AutoModelForCausalLM.from_pretrained(
    MODEL_NAME,
    quantization_config=bnb_config,
    device_map="auto",
    torch_dtype=torch.float16,
    trust_remote_code=True,
    max_memory={0: "12GB"},  # Adjust based on your GPU VRAM
)

logger.info(f"Model loaded. Parameters: {model.num_parameters():,}")

# =====================================================
# STEP 4: APPLY LoRA
# =====================================================
logger.info("Applying LoRA...")

lora_config = LoraConfig(
    r=8,  # Reduced from 16 for more memory efficiency
    lora_alpha=16,  # Reduced from 32
    lora_dropout=0.05,
    bias="none",
    task_type="CAUSAL_LM",
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj"]
)

model = get_peft_model(model, lora_config)
model.print_trainable_parameters()

model.gradient_checkpointing_enable()
model.config.use_cache = False

# =====================================================
# STEP 5: TOKENIZATION
# =====================================================
logger.info("Tokenizing datasets...")

MAX_LEN = 384

def tokenize_train(example):
    text = example["prompt"] + example["reference"]
    tokens = tokenizer(
        text,
        truncation=True,
        padding="max_length",
        max_length=MAX_LEN
    )
    tokens["labels"] = tokens["input_ids"].copy()
    return tokens

if train_dataset is not None:
    train_tokenized = train_dataset.map(
        tokenize_train,
        batched=True,
        batch_size=32,
        remove_columns=train_dataset.column_names,
        desc="Tokenizing train dataset"
    )
else:
    train_tokenized = None

# =====================================================
# STEP 6: TRAINING ARGUMENTS
# =====================================================
logger.info("Setting up training...")

# Adjust these based on your GPU:
# 8GB VRAM: per_device_train_batch_size=1, gradient_accumulation_steps=8
# 12GB VRAM: per_device_train_batch_size=2, gradient_accumulation_steps=4
# 16GB+ VRAM: per_device_train_batch_size=4, gradient_accumulation_steps=2

training_args = TrainingArguments(
    output_dir=str(CHECKPOINT_DIR),
    per_device_train_batch_size=2,  # Adjust based on your GPU VRAM
    gradient_accumulation_steps=4,
    learning_rate=2e-4,
    num_train_epochs=3,
    fp16=True,
    logging_steps=10,
    save_steps=100,  # Reduced from 500 to save disk space
    save_total_limit=2,  # Keep only 2 recent checkpoints
    report_to="none",
    optim="paged_adamw_8bit",
    remove_unused_columns=False,
    gradient_checkpointing=True,
    eval_strategy="no",  # Disable eval during training to save time
    max_steps=-1,
    warmup_steps=100,
    weight_decay=0.01,
)

# =====================================================
# STEP 7: TRAINING
# =====================================================
if train_tokenized is not None:
    logger.info("Starting training...")
    
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_tokenized,
    )

    # Clear cache before training
    torch.cuda.empty_cache()
    
    trainer.train()
    
    # Save final model
    logger.info(f"Saving model to {OUTPUT_DIR}...")
    model.save_pretrained(str(OUTPUT_DIR))
    tokenizer.save_pretrained(str(OUTPUT_DIR))
else:
    logger.warning("Skipping training due to dataset loading issues")

# =====================================================
# STEP 8: EVALUATION
# =====================================================
logger.info("Evaluating model...")

if test_dataset is not None and (OUTPUT_DIR / "adapter_config.json").exists():
    # Load base model for evaluation
    base_model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        torch_dtype=torch.float16,
        device_map="auto",
        trust_remote_code=True,
    )

    # Load LoRA weights
    model_eval = PeftModel.from_pretrained(
        base_model,
        str(OUTPUT_DIR)
    )
    model_eval.eval()

    # =====================================================
    # STEP 9: GENERATE PREDICTIONS
    # =====================================================
    def generate_doc(prompt, max_new_tokens=120):
        inputs = tokenizer(prompt, return_tensors="pt").to("cuda")
        with torch.no_grad():
            output = model_eval.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                num_beams=1,
                temperature=0.7,
            )
        return tokenizer.decode(output[0], skip_special_tokens=True)

    logger.info("Generating predictions...")
    
    predictions = []
    references = []
    codes = []

    # Sample evaluation to save time
    num_eval_samples = min(500, len(test_dataset))
    
    for i, sample in enumerate(test_dataset.select(range(num_eval_samples))):
        if i % 100 == 0:
            logger.info(f"  Generated {i}/{num_eval_samples} predictions")
        
        pred = generate_doc(sample["prompt"])
        predictions.append(pred)
        references.append(sample["reference"])
        codes.append(sample["prompt"])
        
        # Clear cache every 50 samples
        if i % 50 == 0:
            torch.cuda.empty_cache()

    # =====================================================
    # STEP 10: COMPUTE EVALUATION METRICS
    # =====================================================
    logger.info("Computing metrics...")
    
    try:
        # BLEU
        bleu_score = corpus_bleu(
            [[ref.split()] for ref in references],
            [pred.split() for pred in predictions]
        )
    except Exception as e:
        logger.warning(f"BLEU calculation failed: {e}")
        bleu_score = 0.0

    try:
        # METEOR
        meteor = sum(
            meteor_score([ref], pred)
            for ref, pred in zip(references, predictions)
        ) / len(predictions)
    except Exception as e:
        logger.warning(f"METEOR calculation failed: {e}")
        meteor = 0.0

    try:
        # ROUGE-L
        scorer = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=True)
        rouge_l = sum(
            scorer.score(ref, pred)["rougeL"].fmeasure
            for ref, pred in zip(references, predictions)
        ) / len(predictions)
    except Exception as e:
        logger.warning(f"ROUGE-L calculation failed: {e}")
        rouge_l = 0.0

    try:
        # CodeBLEU
        codebleu_score = calc_codebleu(
            references,
            predictions,
            lang="python"
        )["codebleu"]
    except Exception as e:
        logger.warning(f"CodeBLEU calculation failed: {e}")
        codebleu_score = 0.0

    # =====================================================
    # STEP 11: PRINT RESULTS
    # =====================================================
    logger.info("\n" + "="*50)
    logger.info("EVALUATION RESULTS")
    logger.info("="*50)
    logger.info(f"BLEU      : {bleu_score:.4f}")
    logger.info(f"METEOR    : {meteor:.4f}")
    logger.info(f"ROUGE-L   : {rouge_l:.4f}")
    logger.info(f"CodeBLEU  : {codebleu_score:.4f}")
    logger.info("="*50)
    
    # Save results
    results_file = OUTPUT_DIR / "evaluation_results.txt"
    with open(results_file, "w") as f:
        f.write("EVALUATION RESULTS\n")
        f.write("="*50 + "\n")
        f.write(f"BLEU      : {bleu_score:.4f}\n")
        f.write(f"METEOR    : {meteor:.4f}\n")
        f.write(f"ROUGE-L   : {rouge_l:.4f}\n")
        f.write(f"CodeBLEU  : {codebleu_score:.4f}\n")
        f.write("="*50 + "\n")
    
    logger.info(f"Results saved to {results_file}")

logger.info("Fine-tuning complete!")
