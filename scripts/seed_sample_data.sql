-- =============================================================================
-- EasyInventory – Sample Seed Data
-- (stores, layouts, zones, inventory, placements, movements)
-- =============================================================================
-- Designed to run AFTER the app bootstrap, which creates:
--   * 1 organization  (BOOTSTRAP_ORG_NAME / "Default Organization")
--   * 1 admin user    (BOOTSTRAP_ADMIN_EMAIL)
--   * 4 suppliers     (Fresh Farms, Pacific Coast, Valley Grains, Mountain Spring)
--   * 5 products      (Organic Apples, Whole Wheat Flour, Organic Oranges,
--                       Whole Milk, Brown Rice)
--
-- This script adds:
--   * 2 stores
--   * 2 layout versions  (one per store, 5x8 grid, active)
--   * 8 zones            (Produce, Dairy, Dry Goods, Bulk Storage per store)
--   * 10 store_inventory rows  (5 products x 2 stores)
--   * 10 inventory_placements  (one active placement per inventory item)
--   * 150 inventory movements  (~15 per item per store, with zone_id)
--
-- All IDs are deterministic via uuid(md5(...)) so the script is idempotent.
-- The script resolves bootstrap IDs dynamically via sub-selects.
-- =============================================================================

BEGIN;

-- Helper: grab the bootstrap org & admin user

CREATE TEMP TABLE _seed_ctx ON COMMIT DROP AS
SELECT
    o.id  AS org_id,
    u.id  AS user_id
FROM organizations o
JOIN org_memberships m ON m.org_id = o.id AND m.org_role = 'ORG_OWNER'
JOIN users u           ON u.id = m.user_id
ORDER BY o.created_at
LIMIT 1;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM _seed_ctx) THEN
        RAISE EXCEPTION '[seed] No bootstrap org found - run the app first.';
    END IF;
END $$;

-- Helper: product lookup
CREATE TEMP TABLE _seed_products ON COMMIT DROP AS
SELECT p.id, p.sku
FROM products p
JOIN _seed_ctx c ON p.org_id = c.org_id;


-- ---------------------------------------------------------------------------
-- 1. Stores
-- ---------------------------------------------------------------------------
INSERT INTO stores (id, org_id, name, is_active, updated_at, created_at)
SELECT
    uuid(md5(c.org_id::text || 'Downtown Store')),
    c.org_id, 'Downtown Store', TRUE,
    NOW() - INTERVAL '80 days', NOW() - INTERVAL '80 days'
FROM _seed_ctx c
ON CONFLICT (id) DO NOTHING;

INSERT INTO stores (id, org_id, name, is_active, updated_at, created_at)
SELECT
    uuid(md5(c.org_id::text || 'Eastside Warehouse')),
    c.org_id, 'Eastside Warehouse', TRUE,
    NOW() - INTERVAL '78 days', NOW() - INTERVAL '78 days'
FROM _seed_ctx c
ON CONFLICT (id) DO NOTHING;

CREATE TEMP TABLE _seed_stores ON COMMIT DROP AS
SELECT s.id, s.name
FROM stores s
JOIN _seed_ctx c ON s.org_id = c.org_id
WHERE s.name IN ('Downtown Store', 'Eastside Warehouse');


-- ---------------------------------------------------------------------------
-- 2. Layout Versions  (one per store, 5x8, active)
-- ---------------------------------------------------------------------------
INSERT INTO layout_versions (id, store_id, version_number, rows, cols, is_active, updated_at, created_at)
SELECT
    uuid(md5(st.id::text || 'layout-v1')),
    st.id, 1, 5, 8, TRUE,
    NOW() - INTERVAL '79 days', NOW() - INTERVAL '79 days'
FROM _seed_stores st
WHERE st.name = 'Downtown Store'
ON CONFLICT (id) DO NOTHING;

INSERT INTO layout_versions (id, store_id, version_number, rows, cols, is_active, updated_at, created_at)
SELECT
    uuid(md5(st.id::text || 'layout-v1')),
    st.id, 1, 5, 8, TRUE,
    NOW() - INTERVAL '77 days', NOW() - INTERVAL '77 days'
FROM _seed_stores st
WHERE st.name = 'Eastside Warehouse'
ON CONFLICT (id) DO NOTHING;

-- Layout lookup
CREATE TEMP TABLE _seed_layouts ON COMMIT DROP AS
SELECT lv.id AS layout_id, st.name AS store_name
FROM layout_versions lv
JOIN _seed_stores st ON lv.store_id = st.id
WHERE lv.version_number = 1;


-- ---------------------------------------------------------------------------
-- 3. Zones  (4 per store: Produce, Dairy, Dry Goods, Bulk Storage)
--
--    Downtown Store (5x8 grid):
--      Produce      - rows 0-1, cols 0-2  (6 cells)   apples, oranges
--      Dairy        - rows 0-1, cols 3-4  (4 cells)   milk
--      Dry Goods    - rows 2-3, cols 0-3  (8 cells)   flour, rice
--      Bulk Storage - rows 3-4, cols 4-7  (8 cells)   overflow / restock staging
--
--    Eastside Warehouse (5x8 grid):
--      Produce      - rows 0-1, cols 0-3  (8 cells)
--      Dairy        - rows 0-1, cols 4-7  (8 cells)
--      Dry Goods    - rows 2-3, cols 0-3  (8 cells)
--      Bulk Storage - rows 2-4, cols 4-7  (12 cells)
-- ---------------------------------------------------------------------------

-- Downtown Store zones
INSERT INTO zones (id, layout_version_id, name, color, cells, updated_at, created_at)
SELECT
    uuid(md5(l.layout_id::text || 'Produce')),
    l.layout_id, 'Produce', '#22C55E',
    '[{"row":0,"col":0},{"row":0,"col":1},{"row":0,"col":2},{"row":1,"col":0},{"row":1,"col":1},{"row":1,"col":2}]'::json,
    NOW() - INTERVAL '79 days', NOW() - INTERVAL '79 days'
FROM _seed_layouts l WHERE l.store_name = 'Downtown Store'
ON CONFLICT (id) DO NOTHING;

INSERT INTO zones (id, layout_version_id, name, color, cells, updated_at, created_at)
SELECT
    uuid(md5(l.layout_id::text || 'Dairy')),
    l.layout_id, 'Dairy', '#3B82F6',
    '[{"row":0,"col":3},{"row":0,"col":4},{"row":1,"col":3},{"row":1,"col":4}]'::json,
    NOW() - INTERVAL '79 days', NOW() - INTERVAL '79 days'
FROM _seed_layouts l WHERE l.store_name = 'Downtown Store'
ON CONFLICT (id) DO NOTHING;

INSERT INTO zones (id, layout_version_id, name, color, cells, updated_at, created_at)
SELECT
    uuid(md5(l.layout_id::text || 'Dry Goods')),
    l.layout_id, 'Dry Goods', '#F59E0B',
    '[{"row":2,"col":0},{"row":2,"col":1},{"row":2,"col":2},{"row":2,"col":3},{"row":3,"col":0},{"row":3,"col":1},{"row":3,"col":2},{"row":3,"col":3}]'::json,
    NOW() - INTERVAL '79 days', NOW() - INTERVAL '79 days'
FROM _seed_layouts l WHERE l.store_name = 'Downtown Store'
ON CONFLICT (id) DO NOTHING;

INSERT INTO zones (id, layout_version_id, name, color, cells, updated_at, created_at)
SELECT
    uuid(md5(l.layout_id::text || 'Bulk Storage')),
    l.layout_id, 'Bulk Storage', '#8B5CF6',
    '[{"row":3,"col":4},{"row":3,"col":5},{"row":3,"col":6},{"row":3,"col":7},{"row":4,"col":4},{"row":4,"col":5},{"row":4,"col":6},{"row":4,"col":7}]'::json,
    NOW() - INTERVAL '79 days', NOW() - INTERVAL '79 days'
FROM _seed_layouts l WHERE l.store_name = 'Downtown Store'
ON CONFLICT (id) DO NOTHING;

-- Eastside Warehouse zones
INSERT INTO zones (id, layout_version_id, name, color, cells, updated_at, created_at)
SELECT
    uuid(md5(l.layout_id::text || 'Produce')),
    l.layout_id, 'Produce', '#22C55E',
    '[{"row":0,"col":0},{"row":0,"col":1},{"row":0,"col":2},{"row":0,"col":3},{"row":1,"col":0},{"row":1,"col":1},{"row":1,"col":2},{"row":1,"col":3}]'::json,
    NOW() - INTERVAL '77 days', NOW() - INTERVAL '77 days'
