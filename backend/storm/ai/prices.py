"""USD per million tokens, always charged at the uncached rate."""

from decimal import Decimal
import re


CONSERVATIVE_PRICE = (3.00, 15.00)
PRICES = {
    "muse-spark-1.1": (1.25, 4.25),
    "muse-spark-1.2": (1.25, 4.25),
    "muse-spark-1.3": (1.25, 4.25),
    "muse-ember-1.0": (0.10, 0.50),
    "kimi-k3.1-pro": (2.00, 10.00),
    "ember-1": (3.00, 15.00),
    "deepseek-v4.1-flash": (0.30, 1.20),
    "minimax-m3.1-flash": (0.15, 0.60),
}


def price_for_model(model: str) -> tuple[float, float]:
    # Accept Fireworks' accounts/<account>/models/<id> form without guessing
    # prices for version suffixes or unrelated models containing a known name.
    name = re.sub(r"[ _]+", "-", model.rsplit("/", 1)[-1].lower())
    return PRICES.get(name, CONSERVATIVE_PRICE)


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    if any(type(n) is not int or n < 0 for n in (input_tokens, output_tokens)):
        raise ValueError("Token counts must be non-negative integers")
    incoming, outgoing = (Decimal(str(p)) for p in price_for_model(model))
    return float((incoming * input_tokens + outgoing * output_tokens) / 1_000_000)
