# Doxygen — C

Delimiter: `/** ... */` (JavaDoc style) or `/*! ... */` (Qt style).
Use `@brief`, `@param`, `@return`, `@note`.

```c
/**
 * @brief Process a payment order and return a confirmation receipt.
 *
 * The caller must free the returned receipt with receipt_free() when done.
 *
 * @param order_id  Null-terminated order identifier string. Must not be NULL or empty.
 * @param amount    Payment amount in base currency. Must be > 0.
 * @param[out] out  Pointer to a Receipt pointer; populated on success.
 *
 * @return 0 on success, negative error code on failure:
 *         -EINVAL if order_id is NULL/empty or amount is not positive.
 *         -ECONNREFUSED if the payment gateway is unreachable.
 *
 * @note This function is thread-safe.
 */
int process_order(const char *order_id, double amount, Receipt **out);
```
