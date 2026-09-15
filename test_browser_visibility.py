import subprocess
import unittest
import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
import monitor

class BrowserVisibilityTest(unittest.TestCase):
    def test_read_activates_only_its_owned_page_before_evaluation(self):
        ok=subprocess.CompletedProcess([],0,'{}','')
        with patch.object(monitor.runtime,'opencli_command',return_value=['opencli']),patch.object(monitor.runtime,'browser_profile',return_value=None),patch.object(monitor.subprocess,'run',return_value=ok) as run,patch.object(monitor.time,'sleep'):
            monitor.cli({'_page':'owned-page'},{'id':'demo'},'eval','document.visibilityState')
        self.assertEqual(len(run.call_args_list),2)
        for call in run.call_args_list:
            self.assertEqual(call.kwargs.get('env',{}).get('OPENCLI_WINDOW'),'background')
        self.assertEqual(run.call_args_list[0].args[0][-3:],['tab','select','owned-page'])
        self.assertEqual(run.call_args_list[1].args[0][-2:],['eval','document.visibilityState'])

    def test_parallel_read_cannot_steal_another_readers_active_tab(self):
        calls=[]
        def run(command,**kwargs):
            calls.append(command)
            time.sleep(.005)
            return subprocess.CompletedProcess(command,0,'{}','')
        with patch.object(monitor.runtime,'opencli_command',return_value=['opencli']),patch.object(monitor.runtime,'browser_profile',return_value=None),patch.object(monitor.subprocess,'run',side_effect=run):
            with ThreadPoolExecutor(max_workers=3) as pool:
                list(pool.map(lambda i:monitor.cli({'_page':'page-'+str(i)},{'id':str(i)},'eval','test'),range(3)))
        for i in range(0,len(calls),2):
            self.assertEqual(calls[i][2],calls[i+1][2])
            self.assertEqual(calls[i][-3:-1],['tab','select'])
            self.assertEqual(calls[i+1][-2:],['eval','test'])
