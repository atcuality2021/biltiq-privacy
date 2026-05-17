# rustdoc — Rust

Delimiter: `///` outer doc comment (rendered by `cargo doc`). Use `//!` for module/crate level.
Markdown is supported. Include `# Examples` and `# Errors` for public API functions.

```rust
/// Processes a payment order and returns a confirmation receipt.
///
/// # Arguments
///
/// * `order_id` — Unique order identifier. Must be non-empty.
/// * `amount` — Payment amount in base currency. Must be greater than zero.
///
/// # Returns
///
/// A [`Receipt`] containing the `status` and `receipt_id` on success.
///
/// # Errors
///
/// Returns [`OrderError::EmptyId`] if `order_id` is empty.
/// Returns [`OrderError::InvalidAmount`] if `amount` is not positive.
///
/// # Examples
///
/// ```
/// use mylib::process_order;
///
/// let receipt = process_order("ord_123", 49.99)?;
/// assert_eq!(receipt.status, "ok");
/// ```
pub fn process_order(order_id: &str, amount: f64) -> Result<Receipt, OrderError> {
```

For module-level documentation use `//!` (inner doc comment):

```rust
//! # orders
//! Types and functions for managing payment orders.
//! All monetary values are in the account's base currency.
```

