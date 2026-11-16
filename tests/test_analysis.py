import unittest
import pandas as pd
from src.analysis import analyse, validate_inputs, cohort_retention


def fixture():
    clients = pd.DataFrame([
        [1, 'Company A', 1, 'IT', '2024-01-01'],
        [2, 'Company B', 2, 'IT', '2024-01-01'],
        [3, 'Company C', 3, 'IT', '2024-01-01']],
        columns=['client_id','company_name','tier','industry','first_booking_date'])
    bookings = pd.DataFrame([
        [1,1,'avia','2025-01-01','2025-01-02',100,'confirmed'],
        [2,1,'avia','2025-01-01','2025-01-02',200,'confirmed'],
        [3,1,'hotel','2025-08-01','2025-08-02',500,'cancelled'],
        [4,2,'hotel','2025-02-01','2025-02-02',400,'confirmed'],
        [5,2,'hotel','2025-09-01','2025-09-02',600,'confirmed'],
        [6,3,'avia','2024-01-01','2024-01-02',9999,'confirmed']],
        columns=['booking_id','client_id','subproduct','booking_date','trip_date','amount_rub','status'])
    return bookings, clients


class AnalysisTests(unittest.TestCase):
    def test_company_parallel_bookings_are_retained(self):
        b,c=fixture(); s,_,_=analyse(b,c)
        self.assertEqual(s['confirmed_bookings'],4)
        self.assertEqual(s['confirmed_gmv_rub'],1300)

    def test_cancelled_h2_is_not_confirmed_activity(self):
        b,c=fixture(); s,t,_=analyse(b,c)
        self.assertEqual(set(t['inactive_h2'].client_id),{1})
        self.assertEqual(s['h1_active_companies'],2)
        self.assertEqual(s['h2_inactive_pct_of_h1'],50)
        self.assertEqual(s['inactive_companies_historical_h1_gmv_rub'],300)

    def test_year_filter_excludes_prior_year_from_gmv(self):
        b,c=fixture(); _,t,_=analyse(b,c)
        self.assertEqual(t['products'].gmv.sum(),1300)
        self.assertEqual(len(t['monthly']),48)

    def test_conflicting_booking_keys_fail(self):
        b,c=fixture(); b.loc[1,'booking_id']=1
        with self.assertRaises(ValueError):validate_inputs(b,c)

    def test_duplicate_companies_fail_before_join(self):
        b,c=fixture(); c=pd.concat([c,c.iloc[:1]])
        with self.assertRaises(ValueError):validate_inputs(b,c)

    def test_unknown_company_fails(self):
        b,c=fixture(); b.loc[0,'client_id']=999
        with self.assertRaises(ValueError):validate_inputs(b,c)

    def test_no_new_companies_is_not_zero_retention(self):
        b,c=fixture(); _,t,_=analyse(b,c)
        self.assertTrue(t['retention'].empty)

    def test_future_cohort_months_are_unobserved(self):
        b,c=fixture(); c.loc[0,'first_booking_date']='2025-11-01'
        b=b.iloc[:2].copy();b['booking_date']=['2025-11-01','2025-12-01'];b['trip_date']=['2025-11-02','2025-12-02']
        _,t,_=analyse(b,c)
        self.assertEqual(t['retention'].loc['2025-11',1],1)
        self.assertTrue(pd.isna(t['retention'].loc['2025-11',2]))

    def test_cancelled_only_product_has_zero_confirmed_gmv(self):
        b,c=fixture(); _,t,_=analyse(b,c)
        row=t['cancellations'].set_index('subproduct').loc['hotel']
        self.assertAlmostEqual(row.cancel_rate_pct,100/3)


if __name__=='__main__':unittest.main()
