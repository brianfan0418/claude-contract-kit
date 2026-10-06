# 合約網頁系統交接

2026-10-07 依 B5 完成「共用檔案＋File System Access」原型。修改範圍只有 dashboard/，不包含公司名稱或 logo；不 push。根目錄 README 已指向本檔，現行操作依以下說明。

## 開啟與重建

- 直接以 Windows Edge／Chrome 開啟 dashboard/app/index.html（file://）。未連接為唯讀快照；連接系統資料夾後，可新增合約／案件、編輯及記錄進度。
- 詳細資料格式、權限恢復、介面操作與限制統一在 [README.md](README.md)，本檔只保存工作狀態。

```sh
python3 dashboard/build_dashboard.py --register dashboard/sample_register.csv --out dashboard/app/data/data.js --today 2026-10-07
python3 -m unittest discover -s dashboard
node dashboard/test_datasource.js
```

## 已驗證與限制

- Python unittest 25 項通過，包含 CSV／Markdown／案件格式、快照產生、缺值、schema 改名、logo 及 Node 寫入模擬測試。
- Node 模擬 directory handle 的 16 項檢查通過，驗證新增、更新、進度新檔、狀態流程、來源內容保存、權限失效與樂觀衝突。
- Linux headless Chromium 直接 file:// 開啟：安全內容及 picker API 存在。UI 新增／進度表單用模擬 handle 保存；沒有自動化操作真實資料夾選擇視窗。
- **Windows Edge 實機未測**，包括 UNC／網路磁碟與授權保存。File System Access 沒有跨電腦原子 compare-and-swap；主檔同時編輯仍需協調。
- 私人說明頁、公司 logo、27 筆年報摘錄與 4 件虛構案件留在 tw-admin-ai，沒有納入公開 repo。來源未揭露的欄位留白；年報摘要不當作合約全文。
- 瀏覽器 72 項檢查通過；19 張截圖及每輪結果保存在私人 ui-validation.json／scratchpad/ui3，涵蓋 1920×1080 亮暗、100／200% 字級、390px 版型與模擬寫入表單。這不是 WCAG 全面認證。

下一步由公司以 Windows Edge 真實共用資料夾測試授權、兩人衝突及 Git 提交流程；手機內網 HTTPS 主機仍為後續選項，不是桌面使用前提。
