import importlib.util
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("wte_controller",ROOT/"src/write_to_earn_7day_controller.py")
wte=importlib.util.module_from_spec(spec); spec.loader.exec_module(wte)

class WTECampaignLineageTests(unittest.TestCase):
    def setUp(self):
        self.start=datetime(2026,10,12,3,0,tzinfo=timezone.utc)
        self.row={"status":"PUBLISHED_VERIFIED_BY_API_RESPONSE","publication_proof":"binance_openapi_response_post_id","post_id":"p123","canonical_post_id":"p123","published_at":self.start.isoformat(),"github_run_id":"run-1"}
        self.result={"status":"PUBLISHED_VERIFIED_BY_API_RESPONSE","post_id":"p123","canonical_post_id":"p123","github_run_id":"run-1","checked_at":(self.start+timedelta(seconds=2)).isoformat()}

    def test_new_campaign_starts_at_current_run_verified_post(self):
        got=wte.campaign_start({},[self.row],self.result,"run-1",self.start+timedelta(seconds=5))
        self.assertEqual(got,self.start)

    def test_wrong_run_cannot_backdate_campaign(self):
        got=wte.campaign_start({},[self.row],self.result,"run-2",self.start+timedelta(seconds=5))
        self.assertEqual(got,self.start+timedelta(seconds=5))

    def test_unverified_or_missing_post_cannot_backdate(self):
        result={**self.result,"status":"PUBLISHED_SUBMITTED_504"}
        got=wte.campaign_start({},[self.row],result,"run-1",self.start+timedelta(seconds=5))
        self.assertEqual(got,self.start+timedelta(seconds=5))

    def test_repairs_old_post_publish_startup_race_only_when_zero_count(self):
        previous={"campaign_start_utc":(self.start+timedelta(minutes=2)).isoformat(),"verified_publications_total":0}
        got=wte.campaign_start(previous,[self.row],self.result,"run-1",self.start+timedelta(minutes=3))
        self.assertEqual(got,self.start)

    def test_does_not_reset_established_campaign(self):
        previous={"campaign_start_utc":(self.start-timedelta(days=2)).isoformat(),"verified_publications_total":12}
        got=wte.campaign_start(previous,[self.row],self.result,"run-1",self.start+timedelta(minutes=3))
        self.assertEqual(got,self.start-timedelta(days=2))

    def test_elapsed_campaign_day_not_calendar_date(self):
        start=datetime(2026,10,12,23,59,tzinfo=timezone.utc)
        stamp=datetime(2026,10,13,0,1,tzinfo=timezone.utc)
        bucket=max(1,int((stamp-start).total_seconds()//86400)+1)
        self.assertEqual(bucket,1)

if __name__=="__main__": unittest.main()
