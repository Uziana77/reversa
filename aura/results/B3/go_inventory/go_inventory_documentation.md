# Warehouse Inventory Engine (INV-31 / POS-7) — Reference Documentation

## System Overview

Two legacy Go services keep the warehouse and the outlet counters
running. `inventory.go` (job INV-31) is the nightly stock planner;
`pricing.go` (job POS-7) prices counter orders and shipments. Both were
ported from the 1998 planner and must behave identically.

## inventory.go

### applyDemand

Demand is served against the shelf stock. When demand exceeds the
available stock the result is 0 (stock is never negative); otherwise the
remaining stock is `stock - demand`.

### computeReorder

The reorder quantity covers the gap to the reorder level plus the
lead-time demand (`leadDays * dailyDemand`). The gap is floored at zero —
stock at or above the reorder level adds nothing — and the final reorder
quantity is capped at the 500-unit shelf cap.

### classify

Stock lines are labelled `OUT` when empty, `LOW` when below the reorder
level, and `OK` otherwise.

### runBatch

The nightly entry point serves demand first, then computes the reorder
from the post-demand stock, then classifies the line.

## pricing.go

### priceOrder

The order total is `units * unitPrice`. Discounts never stack: orders of
more than 50 units take a 10 percent bulk discount; otherwise member
orders take 5 percent; everyone else pays full price.

### shippingFee

Zone 1 charges 5 per kg, zone 2 charges 8 per kg plus a 10 base fee, and
any other zone ships at a flat 20.

### runPricing

The counter entry point returns the total, the discounted net and the
shipping fee together.

## Data Dictionary

| Field | Meaning |
| --- | --- |
| stock | shelf units before serving demand |
| demand | units requested in this run |
| reorderLevel | stock level that triggers reordering |
| leadDays | supplier lead time in days |
| dailyDemand | average units sold per day |
| final_stock | shelf units after serving demand |
| reorder_qty | reorder quantity (gap + lead need, capped 500) |
| lead_need | lead-time demand |
| status | OUT / LOW / OK label |
| units | units ordered at the counter |
| unitPrice | price per unit |
| member | 1 for loyalty members |
| weight | shipment weight in kg |
| zone | shipping zone (1, 2, other) |
| total | order total before discount |
| net | order total after discount |
| shipping | shipping fee |
