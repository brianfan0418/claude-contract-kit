# 合約管理

整理公司全部合約、分類與篩選、到期與續約提醒、續約與同類合約比對、條款初審的一組工具，供 Claude 與合約最終把關者使用。

## 設計原則

1. 原始合約檔唯讀，不由任何工具修改。
2. 每份合約先轉成 Markdown，頁首以 YAML frontmatter 存 metadata（欄位與 `schema/fields.json` 一致）。Markdown 與 `register.csv` 都是衍生資料，可由原檔重新產生。
3. `register.csv` 只由 `build_register.py` 從 frontmatter 彙整產生，不手動編輯。
4. 所有由 AI 產出的欄位與意見都附原文出處（檔案、頁碼、條號、逐字引句）；抽不到的寫「未載明」，不推測。
5. 做與驗分開：抽取與審閱的結果由另一個不帶前情的對話逐條回原文比對，比對不符者不寫入主檔。
6. AI 初審不取代法務與律師判斷。

## 資料夾結構

工具（本資料夾）：

```
contracts/
  README.md
  build_register.py        由 Markdown frontmatter 產生 register.csv，並檢查引句是否逐字在原文
  schema/
    fields.json            欄位定義與分類代碼
    register.csv           只有表頭的主檔範本
  skills/
    contract-intake/       讀合約、抽欄位、附出處、驗證、寫入主檔
    contract-compare/      續約與同類合約逐條比對
    contract-review/       依審閱手冊做初審
  playbook/playbook.md     審閱手冊範本（公司立場待填）
  dashboard/
    build_dashboard.py     由 register.csv 產生單一 HTML 面板
    sample_register.csv    虛構範例，僅供測試
```

使用者的合約資料（建議放在工具資料夾之外，內容不進版本控制）：

```
合約庫/
  原檔/                    原始合約，唯讀
  md/                      doc-library 轉出的 Markdown，頁首含 frontmatter
  register.csv             build_register.py 產生
  dashboard.html           build_dashboard.py 產生
  審閱紀錄/                比對與初審輸出
```

## 工作流程

| 階段 | 做什麼 | 工具 | 產出 |
|---|---|---|---|
| 1 收件 | 取得最終或待審版本，放入 `原檔/` | Outlook 監看（`tools/outlook-watch.py`）可提示新信與附件 | 原檔 |
| 2 登錄 | 轉 Markdown、抽取欄位與章節目錄、附出處 | doc-library、contract-intake | `md/*.md`（驗證狀態：未驗證） |
| 3 驗證 | 不帶前情的對話逐條回原文比對 | contract-intake 的驗證交辦 | 驗證狀態：已驗證或驗證不符 |
| 4 審閱 | 依審閱手冊初審；續約時與上期比對 | contract-review、contract-compare | `審閱紀錄/` |
| 5 簽署 | 人工簽署；最終版本重新走 2 至 3，狀態改為「有效」 | contract-intake | 更新 frontmatter |
| 6 執行與義務追蹤 | 於 `obligations` 記錄交付、付款、報告、保險、稽核等日期 | contract-intake | frontmatter |
| 7 到期與續約 | 面板顯示到期與通知截止日；續約時開新編號並以 `prior_contract_id` 連結上期，上期狀態改為「已被續約取代」 | build_dashboard.py、contract-compare | 面板、比對表 |
| 8 歸檔 | 終止或到期後狀態改為「已終止」「已到期」或「已歸檔」 | — | frontmatter |

更新主檔的方式一律是修改 Markdown frontmatter（經驗證）後重跑 `build_register.py`，再重跑 `build_dashboard.py`。

## Markdown frontmatter

