import json
import tempfile
import unittest
from pathlib import Path
from interviews import Interviews

class InterviewTests(unittest.TestCase):
    def test_create_edit_delete_survives_reopen(self):
        with tempfile.TemporaryDirectory() as d:
            store=Interviews(d)
            event={'action':'save','company':'示例科技','start':'2026-09-24T09:00','end':'2026-09-24T10:00'}
            row=store.access(event)[0]
            self.assertEqual(Interviews(d).access()[0]['id'],row['id'])
            row.update(action='save',round='技术面',end='2026-09-24T11:00')
            self.assertEqual(store.access(row)[0]['round'],'技术面')
            self.assertEqual(store.access({'action':'delete','id':row['id']}),[])

    def test_invalid_inputs_do_not_replace_saved_data(self):
        with tempfile.TemporaryDirectory() as d:
            store=Interviews(d);valid={'action':'save','company':'示例','start':'2026-09-24T09:00','end':'2026-09-24T10:00'}
            store.access(valid);before=(Path(d)/'interviews.json').read_bytes()
            for change in [{'end':'2026-09-24T08:00'},{'company':''},{'start':'2026-02-30T09:00'},{'status':'invalid'},{'notes':123},{'id':'missing'}]:
                with self.subTest(change=change),self.assertRaises(ValueError):store.access(dict(valid,**change))
                self.assertEqual(before,(Path(d)/'interviews.json').read_bytes())

    def test_corrupt_file_is_not_silently_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'interviews.json';path.write_text('{bad')
            with self.assertRaises(ValueError):Interviews(d).access({'action':'save'})
            self.assertEqual(path.read_text(),'{bad')