FROM _seed_layouts l WHERE l.store_name = 'Eastside Warehouse'
ON CONFLICT (id) DO NOTHING;

INSERT INTO zones (id, layout_version_id, name, color, cells, updated_at, created_at)
SELECT
    uuid(md5(l.layout_id::text || 'Dairy')),
    l.layout_id, 'Dairy', '#3B82F6',
    '[{"row":0,"col":4},{"row":0,"col":5},{"row":0,"col":6},{"row":0,"col":7},{"row":1,"col":4},{"row":1,"col":5},{"row":1,"col":6},{"row":1,"col":7}]'::json,
    NOW() - INTERVAL '77 days', NOW() - INTERVAL '77 days'
FROM _seed_layouts l WHERE l.store_name = 'Eastside Warehouse'
ON CONFLICT (id) DO NOTHING;

INSERT INTO zones (id, layout_version_id, name, color, cells, updated_at, created_at)
SELECT
    uuid(md5(l.layout_id::text || 'Dry Goods')),
    l.layout_id, 'Dry Goods', '#F59E0B',
    '[{"row":2,"col":0},{"row":2,"col":1},{"row":2,"col":2},{"row":2,"col":3},{"row":3,"col":0},{"row":3,"col":1},{"row":3,"col":2},{"row":3,"col":3}]'::json,
    NOW() - INTERVAL '77 days', NOW() - INTERVAL '77 days'
FROM _seed_layouts l WHERE l.store_name = 'Eastside Warehouse'
ON CONFLICT (id) DO NOTHING;

INSERT INTO zones (id, layout_version_id, name, color, cells, updated_at, created_at)
SELECT
    uuid(md5(l.layout_id::text || 'Bulk Storage')),
    l.layout_id, 'Bulk Storage', '#8B5CF6',
    '[{"row":2,"col":4},{"row":2,"col":5},{"row":2,"col":6},{"row":2,"col":7},{"row":3,"col":4},{"row":3,"col":5},{"row":3,"col":6},{"row":3,"col":7},{"row":4,"col":4},{"row":4,"col":5},{"row":4,"col":6},{"row":4,"col":7}]'::json,
    NOW() - INTERVAL '77 days', NOW() - INTERVAL '77 days'
FROM _seed_layouts l WHERE l.store_name = 'Eastside Warehouse'
ON CONFLICT (id) DO NOTHING;

-- Zone lookup: map (store_name, zone_name) -> zone_id
CREATE TEMP TABLE _seed_zones ON COMMIT DROP AS
SELECT z.id AS zone_id, z.name AS zone_name, sl.store_name
FROM zones z
JOIN _seed_layouts sl ON z.layout_version_id = sl.layout_id;


-- ---------------------------------------------------------------------------
-- 4. Store Inventory  (5 products x 2 stores)
-- ---------------------------------------------------------------------------

-- Downtown Store
INSERT INTO store_inventory (id, store_id, product_id, quantity, unit_price, low_stock_threshold, updated_at, created_at)
SELECT
    uuid(md5(st.id::text || p.id::text)),
    st.id, p.id,
    0,
    CASE p.sku
        WHEN 'PRD-001' THEN 3.49
        WHEN 'PRD-002' THEN 18.99
        WHEN 'PRD-003' THEN 4.29
        WHEN 'PRD-004' THEN 5.49
        WHEN 'PRD-005' THEN 24.99
    END,
    CASE p.sku
        WHEN 'PRD-001' THEN 20
        WHEN 'PRD-002' THEN  8
        WHEN 'PRD-003' THEN 15
        WHEN 'PRD-004' THEN 10
        WHEN 'PRD-005' THEN  5
    END,
    NOW(),
    NOW() - INTERVAL '75 days'
FROM _seed_stores st
CROSS JOIN _seed_products p
WHERE st.name = 'Downtown Store'
ON CONFLICT (id) DO NOTHING;

-- Eastside Warehouse
INSERT INTO store_inventory (id, store_id, product_id, quantity, unit_price, low_stock_threshold, updated_at, created_at)
SELECT
    uuid(md5(st.id::text || p.id::text)),
    st.id, p.id,
    0,
    CASE p.sku
        WHEN 'PRD-001' THEN 3.49
        WHEN 'PRD-002' THEN 18.99
        WHEN 'PRD-003' THEN 4.29
        WHEN 'PRD-004' THEN 5.49
        WHEN 'PRD-005' THEN 24.99
    END,
    CASE p.sku
        WHEN 'PRD-001' THEN 30
        WHEN 'PRD-002' THEN 12
        WHEN 'PRD-003' THEN 25
        WHEN 'PRD-004' THEN 15
        WHEN 'PRD-005' THEN  8
    END,
    NOW(),
    NOW() - INTERVAL '73 days'
FROM _seed_stores st
CROSS JOIN _seed_products p
WHERE st.name = 'Eastside Warehouse'
ON CONFLICT (id) DO NOTHING;

-- Store-inventory lookup
CREATE TEMP TABLE _seed_si ON COMMIT DROP AS
SELECT si.id AS si_id, st.name AS store_name, p.sku
FROM store_inventory si
JOIN _seed_stores  st ON si.store_id  = st.id
JOIN _seed_products p ON si.product_id = p.id;


-- ---------------------------------------------------------------------------
-- 5. Inventory Placements  (one active placement per inventory item)
--
--    Product -> Zone mapping:
--      PRD-001 Organic Apples    -> Produce
--      PRD-002 Whole Wheat Flour -> Dry Goods
--      PRD-003 Organic Oranges   -> Produce
--      PRD-004 Whole Milk        -> Dairy
--      PRD-005 Brown Rice        -> Dry Goods
-- ---------------------------------------------------------------------------
INSERT INTO inventory_placements (id, store_inventory_id, zone_id, ended_at, placed_by_user_id, created_at)
SELECT
    uuid(md5(si.si_id::text || 'placement')),
    si.si_id,
    CASE si.sku
        WHEN 'PRD-001' THEN (SELECT zone_id FROM _seed_zones WHERE store_name = si.store_name AND zone_name = 'Produce')
        WHEN 'PRD-002' THEN (SELECT zone_id FROM _seed_zones WHERE store_name = si.store_name AND zone_name = 'Dry Goods')
        WHEN 'PRD-003' THEN (SELECT zone_id FROM _seed_zones WHERE store_name = si.store_name AND zone_name = 'Produce')
        WHEN 'PRD-004' THEN (SELECT zone_id FROM _seed_zones WHERE store_name = si.store_name AND zone_name = 'Dairy')
        WHEN 'PRD-005' THEN (SELECT zone_id FROM _seed_zones WHERE store_name = si.store_name AND zone_name = 'Dry Goods')
    END,
    NULL,
    c.user_id,
    NOW() - INTERVAL '75 days'
FROM _seed_si si, _seed_ctx c
ON CONFLICT (id) DO NOTHING;


-- ---------------------------------------------------------------------------
-- 6. Inventory Movements  (~15 per item per store, with zone_id)
-- ---------------------------------------------------------------------------

INSERT INTO inventory_movements (
    id, store_inventory_id, movement_type, quantity,
    unit_cost, unit_price, reference_number, notes,
    performed_by_user_id, zone_id, created_at
)
SELECT id, si_id, movement_type::movement_type, quantity,
       unit_cost, unit_price, reference_number, notes,
       user_id, zone_id, created_at
