"""Replicate-backed image generation utilities.

This module provides:
- A legacy `ReplicateGenerator` (single-step generation).
- A modern `ReplicateLoraWorkflow` for identity LoRA training + photorealistic generation.

Note: Replicate model schemas vary. `ReplicateLoraWorkflow` is configurable via settings/env so
you can swap training/generation models without changing code.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import httpx
import replicate

logger = logging.getLogger(__name__)


class ReplicateGenerator:
    """Generate packs using a Replicate model (legacy path).

    This class fixes the previous bug where a raw file handle was passed to Replicate.
    Replicate expects a Replicate File (or URL) for file inputs.
    """

    def __init__(
        self,
        api_token: str,
        model: str = "tstramer/any-illustration-diffusion",
    ) -> None:
        self.client = replicate.Client(api_token=api_token)
        self.model = model

    async def _download_image(self, url: str, destination: Path) -> None:
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.get(url)
            response.raise_for_status()
            destination.write_bytes(response.content)

    async def generate_batch(
        self,
        prompts: Iterable[str],
        reference_images: List[Path],
        output_dir: Path,
    ) -> List[Path]:
        """Generate images for each prompt.

        Returns a list of downloaded image paths (may be empty if generation fails).
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        results: List[Path] = []

        ref_file: Optional[replicate.file.File] = None
        if reference_images:
            try:
                ref_file = await self.client.files.async_create(reference_images[0])
            except Exception as exc:  # noqa: BLE001
                logger.exception("Failed to upload reference image to Replicate: %s", exc)
                ref_file = None

        for idx, prompt in enumerate(prompts):
            try:
                input_payload: Dict[str, Any] = {"prompt": prompt}
                if ref_file is not None:
                    input_payload["image"] = ref_file

                urls = await self.client.async_run(self.model, input_payload)

                if not urls:
                    logger.warning("Replicate returned empty output for prompt index %s", idx)
                    continue

                # Handle both single URL string and list/iterable of URLs
                if isinstance(urls, str):
                    urls_list = [urls]
                elif isinstance(urls, (list, tuple)):
                    urls_list = list(urls)
                else:
                    try:
                        urls_list = list(urls)
                    except TypeError:
                        urls_list = []

                for url_index, url in enumerate(urls_list):
                    if not url:
                        continue
                    destination = output_dir / f"gesture_{idx}_{url_index}.png"
                    try:
                        await self._download_image(str(url), destination)
                        results.append(destination)
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("Failed to download image %s: %s", url, exc)
                        continue

            except Exception as exc:  # noqa: BLE001
                logger.exception("Failed to generate image for prompt %s: %s", idx, exc)
                continue

        return results


class ReplicateLoraWorkflow:
    """Identity LoRA training + photorealistic generation workflow.

    This wrapper is intentionally configurable because Replicate trainer / generator
    models have different input schemas.
    """

    def __init__(
        self,
        api_token: str,
        training_model: str,
        training_version: Optional[str] = None,
        training_params_json: Optional[str] = None,
        trigger_word: str = "TOK",
        generation_params_json: Optional[str] = None,
        default_negative_prompt: Optional[str] = None,
    ) -> None:
        self.client = replicate.Client(api_token=api_token)

        self.training_model = training_model
        self.training_version = training_version
        self.trigger_word = trigger_word

        self.training_params: Dict[str, Any] = {}
        if training_params_json:
            try:
                self.training_params = json.loads(training_params_json)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Invalid REPLICATE_TRAINING_PARAMS_JSON: %s", exc)

        self.generation_params: Dict[str, Any] = {}
        if generation_params_json:
            try:
                self.generation_params = json.loads(generation_params_json)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Invalid REPLICATE_GENERATION_PARAMS_JSON: %s", exc)

        self.default_negative_prompt = default_negative_prompt or (
            "cgi, 3d, plastic skin, doll, waxy, blurry, lowres, bad anatomy, bad hands, "
            "extra fingers, deformed, text, watermark, logo, oversharpen, artifacts, "
            "airbrushed, unnatural skin, uncanny, anime"
        )

    async def start_training(
        self,
        dataset_zip_path: Path,
        destination: str,
        trigger_word: Optional[str] = None,
    ) -> replicate.training.Training:
        """Start a Replicate training job.

        `destination` is required by the Replicate trainings API (where the model is published).

        Important: many Replicate training models expect `input_images` to be a zip file.
        Passing the Path directly allows the SDK to handle file encoding/upload correctly.
        """
        # Default schema used by many LoRA trainers (override via REPLICATE_TRAINING_PARAMS_JSON)
        training_input: Dict[str, Any] = {
            "input_images": dataset_zip_path,
            "trigger_word": trigger_word or self.trigger_word,
        }
        training_input.update(self.training_params)

        logger.info(
            "Starting Replicate training model=%s version=%s destination=%s input_keys=%s",
            self.training_model,
            self.training_version,
            destination,
            sorted(training_input.keys()),
        )

        training = await self.client.trainings.async_create(
            model=self.training_model,
            version=self.training_version,
            input=training_input,
            destination=destination,
        )
        return training

    async def get_training(self, training_id: str) -> replicate.training.Training:
        return await self.client.trainings.async_get(training_id)

    async def _download_image(self, url: str, destination: Path) -> None:
        async with httpx.AsyncClient(timeout=180) as client:
            response = await client.get(url)
            response.raise_for_status()
            destination.write_bytes(response.content)

    async def generate_batch(
        self,
        trained_model: str,
        prompts: Iterable[str],
        output_dir: Path,
        negative_prompt: Optional[str] = None,
    ) -> List[Path]:
        """Generate images using the trained model.

        `trained_model` should be the destination model (e.g. "owner/model") or a fully qualified version.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        results: List[Path] = []

        neg = negative_prompt or self.default_negative_prompt

        for idx, prompt in enumerate(prompts):
            # The most common schema is `prompt`/`negative_prompt` (override via REPLICATE_GENERATION_PARAMS_JSON)
            input_payload: Dict[str, Any] = {
                "prompt": prompt,
                "negative_prompt": neg,
            }
            input_payload.update(self.generation_params)

            output = await self.client.async_run(trained_model, input_payload)

            if not output:
                logger.warning("Replicate returned empty output for generation index %s", idx)
                continue

            if isinstance(output, str):
                urls_list = [output]
            elif isinstance(output, (list, tuple)):
                urls_list = list(output)
            else:
                try:
                    urls_list = list(output)
                except TypeError:
                    urls_list = []

            for url_index, url in enumerate(urls_list):
                if not url:
                    continue
                destination = output_dir / f"image_{idx:03d}_{url_index}.png"
                await self._download_image(str(url), destination)
                results.append(destination)

        return results
