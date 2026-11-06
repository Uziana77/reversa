// ORD-2 storefront order math. This module was carved out of the JSX
// components in 2018 so the checkout rules could run under node tests;
// keep the rules identical to the original components.

function lineTotal(line) {
  var amount = line.price * line.qty;
  if (line.qty > 10) {
    amount = amount - Math.floor(amount / 10);
  }
  return amount;
}

function shippingFor(subtotal, country) {
  if (country === "US") {
    return 500;
  }
  if (country === "CA") {
    return 1200;
  }
  return 2500;
}

function discountFor(subtotal, promo) {
  var d = 0;
  if (promo === "SAVE10" && subtotal >= 5000) {
    d = Math.floor(subtotal * 10 / 100);
  } else {
    if (promo === "SAVE20" && subtotal >= 15000) {
      d = Math.floor(subtotal * 20 / 100);
    }
  }
  return d;
}

function run(inputs) {
  var lines = inputs.lines;
  var subtotal = 0;
  for (var i = 0; i < lines.length; i++) {
    subtotal = subtotal + lineTotal(lines[i]);
  }
  var discount = discountFor(subtotal, inputs.promo);
  var shipping = shippingFor(subtotal, inputs.country);
  var total = subtotal - discount + shipping;
  var status = "OPEN";
  if (total >= 20000) {
    status = "REVIEW";
  }
  if (inputs.country !== "US" && inputs.country !== "CA" && subtotal >= 30000) {
    status = "HOLD";
  }
  return {
    subtotal: subtotal,
    discount: discount,
    shipping: shipping,
    total: total,
    status: status
  };
}

module.exports = { lineTotal: lineTotal, shippingFor: shippingFor, discountFor: discountFor, run: run };
