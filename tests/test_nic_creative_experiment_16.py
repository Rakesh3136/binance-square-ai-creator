"""Basic NIC 16 contract tests."""
import ast, pathlib
p=pathlib.Path("src/nic_creative_experiment_16.py")
ast.parse(p.read_text(encoding="utf-8"))
ns={}
exec(compile(p.read_text(encoding="utf-8"),str(p),"exec"),ns)
assert ns["arm_for"]("exp","same-run") == ns["arm_for"]("exp","same-run")
assert ns["arm_for"]("exp","same-run") in {"control","treatment"}
assert len(ns["VARIABLES"]) == 4
for k,v in ns["SAFE_FALLBACKS"].items():
    assert v[0] in ns["VARIABLES"][k] and v[1] in ns["VARIABLES"][k]
print("NIC 16 tests passed")
