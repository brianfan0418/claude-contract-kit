# 交接

最後更新：2026-10-07 B14（台灣時間）

## 現況

獨立合約資源 repo 已有台灣製藥／生技／化妝品分類、台灣法與涉外合約手冊。已具備台灣法規技能、下載工具及本機合約系統。正式版建議採個人電腦單人本機 HTTP、json-server REST 與 AI CLI；B11 修正既有缺值資料的單欄更新，建立本機 commit，由使用者 push；私人組織、logo、年報契約與介面截圖不進公開 repo。

## 完成項目與決定

- `README.md` 列資源、資料流程與採用方式；文件轉檔可選用 [claude-office-kit 的 doc-library](https://github.com/brianfan0418/claude-office-kit/tree/main/skills/doc-library)，已有符合 schema 的 Markdown 可直接使用。
- `schema/fields.json` v2 定義主要分類及語言／幣別／準據法／爭議方式／機構／地點；有值時須引用原文。舊「經銷代理」由使用者確認市場後分類，`jurisdiction` 留作相容，新資料改填三個爭議欄位，不自動拆舊值。
- `skills/tw-law/` 僅以全國法規資料庫為法條來源，列 18 部法規與合約查證題目；正式資料取得方式及限制集中於 `references/acquisition.md`。公開法條可連線取得，每次存入交付資料夾法規目錄的新版本；引用保存檔案、條號、來源與取得日期，並記施行核對結果，不以記憶重述法條。
- `tools/fetch_law.py` 僅用標準庫，依完整名稱由官方法律／命令 JSON ZIP 查代碼，或按代碼抓官方所有條文頁。法規名稱、代碼、日期與條文不完整時拒收；HTTPS 來源與重新導向限全國法規資料庫；失敗保留既有快取。
- 有未生效註記時保存官方指定舊版與註記；公布版本及整部舊版均不自動認定為現行施行條文。`current_text_verified: false` 表示引用前仍須逐條核對施行狀態。快取附來源、修正／公布日期、抓取日期及時間，`law-cache/` 排除版本控制。
- `playbook/playbook.md` 0.4 分列授權、國內／海外經銷、委託製造、原料供應、技術讓與、顧問、工程、租賃、融資與保密等要點，全部公司立場待填；`contract-review` 透過 tw-law 引用法規，未確認施行版本時只列問題。
- `dashboard/sample_register.csv` 改為 13 筆、11 類虛構業別案例，表頭與 schema 範本一致，含多語、外幣、外國準據法及仲裁的虛構約定；保留既有提醒邊界與狀態數，未提供原文出處就留空，不補造引用。
- B9 面板採 json-server 本機 HTTP；資料在 data/db.json，人與 AI 都經 REST 寫入，AI CLI 先檢查欄位。B7 的兩種 discovery 匯入修正保留。詳細介面與資料格式依 [dashboard/HANDOFF.md](../dashboard/HANDOFF.md)。
- 私人年報主檔以清冊列次給系統編號，註明 system；顯示名稱照錄契約性質，另附頁碼及原文引句。其餘未揭露欄位留白，授信額度不當作合約總額，非已驗證的正式主檔。

## 已完成驗證

2026-10-07 B11：新增時維持全部必填與格式檢查；更新只驗證變更欄位，保留既有空值、歷史 enum 與未變更原文值。表單依顯示初值產生變更欄位，不要求補齊舊資料；空值顯示「未載明」。非本機拒收測試使用 RFC 5737 文件位址。

```text
python3 -m unittest discover -s .             81 tests，OK
python3 -m unittest discover -s dashboard     46 tests，OK
node dashboard/test_datasource.js             22 checks，0 failed
```

根目錄包含 dashboard 的 46 個測試，不重複加總。Linux 使用與私人交付相同 package-lock 實際 npm ci，安裝 43 個套件；本機首頁與合約 API 均 HTTP 200。CLI 合格新增與僅變更備註的既有資料更新確認寫回磁碟；不合格新增 exit 1，未寫入。Chromium 實際編輯缺必填值的年報主檔成功，其餘空值保留。停止程式後逐位元還原範例 db.json，驗證紀錄保存於私人交付 validation-b11.json。公開去識別掃描排除 .git，驗收指定規則零命中；Windows 實機未測。


2026-10-07 B9，於 repo 根目錄執行原指令；沒有設定 PYTHONPATH：

```text
python3 -m unittest discover -s .             79 tests，OK
python3 -m unittest discover -s dashboard     44 tests，OK
node dashboard/test_datasource.js             19 checks，0 failed
```

根目錄已包含 dashboard 的 44 個 unittest，不重複計算總數；Node HTTP 模擬檢查也由 unittest 呼叫。實際 Linux json-server 的網頁與 CLI 寫回另行驗證，測後還原 27 筆契約、4 件範例案件。B9 本機／說明頁圖像與結果保存私人 ui-validation-b9.json；B7、B8 舊驗證留作歷史，不當作本機後端的測試。

電子簽章法官方取得成功，存入私人交付的法規新版本目錄，包含來源及取得日期；施行核對檔標「未查證」。B7 法規證據在私人 ui-validation-b7.json，B8 面板證據在 ui-validation-b8.json；git diff --check 通過。法規工具的 13 個測試仍為假回應測試，不等同逐條施行核對。

## 接續與限制

第一個可執行動作：在副總 Windows 電腦依 dashboard/README.md 安裝 Node.js 與套件，以 start.bat 啟動並驗證網頁及 CLI 寫回；依 tw-law 取得方式保存法規，選定所引條號並核對施行註記；法務另填公司手冊的立場與接受範圍，再審實際簽署版。

- 單一法規的正式 API 查詢端點查不到；官方 API 是批次 ZIP，本工具按代碼的條文抓取使用 HTML 解析，版型改動時可能拒收。
- Windows、Cowork 執行程式未實測；XML ZIP 未下載驗證。法規個案適用及未生效修法的逐條版本仍須法務確認。
- 私人年報表格文字已讀取，PDF 圖像逐列核對未完整完成；原始合約全文、公司最新狀態與未揭露欄位須承辦人提供，不能當作正式主檔驗證通過。

## B12：穩定版本更新

2026-10-07：固定 json-server 0.17.4，官方 engines.node >=12；啟動改用公開 create／defaults／router，移除自訂 lowdb 依賴。POST 明確指定字串 UUID，CLI 及匯入支援數字舊 ID，既有單欄更新驗證保留。82 個根目錄 unittest（含 dashboard 47 個）、22 項 Node 檢查全過，指定去識別規則零命中。私人 demo、鎖檔、說明頁與交付 README 同步。

未完成：官方 Node 20 二進位及 SHA256 已驗證，但 npm ci 下載套件出現 EPIPE，期限前安裝未完成，Node 20／22 的 HTTP、CLI 新增／更新／進度實測皆 NOT_RUN；範例 db.json 完全未變更。接續先在可下載套件的環境完成 npm ci，再依 README 以 Node 20／22 各自啟動、確認磁碟寫回，停止程式並還原資料。私人 validation-b12.json 保存狀態。


## B13：面板資料呈現與說明整合

2026-10-07：面板頂部新增「說明」，start.mjs 以 /docs/ 提供完整 MkDocs 產物，安裝目錄與操作與調整方式集中於 [面板 README](../dashboard/README.md)。欄位出處改成標籤、原文引句、印刷頁／PDF 實體頁連結與驗證狀態，不顯示來源 JSON。欄寬支援拖曳、方向鍵、雙擊自動適應、localStorage 保存與數字輸入對話框；字級、側欄、抽屜、欄位選擇功能保留。SVG logo 匯入新增格式與外部 href／事件拒收檢查；公開範例不包含公司圖檔。虛構欄位以 demo_fields 明確列出，介面逐欄標「範例」。

驗證：根目錄 discovery 83 tests（含 dashboard 48）、Node 25 checks 全過；Linux 實際 npm ci，Node 20.20.2 與 22.23.2 各自啟動，首頁、docs 與 API 200，CLI 新增案件、單欄更新與進度均確認寫回磁碟，測後逐位元還原。瀏覽器確認欄寬拖曳、方向鍵、數字輸入、雙擊適應及重新排序後保留；來源頁碼顯示印刷頁而連結對應 PDF 實體頁。私人範例 27 合約、4 案件的補值與 VM 種子同步，年報非空原文欄位逐欄保留。Windows 實機限制仍依 README，不能以 Linux 驗證代替。B12 的 NOT_RUN 為當輪歷史狀態，穩定版執行驗證已於 B13 補完。

## B14：展示版與建議方案交付

已加入瀏覽器展示資料層：與 REST 共用面板、schema 驗證、案件進度及審閱流程，只替換 api 方法。記憶體資料以 localStorage 保存，讀寫失敗有提示，原型資料不寫入正式資料庫。build_demo.py 將 db.json 作 seed 包裝為 file:// 可開的展示版；私人封裝亦可從面板目錄取得共用程式。

逐條出處採 clause_id、quote 與 original_clauses，點連結捲至該條並移動焦點。原檔待上傳的登錄資料不顯示條款出處表；備註不攤開網址或來源字串。Markdown 匯入保留原文條款及示範 metadata。需求部門與法務承辦人由私人設定提供，公開程式不含公司資料。說明連結新分頁，README 採建議方案語氣，Git 為選用。

驗證：根目錄 unittest 87 tests、dashboard 52 tests、Node 28 checks 通過。瀏覽器實際 file:// 新增案件，Page.reload 後仍在；出處連結聚焦對應條款；年報占位無出處表。MkDocs 字級四段並保存，VM 首頁、文件站與 API 200。私人證據保存在 ui-validation-b14.json 及 ui6/，不提交公開 repo。

正式版仍使用 json-server 0.17.4 及本機 REST；第二階段需登入、案件權限、資料庫與備份。Windows 實機未測。下一個可執行動作：如需正式使用，可由您的 AI 依 dashboard/README.md 協助設定；開展示版則無需本機程式。
