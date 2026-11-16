-- SQLite 3; company is the client unit. Amounts are GMV, not revenue.
-- Q1: confirmed monthly product metrics, 2025 only.
SELECT substr(booking_date,1,7) AS month, subproduct,
       SUM(amount_rub) AS gmv_rub, COUNT(*) AS bookings
FROM bookings WHERE status='confirmed'
AND booking_date >= '2025-01-01' AND booking_date < '2026-01-01'
GROUP BY 1,2 ORDER BY 1,2;

-- Q2: top companies, not employees; unique clients are validated before JOIN.
SELECT b.client_id,c.company_name,c.tier,c.industry,
       SUM(b.amount_rub) AS gmv_rub,COUNT(*) AS bookings,
       AVG(b.amount_rub) AS average_booking_rub
FROM bookings b JOIN clients c ON b.client_id=c.client_id
WHERE b.status='confirmed' AND b.booking_date >= '2025-01-01'
AND b.booking_date < '2026-01-01'
GROUP BY b.client_id,c.company_name,c.tier,c.industry
ORDER BY gmv_rub DESC,b.client_id LIMIT 10;

-- Q3: cancellation denominator includes both valid statuses, in the same year.
SELECT subproduct,COUNT(*) AS all_bookings,
       SUM(CASE WHEN status='cancelled' THEN 1 ELSE 0 END) AS cancelled,
       100.0*SUM(CASE WHEN status='cancelled' THEN 1 ELSE 0 END)/COUNT(*) AS cancelled_pct
FROM bookings WHERE booking_date >= '2025-01-01'
AND booking_date < '2026-01-01' GROUP BY subproduct;

-- Q5: operational inactivity flag; historical H1 GMV is not a loss estimate.
WITH h1 AS (
 SELECT client_id,SUM(amount_rub) AS historical_h1_gmv,COUNT(*) AS h1_bookings
 FROM bookings WHERE status='confirmed' AND booking_date >= '2025-01-01'
 AND booking_date < '2025-07-01' GROUP BY client_id
), h2 AS (
 SELECT DISTINCT client_id FROM bookings WHERE status='confirmed'
 AND booking_date >= '2025-07-01' AND booking_date < '2026-01-01'
)
SELECT h1.*,c.company_name,c.tier,c.industry
FROM h1 JOIN clients c ON c.client_id=h1.client_id
LEFT JOIN h2 ON h1.client_id=h2.client_id WHERE h2.client_id IS NULL
ORDER BY historical_h1_gmv DESC;
