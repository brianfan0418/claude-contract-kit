# 交接

最後更新：2026-10-07 08:23（台灣時間）

## 現況

獨立合約資源 repo 已有台灣製藥／生技／化妝品分類、台灣法與涉外合約手冊。已具備台灣法規技能、下載工具及共用檔案面板。本輪修正根目錄測試匯入與法規保存規則，建立本機 commit，由使用者 push；私人組織、logo、年報契約與介面截圖不進公開 repo。

## 完成項目與決定

- `README.md` 列資源、資料流程與採用方式；文件轉檔可選用 [claude-office-kit 的 doc-library](https://github.com/brianfan0418/claude-office-kit/tree/main/skills/doc-library)，已有符合 schema 的 Markdown 可直接使用。
- `schema/fields.json` v2 定義主要分類及語言／幣別／準據法／爭議方式／機構／地點；有值時須引用原文。舊「經銷代理」由使用者確認市場後分類，`jurisdiction` 留作相容，新資料改填三個爭議欄位，不自動拆舊值。
- `skills/tw-law/` 僅以全國法規資料庫為法條來源，列 18 部法規與合約查證題目；正式資料取得方式及限制集中於 `references/acquisition.md`。公開法條可連線取得，每次存入交付資料夾法規目錄的新版本；引用保存檔案、條號、來源與取得日期，並記施行核對結果，不以記憶重述法條。
- `tools/fetch_law.py` 僅用標準庫，依完整名稱由官方法律／命令 JSON ZIP 查代碼，或按代碼抓官方所有條文頁。法規名稱、代碼、日期與條文不完整時拒收；HTTPS 來源與重新導向限全國法規資料庫；失敗保留既有快取。
- 有未生效註記時保存官方指定舊版與註記；公布版本及整部舊版均不自動認定為現行施行條文。`current_text_verified: false` 表示引用前仍須逐條核對施行狀態。快取附來源、修正／公布日期、抓取日期及時間，`law-cache/` 排除版本控制。
- `playbook/playbook.md` 0.4 分列授權、國內／海外經銷、委託製造、原料供應、技術讓與、顧問、工程、租賃、融資與保密等要點，全部公司立場待填；`contract-review` 透過 tw-law 引用法規，未確認施行版本時只列問題。
- `dashboard/sample_register.csv` 改為 13 筆、11 類虛構業別案例，表頭與 schema 範本一致，含多語、外幣、外國準據法及仲裁的虛構約定；保留既有提醒邊界與狀態數，未提供原文出處就留空，不補造引用。
- 面板採共用檔案與 File System Access；B7 修正 `dashboard/test_review.py` 的套件匯入與 mock 目標，使根目錄及 dashboard 兩種 discovery 都可直接執行。詳細介面與資料格式依 [dashboard/HANDOFF.md](../dashboard/HANDOFF.md)。
- 私人年報契約清冊逐列附頁碼與來源；年報未揭露者留空，契約性質保留原列值，授信額度不當作合約總額，非已驗證的正式主檔。

## 已完成驗證

2026-10-07 B7，於 repo 根目錄執行 README 原指令；沒有設定 PYTHONPATH：

```text
python3 -m unittest discover -s .             65 tests，OK
python3 -m unittest discover -s dashboard     30 tests，OK
node dashboard/test_datasource.js             23 checks，0 failed
```

根目錄已包含 dashboard 的 30 個 unittest，不重複計算總數。Node 23 個是模擬 directory handle 的寫入、衝突與審閱檢查，亦由 unittest 呼叫；不能當作 Windows 實機證據。

私人頁面及範例用 Linux headless Chromium、file:// 驗證：24 項檢查通過，涵蓋桌面 1920、手機 390、200% 字級、明暗及側欄／抽屜鍵盤調寬。7 張亮色截圖逐張檢查，長段落留在卡片內；兩個說明頁的單欄改為自然列高。私人重建命令補 --settings，實際重建保留 27 筆契約、4 件虛構案件、271 單位、90 人與 14 則核決提示；手冊及法規技能相對連結均存在。

電子簽章法官方取得成功，存入私人交付的法規新版本目錄，包含來源及取得日期；施行核對檔標「未查證」。完整證據在私人 ui-validation-b7.json；git diff --check 通過。法規工具的 13 個測試仍為假回應測試，不等同逐條施行核對。

## 接續與限制

第一個可執行動作：以 Windows Edge 實機連接共用資料夾驗證授權及多人衝突；依 tw-law 取得方式保存法規，選定所引條號並核對施行註記；法務另填公司手冊的立場與接受範圍，再審實際簽署版。

- 單一法規的正式 API 查詢端點查不到；官方 API 是批次 ZIP，本工具按代碼的條文抓取使用 HTML 解析，版型改動時可能拒收。
- Windows、Cowork 執行程式未實測；XML ZIP 未下載驗證。法規個案適用及未生效修法的逐條版本仍須法務確認。
- 私人年報表格文字已讀取，PDF 圖像逐列核對未完整完成；原始合約全文、公司最新狀態與未揭露欄位須承辦人提供，不能當作正式主檔驗證通過。
