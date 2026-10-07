# 合約網頁系統交接

2026-10-07 依 B6／B7 完成「共用檔案＋File System Access」原型。公開面板不包含公司名稱或 logo；B7 另依使用者指示修改根目錄交接及台灣法規技能，不 push。根目錄 README 已指向本檔，現行操作依以下說明。

## 開啟與重建

- 直接以 Windows Edge／Chrome 開啟 dashboard/app/index.html（file://）。未連接為唯讀快照；連接系統資料夾後，可新增合約／案件、編輯及記錄進度。
- 詳細資料格式、權限恢復、介面操作與限制統一在 [README.md](README.md)，本檔只保存工作狀態。

```sh
python3 dashboard/build_dashboard.py --register dashboard/sample_register.csv --out dashboard/app/data/data.js --today 2026-10-07
python3 -m unittest discover -s dashboard
node dashboard/test_datasource.js
```

## 已驗證與限制

- 根目錄 README 原 discovery 指令 65 項通過，無需 PYTHONPATH；dashboard discovery 30 項通過，包含 CSV／Markdown／案件格式、快照產生、缺值、schema 改名、logo 及 Node 寫入模擬測試。
- Node 模擬 directory handle 的 23 項檢查通過，驗證新增、更新、進度新檔、狀態流程、來源內容保存、權限失效與樂觀衝突。
- Linux headless Chromium 直接 file:// 開啟：安全內容及 picker API 存在。UI 新增／進度表單用模擬 handle 保存；沒有自動化操作真實資料夾選擇視窗。
- **Windows Edge 實機未測**，包括 UNC／網路磁碟與授權保存。File System Access 沒有跨電腦原子 compare-and-swap；主檔同時編輯仍需協調。
- 私人說明頁、公司 logo、27 筆年報摘錄與 4 件虛構案件留在 tw-admin-ai，沒有納入公開 repo。來源未揭露的欄位留白；年報摘要不當作合約全文。
- B6 瀏覽器 51 項檢查通過；23 張截圖及每輪結果保存在私人 ui-validation-b6.json／scratchpad/ui3/b6，涵蓋 1920×1080 亮暗、100／200% 字級、390px 版型與模擬寫入表單。這不是 WCAG 全面認證。

下一步由公司以 Windows Edge 真實共用資料夾測試授權、兩人衝突及 Git 提交流程；手機內網 HTTPS 主機仍為後續選項，不是桌面使用前提。

## B6 審閱與提案

- 案件審閱分頁按條號比較不可變版本；留言、回覆、解決與重新開啟各新增一檔，保存版本與 TextQuoteSelector。快照與連接資料夾使用同一格式，非法錨點與變更版本拒收。
- import_review.py 用 Pandoc --track-changes=all 建立兩個版本與註解；合成 DOCX 實際成功取出一條修訂及一則註解，未知 inline／圖形／跨條號註解須另核對。完整 Word 排版不在本輪範圍。
- 架構圖、AI 角色平等描述、第二階段帳號提案、真實組織下拉及歷史核決提示留在私人資料夾；公開設定僅在 --settings 提供時納入快照。未修改 schema 或私人 research。
- 第二階段只提案，沒有 AD、NAS、帳號或案件層級權限實作。Windows Edge 真實共用路徑與資料夾授權仍未測；不要把模擬 handle 當作 Windows 實測。

第一個驗證動作：公司用 Windows Edge 連接範例根目錄，選處理人後於案件「審閱」留言、回覆、解決，再重開面板確認檔案。核決公告只提示來源，不自動判定有效性或金額授權。

## B7 驗收修正

套件與直接 discovery 分別採相對／一般匯入，mock 使用已匯入模組的 subprocess 物件。私人說明頁單欄卡片改自然列高；7 張桌面／手機亮色圖逐張檢查，24 項瀏覽器檢查通過。法規來源、手冊連結及重建設定的證據依根目錄 [交接](../docs/HANDOFF.md)，不在此重複法規規則。Windows Edge 實機授權仍未測。
