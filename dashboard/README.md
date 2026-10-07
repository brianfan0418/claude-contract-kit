# 共用檔案合約系統

人與 Claude／Codex 讀寫同一套共用資料夾檔案。固定網頁直接以 file:// 開啟，不啟動伺服器、不連外部資料服務、不用 CDN 或外部字型。未連接資料夾時顯示唯讀 data.js 快照；按「連接資料夾」選取系統資料夾並授予讀寫權限後，可新增合約、建立案件、編輯欄位與保存進度。

## 瀏覽器與權限

Windows Edge／Chrome 支援 showDirectoryPicker；[MDN 相容資料](https://github.com/mdn/browser-compat-data/blob/main/api/Window.json) 記載 Chrome 86 起支援，Edge 繼承 Chromium。Firefox／Safari 未支援時保留唯讀模式。[MDN secure contexts](https://developer.mozilla.org/en-US/docs/Web/Security/Defenses/Secure_Contexts) 將頂層 file:// 列為安全內容；[WICG 規格](https://wicg.github.io/file-system-access/) 仍要求非 opaque origin、同頂層 origin 與使用者點擊。

本輪 Linux headless Chromium 確認 file:// 的 isSecureContext=true、API 存在；呼叫 picker 回 AbortError，未完成圖形選擇及共用路徑授權。**Windows Edge 實機未測**，尤其 UNC／網路磁碟存取與權限記住，正式使用前需實測。

依 [Chrome 官方指南](https://developer.chrome.com/docs/capabilities/web-apis/file-system-access)，directory handle 存入 IndexedDB；啟動時 queryPermission，已授權才載入。權限失效時按「重新授權資料夾」，在點擊事件中 requestPermission。IndexedDB 保存失敗不阻止當次連接，下次重新選資料夾。沒有把合約資料假寫入 localStorage。

企業政策可能阻擋 API。IT 可檢查 [Edge read guard](https://learn.microsoft.com/en-us/deployedge/microsoft-edge-policies/defaultfilesystemreadguardsetting) 與 [write guard](https://learn.microsoft.com/en-us/deployedge/microsoft-edge-policies/defaultfilesystemwriteguardsetting)：3 為可詢問授權，2 為禁止。由公司決定是否允許，不使用停用瀏覽器安全性的旗標；無法授權時仍可讀快照並由 AI 更新來源。

## 檔案格式

| 路徑 | 用途 |
|---|---|
| 原檔/ | 原合約及各附件版本，唯讀保留 |
| md/*.md | 合約主檔與文字；頂層 YAML frontmatter 使用 schema name |
| cases/案號/index.md | 案件欄位，含 case_id；新案號自動生成 |
| cases/案號/log/時間-處理人-UUID.md | 每次事件一個新檔；frontmatter 含 time、user、action、from_stage、to_stage、attachment_version，內文為處理意見 |
| 收件匣/ | AI 登錄來信附件的輔助管道 |
| 面板/ | 固定前端與 data/data.js 快照 |

每筆進度只新增檔案，不覆寫舊紀錄；修正另加一筆。狀態由按時間排序的事件推導，保存退回與多輪協商。同時從相同舊狀態推進的事件會標示衝突，交由人／AI 核對。主檔更新先比對 getFile 的 lastModified 與原內容，開啟 writable 後再次比對；已改過時拒絕寫入並提示重新載入。

此為樂觀衝突檢查，參考 [Microsoft EF Core optimistic concurrency](https://learn.microsoft.com/en-us/ef/core/saving/concurrency)。File System Access 沒有跨電腦的原子 compare-and-swap；檢查與寫入之間的競爭仍可能發生，不能宣稱具有資料庫交易保證。同一主檔同時多人修改仍應協調。事件檔使用時間＋UUID 分散寫入，參考 [事件資料追加模式](https://learn.microsoft.com/en-us/azure/architecture/patterns/event-sourcing)；本案不使用 Azure 服務。

人與 AI 都使用相同格式。AI 以 Git 提交來源與快照，保存 author、時間與差異；處理人與 Git 寫入者分別記錄。網頁寫入後由 AI 核對差異再 commit，不在網頁假設已執行 Git。公司管理權限與備份；Git 不等於防竄改儲存。

## 重建快照與驗證

從 repo 根目錄執行，Python 3 標準函式庫；寫入模擬測試另需 Node：

```sh
python3 dashboard/build_dashboard.py --register dashboard/sample_register.csv --out dashboard/app/data/data.js
python3 dashboard/build_dashboard.py --md-dir /path/to/md --cases-dir /path/to/cases --out /path/to/面板/data/data.js --logo /path/to/logo.png
python3 -m unittest discover -s dashboard
node dashboard/test_datasource.js
```

CSV／Markdown 可擇一或合併；重複編號拒絕。--fields 預設 repo schema；--today 固定到期計算基準。缺欄位留白，內部 IMPORT 編號不填入原合約編號。--logo 才內嵌 PNG／JPEG／GIF／WebP，公開範例不含公司 logo。生成失敗保留前次快照；成功置換 data.js，外框不重建。

Frontmatter 支援頂層 scalar、JSON 引號字串、單行 JSON、兩空格的 literal／folded block；不是完整 YAML parser，巢狀 YAML 請用單行 JSON。舊版每案單一 Markdown＋JSONL 可重建快照，但連接資料夾編輯使用上表的新格式。

## 介面與手機

Fluent 2 Body 1 14px／20px、Subtitle 2 16px／22px、官方亮暗 alias tokens。字級 100／125／150／200%；明暗、字級、側欄／抽屜寬度以 localStorage 記住，讀寫 try/catch。側欄 180～480px（預設 240）、抽屜 360～1100px（預設 620），另受視窗限制；拖曳、方向鍵、Home／End、Enter／雙擊還原。手機採可開關導覽。

手機寬度支援 390px；手機存取共用資料需公司內網常開的 HTTPS 網頁主機，例如 NAS，為後續選項。一般內網 HTTP 不屬 secure context，不能假定資料夾寫入可用；桌面 file:// 是本次使用方式。

唯一視覺依據 [Fluent 2](https://fluent2.microsoft.design/)，原生 HTML 實作而非官方 React 元件。[System Icons](https://github.com/microsoft/fluentui-system-icons) SVG 內嵌，MIT 授權在 app/fluent-icons.LICENSE。分隔語意依 [WAI-ARIA Window Splitter](https://www.w3.org/WAI/ARIA/apg/patterns/windowsplitter/)。流程參考 [Ironclad](https://developer.ironcladapp.com/reference/webhooks)、[DocuSign CLM](https://www.docusign.com/blog/how-does-docusign-clm-work)；人可讀日誌借用 [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) 概念，檔案格式由本案定義。

偏好設定仍以 localStorage 保存；file:// 的儲存行為由瀏覽器決定，另以 history.state 作同一分頁重新整理的備援，兩者均捕捉存取錯誤。跨瀏覽器、關閉分頁後的保留需在 Windows Edge 實測。依據：[MDN localStorage](https://developer.mozilla.org/en-US/docs/Web/API/Window/localStorage)。

## 按條號線上審閱

案件明細新增「審閱」分頁：上一輪／本輪條款依 id 對應，以最長共同子序列只標必要增刪（刪除線／底線，使用中性色）。長於一百萬個比較格的條款改用共同前綴／後綴，以限制瀏覽器記憶體。留言串顯示處理人、時間、待處理／已解決；可只看未解決，連接資料夾後可留言、回覆、解決及重新開啟。瀏覽器不直接改合約文字，條款新版本由 AI 匯入或建立；沒有自動接受建議。

| 檔案 | 格式 |
|---|---|
| cases/案號/review/versions/V1.md | version_id；clauses 單行 JSON 陣列，每條含唯一 id、title、text；只新增，舊版本不改 |
| cases/案號/review/comments/時間-UUID.md | id、thread_id、version_id、clause_id、user、含時區 time、action、selector；內文為留言 |

留言 action 為 comment／resolve／reopen。首筆 thread_id=id；後續同串維持版本、條號及 selector。selector 含 type=TextQuoteSelector、exact、prefix、suffix，錨定不可變版本的原文。新增留言前比對最新版本，變動時拒寫；每個事件只新增新檔。多人的解決／重新開啟以時間順序重播；這仍不是跨電腦交易鎖。非法錨點或缺少串首筆拒收，快照生成失敗保留原快照。

AI 與人同用這套格式；AI（Codex、Claude 皆可）轉檔、抽欄位、審閱、比對，預設交 Codex 執行以控制費用，驗收由另一個對話執行。

Word 修訂稿匯入需本機 Pandoc（不連外）：

```sh
python3 dashboard/import_review.py /path/to/revised.docx --case-dir /path/to/cases/CASE-001 --previous V1 --current V2
python3 dashboard/build_dashboard.py --md-dir /path/to/md --cases-dir /path/to/cases --out /path/to/面板/data/data.js --settings /path/to/設定/組織與核決.json
```

匯入器實際執行 pandoc --track-changes=all -t json，分成修訂前／後文字與 Word 註解，保留修訂作者與時間；不覆寫既有版本。支援段落、條號標題、清單與表格內段落；複雜圖形、未知 inline 或跨條號註解無法保證錨定，拒收並核對原稿。匯入不是 Word 排版重現，須以另一個對話對照原文驗收。原始 DOCX 保留唯讀。

--settings 可加入私人 organization（units: id／name／path；people: name／unit）與 approvalAuthority（rules: department／text／source；caveat）。表單部門與處理人使用下拉選單；核准步驟附來源提示。設定只在提供參數時納入快照，公開 repo 不含真實組織或核決資料；不得將歷史公告當作目前有效授權。

成熟依據：[GitHub PR 審閱](https://docs.github.com/en/pull-requests/how-tos/review-pull-requests/commenting-on-a-pull-request)、[Google 建議](https://support.google.com/docs/answer/6033474)、[W3C TextQuoteSelector](https://www.w3.org/TR/annotation-model/#text-quote-selector)、[Pandoc track-changes](https://pandoc.org/MANUAL.html#option--track-changes)、[WAI-ARIA 分頁](https://www.w3.org/WAI/ARIA/apg/patterns/tabs/)。本格式借用錨點概念，不宣稱完整 JSON-LD 標準相容。Windows Edge 實機仍未測。
