// ORD-2 storefront order table (legacy React class component).
// Rendering only — the checkout rules live in orderMath.js.

import React from "react";
import { lineTotal } from "./orderMath";

export default class OrderTable extends React.Component {
  renderLine(line, idx) {
    return (
      <tr key={idx}>
        <td>{line.sku}</td>
        <td>{line.qty}</td>
        <td>{lineTotal(line)}</td>
      </tr>
    );
  }

  render() {
    var lines = this.props.lines || [];
    return (
      <table className="order-table">
        <thead>
          <tr><th>SKU</th><th>Qty</th><th>Total</th></tr>
        </thead>
        <tbody>{lines.map(this.renderLine)}</tbody>
      </table>
    );
  }
}
