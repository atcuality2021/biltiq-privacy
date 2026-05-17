# JSDoc — TSX (React components)

Delimiter: `/** ... */` — use on props interfaces and component functions.

```tsx
/** Props for the OrderSummary component. */
interface OrderSummaryProps {
  /** Unique order identifier displayed in the header. */
  orderId: string;
  /** Total amount in the account's base currency. */
  amount: number;
  /** Called when the user confirms the order. */
  onConfirm: (orderId: string) => void;
}

/**
 * Displays an order summary card with a confirmation button.
 *
 * @param props - See {@link OrderSummaryProps}.
 * @returns A card element with order details and a confirm button.
 */
function OrderSummary({ orderId, amount, onConfirm }: OrderSummaryProps): JSX.Element {
```