```
---
contract_id: "C-2026-0001"
title: "原料供應合約"
end_date: "2026-11-30"
renewal_type: "自動續約"
...（其餘欄位見下表，沒有值的欄位寫 "" ）
source_path: "原檔/原料供應合約.pdf"
source_sha256: "（原檔的 SHA-256）"
converter: "doc-library"
converted_at: "2026-10-07"
ocr: false
verification_status: "已驗證"
verified_at: "2026-10-07"
verifier_note: ""
citations:
  - {"field":"end_date","file":"原檔/原料供應合約.pdf","page":3,"clause":"第6條","quote":"本合約有效期間至民國115年11月30日止"}
---
<!-- page: 1 -->
（doc-library 轉出的內文，原樣保留）
```

轉檔與驗證鍵的定義見 `schema/fields.json` 的 `frontmatter`；除共用的 `title` 外，這些鍵不進 `register.csv`。轉檔以檔名預填 `title`，contract-intake 核對原文後覆寫同一鍵，不再新增第二個 `title`。

`build_register.py` 寫入一份合約的條件：欄位型別與列舉值符合 `fields.json`；須附出處的欄位有值（且不是「未載明」）時至少有一筆 citations；每筆 citations 須有頁碼或條號，quote 逐字出現在內文（有 page 者該頁須有頁標記，且引句須在該頁）；`needs_review` 不為 true；`verification_status` 為「已驗證」；給 `--source-root` 時 `source_sha256` 與原檔相符。任一項不符就不寫入該份並列出原因。遞迴掃描排除 `_history/`。原檔重轉後驗證狀態重設為「未驗證」，待新版複核完成才解除 `needs_review`。

## 合約主檔欄位

`register.csv` 欄位順序與下表一致。日期一律 `YYYY-MM-DD`。列舉欄位儲存中文 label（便於以 Excel 檢視），`fields.json` 同時提供 code。CSV 使用 UTF-8 含 BOM，Excel 可直接開啟。

