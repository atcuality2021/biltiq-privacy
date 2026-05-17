# YARD — Ruby

Delimiter: `#` single-line comments above the method with YARD tags.
Run `yard doc` to generate HTML documentation.

```ruby
# Processes a payment order and returns a confirmation receipt.
#
# @param order_id [String] Unique identifier for the order. Must not be empty.
# @param amount [Float] Payment amount in base currency. Must be > 0.
# @return [Receipt] A receipt object with +status+ and +receipt_id+ attributes.
# @raise [ArgumentError] If +order_id+ is empty or +amount+ is not positive.
# @raise [PaymentGatewayError] If the upstream processor is unavailable.
#
# @example
#   receipt = OrderService.new.process_order("ord_123", 49.99)
#   puts receipt.status  # => "ok"
def process_order(order_id, amount)
```
