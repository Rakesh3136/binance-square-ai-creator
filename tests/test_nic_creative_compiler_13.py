import sys
sys.path.insert(0,"src")
import nic_creative_compiler_13 as m
assert m.sim("same volume breakout thesis","same volume breakout thesis")==1.0
assert m.sim("volume breakout thesis","banana recipe for dinner")<0.2
print("NIC 13 tests: PASS")
