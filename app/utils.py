import logging


class SafeFormatDict(dict):
    def __missing__(self, key):
        logging.warning(f"Неизвестная переменная в шаблоне: {{{key}}}")
        return f"{{{key}}}"


def build_template_vars(payment) -> SafeFormatDict:
    metadata = payment.metadata or {}

    invoice_id = ""
    if payment.invoice_details and hasattr(payment.invoice_details, "id"):
        invoice_id = payment.invoice_details.id or ""

    return SafeFormatDict({
        "description": payment.description or payment.id,
        "id": payment.id,
        "payment_description": payment.description or "",
        "order_number": metadata.get("orderNumber") or metadata.get("dashboardInvoiceOriginalNumber") or "",
        "invoice_id": invoice_id,
        "customer_name": metadata.get("custName") or metadata.get("customerNumber") or "",
        "amount": payment.amount.value,
        "merchant_customer_id": getattr(payment, "merchant_customer_id", "") or "",
    })
