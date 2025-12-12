"""Replicate-backed image generation utilities."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Iterable, List

import httpx
import replicate


class ReplicateGenerator:
    """Generate gesture packs using a Replicate model."""

    def __init__(
        self,
        api_token: str,
        model: str = "tstramer/any-illustration-diffusion",
    ) -> None:
        self.client = replicate.Client(api_token=api_token)
        self.model = model

    async def _download_image(self, url: str, destination: Path) -> None:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.get(url)
            response.raise_for_status()
            destination.write_bytes(response.content)

    async def generate_batch(
        self,
        prompts: Iterable[str],
        reference_images: List[Path],
        output_dir: Path,
    ) -> List[Path]:
        """Generate images for each prompt; text-only model defaults when no refs."""

        output_dir.mkdir(parents=True, exist_ok=True)
        results: List[Path] = []

        # Replicate calls are synchronous; offload to thread to avoid blocking loop.
        for idx, prompt in enumerate(prompts):
            try:
                input_payload = {"prompt": prompt}
                if reference_images:
                    with open(reference_images[0], "rb") as ref_img:
                        input_payload["image"] = ref_img
                        urls = await asyncio.to_thread(
                            self.client.run, self.model, input_payload
                        )
                else:
                    urls = await asyncio.to_thread(self.client.run, self.model, input_payload)
                
                if not urls:
                    continue

                # Handle both single URL string and list of URLs
                if isinstance(urls, str):
                    urls = [urls]
                elif not isinstance(urls, (list, tuple)):
                    urls = list(urls) if urls else []

                for url_index, url in enumerate(urls):
                    if not url:
                        continue
                    destination = output_dir / f"gesture_{idx}_{url_index}.png"
                    try:
                        await self._download_image(url, destination)
                        results.append(destination)
                    except Exception as e:
                        # Log but continue with other images
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.warning(f"Failed to download image {url}: {e}")
                        continue
            except Exception as e:
                # Log but continue with other prompts
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Failed to generate image for prompt {idx}: {e}")
                continue

        return results





