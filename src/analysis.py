"""Reproducible metrics for the synthetic 2025 Business Travel assignment.

The unit of a client is a company, not an employee. GMV is not platform revenue.
"""
from pathlib import Path
import sqlite3
import numpy as np
import pandas as pd

PRODUCTS = ('avia', 'hotel', 'train', 'taxi')


def validate_inputs(bookings, clients):
    b, c = bookings.copy(), clients.copy()
    required_b = {'booking_id', 'client_id', 'subproduct', 'booking_date', 'trip_date', 'amount_rub', 'status'}
    required_c = {'client_id', 'company_name', 'tier', 'industry', 'first_booking_date'}
    if not required_b.issubset(b) or not required_c.issubset(c):
        raise ValueError('Missing required columns; see assignment.md')
    if b[list(required_b)].isna().any().any() or c[list(required_c)].isna().any().any():
        raise ValueError('Required fields contain missing values; investigate before reporting')
    for frame, key in [(b, 'booking_id'), (c, 'client_id')]:
        if frame[key].duplicated().any():
            raise ValueError(f'Duplicate {key}; do not silently drop conflicting records')
    if not set(b.client_id).issubset(set(c.client_id)):
        raise ValueError('Booking references an unknown company')
    if not set(b.status).issubset({'confirmed', 'cancelled'}):
        raise ValueError('Unknown booking status')
    if not set(b.subproduct).issubset(PRODUCTS) or not set(c.tier).issubset({1, 2, 3}):
        raise ValueError('Unknown subproduct or company tier')
    b['amount_rub'] = pd.to_numeric(b.amount_rub, errors='raise')
    if not np.isfinite(b.amount_rub).all() or (b.amount_rub <= 0).any():
        raise ValueError('Nonpositive or nonfinite booking amount')
    for col in ('booking_date', 'trip_date'):
        b[col] = pd.to_datetime(b[col], errors='raise')
    c['first_booking_date'] = pd.to_datetime(c.first_booking_date, errors='raise')
    if b[['booking_date', 'trip_date']].isna().any().any() or c.first_booking_date.isna().any():
        raise ValueError('Invalid dates')
    if (b.trip_date < b.booking_date).any():
        raise ValueError('Trip before booking; investigate instead of deleting automatically')
    # Many bookings per company/day are legitimate: employee_id does not exist.
    return b, c


def cohort_retention(confirmed, clients, year=2025):
    """New companies only; cohort from first observed confirmed month in year.

    The initial cohort size stays fixed; future unobserved periods are NaN.
    A historical first_booking_date is an eligibility rule, not a substitute
    for a confirmed transaction. No eligible companies -> empty, not zero.
    """
    eligible = clients.loc[clients.first_booking_date.dt.year.eq(year), 'client_id']
    a = confirmed.loc[confirmed.client_id.isin(eligible), ['client_id', 'booking_date']].copy()
    if a.empty:
        return pd.DataFrame()
    a['month'] = a.booking_date.dt.to_period('M')
    first = a.groupby('client_id')['month'].min()
    a['cohort'] = a.client_id.map(first)
    a['age'] = (a['month'].astype('int64') - a['cohort'].astype('int64')).astype(int)
    counts = a.groupby(['cohort', 'age']).client_id.nunique().unstack()
    counts = counts.reindex(columns=range(12), fill_value=np.nan)
    sizes = first.value_counts().reindex(counts.index)
    result = counts.fillna(0).div(sizes, axis=0)
    last = pd.Period(f'{year}-12')
    for cohort in result.index:
        for age in result.columns:
            if cohort + age > last:
                result.loc[cohort, age] = np.nan
    result.index = result.index.astype(str)
    return result


