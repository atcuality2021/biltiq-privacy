# JSDoc — JavaScript

Delimiter: `/** ... */`

```javascript
/**
 * Process a payment order and return a confirmation receipt.
 *
 * @param {string} orderId - Unique identifier for the order. Must be non-empty.
 * @param {number} amount - Payment amount in base currency. Must be > 0.
 * @returns {Promise<{status: string, receiptId: string}>} Receipt with status and ID.
 * @throws {Error} If orderId is empty or amount is not positive.
 *
 * @example
 * const receipt = await processOrder("ord_123", 49.99);
 */
async function processOrder(orderId, amount) {
```
