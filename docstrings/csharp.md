# XML doc comments — C#

Delimiter: `/// <summary>...</summary>` with `<param>`, `<returns>`, `<exception>` tags.
Rendered by Visual Studio IntelliSense and `dotnet doc`.

```csharp
/// <summary>
/// Processes a payment order and returns a confirmation receipt.
/// </summary>
/// <param name="orderId">
/// Unique identifier for the order. Must not be null or empty.
/// </param>
/// <param name="amount">
/// Payment amount in the account's base currency. Must be greater than zero.
/// </param>
/// <returns>
/// A <see cref="Receipt"/> containing the <c>Status</c> and <c>ReceiptId</c>.
/// </returns>
/// <exception cref="ArgumentException">
/// Thrown when <paramref name="orderId"/> is empty or <paramref name="amount"/>
/// is not positive.
/// </exception>
/// <exception cref="PaymentGatewayException">
/// Thrown when the upstream processor is unavailable.
/// </exception>
public async Task<Receipt> ProcessOrderAsync(string orderId, decimal amount)
{
```