def analyse(bookings, clients, year=2025):
    b, c = validate_inputs(bookings, clients)
    b = b.loc[b.booking_date.dt.year.eq(year)].copy()
    if b.empty:
        raise ValueError('No bookings in selected year')
    b['month'] = b.booking_date.dt.strftime('%Y-%m')
    confirmed = b.loc[b.status.eq('confirmed')].copy()
    if confirmed.empty:
        raise ValueError('No confirmed bookings in selected year')
    enriched = confirmed.merge(c, on='client_id', how='left', validate='many_to_one')
    months = [f'{year}-{m:02}' for m in range(1, 13)]
    grid = pd.MultiIndex.from_product([months, PRODUCTS], names=['month', 'subproduct'])
    monthly = confirmed.groupby(['month', 'subproduct']).agg(gmv=('amount_rub', 'sum'), bookings=('booking_id', 'count')).reindex(grid, fill_value=0).reset_index()
    product = confirmed.groupby('subproduct').agg(gmv=('amount_rub', 'sum'), bookings=('booking_id', 'count')).reindex(PRODUCTS, fill_value=0).reset_index()
    product['share_pct'] = product.gmv / product.gmv.sum() * 100
    product['aov'] = product.gmv.div(product.bookings.replace(0, np.nan))
    top_clients = enriched.groupby(['client_id', 'company_name', 'tier', 'industry']).agg(gmv=('amount_rub', 'sum'), bookings=('booking_id', 'count')).reset_index()
    top_clients['aov'] = top_clients.gmv / top_clients.bookings
    top_clients = top_clients.sort_values(['gmv', 'client_id'], ascending=[False, True])
    cancellation = b.assign(is_cancelled=b.status.eq('cancelled')).groupby('subproduct').agg(all_bookings=('booking_id', 'count'), cancelled=('is_cancelled', 'sum')).reindex(PRODUCTS, fill_value=0).reset_index()
    cancellation['cancel_rate_pct'] = cancellation.cancelled.div(cancellation.all_bookings.replace(0, np.nan)) * 100
    tiers = enriched.groupby('tier').agg(gmv=('amount_rub', 'sum'), bookings=('booking_id', 'count'), active_companies=('client_id', 'nunique')).reset_index()
    tiers['aov'] = tiers.gmv / tiers.bookings
    tiers['bookings_per_company'] = tiers.bookings / tiers.active_companies
    tiers['gmv_per_company'] = tiers.gmv / tiers.active_companies
    tiers['share_pct'] = tiers.gmv / tiers.gmv.sum() * 100
    h1, h2 = confirmed.loc[confirmed.booking_date.dt.month.le(6)], confirmed.loc[confirmed.booking_date.dt.month.gt(6)]
    ids1, ids2 = set(h1.client_id), set(h2.client_id)
    churn_ids = ids1 - ids2
    churn = h1.loc[h1.client_id.isin(churn_ids)].groupby('client_id').agg(gmv_h1=('amount_rub', 'sum'), bookings_h1=('booking_id', 'count')).reset_index().merge(c, on='client_id', validate='one_to_one')
    churn = churn.sort_values(['gmv_h1', 'client_id'], ascending=[False, True])
    h1_by_tier = c.loc[c.client_id.isin(ids1)].groupby('tier').size()
    churn_tier = churn.groupby('tier').agg(companies=('client_id', 'count'), historical_gmv_h1=('gmv_h1', 'sum')).reindex(h1_by_tier.index, fill_value=0)
    churn_tier['eligible_h1_companies'] = h1_by_tier
    churn_tier['inactive_h2_pct'] = churn_tier.companies / churn_tier.eligible_h1_companies * 100
    retention = cohort_retention(confirmed, c, year)
    summary = {
        'year': year, 'data_kind': 'synthetic educational assignment',
        'client_unit': 'company', 'currency': 'RUB', 'amount_definition': 'GMV of confirmed bookings; not platform revenue or profit',
        'source_rows': len(bookings), 'year_rows': len(b), 'confirmed_bookings': len(confirmed),
        'confirmed_gmv_rub': float(confirmed.amount_rub.sum()), 'companies': len(c),
        'active_companies': int(confirmed.client_id.nunique()), 'h1_active_companies': len(ids1),
        'h2_inactive_companies': len(churn_ids), 'h2_inactive_pct_of_h1': len(churn_ids) / len(ids1) * 100 if ids1 else None,
        'inactive_companies_historical_h1_gmv_rub': float(churn.gmv_h1.sum()),
        'h1_total_gmv_rub': float(h1.amount_rub.sum()), 'h2_total_gmv_rub': float(h2.amount_rub.sum()),
        'new_companies_2025': int(c.first_booking_date.dt.year.eq(year).sum()),
        'top3_share_of_inactive_h1_gmv_pct': float(churn.head(3).gmv_h1.sum() / churn.gmv_h1.sum() * 100) if churn.gmv_h1.sum() else None,
        'limitations': ['One year cannot establish recurring seasonality.', 'H2 inactivity is an operational flag, not confirmed permanent churn.', 'Historical GMV is not lost revenue; no counterfactual or margin is available.', 'Company-level data cannot estimate employee activity or employee LTV.'],
    }
    tables = {'monthly': monthly, 'products': product, 'top_clients': top_clients.head(10), 'cancellations': cancellation, 'tiers': tiers, 'inactive_h2': churn, 'inactive_by_tier': churn_tier.reset_index(), 'retention': retention}
    return summary, tables, b


def reconcile_sql(bookings, clients, monthly, year=2025):
    """Independently aggregate in SQLite; compare amount and counts by key."""
    with sqlite3.connect(':memory:') as con:
        b = bookings.copy()
        for col in ('booking_date', 'trip_date'):
            b[col] = b[col].dt.strftime('%Y-%m-%d')
        b.to_sql('bookings', con, index=False)
        clients.to_sql('clients', con, index=False)
        q = """SELECT substr(booking_date,1,7) AS month, subproduct,
                    SUM(amount_rub) AS gmv, COUNT(*) AS bookings
               FROM bookings WHERE status='confirmed' AND substr(booking_date,1,4)=?
               GROUP BY month,subproduct ORDER BY month,subproduct"""
        sql = pd.read_sql_query(q, con, params=[str(year)])
    comparison = monthly.merge(sql, on=['month', 'subproduct'], suffixes=('_pandas', '_sql'), how='outer')
    comparison[['gmv_sql', 'bookings_sql']] = comparison[['gmv_sql', 'bookings_sql']].fillna(0)
    comparison['matches'] = np.isclose(comparison.gmv_pandas, comparison.gmv_sql, rtol=0, atol=0.005) & comparison.bookings_pandas.eq(comparison.bookings_sql)
    if not comparison.matches.all():
        raise AssertionError('SQL and pandas monthly aggregates disagree')
    return comparison


def load_and_analyse(root):
    root = Path(root)
    b = pd.read_csv(root / 'data/bookings.csv')
    c = pd.read_csv(root / 'data/clients.csv')
    summary, tables, clean = analyse(b, c)
    check = reconcile_sql(clean, c, tables['monthly'])
    summary['sql_month_product_checks'] = len(check)
    summary['sql_checks_passed'] = int(check.matches.sum())
    return summary, tables, check
