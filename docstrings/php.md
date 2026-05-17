# PHPDoc — PHP

Delimiter: `/** ... */` with `@param`, `@return`, `@throws` tags.
Rendered by phpDocumentor and supported by PhpStorm.

```php
/**
 * Process a payment order and return a confirmation receipt.
 *
 * @param string $orderId Unique identifier for the order. Must not be empty.
 * @param float  $amount  Payment amount in base currency. Must be > 0.
 *
 * @return Receipt A receipt with `status` and `receiptId` properties.
 *
 * @throws \InvalidArgumentException If $orderId is empty or $amount is not positive.
 * @throws PaymentGatewayException   If the upstream processor is unavailable.
 *
 * @example
 * $receipt = $service->processOrder('ord_123', 49.99);
 * echo $receipt->status; // "ok"
 */
public function processOrder(string $orderId, float $amount): Receipt
{
```
