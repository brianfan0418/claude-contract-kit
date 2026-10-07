# 本機合約系統

第一階段由一人在 Windows 電腦使用。瀏覽器開本機 HTTP，json-server 讀寫 data/db.json；人與 Codex／Claude 經同一個 REST 介面操作。原檔唯讀保留，Markdown 保存文字及來源。第二階段將網頁、資料庫與資料夾搬到內網正式伺服器，加入公司登入、案件權限、正式資料庫、備份與維運；本輪未實作第二階段。

## 安裝、啟動、停止

需要 Node.js **22.12.0 以上**（Codex 外掛亦使用 Node.js）及 Python 3。從 dashboard 資料夾執行一次：

```sh
npm install json-server@1.0.0-beta.15 lowdb@7.0.1 --save-exact
```

Windows 雙擊 start.bat；Linux 執行 ./start.sh。預設 3000 埠，可用 start.bat 3001／./start.sh 3001 改埠。腳本啟動 json-server 並開啟 http://127.0.0.1:3000/（localhost 同為本機）。保持程式視窗開啟；按 Ctrl+C 停止。安裝需要下載套件，安裝後操作資料不連外部服務；不使用 CDN 或外部字型。**Windows 啟動腳本實機未測**；Linux 啟動、REST 寫回及瀏覽器操作已實測。

