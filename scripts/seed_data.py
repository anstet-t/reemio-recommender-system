#!/usr/bin/env python3
"""
Seed database with test data for development.

Usage:
    python scripts/seed_data.py
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from uuid import uuid4

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


async def seed_products():
    """Seed sample products."""
    products = [
        {
            "id": str(uuid4()),
            "external_product_id": "prod-001",
            "name": "Wireless Noise-Canceling Headphones",
            "description": "Premium over-ear headphones with active noise cancellation and 30-hour battery life.",
            "category": "Electronics",
            "price": 299.99,
            "stock_quantity": 50,
            "image_url": "https://example.com/headphones.jpg",
        },
        {
            "id": str(uuid4()),
            "external_product_id": "prod-002",
            "name": "Mechanical Gaming Keyboard",
            "description": "RGB backlit mechanical keyboard with Cherry MX switches.",
            "category": "Electronics",
            "price": 149.99,
            "stock_quantity": 100,
            "image_url": "https://example.com/keyboard.jpg",
        },
        {
            "id": str(uuid4()),
            "external_product_id": "prod-003",
            "name": "Ergonomic Office Chair",
            "description": "Adjustable lumbar support, breathable mesh, and armrests.",
            "category": "Furniture",
            "price": 399.99,
            "stock_quantity": 25,
            "image_url": "https://example.com/chair.jpg",
        },
        {
            "id": str(uuid4()),
            "external_product_id": "prod-004",
            "name": "4K Ultra HD Monitor",
            "description": "27-inch 4K display with HDR support and USB-C connectivity.",
            "category": "Electronics",
            "price": 449.99,
            "stock_quantity": 30,
            "image_url": "https://example.com/monitor.jpg",
        },
        {
            "id": str(uuid4()),
            "external_product_id": "prod-005",
            "name": "Standing Desk Converter",
            "description": "Height-adjustable desk converter for existing desks.",
            "category": "Furniture",
            "price": 199.99,
            "stock_quantity": 40,
            "image_url": "https://example.com/desk.jpg",
        },
        {
            "id": str(uuid4()),
            "external_product_id": "prod-006",
            "name": "Wireless Mouse",
            "description": "Ergonomic wireless mouse with customizable buttons.",
            "category": "Electronics",
            "price": 79.99,
            "stock_quantity": 150,
            "image_url": "https://example.com/mouse.jpg",
        },
        {
            "id": str(uuid4()),
            "external_product_id": "prod-007",
            "name": "USB-C Hub",
            "description": "7-in-1 USB-C hub with HDMI, USB-A, and SD card reader.",
            "category": "Electronics",
            "price": 49.99,
            "stock_quantity": 200,
            "image_url": "https://example.com/hub.jpg",
        },
        {
            "id": str(uuid4()),
            "external_product_id": "prod-008",
            "name": "Desk Lamp",
            "description": "LED desk lamp with adjustable brightness and color temperature.",
            "category": "Furniture",
            "price": 59.99,
            "stock_quantity": 75,
            "image_url": "https://example.com/lamp.jpg",
        },
        {
            "id": str(uuid4()),
            "external_product_id": "prod-009",
            "name": "Webcam HD 1080p",
            "description": "Full HD webcam with built-in microphone and auto-focus.",
            "category": "Electronics",
            "price": 89.99,
            "stock_quantity": 60,
            "image_url": "https://example.com/webcam.jpg",
        },
        {
            "id": str(uuid4()),
            "external_product_id": "prod-010",
            "name": "Laptop Stand",
            "description": "Aluminum laptop stand with adjustable height.",
            "category": "Accessories",
            "price": 39.99,
            "stock_quantity": 120,
            "image_url": "https://example.com/stand.jpg",
        },
    ]

    print(f"Created {len(products)} sample products")
    return products


async def seed_users():
    """Seed sample users."""
    users = [
        {
            "id": str(uuid4()),
            "external_user_id": "user-001",
            "email": "alice@example.com",
        },
        {
            "id": str(uuid4()),
            "external_user_id": "user-002",
            "email": "bob@example.com",
        },
        {
            "id": str(uuid4()),
            "external_user_id": "user-003",
            "email": "charlie@example.com",
        },
    ]

    print(f"Created {len(users)} sample users")
    return users


async def seed_interactions(users, products):
    """Seed sample interactions."""
    interactions = []
    now = datetime.now(timezone.utc)

    # Alice: Interested in electronics, viewed many items, purchased headphones
    alice = users[0]
    for i, prod in enumerate(products[:5]):
        interactions.append({
            "id": str(uuid4()),
            "user_id": alice["id"],
            "product_id": prod["id"],
            "interaction_type": "view",
            "created_at": now - timedelta(days=i, hours=i * 2),
        })

    interactions.append({
        "id": str(uuid4()),
        "user_id": alice["id"],
        "product_id": products[0]["id"],  # Headphones
        "interaction_type": "cart_add",
        "created_at": now - timedelta(days=1),
    })

    interactions.append({
        "id": str(uuid4()),
        "user_id": alice["id"],
        "product_id": products[0]["id"],
        "interaction_type": "purchase",
        "created_at": now - timedelta(hours=12),
    })

    # Bob: Browsing furniture, added to cart but abandoned
    bob = users[1]
    for prod in [products[2], products[4], products[7]]:  # Furniture items
        interactions.append({
            "id": str(uuid4()),
            "user_id": bob["id"],
            "product_id": prod["id"],
            "interaction_type": "view",
            "created_at": now - timedelta(hours=3),
        })

    interactions.append({
        "id": str(uuid4()),
        "user_id": bob["id"],
        "product_id": products[2]["id"],  # Office chair
        "interaction_type": "cart_add",
        "created_at": now - timedelta(hours=2, minutes=30),
    })

    print(f"Created {len(interactions)} sample interactions")
    return interactions


async def main():
    """Run seeding."""
    print("Seeding database with test data...")
    print("=" * 50)

    products = await seed_products()
    users = await seed_users()
    interactions = await seed_interactions(users, products)

    print("=" * 50)
    print("Seeding complete!")
    print("")
    print("Note: This script creates sample data structures.")
    print("To actually insert into the database, implement the database connection.")


if __name__ == "__main__":
    asyncio.run(main())
