import unittest
import ci_merge as c

class RequiredCITests(unittest.TestCase):
    def pr(self,status='COMPLETED',conclusion='SUCCESS',merge='CLEAN'):
        return {'state':'OPEN','headRefOid':'approved','isDraft':False,'mergeStateStatus':merge,
                'statusCheckRollup':[{'name':'foundation','status':status,'conclusion':conclusion}]}
    def test_pending_and_missing_are_retryable_not_failure(self):
        self.assertEqual(c.evaluate(self.pr('IN_PROGRESS',None),'approved',{'foundation'})[0],'pending')
        p=self.pr();p['statusCheckRollup']=[]
        self.assertEqual(c.evaluate(p,'approved',{'foundation'})[0],'pending')
    def test_exact_head_success_and_other_required_checks(self):
        self.assertEqual(c.evaluate(self.pr(),'approved',{'foundation'})[0],'ready')
        self.assertEqual(c.evaluate(self.pr(),'different',{'foundation'})[0],'failed')
        self.assertEqual(c.evaluate(self.pr(),'approved',{'foundation','other'})[0],'pending')
    def test_failed_cancelled_and_behind_do_not_merge(self):
        for result in ('FAILURE','CANCELLED','SKIPPED'):
            self.assertEqual(c.evaluate(self.pr(conclusion=result),'approved',{'foundation'})[0],'failed')
        self.assertEqual(c.evaluate(self.pr(merge='BEHIND'),'approved',{'foundation'})[0],'pending')
    def test_api_failure_defers(self):
        self.assertEqual(c.check(95,'approved','repo',lambda *a,**k:(1,''))[0],'pending')
