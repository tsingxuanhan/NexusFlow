"""Reporting module for generating order summaries."""

from utils import compute_order_total, format_currency


def daily_sales_report(orders):
    """Generate a daily sales report from a list of orders.

    Each order total is computed via compute_order_total which
    includes tax in the final amount.

    Args:
        orders: List of dicts, each with an 'items' key.

    Returns:
        A report string.
    """
    lines = ["Daily Sales Report", "=" * 40]
    grand_total = 0

    for i, order in enumerate(orders, 1):
        total = compute_order_total(order["items"])
        grand_total += total
        lines.append(f"  Order {i}: {format_currency(total)}")

    lines.append("-" * 40)
    lines.append(f"  Grand Total: {format_currency(grand_total)}")
    return "\n".join(lines)


def average_order_value(orders):
    """Calculate the average order value across all orders."""
    if not orders:
        return 0
    totals = [compute_order_total(o["items"]) for o in orders]
    return sum(totals) / len(totals)