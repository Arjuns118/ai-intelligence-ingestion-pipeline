import re
import json
from pathlib import Path


# ============================================================
# PROJECT PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

INPUT_FILE = PROJECT_ROOT / "data" / "processed" / "news.json"

OUTPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "entity_mapping.json"
)


# ============================================================
# SEED ENTITIES
# ============================================================

SEED_ENTITIES = {
    "OpenAI": [
        "openai",
        "open ai",
        "openai inc",
        "openai inc."
    ],

    "Anthropic": [
        "anthropic",
        "anthropic pbc"
    ],

    "Google": [
        "google",
        "google ai",
        "google deepmind",
        "deepmind"
    ],

    "Microsoft": [
        "microsoft",
        "microsoft ai"
    ],

    "Meta": [
        "meta",
        "meta ai",
        "facebook ai"
    ],

    "NVIDIA": [
        "nvidia",
        "nvidia ai"
    ],

    "Mistral AI": [
        "mistral",
        "mistral ai"
    ],

    "Cohere": [
        "cohere",
        "cohere ai"
    ],

    "xAI": [
        "xai",
        "x ai"
    ],

    "Hugging Face": [
        "hugging face",
        "huggingface"
    ],

    "Perplexity": [
        "perplexity",
        "perplexity ai"
    ],

    "Scale AI": [
        "scale ai"
    ],

    "Databricks": [
        "databricks"
    ],

    "Snowflake": [
        "snowflake"
    ],

    "Runway": [
        "runway",
        "runway ai"
    ],

    "Stability AI": [
        "stability ai",
        "stability"
    ],

    "Character AI": [
        "character ai",
        "character.ai"
    ],

    "Inflection AI": [
        "inflection",
        "inflection ai"
    ],

    "ElevenLabs": [
        "elevenlabs",
        "eleven labs"
    ],

    "Synthesia": [
        "synthesia"
    ],

    "Jasper": [
        "jasper",
        "jasper ai"
    ],

    "Replit": [
        "replit"
    ],

    "Cursor": [
        "cursor",
        "cursor ai"
    ],

    "Together AI": [
        "together ai"
    ],

    "Groq": [
        "groq"
    ],

    "Replicate": [
        "replicate"
    ],

    "Weights & Biases": [
        "weights & biases",
        "weights and biases",
        "wandb"
    ],

    "Pinecone": [
        "pinecone"
    ],

    "Weaviate": [
        "weaviate"
    ],

    "Vercel": [
        "vercel"
    ],

    "Midjourney": [
        "midjourney",
        "midjourney ai"
    ],

    "Adobe": [
        "adobe",
        "adobe ai"
    ],

    "Amazon": [
        "amazon",
        "aws",
        "amazon web services"
    ],

    "IBM": [
        "ibm",
        "ibm watson"
    ],

    "Oracle": [
        "oracle",
        "oracle ai"
    ],

    "Salesforce": [
        "salesforce",
        "salesforce ai"
    ],

    "Datadog": [
        "datadog"
    ],

    "Palantir": [
        "palantir",
        "palantir ai"
    ],

    "UiPath": [
        "uipath"
    ],

    "ServiceNow": [
        "servicenow",
        "service now"
    ],

    "Dataiku": [
        "dataiku"
    ],

    "AI21 Labs": [
        "ai21",
        "ai21 labs"
    ],

    "Aleph Alpha": [
        "aleph alpha"
    ],

    "Sakana AI": [
        "sakana",
        "sakana ai"
    ],

    "Writer": [
        "writer",
        "writer ai"
    ],

    "Glean": [
        "glean",
        "glean ai"
    ],

    "Harvey": [
        "harvey",
        "harvey ai"
    ],

    "Mercor": [
        "mercor"
    ]
}


# ============================================================
# NORMALIZE NAME
# ============================================================

def normalize_name(name):

    if not name:
        return ""

    name = name.lower().strip()

    name = name.replace(",", " ")
    name = name.replace(".", " ")

    name = re.sub(
        r"\b(incorporated|inc|corp|corporation|ltd|limited)\b",
        "",
        name
    )

    name = re.sub(
        r"[^a-z0-9& ]",
        " ",
        name
    )

    name = re.sub(
        r"\s+",
        " ",
        name
    )

    return name.strip()


# ============================================================
# BUILD LOOKUP
# ============================================================

def build_lookup():

    lookup = {}

    for canonical, aliases in SEED_ENTITIES.items():

        # Canonical name
        lookup[
            normalize_name(canonical)
        ] = canonical

        # Aliases
        for alias in aliases:

            normalized = normalize_name(
                alias
            )

            if normalized:

                lookup[
                    normalized
                ] = canonical

    return lookup


LOOKUP = build_lookup()


# ============================================================
# RESOLVE ENTITY
# ============================================================

def resolve_entity(name):

    if not name:
        return None

    normalized = normalize_name(
        name
    )

    if normalized in LOOKUP:

        return LOOKUP[
            normalized
        ]

    # Unknown entity:
    # preserve original value rather than
    # inventing a canonical mapping.
    return name.strip()


# ============================================================
# TEST
# ============================================================

def test_resolution():

    test_names = [
        "OpenAI",
        "Open AI",
        "OpenAI, Inc.",
        "HuggingFace",
        "Eleven Labs",
        "Google AI"
    ]

    print(
        "Entity resolution test:\n"
    )

    for name in test_names:

        print(
            f"{name} -> "
            f"{resolve_entity(name)}"
        )


# ============================================================
# PROCESS NEWS
# ============================================================

def process_entities():

    if not INPUT_FILE.exists():

        print(
            f"Input file not found:\n"
            f"{INPUT_FILE}"
        )

        return

    with open(
        INPUT_FILE,
        "r",
        encoding="utf-8"
    ) as file:

        records = json.load(file)

    mappings = []

    for record in records:

        content = record.get(
            "content",
            {}
        )

        raw_name = content.get(
            "entityName"
        )

        canonical_name = resolve_entity(
            raw_name
        )

        mapping = {

            "rawEntityName":
                raw_name,

            "canonicalEntityName":
                canonical_name,

            "source":
                record.get(
                    "source",
                    {}
                ),

            "recordType":
                record.get(
                    "recordType"
                )
        }

        mappings.append(
            mapping
        )

        # Update entity name in news record
        content[
            "entityName"
        ] = canonical_name

    # --------------------------------------------------------
    # Save updated news
    # --------------------------------------------------------

    with open(
        INPUT_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            records,
            file,
            indent=2,
            ensure_ascii=False
        )

    # --------------------------------------------------------
    # Save entity mapping log
    # --------------------------------------------------------

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            mappings,
            file,
            indent=2,
            ensure_ascii=False
        )

    print(
        f"\nProcessed entities: "
        f"{len(records)}"
    )

    print(
        f"Mapping log saved to:\n"
        f"{OUTPUT_FILE}"
    )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    test_resolution()

    print(
        "\nProcessing actual news data..."
    )

    process_entities()