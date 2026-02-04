"""LLM module for Qwen2-VL-2B-Instruct inference."""

import logging
from functools import lru_cache
from typing import Optional

import torch
from PIL import Image
from transformers import AutoProcessor, Qwen2VLForConditionalGeneration

logger = logging.getLogger(__name__)

MODEL_ID = "Qwen/Qwen2-VL-2B-Instruct"

_model: Optional[Qwen2VLForConditionalGeneration] = None
_processor: Optional[AutoProcessor] = None


def get_device() -> str:
    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


@lru_cache(maxsize=1)
def load_model() -> tuple[Qwen2VLForConditionalGeneration, AutoProcessor]:
    """Load and cache the Qwen2-VL model and processor."""
    global _model, _processor

    if _model is not None and _processor is not None:
        return _model, _processor

    logger.info(f"Loading model {MODEL_ID}...")
    device = get_device()
    logger.info(f"Using device: {device}")

    try:
        _processor = AutoProcessor.from_pretrained(MODEL_ID, local_files_only=True)
        _model = Qwen2VLForConditionalGeneration.from_pretrained(
            MODEL_ID,
            torch_dtype=torch.float16 if device == "cuda" else torch.float32,
            device_map="auto" if device == "cuda" else None,
            local_files_only=True,
        )
        logger.info("Loaded from local cache")
    except OSError:
        logger.info("Model not in cache, downloading...")
        _processor = AutoProcessor.from_pretrained(MODEL_ID)
        _model = Qwen2VLForConditionalGeneration.from_pretrained(
            MODEL_ID,
            torch_dtype=torch.float16 if device == "cuda" else torch.float32,
            device_map="auto" if device == "cuda" else None,
        )

    if device == "cpu":
        _model = _model.to(device)

    logger.info("Model loaded successfully")
    return _model, _processor


def image_inference(image: Image.Image, prompt: str, max_tokens: int = 2048) -> str:
    """
    Run inference on an image with a text prompt.

    Args:
        image: PIL Image to analyze
        prompt: Text prompt describing what to extract
        max_tokens: Maximum tokens to generate

    Returns:
        Generated text response
    """
    model, processor = load_model()

    # Prepare messages in Qwen2-VL format
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image", "image": image},
                {"type": "text", "text": prompt},
            ],
        }
    ]

    # Process inputs
    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)

    # Use qwen_vl_utils for image processing if available
    try:
        from qwen_vl_utils import process_vision_info
        image_inputs, video_inputs = process_vision_info(messages)
        inputs = processor(
            text=[text],
            images=image_inputs,
            videos=video_inputs,
            padding=True,
            return_tensors="pt",
        )
    except ImportError:
        # Fallback without qwen_vl_utils
        inputs = processor(
            text=[text],
            images=[image],
            padding=True,
            return_tensors="pt",
        )

    inputs = inputs.to(model.device)

    # Generate
    with torch.no_grad():
        generated_ids = model.generate(
            **inputs,
            max_new_tokens=max_tokens,
            do_sample=False,
            pad_token_id=processor.tokenizer.pad_token_id,
        )

    # Decode only the new tokens
    generated_ids_trimmed = [
        out_ids[len(in_ids):]
        for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
    ]
    output_text = processor.batch_decode(
        generated_ids_trimmed,
        skip_special_tokens=True,
        clean_up_tokenization_spaces=False
    )[0]

    return output_text.strip()


def text_inference(text: str, prompt: str, max_tokens: int = 2048) -> str:
    """
    Run inference on text input (for XML/text-based diagrams).

    Args:
        text: Text content to analyze
        prompt: Text prompt describing what to extract
        max_tokens: Maximum tokens to generate

    Returns:
        Generated text response
    """
    model, processor = load_model()

    # For text-only input, combine content and prompt
    full_prompt = f"{prompt}\n\nContent to analyze:\n{text}"

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": full_prompt},
            ],
        }
    ]

    text_input = processor.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )
    inputs = processor(
        text=[text_input],
        padding=True,
        return_tensors="pt",
    )
    inputs = inputs.to(model.device)

    # Generate
    with torch.no_grad():
        generated_ids = model.generate(
            **inputs,
            max_new_tokens=max_tokens,
            do_sample=False,
            pad_token_id=processor.tokenizer.pad_token_id,
        )

    generated_ids_trimmed = [
        out_ids[len(in_ids):]
        for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
    ]
    output_text = processor.batch_decode(
        generated_ids_trimmed,
        skip_special_tokens=True,
        clean_up_tokenization_spaces=False
    )[0]

    return output_text.strip()


def warmup() -> bool:
    """
    Warm up the model by loading it.

    Returns:
        True if successful, False otherwise
    """
    try:
        load_model()
        return True
    except Exception as e:
        logger.error(f"Failed to warm up model: {e}")
        return False


if __name__ == "__main__":
    # Quick test
    logging.basicConfig(level=logging.INFO)
    print("Testing LLM module...")

    if warmup():
        print("Model loaded successfully!")

        # Test with a simple text inference
        result = text_inference(
            "A -> B: Hello\nB -> A: Hi",
            "What are the steps in this sequence?"
        )
        print(f"Text inference result: {result[:200]}...")
    else:
        print("Failed to load model")
