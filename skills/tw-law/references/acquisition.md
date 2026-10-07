# 全國法規資料庫的取得方式

查閱日期：2026-10-07。唯一法條來源為 `https://law.moj.gov.tw/`；以下為本次實際查閱及下載所得，並非推測端點。

## 官方公開 API

[首頁](https://law.moj.gov.tw/)頁尾「API 文件」連至 [Open API Swagger](https://law.moj.gov.tw/api/swagger/index.html)。該頁指定的正式規格為 [Swagger JSON](https://law.moj.gov.tw/api/swagger/docs/v1)。本次以 Python 標準庫取得規格並實際下載兩個中文 JSON ZIP，HTTP 200；未提供憑證即可讀取，不據此推定後續服務保證或流量限制。

| 官方端點 | 正式文件的功能 |
|---|---|
| [中文法律 JSON](https://law.moj.gov.tw/api/ch/law/json) | 中文法律批次 ZIP，含 `ChLaw.json`、`schema.csv`、`manifest.csv` |
| [中文命令 JSON](https://law.moj.gov.tw/api/ch/order/json) | 中文命令批次 ZIP，含 `ChOrder.json`、`schema.csv`、`manifest.csv` |
| [中文法律 XML](https://law.moj.gov.tw/api/ch/law/xml) | 官方文件列有 XML 格式；本輪未下載驗證 XML 內容 |
| [中文命令 XML](https://law.moj.gov.tw/api/ch/order/xml) | 官方文件列有 XML 格式；本輪未下載驗證 XML 內容 |

規格的路徑參數為 `fileType`，支援 XML 或 json，未列名稱／pcode 查單一法規的 API；本次查不到正式文件所載的單一法規查詢 API。`LawName`、`LawURL`、`LawModifiedDate`、`LawEffectiveDate`、`LawEffectiveNote`、`LawAbandonNote`、`LawArticles` 與條號／內容等欄位依 ZIP 中 `schema.csv` 說明。批次資料的 `UpdateDate` 不等於抓取日期。

## 本工具如何取得

- `--name`：下載官方法律索引，精確比對 `LawName`；查不到再查官方命令索引。`--category law` 或 `--category order` 可指定單一索引，降低下載量。由官方 `LawURL` 取出代碼，再抓「所有條文」HTML 頁。批次 JSON 只負責名稱查找，不直接當成已施行條文。
- `--code`：直接抓官方 `LawClass/LawAll.aspx?pcode=代碼` 頁，避免每次下載整批索引。例如[民法所有條文](https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=B0000001)；官方頁另有[條號查詢](https://law.moj.gov.tw/LawClass/LawSearchCNKey.aspx?BTNType=NO&pcode=B0000001)與[單一條文](https://law.moj.gov.tw/LawClass/LawSingle.aspx?pcode=B0000001&flno=254)導覽。本工具使用 HTML 解析，網站版型改動可能導致拒收，並非未公開 API。
- 網站標示部分條文尚未生效時，跟隨該頁的官方舊法連結，保存兩版本、日期及生效註記；不自動將整部舊法視為現行。例如[民法官方連結的舊版本](https://law.moj.gov.tw/LawClass/LawOldVer.aspx?pcode=B0000001)是歷史版本，不能僅因其日期較早就推定每條均適用。
- 所有下載及重新導向限制在 HTTPS 的 `law.moj.gov.tw`；只在資料完整後替換 Markdown。查不到或下載失敗返回非零，不以舊快取冒充現抓。

## 使用命令

在工具包根目錄執行；Python 僅使用標準庫，Linux 不須安裝套件。將「交付資料夾」替換為使用者實際系統根目錄；每次取得先產生新的「取得時間-唯一識別碼」（例如 UTC 時間加 UUID），以下兩行為各自獨立的示例。

```text
python3 tools/fetch_law.py --name 民法 --category law --cache-dir 交付資料夾/法規/取得時間-唯一識別碼
python3 tools/fetch_law.py --code G0400045 --cache-dir 交付資料夾/法規/取得時間-唯一識別碼
python3 -m unittest tools.test_fetch_law
```

Windows 將 `python3` 換成已確認可用的 `python` 或 `py -3`。未指定 `--cache-dir` 時存工具包的 `law-cache/`（已排除版本控制）；交付作業每次明確指定新的 `交付資料夾/法規/<取得時間-唯一識別碼>/`，不得依賴預設目錄；公司資料及引用版本不進公開 repo。

輸出 `法規/<取得時間-唯一識別碼>/<官方法規名稱>.md` 的 frontmatter 包含來源網址、法規修正／公布日期、抓取日期及時間、施行註記摘要，另保留官方舊版日期／網址（如有）。`current_text_verified: false` 表示程式下載成功不等於法務已核對所引條文的現行施行版本。引用格式與停止條件見 [SKILL.md](../SKILL.md)。引用先讀此保存檔案；記錄保存相對路徑、取得日期、核對日期、條號、施行狀態、官方註記及核對者於同目錄的 `施行核對.md`。尚未核對時明寫「未查證」，不把下載成功視為施行確認。

## 尚待核對

單一法規的正式 API 查詢方式查不到；HTML 解析是本工具的實作方式。法規施行狀態的逐條法律判斷、官方資料尚未整編的修法、主管機關公布文字與資料庫差異及個案適用性，須由法務確認。[官方首頁](https://law.moj.gov.tw/)亦說明資料更新與主管機關公布資料的優先關係，不能把抓取日當作資料已更新到該日的保證。Windows、Cowork 本輪未實測。
