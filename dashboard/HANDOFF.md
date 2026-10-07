# 合約系統交接

2026-10-07 B9：使用者改定第一階段為 Windows 本機單人系統。json-server REST 取代資料夾授權與直接檔案讀寫；第二階段才搬到內網正式伺服器並加登入、權限、資料庫與備份。固定前端功能保留，操作與資料格式集中於 [README.md](README.md)。本輪 commit 後由使用者 push。

## 實作

- start.bat／start.sh 呼叫 start.mjs，固定 json-server 1.0.0-beta.15、lowdb 7.0.1；Node.js >=22.12.0。Node HTTP listener 明確綁 127.0.0.1；官方 beta.15 CLI 的 --host 未傳入 listen，因此沒有直接採用該 CLI 啟動。
- HTTP 資料源啟動時讀 config、contracts、cases；新增、更新、進度、審閱留言都經 REST。UI 與 AI CLI 檢查 schema 必填及格式，偏好才存 localStorage，合約資料不存瀏覽器。
- build_dashboard.py 初次可建立不存在的 db.json；已存在時拒絕直接覆寫，須 --api 匯入。進度／留言只追加，版本不可變；import_key 對應原匯入編號，適應 beta.15 POST 生成內部 id 的行為。
- AI 工具在 dashboard/tools/contract_cli.py，原檔與 Markdown 保留資料夾。公開 db.json 僅 13 筆虛構去識別合約，無公司 logo、組織、核決或年報內容。
- 私人範例保留 27 筆年報摘錄、4 件虛構案件及組織／核決設定；既有 cases 為匯入來源，正式操作資料保存在 data/db.json。私人說明頁、架構圖與交付 README 已換成本機與第二階段移轉說明。

## 驗證

2026-10-07 B11：CLI、HTTP 資料源與表單更新只驗證變更欄位，既有缺值及未變更原文值保留；新增仍檢查全部必填，清空已知必填或新增不合法值拒收。欄位未載明以「未載明」呈現。根目錄 discovery 81 tests、dashboard 46 tests、Node 22 checks 全過。Linux 實際 npm ci、首頁／API HTTP 200、CLI 合格新增與單欄更新、瀏覽器單欄更新均確認寫回；無效新增未寫入。停止程式後按備份逐位元還原私人範例。B9 以下驗證為歷史紀錄。


根目錄原指令、不設 PYTHONPATH：python3 -m unittest discover -s . 共 79 tests，OK；dashboard discovery 共 44 tests，OK；node dashboard/test_datasource.js 共 19 checks，0 failed。Node 檢查含模擬 HTTP、server ID、格式拒收、進度、審閱錨點與日期／欄位偏好；不等同 Windows 實測。

Linux 實際啟動 json-server，ss 確認 127.0.0.1:3099。headless Chromium 網頁新增案件、推進法務審閱、留言及標記已解決後，從磁碟 db.json 確認寫回；CLI 新增、更新、推進及格式拒收亦實測。測後停止程式、按原備份逐位元還原範例資料。19 張 1920 亮暗／100%／200%、390 亮暗及審閱圖已逐張查看；色票最低文字對比 5.18:1、鍵盤分隔、表格與欄位視窗通過。圖像證據在私人 ui-validation-b9.json／scratchpad/ui3/b9。

## 後續與限制

Windows start.bat、瀏覽器啟動與 Edge 實機未測；下一步在副總電腦依 README 安裝及驗證。json-server 原型沒有登入、案件權限或多請求交易，不能直接公開成多人正式服務。第二階段須 IT 提供常開主機、Node.js、對內網址、公司登入、資料庫與備份，移轉 db.json 及文件資料夾後做權限、件數及還原驗證。

法規規則與手冊依根目錄 [交接](../docs/HANDOFF.md)；Windows／Cowork 法規取得能力及法條逐條施行核對仍未驗證。年報摘錄不等於合約全文，歷史核決公告不等於目前有效授權。
