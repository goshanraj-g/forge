import type { Order } from '../types/factory'

// The backend quantizes every float it stores to this many decimals, so we do
// the same before rounding up. Subtracting raw floats in JS otherwise leaves a
// tail (250 - 247.50001 = 2.499989999999997) that can push a whole number over
// its own ceiling.
const PRECISION = 6

// Units an order still needs built. Production runs at a continuous rate, so
// `produced` can land mid-unit; a partial unit still takes a full unit of
// capacity to finish, which is why the optimizer ceils remaining demand too.
export function unitsLeft(order: Order): number {
  const remaining = Math.max(0, order.quantity - order.produced)
  return Math.ceil(Number(remaining.toFixed(PRECISION)))
}
