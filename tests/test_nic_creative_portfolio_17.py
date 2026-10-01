from pathlib import Path
import ast
ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/"src/nic_creative_portfolio_17.py"
TREE=ast.parse(SRC.read_text(encoding="utf-8"))
required=["build_slots","choose_value","reward_patterns","mature_outcomes","main"]
names={n.name for n in TREE.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
for name in required:
    assert name in names, name
ns={}
exec(compile(TREE,str(SRC),"exec"),ns)
assert ns["MAX_DIM_REPEAT"]==3
assert ns["N"]==6
slots=ns["build_slots"]([],[],{"experiment_id":"x","primary_variable":"hook_type","directive":{"force_variable":"hook_type","selected_value":"data_contradiction"},"assignment":{"selected_value":"data_contradiction"}})
assert len(slots)==6
assert all(x["lineage"]["portfolio_plan_id"]==ns["PLAN_ID"] for x in slots)
assert all(x["lineage"]["slot_id"]==x["slot_id"] for x in slots)
assert any(x["hook_type"]=="data_contradiction" for x in slots)
print("NIC17 tests passed")
