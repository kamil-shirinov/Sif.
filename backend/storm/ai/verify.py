"""Exact decimal verification, with rounding at the precision actually written.

This checks numeric membership, not which subject a number describes. The
independent inspector checks associations, invented causes and other claims.
"""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
import re


_DIGITS = re.compile(
    r"[+\-−]?(?:\$[+\-−]?)?(?:\d{1,3}(?:,\d{3})+|\d+|(?=\.\d))"
    r"(?:\.\d+)?(?:[eE][+\-]?\d+)?(?:\s?(?:billion|million|thousand|[kKmMbB])\b)?"
)
_SMALL = dict(zip(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split(),
    range(20),
))
_TENS = dict(zip("twenty thirty forty fifty sixty seventy eighty ninety".split(), range(20, 100, 10)))
_SCALES = {"hundred": 100, "thousand": 1000, "million": 1_000_000, "billion": 1_000_000_000}
_WORDS = re.compile(r"\b(?:" + "|".join((*_SMALL, *_TENS, *_SCALES)) + r")\b", re.I)
_SUFFIX = re.compile(r"\s*(billion|million|thousand|[kmb])$", re.I)


def _number_spans(text: str) -> list[tuple[int, int, str]]:
    digits = [(m.start(), m.end(), m.group()) for m in _DIGITS.finditer(text)]
    words = []
    for match in _WORDS.finditer(text):
        if any(start <= match.start() < end for start, end, _ in digits):
            continue
        if words and re.fullmatch(r"(?:[\s-]|and)+", text[words[-1][1]:match.start()]):
            start, _, previous = words.pop()
            words.append((start, match.end(), previous + " " + match.group()))
        else:
            words.append((match.start(), match.end(), match.group()))
    return sorted(digits + words)


def extract_numbers(text: str) -> list[str]:
    return [value for _, _, value in _number_spans(text)]


def _decimal(token: str) -> tuple[Decimal, Decimal]:
    token = token.replace("−", "-").replace("$", "").replace(",", "").strip().lower()
    if token and token[0].isalpha():
        current = total = 0
        for word in token.replace("-", " ").split():
            if word in _SMALL:
                current += _SMALL[word]
            elif word in _TENS:
                current += _TENS[word]
            elif word == "hundred":
                current = max(current, 1) * 100
            elif word in _SCALES:
                total += max(current, 1) * _SCALES[word]
                current = 0
        return Decimal(total + current), Decimal(1)
    multiplier = Decimal(1)
    suffix = _SUFFIX.search(token)
    if suffix:
        multiplier = Decimal({"k": 1000, "thousand": 1000, "m": 1_000_000,
                              "million": 1_000_000, "b": 1_000_000_000,
                              "billion": 1_000_000_000}[suffix.group(1)])
        token = token[:suffix.start()]
    number = Decimal(token)
    quantum = Decimal(1).scaleb(number.as_tuple().exponent) * multiplier
    return number * multiplier, quantum


def _fact_numbers(value):
    if isinstance(value, bool) or value is None:
        return
    if isinstance(value, (int, float, Decimal)):
        number = Decimal(str(value))
        if number.is_finite():
            yield number
    elif isinstance(value, str):
        for token in extract_numbers(value):
            yield _decimal(token)[0]
    elif isinstance(value, dict):
        for item in value.values():
            yield from _fact_numbers(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _fact_numbers(item)


def _directional_number(number: Decimal, text: str, start: int, end: int, token: str) -> Decimal:
    """Read explicit trader phrasing without accepting arbitrary absolute values."""
    before, after = text[max(0, start - 80):start], text[end:end + 40]
    direction = None
    if re.match(r"\s*(?:%|percent)\s+(?:fall|drop|decline|decrease|loss)\b", after, re.I):
        direction = -1
    elif re.match(r"\s*(?:%|percent)\s+(?:rise|gain|increase)\b", after, re.I):
        direction = 1
    elif re.match(r"\s*(?:%|percent\b)", after, re.I):
        if re.search(r"\b(?:falls?|drops?|declines?|decreases?)(?: of| by)?\s*$", before, re.I):
            direction = -1
        elif re.search(r"\b(?:rises?|gains?|increases?)(?: of| by)?\s*$", before, re.I):
            direction = 1
    if "$" in token:
        # Stop at another number, percentage, dollar amount or sentence so a
        # cost verb cannot silently reverse unrelated numbers later in prose.
        if re.search(r"\b(?:costs?|costing|lose|lost|losing|loss(?: of)?)\b[^\d.!?;$%]{0,60}$", before, re.I):
            direction = -1
        elif re.search(r"\b(?:gains?|gain of|profit of|earn|earned)\b[^\d.!?;$%]{0,60}$", before, re.I):
            direction = 1
    if direction == 1 and number < 0:
        raise ValueError("A negative amount cannot describe a rise or gain")
    return -number if direction == -1 and number > 0 else number


def verify_numbers(text: str, facts: dict, *, allow_direction_words: bool = False) -> dict:
    allowed = set(_fact_numbers(facts))
    bad = []
    for start, end, token in _number_spans(text):
        try:
            number, quantum = _decimal(token)
            if allow_direction_words:
                number = _directional_number(number, text, start, end, token)
            with localcontext() as context:
                context.prec = 64
                matches = any(
                    number == fact or number == (fact / quantum).quantize(Decimal(1), rounding=ROUND_HALF_UP) * quantum
                    for fact in allowed
                )
        except (InvalidOperation, ValueError, OverflowError):
            matches = False
        if not matches and token not in bad:
            bad.append(token)
    return {"verified": not bad, "unverified_numbers": bad}
