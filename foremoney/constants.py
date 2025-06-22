ACCOUNT_TYPES = [
    "assets",
    "expenditures",
    "liabilities",
    "income",
    "capital",
]

# Short codes for account types used in transaction descriptions
ACCOUNT_TYPE_CODES = {
    "assets": "A",
    "expenditures": "E",
    "liabilities": "L",
    "income": "I",
    "capital": "C",
}

ACCOUNT_GROUPS = {
    "assets": [
        "cash",
        "bank accounts",
        "bank deposits",
        "debit card",
        "credit card",
        "fixed assets",
    ],
    "expenditures": [
        "Education",
        "Living space",
        "Entertainment",
        "Transport",
        "Health & Sport",
        "Culture",
        "Digital",
        "Electronics",
        "Apparel",
    ],
    "liabilities": [
        "Mortgage",
    ],
    "income": [
        "Salary",
    ],
    "capital": [
        "assets",
        "liabilities",
        "expenditures",
        "income",
        "Corrections",
    ],
}

# Mapping of capital account groups to subordinate account names.
# Each capital group mirrors the account groups from the respective
# account type.
CAPITAL_ACCOUNTS = {
    "assets": ACCOUNT_GROUPS["assets"],
    "liabilities": ACCOUNT_GROUPS["liabilities"],
    "expenditures": ACCOUNT_GROUPS["expenditures"],
    "income": ACCOUNT_GROUPS["income"],
}
