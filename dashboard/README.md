# 本機合約系統

建議方案：第一階段由一人在 Windows 電腦使用。瀏覽器開本機 HTTP，json-server 讀寫 data/db.json；人與 Codex／Claude 經同一個 REST 介面操作。原檔唯讀保留，Markdown 保存文字及來源。第二階段將網頁、資料庫與資料夾搬到內網正式伺服器，加入公司登入、案件權限、正式資料庫、備份與維運；第二階段尚未實作。

## 展示與正式使用建議

展示版可直接開啟；如需實際使用，可由您的 AI 依原始碼與 README 協助設定。正式版與展示版共用 app.js、CSS、驗證及案件流程；展示版只替換資料層，使用記憶體及包 try/catch 的 localStorage。頂部標示「展示版：資料只存在本瀏覽器」。如保存受限，改用記憶體並提示；file:// 的保存行為依瀏覽器而異，參考 [MDN](https://developer.mozilla.org/en-US/docs/Web/API/Window/localStorage)。

```sh
python3 dashboard/build_demo.py --db dashboard/data/db.json --out /path/to/展示版
```

如需設定正式本機系統，可由您的 AI 確認 Node.js 12 以上後於 dashboard 執行 npm ci，再以 node start.mjs 啟動；預設 3000 埠，停止為 Ctrl+C。CLI／匯入另需 Python 3，Word 修訂匯入另需 Pandoc。平台啟動腳本保留供 AI 參考。Windows 實機未測；Linux HTTP 與寫回已實測。網頁不使用 CDN 或外部字型。