FROM (

-- ======= DOWNTOWN STORE =======

-- PRD-001 Organic Apples (Downtown) -> Produce
SELECT uuid(md5(si.si_id::text || '01')) AS id, si.si_id, 'receipt' AS movement_type, 100 AS quantity, 2.10 AS unit_cost, 3.49 AS unit_price, 'PO-0001' AS reference_number, 'Initial stock - Organic Apples' AS notes, c.user_id, z.zone_id, NOW() - INTERVAL '85 days' AS created_at FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Downtown Store' AND si.sku='PRD-001' AND z.store_name='Downtown Store' AND z.zone_name='Produce'
UNION ALL SELECT uuid(md5(si.si_id::text || '02')), si.si_id, 'sale', -8,  NULL, 3.49, 'SO-0001', 'Walk-in sale', c.user_id, z.zone_id, NOW()-INTERVAL '80 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Downtown Store' AND si.sku='PRD-001' AND z.store_name='Downtown Store' AND z.zone_name='Produce'
UNION ALL SELECT uuid(md5(si.si_id::text || '03')), si.si_id, 'sale', -12, NULL, 3.49, 'SO-0010', 'Morning rush', c.user_id, z.zone_id, NOW()-INTERVAL '73 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Downtown Store' AND si.sku='PRD-001' AND z.store_name='Downtown Store' AND z.zone_name='Produce'
UNION ALL SELECT uuid(md5(si.si_id::text || '04')), si.si_id, 'sale', -6,  NULL, 3.49, 'SO-0020', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '66 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Downtown Store' AND si.sku='PRD-001' AND z.store_name='Downtown Store' AND z.zone_name='Produce'
UNION ALL SELECT uuid(md5(si.si_id::text || '05')), si.si_id, 'receipt', 60, 2.10, 3.49, 'PO-0011', 'Restock - apples running low', c.user_id, z.zone_id, NOW()-INTERVAL '59 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Downtown Store' AND si.sku='PRD-001' AND z.store_name='Downtown Store' AND z.zone_name='Produce'
UNION ALL SELECT uuid(md5(si.si_id::text || '06')), si.si_id, 'sale', -15, NULL, 3.49, 'SO-0030', 'Weekend sale event', c.user_id, z.zone_id, NOW()-INTERVAL '53 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Downtown Store' AND si.sku='PRD-001' AND z.store_name='Downtown Store' AND z.zone_name='Produce'
UNION ALL SELECT uuid(md5(si.si_id::text || '07')), si.si_id, 'sale', -10, NULL, 3.49, 'SO-0040', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '47 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Downtown Store' AND si.sku='PRD-001' AND z.store_name='Downtown Store' AND z.zone_name='Produce'
UNION ALL SELECT uuid(md5(si.si_id::text || '08')), si.si_id, 'sale', -9,  NULL, 3.49, 'SO-0050', 'Bulk order - local cafe', c.user_id, z.zone_id, NOW()-INTERVAL '40 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Downtown Store' AND si.sku='PRD-001' AND z.store_name='Downtown Store' AND z.zone_name='Produce'
UNION ALL SELECT uuid(md5(si.si_id::text || '09')), si.si_id, 'receipt', 50, 2.15, 3.49, 'PO-0021', 'Restock', c.user_id, z.zone_id, NOW()-INTERVAL '34 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Downtown Store' AND si.sku='PRD-001' AND z.store_name='Downtown Store' AND z.zone_name='Produce'
UNION ALL SELECT uuid(md5(si.si_id::text || '10')), si.si_id, 'sale', -14, NULL, 3.49, 'SO-0060', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '28 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Downtown Store' AND si.sku='PRD-001' AND z.store_name='Downtown Store' AND z.zone_name='Produce'
UNION ALL SELECT uuid(md5(si.si_id::text || '11')), si.si_id, 'sale', -11, NULL, 3.49, 'SO-0070', 'Farmers market prep', c.user_id, z.zone_id, NOW()-INTERVAL '22 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Downtown Store' AND si.sku='PRD-001' AND z.store_name='Downtown Store' AND z.zone_name='Produce'
UNION ALL SELECT uuid(md5(si.si_id::text || '12')), si.si_id, 'sale', -7,  NULL, 3.49, 'SO-0080', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '17 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Downtown Store' AND si.sku='PRD-001' AND z.store_name='Downtown Store' AND z.zone_name='Produce'
UNION ALL SELECT uuid(md5(si.si_id::text || '13')), si.si_id, 'receipt', 40, 2.15, 3.49, 'PO-0031', 'Restock - seasonal demand', c.user_id, z.zone_id, NOW()-INTERVAL '11 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Downtown Store' AND si.sku='PRD-001' AND z.store_name='Downtown Store' AND z.zone_name='Produce'
UNION ALL SELECT uuid(md5(si.si_id::text || '14')), si.si_id, 'sale', -5,  NULL, 3.49, 'SO-0090', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '6 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Downtown Store' AND si.sku='PRD-001' AND z.store_name='Downtown Store' AND z.zone_name='Produce'
UNION ALL SELECT uuid(md5(si.si_id::text || '15')), si.si_id, 'sale', -3,  NULL, 3.49, 'SO-0100', 'End-of-week sale', c.user_id, z.zone_id, NOW()-INTERVAL '2 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Downtown Store' AND si.sku='PRD-001' AND z.store_name='Downtown Store' AND z.zone_name='Produce'

-- PRD-002 Whole Wheat Flour (Downtown) -> Dry Goods
UNION ALL SELECT uuid(md5(si.si_id::text || '01')), si.si_id, 'receipt', 40, 12.50, 18.99, 'PO-0002', 'Initial stock - Whole Wheat Flour', c.user_id, z.zone_id, NOW()-INTERVAL '85 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Downtown Store' AND si.sku='PRD-002' AND z.store_name='Downtown Store' AND z.zone_name='Dry Goods'
UNION ALL SELECT uuid(md5(si.si_id::text || '02')), si.si_id, 'sale', -3, NULL, 18.99, 'SO-0002', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '80 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Downtown Store' AND si.sku='PRD-002' AND z.store_name='Downtown Store' AND z.zone_name='Dry Goods'
UNION ALL SELECT uuid(md5(si.si_id::text || '03')), si.si_id, 'sale', -2, NULL, 18.99, 'SO-0011', 'Bakery order', c.user_id, z.zone_id, NOW()-INTERVAL '73 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Downtown Store' AND si.sku='PRD-002' AND z.store_name='Downtown Store' AND z.zone_name='Dry Goods'
UNION ALL SELECT uuid(md5(si.si_id::text || '04')), si.si_id, 'sale', -4, NULL, 18.99, 'SO-0021', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '66 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Downtown Store' AND si.sku='PRD-002' AND z.store_name='Downtown Store' AND z.zone_name='Dry Goods'
UNION ALL SELECT uuid(md5(si.si_id::text || '05')), si.si_id, 'receipt', 25, 12.50, 18.99, 'PO-0012', 'Restock', c.user_id, z.zone_id, NOW()-INTERVAL '59 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Downtown Store' AND si.sku='PRD-002' AND z.store_name='Downtown Store' AND z.zone_name='Dry Goods'
UNION ALL SELECT uuid(md5(si.si_id::text || '06')), si.si_id, 'sale', -5, NULL, 18.99, 'SO-0031', 'Restaurant bulk', c.user_id, z.zone_id, NOW()-INTERVAL '53 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Downtown Store' AND si.sku='PRD-002' AND z.store_name='Downtown Store' AND z.zone_name='Dry Goods'
UNION ALL SELECT uuid(md5(si.si_id::text || '07')), si.si_id, 'sale', -3, NULL, 18.99, 'SO-0041', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '47 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Downtown Store' AND si.sku='PRD-002' AND z.store_name='Downtown Store' AND z.zone_name='Dry Goods'
UNION ALL SELECT uuid(md5(si.si_id::text || '08')), si.si_id, 'sale', -2, NULL, 18.99, 'SO-0051', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '40 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Downtown Store' AND si.sku='PRD-002' AND z.store_name='Downtown Store' AND z.zone_name='Dry Goods'
UNION ALL SELECT uuid(md5(si.si_id::text || '09')), si.si_id, 'receipt', 20, 12.75, 18.99, 'PO-0022', 'Restock - price increase from vendor', c.user_id, z.zone_id, NOW()-INTERVAL '34 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Downtown Store' AND si.sku='PRD-002' AND z.store_name='Downtown Store' AND z.zone_name='Dry Goods'
UNION ALL SELECT uuid(md5(si.si_id::text || '10')), si.si_id, 'sale', -4, NULL, 18.99, 'SO-0061', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '28 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Downtown Store' AND si.sku='PRD-002' AND z.store_name='Downtown Store' AND z.zone_name='Dry Goods'
UNION ALL SELECT uuid(md5(si.si_id::text || '11')), si.si_id, 'sale', -3, NULL, 18.99, 'SO-0071', 'Walk-in', c.user_id, z.zone_id, NOW()-INTERVAL '22 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Downtown Store' AND si.sku='PRD-002' AND z.store_name='Downtown Store' AND z.zone_name='Dry Goods'
UNION ALL SELECT uuid(md5(si.si_id::text || '12')), si.si_id, 'sale', -2, NULL, 18.99, 'SO-0081', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '17 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Downtown Store' AND si.sku='PRD-002' AND z.store_name='Downtown Store' AND z.zone_name='Dry Goods'
UNION ALL SELECT uuid(md5(si.si_id::text || '13')), si.si_id, 'receipt', 15, 12.75, 18.99, 'PO-0032', 'Restock', c.user_id, z.zone_id, NOW()-INTERVAL '11 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Downtown Store' AND si.sku='PRD-002' AND z.store_name='Downtown Store' AND z.zone_name='Dry Goods'
UNION ALL SELECT uuid(md5(si.si_id::text || '14')), si.si_id, 'sale', -3, NULL, 18.99, 'SO-0091', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '6 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Downtown Store' AND si.sku='PRD-002' AND z.store_name='Downtown Store' AND z.zone_name='Dry Goods'
UNION ALL SELECT uuid(md5(si.si_id::text || '15')), si.si_id, 'sale', -1, NULL, 18.99, 'SO-0101', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '2 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Downtown Store' AND si.sku='PRD-002' AND z.store_name='Downtown Store' AND z.zone_name='Dry Goods'

-- PRD-003 Organic Oranges (Downtown) -> Produce
UNION ALL SELECT uuid(md5(si.si_id::text || '01')), si.si_id, 'receipt', 80, 2.80, 4.29, 'PO-0003', 'Initial stock - Organic Oranges', c.user_id, z.zone_id, NOW()-INTERVAL '85 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Downtown Store' AND si.sku='PRD-003' AND z.store_name='Downtown Store' AND z.zone_name='Produce'
UNION ALL SELECT uuid(md5(si.si_id::text || '02')), si.si_id, 'sale', -10, NULL, 4.29, 'SO-0003', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '80 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Downtown Store' AND si.sku='PRD-003' AND z.store_name='Downtown Store' AND z.zone_name='Produce'
UNION ALL SELECT uuid(md5(si.si_id::text || '03')), si.si_id, 'sale', -8,  NULL, 4.29, 'SO-0012', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '73 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Downtown Store' AND si.sku='PRD-003' AND z.store_name='Downtown Store' AND z.zone_name='Produce'
UNION ALL SELECT uuid(md5(si.si_id::text || '04')), si.si_id, 'sale', -12, NULL, 4.29, 'SO-0022', 'Juice bar order', c.user_id, z.zone_id, NOW()-INTERVAL '66 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Downtown Store' AND si.sku='PRD-003' AND z.store_name='Downtown Store' AND z.zone_name='Produce'
UNION ALL SELECT uuid(md5(si.si_id::text || '05')), si.si_id, 'receipt', 60, 2.80, 4.29, 'PO-0013', 'Restock', c.user_id, z.zone_id, NOW()-INTERVAL '59 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Downtown Store' AND si.sku='PRD-003' AND z.store_name='Downtown Store' AND z.zone_name='Produce'
UNION ALL SELECT uuid(md5(si.si_id::text || '06')), si.si_id, 'sale', -9,  NULL, 4.29, 'SO-0032', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '53 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Downtown Store' AND si.sku='PRD-003' AND z.store_name='Downtown Store' AND z.zone_name='Produce'
UNION ALL SELECT uuid(md5(si.si_id::text || '07')), si.si_id, 'sale', -14, NULL, 4.29, 'SO-0042', 'School lunch program', c.user_id, z.zone_id, NOW()-INTERVAL '47 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Downtown Store' AND si.sku='PRD-003' AND z.store_name='Downtown Store' AND z.zone_name='Produce'
UNION ALL SELECT uuid(md5(si.si_id::text || '08')), si.si_id, 'sale', -7,  NULL, 4.29, 'SO-0052', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '40 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Downtown Store' AND si.sku='PRD-003' AND z.store_name='Downtown Store' AND z.zone_name='Produce'
UNION ALL SELECT uuid(md5(si.si_id::text || '09')), si.si_id, 'receipt', 50, 2.85, 4.29, 'PO-0023', 'Restock', c.user_id, z.zone_id, NOW()-INTERVAL '34 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Downtown Store' AND si.sku='PRD-003' AND z.store_name='Downtown Store' AND z.zone_name='Produce'
UNION ALL SELECT uuid(md5(si.si_id::text || '10')), si.si_id, 'sale', -11, NULL, 4.29, 'SO-0062', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '28 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Downtown Store' AND si.sku='PRD-003' AND z.store_name='Downtown Store' AND z.zone_name='Produce'
UNION ALL SELECT uuid(md5(si.si_id::text || '11')), si.si_id, 'sale', -6,  NULL, 4.29, 'SO-0072', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '22 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Downtown Store' AND si.sku='PRD-003' AND z.store_name='Downtown Store' AND z.zone_name='Produce'
UNION ALL SELECT uuid(md5(si.si_id::text || '12')), si.si_id, 'sale', -8,  NULL, 4.29, 'SO-0082', 'Regular customer', c.user_id, z.zone_id, NOW()-INTERVAL '17 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Downtown Store' AND si.sku='PRD-003' AND z.store_name='Downtown Store' AND z.zone_name='Produce'
UNION ALL SELECT uuid(md5(si.si_id::text || '13')), si.si_id, 'receipt', 40, 2.85, 4.29, 'PO-0033', 'Restock', c.user_id, z.zone_id, NOW()-INTERVAL '11 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Downtown Store' AND si.sku='PRD-003' AND z.store_name='Downtown Store' AND z.zone_name='Produce'
UNION ALL SELECT uuid(md5(si.si_id::text || '14')), si.si_id, 'sale', -5,  NULL, 4.29, 'SO-0092', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '6 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Downtown Store' AND si.sku='PRD-003' AND z.store_name='Downtown Store' AND z.zone_name='Produce'
UNION ALL SELECT uuid(md5(si.si_id::text || '15')), si.si_id, 'sale', -10, NULL, 4.29, 'SO-0102', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '2 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Downtown Store' AND si.sku='PRD-003' AND z.store_name='Downtown Store' AND z.zone_name='Produce'

-- PRD-004 Whole Milk (Downtown) -> Dairy
UNION ALL SELECT uuid(md5(si.si_id::text || '01')), si.si_id, 'receipt', 60, 3.20, 5.49, 'PO-0004', 'Initial stock - Whole Milk', c.user_id, z.zone_id, NOW()-INTERVAL '85 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Downtown Store' AND si.sku='PRD-004' AND z.store_name='Downtown Store' AND z.zone_name='Dairy'
UNION ALL SELECT uuid(md5(si.si_id::text || '02')), si.si_id, 'sale', -8,  NULL, 5.49, 'SO-0004', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '82 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Downtown Store' AND si.sku='PRD-004' AND z.store_name='Downtown Store' AND z.zone_name='Dairy'
UNION ALL SELECT uuid(md5(si.si_id::text || '03')), si.si_id, 'sale', -10, NULL, 5.49, 'SO-0013', 'Coffee shop order', c.user_id, z.zone_id, NOW()-INTERVAL '76 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Downtown Store' AND si.sku='PRD-004' AND z.store_name='Downtown Store' AND z.zone_name='Dairy'
UNION ALL SELECT uuid(md5(si.si_id::text || '04')), si.si_id, 'receipt', 48, 3.20, 5.49, 'PO-0014', 'Restock - dairy sells fast', c.user_id, z.zone_id, NOW()-INTERVAL '70 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Downtown Store' AND si.sku='PRD-004' AND z.store_name='Downtown Store' AND z.zone_name='Dairy'
UNION ALL SELECT uuid(md5(si.si_id::text || '05')), si.si_id, 'sale', -12, NULL, 5.49, 'SO-0023', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '64 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Downtown Store' AND si.sku='PRD-004' AND z.store_name='Downtown Store' AND z.zone_name='Dairy'
UNION ALL SELECT uuid(md5(si.si_id::text || '06')), si.si_id, 'sale', -9,  NULL, 5.49, 'SO-0033', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '57 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Downtown Store' AND si.sku='PRD-004' AND z.store_name='Downtown Store' AND z.zone_name='Dairy'
UNION ALL SELECT uuid(md5(si.si_id::text || '07')), si.si_id, 'receipt', 48, 3.25, 5.49, 'PO-0024', 'Restock', c.user_id, z.zone_id, NOW()-INTERVAL '50 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Downtown Store' AND si.sku='PRD-004' AND z.store_name='Downtown Store' AND z.zone_name='Dairy'
UNION ALL SELECT uuid(md5(si.si_id::text || '08')), si.si_id, 'sale', -14, NULL, 5.49, 'SO-0043', 'Daycare weekly order', c.user_id, z.zone_id, NOW()-INTERVAL '43 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Downtown Store' AND si.sku='PRD-004' AND z.store_name='Downtown Store' AND z.zone_name='Dairy'
UNION ALL SELECT uuid(md5(si.si_id::text || '09')), si.si_id, 'sale', -10, NULL, 5.49, 'SO-0053', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '36 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Downtown Store' AND si.sku='PRD-004' AND z.store_name='Downtown Store' AND z.zone_name='Dairy'
UNION ALL SELECT uuid(md5(si.si_id::text || '10')), si.si_id, 'receipt', 36, 3.25, 5.49, 'PO-0034', 'Restock', c.user_id, z.zone_id, NOW()-INTERVAL '30 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Downtown Store' AND si.sku='PRD-004' AND z.store_name='Downtown Store' AND z.zone_name='Dairy'
UNION ALL SELECT uuid(md5(si.si_id::text || '11')), si.si_id, 'sale', -8,  NULL, 5.49, 'SO-0063', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '24 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Downtown Store' AND si.sku='PRD-004' AND z.store_name='Downtown Store' AND z.zone_name='Dairy'
UNION ALL SELECT uuid(md5(si.si_id::text || '12')), si.si_id, 'sale', -11, NULL, 5.49, 'SO-0073', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '18 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Downtown Store' AND si.sku='PRD-004' AND z.store_name='Downtown Store' AND z.zone_name='Dairy'
UNION ALL SELECT uuid(md5(si.si_id::text || '13')), si.si_id, 'receipt', 36, 3.30, 5.49, 'PO-0044', 'Restock - new pricing', c.user_id, z.zone_id, NOW()-INTERVAL '12 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Downtown Store' AND si.sku='PRD-004' AND z.store_name='Downtown Store' AND z.zone_name='Dairy'
UNION ALL SELECT uuid(md5(si.si_id::text || '14')), si.si_id, 'sale', -6,  NULL, 5.49, 'SO-0083', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '7 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Downtown Store' AND si.sku='PRD-004' AND z.store_name='Downtown Store' AND z.zone_name='Dairy'
UNION ALL SELECT uuid(md5(si.si_id::text || '15')), si.si_id, 'sale', -4,  NULL, 5.49, 'SO-0093', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '1 day' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Downtown Store' AND si.sku='PRD-004' AND z.store_name='Downtown Store' AND z.zone_name='Dairy'

-- PRD-005 Brown Rice (Downtown) -> Dry Goods
UNION ALL SELECT uuid(md5(si.si_id::text || '01')), si.si_id, 'receipt', 30, 16.00, 24.99, 'PO-0005', 'Initial stock - Brown Rice', c.user_id, z.zone_id, NOW()-INTERVAL '85 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Downtown Store' AND si.sku='PRD-005' AND z.store_name='Downtown Store' AND z.zone_name='Dry Goods'
UNION ALL SELECT uuid(md5(si.si_id::text || '02')), si.si_id, 'sale', -2, NULL, 24.99, 'SO-0005', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '79 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Downtown Store' AND si.sku='PRD-005' AND z.store_name='Downtown Store' AND z.zone_name='Dry Goods'
UNION ALL SELECT uuid(md5(si.si_id::text || '03')), si.si_id, 'sale', -3, NULL, 24.99, 'SO-0014', 'Restaurant order', c.user_id, z.zone_id, NOW()-INTERVAL '72 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Downtown Store' AND si.sku='PRD-005' AND z.store_name='Downtown Store' AND z.zone_name='Dry Goods'
UNION ALL SELECT uuid(md5(si.si_id::text || '04')), si.si_id, 'sale', -1, NULL, 24.99, 'SO-0024', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '65 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Downtown Store' AND si.sku='PRD-005' AND z.store_name='Downtown Store' AND z.zone_name='Dry Goods'
UNION ALL SELECT uuid(md5(si.si_id::text || '05')), si.si_id, 'receipt', 20, 16.00, 24.99, 'PO-0015', 'Restock', c.user_id, z.zone_id, NOW()-INTERVAL '58 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Downtown Store' AND si.sku='PRD-005' AND z.store_name='Downtown Store' AND z.zone_name='Dry Goods'
UNION ALL SELECT uuid(md5(si.si_id::text || '06')), si.si_id, 'sale', -4, NULL, 24.99, 'SO-0034', 'Meal prep service', c.user_id, z.zone_id, NOW()-INTERVAL '52 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Downtown Store' AND si.sku='PRD-005' AND z.store_name='Downtown Store' AND z.zone_name='Dry Goods'
UNION ALL SELECT uuid(md5(si.si_id::text || '07')), si.si_id, 'sale', -2, NULL, 24.99, 'SO-0044', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '45 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Downtown Store' AND si.sku='PRD-005' AND z.store_name='Downtown Store' AND z.zone_name='Dry Goods'
UNION ALL SELECT uuid(md5(si.si_id::text || '08')), si.si_id, 'sale', -3, NULL, 24.99, 'SO-0054', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '38 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Downtown Store' AND si.sku='PRD-005' AND z.store_name='Downtown Store' AND z.zone_name='Dry Goods'
UNION ALL SELECT uuid(md5(si.si_id::text || '09')), si.si_id, 'receipt', 15, 16.25, 24.99, 'PO-0025', 'Restock', c.user_id, z.zone_id, NOW()-INTERVAL '31 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Downtown Store' AND si.sku='PRD-005' AND z.store_name='Downtown Store' AND z.zone_name='Dry Goods'
UNION ALL SELECT uuid(md5(si.si_id::text || '10')), si.si_id, 'sale', -2, NULL, 24.99, 'SO-0064', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '25 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Downtown Store' AND si.sku='PRD-005' AND z.store_name='Downtown Store' AND z.zone_name='Dry Goods'
UNION ALL SELECT uuid(md5(si.si_id::text || '11')), si.si_id, 'sale', -5, NULL, 24.99, 'SO-0074', 'Caterer bulk', c.user_id, z.zone_id, NOW()-INTERVAL '19 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Downtown Store' AND si.sku='PRD-005' AND z.store_name='Downtown Store' AND z.zone_name='Dry Goods'
UNION ALL SELECT uuid(md5(si.si_id::text || '12')), si.si_id, 'sale', -1, NULL, 24.99, 'SO-0084', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '14 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Downtown Store' AND si.sku='PRD-005' AND z.store_name='Downtown Store' AND z.zone_name='Dry Goods'
UNION ALL SELECT uuid(md5(si.si_id::text || '13')), si.si_id, 'receipt', 15, 16.25, 24.99, 'PO-0035', 'Restock', c.user_id, z.zone_id, NOW()-INTERVAL '9 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Downtown Store' AND si.sku='PRD-005' AND z.store_name='Downtown Store' AND z.zone_name='Dry Goods'
UNION ALL SELECT uuid(md5(si.si_id::text || '14')), si.si_id, 'sale', -3, NULL, 24.99, 'SO-0094', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '4 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Downtown Store' AND si.sku='PRD-005' AND z.store_name='Downtown Store' AND z.zone_name='Dry Goods'
UNION ALL SELECT uuid(md5(si.si_id::text || '15')), si.si_id, 'sale', -2, NULL, 24.99, 'SO-0104', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '1 day' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Downtown Store' AND si.sku='PRD-005' AND z.store_name='Downtown Store' AND z.zone_name='Dry Goods'

-- ======= EASTSIDE WAREHOUSE =======

-- PRD-001 Organic Apples (Eastside) -> Produce
UNION ALL SELECT uuid(md5(si.si_id::text || '01')), si.si_id, 'receipt', 150, 2.05, 3.49, 'PO-1001', 'Initial stock - Organic Apples (warehouse)', c.user_id, z.zone_id, NOW()-INTERVAL '83 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Eastside Warehouse' AND si.sku='PRD-001' AND z.store_name='Eastside Warehouse' AND z.zone_name='Produce'
UNION ALL SELECT uuid(md5(si.si_id::text || '02')), si.si_id, 'sale', -20, NULL, 3.49, 'SO-1001', 'Grocery chain order', c.user_id, z.zone_id, NOW()-INTERVAL '78 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Eastside Warehouse' AND si.sku='PRD-001' AND z.store_name='Eastside Warehouse' AND z.zone_name='Produce'
UNION ALL SELECT uuid(md5(si.si_id::text || '03')), si.si_id, 'sale', -15, NULL, 3.49, 'SO-1010', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '71 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Eastside Warehouse' AND si.sku='PRD-001' AND z.store_name='Eastside Warehouse' AND z.zone_name='Produce'
UNION ALL SELECT uuid(md5(si.si_id::text || '04')), si.si_id, 'sale', -18, NULL, 3.49, 'SO-1020', 'Weekly distribution', c.user_id, z.zone_id, NOW()-INTERVAL '64 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Eastside Warehouse' AND si.sku='PRD-001' AND z.store_name='Eastside Warehouse' AND z.zone_name='Produce'
UNION ALL SELECT uuid(md5(si.si_id::text || '05')), si.si_id, 'receipt', 100, 2.10, 3.49, 'PO-1011', 'Restock', c.user_id, z.zone_id, NOW()-INTERVAL '57 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Eastside Warehouse' AND si.sku='PRD-001' AND z.store_name='Eastside Warehouse' AND z.zone_name='Produce'
UNION ALL SELECT uuid(md5(si.si_id::text || '06')), si.si_id, 'sale', -25, NULL, 3.49, 'SO-1030', 'Large wholesale', c.user_id, z.zone_id, NOW()-INTERVAL '50 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Eastside Warehouse' AND si.sku='PRD-001' AND z.store_name='Eastside Warehouse' AND z.zone_name='Produce'
UNION ALL SELECT uuid(md5(si.si_id::text || '07')), si.si_id, 'sale', -12, NULL, 3.49, 'SO-1040', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '43 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Eastside Warehouse' AND si.sku='PRD-001' AND z.store_name='Eastside Warehouse' AND z.zone_name='Produce'
UNION ALL SELECT uuid(md5(si.si_id::text || '08')), si.si_id, 'sale', -10, NULL, 3.49, 'SO-1050', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '36 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Eastside Warehouse' AND si.sku='PRD-001' AND z.store_name='Eastside Warehouse' AND z.zone_name='Produce'
UNION ALL SELECT uuid(md5(si.si_id::text || '09')), si.si_id, 'receipt', 80, 2.10, 3.49, 'PO-1021', 'Restock', c.user_id, z.zone_id, NOW()-INTERVAL '29 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Eastside Warehouse' AND si.sku='PRD-001' AND z.store_name='Eastside Warehouse' AND z.zone_name='Produce'
UNION ALL SELECT uuid(md5(si.si_id::text || '10')), si.si_id, 'sale', -22, NULL, 3.49, 'SO-1060', 'School district order', c.user_id, z.zone_id, NOW()-INTERVAL '22 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Eastside Warehouse' AND si.sku='PRD-001' AND z.store_name='Eastside Warehouse' AND z.zone_name='Produce'
UNION ALL SELECT uuid(md5(si.si_id::text || '11')), si.si_id, 'sale', -16, NULL, 3.49, 'SO-1070', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '15 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Eastside Warehouse' AND si.sku='PRD-001' AND z.store_name='Eastside Warehouse' AND z.zone_name='Produce'
UNION ALL SELECT uuid(md5(si.si_id::text || '12')), si.si_id, 'sale', -14, NULL, 3.49, 'SO-1080', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '10 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Eastside Warehouse' AND si.sku='PRD-001' AND z.store_name='Eastside Warehouse' AND z.zone_name='Produce'
UNION ALL SELECT uuid(md5(si.si_id::text || '13')), si.si_id, 'receipt', 70, 2.15, 3.49, 'PO-1031', 'Restock - seasonal peak', c.user_id, z.zone_id, NOW()-INTERVAL '7 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Eastside Warehouse' AND si.sku='PRD-001' AND z.store_name='Eastside Warehouse' AND z.zone_name='Produce'
UNION ALL SELECT uuid(md5(si.si_id::text || '14')), si.si_id, 'sale', -18, NULL, 3.49, 'SO-1090', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '4 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Eastside Warehouse' AND si.sku='PRD-001' AND z.store_name='Eastside Warehouse' AND z.zone_name='Produce'
UNION ALL SELECT uuid(md5(si.si_id::text || '15')), si.si_id, 'sale', -10, NULL, 3.49, 'SO-1100', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '1 day' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Eastside Warehouse' AND si.sku='PRD-001' AND z.store_name='Eastside Warehouse' AND z.zone_name='Produce'

-- PRD-002 Whole Wheat Flour (Eastside) -> Dry Goods
UNION ALL SELECT uuid(md5(si.si_id::text || '01')), si.si_id, 'receipt', 60, 12.00, 18.99, 'PO-1002', 'Initial stock - Whole Wheat Flour (warehouse)', c.user_id, z.zone_id, NOW()-INTERVAL '83 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Eastside Warehouse' AND si.sku='PRD-002' AND z.store_name='Eastside Warehouse' AND z.zone_name='Dry Goods'
UNION ALL SELECT uuid(md5(si.si_id::text || '02')), si.si_id, 'sale', -5, NULL, 18.99, 'SO-1002', 'Bakery chain', c.user_id, z.zone_id, NOW()-INTERVAL '77 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Eastside Warehouse' AND si.sku='PRD-002' AND z.store_name='Eastside Warehouse' AND z.zone_name='Dry Goods'
UNION ALL SELECT uuid(md5(si.si_id::text || '03')), si.si_id, 'sale', -8, NULL, 18.99, 'SO-1011', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '70 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Eastside Warehouse' AND si.sku='PRD-002' AND z.store_name='Eastside Warehouse' AND z.zone_name='Dry Goods'
UNION ALL SELECT uuid(md5(si.si_id::text || '04')), si.si_id, 'sale', -4, NULL, 18.99, 'SO-1021', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '63 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Eastside Warehouse' AND si.sku='PRD-002' AND z.store_name='Eastside Warehouse' AND z.zone_name='Dry Goods'
UNION ALL SELECT uuid(md5(si.si_id::text || '05')), si.si_id, 'receipt', 40, 12.25, 18.99, 'PO-1012', 'Restock', c.user_id, z.zone_id, NOW()-INTERVAL '56 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Eastside Warehouse' AND si.sku='PRD-002' AND z.store_name='Eastside Warehouse' AND z.zone_name='Dry Goods'
UNION ALL SELECT uuid(md5(si.si_id::text || '06')), si.si_id, 'sale', -6, NULL, 18.99, 'SO-1031', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '49 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Eastside Warehouse' AND si.sku='PRD-002' AND z.store_name='Eastside Warehouse' AND z.zone_name='Dry Goods'
UNION ALL SELECT uuid(md5(si.si_id::text || '07')), si.si_id, 'sale', -7, NULL, 18.99, 'SO-1041', 'Large bakery order', c.user_id, z.zone_id, NOW()-INTERVAL '42 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Eastside Warehouse' AND si.sku='PRD-002' AND z.store_name='Eastside Warehouse' AND z.zone_name='Dry Goods'
UNION ALL SELECT uuid(md5(si.si_id::text || '08')), si.si_id, 'sale', -3, NULL, 18.99, 'SO-1051', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '35 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Eastside Warehouse' AND si.sku='PRD-002' AND z.store_name='Eastside Warehouse' AND z.zone_name='Dry Goods'
UNION ALL SELECT uuid(md5(si.si_id::text || '09')), si.si_id, 'receipt', 30, 12.25, 18.99, 'PO-1022', 'Restock', c.user_id, z.zone_id, NOW()-INTERVAL '28 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Eastside Warehouse' AND si.sku='PRD-002' AND z.store_name='Eastside Warehouse' AND z.zone_name='Dry Goods'
UNION ALL SELECT uuid(md5(si.si_id::text || '10')), si.si_id, 'sale', -5, NULL, 18.99, 'SO-1061', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '21 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Eastside Warehouse' AND si.sku='PRD-002' AND z.store_name='Eastside Warehouse' AND z.zone_name='Dry Goods'
UNION ALL SELECT uuid(md5(si.si_id::text || '11')), si.si_id, 'sale', -4, NULL, 18.99, 'SO-1071', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '16 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Eastside Warehouse' AND si.sku='PRD-002' AND z.store_name='Eastside Warehouse' AND z.zone_name='Dry Goods'
UNION ALL SELECT uuid(md5(si.si_id::text || '12')), si.si_id, 'sale', -6, NULL, 18.99, 'SO-1081', 'Pizza restaurant', c.user_id, z.zone_id, NOW()-INTERVAL '11 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Eastside Warehouse' AND si.sku='PRD-002' AND z.store_name='Eastside Warehouse' AND z.zone_name='Dry Goods'
UNION ALL SELECT uuid(md5(si.si_id::text || '13')), si.si_id, 'receipt', 25, 12.50, 18.99, 'PO-1032', 'Restock', c.user_id, z.zone_id, NOW()-INTERVAL '8 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Eastside Warehouse' AND si.sku='PRD-002' AND z.store_name='Eastside Warehouse' AND z.zone_name='Dry Goods'
UNION ALL SELECT uuid(md5(si.si_id::text || '14')), si.si_id, 'sale', -3, NULL, 18.99, 'SO-1091', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '4 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Eastside Warehouse' AND si.sku='PRD-002' AND z.store_name='Eastside Warehouse' AND z.zone_name='Dry Goods'
UNION ALL SELECT uuid(md5(si.si_id::text || '15')), si.si_id, 'sale', -4, NULL, 18.99, 'SO-1101', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '1 day' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Eastside Warehouse' AND si.sku='PRD-002' AND z.store_name='Eastside Warehouse' AND z.zone_name='Dry Goods'

-- PRD-003 Organic Oranges (Eastside) -> Produce
UNION ALL SELECT uuid(md5(si.si_id::text || '01')), si.si_id, 'receipt', 120, 2.70, 4.29, 'PO-1003', 'Initial stock - Organic Oranges (warehouse)', c.user_id, z.zone_id, NOW()-INTERVAL '83 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Eastside Warehouse' AND si.sku='PRD-003' AND z.store_name='Eastside Warehouse' AND z.zone_name='Produce'
UNION ALL SELECT uuid(md5(si.si_id::text || '02')), si.si_id, 'sale', -15, NULL, 4.29, 'SO-1003', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '77 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Eastside Warehouse' AND si.sku='PRD-003' AND z.store_name='Eastside Warehouse' AND z.zone_name='Produce'
UNION ALL SELECT uuid(md5(si.si_id::text || '03')), si.si_id, 'sale', -20, NULL, 4.29, 'SO-1012', 'Juice company', c.user_id, z.zone_id, NOW()-INTERVAL '70 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Eastside Warehouse' AND si.sku='PRD-003' AND z.store_name='Eastside Warehouse' AND z.zone_name='Produce'
UNION ALL SELECT uuid(md5(si.si_id::text || '04')), si.si_id, 'sale', -10, NULL, 4.29, 'SO-1022', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '63 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Eastside Warehouse' AND si.sku='PRD-003' AND z.store_name='Eastside Warehouse' AND z.zone_name='Produce'
UNION ALL SELECT uuid(md5(si.si_id::text || '05')), si.si_id, 'receipt', 80, 2.75, 4.29, 'PO-1013', 'Restock', c.user_id, z.zone_id, NOW()-INTERVAL '56 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Eastside Warehouse' AND si.sku='PRD-003' AND z.store_name='Eastside Warehouse' AND z.zone_name='Produce'
UNION ALL SELECT uuid(md5(si.si_id::text || '06')), si.si_id, 'sale', -18, NULL, 4.29, 'SO-1032', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '49 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Eastside Warehouse' AND si.sku='PRD-003' AND z.store_name='Eastside Warehouse' AND z.zone_name='Produce'
UNION ALL SELECT uuid(md5(si.si_id::text || '07')), si.si_id, 'sale', -12, NULL, 4.29, 'SO-1042', 'Farmers market', c.user_id, z.zone_id, NOW()-INTERVAL '42 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Eastside Warehouse' AND si.sku='PRD-003' AND z.store_name='Eastside Warehouse' AND z.zone_name='Produce'
UNION ALL SELECT uuid(md5(si.si_id::text || '08')), si.si_id, 'sale', -8,  NULL, 4.29, 'SO-1052', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '35 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Eastside Warehouse' AND si.sku='PRD-003' AND z.store_name='Eastside Warehouse' AND z.zone_name='Produce'
UNION ALL SELECT uuid(md5(si.si_id::text || '09')), si.si_id, 'receipt', 70, 2.80, 4.29, 'PO-1023', 'Restock', c.user_id, z.zone_id, NOW()-INTERVAL '28 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Eastside Warehouse' AND si.sku='PRD-003' AND z.store_name='Eastside Warehouse' AND z.zone_name='Produce'
UNION ALL SELECT uuid(md5(si.si_id::text || '10')), si.si_id, 'sale', -22, NULL, 4.29, 'SO-1062', 'Hotel chain', c.user_id, z.zone_id, NOW()-INTERVAL '21 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Eastside Warehouse' AND si.sku='PRD-003' AND z.store_name='Eastside Warehouse' AND z.zone_name='Produce'
UNION ALL SELECT uuid(md5(si.si_id::text || '11')), si.si_id, 'sale', -14, NULL, 4.29, 'SO-1072', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '15 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Eastside Warehouse' AND si.sku='PRD-003' AND z.store_name='Eastside Warehouse' AND z.zone_name='Produce'
UNION ALL SELECT uuid(md5(si.si_id::text || '12')), si.si_id, 'sale', -11, NULL, 4.29, 'SO-1082', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '10 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Eastside Warehouse' AND si.sku='PRD-003' AND z.store_name='Eastside Warehouse' AND z.zone_name='Produce'
UNION ALL SELECT uuid(md5(si.si_id::text || '13')), si.si_id, 'receipt', 60, 2.80, 4.29, 'PO-1033', 'Restock', c.user_id, z.zone_id, NOW()-INTERVAL '7 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Eastside Warehouse' AND si.sku='PRD-003' AND z.store_name='Eastside Warehouse' AND z.zone_name='Produce'
UNION ALL SELECT uuid(md5(si.si_id::text || '14')), si.si_id, 'sale', -16, NULL, 4.29, 'SO-1092', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '4 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Eastside Warehouse' AND si.sku='PRD-003' AND z.store_name='Eastside Warehouse' AND z.zone_name='Produce'
UNION ALL SELECT uuid(md5(si.si_id::text || '15')), si.si_id, 'sale', -9,  NULL, 4.29, 'SO-1102', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '1 day' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Eastside Warehouse' AND si.sku='PRD-003' AND z.store_name='Eastside Warehouse' AND z.zone_name='Produce'

-- PRD-004 Whole Milk (Eastside) -> Dairy
UNION ALL SELECT uuid(md5(si.si_id::text || '01')), si.si_id, 'receipt', 96, 3.10, 5.49, 'PO-1004', 'Initial stock - Whole Milk (warehouse)', c.user_id, z.zone_id, NOW()-INTERVAL '83 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Eastside Warehouse' AND si.sku='PRD-004' AND z.store_name='Eastside Warehouse' AND z.zone_name='Dairy'
UNION ALL SELECT uuid(md5(si.si_id::text || '02')), si.si_id, 'sale', -12, NULL, 5.49, 'SO-1004', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '79 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Eastside Warehouse' AND si.sku='PRD-004' AND z.store_name='Eastside Warehouse' AND z.zone_name='Dairy'
UNION ALL SELECT uuid(md5(si.si_id::text || '03')), si.si_id, 'sale', -15, NULL, 5.49, 'SO-1013', 'Cafe chain', c.user_id, z.zone_id, NOW()-INTERVAL '73 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Eastside Warehouse' AND si.sku='PRD-004' AND z.store_name='Eastside Warehouse' AND z.zone_name='Dairy'
UNION ALL SELECT uuid(md5(si.si_id::text || '04')), si.si_id, 'receipt', 72, 3.15, 5.49, 'PO-1014', 'Restock', c.user_id, z.zone_id, NOW()-INTERVAL '67 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Eastside Warehouse' AND si.sku='PRD-004' AND z.store_name='Eastside Warehouse' AND z.zone_name='Dairy'
UNION ALL SELECT uuid(md5(si.si_id::text || '05')), si.si_id, 'sale', -18, NULL, 5.49, 'SO-1023', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '61 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Eastside Warehouse' AND si.sku='PRD-004' AND z.store_name='Eastside Warehouse' AND z.zone_name='Dairy'
UNION ALL SELECT uuid(md5(si.si_id::text || '06')), si.si_id, 'sale', -10, NULL, 5.49, 'SO-1033', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '55 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Eastside Warehouse' AND si.sku='PRD-004' AND z.store_name='Eastside Warehouse' AND z.zone_name='Dairy'
UNION ALL SELECT uuid(md5(si.si_id::text || '07')), si.si_id, 'receipt', 60, 3.15, 5.49, 'PO-1024', 'Restock', c.user_id, z.zone_id, NOW()-INTERVAL '49 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Eastside Warehouse' AND si.sku='PRD-004' AND z.store_name='Eastside Warehouse' AND z.zone_name='Dairy'
UNION ALL SELECT uuid(md5(si.si_id::text || '08')), si.si_id, 'sale', -20, NULL, 5.49, 'SO-1043', 'Hospital cafeteria', c.user_id, z.zone_id, NOW()-INTERVAL '43 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Eastside Warehouse' AND si.sku='PRD-004' AND z.store_name='Eastside Warehouse' AND z.zone_name='Dairy'
UNION ALL SELECT uuid(md5(si.si_id::text || '09')), si.si_id, 'sale', -14, NULL, 5.49, 'SO-1053', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '37 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Eastside Warehouse' AND si.sku='PRD-004' AND z.store_name='Eastside Warehouse' AND z.zone_name='Dairy'
UNION ALL SELECT uuid(md5(si.si_id::text || '10')), si.si_id, 'receipt', 48, 3.20, 5.49, 'PO-1034', 'Restock', c.user_id, z.zone_id, NOW()-INTERVAL '31 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Eastside Warehouse' AND si.sku='PRD-004' AND z.store_name='Eastside Warehouse' AND z.zone_name='Dairy'
UNION ALL SELECT uuid(md5(si.si_id::text || '11')), si.si_id, 'sale', -16, NULL, 5.49, 'SO-1063', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '25 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Eastside Warehouse' AND si.sku='PRD-004' AND z.store_name='Eastside Warehouse' AND z.zone_name='Dairy'
UNION ALL SELECT uuid(md5(si.si_id::text || '12')), si.si_id, 'sale', -11, NULL, 5.49, 'SO-1073', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '19 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Eastside Warehouse' AND si.sku='PRD-004' AND z.store_name='Eastside Warehouse' AND z.zone_name='Dairy'
UNION ALL SELECT uuid(md5(si.si_id::text || '13')), si.si_id, 'receipt', 48, 3.20, 5.49, 'PO-1044', 'Restock', c.user_id, z.zone_id, NOW()-INTERVAL '13 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Eastside Warehouse' AND si.sku='PRD-004' AND z.store_name='Eastside Warehouse' AND z.zone_name='Dairy'
UNION ALL SELECT uuid(md5(si.si_id::text || '14')), si.si_id, 'sale', -8,  NULL, 5.49, 'SO-1083', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '7 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Eastside Warehouse' AND si.sku='PRD-004' AND z.store_name='Eastside Warehouse' AND z.zone_name='Dairy'
UNION ALL SELECT uuid(md5(si.si_id::text || '15')), si.si_id, 'sale', -12, NULL, 5.49, 'SO-1093', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '2 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Eastside Warehouse' AND si.sku='PRD-004' AND z.store_name='Eastside Warehouse' AND z.zone_name='Dairy'

-- PRD-005 Brown Rice (Eastside) -> Dry Goods
UNION ALL SELECT uuid(md5(si.si_id::text || '01')), si.si_id, 'receipt', 50, 15.50, 24.99, 'PO-1005', 'Initial stock - Brown Rice (warehouse)', c.user_id, z.zone_id, NOW()-INTERVAL '83 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Eastside Warehouse' AND si.sku='PRD-005' AND z.store_name='Eastside Warehouse' AND z.zone_name='Dry Goods'
UNION ALL SELECT uuid(md5(si.si_id::text || '02')), si.si_id, 'sale', -4, NULL, 24.99, 'SO-1005', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '77 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Eastside Warehouse' AND si.sku='PRD-005' AND z.store_name='Eastside Warehouse' AND z.zone_name='Dry Goods'
UNION ALL SELECT uuid(md5(si.si_id::text || '03')), si.si_id, 'sale', -6, NULL, 24.99, 'SO-1014', 'Thai restaurant', c.user_id, z.zone_id, NOW()-INTERVAL '70 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Eastside Warehouse' AND si.sku='PRD-005' AND z.store_name='Eastside Warehouse' AND z.zone_name='Dry Goods'
UNION ALL SELECT uuid(md5(si.si_id::text || '04')), si.si_id, 'sale', -3, NULL, 24.99, 'SO-1024', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '63 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Eastside Warehouse' AND si.sku='PRD-005' AND z.store_name='Eastside Warehouse' AND z.zone_name='Dry Goods'
UNION ALL SELECT uuid(md5(si.si_id::text || '05')), si.si_id, 'receipt', 35, 15.75, 24.99, 'PO-1015', 'Restock', c.user_id, z.zone_id, NOW()-INTERVAL '56 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Eastside Warehouse' AND si.sku='PRD-005' AND z.store_name='Eastside Warehouse' AND z.zone_name='Dry Goods'
UNION ALL SELECT uuid(md5(si.si_id::text || '06')), si.si_id, 'sale', -8, NULL, 24.99, 'SO-1034', 'Bulk buyer', c.user_id, z.zone_id, NOW()-INTERVAL '49 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Eastside Warehouse' AND si.sku='PRD-005' AND z.store_name='Eastside Warehouse' AND z.zone_name='Dry Goods'
UNION ALL SELECT uuid(md5(si.si_id::text || '07')), si.si_id, 'sale', -5, NULL, 24.99, 'SO-1044', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '42 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Eastside Warehouse' AND si.sku='PRD-005' AND z.store_name='Eastside Warehouse' AND z.zone_name='Dry Goods'
UNION ALL SELECT uuid(md5(si.si_id::text || '08')), si.si_id, 'sale', -3, NULL, 24.99, 'SO-1054', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '35 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Eastside Warehouse' AND si.sku='PRD-005' AND z.store_name='Eastside Warehouse' AND z.zone_name='Dry Goods'
UNION ALL SELECT uuid(md5(si.si_id::text || '09')), si.si_id, 'receipt', 25, 15.75, 24.99, 'PO-1025', 'Restock', c.user_id, z.zone_id, NOW()-INTERVAL '28 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Eastside Warehouse' AND si.sku='PRD-005' AND z.store_name='Eastside Warehouse' AND z.zone_name='Dry Goods'
UNION ALL SELECT uuid(md5(si.si_id::text || '10')), si.si_id, 'sale', -4, NULL, 24.99, 'SO-1064', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '21 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Eastside Warehouse' AND si.sku='PRD-005' AND z.store_name='Eastside Warehouse' AND z.zone_name='Dry Goods'
UNION ALL SELECT uuid(md5(si.si_id::text || '11')), si.si_id, 'sale', -7, NULL, 24.99, 'SO-1074', 'Sushi restaurant', c.user_id, z.zone_id, NOW()-INTERVAL '15 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Eastside Warehouse' AND si.sku='PRD-005' AND z.store_name='Eastside Warehouse' AND z.zone_name='Dry Goods'
UNION ALL SELECT uuid(md5(si.si_id::text || '12')), si.si_id, 'sale', -2, NULL, 24.99, 'SO-1084', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '10 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Eastside Warehouse' AND si.sku='PRD-005' AND z.store_name='Eastside Warehouse' AND z.zone_name='Dry Goods'
UNION ALL SELECT uuid(md5(si.si_id::text || '13')), si.si_id, 'receipt', 20, 16.00, 24.99, 'PO-1035', 'Restock', c.user_id, z.zone_id, NOW()-INTERVAL '7 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Eastside Warehouse' AND si.sku='PRD-005' AND z.store_name='Eastside Warehouse' AND z.zone_name='Dry Goods'
UNION ALL SELECT uuid(md5(si.si_id::text || '14')), si.si_id, 'sale', -5, NULL, 24.99, 'SO-1094', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '3 days' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Eastside Warehouse' AND si.sku='PRD-005' AND z.store_name='Eastside Warehouse' AND z.zone_name='Dry Goods'
UNION ALL SELECT uuid(md5(si.si_id::text || '15')), si.si_id, 'sale', -3, NULL, 24.99, 'SO-1104', NULL, c.user_id, z.zone_id, NOW()-INTERVAL '1 day' FROM _seed_si si, _seed_ctx c, _seed_zones z WHERE si.store_name='Eastside Warehouse' AND si.sku='PRD-005' AND z.store_name='Eastside Warehouse' AND z.zone_name='Dry Goods'

) movements
ON CONFLICT (id) DO NOTHING;


