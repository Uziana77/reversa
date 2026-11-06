package main

// POS-7 pricing and shipping for the outlet stores. Discounts never
// stack: the bulk discount wins whenever it applies.

// priceOrder returns the order total and the net after discount. Orders
// above 50 units take a 10 percent bulk discount; smaller member orders
// take 5 percent.
func priceOrder(units int, unitPrice int, member int) (int, int) {
	total := units * unitPrice
	discount := 0
	if units > 50 {
		discount = total / 10
	} else {
		if member == 1 {
			discount = total / 20
		}
	}
	net := total - discount
	return total, net
}

// shippingFee prices the shipment by zone: zone 1 charges 5 per kg,
// zone 2 charges 8 per kg plus a 10 base fee, any other zone is flat 20.
func shippingFee(weight int, zone int) int {
	if zone == 1 {
		return weight * 5
	}
	if zone == 2 {
		return weight*8 + 10
	}
	return 20
}

// runPricing is the counter entry point.
func runPricing(units int, unitPrice int, member int, weight int, zone int) (int, int, int) {
	total, net := priceOrder(units, unitPrice, member)
	fee := shippingFee(weight, zone)
	return total, net, fee
}
