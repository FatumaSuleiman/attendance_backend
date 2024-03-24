from invoice_report import fetch_list_entry_period_employee_entries


def update_invoice_amount(entryp_id: int, unit_price: float) -> float:
    quantity = len(fetch_list_entry_period_employee_entries(period_id=entryp_id))
    return quantity * unit_price
