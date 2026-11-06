# Storefront Order Math (ORD-2) — Reference Documentation

## System Overview

The storefront checkout computes order totals both in the legacy React
class components and in `orderMath.js`, the module carved out of them in
2018 so the checkout rules could run under node tests. The rules must
stay identical across both. `OrderTable.jsx` renders lines only.

## orderMath.js

### Line totals

A line's total is `price * qty`. A line with more than 10 units takes a
10 percent quantity break, rounded down: the line total becomes
`price * qty - floor(price * qty / 10)`.

### Subtotal

The order subtotal is the sum of all line totals (an empty order has
subtotal 0).

### Shipping

US orders ship at a flat 500, Canadian orders at 1200, and every other
country at 2500.

### Promotions

Promo `SAVE10` on a subtotal of 5000 or more takes 10 percent off,
rounded down; below 5000 it gives nothing. Promo `SAVE20` on a subtotal
of 15000 or more takes 20 percent off, rounded down; below 15000 it
gives nothing.

### Order total and status

The order total is `subtotal - discount + shipping`. An order totaling
20000 or more is flagged `REVIEW`. An international order (neither US
nor CA) with a subtotal of 30000 or more is flagged `HOLD`, overriding
the review flag. Everything else stays `OPEN`.

## Data Dictionary

| Field | Meaning |
| --- | --- |
| lines | list of order lines {price, qty} |
| promo | promo code (SAVE10 / SAVE20 / other) |
| country | shipping country code |
| subtotal | sum of line totals |
| discount | promo discount |
| shipping | flat shipping fee |
| total | subtotal - discount + shipping |
| status | OPEN / REVIEW / HOLD |