[官方 v0 README](https://github.com/typicode/json-server/tree/v0) 說明 0.17 用法：`npx json-server --watch data/db.json --host 127.0.0.1 --port 3000 --static app`。`--watch` 監看檔案，`--static` 指定靜態目錄，`--host` 指定監聽位址。集合提供 GET／POST／PUT／PATCH／DELETE，config 單一物件亦有讀寫路由；寫入帶 application/json，REST 變更由內建 lowdb 保存至 JSON。[npm registry 套件資料](https://registry.npmjs.org/json-server/0.17.4) 的 engines.node 為 >=12；2026-10-07 執行 npm view json-server@0.17 engines version 確認最新 0.17 為 0.17.4。

start.mjs 使用官方公開的 create／defaults／router，明確 listen(port, '127.0.0.1')；defaults 提供 app（私人版為面板）的靜態網頁及 JSON 解析，關閉 CORS 並拒絕非本機 Origin。啟動腳本檢查 Node.js 最低版本；本程式不啟用檔案監看，資料由 REST 寫入。直接依套件清單安裝亦可使用 npm install json-server@0.17.4 --save-exact。

0.17 的未分頁 GET 回傳全部陣列；分頁使用 _page／_limit（預設每頁 10），頁數連結與總數在回應標頭；巢狀欄位篩選使用 fields.department 等點記法。本面板載入全部集合，篩選與排序在前端處理，未使用 v1 的分頁物件或 _per_page。PATCH 帶完整合併後的 fields，保留未變更欄位；PUT／PATCH 不更改 id，POST 可指定未重複的 id。

## 資料與寫入

| 位置／集合 | 內容 |
|---|---|
| 原檔/、md/ | 原始檔、轉出文字及出處；UI 不改原檔 |
| data/db.json：contracts、cases | 合約欄位、案件欄位與目前狀態 |
| progress | 每筆獨立紀錄：case_id、time、user、action、from_stage、to_stage、comment、attachment_version |
| review_versions、review_comments | 不可變條款版本；追加留言、resolve、reopen 事件與文字錨點 |
| config | 由 schema/fields.json 匯入的欄位、選項、流程，選擇性組織、核決、logo |
| app/（私人交付為面板/） | 固定前端，啟動時 HTTP 載入資料；新增、更新後局部重新整理 |

新增由網頁、CLI 與匯入工具明確指定字串 UUID id；0.17 POST 保留指定 id，也可能為未給號的外部輸入產生數字 id，CLI 相容數字舊 ID。此內部 ID 與人使用的合約編號、case_number 案號分開。新合約留空編號時自動給 C-年份-流水號並記 contract_id_origin=system，新案件自動給 CASE-日期-隨機碼。新增時由 config.schema 檢查全部必填、日期、數值、整數、enum 及 pattern；更新只驗證本次變更欄位，保留既有空值與歷史原值。空值在畫面標「未載明」；變更欄位仍須符合必填與格式，不能新填未知 enum 或清空已有值的必填欄位。案件可不填所屬合約編號；處理人與意見必填。

流程：收件 → 法務審閱 → 退回需求部門／與對方協商（可多輪）→ 核准 → 簽署 → 歸檔。每次推進追加 progress，再更新案件狀態。狀態非法拒絕寫入。json-server 不提供多次 REST 呼叫的資料庫交易；若中途失敗，介面報錯，AI 核對進度與主檔後修復，不直接改 db.json。單人使用，不提供多人鎖或登入。系統本身保留版本與處理紀錄；若您的 AI 需要追蹤自己修改的檔案，可選用 Git。正式使用建議停止程式後備份完整資料夾；Git 不代替備份。

## AI 命令列工具

AI 不直接修改 db.json。從 repo 根目錄執行（私人交付用 tools/contract_cli.py）：

```sh
python3 dashboard/tools/contract_cli.py list contracts
python3 dashboard/tools/contract_cli.py create cases --input request.json
python3 dashboard/tools/contract_cli.py update contracts C-2026-0001 --input request.json
python3 dashboard/tools/contract_cli.py progress CASE-20261007-12345678 --input progress.json
python3 dashboard/tools/contract_cli.py review-import CASE-20261007-12345678 --case-dir /path/to/cases/source
```

新增／更新 JSON：{"fields":{"title":"…","contract_type":"…"},"user":"處理人","comment":"意見","attachment_version":"V1"}；新增須填完整必填欄位，更新 fields 只需提供變更欄位。進度 JSON：{"stage":"法務審閱","user":"處理人","comment":"意見","attachment_version":"V1"}。--api 指定其他本機埠，--fields 可指定 schema；repo CLI 預設讀 schema/fields.json；獨立交付沒有 repo schema 時使用本機 config 的欄位，並套用私人部門選項。格式不合時回傳非零並列出錯誤，驗證完成前沒有 POST／PATCH。單人原型的 REST 未設登入，操作限本機。

## 匯入與測試

初次可由 CSV 或 Markdown 建立不存在的 db.json；既有資料只能 --api 匯入，不直接覆寫檔案。建議先備份、核對來源再匯入；主檔依編號合併欄位，歷史 progress、審閱事件只加入，差異事件拒絕覆寫。

```sh
python3 dashboard/build_dashboard.py --register dashboard/sample_register.csv --out /new/path/data/db.json
python3 dashboard/build_dashboard.py --md-dir /path/to/md --cases-dir /path/to/cases --settings /path/to/settings.json --api http://127.0.0.1:3000
python3 -m unittest discover -s dashboard
node dashboard/test_datasource.js
```

--logo 才內嵌 SVG／PNG／JPEG／GIF／WebP，公開範例沒有公司 logo。缺欄位留白，缺編號自動給號；不改原 CSV／Markdown。解析可攜頂層 YAML scalar、JSON inline、兩空格 literal／folded block；巢狀 YAML 用單行 JSON。cases 舊版 Markdown／JSONL 與每案資料夾日誌可作匯入來源，正式操作資料是本機程式管理的集合。--fields 預設 repo schema；--settings 只加入 organization／approvalAuthority。部門與處理人下拉、核准步驟來源提示保留。

## 介面與審閱

[Fluent 2](https://fluent2.microsoft.design/) 亮暗配色與 [System Icons](https://github.com/microsoft/fluentui-system-icons) SVG 內嵌，MIT 授權見 app/fluent-icons.LICENSE。明暗、100／125／150／200% 字級、欄位選擇、側欄與抽屜寬度保存 localStorage，讀寫包 try/catch。分隔可拖曳、方向鍵調寬、Home／End、Enter／雙擊還原，依 [WAI-ARIA Splitter](https://www.w3.org/WAI/ARIA/apg/patterns/windowsplitter/)。390px 手機版型保留；第一階段手機不能連入，第二階段內網主機與登入上線後才開放。

到期日依瀏覽器當天本地日期計算；不依狀態。已逾期、當天至 90 天、明載自動續約與通知期限、到期日未載明分別檢視。全空欄預設隱藏，可由「欄位」選擇器顯示。

審閱分頁按條號比對上一輪／本輪，以底線、刪除線只標必要增刪；留言串記處理人、時間、待處理／已解決，可只看未解決。selector 使用 TextQuoteSelector 的 exact／prefix／suffix，錨定不可變版本；新留言、回覆、解決與重開各追加事件。新版本由 AI 匯入，網頁不自動接受修訂。成熟依據：[GitHub PR](https://docs.github.com/en/pull-requests/how-tos/review-pull-requests/commenting-on-a-pull-request)、[Google 建議](https://support.google.com/docs/answer/6033474)、[W3C 錨點](https://www.w3.org/TR/annotation-model/#text-quote-selector)。

Word 修訂稿由 import_review.py 使用本機 Pandoc --track-changes=all -t json，產生唯讀匯入來源版本與註解，再經 CLI review-import 寫入本機介面。複雜 inline／跨條號註解拒收，對照原稿驗收。依據：[Pandoc](https://pandoc.org/MANUAL.html#option--track-changes)。


## 文件路由、欄位出處與欄寬

json-server 的 [v0 公開模組 API](https://github.com/typicode/json-server/tree/v0#module) 提供 defaults 的 static 選項；將完整 MkDocs 產物放在 `docs-site/site/`，由 start.mjs 掛於 `/docs/`。另可用 `CONTRACT_DOCS_DIR` 指定建置產物目錄。面板頂部「說明」以新分頁開啟同一程式的 `/docs/index.html`。

欄寬採 [Microsoft Fluent DataGrid](https://fluentui-blazor.azurewebsites.net/datagrid) 的 ResizableColumns 拖曳邊界與鍵盤調整概念；vanilla 實作遵循 [WAI-ARIA Separator／Window Splitter](https://www.w3.org/WAI/ARIA/apg/patterns/windowsplitter/)。表頭邊界可拖曳，聚焦後左右鍵調整 16px、Shift＋左右鍵 32px，Home／End 選 80／1000px；雙擊或 Enter 按目前顯示資料自動適應。「欄寬」可直接輸入尺寸，提供不拖曳的單指標操作方式。合約與案件的欄寬分別保存，localStorage 失敗時仍可使用。

欄位出處以欄位名稱、原文引句、來源與驗證狀態呈現。頁碼標示採印刷頁，PDF 連結採實體頁；缺原文與驗證資料不推定。`demo: true` 加 `demo_fields` 列出虛構補值欄位，介面只對這些值標「範例」，原文摘錄不加範例標記。`--logo` 支援 SVG 及點陣圖；SVG 拒絕 script、事件屬性與外部 href。公司圖檔只放私人交付。

欄位出處可使用 clause_id 與 quote；明細點條號跳至 original_clauses 的原文。Markdown 匯入可附 original_status、original_clauses、demo 及 demo_fields，保存在主檔 metadata，與欄位分開。既有清冊尚無原檔時建議標 pending，不將清冊當作合約條款出處。備註的網址與原始來源字串不展開；來源以短標與連結呈現。
