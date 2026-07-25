"""Reviewed payment-dispute cases shared by quality and evidence checks."""

from __future__ import annotations

CASES: tuple[tuple[str, str], ...] = (
    ("My card was charged twice for the same order.", "duplicate_charge"),
    ("The shop promised a refund but it has not arrived.", "refund_delay"),
    ("I do not recognise this card purchase.", "card_security"),
    ("The merchant charged more than the agreed amount.", "merchant_dispute"),
    (
        "Cash came out of my balance but the ATM dispensed nothing.",
        "cash_withdrawal",
    ),
    ("The bank transfer is still pending after two days.", "transfer_delay"),
)

ROUTES: tuple[str, ...] = tuple(expected for _, expected in CASES)
