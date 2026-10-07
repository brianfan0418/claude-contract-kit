# 合約系統交接

2026-10-07 B14：建議方案為展示版直接開啟，正式版採 Windows 本機單人系統。json-server REST 取代資料夾授權與直接檔案讀寫；第二階段才搬到內網正式伺服器並加登入、權限、資料庫與備份。固定前端功能保留，操作與資料格式集中於 [README.md](README.md)。公開程式與文件由 Codex commit 並 push。

## 實作

- node start.mjs 或 start.sh 啟動，固定 json-server 0.17.4；套件官方 Node.js 最低要求 >=12，Node 與 shell 啟動入口均檢查最低版本。使用官方公開 create／defaults／router，明確綁 127.0.0.1；lowdb 使用套件內建版本，不另外釘選。
- HTTP 資料源啟動時讀 config、contracts、cases；新增、更新、進度、審閱留言都經 REST。UI 與 AI CLI 檢查 schema 必填及格式，正式版只將偏好存 localStorage；展示版經瀏覽器資料層保存合約、案件、進度與留言。
- build_dashboard.py 初次可建立不存在的 db.json；已存在時拒絕直接覆寫，須 --api 匯入。進度／留言只追加，版本不可變；import_key 對應原匯入編號，POST 明確指定字串 UUID，0.17 保留指定 id；CLI 相容數字舊 ID。
- AI 工具在 dashboard/tools/contract_cli.py，原檔與 Markdown 保留資料夾。公開 db.json 僅 13 筆虛構去識別合約，無公司 logo、組織、核決或年報內容。
- 私人範例含 27 筆既有登錄占位、4 份虛構合約、4 件虛構案件及組織／核決設定；既有 cases 為匯入來源，正式操作資料保存在 data/db.json。私人說明頁、架構圖與交付 README 已換成本機與第二階段移轉說明。

## 驗證

2026-10-07 B11：CLI、HTTP 資料源與表單更新只驗證變更欄位，既有缺值及未變更原文值保留；新增仍檢查全部必填，清空已知必填或新增不合法值拒收。欄位未載明以「未載明」呈現。根目錄 discovery 81 tests、dashboard 46 tests、Node 22 checks 全過。Linux 實際 npm ci、首頁／API HTTP 200、CLI 合格新增與單欄更新、瀏覽器單欄更新均確認寫回；無效新增未寫入。停止程式後按備份逐位元還原私人範例。B9 以下驗證為歷史紀錄。


根目錄原指令、不設 PYTHONPATH：python3 -m unittest discover -s . 共 79 tests，OK；dashboard discovery 共 44 tests，OK；node dashboard/test_datasource.js 共 19 checks，0 failed。Node 檢查含模擬 HTTP、server ID、格式拒收、進度、審閱錨點與日期／欄位偏好；不等同 Windows 實測。

Linux 實際啟動 json-server，ss 確認 127.0.0.1:3099。headless Chromium 網頁新增案件、推進法務審閱、留言及標記已解決後，從磁碟 db.json 確認寫回；CLI 新增、更新、推進及格式拒收亦實測。測後停止程式、按原備份逐位元還原範例資料。19 張 1920 亮暗／100%／200%、390 亮暗及審閱圖已逐張查看；色票最低文字對比 5.18:1、鍵盤分隔、表格與欄位視窗通過。圖像證據在私人 ui-validation-b9.json／scratchpad/ui3/b9。

## 後續與限制

Windows 瀏覽器啟動與 Edge 實機未測；如需正式使用，建議由您的 AI 依 README 協助設定並驗證。json-server 原型沒有登入、案件權限或多請求交易，不能直接公開成多人正式服務。第二階段須 IT 提供常開主機、Node.js、對內網址、公司登入、資料庫與備份，移轉 db.json 及文件資料夾後做權限、件數及還原驗證。

法規規則與手冊依根目錄 [交接](../docs/HANDOFF.md)；Windows／Cowork 法規取得能力及法條逐條施行核對仍未驗證。年報摘錄不等於合約全文，歷史核決公告不等於目前有效授權。

## B12 接續

穩定版本更新與未完成驗證依根目錄 [交接](../docs/HANDOFF.md) 的 B12 節；前述 B9、B11 寫回驗證不代表 0.17.4 已完成實測。


## B13 接續

欄位出處、欄寬、SVG、說明路由與穩定版實測的決定、證據和限制集中於 [根目錄交接](../docs/HANDOFF.md#b13面板資料呈現與說明整合)。安裝與操作依 [README.md](README.md)。本輪由 Codex commit 並 push，公開產物不含公司資料或 Logo。

## B14 接續

展示版資料層、逐條出處與交付文案的實作及驗證集中於 [根目錄交接](../docs/HANDOFF.md#b14展示版與建議方案交付)。app.js、CSS 與驗證共用，build_demo.py 只加入 seed 及 BrowserDataSource；正式版仍經 REST，不改 db.json。

## B15 接續

Word 原生審閱、預設系統版本紀錄與驗證集中於 [根目錄交接](../docs/HANDOFF.md#b15word-原生審閱與系統版本紀錄)；工具用法與 OOXML 支援範圍依 README。編輯與接受／拒絕仍用 Word，網頁提供總覽、版本比對、AI 建議的新 Word 及下載。

## B16 接續

案件全頁、三分頁、窄螢幕下拉、返回列表狀態與可搬移文件站 sitemap 的實作及驗證集中於 [根目錄交接](../docs/HANDOFF.md#b16案件全頁與說明即時導覽)。新增三個實際本機服務整合測試需先於 dashboard 執行 npm ci；一般 discovery 與 Node 指令維持不變。

## B18：頁面、檢視與篩選分層

側欄主頁帶 Fluent System Icons，預設檢視縮排；篩選改為列表上方可收合面板。案件仍為全頁、合約仍為抽屜，返回案件列表保留篩選。Word 分頁新增三步驟流程及 ONLYOFFICE 官方審閱畫面連結，條文編輯仍在 Word，現有匯入、下載及逐條總覽保留。舊 Windows 批次啟動檔已移除，AI 可依 README 使用 node start.mjs。

根目錄 96／dashboard 61 個 unittest、Node 28 checks 全過；私人完整交付包的瀏覽器導覽、新增保存、REST 與 CLI 寫回均通過。Windows 實機限制維持。
