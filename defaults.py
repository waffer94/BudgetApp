"""Seed data used the first time the app runs against an empty sheet."""

PEOPLE = [
    {"id": "aishwarya", "name": "Aishwarya"},
    {"id": "shriniwas", "name": "Shriniwas"},
]

SETTINGS = {
    "income_aishwarya": 2600,
    "income_shriniwas": 3000,
    # Aishwarya's share of shared costs; Shriniwas carries the rest.
    "split_pct": 50,
}

# flow:  "out" = money leaves, "in" = money arrives
# payer: whose account it actually moves through. "common" means each of you
#        pays your own share directly, so nothing needs settling.
CATEGORIES = [
    ("c01", "India Loans",           "aishwarya", "out", "Loans",         1100, True,  "aishwarya"),
    ("c02", "Rent",                  "aishwarya", "out", "Rent",           900, True,  "aishwarya"),
    ("c03", "Rent",                  "shriniwas", "out", "Rent",           900, True,  "shriniwas"),
    ("c04", "Tabrez",                "aishwarya", "out", "Personal loan",  100, True,  "aishwarya"),
    ("c05", "Phone + Fido",          "aishwarya", "out", "Bills",          100, True,  "aishwarya"),
    ("c06", "Travel",                "aishwarya", "out", "Transport",      200, False, "aishwarya"),
    ("c07", "Travel",                "shriniwas", "out", "Transport",       60, False, "shriniwas"),
    ("c08", "Mint",                  "shriniwas", "out", "Bills",           50, True,  "shriniwas"),
    ("c09", "Utilities",             "common",    "out", "Bills",          150, True,  "common"),
    ("c10", "Parking (rented out)",  "common",    "in",  "Rental",         150, True,  "common"),
    ("c11", "Subscriptions",         "common",    "out", "Subscriptions",  100, True,  "common"),
    ("c12", "Groceries",             "common",    "out", "Living",         500, False, "common"),
    ("c13", "Entertainment",         "common",    "out", "Lifestyle",      300, False, "common"),
    ("c14", "Vape + Drinks",         "common",    "out", "Lifestyle",      300, False, "common"),
    ("c15", "Outside Food + Drinks", "common",    "out", "Lifestyle",      200, False, "common"),
    ("c16", "Savings for Vacation",  "common",    "out", "Savings",        500, True,  "common"),
]

CATEGORY_ROWS = [
    {"id": c[0], "name": c[1], "owner": c[2], "flow": c[3],
     "type": c[4], "budget": c[5], "fixed": c[6], "payer": c[7]}
    for c in CATEGORIES
]