| 欄位 | 中文名 | 型別 | 必填 | 須附原文出處 | 說明 | 來源 |
|---|---|---|---|---|---|---|
| `contract_id` | 合約編號 | string | 是 | 否（人工或系統填） | 主鍵。格式 C-西元年-四位流水號，例 C-2026-0001；一份合約一個編號，續約另編新號並以 prior_contract_id 連結上期。 | CLM 通行欄位（Contract ID） |
| `title` | 合約名稱 | string | 是 | 是 | 合約封面或首頁所載名稱；未載明時以「對象＋類型」自擬並於 notes 註明。 | CUAD:Document Name |
| `contract_type` | 合約類型 | enum | 是 | 否（人工或系統填） | 分類代碼見 fields.json 的 contract_type。 | CLM 通行欄位（Contract Type） |
| `department` | 承辦部門 | enum | 是 | 否（人工或系統填） | 負責該合約的部門，分類見 fields.json 的 department；各公司應依組織調整。 | CLM 通行欄位（Business Unit / Department） |
| `owner` | 承辦人 | string | 否 | 否（人工或系統填） | 合約的日常承辦人姓名或職稱，供提醒對象使用。 | CLM 通行欄位（Contract Owner） |
| `our_entity` | 本方簽約主體 | string | 是 | 是 | 本公司簽約的法人全名。 | CUAD:Parties |
| `counterparty_name` | 對象名稱 | string | 是 | 是 | 相對人法人或自然人全名，以合約首頁或簽章頁為準。 | CUAD:Parties |
| `counterparty_category` | 對象類別 | enum | 是 | 否（人工或系統填） | 分類見 fields.json 的 counterparty_category。 | CLM 通行欄位（Counterparty Type） |
| `counterparty_tax_id` | 對象統一編號 | string | 否 | 是 | 相對人統一編號或身分證明字號；未載明時留空。 | 本工具自訂 |
| `status` | 狀態 | enum | 是 | 否（人工或系統填） | 分類見 fields.json 的 status；到期與否由面板依日期計算，不另存。 | CLM 通行欄位（Contract Status / Lifecycle Stage） |
| `signing_date` | 簽署日 | date | 否 | 是 | 最後一方簽署之日，格式 YYYY-MM-DD。 | CUAD:Agreement Date |
| `effective_date` | 生效日 | date | 否 | 是 | 合約約定的起算日，格式 YYYY-MM-DD。 | CUAD:Effective Date |
| `end_date` | 到期日 | date | 否 | 是 | 現行期間的屆滿日；無固定期限者留空並將 renewal_type 設為「無固定期限」。 | CUAD:Expiration Date |
| `renewal_type` | 續約方式 | enum | 是 | 是 | 自動續約／書面續約／不續約／無固定期限／未載明。 | CUAD:Renewal Term |
| `renewal_term_months` | 續約期間（月） | integer | 否 | 是 | 每次續約延長的月數；未載明留空。 | CUAD:Renewal Term |
| `notice_days` | 通知期限（天） | integer | 否 | 是 | 不續約或終止須提前通知的天數；通知截止日 = 到期日 - 通知期限，由面板計算。 | CUAD:Notice to Terminate Renewal |
| `termination_for_convenience` | 無因終止權 | enum | 否 | 是 | 有（雙方）／有（僅本方）／有（僅對方）／無／未載明。 | CUAD:Termination for Convenience |
| `contract_value` | 合約金額 | number | 否 | 是 | 合約總額或年額（於 value_basis 註明）；無金額者留空。 | CLM 通行欄位（Contract Value） |
| `currency` | 幣別 | string | 否 | 是 | ISO 4217 三碼，例 TWD、USD、CNY。 | ISO 4217 |
| `value_basis` | 金額基礎 | string | 否 | 是 | 總額／年額／月額／單價／未載明。 | 本工具自訂 |
| `payment_terms` | 付款條件 | string | 否 | 是 | 付款時點與期限摘要，例「月結 60 天」。 | CLM 通行欄位（Payment Terms） |
| `liability_cap` | 責任上限 | string | 否 | 是 | 責任上限條款摘要（金額或倍數、例外）；無上限寫「無上限」，未載明寫「未載明」。 | CUAD:Cap on Liability / Uncapped Liability |
| `governing_law` | 準據法 | string | 否 | 是 | 準據法所載法域，例「中華民國法」。 | CUAD:Governing Law |
| `jurisdiction` | 管轄法院或仲裁 | string | 否 | 是 | 約定管轄法院或仲裁機構與地點。 | CLM 通行欄位（Dispute Resolution / Jurisdiction） |
| `assignment_restriction` | 轉讓限制 | string | 否 | 是 | 轉讓、控制權變更限制摘要。 | CUAD:Anti-Assignment / Change of Control |
| `involves_personal_data` | 涉及個資 | enum | 否 | 是 | 是／否／未載明。 | 本工具自訂 |
| `confidentiality` | 保密條款 | enum | 否 | 是 | 有／無／未載明。 | CLM 通行欄位（Confidentiality） |
| `prior_contract_id` | 上期合約編號 | string | 否 | 否（人工或系統填） | 續約時指向被取代的上期 contract_id。 | CLM 通行欄位（Renewal Chain） |
| `parent_contract_id` | 主約編號 | string | 否 | 否（人工或系統填） | 補充協議、訂單、附件所屬的主約 contract_id。 | CLM 通行欄位（Parent / Child Agreement） |
| `obligations` | 主要義務與里程碑 | string | 否 | 是 | 需追蹤的義務（交付、付款、報告、保險、稽核）與日期，以「日期：事項」逐項、以 | 分隔。 | CLM 通行欄位（Obligation Management） |
| `toc` | 章節目錄 | string | 否 | 是 | 章節與條號清單，以 | 分隔，例「第1條 定義 | 第2條 服務範圍」。 | 本工具自訂 |
| `key_clauses` | 關鍵條款摘要 | string | 否 | 是 | 關鍵條款的條號與摘要，以 | 分隔，例「第8條：責任上限為前12個月已付費用」。 | 本工具自訂 |
| `risk_level` | 初審風險等級 | enum | 否 | 否（人工或系統填） | 低／中／高／未審；由 contract-review 寫入，人工覆核後才視為定案。 | 本工具自訂 |
| `last_review_date` | 最近審閱日 | date | 否 | 否（人工或系統填） | 最近一次審閱完成日。 | 本工具自訂 |
| `source_refs` | 欄位出處 | string | 否 | 否（人工或系統填） | 各欄位的原文出處，格式「欄位=頁碼/條號」，以 | 分隔；由 contract-intake 寫入。 | 本工具自訂 |
| `file_path` | 原檔位置 | string | 否 | 否（人工或系統填） | 最終簽署版原檔所在位置或連結。 | CLM 通行欄位（Document Repository Link） |
| `notes` | 備註 | string | 否 | 否（人工或系統填） | 其他須記錄的事項。 | CLM 通行欄位 |
| `updated_at` | 最後更新日 | date | 是 | 否（人工或系統填） | 主檔此列最後修改日。 | CLM 通行欄位 |

