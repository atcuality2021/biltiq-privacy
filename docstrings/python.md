# Google style — Python

Delimiter: `"""..."""` (triple double-quote)

```python
def process_order(order_id: str, amount: float) -> dict[str, str]:
    """Process a payment order and return a confirmation receipt.

    Args:
        order_id: Unique identifier for the order. Must be non-empty.
        amount: Payment amount in the account's base currency. Must be > 0.

    Returns:
        A dict with keys ``status`` (``"ok"`` or ``"failed"``) and
        ``receipt_id`` (populated on success, empty string on failure).

    Raises:
        ValueError: If ``order_id`` is empty or ``amount`` is not positive.
        PaymentGatewayError: If the upstream payment processor is unavailable.
    """
```
