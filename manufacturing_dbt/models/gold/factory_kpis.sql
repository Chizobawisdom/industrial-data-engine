{{ config(materialized='table', schema='gold') }}

-- =====================================================
-- 1. DEVICE LIFECYCLE
-- =====================================================

WITH created AS (
    SELECT
        serial_number,
        MIN(sim_timestamp) AS created_at
    FROM {{ ref('station_visits') }}
    WHERE station = 'SOURCE'
      AND action = 'ENTRY'
    GROUP BY serial_number
),

packaged AS (
    SELECT
        serial_number,
        MIN(sim_timestamp) AS packaged_at
    FROM {{ ref('station_visits') }}
    WHERE station = 'PACKAGING'
      AND action = 'EXIT'
    GROUP BY serial_number
),

scrapped AS (
    SELECT DISTINCT serial_number
    FROM {{ ref('scrap_events') }}
),

rework_units AS (
    SELECT DISTINCT serial_number
    FROM {{ ref('rework_events') }}
),

device_lifecycle AS (
    SELECT
        c.serial_number,
        c.created_at,
        p.packaged_at,
        p.serial_number IS NOT NULL AS is_packaged,
        s.serial_number IS NOT NULL AS is_scrapped,
        r.serial_number IS NOT NULL AS is_reworked
    FROM created AS c
    LEFT JOIN packaged AS p USING (serial_number)
    LEFT JOIN scrapped AS s USING (serial_number)
    LEFT JOIN rework_units AS r USING (serial_number)
),

-- =====================================================
-- 2. PRODUCTION COUNTS
-- =====================================================

production_counts AS (
    SELECT
        COUNT(*) AS created_units,

        COUNT(*) FILTER (
            WHERE is_packaged AND NOT is_scrapped
        ) AS packaged_units,

        COUNT(*) FILTER (
            WHERE is_scrapped AND NOT is_packaged
        ) AS scrapped_units,

        COUNT(*) FILTER (
            WHERE is_reworked
        ) AS reworked_units,

        COUNT(*) FILTER (
            WHERE NOT is_packaged
              AND NOT is_scrapped
        ) AS wip_units,

        COUNT(*) FILTER (
            WHERE is_packaged AND is_scrapped
        ) AS conflicting_outcomes,

        AVG(packaged_at - created_at) FILTER (
            WHERE is_packaged
              AND NOT is_scrapped
              AND packaged_at >= created_at
        ) AS avg_total_cycle_time

    FROM device_lifecycle
),

-- =====================================================
-- 3. ELECTRICAL TESTING FIRST PASS YIELD
-- =====================================================

first_test AS (
    SELECT DISTINCT ON (serial_number)
        serial_number,
        result
    FROM {{ ref('quality_inspections') }}
    WHERE station = 'ELEC_TESTING'
    ORDER BY
        serial_number,
        sim_timestamp
),

fpy_counts AS (
    SELECT
        COUNT(*) FILTER (
            WHERE result IN ('PASS', 'FAIL')
        ) AS total_initial_tests,

        COUNT(*) FILTER (
            WHERE result = 'PASS'
        ) AS passed_first_time,

        COUNT(*) FILTER (
            WHERE result = 'FAIL'
        ) AS failed_first_time

    FROM first_test
),

-- =====================================================
-- 4. ELECTRICAL TESTING PERFORMANCE
-- Includes retests after rework
-- =====================================================

electrical_tests AS (
    SELECT
        COUNT(*) FILTER (
            WHERE result IN ('PASS', 'FAIL')
        ) AS total_electrical_tests,

        COUNT(*) FILTER (
            WHERE result = 'PASS'
        ) AS electrical_tests_passed,

        COUNT(*) FILTER (
            WHERE result = 'FAIL'
        ) AS electrical_tests_failed

    FROM {{ ref('quality_inspections') }}
    WHERE station = 'ELEC_TESTING'
),

-- =====================================================
-- 5. FINAL INSPECTION PERFORMANCE
-- =====================================================

