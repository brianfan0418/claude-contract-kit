# 合約面板交接

2026-10-07 完成側欄、緊湊表格與右側明細抽屜改版。這次修改範圍只有 `dashboard/`；其他工作線正在修改 schema、審閱規則與 README，未納入本次提交。

## 產生與驗證

```sh
python3 dashboard/build_dashboard.py --register dashboard/sample_register.csv --out dashboard/sample_dashboard.html --today 2026-10-07
python3 -m unittest discover -s dashboard
```

- `--logo` 將 PNG、JPEG、GIF 或 WebP 圖檔以 data URI 內嵌；不指定時不產生 logo 元素。公開範例未含 logo。
- `--fields` 預設讀取 `schema/fields.json`。表頭、篩選名稱及明細欄位從 schema 取得；CSV 缺欄位時留白。日期衍生欄位與檢視判斷沿用主檔的既有欄位名稱。
- `source_refs` 以文字顯示，JSON 內容格式化後呈現；未提供出處時留白。範例 CSV 未提供原文出處，不補造引用。
- 預設明暗跟隨系統；切換偏好存於 localStorage，讀寫失敗時仍能操作。
- 2026-10-07 實測：23 個 unittest 通過；Chromium 的 27 項操作檢查通過，涵蓋預設檢視、搜尋、篩選、排序、抽屜、系統暗色、偏好保存及 localStorage 拒絕存取。
- 三頁亮暗色與面板抽屜共 8 張 1920×1080 截圖已檢視。說明頁與帶品牌範例位於私人工作目錄，未納入公開 repo。

## 設計依據

- [Tabler：Page layouts](https://docs.tabler.io/ui/layout/page-layouts)：側欄品牌與導覽、頂列、內容區。
- [IBM Carbon：Data table guidelines](https://www.carbondesignsystem.com/building-blocks/core/components/data-table/guidelines)：32px 緊湊列高、全寬表格、排序與補充資訊側面板。
- [Ironclad：Dashboard Overview](https://support.ironcladapp.com/hc/en-us/articles/12286392777751-Dashboard-Overview)：左側預設檢視、件數與疊加篩選。

後續調整介面時先執行上述測試；schema 增修後重新產生範例，檢查新增欄位與窄視窗水平捲動。
