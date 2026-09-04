import os
import json
import random
import time
import requests
from pathlib import Path
from dotenv import load_dotenv


# ============================================================
# ENVIRONMENT
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

load_dotenv(PROJECT_ROOT / ".env")


# ============================================================
# CONFIGURATION
# ============================================================

MAX_CHARS = 12000
MAX_RETRIES = 4
TIMEOUT = 60

# Providers disabled during the current program run.
DISABLED_PROVIDERS = set()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")


# ============================================================
# API ENDPOINTS
# ============================================================

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/"
    "v1beta/models/gemini-3.7-flash:generateContent"
)

GROQ_URL = (
    "https://api.groq.com/openai/v1/chat/completions"
)

DEEPSEEK_URL = (
    "https://api.deepseek.com/chat/completions"
)


# ============================================================
# MODELS
# ============================================================

GROQ_MODEL = "openai/gpt-oss-20b"

DEEPSEEK_MODEL = "deepseek-v4-flash"


# ============================================================
# EXTRACTION PROMPT
# ============================================================

SYSTEM_PROMPT = """
You are a data extraction engine.

Convert the supplied raw text into canonical JSON.

Return ONLY valid JSON.

Use exactly these fields:

{
  "entityName": null,
  "description": null,
  "company": null,
  "url": null,
  "category": null,
  "pricingModel": null,
  "employeeCount": null,
  "publishedDate": null,
  "isRemote": null,
  "roleFamily": null
}

Rules:

1. Never invent information.
2. If information is not present, return null.
3. Keep URLs exactly as found.
4. pricingModel must be one of:
   FREE, FREEMIUM, PAID, ENTERPRISE
   or null.
5. employeeCount must only be returned when explicitly supported.
6. publishedDate must only be returned when explicitly supported.
7. isRemote must only be true or false when supported.
8. roleFamily should describe the job family when applicable.
"""


# ============================================================
# EMPTY RESULT
# ============================================================

def empty_result():

    return {
        "entityName": None,
        "description": None,
        "company": None,
        "url": None,
        "category": None,
        "pricingModel": None,
        "employeeCount": None,
        "publishedDate": None,
        "isRemote": None,
        "roleFamily": None
    }


# ============================================================
# CHUNK TEXT
# ============================================================

def chunk_text(text, max_chars=MAX_CHARS):

    if not text:
        return []

    if len(text) <= max_chars:
        return [text]

    chunks = []

    for start in range(0, len(text), max_chars):

        chunks.append(
            text[start:start + max_chars]
        )

    return chunks


# ============================================================
# PARSE JSON
# ============================================================

def parse_json_response(text):

    if not text:
        raise ValueError(
            "Empty LLM response"
        )

    text = text.strip()

    # Remove markdown code fences
    if text.startswith("```"):

        lines = text.splitlines()

        if len(lines) >= 3:

            text = "\n".join(
                lines[1:-1]
            ).strip()

    # Normal JSON
    try:

        result = json.loads(text)

        if not isinstance(result, dict):

            raise ValueError(
                "LLM response is not a JSON object"
            )

        return result

    except json.JSONDecodeError:

        pass

    # JSON embedded inside text
    start = text.find("{")
    end = text.rfind("}")

    if start != -1 and end != -1:

        try:

            result = json.loads(
                text[start:end + 1]
            )

            if isinstance(result, dict):
                return result

        except json.JSONDecodeError:

            pass

    raise ValueError(
        "LLM did not return valid JSON"
    )


# ============================================================
# EXPONENTIAL BACKOFF
# ============================================================

def backoff(attempt):

    delay = min(
        60,
        2 ** attempt
    )

    jitter = random.uniform(
        0,
        1
    )

    total_delay = delay + jitter

    print(
        f"Waiting {total_delay:.2f}s "
        f"before retry..."
    )

    time.sleep(
        total_delay
    )


# ============================================================
# GEMINI
# ============================================================