final_inspections AS (
    SELECT
        COUNT(*) FILTER (
            WHERE result IN ('PASS', 'FAIL')
        ) AS total_final_inspections,

        COUNT(*) FILTER (
            WHERE result = 'PASS'
        ) AS final_inspections_passed,

        COUNT(*) FILTER (
            WHERE result = 'FAIL'
        ) AS final_inspections_failed

    FROM {{ ref('quality_inspections') }}
    WHERE station = 'FINAL_INSPECTION'
),

-- =====================================================
-- 6. REWORK ATTEMPTS
-- =====================================================

rework_counts AS (
    SELECT
        COUNT(*) AS total_rework_attempts
    FROM {{ ref('rework_events') }}
),

-- =====================================================
-- 7. PAIR STATION ENTRY AND EXIT EVENTS
-- =====================================================

visit_pairs AS (
    SELECT
        serial_number,
        station,
        action,
        sim_timestamp,

        LEAD(action) OVER w AS next_action,

        LEAD(sim_timestamp) OVER w
            - sim_timestamp AS duration

    FROM {{ ref('station_visits') }}

    WHERE action IN ('ENTRY', 'EXIT')
      AND station NOT IN ('SOURCE', 'SINK', 'SCRAP')

    WINDOW w AS (
        PARTITION BY serial_number, station
        ORDER BY
            sim_timestamp,
            CASE
                WHEN action = 'ENTRY' THEN 0
                ELSE 1
            END
    )
),

completed_visits AS (
    SELECT
        serial_number,
        station,
        sim_timestamp,
        duration
    FROM visit_pairs
    WHERE action = 'ENTRY'
      AND next_action = 'EXIT'
      AND duration >= 0
),

-- =====================================================
-- 8. STATION PERFORMANCE
-- =====================================================

station_metrics AS (
    SELECT
        station,

        COUNT(*) AS completed_visits,

        COUNT(DISTINCT serial_number) AS unique_units,

        AVG(duration) AS avg_cycle_time,

        MIN(duration) AS min_cycle_time,

        MAX(duration) AS max_cycle_time,

        PERCENTILE_CONT(0.5)
            WITHIN GROUP (ORDER BY duration)
            AS median_cycle_time,

        PERCENTILE_CONT(0.95)
            WITHIN GROUP (ORDER BY duration)
            AS p95_cycle_time

    FROM completed_visits
    GROUP BY station
),

-- =====================================================
-- 9. STATION METRICS PIVOT
-- =====================================================

station_summary AS (
    SELECT
        COALESCE(MAX(completed_visits) FILTER (
            WHERE station = 'PCB_ASSEMBLY'
        ), 0) AS pcb_units_processed,

        COALESCE(MAX(completed_visits) FILTER (
            WHERE station = 'MECH_ASSEMBLY'
        ), 0) AS mechanical_units_processed,

        COALESCE(MAX(completed_visits) FILTER (
            WHERE station = 'ELEC_TESTING'
        ), 0) AS electrical_units_processed,

        COALESCE(MAX(completed_visits) FILTER (
            WHERE station = 'FINAL_INSPECTION'
        ), 0) AS inspection_units_processed,

        COALESCE(MAX(completed_visits) FILTER (
            WHERE station = 'PACKAGING'
        ), 0) AS packaging_units_processed,

        COALESCE(MAX(completed_visits) FILTER (
            WHERE station = 'REWORK'
        ), 0) AS rework_units_processed,

        MAX(avg_cycle_time) FILTER (
            WHERE station = 'PCB_ASSEMBLY'
        ) AS pcb_avg_cycle_time,

        MAX(avg_cycle_time) FILTER (
            WHERE station = 'MECH_ASSEMBLY'
        ) AS mechanical_avg_cycle_time,

        MAX(avg_cycle_time) FILTER (
            WHERE station = 'ELEC_TESTING'
        ) AS electrical_avg_cycle_time,

        MAX(avg_cycle_time) FILTER (
            WHERE station = 'FINAL_INSPECTION'
        ) AS inspection_avg_cycle_time,

        MAX(avg_cycle_time) FILTER (
            WHERE station = 'PACKAGING'
        ) AS packaging_avg_cycle_time,

        MAX(avg_cycle_time) FILTER (
            WHERE station = 'REWORK'
        ) AS rework_avg_cycle_time,

        MAX(p95_cycle_time) FILTER (
            WHERE station = 'PCB_ASSEMBLY'
        ) AS pcb_p95_cycle_time,

        MAX(p95_cycle_time) FILTER (
            WHERE station = 'MECH_ASSEMBLY'
        ) AS mechanical_p95_cycle_time,

        MAX(p95_cycle_time) FILTER (
            WHERE station = 'ELEC_TESTING'
        ) AS electrical_p95_cycle_time,

        MAX(p95_cycle_time) FILTER (
            WHERE station = 'FINAL_INSPECTION'
        ) AS inspection_p95_cycle_time,

        MAX(p95_cycle_time) FILTER (
            WHERE station = 'PACKAGING'
        ) AS packaging_p95_cycle_time,

        MAX(p95_cycle_time) FILTER (
            WHERE station = 'REWORK'
        ) AS rework_p95_cycle_time

    FROM station_metrics
),

