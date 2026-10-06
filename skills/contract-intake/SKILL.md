---
name: contract-intake
description: 讀一份合約（PDF、Word、掃描檔），抽出合約主檔欄位與章節目錄，每個欄位附原文出處，經獨立驗證與使用者確認後才寫入主檔。使用者要登錄、整理、建檔、盤點合約時使用。
---

# 合約登錄（contract-intake）

目標：把一份合約變成可驗證的主檔資料。結論正確性優先於速度；任何一個欄位都不憑印象、不推測、不補常識。

## 不可違反的規則

1. 只從合約原文抽取。原文沒有的欄位寫「未載明」（日期、數字、字串欄位留空，列舉欄位選「未載明」），不由其他欄位或慣例推算。需要推算的值（例如通知截止日）不寫入主檔，由面板計算。
2. 每個由原文抽取且有值的欄位附 `citations`：檔案（`source_path`）、頁碼或條號、逐字引句（從原文複製，不改寫、不省略號、不翻譯）。Word 等無固定頁碼來源以原文條號定位，`page` 可為空；每筆須有頁碼或條號。有頁碼者該頁須有頁標記，引句須逐字出現在該頁；無頁碼者引句須逐字出現在內文，並回原檔核對條號。
3. 原始合約檔唯讀，不改名、不移動、不覆寫。Markdown 與主檔都是可重新產生的衍生資料。
4. 驗證由另一個不帶前情的對話執行；抽取者不得自行驗證自己的結果。驗證不符的項目不得寫入主檔。
5. 寫入主檔前須取得使用者確認。

## 步驟

1. **轉成 Markdown**：先用 `doc-library` skill 把原檔轉成 Markdown。PDF 輸出每頁開頭有 `<!-- page: N -->` 標記；後續頁碼以這些標記為準。Word 等無固定頁碼者以原文條號定位，不自編頁碼。掃描檔（`ocr` 為 true）的文字可能有辨識錯誤，關鍵欄位（日期、金額、對象名稱、期間）須對照該頁影像再引用，並在 `notes` 註明。轉換失敗、PDF 缺頁或頁標記不連續時停止，向使用者回報，不繼續抽取。
2. **建立章節目錄**：依原文標題列出條號與標題，格式 `第N條 標題`，以 ` | ` 串接，寫入 `toc`。原文沒有條號者以其標題原文為準，不自編條號。每個章節附一筆 citations（`field` 為 `toc`），引句取標題原文。
3. **抽取欄位**：依 `<工具包資料夾>/contracts/schema/fields.json` 逐欄處理。`from_text` 為 true 的欄位須附 citations；`from_text` 為 false 的欄位（承辦部門、承辦人、合約類型、對象類別、狀態、合約編號、備註等）不由原文判斷，向使用者詢問或留空。列舉欄位只能填 `fields.json` 中該列舉的 label。`title` 驗證前保留檔名預填值，先記錄支持原文正式名稱的 `citations`，由步驟 7 核對後覆寫同一鍵。日期一律 `YYYY-MM-DD`；原文為民國年者，轉換後在 citations 的 quote 保留民國年原文。
4. **整理關鍵條款摘要**：`key_clauses` 以 `第N條：摘要` 書寫，摘要只複述原文所載事實，每項附 citations。手冊涵蓋的條款類型（期間與續約、終止、付款、責任上限、賠償、保密、智慧財產、個資、準據法與管轄、不可抗力、轉讓）逐一檢查：有則摘要，全文找不到則在 `notes` 寫「全文未見○○條款」並註明搜尋用語。
5. **寫入 Markdown frontmatter**：更新轉換後 Markdown 既有的 YAML frontmatter，格式見 `<工具包資料夾>/contracts/build_register.py` 的說明；內文原樣保留不修改。frontmatter 含：
   - `fields.json` 的所有欄位（欄位名稱一致）。`title` 沿用轉檔的同一鍵，核對原文並完成驗證後覆寫，不新增第二個 `title`。
   - `source_path`、`source_sha256`、`source_modified`、`converter`、`converted_at`、`pages`、`ocr`、`ocr_engine`、`ocr_pages`：沿用 doc-library 輸出者，不自行編造；缺少時回報使用者。
   - `verification_status: "未驗證"`。
   - `citations`：每行一筆單行 JSON，`{"field":"end_date","file":"<source_path>","page":3,"clause":"第5條","quote":"逐字引句"}`。同一欄位有多個依據時寫多筆。無固定頁碼例：`{"field":"end_date","page":null,"clause":"第5條","quote":"逐字引句"}`。
6. **機械檢查**：執行 `python "<工具包資料夾>/contracts/build_register.py" --md-dir <md 資料夾> --out <暫存 csv> --allow-unverified`，重轉文件若 `needs_review: true`，先完成步驟 7 的新版原文驗證，驗證成功後解除旗標，再重跑本步驟。確認沒有「quote 不在原文中」「有值但沒有 citations」等錯誤；有錯誤先修正再繼續。
7. **獨立驗證**：開一個不帶前情的新對話（或不帶前情的 subagent），只給它轉換後的 Markdown 路徑、可讀取的原檔路徑與下方「驗證交辦」，不給抽取過程的推理。驗證者更新 `verification_status`、`verified_at`、`verifier_note`；全部相符後將 `needs_review` 設為 false。`title` 確認相符後以原文正式名稱覆寫原鍵，其餘欄位值與 `citations` 不改。結果為「驗證不符」的欄位，回到步驟 3 修正後重驗；無法修正者改填「未載明」並在 `notes` 說明。
8. **使用者確認**：給使用者一張逐欄表：欄位、值、頁碼、條號、引句、驗證結果；`未載明` 欄位單獨列出。使用者確認後才執行：`python "<工具包資料夾>/contracts/build_register.py" --md-dir <md 資料夾> --out <主檔 register.csv>`（只寫入 `verification_status` 為「已驗證」且 `needs_review` 不為 true 者）。
9. 回報寫入筆數與被擋下的清單；不要手動編輯 `register.csv`。

## 驗證交辦（交給不帶前情的對話）

> 你是合約抽取結果的驗證者。檔案：`<md 路徑>`；原檔：`<原檔路徑>`。逐一檢查 frontmatter 的 `citations`：(1) 每筆須有頁碼或條號：有 `page` 者，`quote` 須逐字出現在該頁頁標記之後、下一個標記之前；無固定頁碼者 `page` 可空，但須有 `clause` 原文條號，引句逐字出現在內文且回原檔核對該條；(2) 該欄位的值是否被這段引句直接支持，沒有多出引句沒有的內容；`title` 若仍為檔名預填值，核對引句與原文正式名稱後覆寫該鍵，再判定相符；(3) 有值但沒有 citations 的欄位；(4) 原文有載明但被填為「未載明」的欄位（自行在全文搜尋）；(5) `ocr` 為 true 時，關鍵欄位對照該頁影像。驗證完成後可將檔名預填的 `title` 覆寫為核對過的原文正式名稱；其餘欄位值與內文不修改。輸出每筆 citations 的「相符／不符／無法判斷」與理由，最後把 `verification_status` 設為「已驗證」（全部相符）、確認不符時設為「驗證不符」、無法對照原檔或 OCR 影像時維持「未驗證」。全部相符後才將 `needs_review` 設為 false，並填 `verified_at` 與 `verifier_note`。AI 的驗證不取代人工覆核。

## 輸出給使用者的語氣

只報告原文所載與驗證結果；不寫「應該」「通常」「大概」。無法確定處寫「無法確認」並說明缺什麼。
