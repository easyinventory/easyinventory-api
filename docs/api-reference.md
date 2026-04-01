# API Reference

Complete reference for every endpoint in the EasyInventory API. All routes return JSON.

> **Interactive docs:** When the API is running, visit `http://localhost:8000/docs` (Swagger UI) or `http://localhost:8000/redoc` (ReDoc) for auto-generated, interactive documentation.

---

## Table of Contents

- [Authentication](#authentication)
- [Common Headers](#common-headers)
- [Error Format](#error-format)
- [Health](#health)
- [Auth](#auth)
- [Organizations](#organizations)
- [Suppliers](#suppliers)
- [Products](#products)
- [Product–Supplier Links](#productsupplier-links)
- [Stores](#stores)
- [Store Inventory](#store-inventory)
- [Inventory Movements](#inventory-movements)
- [Inventory Placements](#inventory-placements)
- [Layout Versions](#layout-versions)
- [Zones](#zones)
- [Admin: Organizations](#admin-organizations)
- [Admin: Users](#admin-users)
- [Invite Flow Details](#invite-flow-details)

---

## Authentication

Most endpoints require a valid JWT access token from AWS Cognito in the `Authorization` header:

```
Authorization: Bearer <access_token>
```

Tokens are obtained by signing in through the Cognito Hosted UI or SDK. See [cognito-setup.md](cognito-setup.md) for Cognito configuration details.

**Unauthenticated endpoints:** Only `GET /health` is public.

---

## Common Headers

| Header | Required | Description |
|---|---|---|
| `Authorization` | Yes (all except `/health`) | `Bearer <jwt_access_token>` |
| `X-Org-Id` | Optional | UUID of the organization to scope the request to. If omitted, uses the user's most recently joined active org. |
| `Content-Type` | For POST/PUT/PATCH | `application/json` |

---

## Error Format

All errors return a JSON object with a `detail` field:

```json
{
  "detail": "Human-readable error message"
}
```

### Common Status Codes

| Code | Meaning |
|---|---|
| `200` | Success |
| `201` | Created |
| `204` | No Content (successful deletion) |
| `400` | Bad request / validation error / business rule violation |
| `401` | Missing or invalid JWT token |
| `403` | Insufficient permissions |
| `404` | Resource not found |
| `409` | Conflict (duplicate resource) |
| `422` | Validation error (Pydantic) |
| `500` | Internal server error |

---

## Health

### `GET /health`

Health check endpoint. No authentication required.

**Response** `200`

```json
{
  "status": "healthy",
  "service": "easyinventory-api"
}
```

---

## Auth

### `GET /api/me`

Returns the current authenticated user's profile. On the very first call, automatically creates the user record in the database from the JWT claims.

**Auth:** Required  
**Response** `200`

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "user@example.com",
  "system_role": "SYSTEM_USER",
  "is_active": true,
  "created_at": "2024-01-15T10:30:00Z"
}
```

---

## Organizations

All organization endpoints require authentication. Org-scoped endpoints use the `X-Org-Id` header or fall back to the user's default org.

### `GET /api/orgs/me`

Returns all of the current user's active organization memberships.

**Auth:** Required  
**Response** `200`

```json
[
  {
    "id": "membership-uuid",
    "org_id": "org-uuid",
    "org_role": "ORG_OWNER",
    "is_active": true,
    "joined_at": "2024-01-15T10:30:00Z",
    "organization": {
      "id": "org-uuid",
      "name": "My Organization",
      "created_at": "2024-01-15T10:30:00Z"
    }
  }
]
```

---

### `GET /api/orgs/members`

Lists all members of the current organization.

**Auth:** Required — any org member  
**Response** `200`

```json
[
  {
    "id": "membership-uuid",
    "user_id": "user-uuid",
    "email": "owner@example.com",
    "org_role": "ORG_OWNER",
    "is_active": true,
    "joined_at": "2024-01-15T10:30:00Z"
  },
  {
    "id": "membership-uuid",
    "user_id": "user-uuid",
    "email": "employee@example.com",
    "org_role": "ORG_EMPLOYEE",
    "is_active": true,
    "joined_at": "2024-02-01T09:00:00Z"
  }
]
```

---

### `POST /api/orgs/invite`

Invites a user to the current organization by email. See [Invite Flow Details](#invite-flow-details) for how the three invite scenarios work.

**Auth:** Required — `ORG_OWNER` or `ORG_ADMIN`  
**Request Body**

```json
{
  "email": "newmember@example.com",
  "org_role": "ORG_EMPLOYEE"
}
```

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `email` | string (email) | Yes | — | Email address of the person to invite |
| `org_role` | string | No | `"ORG_EMPLOYEE"` | One of: `ORG_ADMIN`, `ORG_EMPLOYEE`, `ORG_VIEWER` |

**Permission rules:**
- Owners can assign `ORG_ADMIN`, `ORG_EMPLOYEE`, or `ORG_VIEWER`.
- Admins can only assign `ORG_EMPLOYEE` or `ORG_VIEWER` (not `ORG_ADMIN`).
- `ORG_OWNER` cannot be assigned via invite — use the ownership transfer endpoint.

**Response** `201`

```json
{
  "id": "membership-uuid",
  "user_id": "user-uuid",
  "email": "newmember@example.com",
  "org_role": "ORG_EMPLOYEE",
  "is_active": true,
  "joined_at": "2024-02-10T14:00:00Z"
}
```

**Errors:**
- `400` — User is already a member, or invalid role.
- `403` — Caller lacks permission to assign the requested role.

---

### `PATCH /api/orgs/members/{member_id}/role`

Changes a member's role within the organization.

**Auth:** Required — `ORG_OWNER` or `ORG_ADMIN`  
**Path:** `member_id` — the UUID of the **membership** (not the user)  
**Request Body**

```json
{
  "org_role": "ORG_ADMIN"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `org_role` | string | Yes | New role: `ORG_ADMIN`, `ORG_EMPLOYEE`, or `ORG_VIEWER` |

**Permission rules:**
- The org owner's role **cannot** be changed by anyone.
- Only the owner can change an admin's role.
- Admins can only change roles of employees and viewers.
- The target role must be one the caller is allowed to assign.

**Response** `200` — Updated member details (same shape as invite response)

**Errors:**
- `403` — Owner protected, admin hierarchy violation, or insufficient permission.
- `404` — Membership not found.

---

### `PATCH /api/orgs/members/{member_id}/deactivate`

Deactivates a member. They lose access but their membership record is preserved and can be reactivated later.

**Auth:** Required — `ORG_OWNER` or `ORG_ADMIN`  
**Path:** `member_id` — membership UUID  
**Request Body:** None

**Permission rules:**
- The owner cannot be deactivated.
- Only the owner can deactivate admins.

**Response** `200` — Updated member details with `"is_active": false`

---

### `PATCH /api/orgs/members/{member_id}/activate`

Reactivates a previously deactivated member.

**Auth:** Required — `ORG_OWNER` or `ORG_ADMIN`  
**Path:** `member_id` — membership UUID  
**Request Body:** None

**Response** `200` — Updated member details with `"is_active": true`

---

### `DELETE /api/orgs/members/{member_id}`

Permanently removes a member from the organization.

**Auth:** Required — `ORG_OWNER` or `ORG_ADMIN`  
**Path:** `member_id` — membership UUID  
**Request Body:** None

**Permission rules:**
- The owner cannot be removed.
- Only the owner can remove admins.

**Response** `204` — No content

---

## Suppliers

All supplier endpoints are org-scoped. The organization is determined by the authenticated user's membership (or the `X-Org-Id` header).

### `GET /api/suppliers`

Lists all suppliers for the current organization.

**Auth:** Required — any org member  
**Response** `200`

```json
[
  {
    "id": "supplier-uuid",
    "org_id": "org-uuid",
    "name": "Fresh Farms Produce",
    "contact_name": "Sarah Johnson",
    "contact_email": "sarah@freshfarms.example.com",
    "contact_phone": "555-0101",
    "notes": "Organic produce specialist",
    "created_at": "2024-01-15T10:30:00Z",
    "updated_at": "2024-01-15T10:30:00Z"
  }
]
```

---

### `GET /api/suppliers/{supplier_id}`

Returns a single supplier by ID.

**Auth:** Required — any org member  
**Response** `200` — Single supplier object (same shape as list items)

**Errors:**
- `404` — Supplier not found in the current org.

---

### `POST /api/suppliers`

Creates a new supplier.

**Auth:** Required — any org member  
**Request Body**

```json
{
  "name": "Pacific Coast Seafood",
  "contact_name": "Mike Chen",
  "contact_email": "mike@pacificseafood.example.com",
  "contact_phone": "555-0102",
  "notes": "Delivers fresh seafood Mon/Wed/Fri"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | Yes | Supplier name |
| `contact_name` | string | No | Primary contact person |
| `contact_email` | string (email) | No | Contact email |
| `contact_phone` | string | No | Contact phone number |
| `notes` | string | No | Free-text notes |

**Response** `201` — The created supplier object

---

### `PUT /api/suppliers/{supplier_id}`

Updates an existing supplier. All fields are optional — only provided fields are updated.

**Auth:** Required — any org member  
**Request Body**

```json
{
  "name": "Pacific Coast Seafood LLC",
  "notes": "Updated delivery schedule: Mon-Fri"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | No | Updated name |
| `contact_name` | string | No | Updated contact person |
| `contact_email` | string (email) | No | Updated email |
| `contact_phone` | string | No | Updated phone |
| `notes` | string | No | Updated notes |

**Response** `200` — The updated supplier object

**Errors:**
- `404` — Supplier not found in the current org.

---

### `DELETE /api/suppliers/{supplier_id}`

Deletes a supplier. This also removes any product-supplier links associated with this supplier.

**Auth:** Required — `ORG_OWNER` or `ORG_ADMIN`  
**Response** `204` — No content

**Errors:**
- `404` — Supplier not found in the current org.

---

## Products

All product endpoints are org-scoped.

### `GET /api/products`

Lists all products for the current organization. Returns a lightweight response **without** nested supplier information (for performance on large lists).

**Auth:** Required — any org member  
**Response** `200`

```json
[
  {
    "id": "product-uuid",
    "org_id": "org-uuid",
    "name": "Organic Apples",
    "description": "Fresh organic Gala apples",
    "sku": "PROD-001",
    "category": "Produce",
    "created_at": "2024-01-15T10:30:00Z",
    "updated_at": "2024-01-15T10:30:00Z"
  }
]
```

---

### `GET /api/products/{product_id}`

Returns a single product by ID, **including** its linked suppliers.

**Auth:** Required — any org member  
**Response** `200`

```json
{
  "id": "product-uuid",
  "org_id": "org-uuid",
  "name": "Organic Apples",
  "description": "Fresh organic Gala apples",
  "sku": "PROD-001",
  "category": "Produce",
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z",
  "product_suppliers": [
    {
      "id": "link-uuid",
      "supplier_id": "supplier-uuid",
      "supplier_name": "Fresh Farms Produce",
      "is_active": true,
      "created_at": "2024-01-20T08:00:00Z",
      "updated_at": "2024-01-20T08:00:00Z"
    }
  ]
}
```

---

### `POST /api/products`

Creates a new product.

**Auth:** Required — any org member  
**Request Body**

```json
{
  "name": "Organic Apples",
  "description": "Fresh organic Gala apples",
  "sku": "PROD-001",
  "category": "Produce"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | Yes | Product name |
| `description` | string | No | Product description |
| `sku` | string | No | Stock keeping unit |
| `category` | string | No | Product category |

**Response** `201` — The created product (with empty `product_suppliers` array)

---

### `PUT /api/products/{product_id}`

Updates a product's details. All fields are optional.

**Auth:** Required — any org member  
**Request Body**

```json
{
  "name": "Organic Gala Apples",
  "category": "Fresh Produce"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | No | Updated name |
| `description` | string | No | Updated description |
| `sku` | string | No | Updated SKU |
| `category` | string | No | Updated category |

**Response** `200` — The updated product (with nested suppliers)

---

### `DELETE /api/products/{product_id}`

Deletes a product and all its supplier links.

**Auth:** Required — `ORG_OWNER` or `ORG_ADMIN`  
**Response** `204` — No content

---

## Product–Supplier Links

These endpoints manage the many-to-many relationship between products and suppliers. Both the product and supplier must belong to the same organization.

### `GET /api/products/{product_id}/suppliers`

Lists all suppliers linked to a specific product.

**Auth:** Required — any org member  
**Response** `200`

```json
[
  {
    "id": "link-uuid",
    "product_id": "product-uuid",
    "supplier_id": "supplier-uuid",
    "supplier_name": "Fresh Farms Produce",
    "is_active": true,
    "created_at": "2024-01-20T08:00:00Z",
    "updated_at": "2024-01-20T08:00:00Z"
  }
]
```

---

### `POST /api/products/{product_id}/suppliers`

Links a supplier to a product.

**Auth:** Required — any org member  
**Request Body**

```json
{
  "supplier_id": "supplier-uuid"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `supplier_id` | UUID | Yes | ID of the supplier to link |

**Response** `201` — The created link

**Errors:**
- `404` — Product or supplier not found in the current org.
- `409` — Supplier is already linked to this product.

---

### `PATCH /api/products/{product_id}/suppliers/{supplier_id}`

Updates the `is_active` flag on a product-supplier link. Use this to temporarily disable a supplier for a product without removing the link entirely.

**Auth:** Required — any org member  
**Request Body**

```json
{
  "is_active": false
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `is_active` | boolean | Yes | Whether the link is active |

**Response** `200` — The updated link

**Errors:**
- `404` — Link not found (product and supplier are not linked).

---

### `DELETE /api/products/{product_id}/suppliers/{supplier_id}`

Permanently removes a supplier link from a product.

**Auth:** Required — any org member  
**Response** `204` — No content

**Errors:**
- `404` — Link not found.

---

## Stores

All store endpoints are org-scoped. Stores represent physical or logical locations within an organization (e.g., a warehouse or retail outlet). Every organization automatically has a default store created when it is first provisioned.

### `GET /api/stores`

Lists all active stores for the current organization.

**Auth:** Required — any org member  
**Response** `200`

```json
[
  {
    "id": "store-uuid",
    "org_id": "org-uuid",
    "name": "Acme Corporation Default Store",
    "is_active": true,
    "created_at": "2024-01-15T10:30:00Z",
    "updated_at": "2024-01-15T10:30:00Z"
  }
]
```

---

### `POST /api/stores`

Creates a new store within the current organization.

**Auth:** Required — `ORG_OWNER`  
**Request Body**

```json
{
  "name": "Downtown Warehouse"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string (min length 1) | Yes | Store name |

**Response** `201`

```json
{
  "id": "store-uuid",
  "org_id": "org-uuid",
  "name": "Downtown Warehouse",
  "is_active": true,
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z"
}
```

**Errors:**
- `403` — Caller is not the org owner.
- `422` — Missing or empty `name`.

---

## Store Inventory

Store inventory endpoints track which products a store stocks and at what quantity. Inventory is scoped to a specific store and linked to org-scoped products. All inventory responses include embedded product metadata.

All endpoints are nested under a store: `/api/stores/{store_id}/inventory`

They require authentication and a valid `X-Org-Id` header, and validate that `store_id` belongs to the caller's organization.

---

### `GET /api/stores/{store_id}/inventory`

Returns a paginated list of all inventory entries for the store. Supports full-text search and category filtering.

**Auth:** Required — any org member  
**Query Parameters**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `search` | string | — | Case-insensitive partial match on product **name** or **category** |
| `category` | string | — | Case-insensitive partial match on product **category** only |
| `page` | integer | `1` | 1-based page number |
| `page_size` | integer | `20` | Items per page (min 1, max 100) |

**Response** `200`

```json
{
  "items": [
    {
      "id": "entry-uuid",
      "store_id": "store-uuid",
      "product_id": "product-uuid",
      "quantity": 48.0,
      "unit_price": "2.9900",
      "low_stock_threshold": 10.0,
      "created_at": "2026-03-31T10:00:00Z",
      "updated_at": "2026-03-31T10:00:00Z",
      "product": {
        "id": "product-uuid",
        "name": "Organic Apples",
        "sku": "PROD-001",
        "category": "Produce",
        "description": "Fresh organic Gala apples"
      }
    }
  ],
  "total": 42,
  "page": 1,
  "page_size": 20
}
```

> `total` reflects the count of rows matching the active filters (before pagination), not the total number of entries in the store.

**Errors:**
- `404` — Store not found in the current org.

---

### `POST /api/stores/{store_id}/inventory`

Adds a product to the store's inventory.

**Auth:** Required — any org member  
**Request Body**

```json
{
  "product_id": "product-uuid",
  "quantity": 48.0,
  "unit_price": "2.99",
  "low_stock_threshold": 10.0
}
```

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `product_id` | UUID | Yes | — | ID of the product to stock (must belong to this org) |
| `quantity` | float | No | `0.0` | Units currently in stock (≥ 0) |
| `unit_price` | decimal string | No | `null` | Per-unit price |
| `low_stock_threshold` | float | No | `null` | Alert threshold for low stock (≥ 0) |

**Response** `201` — The created inventory entry (same shape as a list item)

**Errors:**
- `404` — Product not found in the current org (tenant isolation — prevents stocking products from other orgs).
- `404` — Store not found in the current org.
- `409` — Product is already stocked in this store.

---

### `GET /api/stores/{store_id}/inventory/{entry_id}`

Returns a single inventory entry by ID.

**Auth:** Required — any org member  
**Response** `200` — Single inventory entry (same shape as a list item)

**Errors:**
- `404` — Entry not found for this store.
- `404` — Store not found in the current org.

---

### `PATCH /api/stores/{store_id}/inventory/{entry_id}`

Partially updates an inventory entry. Only the fields provided in the request body are changed.

**Auth:** Required — any org member  
**Request Body** — all fields optional

```json
{
  "quantity": 100.0,
  "unit_price": "3.49",
  "low_stock_threshold": 20.0
}
```

| Field | Type | Constraints | Description |
|---|---|---|---|
| `quantity` | float | ≥ 0 | New quantity in stock |
| `unit_price` | decimal string or `null` | — | Updated price; send `null` to clear |
| `low_stock_threshold` | float or `null` | ≥ 0 | Updated threshold; send `null` to clear |

**Response** `200` — The updated inventory entry

**Errors:**
- `404` — Entry not found for this store.
- `404` — Store not found in the current org.

---

### `DELETE /api/stores/{store_id}/inventory/{entry_id}`

Removes a product from the store's inventory.

**Auth:** Required — `ORG_OWNER`  
**Response** `204` — No content

**Errors:**
- `403` — Caller is not the org owner.
- `404` — Entry not found for this store.
- `404` — Store not found in the current org.

---

## Inventory Movements

Inventory movements record every stock change with a full audit trail. Each movement stores who performed the action, the quantity, optional cost/price, and an optional reference number. Two movement types are supported:

| Type | Effect | Endpoint |
|---|---|---|
| `receipt` | Increases store quantity | `POST …/receipts` |
| `sale` | Decreases store quantity (validates no negative stock) | `POST …/sales` |

Movement history can be retrieved via `GET …/movements`.

All movement endpoints are nested under an inventory entry: `/api/stores/{store_id}/inventory/{inventory_id}/`.

They require authentication and a valid `X-Org-Id` header, and validate that `store_id` belongs to the caller's organization.

---

### `POST /api/stores/{store_id}/inventory/{inventory_id}/receipts`

Records an incoming stock receipt. Increments the inventory entry's `quantity` by the received amount and creates an `InventoryMovement` record linked to the calling user.

**Auth:** Required — any org member  
**Request Body**

```json
{
  "quantity": 50,
  "unit_cost": "1.25",
  "reference_number": "PO-2026-001",
  "notes": "Spring restock from Fresh Farms"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `quantity` | integer | Yes (> 0) | Number of units received |
| `unit_cost` | decimal string | No | Per-unit cost paid |
| `reference_number` | string (≤ 100 chars) | No | Purchase order or delivery reference |
| `notes` | string | No | Free-text notes |

**Response** `201`

```json
{
  "id": "movement-uuid",
  "store_inventory_id": "entry-uuid",
  "movement_type": "receipt",
  "quantity": 50,
  "unit_cost": "1.25",
  "unit_price": null,
  "reference_number": "PO-2026-001",
  "notes": "Spring restock from Fresh Farms",
  "performed_by_user_id": "user-uuid",
  "created_at": "2026-03-31T14:00:00Z"
}
```

**Errors:**
- `404` — Inventory entry not found.
- `404` — Store not found in the current org.

---

### `POST /api/stores/{store_id}/inventory/{inventory_id}/sales`

Records an outgoing stock sale. Decrements the inventory entry's `quantity` by the sold amount and creates an `InventoryMovement` record linked to the calling user. Rejected if the sale quantity exceeds available stock.

**Auth:** Required — any org member  
**Request Body**

```json
{
  "quantity": 12,
  "unit_price": "2.99",
  "reference_number": "INV-2026-042",
  "notes": "Weekly sale batch"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `quantity` | integer | Yes (> 0) | Number of units sold |
| `unit_price` | decimal string | No | Per-unit price charged |
| `reference_number` | string (≤ 100 chars) | No | Invoice or POS reference |
| `notes` | string | No | Free-text notes |

**Response** `201`

```json
{
  "id": "movement-uuid",
  "store_inventory_id": "entry-uuid",
  "movement_type": "sale",
  "quantity": 12,
  "unit_cost": null,
  "unit_price": "2.99",
  "reference_number": "INV-2026-042",
  "notes": "Weekly sale batch",
  "performed_by_user_id": "user-uuid",
  "created_at": "2026-03-31T14:05:00Z"
}
```

**Errors:**
- `400` — Insufficient stock (sale quantity exceeds `quantity` on the inventory entry).
- `404` — Inventory entry not found.
- `404` — Store not found in the current org.

---

### `GET /api/stores/{store_id}/inventory/{inventory_id}/movements`

Returns the full stock-movement history for an inventory item, newest first. Includes both receipts and sales.

**Auth:** Required — any org member  
**Response** `200`

```json
[
  {
    "id": "movement-uuid",
    "store_inventory_id": "entry-uuid",
    "movement_type": "sale",
    "quantity": 12,
    "unit_cost": null,
    "unit_price": "2.99",
    "reference_number": "INV-2026-042",
    "notes": "Weekly sale batch",
    "performed_by_user_id": "user-uuid",
    "created_at": "2026-03-31T14:05:00Z"
  },
  {
    "id": "movement-uuid-2",
    "store_inventory_id": "entry-uuid",
    "movement_type": "receipt",
    "quantity": 50,
    "unit_cost": "1.25",
    "unit_price": null,
    "reference_number": "PO-2026-001",
    "notes": "Spring restock from Fresh Farms",
    "performed_by_user_id": "user-uuid",
    "created_at": "2026-03-31T14:00:00Z"
  }
]
```

**Errors:**
- `404` — Inventory entry not found.
- `404` — Store not found in the current org.

---

## Inventory Placements

Inventory placements record where on the shop floor each inventory item is physically located. Only one placement per inventory item may be active (`ended_at IS NULL`) at a time. Assigning an item to a new zone automatically closes the previous active placement.

All placement endpoints are nested under an inventory entry: `/api/stores/{store_id}/inventory/{inventory_id}/placements`.

They require authentication and a valid `X-Org-Id` header, and validate that the `store_id` belongs to the caller's organisation and that the referenced zone belongs to one of that store's layout versions.

---

### `PATCH /api/stores/{store_id}/inventory/{inventory_id}/placements`

Assigns the inventory item to a zone. If the item is already in a zone, the previous active placement is closed automatically (`ended_at` set to now) and a new one is created.

**Auth:** Required — any org member  
**Request Body**

```json
{
  "active_zone_id": "zone-uuid"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `active_zone_id` | UUID | Yes | ID of the zone to assign the item to. Must belong to one of the store's layout versions. |

**Response** `201`

```json
{
  "id": "placement-uuid",
  "store_inventory_id": "entry-uuid",
  "zone_id": "zone-uuid",
  "zone_name": "Refrigerated Aisle",
  "started_at": "2026-03-31T14:00:00Z",
  "ended_at": null,
  "placed_by_user_id": "user-uuid",
  "duration_display": null,
  "created_at": "2026-03-31T14:00:00Z"
}
```

**Errors:**
- `404` — Inventory entry not found in this store.
- `404` — Zone not found in this store's layout versions.
- `404` — Store not found in the current org.

---

### `GET /api/stores/{store_id}/inventory/{inventory_id}/placements`

Returns the full placement history for the inventory item, newest first. The currently active placement (if any) will have `ended_at: null`.

**Auth:** Required — any org member  
**Response** `200`

```json
[
  {
    "id": "placement-uuid",
    "store_inventory_id": "entry-uuid",
    "zone_id": "zone-uuid",
    "zone_name": "Refrigerated Aisle",
    "started_at": "2026-03-31T16:00:00Z",
    "ended_at": null,
    "placed_by_user_id": "user-uuid",
    "duration_display": null,
    "created_at": "2026-03-31T16:00:00Z"
  },
  {
    "id": "placement-uuid-2",
    "store_inventory_id": "entry-uuid",
    "zone_id": "zone-uuid-2",
    "zone_name": "Dry Goods",
    "started_at": "2026-03-30T09:00:00Z",
    "ended_at": "2026-03-31T16:00:00Z",
    "placed_by_user_id": "user-uuid",
    "duration_display": "1 day, 7 hrs",
    "created_at": "2026-03-30T09:00:00Z"
  }
]
```

**`duration_display` format:**

| Duration | Example output |
|---|---|
| ≥ 1 day | `"2 days, 3 hrs"` |
| ≥ 1 hour, < 1 day | `"4 hrs, 30 mins"` |
| ≥ 1 minute, < 1 hour | `"45 mins"` |
| < 1 minute | `"< 1 min"` |
| Active (ended_at is null) | `null` |

**Errors:**
- `404` — Inventory entry not found in this store.
- `404` — Store not found in the current org.

---

### `DELETE /api/stores/{store_id}/inventory/{inventory_id}/placements/current`

Removes the inventory item from its current zone by closing the active placement (`ended_at` set to now). Returns `404` if the item is not currently assigned to any zone.

**Auth:** Required — any org member  
**Response** `204` — No content

**Errors:**
- `404` — Inventory entry has no active placement.
- `404` — Inventory entry not found in this store.
- `404` — Store not found in the current org.

---

## Layout Versions

Layout versions represent versioned grid configurations for a store. Each version defines a rows × cols grid. Only one version can be active at a time per store. Zones and fixtures (BE-08) are nested within a layout version.

**All layout endpoints require a valid `X-Org-Id` header** and validate that `store_id` belongs to the caller's organization.

---

### `GET /api/stores/{store_id}/layouts`

Returns all layout versions for the store ordered by `version_number` ascending.

**Auth:** Required — any org member  
**Response** `200`

```json
[
  {
    "id": "layout-uuid",
    "store_id": "store-uuid",
    "version_number": 1,
    "rows": 10,
    "cols": 8,
    "is_active": false,
    "created_at": "2026-03-31T10:00:00Z",
    "updated_at": "2026-03-31T10:00:00Z",
    "zones": [],
    "fixtures": []
  }
]
```

**Errors:**
- `404` — Store not found in the current org.

---

### `GET /api/stores/{store_id}/layouts/active`

Returns the currently active layout version with zones and fixtures eagerly loaded.

**Auth:** Required — any org member  
**Response** `200`

```json
{
  "id": "layout-uuid",
  "store_id": "store-uuid",
  "version_number": 2,
  "rows": 10,
  "cols": 8,
  "is_active": true,
  "created_at": "2026-03-31T10:00:00Z",
  "updated_at": "2026-03-31T11:00:00Z",
  "zones": [],
  "fixtures": []
}
```

**Errors:**
- `404` — No active layout version exists for the store.
- `404` — Store not found in the current org.

---

### `POST /api/stores/{store_id}/layouts`

Creates a new layout version. The `version_number` is auto-incremented (starts at 1, increments by 1 for each subsequent version). New versions are inactive by default.

**Auth:** Required — `ORG_OWNER` or `ORG_ADMIN`  
**Request Body**

```json
{
  "rows": 10,
  "cols": 8
}
```

| Field | Type | Required | Constraints | Description |
|---|---|---|---|---|
| `rows` | integer | Yes | min 2, max 30 | Number of grid rows |
| `cols` | integer | Yes | min 2, max 30 | Number of grid columns |

**Response** `201`

```json
{
  "id": "layout-uuid",
  "store_id": "store-uuid",
  "version_number": 1,
  "rows": 10,
  "cols": 8,
  "is_active": false,
  "created_at": "2026-03-31T10:00:00Z",
  "updated_at": "2026-03-31T10:00:00Z",
  "zones": [],
  "fixtures": []
}
```

**Errors:**
- `403` — Caller is not `ORG_OWNER` or `ORG_ADMIN`.
- `404` — Store not found in the current org.
- `422` — `rows` or `cols` is outside the 2–30 range.

---

### `POST /api/stores/{store_id}/layouts/{layout_id}/activate`

Activates the specified layout version and deactivates all other versions for the store.

**Auth:** Required — `ORG_OWNER` or `ORG_ADMIN`  
**Response** `200` — Returns the now-active layout version.

```json
{
  "id": "layout-uuid",
  "store_id": "store-uuid",
  "version_number": 2,
  "rows": 10,
  "cols": 8,
  "is_active": true,
  "created_at": "2026-03-31T10:00:00Z",
  "updated_at": "2026-03-31T11:00:00Z",
  "zones": [],
  "fixtures": []
}
```

**Errors:**
- `403` — Caller is not `ORG_OWNER` or `ORG_ADMIN`.
- `404` — Layout version not found for the store.
- `404` — Store not found in the current org.

---

## Zones

Zones represent named, coloured regions of a layout version's grid. Each zone owns a set of `(row, col)` cell positions. A cell may belong to at most one zone within a layout version.

All zone endpoints are nested under a store and a layout version:
`/api/stores/{store_id}/layouts/{layout_version_id}/zones`

They require a valid `X-Org-Id` header and validate that both `store_id` and `layout_version_id` belong to the caller's organization.

---

### `GET /api/stores/{store_id}/layouts/{layout_version_id}/zones`

Returns all zones for the layout version ordered by `created_at` ascending.

**Auth:** Required — any org member  
**Response** `200`

```json
[
  {
    "id": "zone-uuid",
    "layout_version_id": "layout-uuid",
    "name": "Produce",
    "color": "#00FF00",
    "cells": [
      {"row": 0, "col": 0},
      {"row": 0, "col": 1}
    ],
    "created_at": "2026-03-31T10:00:00Z",
    "updated_at": "2026-03-31T10:00:00Z"
  }
]
```

**Errors:**
- `404` — Layout version not found for the store.
- `404` — Store not found in the current org.

---

### `POST /api/stores/{store_id}/layouts/{layout_version_id}/zones`

Creates a new zone within a layout version.

**Auth:** Required — `ORG_OWNER` or `ORG_ADMIN`  
**Request Body**

```json
{
  "name": "Produce",
  "color": "#00FF00",
  "cells": [
    {"row": 0, "col": 0},
    {"row": 0, "col": 1}
  ]
}
```

| Field | Type | Required | Constraints | Description |
|---|---|---|---|---|
| `name` | string | Yes | 1–100 chars | Zone display name |
| `color` | string | Yes | `#RRGGBB` hex | Zone colour |
| `cells` | array | Yes | min 1, no duplicates | Cell positions claimed by this zone |
| `cells[].row` | integer | Yes | ≥ 0, < `layout.rows` | Row index (0-based) |
| `cells[].col` | integer | Yes | ≥ 0, < `layout.cols` | Column index (0-based) |

**Response** `201`

```json
{
  "id": "zone-uuid",
  "layout_version_id": "layout-uuid",
  "name": "Produce",
  "color": "#00FF00",
  "cells": [
    {"row": 0, "col": 0},
    {"row": 0, "col": 1}
  ],
  "created_at": "2026-03-31T10:00:00Z",
  "updated_at": "2026-03-31T10:00:00Z"
}
```

**Errors:**
- `400` — One or more cells lie outside the layout's grid dimensions.
- `403` — Caller is not `ORG_OWNER` or `ORG_ADMIN`.
- `404` — Layout version or store not found in the current org.
- `409` — One or more cells overlap with an existing zone.
- `422` — `cells` is empty, contains duplicates, or `color` is not a valid `#RRGGBB` hex string.

---

### `GET /api/stores/{store_id}/layouts/{layout_version_id}/zones/{zone_id}`

Returns a single zone by ID.

**Auth:** Required — any org member  
**Response** `200` — Zone object (same shape as list items)

**Errors:**
- `404` — Zone, layout version, or store not found in the current org.

---

### `PUT /api/stores/{store_id}/layouts/{layout_version_id}/zones/{zone_id}`

Partially updates a zone. Only the fields provided are changed.

**Auth:** Required — `ORG_OWNER` or `ORG_ADMIN`  
**Request Body** — all fields optional

```json
{
  "name": "Dairy",
  "color": "#0000FF",
  "cells": [{"row": 1, "col": 0}]
}
```

| Field | Type | Constraints | Description |
|---|---|---|---|
| `name` | string | 1–100 chars | New display name |
| `color` | string | `#RRGGBB` hex | New colour |
| `cells` | array | min 1, no duplicates, within grid bounds, no overlap (excluding self) | New cell set |

**Response** `200` — Updated zone object

**Errors:**
- `400` — One or more new cells lie outside the layout's grid dimensions.
- `403` — Caller is not `ORG_OWNER` or `ORG_ADMIN`.
- `404` — Zone, layout version, or store not found in the current org.
- `409` — New cells overlap with another existing zone.
- `422` — Invalid field values.

---

### `DELETE /api/stores/{store_id}/layouts/{layout_version_id}/zones/{zone_id}`

Deletes a zone.

**Auth:** Required — `ORG_OWNER` or `ORG_ADMIN`  
**Response** `204` — No content

**Errors:**
- `403` — Caller is not `ORG_OWNER` or `ORG_ADMIN`.
- `404` — Zone, layout version, or store not found in the current org.

---

## Admin: Organizations

System-admin endpoints for managing organizations globally. All endpoints require `SYSTEM_ADMIN` system role.

### `GET /api/admin/status`

Verifies the caller has system admin access.

**Auth:** Required — `SYSTEM_ADMIN`  
**Response** `200`

```json
{
  "message": "You are an admin",
  "email": "admin@example.com",
  "role": "SYSTEM_ADMIN"
}
```

---

### `POST /api/admin/orgs`

Creates a new organization and assigns an owner. If the owner email doesn't exist in the system, a Cognito invite is sent and a placeholder user is created.

**Auth:** Required — `SYSTEM_ADMIN`  
**Request Body**

```json
{
  "name": "Acme Corporation",
  "owner_email": "owner@acme.example.com"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | Yes | Organization name |
| `owner_email` | string (email) | Yes | Email of the person who will own the org |

**Response** `201`

```json
{
  "id": "org-uuid",
  "name": "Acme Corporation",
  "created_at": "2024-01-15T10:30:00Z",
  "owner_email": "owner@acme.example.com",
  "member_count": 1
}
```

> **Note:** Creating an organization automatically creates a default store named `"<Org Name> Default Store"` for that org.

---

### `GET /api/admin/orgs`

Lists all organizations with owner email and member count.

**Auth:** Required — `SYSTEM_ADMIN`  
**Response** `200`

```json
[
  {
    "id": "org-uuid",
    "name": "Acme Corporation",
    "created_at": "2024-01-15T10:30:00Z",
    "owner_email": "owner@acme.example.com",
    "member_count": 5
  }
]
```

---

### `PATCH /api/admin/orgs/{org_id}`

Renames an organization.

**Auth:** Required — `SYSTEM_ADMIN`  
**Request Body**

```json
{
  "name": "Acme Corp (Renamed)"
}
```

**Response** `200` — The updated org (same shape as list items)

---

### `DELETE /api/admin/orgs/{org_id}`

Deletes an organization and all its memberships.

**Auth:** Required — `SYSTEM_ADMIN`  
**Response** `204` — No content

---

### `POST /api/admin/orgs/{org_id}/transfer-ownership`

Transfers ownership of an organization to another member.

**Auth:** Required — `SYSTEM_ADMIN`  
**Request Body**

```json
{
  "new_owner_email": "newowner@example.com"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `new_owner_email` | string (email) | Yes | Email of the new owner (must be an existing member) |

**Response** `200`

```json
{
  "id": "membership-uuid",
  "user_id": "user-uuid",
  "email": "newowner@example.com",
  "org_role": "ORG_OWNER",
  "is_active": true,
  "joined_at": "2024-01-15T10:30:00Z"
}
```

---

### `GET /api/admin/orgs/{org_id}/members`

Lists all members of a specific organization.

**Auth:** Required — `SYSTEM_ADMIN`  
**Response** `200` — Array of member details (same shape as `GET /api/orgs/members`)

---

## Admin: Users

System-admin endpoints for managing users globally.

### `GET /api/admin/users`

Lists all users across all organizations.

**Auth:** Required — `SYSTEM_ADMIN`  
**Response** `200`

```json
[
  {
    "id": "user-uuid",
    "email": "user@example.com",
    "system_role": "SYSTEM_USER",
    "is_active": true,
    "created_at": "2024-01-15T10:30:00Z",
    "org_count": 2
  }
]
```

---

### `DELETE /api/admin/users/{user_id}`

Deletes a user from both the local database and AWS Cognito. Removes all their org memberships.

**Auth:** Required — `SYSTEM_ADMIN`  
**Response** `204` — No content

**Errors:**
- `400` — You cannot delete your own account.
- `404` — User not found.

---

## Invite Flow Details

The invite system handles three scenarios transparently:

### Scenario 1: Known user, not yet a member

The invited email belongs to someone who already has an account (they've logged in at least once).

1. API finds the existing `User` record by email.
2. Creates an **active** `OrgMembership` linking the user to the organization.
3. The user can immediately access the org — no further action needed.

### Scenario 2: Known user, already a member

The email belongs to someone who is already a member (active or pending) of this organization.

- API raises `AlreadyExists` with an appropriate message.
- **Status:** `400`

### Scenario 3: Unknown user (new invite)

The email doesn't exist in the local database.

1. API calls **Cognito `AdminCreateUser`** — Cognito sends an email invitation with a temporary password.
2. API creates a **placeholder** `User` record in the local database (has email but no `cognito_sub`).
3. API creates an **inactive** `OrgMembership` (the user hasn't accepted yet).
4. When the user accepts the Cognito invite and makes their first API call:
   - The `get_current_user` dependency matches their `email` to the placeholder.
   - The placeholder is **claimed** — `cognito_sub` is set from the JWT.
   - All inactive memberships are **activated**.

### Visual flow

```
Org Admin invites "alice@co.example"
    │
    ├─ User table has alice@co.example?
    │   ├─ YES: Already a member?
    │   │    ├─ YES → 400 AlreadyExists
    │   │    └─ NO  → Create active membership → 201 ✓
    │   │
    │   └─ NO: Unknown user
    │        ├─ Cognito AdminCreateUser (sends email invite)
    │        ├─ Create placeholder User (no cognito_sub)
    │        └─ Create inactive membership → 201 ✓
    │
    │  (Later, when Alice signs up and calls /api/me)
    │        ├─ Match email → claim placeholder (set cognito_sub)
    │        └─ Activate all inactive memberships
```

---

## Related Guides

- [Architecture](architecture.md) — System design, request lifecycle, RBAC
- [Developer Guide](developer-guide.md) — Adding new endpoints
- [Getting Started](getting-started.md) — Setup and installation