-- =====================================================
-- 10. OBSERVED SIMULATION DURATION
-- =====================================================

simulation_duration AS (
    SELECT
        MIN(sim_timestamp) AS simulation_start,

        MAX(sim_timestamp) AS simulation_end,

        MAX(sim_timestamp) - MIN(sim_timestamp)
            AS simulation_duration_minutes

    FROM {{ ref('station_visits') }}
),

-- =====================================================
-- 11. DATA INTEGRITY
-- =====================================================

integrity_checks AS (
    SELECT
        (
            SELECT COUNT(*)
            FROM packaged AS p
            WHERE NOT EXISTS (
                SELECT 1
                FROM created AS c
                WHERE c.serial_number = p.serial_number
            )
        ) AS unexpected_packaged_units,

        (
            SELECT COUNT(*)
            FROM scrapped AS s
            WHERE NOT EXISTS (
                SELECT 1
                FROM created AS c
                WHERE c.serial_number = s.serial_number
            )
        ) AS unexpected_scrapped_units
),

-- =====================================================
-- 12. FINAL GOLD KPI MODEL
-- =====================================================

final AS (
    SELECT
        CURRENT_TIMESTAMP AS refreshed_at,

        sd.simulation_start,
        sd.simulation_end,

        ROUND(
            sd.simulation_duration_minutes::numeric, 2
        ) AS simulation_duration_minutes,

        -- Production volume

        pc.created_units,
        pc.packaged_units,
        pc.scrapped_units,
        pc.reworked_units,
        pc.wip_units,

        pc.packaged_units + pc.scrapped_units
            AS completed_units,

        -- Final production yield (%)

        ROUND(
            100.0 * pc.packaged_units
            / NULLIF(
                pc.packaged_units + pc.scrapped_units, 0
            ),
            2
        ) AS final_yield_pct,

        -- Scrap rate (% of completed units)

        ROUND(
            100.0 * pc.scrapped_units
            / NULLIF(
                pc.packaged_units + pc.scrapped_units, 0
            ),
            2
        ) AS scrap_rate_pct,

        -- Rework incidence (% of created units)

        ROUND(
            100.0 * pc.reworked_units
            / NULLIF(pc.created_units, 0),
            2
        ) AS rework_rate_pct,

        -- Work in progress (%)

        ROUND(
            100.0 * pc.wip_units
            / NULLIF(pc.created_units, 0),
            2
        ) AS wip_pct,

        -- Electrical testing first pass yield

        fp.total_initial_tests,
        fp.passed_first_time,
        fp.failed_first_time,

        ROUND(
            100.0 * fp.passed_first_time
            / NULLIF(fp.total_initial_tests, 0),
            2
        ) AS first_pass_yield_pct,

        -- Electrical testing yield including retests

        et.total_electrical_tests,
        et.electrical_tests_passed,
        et.electrical_tests_failed,

        ROUND(
            100.0 * et.electrical_tests_passed
            / NULLIF(et.total_electrical_tests, 0),
            2
        ) AS electrical_test_yield_pct,

        -- Final inspection yield

        fi.total_final_inspections,
        fi.final_inspections_passed,
        fi.final_inspections_failed,

        ROUND(
            100.0 * fi.final_inspections_passed
            / NULLIF(fi.total_final_inspections, 0),
            2
        ) AS final_inspection_yield_pct,

        -- Rework performance

        rc.total_rework_attempts,

        ROUND(
            rc.total_rework_attempts::numeric
            / NULLIF(pc.reworked_units, 0),
            2
        ) AS avg_rework_attempts_per_unit,

        -- Production throughput (units/hour)

        ROUND(
            60.0 * pc.packaged_units
            / NULLIF(
                sd.simulation_duration_minutes::numeric, 0
            ),
            2
        ) AS throughput_units_per_hour,

        -- End-to-end cycle time

        ROUND(
            pc.avg_total_cycle_time::numeric, 2
        ) AS avg_total_cycle_time_minutes,

        -- Station processing counts

        ss.pcb_units_processed,
        ss.mechanical_units_processed,
        ss.electrical_units_processed,
        ss.inspection_units_processed,
        ss.packaging_units_processed,
        ss.rework_units_processed,

        -- Average station cycle times

        ROUND(ss.pcb_avg_cycle_time::numeric, 2)
            AS pcb_avg_cycle_time_minutes,

        ROUND(ss.mechanical_avg_cycle_time::numeric, 2)
            AS mechanical_avg_cycle_time_minutes,

        ROUND(ss.electrical_avg_cycle_time::numeric, 2)
            AS electrical_avg_cycle_time_minutes,

        ROUND(ss.inspection_avg_cycle_time::numeric, 2)
            AS inspection_avg_cycle_time_minutes,

        ROUND(ss.packaging_avg_cycle_time::numeric, 2)
            AS packaging_avg_cycle_time_minutes,

        ROUND(ss.rework_avg_cycle_time::numeric, 2)
            AS rework_avg_cycle_time_minutes,

        -- P95 station cycle times

        ROUND(ss.pcb_p95_cycle_time::numeric, 2)
            AS pcb_p95_cycle_time_minutes,

        ROUND(ss.mechanical_p95_cycle_time::numeric, 2)
            AS mechanical_p95_cycle_time_minutes,

        ROUND(ss.electrical_p95_cycle_time::numeric, 2)
            AS electrical_p95_cycle_time_minutes,

        ROUND(ss.inspection_p95_cycle_time::numeric, 2)
            AS inspection_p95_cycle_time_minutes,

        ROUND(ss.packaging_p95_cycle_time::numeric, 2)
            AS packaging_p95_cycle_time_minutes,

        ROUND(ss.rework_p95_cycle_time::numeric, 2)
            AS rework_p95_cycle_time_minutes,

        -- Data integrity

        pc.conflicting_outcomes,
        ic.unexpected_packaged_units,
        ic.unexpected_scrapped_units,

        pc.created_units
            - pc.packaged_units
            - pc.scrapped_units
            - pc.wip_units
            AS conservation_difference,

        CASE
            WHEN pc.conflicting_outcomes = 0
             AND ic.unexpected_packaged_units = 0
             AND ic.unexpected_scrapped_units = 0
            THEN 'PASS'
            ELSE 'FAIL'
        END AS lifecycle_consistency_status

    FROM production_counts AS pc
    CROSS JOIN fpy_counts AS fp
    CROSS JOIN electrical_tests AS et
    CROSS JOIN final_inspections AS fi
    CROSS JOIN rework_counts AS rc
    CROSS JOIN station_summary AS ss
    CROSS JOIN simulation_duration AS sd
    CROSS JOIN integrity_checks AS ic
)

SELECT *
FROM final
