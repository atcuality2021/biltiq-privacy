# godoc — Go

Delimiter: `//` single-line, immediately before the declaration, no blank line.
Comment must begin with the function/type name (exported identifier).

```go
// ProcessOrder processes a payment order and returns a confirmation receipt.
// It returns an error if orderId is empty or amount is not positive.
// The caller is responsible for closing the returned Receipt when done.
func ProcessOrder(orderId string, amount float64) (*Receipt, error) {
```

For types:

```go
// OrderService manages the lifecycle of payment orders.
// Use NewOrderService to construct a valid instance.
type OrderService struct {
```

For packages (in doc.go or at top of the first file):

```go
// Package orders provides types and functions for managing payment orders.
// All monetary values are in the account's base currency.
package orders
```
