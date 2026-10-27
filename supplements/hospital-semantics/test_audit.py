import unittest
from audit import parse, effective, count, matches_displayed_f1

class AuditTests(unittest.TestCase):
    def test_boundary_display(self):
        self.assertTrue(matches_displayed_f1(175,229,219,.7813))
        self.assertTrue(matches_displayed_f1(175,229,219,.7812))
        self.assertFalse(matches_displayed_f1(175,229,219,.7814))
    def test_zero(self):
        self.assertTrue(matches_displayed_f1(0,0,0,0))
    def test_noop_and_false_edit(self):
        d=[['al','1x']];c=[['al','12']];columns=['State','ZipCode']
        p=effective(d,columns,[{'row':1,'column':'State','value':'AL'},
            {'row':1,'column':'ZipCode','value':'12'}])
        self.assertEqual(count(d,c,columns,p),{'errors':1,'predicted':1,'detected':1,'repaired':1})
        p=effective(d,columns,[{'row':1,'column':'State','value':'ia'}])
        self.assertEqual(count(d,c,columns,p),{'errors':1,'predicted':1,'detected':0,'repaired':0})
    def test_fallback(self):
        self.assertEqual(len(parse('bad {"corrections":[{"row":1,"column":"State","value":"al"},')),1)
    def test_last_effective_edit(self):
        self.assertEqual(effective([['x']],['v'],[{'row':1,'column':'v','value':'a'},
            {'row':1,'column':'v','value':'b'},{'row':1,'column':'v','value':'x'}]),{(0,'v'):'b'})

if __name__=='__main__':unittest.main()
