"""USD per million tokens, always charged at the uncached rate."""

from decimal import Decimal
import re


CONSERVATIVE_PRICE = (3.00, 15.00)
PRICES = {
    "muse-wonder-1.0": (4.00, 20.00),
    "qwen3p8-max": (2.00, 6.00),
    "glm-5p3": (1.40, 4.40),
    "muse-spark-1.1": (1.25, 4.25),
    "muse-spark-1.2": (1.25, 4.25),
    "muse-spark-1.3": (1.25, 4.25),
    "muse-ember-1.0": (0.10, 0.50),
    "kimi-k3.1-pro": (2.00, 10.00),
    "kimi-k3p1-pro": (2.00, 10.00),
    "ember-1": (3.00, 15.00),
    "deepseek-v4.1-flash": (0.30, 1.20),
    "deepseek-v4p1-flash": (0.30, 1.20),
    "minimax-m3.1-flash": (0.15, 0.60),
    "minimax-m3p1-flash": (0.15, 0.60),
}


def price_for_model(model: str) -> tuple[float, float]:
    # Accept Fireworks' accounts/<account>/models/<id> form without guessing
    # prices for version suffixes or unrelated models containing a known name.
    name = re.sub(r"[ _]+", "-", model.rsplit("/", 1)[-1].lower())
    return PRICES.get(name, CONSERVATIVE_PRICE)


def cost_usd(model: str, input_tokens: int, output_tokens: int, *, provider: str | None = None) -> float:
    if any(type(n) is not int or n < 0 for n in (input_tokens, output_tokens)):
        raise ValueError("Token counts must be non-negative integers")
    # Modal bills GPU runtime under its workspace limits, not model tokens.
    # Key this on provider so the same weights hosted elsewhere still cost money.
    if provider == "modal":
        return 0.0
    incoming, outgoing = (Decimal(str(p)) for p in price_for_model(model))
    return float((incoming * input_tokens + outgoing * output_tokens) / 1_000_000)
