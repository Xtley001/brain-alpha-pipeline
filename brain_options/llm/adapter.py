"""
Multi-provider LLM adapter with key rotation and sequential provider fallback.
Supports Groq, Cerebras, OpenRouter, and Google Gemini.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, List, Optional
from brain_options.config import OptionsConfig

log = logging.getLogger("brain_options.llm")


def clean_json_array(text: str) -> list[dict]:
    """Cleans markdown fences or surrounding commentary and parses JSON array.
    
    Resilient against:
    - Conversational text before/after markdown fences
    - Trailing commas before closing brackets
    - Truncated arrays (extracts completed individual JSON objects via brace tracking)
    - Single-quoted JSON or unescaped characters
    """
    if not text:
        return []

    # 1. Strip markdown code fences if present (anywhere in output)
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    cleaned = fence_match.group(1).strip() if fence_match else text.strip()

    # 2. Strip trailing commas before closing brackets/braces
    cleaned_no_commas = re.sub(r",\s*([\]}])", r"\1", cleaned)

    # 3. Direct parse attempt
    try:
        data = json.loads(cleaned_no_commas)
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        elif isinstance(data, dict):
            return [data]
    except (json.JSONDecodeError, ValueError):
        pass

    # 4. Regex array extraction attempt
    match = re.search(r"\[\s*\{[\s\S]*\}\s*\]", cleaned_no_commas)
    if match:
        try:
            data = json.loads(match.group(0))
            if isinstance(data, list):
                return [item for item in data if isinstance(item, dict)]
        except Exception:
            pass

    # 5. Resilient individual JSON object extractor (balanced-brace parsing)
    # Recovers all completed objects even if response was truncated mid-stream
    results: list[dict] = []
    brace_depth = 0
    start_idx = -1
    for idx, ch in enumerate(cleaned):
        if ch == "{":
            if brace_depth == 0:
                start_idx = idx
            brace_depth += 1
        elif ch == "}":
            if brace_depth > 0:
                brace_depth -= 1
                if brace_depth == 0 and start_idx != -1:
                    chunk = cleaned[start_idx : idx + 1]
                    try:
                        chunk_clean = re.sub(r",\s*([\]}])", r"\1", chunk)
                        item = json.loads(chunk_clean)
                        if isinstance(item, dict) and "expression" in item:
                            results.append(item)
                    except Exception:
                        try:
                            item = json.loads(chunk.replace("'", '"'))
                            if isinstance(item, dict) and "expression" in item:
                                results.append(item)
                        except Exception:
                            pass
                    start_idx = -1

    if results:
        log.info("Recovered %d candidate objects via resilient brace parser.", len(results))
        return results

    log.warning("clean_json_array: Failed to parse or recover any JSON objects from response (length=%d).", len(text))
    return []


class LLMAdapter:
    def __init__(self, config: OptionsConfig):
        self.config = config

    def _call_openai_compatible(
        self, base_url: str, api_key: str, model: str, prompt: str, system_prompt: str, temperature: float = 0.7
    ) -> Optional[str]:
        try:
            from openai import OpenAI
            client = OpenAI(base_url=base_url, api_key=api_key, timeout=30.0)
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                temperature=temperature,
            )
            if response.choices and response.choices[0].message.content:
                return response.choices[0].message.content.strip()
        except Exception as e:
            log.warning("Call to %s (%s) failed: %s", base_url, model, e)
        return None

    def _call_gemini(
        self, api_key: str, model: str, prompt: str, system_prompt: str, temperature: float = 0.7
    ) -> Optional[str]:
        try:
            from google import genai
            client = genai.Client(api_key=api_key)
            full_prompt = f"{system_prompt}\n\nUser Task:\n{prompt}"
            resp = client.models.generate_content(
                model=model,
                contents=full_prompt,
                config={"temperature": temperature},
            )
            if resp and resp.text:
                return resp.text.strip()
        except Exception as e:
            log.warning("Gemini call failed (%s): %s", model, e)
        return None

    def generate(self, prompt: str, system_prompt: str, temperature: float = 0.7) -> Optional[str]:
        """Tries configured providers sequentially with key rotation."""
        # 1. Groq (active models)
        for key in self.config.groq_keys:
            for model in [
                "openai/gpt-oss-120b",
                "openai/gpt-oss-20b",
                "qwen/qwen3.8-27b",
                "qwen/qwen3.6-27b",
                "groq/compound",
            ]:
                res = self._call_openai_compatible(
                    base_url="https://api.groq.com/openai/v1",
                    api_key=key,
                    model=model,
                    prompt=prompt,
                    system_prompt=system_prompt,
                    temperature=temperature,
                )
                if res:
                    return res

        # 2. Cerebras
        for key in self.config.cerebras_keys:
            for model in ["llama-3.3-70b", "llama3.1-8b"]:
                res = self._call_openai_compatible(
                    base_url="https://api.cerebras.ai/v1",
                    api_key=key,
                    model=model,
                    prompt=prompt,
                    system_prompt=system_prompt,
                    temperature=temperature,
                )
                if res:
                    return res

        # 3. OpenRouter
        for key in self.config.openrouter_keys:
            for model in [
                "meta-llama/llama-3.3-70b-instruct:free",
                "meta-llama/llama-3.1-8b-instruct:free",
                "mistralai/mistral-7b-instruct:free",
            ]:
                res = self._call_openai_compatible(
                    base_url="https://openrouter.ai/api/v1",
                    api_key=key,
                    model=model,
                    prompt=prompt,
                    system_prompt=system_prompt,
                    temperature=temperature,
                )
                if res:
                    return res

        # 4. Google Gemini (valid model identifiers)
        for key in self.config.gemini_keys:
            for model in ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"]:
                res = self._call_gemini(
                    api_key=key,
                    model=model,
                    prompt=prompt,
                    system_prompt=system_prompt,
                    temperature=temperature,
                )
                if res:
                    return res

        log.error("All LLM providers and keys failed for generation request.")
        return None