[官方 README](https://github.com/typicode/json-server) 的 v1 用法是 npx json-server data/db.json，預設提供 ./public，額外靜態目錄使用 -s app；不必 --watch。集合提供 GET、POST、PUT、PATCH、DELETE；單一 config 物件提供 GET、PUT、PATCH。[官方 service](https://github.com/typicode/json-server/blob/main/src/service.ts) 的寫入呼叫 db.write，更新會保存至 JSON。本案固定 beta.15，避免 beta 介面變更。

實測 beta.15 [啟動原始碼](https://github.com/typicode/json-server/blob/main/src/bin.ts) 雖解析 --host，listen 呼叫未帶 host。因此 start.mjs 使用該版本的 createApp 與 lowdb JSONFile，以 Node HTTP server 明確 listen(port, '127.0.0.1')，其他電腦無法連入。程式啟動後只由 REST 寫入，不監看外部直接改檔。此程式依固定版本內部介面載入；升級套件須重跑測試及本機寫入驗證。

## 資料與寫入

| 位置／集合 | 內容 |
|---|---|
| 原檔/、md/ | 原始檔、轉出文字及出處；UI 不改原檔 |
| data/db.json：contracts、cases | 合約欄位、案件欄位與目前狀態 |
| progress | 每筆獨立紀錄：case_id、time、user、action、from_stage、to_stage、comment、attachment_version |
| review_versions、review_comments | 不可變條款版本；追加留言、resolve、reopen 事件與文字錨點 |
| config | 由 schema/fields.json 匯入的欄位、選項、流程，選擇性組織、核決、logo |
| app/（私人交付為面板/） | 固定前端，啟動時 HTTP 載入資料；新增、更新後局部重新整理 |

json-server beta.15 的 POST 自動生成字串 id；此內部 ID 與人使用的合約編號、case_number 案號分開。新合約留空編號時自動給 C-年份-流水號並記 contract_id_origin=system，新案件自動給 CASE-日期-隨機碼。欄位由 config.schema 檢查必填、日期、數值、整數、enum 及 pattern；更新可保留既有歷史 enum 原值，不能新填未知值。案件可不填所屬合約編號；處理人與意見必填。

流程：收件 → 法務審閱 → 退回需求部門／與對方協商（可多輪）→ 核准 → 簽署 → 歸檔。每次推進追加 progress，再更新案件狀態。狀態非法拒絕寫入。json-server 不提供多次 REST 呼叫的資料庫交易；若中途失敗，介面報錯，AI 核對進度與主檔後修復，不直接改 db.json。單人使用，不提供多人鎖或登入。AI 停止程式後以 Git 保存版本、提交者及差異，並備份整個資料夾；Git 不代替備份。

## AI 命令列工具

AI 不直接修改 db.json。從 repo 根目錄執行（私人交付用 tools/contract_cli.py）：

```sh
python3 dashboard/tools/contract_cli.py list contracts
python3 dashboard/tools/contract_cli.py create cases --input request.json
python3 dashboard/tools/contract_cli.py update contracts C-2026-0001 --input request.json
python3 dashboard/tools/contract_cli.py progress CASE-20261007-12345678 --input progress.json
python3 dashboard/tools/contract_cli.py review-import CASE-20261007-12345678 --case-dir /path/to/cases/source
```

新增／更新 JSON：{"fields":{"title":"…","contract_type":"…"},"user":"處理人","comment":"意見","attachment_version":"V1"}；須填完整必填欄位。進度 JSON：{"stage":"法務審閱","user":"處理人","comment":"意見","attachment_version":"V1"}。--api 指定其他本機埠，--fields 可指定 schema；repo CLI 預設讀 schema/fields.json；獨立交付沒有 repo schema 時使用本機 config 的欄位，並套用私人部門選項。格式不合時回傳非零並列出錯誤，驗證完成前沒有 POST／PATCH。單人原型的 REST 未設登入，操作限本機。

## 匯入與測試

初次可由 CSV 或 Markdown 建立不存在的 db.json；既有資料只能 --api 匯入，不直接覆寫檔案。請先備份、核對來源再匯入；主檔依編號合併欄位，歷史 progress、審閱事件只加入，差異事件拒絕覆寫。

```sh
python3 dashboard/build_dashboard.py --register dashboard/sample_register.csv --out /new/path/data/db.json
python3 dashboard/build_dashboard.py --md-dir /path/to/md --cases-dir /path/to/cases --settings /path/to/settings.json --api http://127.0.0.1:3000
python3 -m unittest discover -s dashboard
node dashboard/test_datasource.js
```

--logo 才內嵌 PNG／JPEG／GIF／WebP，公開範例沒有公司 logo。缺欄位留白，缺編號自動給號；不改原 CSV／Markdown。解析可攜頂層 YAML scalar、JSON inline、兩空格 literal／folded block；巢狀 YAML 用單行 JSON。cases 舊版 Markdown／JSONL 與每案資料夾日誌可作匯入來源，正式操作資料是本機程式管理的集合。--fields 預設 repo schema；--settings 只加入 organization／approvalAuthority。部門與處理人下拉、核准步驟來源提示保留。

## 介面與審閱

[Fluent 2](https://fluent2.microsoft.design/) 亮暗配色與 [System Icons](https://github.com/microsoft/fluentui-system-icons) SVG 內嵌，MIT 授權見 app/fluent-icons.LICENSE。明暗、100／125／150／200% 字級、欄位選擇、側欄與抽屜寬度保存 localStorage，讀寫包 try/catch。分隔可拖曳、方向鍵調寬、Home／End、Enter／雙擊還原，依 [WAI-ARIA Splitter](https://www.w3.org/WAI/ARIA/apg/patterns/windowsplitter/)。390px 手機版型保留；第一階段手機不能連入，第二階段內網主機與登入上線後才開放。

到期日依瀏覽器當天本地日期計算；不依狀態。已逾期、當天至 90 天、明載自動續約與通知期限、到期日未載明分別檢視。全空欄預設隱藏，可由「欄位」選擇器顯示。

審閱分頁按條號比對上一輪／本輪，以底線、刪除線只標必要增刪；留言串記處理人、時間、待處理／已解決，可只看未解決。selector 使用 TextQuoteSelector 的 exact／prefix／suffix，錨定不可變版本；新留言、回覆、解決與重開各追加事件。新版本由 AI 匯入，網頁不自動接受修訂。成熟依據：[GitHub PR](https://docs.github.com/en/pull-requests/how-tos/review-pull-requests/commenting-on-a-pull-request)、[Google 建議](https://support.google.com/docs/answer/6033474)、[W3C 錨點](https://www.w3.org/TR/annotation-model/#text-quote-selector)。

Word 修訂稿由 import_review.py 使用本機 Pandoc --track-changes=all -t json，產生唯讀匯入來源版本與註解，再經 CLI review-import 寫入本機介面。複雜 inline／跨條號註解拒收，對照原稿驗收。依據：[Pandoc](https://pandoc.org/MANUAL.html#option--track-changes)。
