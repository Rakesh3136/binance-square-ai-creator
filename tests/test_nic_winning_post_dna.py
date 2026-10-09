import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from nic_winning_post_dna import build
def row(pid,cat,rev,verified=True):return {"canonical_post_id":pid,"category":cat,"has_primary_cashtag":True,"visual_attached":True,"performance":{"views":100},"verified_activity":{"revenue_verified":verified,"reward_amount_usdc":rev}}
def main():
 x=build({"publication_funnel":[row("a","setup",2),row("b","setup",3),row("c","research",1),row("d","false",90,False)]},{})
 assert x["verified_revenue_post_count"]==3 and x["verified_revenue_total_usdc"]==6
 assert x["editorial_contract"]["historical_best_category_candidate"]=="setup"
 assert x["editorial_contract"]["truth_policy"]["views_are_not_revenue"]
 y=build({"publication_funnel":[row("z","setup",10,False)]},{})
 assert y["status"]=="INSUFFICIENT_VERIFIED_REVENUE" and y["verified_revenue_post_count"]==0
 print("NIC Winning-Post DNA tests: PASS")
if __name__=="__main__":main()