def call_gemini(text):

    if not GEMINI_API_KEY:

        raise RuntimeError(
            "Gemini API key not configured"
        )

    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": GEMINI_API_KEY
    }

    payload = {

        "system_instruction": {
            "parts": [
                {
                    "text": SYSTEM_PROMPT
                }
            ]
        },

        "contents": [
            {
                "parts": [
                    {
                        "text": text
                    }
                ]
            }
        ],

        "generationConfig": {
            "responseMimeType": "application/json"
        }
    }

    for attempt in range(MAX_RETRIES):

        response = requests.post(
            GEMINI_URL,
            headers=headers,
            json=payload,
            timeout=TIMEOUT
        )

        if response.status_code == 401:

            raise RuntimeError(
                "Gemini 401 Unauthorized"
            )

        if response.status_code == 413:

            raise RuntimeError("413")

        if response.status_code == 429:

            print(
                "Gemini: 429 rate limit"
            )

            if attempt < MAX_RETRIES - 1:

                backoff(attempt)

                continue

            raise RuntimeError(
                "Gemini 429 rate limit"
            )

        response.raise_for_status()

        data = response.json()

        candidates = data.get(
            "candidates",
            []
        )

        if not candidates:

            raise RuntimeError(
                "Gemini returned no candidates"
            )

        parts = (
            candidates[0]
            .get("content", {})
            .get("parts", [])
        )

        if not parts:

            raise RuntimeError(
                "Gemini returned no content"
            )

        result = parts[0].get(
            "text",
            ""
        )

        return parse_json_response(
            result
        )

    raise RuntimeError(
        "Gemini failed"
    )


# ============================================================
# GROQ
# ============================================================

def call_groq(text):

    if not GROQ_API_KEY:

        raise RuntimeError(
            "Groq API key not configured"
        )

    headers = {
        "Authorization":
            f"Bearer {GROQ_API_KEY}",

        "Content-Type":
            "application/json"
    }

    payload = {

        "model": GROQ_MODEL,

        "messages": [

            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },

            {
                "role": "user",
                "content": text
            }
        ],

        "temperature": 0,

        "response_format": {
            "type": "json_object"
        }
    }

    for attempt in range(MAX_RETRIES):

        response = requests.post(
            GROQ_URL,
            headers=headers,
            json=payload,
            timeout=TIMEOUT
        )

        if response.status_code == 401:

            raise RuntimeError(
                "Groq 401 Unauthorized"
            )

        if response.status_code == 404:

            raise RuntimeError(
                "Groq 404 - model or endpoint not found"
            )

        if response.status_code == 413:

            raise RuntimeError("413")

        if response.status_code == 429:

            print(
                "Groq: 429 rate limit"
            )

            if attempt < MAX_RETRIES - 1:

                backoff(attempt)

                continue

            raise RuntimeError(
                "Groq 429 rate limit"
            )

        response.raise_for_status()

        data = response.json()

        choices = data.get(
            "choices",
            []
        )

        if not choices:

            raise RuntimeError(
                "Groq returned no choices"
            )

        result = (
            choices[0]
            .get("message", {})
            .get("content", "")
        )

        return parse_json_response(
            result
        )

    raise RuntimeError(
        "Groq failed"
    )


# ============================================================
# DEEPSEEK
# ============================================================

def call_deepseek(text):

    if not DEEPSEEK_API_KEY:

        raise RuntimeError(
            "DeepSeek API key not configured"
        )

    headers = {

        "Authorization":
            f"Bearer {DEEPSEEK_API_KEY}",

        "Content-Type":
            "application/json"
    }

    payload = {

        "model": DEEPSEEK_MODEL,

        "messages": [

            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },

            {
                "role": "user",
                "content": text
            }
        ],

        "temperature": 0,

        "response_format": {
            "type": "json_object"
        }
    }

    for attempt in range(MAX_RETRIES):

        response = requests.post(
            DEEPSEEK_URL,
            headers=headers,
            json=payload,
            timeout=TIMEOUT
        )

        if response.status_code == 401:

            raise RuntimeError(
                "DeepSeek 401 Unauthorized"
            )

        if response.status_code == 404:

            raise RuntimeError(
                "DeepSeek 404 - model or endpoint not found"
            )

        if response.status_code == 413:

            raise RuntimeError("413")

        if response.status_code == 429:

            print(
                "DeepSeek: 429 rate limit"
            )

            if attempt < MAX_RETRIES - 1:

                backoff(attempt)

                continue

            raise RuntimeError(
                "DeepSeek 429 rate limit"
            )

        response.raise_for_status()

        data = response.json()

        choices = data.get(
            "choices",
            []
        )

        if not choices:

            raise RuntimeError(
                "DeepSeek returned no choices"
            )

        result = (
            choices[0]
            .get("message", {})
            .get("content", "")
        )

        return parse_json_response(
            result
        )

    raise RuntimeError(
        "DeepSeek failed"
    )


# ============================================================
# AVAILABLE PROVIDERS
# ============================================================

def get_providers():

    providers = []

    if (
        GEMINI_API_KEY
        and "Gemini" not in DISABLED_PROVIDERS
    ):

        providers.append(
            (
                "Gemini",
                call_gemini
            )
        )

    if (
        GROQ_API_KEY
        and "Groq" not in DISABLED_PROVIDERS
    ):

        providers.append(
            (
                "Groq",
                call_groq
            )
        )

    if (
        DEEPSEEK_API_KEY
        and "DeepSeek" not in DISABLED_PROVIDERS
    ):

        providers.append(
            (
                "DeepSeek",
                call_deepseek
            )
        )

    return providers


