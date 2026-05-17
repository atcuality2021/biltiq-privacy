# Javadoc — Java

Delimiter: `/** ... */` with `@param`, `@return`, `@throws` tags.

```java
/**
 * Processes a payment order and returns a confirmation receipt.
 *
 * <p>The amount must be positive and the orderId must be non-empty.
 * The returned receipt is immutable.
 *
 * @param orderId unique identifier for the order; must not be null or empty
 * @param amount  payment amount in the account's base currency; must be &gt; 0
 * @return a {@link Receipt} containing the status and receipt ID
 * @throws IllegalArgumentException if orderId is empty or amount is not positive
 * @throws PaymentGatewayException  if the upstream processor is unavailable
 */
public Receipt processOrder(String orderId, double amount) {
```
