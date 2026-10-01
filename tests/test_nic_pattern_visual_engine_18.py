import sys
sys.path.insert(0,'src')
import nic_pattern_visual_engine_18 as m
assert m.regression_slope([1,2,3,4]) > 0
assert m.regression_slope([4,3,2,1]) < 0
assert m.regression_slope([1,1,1,1]) == 0
print('NIC 18 pattern engine tests: PASS')