# ============================================================
# MERGE RESULTS
# ============================================================

def merge_results(results):

    merged = empty_result()

    for result in results:

        if not isinstance(
            result,
            dict
        ):
            continue

        for key in merged:

            value = result.get(
                key
            )

            if (
                merged[key] is None
                and value is not None
            ):

                merged[key] = value

    return merged


# ============================================================
# MAIN FALLBACK
# ============================================================

def extract_with_fallback(text):

    if not text or not text.strip():

        return empty_result()

    chunks = chunk_text(
        text
    )

    print(
        f"Text length: "
        f"{len(text)} characters"
    )

    print(
        f"Number of chunks: "
        f"{len(chunks)}"
    )

    results = []

    # ========================================================
    # EACH CHUNK
    # ========================================================

    for index, chunk in enumerate(
        chunks,
        start=1
    ):

        print(
            f"\nProcessing chunk "
            f"{index}/{len(chunks)}"
        )

        extracted = None

        # Get providers fresh each time
        # because a provider can be disabled
        # during the run.

        providers = get_providers()

        if not providers:

            print(
                "No available LLM providers."
            )

            break

        # ====================================================
        # TRY PROVIDERS
        # ====================================================

        for provider_name, provider_function in providers:

            try:

                print(
                    f"Trying {provider_name}..."
                )

                extracted = provider_function(
                    chunk
                )

                print(
                    f"{provider_name} succeeded."
                )

                break

            except RuntimeError as error:

                error_message = str(
                    error
                )

                print(
                    f"{provider_name} failed: "
                    f"{error_message}"
                )

                # --------------------------------------------
                # RATE LIMIT
                # --------------------------------------------

                if "429" in error_message:

                    print(
                        f"Disabling "
                        f"{provider_name} "
                        f"for the rest of "
                        f"this run."
                    )

                    DISABLED_PROVIDERS.add(
                        provider_name
                    )

                    continue

                # --------------------------------------------
                # PAYLOAD TOO LARGE
                # --------------------------------------------

                if error_message == "413":

                    smaller_chunks = chunk_text(
                        chunk,
                        max_chars=max(
                            2000,
                            MAX_CHARS // 2
                        )
                    )

                    print(
                        f"413 received. "
                        f"Splitting into "
                        f"{len(smaller_chunks)} "
                        f"smaller chunks."
                    )

                    for smaller_chunk in smaller_chunks:

                        smaller_result = None

                        smaller_providers = (
                            get_providers()
                        )

                        for (
                            smaller_provider_name,
                            smaller_provider
                        ) in smaller_providers:

                            try:

                                print(
                                    f"Trying "
                                    f"{smaller_provider_name} "
                                    f"on smaller chunk..."
                                )

                                smaller_result = (
                                    smaller_provider(
                                        smaller_chunk
                                    )
                                )

                                print(
                                    f"{smaller_provider_name} "
                                    f"succeeded."
                                )

                                break

                            except RuntimeError as smaller_error:

                                smaller_message = str(
                                    smaller_error
                                )

                                print(
                                    f"{smaller_provider_name} "
                                    f"failed: "
                                    f"{smaller_message}"
                                )

                                if "429" in smaller_message:

                                    DISABLED_PROVIDERS.add(
                                        smaller_provider_name
                                    )

                                continue

                            except Exception as smaller_error:

                                print(
                                    f"{smaller_provider_name} "
                                    f"unexpected error: "
                                    f"{smaller_error}"
                                )

                                continue

                        if smaller_result is not None:

                            results.append(
                                smaller_result
                            )

                    extracted = None

                    break

                # 401, 404 and other errors:
                # try the next provider.

                continue

            except Exception as error:

                print(
                    f"{provider_name} "
                    f"unexpected error: "
                    f"{error}"
                )

                continue

        # ----------------------------------------------------
        # Successful extraction
        # ----------------------------------------------------

        if extracted is not None:

            results.append(
                extracted
            )

    # ========================================================
    # FINAL RESULT
    # ========================================================

    return merge_results(
        results
    )


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    sample_text = """
    OpenAI is an artificial intelligence
    research and deployment company.

    Website: https://openai.com

    OpenAI develops artificial intelligence
    systems and products.
    """

    result = extract_with_fallback(
        sample_text
    )

    print(
        "\n=== LLM RESULT ==="
    )

    print(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False
        )
    )