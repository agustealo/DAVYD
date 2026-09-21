from __future__ import annotations

EXAMPLE_SCHEMAS = {
    "Sentiment Analysis": {
        "text": {"type": "text", "description": "Natural-language input", "required": True},
        "intent": {"type": "category", "description": "Primary user intent", "required": True},
        "sentiment": {"type": "category", "description": "positive, neutral, or negative", "required": True},
        "sentiment_polarity": {"type": "number", "description": "Polarity from -1 to 1", "constraints": {"min": -1, "max": 1}},
        "tone": {"type": "category", "description": "Communication tone"},
        "category": {"type": "category", "description": "Subject/domain grouping"},
        "keywords": {"type": "text", "description": "Concise keywords"},
    },
    "Customer Support": {
        "customer_message": {"type": "text", "description": "Customer request", "required": True},
        "intent": {"type": "category", "description": "Support intent", "required": True},
        "priority": {"type": "category", "description": "low, medium, high, urgent", "required": True},
        "sentiment": {"type": "category", "description": "Customer sentiment"},
        "resolution": {"type": "text", "description": "Appropriate support resolution", "required": True},
    },
    "Product Catalog": {
        "product_name": {"type": "text", "required": True},
        "category": {"type": "category", "required": True},
        "description": {"type": "text", "required": True},
        "price": {"type": "number", "constraints": {"min": 0}, "required": True},
        "in_stock": {"type": "boolean", "required": True},
    },
}