-- ---------------------------------------------------------------------------
-- 7. Update store_inventory quantities to match movement totals
-- ---------------------------------------------------------------------------
UPDATE store_inventory si
SET quantity = sub.net_qty
FROM (
    SELECT im.store_inventory_id, SUM(im.quantity) AS net_qty
    FROM inventory_movements im
    GROUP BY im.store_inventory_id
) sub
WHERE si.id = sub.store_inventory_id;


COMMIT;

-- =============================================================================
-- CLEANUP (uncomment to remove all seed data)
-- =============================================================================
-- BEGIN;
-- DELETE FROM inventory_placements WHERE store_inventory_id IN (
--     SELECT si.id FROM store_inventory si
--     JOIN stores s ON si.store_id = s.id
--     WHERE s.name IN ('Downtown Store','Eastside Warehouse')
-- );
-- DELETE FROM inventory_movements WHERE store_inventory_id IN (
--     SELECT si.id FROM store_inventory si
--     JOIN stores s ON si.store_id = s.id
--     WHERE s.name IN ('Downtown Store','Eastside Warehouse')
-- );
-- DELETE FROM store_inventory WHERE store_id IN (
--     SELECT id FROM stores WHERE name IN ('Downtown Store','Eastside Warehouse')
-- );
-- DELETE FROM zones WHERE layout_version_id IN (
--     SELECT lv.id FROM layout_versions lv
--     JOIN stores s ON lv.store_id = s.id
--     WHERE s.name IN ('Downtown Store','Eastside Warehouse')
-- );
-- DELETE FROM layout_versions WHERE store_id IN (
--     SELECT id FROM stores WHERE name IN ('Downtown Store','Eastside Warehouse')
-- );
-- DELETE FROM stores WHERE name IN ('Downtown Store','Eastside Warehouse');
-- COMMIT;
