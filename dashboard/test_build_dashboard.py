import base64,csv,datetime as dt,json,tempfile,unittest
from pathlib import Path
import build_dashboard as bd
SAMPLE=Path(__file__).parent/'sample_register.csv';TODAY=dt.date(2026,10,7)
class BuildTest(unittest.TestCase):
 def setUp(self):self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
 def tearDown(self):self.temp.cleanup()
 def csv(self,text):p=self.root/'r.csv';p.write_text(text);return p
 def test_date_boundaries(self):
  for end,expected in [('2026-10-07',True),('2027-01-05',True),('2027-01-06',False),('',False)]:self.assertEqual(bd.enrich({'end_date':end,'status':'有效'},TODAY)['is_expiring'],expected)
 def test_notice_and_expired(self):
  r=bd.enrich({'end_date':'2026-12-15','status':'有效','notice_days':'30','renewal_type':'自動續約'},TODAY);self.assertTrue(r['is_notice_due'])
  self.assertTrue(bd.enrich({'end_date':'2026-09-30','status':'有效'},TODAY)['is_expired'])
 def test_invalid_date_and_integer(self):self.assertIsNone(bd.parse_date('bad'));self.assertIsNone(bd.parse_int('bad'))
 def test_missing_fields_preserved_blank(self):
  p=bd.build_payload(self.csv('title,status,end_date\nOnly title\n'),TODAY);self.assertEqual(p['records']['contracts'][0]['fields']['end_date'],'');self.assertEqual(p['records']['contracts'][0]['id'],'C-2026-0001')
 def test_empty_register(self):self.assertEqual(bd.build_payload(self.csv('title\n'),TODAY)['records']['contracts'],[])
 def test_duplicate_id_rejected(self):
  with self.assertRaises(ValueError):bd.build_payload(self.csv('contract_id,title\nC-1,a\nC-1,b\n'),TODAY)
 def test_schema_rename_and_addition(self):
  schema=json.loads(bd.DEFAULT_FIELDS.read_text());schema['fields'][1]['label']='契約名稱';schema['fields'].append({'name':'new','label':'新欄位','type':'string'});p=self.root/'schema.json';p.write_text(json.dumps(schema));data=bd.build_payload(SAMPLE,TODAY,p);self.assertEqual(data['config']['schema']['fields'][1]['label'],'契約名稱');self.assertEqual(data['config']['schema']['fields'][-1]['name'],'new')
 def test_database_json_has_collections_and_literal_text(self):
  source=self.csv('contract_id,title\nC-1,</script>\n');out=self.root/'db.json'
  self.assertEqual(bd.main(['--register',str(source),'--out',str(out)]),0)
  data=json.loads(out.read_text());self.assertEqual(data['contracts'][0]['fields']['title'],'</script>')
  self.assertEqual(set(data),{'contracts','cases','progress','review_versions','review_comments','config'})
 def test_existing_database_requires_api(self):
  out=self.root/'db.json';out.write_text('old')
  self.assertEqual(bd.main(['--register',str(SAMPLE),'--out',str(out)]),1);self.assertEqual(out.read_text(),'old')
 def test_failure_keeps_existing_database(self):
  out=self.root/'db.json';out.write_text('old')
  self.assertEqual(bd.main(['--register',str(self.root/'missing'),'--out',str(out)]),1);self.assertEqual(out.read_text(),'old')
 def test_bad_today(self):self.assertEqual(bd.main(['--today','bad']),2)
 def test_logo_optional(self):
  data=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aS1kAAAAASUVORK5CYII=');p=self.root/'generic.png';p.write_bytes(data);uri=bd.logo_data_uri(p);self.assertEqual(base64.b64decode(uri.split(',')[1]),data);self.assertEqual(bd.build_payload(SAMPLE,TODAY)['config']['logo'],'')
 def test_vector_logo(self):
  p=self.root/'generic.svg';p.write_text('<svg xmlns="http://www.w3.org/2000/svg"><path d="M0 0h10v10z"/></svg>');self.assertTrue(bd.logo_data_uri(p).startswith('data:image/svg+xml;base64,'))
  p.write_text('<svg xmlns="http://www.w3.org/2000/svg"><image href="data:image/png;base64,iVBORw0KGgo="/></svg>');self.assertTrue(bd.logo_data_uri(p).startswith('data:image/svg+xml;base64,'))
  for text in ['<svg><script>bad</script></svg>','<svg onload="bad()"/>','<svg><image href="https://example.org/image.png"/></svg>']:
   p.write_text(text)
   with self.assertRaises(ValueError):bd.logo_data_uri(p)
 def test_bad_logo(self):
  p=self.root/'bad.png';p.write_text('text')
  with self.assertRaises(ValueError):bd.logo_data_uri(p)
 def test_markdown_scalars_blocks_and_json(self):
  p=self.root/'c.md';p.write_text('---\ncontract_id: "C-1"\ntitle: 原料合約\nnotes: |-\n  第一行\n  第二行\nsource_refs: {"title":{"page":2}}\n---\n原文\n');meta,body=bd.read_markdown(p);self.assertEqual(meta['notes'],'第一行\n第二行');self.assertEqual(meta['source_refs']['title']['page'],2);self.assertIn('原文',body)
 def test_unsupported_yaml_rejected(self):
  p=self.root/'bad.md';p.write_text('---\nsource_refs:\n  title: x\n---\n')
  with self.assertRaises(ValueError):bd.read_markdown(p)
 def test_markdown_input(self):
  p=self.root/'c.md';p.write_text('---\ncontract_id: C-1\ntitle: 原料合約\n---\n');data=bd.build_payload(None,TODAY,markdown_dir=self.root);self.assertEqual(data['records']['contracts'][0]['fields']['title'],'原料合約')
 def write_case(self,stages,people=None):
  p=self.root/'CASE-1.md';text='---\ncase_id: CASE-1\nexample: true\ntitle: 範例\n---\n'
  for i,stage in enumerate(stages):text+='```jsonl\n'+json.dumps({'time':f'2026-10-{i+1:02}T09:00:00+08:00','user':(people or ['甲']*len(stages))[i],'action':'狀態變更','to_stage':stage,'comment':'意見','attachment_version':f'V{i+1}'},ensure_ascii=False)+'\n```\n'
  p.write_text(text);return p
 def test_case_multi_round_and_actors(self):
  p=self.write_case(['收件','法務審閱','退回需求部門','法務審閱','與對方協商','法務審閱','核准','簽署','歸檔']);case,entries=bd.read_case(p);self.assertTrue(case['example']);self.assertEqual(case['stage'],'歸檔');self.assertEqual(len(entries),9);self.assertEqual(entries[3]['from_stage'],'退回需求部門')
 def test_case_append_only_multiple_blocks(self):
  p=self.write_case(['收件']);original=p.read_bytes();entry={'time':'2026-10-02T09:00:00+08:00','user':'乙','action':'審閱','to_stage':'法務審閱','comment':'已審','attachment_version':'V2'}
  with p.open('a') as f:f.write('```jsonl\n'+json.dumps(entry,ensure_ascii=False)+'\n```\n')
  self.assertTrue(p.read_bytes().startswith(original));self.assertEqual(bd.read_case(p)[1][-1]['user'],'乙')
 def test_case_invalid_transition(self):
  with self.assertRaises(ValueError):bd.read_case(self.write_case(['收件','歸檔']))
 def test_case_requires_actor(self):
  with self.assertRaises(ValueError):bd.read_case(self.write_case(['收件'],['']))
 def test_case_requires_initial_receipt(self):
  with self.assertRaises(ValueError):bd.read_case(self.write_case(['核准']))
 def test_case_snapshot_includes_timeline(self):
  self.write_case(['收件','法務審閱']);data=bd.build_payload(SAMPLE,TODAY,cases_dir=self.root);self.assertEqual(len(data['records']['cases']),1);self.assertEqual(len(data['records']['progress']['cases:CASE-1']),2)
 def test_frontend_uses_http_and_has_no_folder_picker(self):
  app=Path(__file__).parent/'app';html=(app/'index.html').read_text();self.assertNotIn('id="connect"',html)
  self.assertIn('id="editor"',html);self.assertNotIn('data/data.js',html)
  source=(app/'datasource.js').read_text();self.assertIn('fetch',source);self.assertNotIn('showDirectoryPicker',source)
 def test_database_flattening_preserves_case_links(self):
  self.write_case(['收件','法務審閱']);data=bd.database_from_payload(bd.build_payload(SAMPLE,TODAY,cases_dir=self.root))
  self.assertEqual(data['progress'][0]['case_id'],'CASE-1');self.assertEqual(len({e['id'] for e in data['progress']}),2)
 def test_reminders_do_not_depend_on_status(self):
  for status in ['', '審閱中', '已終止', '有效']:
   self.assertTrue(bd.enrich({'end_date':'2026-10-06','status':status},TODAY)['is_expired'])
   self.assertTrue(bd.enrich({'end_date':'2026-12-19','status':status},TODAY)['is_expiring'])
   self.assertTrue(bd.enrich({'end_date':'2026-11-01','renewal_type':'自動續約','notice_days':'30','status':status},TODAY)['is_notice_due'])
  self.assertFalse(bd.enrich({'end_date':'2027-10-07','status':'已到期'},TODAY)['is_expired'])
 def test_missing_and_invalid_end_date_not_in_alerts(self):
  for value in ['', '未載明', '2026-02-30']:
   r=bd.enrich({'end_date':value,'status':'已到期','renewal_type':'自動續約','notice_days':'30'},TODAY)
   self.assertTrue(r['is_end_unknown']);self.assertFalse(r['is_expired'] or r['is_expiring'] or r['is_notice_due'])
 def test_system_ids_skip_explicit_ids_and_mark_origin(self):
  data=bd.build_payload(self.csv('contract_id,title\n,a\nC-2026-0001,b\n,c\n'),TODAY)['records']['contracts']
  self.assertEqual([r['id'] for r in data],['C-2026-0002','C-2026-0001','C-2026-0003'])
  self.assertEqual([r['fields']['contract_id'] for r in data],[r['id'] for r in data]);self.assertEqual(data[0]['fields']['contract_id_origin'],'system')
 def test_markdown_missing_id_is_generated_without_source_mutation(self):
  path=self.root/'source.md';path.write_text('---\ntitle: example\n---\noriginal body\n');old=path.read_bytes()
  r=bd.build_payload(None,TODAY,markdown_dir=self.root)['records']['contracts'][0]
  self.assertEqual(r['fields']['contract_id'],'C-2026-0001');self.assertEqual(path.read_bytes(),old)
class HttpTest(unittest.TestCase):
 def test_node_http_writes_and_progress(self):
  import subprocess,shutil
  node=shutil.which('node')
  if not node:self.skipTest('Node 未安裝；執行 test_datasource.js 需 Node')
  result=subprocess.run([node,str(Path(__file__).parent/'test_datasource.js')],capture_output=True,text=True)
  self.assertEqual(result.returncode,0,result.stdout+result.stderr)
 def test_per_event_case_directory(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)/'CASE-1';(root/'log').mkdir(parents=True);(root/'index.md').write_text('---\ncase_id: CASE-1\ntitle: 範例\n---\n')
   (root/'log'/'one.md').write_text('---\ntime: "2026-10-07T01:00:00Z"\nuser: 甲\naction: 收件\nto_stage: 收件\nfrom_stage: ""\nattachment_version: V1\n---\n收到附件\n')
   case,entries=bd.read_case_directory(root);self.assertEqual(case['stage'],'收件');self.assertEqual(entries[0]['comment'],'收到附件')
if __name__=='__main__':unittest.main()
