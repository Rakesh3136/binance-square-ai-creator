import importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("scorecard",ROOT/"src/nic_creator_experiment_scorecard.py")
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
def test_unverified_posts_do_not_count():
    r=m.build_scorecard([{"post_id":"x","status":"DRAFT","views":9000}],[])
    assert r["verified_publications"]==0
    assert r["status"]=="NO_VERIFIED_PUBLICATION_SAMPLE"
def test_views_are_not_revenue_and_rewards_need_verification():
    pubs=[{"post_id":"p1","status":"PUBLISHED_VERIFIED_BY_API_RESPONSE","views":5100,"format":"ANALYSIS"}]
    rewards=[{"post_id":"p1","status":"PENDING","amount_usdc":2},{"post_id":"p1","status":"PAID","amount_usdc":"0.201"}]
    r=m.build_scorecard(pubs,rewards)
    assert r["posts"][0]["verified_reward_usdc"]==0.201
    assert r["format_groups"]["ANALYSIS"]["verified_posts"]==1
def test_missing_metrics_are_not_imputed():
    r=m.build_scorecard([{"post_id":"p1","status":"CONFIRMED_PUBLISHED","proof":True,"format":"RESEARCH"}],[])
    assert r["posts"][0]["views"] is None
    assert r["format_groups"]["RESEARCH"]["average_views_per_measured_post"] is None
def test_different_formats_are_grouped_without_declaring_a_winner():
    pubs=[{"post_id":"a","status":"VERIFIED_PUBLISHED","format":"EXPLAINER","views":100},{"post_id":"b","status":"VERIFIED_PUBLISHED","format":"INVESTIGATION","views":200}]
    r=m.build_scorecard(pubs,[])
    assert set(r["format_groups"])=={"EXPLAINER","INVESTIGATION"}
    assert r["rules"]["minimum_posts_before_comparison"]==10
