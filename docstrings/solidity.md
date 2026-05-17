# NatSpec — Solidity

Delimiter: `/** ... */` multi-line or `///` single-line.
Apply to external and public functions. Use `@notice` for users, `@dev` for developers.

```solidity
/// @notice Transfers tokens from the caller to a recipient.
/// @dev Emits a {Transfer} event. Reverts if the caller has insufficient balance.
/// @param recipient The address receiving the tokens. Must not be the zero address.
/// @param amount The number of tokens to transfer. Must be > 0.
/// @return success True if the transfer succeeded.
function transfer(address recipient, uint256 amount) external returns (bool success);
```

Multi-line NatSpec for complex functions:

```solidity
/**
 * @notice Places a limit order on the exchange.
 * @dev Order is stored in the order book until matched or cancelled.
 *      Emits {OrderPlaced}. Reverts with {InsufficientAllowance} if the caller
 *      has not approved this contract for at least `amount` tokens.
 * @param tokenIn  Address of the token the caller is selling.
 * @param tokenOut Address of the token the caller wants to receive.
 * @param amount   Amount of tokenIn to sell (in tokenIn's smallest unit).
 * @param price    Minimum price per tokenIn expressed in tokenOut units.
 * @return orderId Unique identifier for the placed order.
 */
function placeLimitOrder(
    address tokenIn,
    address tokenOut,
    uint256 amount,
    uint256 price
) external returns (bytes32 orderId);
```
