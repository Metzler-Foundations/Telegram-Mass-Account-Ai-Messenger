"""Prompt templates for gesture-oriented photo packs."""

from __future__ import annotations

from typing import Dict, List


def gesture_prompts() -> Dict[str, str]:
    """Return the canonical prompts used for hand-gesture packs."""

    return {
        "peace_sign": "portrait photo, subject making a peace sign with one hand, natural lighting, sharp focus",
        "thumbs_up": "portrait photo, subject giving a thumbs up, smiling, studio lighting, high detail",
        "finger_guns": "portrait photo, subject making finger guns, playful expression, cinematic light",
        "ok_sign": "portrait photo, subject making an OK sign, confident expression, soft light",
        "rock_on": "portrait photo, subject making rock on gesture, energetic vibe, dramatic lighting",
        "heart_hands": "portrait photo, subject forming a heart with hands, warm mood, soft background blur",
    }


def ordered_prompts() -> List[str]:
    """Return prompts as an ordered list to drive batch generation."""

    prompts = gesture_prompts()
    return [prompts[key] for key in sorted(prompts.keys())]