CUAD 類別名稱依論文附錄表 4、5 核對：[CUAD 論文](https://arxiv.org/abs/2103.06268)，查閱日期 2026-10-07。

來源欄說明：「CUAD:」表示借用 The Atticus Project 的 Contract Understanding Atticus Dataset（CUAD v1）的條款類別名稱；「CLM 通行欄位」表示商用合約生命週期管理（CLM）產品的合約主檔普遍具備的欄位（例如合約編號、類型、對象、狀態、金額、續約與通知、原檔連結、上下期關係）；「本工具自訂」為本工具為面板、出處追溯或初審流程所加。欄位名稱為本工具自訂的英文識別字，未逐項對照特定產品或標準的欄位命名。

## 分類代碼

- `contract_type`：採購供應、服務、委外承攬、不動產租賃、設備租賃、保密協定、經銷代理、授權、顧問專業服務、工程裝修、保險、融資借款、合作備忘或意向書、其他
- `department`：總經理室、財務、人資、採購、業務、行銷、研發、品保、生產、資訊、法務、行政總務、其他
- `counterparty_category`：供應商、客戶、外部機構、房東、承租人、專業服務、金融機構、經銷或代理商、關係企業、其他
- `status`：審閱中、待簽署、有效、已到期、已終止、已被續約取代、已歸檔
- `renewal_type`：自動續約、書面續約、不續約、無固定期限、未載明
- `termination_for_convenience`：有（雙方）、有（僅本方）、有（僅對方）、無、未載明
- `involves_personal_data`：是、否、未載明
- `confidentiality`：有、無、未載明
- `risk_level`：低、中、高、未審

各公司應依組織調整 `department` 與其他分類，修改 `schema/fields.json` 後重跑 `build_register.py` 與 `build_dashboard.py`。

## 面板計算規則

基準日為執行 `build_dashboard.py` 當天（可用 `--today` 指定）。

- 通知截止日 = 到期日 - 通知期限（天）。
- 已到期：狀態為「已到期」，或狀態為「有效」但到期日早於基準日。後者代表主檔需要更新（確認是否已續約）。
- 有效：狀態為「有效」且未逾期。
- 90 天內到期：有效，且到期日距基準日 0 至 90 天。
- 自動續約須通知：有效、續約方式為「自動續約」，且通知截止日距基準日 0 至 90 天。通知截止日已過者，表中以紅字標示，不計入此數字。

```
python dashboard/build_dashboard.py --register 合約庫/register.csv --out 合約庫/dashboard.html
```

## 測試

```
python -m unittest discover -s contracts
python -m unittest discover -s contracts/dashboard
```

## 依據

欄位與流程依合約生命週期管理（CLM）的通行做法設計：合約主檔（對象、類型、期間、續約、金額、狀態）、條款庫與審閱手冊（playbook：公司標準立場、可接受範圍、須升級條件）、義務與續約追蹤。建置時本專案另一份 CLM 做法研究報告尚未取得，因此欄位來源逐欄標示於上表，未引用研究報告內容；取得後應回頭核對欄位與條款類別是否有遺漏。審閱手冊的「參考法條」須由法務核對現行條文。
