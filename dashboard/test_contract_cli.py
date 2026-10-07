import datetime as dt
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('contract_cli',Path(__file__).parent/'tools/contract_cli.py')
cli=importlib.util.module_from_spec(spec);spec.loader.exec_module(cli)
SCHEMA=json.loads((Path(__file__).parent.parent/'schema/fields.json').read_text())

def fields():
    result={f['name']:'' for f in SCHEMA['fields']}
    for f in SCHEMA['fields']:
        if f.get('required'):
            if f['type']=='enum':
                v=SCHEMA['enums'][f.get('enum',f['name'])][0];result[f['name']]=v if isinstance(v,str) else v['label']
            else:result[f['name']]=dt.date.today().isoformat() if f['type']=='date' else '測試值'
    result['contract_id']='C-2026-0001'
    return result

class CliTest(unittest.TestCase):
    def client(self):
        c=cli.Client();c.config=lambda:{'schema':SCHEMA,'transitions':{'收件':['法務審閱'],'法務審閱':['核准']}}
        return c

    def test_valid_fields_and_required(self):
        self.assertEqual(cli.validate_fields(fields(),SCHEMA)['title'],'測試值')
        data=fields();data['contract_value']=0
        self.assertEqual(cli.validate_fields(data,SCHEMA)['contract_value'],'0')
        for value in [None,[],{},False,123]:
            data=fields();data['title']=value
            with self.assertRaises(ValueError):cli.validate_fields(data,SCHEMA)
        for f in SCHEMA['fields']:
            if f.get('required'):
                data=fields();data[f['name']]=''
                with self.assertRaises(ValueError):cli.validate_fields(data,SCHEMA)

    def test_date_integer_and_enum(self):
        for name,value in [('end_date','2026-02-30'),('notice_days','1.5'),('contract_value','Infinity'),('status','未知')]:
            data=fields();data[name]=value
            with self.assertRaises(ValueError):cli.validate_fields(data,SCHEMA)

    def test_no_write_for_invalid_create(self):
        c=self.client();calls=[];c.request=lambda *a:calls.append(a) or []
        with self.assertRaisesRegex(ValueError,'合約名稱'):c.create('contracts',{'fields':{},'user':'甲','comment':'x'})
        for body in [[],{'user':'甲','comment':'x','fields':[]},{'user':123,'comment':'x','fields':fields()}]:
            with self.assertRaises(ValueError):c.create('cases',body)
        self.assertFalse(any(len(x)>1 and x[1] in ('POST','PATCH') for x in calls))

    def test_create_case_server_id_and_initial_event(self):
        c=self.client();calls=[]
        def request(path,method='GET',body=None):
            calls.append((path,method,body));return {'id':'server1',**(body or {})} if method=='POST' else []
        c.request=request
        result=c.create('cases',{'fields':fields(),'user':'甲','comment':'收到','attachment_version':'V1'})
        self.assertEqual(result['id'],'server1');self.assertTrue(result['case_number'].startswith('CASE-'))
        event=calls[-1][2];self.assertEqual(event['case_id'],'server1');self.assertEqual(event['to_stage'],'收件')

    def test_invalid_transition_has_no_mutation(self):
        c=self.client();c.read=lambda *a:{'id':'a','stage':'收件'}
        with patch.object(c,'request') as request:
            with self.assertRaises(ValueError):c.progress('a',{'stage':'歸檔','user':'甲','comment':'x'})
            request.assert_not_called()

    def test_progress_posts_then_patches(self):
        c=self.client();c.read=lambda *a:{'id':'server1','stage':'收件'}
        with patch.object(c,'request',return_value={'id':'p1'}) as request:
            c.progress('案號',{'stage':'法務審閱','user':'乙','comment':'開始','attachment_version':'V2'})
            self.assertEqual([c.args[1] for c in request.call_args_list],['POST','PATCH'])
            self.assertEqual(request.call_args_list[0].args[2]['user'],'乙')

    def test_update_preserves_identity_and_history_enum(self):
        c=self.client();old=fields();old['status']='歷史原值'
        c.read=lambda *a:{'id':'a','fields':old}
        with patch.object(c,'request',return_value={'id':'a'}) as request:
            c.update('contracts','a',{'fields':{'contract_id':'changed','title':'修改'},'user':'甲','comment':'x'})
            self.assertEqual(request.call_args.args[2]['fields']['contract_id'],old['contract_id'])
            self.assertEqual(request.call_args.args[2]['fields']['status'],'歷史原值')

    def test_only_loopback_http(self):
        for url in ['https://127.0.0.1:3000','http://example.com','http://203.0.113.1:3000']:
            with self.assertRaises(ValueError):cli.Client(url)

    def test_partial_update_preserves_missing_required_and_legacy_values(self):
        for kind in ('contracts', 'cases'):
            c = self.client()
            old = {'contract_id': 'LEGACY-01', 'title': '', 'department': '',
                   'status': '歷史原值', 'end_date': '原文未載明', 'notes': '', 'source_refs': 'page 1'}
            current = {'id': 'legacy', 'stage': '收件', 'fields': old}
            c.read = lambda *a: current
            with patch.object(c, 'request', return_value={'id': 'legacy'}) as request:
                c.update(kind, 'legacy', {'fields': {'notes': '新增備註'}, 'user': '甲', 'comment': '核對'})
                saved = request.call_args_list[0].args[2]['fields']
                self.assertEqual(saved['notes'], '新增備註')
                for name, value in old.items():
                    if name != 'notes': self.assertEqual(saved[name], value)
                self.assertNotIn('our_entity', saved)
                self.assertEqual(request.call_count, 2 if kind == 'cases' else 1)

    def test_partial_update_validates_changes_before_any_write(self):
        c = self.client()
        old = {'contract_id': 'LEGACY-01', 'title': '原名稱', 'department': '', 'status': ''}
        c.read = lambda *a: {'id': 'legacy', 'fields': old}
        for change in ({'title': ''}, {'end_date': '2026-02-30'}, {'status': '新未知值'}, {'notice_days': '1.5'}, {'notes': []}):
            with patch.object(c, 'request') as request:
                with self.assertRaises(ValueError):
                    c.update('contracts', 'legacy', {'fields': change, 'user': '甲', 'comment': '核對'})
                request.assert_not_called()

    def test_cli_invalid_input_returns_nonzero(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'request.json';p.write_text('{}')
            with patch.object(cli.Client,'config',return_value={'schema':SCHEMA}),patch.object(cli.Client,'request') as request:
                self.assertEqual(cli.main(['create','cases','--input',str(p)]),1);request.assert_not_called()
