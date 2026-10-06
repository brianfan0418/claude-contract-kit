---
name: tw-law
description: 合約審閱、登錄或比較需要引用台灣法條、查施行狀態或核對法規版本時使用。以全國法規資料庫現抓條文與本機快取支援法務核對，不從記憶重述法條。
---

# 台灣法規查證

法條唯一來源為[全國法規資料庫](https://law.moj.gov.tw/)。本技能提供查證流程及法規索引，不作法律意見。以全國法規資料庫現行條文為準；須法務核對現行條文、施行日期及個案適用性。

## 執行流程

1. 先讀合約原文與公司手冊，列出須核對的法律問題、法規名稱及候選條號；手冊未填立場時依 contract-review 列待確認問題，不自行補立場。
2. 使用 `<合約工具包資料夾>/tools/fetch_law.py` 現抓法規，將快取置於使用者私人專案的 `law-cache/`。名稱須為官方全名；「民法債編」以「民法」抓取，再定位債編。正式取得方式、命令與失敗處理見 [references/acquisition.md](references/acquisition.md)。
3. 讀 frontmatter、官方生效註記及對應條文。修正日期與抓取日期分別記錄；官方「所有條文」頁可能含尚未施行修法，不能以最新公布版本逕認已生效。
4. 有未生效註記時，快取同時保留官方指定的舊版本。依註記核對所引條號的版本、施行日期及是否已施行；兩版不同或施行狀態查不到時，標「未查證：現行施行版本」，列兩版來源供法務核對，暫不據此下合法性結論。舊版整部內容不自動視為現行條文。
5. 每次引用附「法規名稱、第 X 條、逐字條文、版本來源網址、法規修正日期、抓取日期 YYYY-MM-DD」，並加「以全國法規資料庫現行條文為準」。合約引句另附檔名及頁碼／條號，法律與合約來源分列。
6. 查不到名稱、下載失敗、缺日期／條文、廢止或缺官方舊法連結時停止引用該項，寫明查不到及錯誤；既有快取只可標為歷史資料，不補造本次抓取日期。未確認的法律判斷寫「提請法務確認」；推論標「推論」。

## 合約法規索引

下列關聯是本工具的查證題目分類，不代表每份合約必須適用全部法規；條文內容一律現抓現引。官方名稱與代碼查閱日期：2026-10-07；名稱及代碼來源為官方中文法律／命令 API，見取得方式文件。

| 法規（官方來源） | 與合約的關聯 |
|---|---|
| [民法](https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=B0000001)（債編為主，仍核對總則及其他適用編） | 核對契約成立、履行、解除、損害賠償及買賣、租賃、承攬、委任、借貸等問題。 |
| [民事訴訟法](https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=B0010001) | 核對合意管轄、訴訟程序及證據安排。 |
| [涉外民事法律適用法](https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=B0000007) | 核對涉外契約準據法及法律選擇問題。 |
| [仲裁法](https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=I0020001) | 核對仲裁約定、程序及裁決承認執行問題。 |
| [個人資料保護法](https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=I0050021) | 核對受託處理個資、健康資料、安全措施及跨境資料處理。 |
| [電子簽章法](https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=J0080037) | 核對電子文件、電子簽署與簽署證據保存安排。 |
| [印花稅法](https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=G0340091) | 核對契據分類、稅負及辦理責任，不預填稅率。 |
| [營業秘密法](https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=J0080028) | 核對配方、製程、技術資料及保密措施的保護問題。 |
| [公平交易法](https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=J0150002) | 核對經銷、獨家、價格、競業及交易限制問題。 |
| [公司法](https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=J0080001) | 核對代表權、公司決議與簽約授權。 |
| [證券交易法](https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=G0400001) | 核對公開發行公司的內控及交易核准問題。 |
| [公開發行公司建立內部控制制度處理準則](https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=G0400045) | 核對採購、銷售、研發、財務及資訊等循環的合約控制程序。 |
| [公開發行公司取得或處分資產處理準則](https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=G0400069) | 核對資產、技術及相關交易的核准、估價及公告程序。 |
| [公開發行公司資金貸與及背書保證處理準則](https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=G0400058) | 核對資金貸與及背書保證的程序與管控，是否適用由法務確認。 |
| [藥事法](https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=L0030001) | 核對藥品製造、輸入、銷售、許可及委託安排。 |
| [化粧品衛生安全管理法](https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=L0030013) | 核對化粧品製造、供應、產品資訊及安全責任分工。 |
| [食品安全衛生管理法](https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=L0040001) | 核對食品或保健食品供應、委託製造及追溯責任。 |
| [著作權法](https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=J0070017) | 核對委託成果的著作權歸屬、讓與及授權。 |

特定產品、臨床試驗或智慧財產交易所需其他法規及子法，由法務依實際標的補查全國法規資料庫；本清單不宣稱已完整涵蓋。外國法另交法務查證，不把外國法條混入本技能法規快取。

## Claude Code 與 Cowork

- Claude Code：在工具包根目錄執行 Python 命令；只採用本技能時，仍須提供 `tools/fetch_law.py` 並替換工具包路徑。
- Claude 桌面版 Cowork：在授權的私人資料夾讀技能及法規快取；可執行 Python 的環境依取得方式文件操作。Cowork 的網路與 Python 執行本輪未實測，不能宣稱已抓取；不能執行時由使用者執行同一腳本並提供結果。
