"""Regression tests using only target/read timing, never policy inputs."""
import unittest
import numpy as np
from p6_export import associate_targets

class AssociationTests(unittest.TestCase):
    def test_capture_survives_missing_status(self):
        s=np.array([100,104,108,112]);sp=np.array([90,110]);sts=np.array([100,108,112]);flags=np.array([False,False,True])
        a=associate_targets(s,sp,sts,flags,dict(zip(sts,flags)),{100:0,108:0,112:112},{100:7})
        self.assertEqual(a[104],('tg',7))
        self.assertEqual(a[108],('tg',7))
        self.assertEqual(a[112],('sp',1))

    def test_read_clock_can_follow_sample(self):
        s=np.array([100,104,108]);sp=np.array([90,103]);sts=s;flags=np.array([True,False,False])
        a=associate_targets(s,sp,sts,flags,dict(zip(sts,flags)),{100:104,104:0,108:0},{})
        self.assertEqual(a[100],('sp',1))
        self.assertEqual(a[108],('sp',1))

    def test_capture_wins_same_cycle_read(self):
        s=np.array([100,104]);sp=np.array([99]);sts=np.array([100]);flags=np.array([True])
        a=associate_targets(s,sp,sts,flags,{100:True},{100:100},{100:4})
        self.assertEqual(a[100],('tg',4))
        self.assertEqual(a[104],('tg',4))

    def test_missing_status_defers_to_recorded_next_read(self):
        s=np.array([100,104,108]);sp=np.array([90,103]);sts=np.array([100,108]);flags=np.array([True,True])
        a=associate_targets(s,sp,sts,flags,dict(zip(sts,flags)),{100:100,108:108},{})
        self.assertEqual(a[104],('sp',0))
        self.assertEqual(a[108],('sp',1))

    def test_profile_does_not_consume_unread_external_target(self):
        s=np.array([100,104,108]);sp=np.array([90,99]);sts=s;flags=np.array([False,True,False])
        a=associate_targets(s,sp,sts,flags,dict(zip(sts,flags)),{100:0,104:104,108:0},{100:7},set())
        self.assertEqual(a[100],('tg',7))
        self.assertEqual(a[104],('sp',1))
        self.assertEqual(a[108],('sp',1))

if __name__=='__main__':unittest.main()
