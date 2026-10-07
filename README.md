# claude-contract-kit

供台灣製藥、生技、化妝品公司的合約承辦人、法務與最終把關者使用的資源目錄：合約登錄、續約及同類合約比對、條款初審、主檔與到期面板。各項資源可分別採用，AI 初審須由法務確認。

## 資源與採用方式

| 路徑 | 用途 | 採用情境 |
|---|---|---|
| `schema/fields.json` | 主檔欄位、分類與引用格式 | 需要建立可追溯的合約清冊 |
| `schema/register.csv` | 只有表頭的主檔範本 | 預覽欄位；正式主檔由程式產生 |
| `skills/contract-intake/` | 抽取、引用、獨立核對後登錄 | 盤點或新增合約 |
| `skills/contract-compare/` | 逐條比較續約與同類合約 | 修改或續約談判 |
| `skills/contract-review/` | 依公司手冊做初審 | 簽約前核對條款 |
| `skills/tw-law/` | 全國法規資料庫的法規索引、現抓引用及施行狀態核對 | 初審需要台灣法條依據 |
| `tools/fetch_law.py` | 依官方名稱或代碼下載法規至本機快取 | 需要可追溯的法規版本與抓取日期 |
| `playbook/playbook.md` | 台灣法與涉外合約條款要點 | 公司法務填入立場、可接受範圍與升級條件 |
| `build_register.py` | 驗證 frontmatter 與引用，產生 CSV | 已有符合規格的 Markdown 合約庫 |
| `dashboard/` | 瀏覽器面板與資料產生工具 | 查看分類、到期與通知截止日 |

Claude Code：建議僅選用您已採用的完整 skill 目錄至專案 `.claude/skills/`，先備份同名內容；將 `<合約工具包資料夾>` 替換為本 repo 的絕對路徑。手冊複製至私人專案，由法務填寫公司立場，skill 改指向該份手冊，避免在公開 repo 保存公司資料。

Claude 桌面版 Cowork：可由您的 AI 協助 在授權資料夾讀取選定 skill 與手冊；需要封裝外掛時，依 [office-kit 的採用指南](https://github.com/brianfan0418/claude-office-kit/blob/main/GUIDE-FOR-CLAUDE.md) 的官方結構選入本 repo 的 skills、schema 與程式，並調整內部路徑。此 repo 本身未附可直接安裝的外掛；Python 執行與資料夾存取須在 Cowork 實測。

## 文件轉檔與資料流程

原始合約唯讀，合約資料放在工具 repo 以外的私人資料夾。已有符合 `fields.json` frontmatter 與頁標記規格的 Markdown 時可直接使用。

需要 Word、PDF、Excel、PowerPoint 或掃描文件轉檔時，可選用 [claude-office-kit 的 doc-library](https://github.com/brianfan0418/claude-office-kit/tree/main/skills/doc-library) 與 [convert_docs.py 說明](https://github.com/brianfan0418/claude-office-kit/blob/main/tools/README-convert-docs.md)。兩個 repo 分別取得，不要求安裝整套 office-kit。需要新信提示時，另選 [Outlook 監看](https://github.com/brianfan0418/claude-office-kit/blob/main/tools/README-outlook-watch.md)。

1. 轉檔並保留來源檔名、SHA-256 與頁碼；轉檔不代表欄位已驗證。
2. contract-intake 按 schema 抽取欄位，逐欄附原文引句與頁碼或條號，未載明者留空或填 schema 允許的「未載明」。
3. 由不帶前情的另一個對話回原檔核對；全部相符才標「已驗證」，使用者確認後更新主檔。
4. contract-review 引用公司手冊，contract-compare 比較版本；手冊尚未填立場時列問題，不自行判定符合公司標準。
5. 最終簽署版重新登錄與驗證；義務、續約鏈與通知期限由原文或使用者確認後更新。

可由您的 AI 在本 repo 根目錄執行（路徑替換為使用者資料夾）：

```text
python3 build_register.py --md-dir 合約庫/md --out 合約庫/register.csv --source-root 合約庫/原檔
```

面板的資料輸出、開啟方式與介面驗證依 [dashboard/HANDOFF.md](dashboard/HANDOFF.md) 操作，使用與目前程式版本一致的命令。Python 程式只用標準庫。Windows 將 `python3` 換成已確認可用的 `python` 或 `py -3`。正式主檔 CSV 由程式產生；公開虛構案例與僅依年報整理的私人研究 CSV 是示範／研究資料，不是已驗證的正式主檔。被拒收的合約會列出錯誤，不寫入正式主檔。

## 欄位與在地化

所有欄位與列舉由 [schema/fields.json](schema/fields.json) 定義，不另維護欄位表。分類包含授權、國內／海外經銷、委託製造、原料供應、臨床試驗、共同研發、技術讓與、合作投資，以及服務、租賃、保密、工程、保險與融資等行政合約。這是本工具依工作情境設計的分類，並非法律定性或公司實際合約清單。

合約語言、幣別、準據法、爭議解決方式、法院／仲裁機構與地點各自記錄；多語優先版本寫於引用支持的關鍵條款。schema v2 保留原有 `currency` 與 `governing_law`，新增 `contract_language`、`dispute_resolution`、`dispute_forum`、`dispute_location`。

升級既有資料時：舊「經銷代理」由使用者依市場確認改為國內或海外經銷；舊 `jurisdiction` 留作相容欄位，新登錄改填三個爭議欄位，舊值須回原文核對後拆分，不自動推定。新欄位屬選填，有值時仍須 citations；舊資料缺少新欄位可留空。修改 schema 後重新產生主檔，再重建面板。面板目前不另提供新欄位專用篩選器。

條款分類部分參考 [CUAD 論文與附錄](https://arxiv.org/abs/2103.06268)（查閱 2026-10-07）。CUAD 是國際公開資料集；本工具借用條款類別名稱，不把其樣本法域或立場當作台灣法律。`source` 的「本工具自訂」為設計來源，不宣稱通用標準。台灣法條及適用性依手冊連結，由法務核對現行條文。

## 面板計算

基準日為執行當天，可用 `--today YYYY-MM-DD` 指定；通知截止日為到期日減通知天數。有效合約的到期與通知期限距基準日 0 至 90 天者列入提醒；通知截止日已過者表中標紅，不計入即將通知數。狀態為「已到期」，或狀態為「有效」但已逾期者列為已到期；後者須由承辦人確認是否已續約再更新主檔。

## 測試與限制

```text
python3 -m unittest discover -s .
python3 -m unittest discover -s dashboard
```

根目錄 discovery 同時納入主檔、法規工具及面板測試；法規工具的網路測試採假回應。正式 API、取得方式、命令及施行狀態限制見 [tw-law 取得方式](skills/tw-law/references/acquisition.md)。法規快取預設排除版本控制；正式引用前現抓，附條號與抓取日期，提醒「以全國法規資料庫現行條文為準」。

`dashboard/sample_register.csv` 為 13 筆虛構資料，涵蓋 11 類授權、國內／海外經銷、委託製造、原料供應、技術讓與、顧問、工程、租賃、貸款及保密案例；含多語、外幣、外國準據法與仲裁的虛構約定。所有名稱、日期及條款設定只供展示，不能作為公司條款立場。第一筆語言留空示範未提供欄位，其他案例顯示語言資料；未提供原文出處，不補造引用。以新版 CSV 重新產生面板即可查看案例。

驗證結果、未實測項目與下一步見 [docs/HANDOFF.md](docs/HANDOFF.md)。MIT 授權見 [LICENSE](LICENSE)。
