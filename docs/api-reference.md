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
