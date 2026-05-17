# JSDoc — TypeScript

Delimiter: `/** ... */`

```typescript
/**
 * Process a payment order and return a confirmation receipt.
 *
 * @param orderId - Unique identifier for the order. Must be non-empty.
 * @param amount - Payment amount in the account's base currency. Must be > 0.
 * @returns A receipt object with `status` and `receiptId` fields.
 * @throws {RangeError} If `orderId` is empty or `amount` is not positive.
 * @throws {PaymentGatewayError} If the upstream processor is unavailable.
 *
 * @example
 * const receipt = await processOrder("ord_123", 49.99);
 * console.log(receipt.status); // "ok"
 */
async function processOrder(
  orderId: string,
  amount: number,
): Promise<{ status: string; receiptId: string }> {
```
