"""
Bootstrap seed data — sample suppliers and products for demo environments.

Separated from the seeder logic so data can be reviewed, tested,
or swapped independently.
"""

from __future__ import annotations

from typing import Any

SEED_SUPPLIERS = [
    {
        "name": "Fresh Farms Co.",
        "contact_name": "Maria Garcia",
        "contact_email": "maria@freshfarms.com",
        "contact_phone": "555-0101",
        "notes": "Local organic produce supplier",
    },
    {
        "name": "Pacific Coast Distributors",
        "contact_name": "James Chen",
        "contact_email": "james@pacificcoast.com",
        "contact_phone": "555-0102",
        "notes": "West coast distribution, 2-day delivery",
    },
    {
        "name": "Valley Grains & Goods",
        "contact_name": "Sarah Miller",
        "contact_email": "sarah@valleygrains.com",
        "contact_phone": "555-0103",
        "notes": "Specialty grains and dry goods",
    },
    {
        "name": "Mountain Spring Dairy",
        "contact_name": "Tom Baker",
        "contact_email": "tom@mountainspring.com",
        "contact_phone": "555-0104",
        "notes": "Dairy and refrigerated products",
    },
]

SEED_PRODUCTS: list[dict[str, Any]] = [
    {
        "name": "Organic Apples",
        "description": "Fresh organic Fuji apples",
        "sku": "PRD-001",
        "category": "Produce",
        "supplier_indices": [0, 1],  # Fresh Farms + Pacific Coast
    },
    {
        "name": "Whole Wheat Flour",
        "description": "Stone-ground whole wheat flour, 25lb bag",
        "sku": "PRD-002",
        "category": "Dry Goods",
        "supplier_indices": [2],  # Valley Grains
    },
    {
        "name": "Organic Oranges",
        "description": "Navel oranges, premium grade",
        "sku": "PRD-003",
        "category": "Produce",
        "supplier_indices": [0, 1],  # Fresh Farms + Pacific Coast
    },
    {
        "name": "Whole Milk",
        "description": "Fresh whole milk, 1 gallon",
        "sku": "PRD-004",
        "category": "Dairy",
        "supplier_indices": [3],  # Mountain Spring
    },
    {
        "name": "Brown Rice",
        "description": "Long grain brown rice, 50lb bag",
        "sku": "PRD-005",
        "category": "Dry Goods",
        "supplier_indices": [2, 1],  # Valley Grains + Pacific Coast
    },
]
