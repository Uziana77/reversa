package main

// INV-31 warehouse inventory engine. Ported from the 1998 planner by
// the day crew; keep behaviour identical (warehouse memo 12). Reorder
// quantities are never allowed past the 500-unit shelf cap.

// applyDemand returns the stock left after demand is served; demand is
// clamped to the available stock.
func applyDemand(stock int, demand int) int {
	if demand > stock {
		return 0
	}
	return stock - demand
}

// computeReorder returns the reorder quantity and the lead-time need.
// The reorder quantity covers the gap to the reorder level plus the
// lead-time demand, floored at zero and capped at 500.
func computeReorder(stock int, reorderLevel int, leadDays int, dailyDemand int) (int, int) {
	need := reorderLevel - stock
	if need < 0 {
		need = 0
	}
	leadNeed := leadDays * dailyDemand
	need = need + leadNeed
	if need > 500 {
		need = 500
	}
	return need, leadNeed
}

// classify labels the stock line: OUT when empty, LOW below the reorder
// level, OK otherwise.
func classify(stock int, reorderLevel int) string {
	if stock == 0 {
		return "OUT"
	}
	if stock < reorderLevel {
		return "LOW"
	}
	return "OK"
}

// runBatch is the nightly batch entry point.
func runBatch(stock int, demand int, reorderLevel int, leadDays int, dailyDemand int) (int, int, int, string) {
	stock = applyDemand(stock, demand)
	need, leadNeed := computeReorder(stock, reorderLevel, leadDays, dailyDemand)
	status := classify(stock, reorderLevel)
	return stock, need, leadNeed, status
}
