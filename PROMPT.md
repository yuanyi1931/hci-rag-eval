# HCI RAG Evaluation — 專案實作 Prompt

> 這份文件是給 Claude Code 讀的專案規格書。使用方式:在 `hci-rag-eval` 資料夾裡打開 Claude Code,輸入「請讀取 PROMPT.md 並照裡面的規劃建立專案,先從 Phase 0 開始」。

---

## 0. 專案定位(請先讀這段)

這個專案的目的**不是**做出一個好用的 RAG 產品,而是要回答一個研究問題:

> **當檢索品質變化時,LLM 生成內容的正確性(validity)、一致性(reliability)與可行動性(actionability)會如何跟著變化?**

因此:
- 檢索的部分刻意做得簡單(embedding + cosine similarity),不需要 reranking、hybrid search、query expansion 等進階技巧
- **評估的部分才是重點**,要做得紮實、方法論說得清楚、統計上站得住腳
- 所有評估指標都必須可重現(固定隨機種子、記錄所有參數、保存原始輸出)

如果在實作過程中需要取捨,請一律優先保證評估層的嚴謹度,而不是檢索層的效能。

---

## 1. 技術棧與環境

- Python 3.10+
- `sentence-transformers`(embedding,預設模型 `all-MiniLM-L6-v2`)
- `numpy` / `pandas`(向量運算與資料整理)
- `anthropic`(LLM 呼叫,預設模型 `claude-sonnet-4-6`)
- `scipy` / `statsmodels`(統計檢定與相關係數)
- `matplotlib`(繪圖,不需要 seaborn)
- `python-dotenv`(讀取 API key)
- `pyyaml`(讀取 config)

**環境設定:**
- API key 放在專案根目錄的 `.env`,格式 `ANTHROPIC_API_KEY=sk-ant-...`
- 一定要建立 `.gitignore`,至少排除 `.env`、`data/`、`__pycache__/`、`outputs/*.json`、`.venv/`
- 產生 `requirements.txt`,版本號用 `>=` 不要鎖死

---

## 2. 專案結構

```
hci-rag-eval/
├── README.md                    # 安裝、執行方式、預期耗時與成本
├── PROMPT.md                    # 本檔案
├── requirements.txt
├── config.yaml                  # 所有可調參數集中在這裡
├── .env.example                 # 範本,不含真實 key
├── .gitignore
├── main.py                      # 一次跑完整個 pipeline 的入口
├── data/
│   ├── raw/abstracts.jsonl      # 抓下來的原始摘要
│   ├── embeddings.npy           # 向量矩陣
│   ├── embeddings_index.json    # 向量順序對應的 paper id
│   └── cache/                   # LLM 回應快取(見 §7)
├── src/
│   ├── __init__.py
│   ├── config.py                # 讀取 config.yaml,提供型別安全的存取
│   ├── fetch_data.py
│   ├── embed.py
│   ├── retrieve.py
│   ├── generate.py
│   ├── llm_client.py            # 統一的 API 呼叫層(重試、快取、計數)
│   ├── evaluate_validity.py
│   ├── evaluate_reliability.py
│   ├── evaluate_actionability.py
│   ├── stats.py                 # ICC、Krippendorff's alpha 等統計工具
│   └── report.py
├── notebooks/
│   └── analysis.ipynb
├── tests/
│   └── test_stats.py            # 統計函式的單元測試(見 §8)
└── outputs/
    ├── generations.jsonl        # 每次生成的原始輸出(含 metadata)
    ├── results.csv              # 彙整後的每個 query 一列
    ├── figures/
    └── report.md
```

---

## 3. 分階段執行(重要:請照順序做,每個 Phase 結束後停下來讓我確認)

### Phase 0 — 骨架與設定
建立資料夾結構、`config.yaml`、`.env.example`、`.gitignore`、`requirements.txt`、`README.md` 草稿。此階段**不呼叫任何 API**。完成後告訴我如何安裝環境,並等我確認。

### Phase 1 — 資料與檢索(不含 LLM)
實作 `fetch_data.py`、`embed.py`、`retrieve.py`。跑完後給我看:
- 抓到幾篇摘要、日期範圍
- 隨機挑 3 個 query 的 top-5 檢索結果(標題 + similarity 分數),讓我肉眼判斷檢索是否合理

此階段**仍然不呼叫 LLM API**。確認檢索結果合理後再進入下一階段。

### Phase 2 — 最小可行生成(Smoke Test)
用 **3 個 query × 3 次重跑 = 9 次 API 呼叫**跑通生成流程,確認:
- 結構化輸出(JSON)能穩定解析
- 快取機制正常運作
- 錯誤處理與重試會被觸發時能正常恢復

把 9 次的原始輸出印給我看,確認格式沒問題再繼續。

### Phase 3 — 評估模組
逐一實作三個評估模組,每個都先在 Phase 2 的 9 筆資料上驗證,再擴大規模。

### Phase 4 — 完整實驗
用 config 裡設定的完整規模跑一次(預設 20 query × 5 次重跑),產出 `results.csv`。

### Phase 5 — 報告
產出圖表與 `report.md`。

---

## 4. 各模組規格

### 4.1 資料收集 `fetch_data.py`
- 用 arXiv API 抓 `cs.HC` 分類論文,預設 500 篇(config 可調)
- 保留欄位:`arxiv_id`, `title`, `abstract`, `published`, `categories`, `authors`
- 過濾掉 abstract 少於 100 字的項目
- 存成 `data/raw/abstracts.jsonl`,一行一筆
- **必須做斷點續傳**:如果檔案已存在且筆數足夠,直接跳過不重抓
- arXiv API 有 rate limit,每次請求之間 sleep 3 秒

### 4.2 Embedding `embed.py`
- 用 `sentence-transformers` 對 abstract 編碼
- 向量存 `data/embeddings.npy`(shape: `[n_docs, dim]`),對應的 id 順序存 `embeddings_index.json`
- 向量做 L2 normalize,這樣 cosine similarity 就等於內積,計算更快
- 如果 `.npy` 已存在且筆數對得上,直接載入不重算

### 4.3 檢索 `retrieve.py`
- `retrieve(query: str, k: int) -> list[dict]`,回傳 top-k 文件與其 similarity 分數
- **同時回傳檢索品質指標**,後續分析要用:
  - `mean_sim`:top-k 的平均相似度
  - `max_sim`:最高相似度
  - `sim_gap`:top-1 與 top-k 的相似度差距(檢索結果是否集中)
- Query 的來源有兩種,config 可切換:
  1. `held_out`:從語料庫中隨機抽出一批論文當 query,並把它們從檢索池中排除(避免檢索到自己)
  2. `manual`:我手動寫的主題句(例如 "How do users build trust in AI-assisted decision making?"),放在 `config.yaml` 的 `manual_queries` 清單裡
- 預設用 `manual`,並在 config 裡預填 10 個 HCI 領域的主題句當作起點

### 4.4 生成 `generate.py`

**Prompt 設計:**把 top-k 摘要組成 context,要求 LLM 統整出洞察。輸出必須是嚴格 JSON:

```json
{
  "insights": [
    {
      "claim": "一句話的洞察陳述",
      "supporting_paper_ids": ["arxiv_id_1", "arxiv_id_2"],
      "reasoning": "為什麼從這些論文可以得出這個結論"
    }
  ],
  "overall_confidence": 0.0
}
```

- 要求生成 **3~5 個 insight**,數量固定才好做跨次比較
- `supporting_paper_ids` 只能從提供的 context 裡挑,這是後續 grounding 檢查的基礎
- 解析失敗時要重試(最多 3 次),仍失敗就記錄下來標記為 `parse_failure`,不要讓整個 pipeline 中斷

**重跑機制(reliability 的基礎):**
- 對同一 query、同一 prompt、同一 temperature,重複呼叫 N 次(預設 5,config 可調)
- 每次呼叫都存進 `outputs/generations.jsonl`,包含 metadata:`query_id`, `run_index`, `model`, `temperature`, `timestamp`, `raw_response`, `parsed_json`, `token_usage`
- Temperature 預設 0.7,但 config 要能設成多個值(例如 `[0.0, 0.7, 1.0]`),之後可以做「temperature 對一致性的影響」這個延伸分析

### 4.5 Validity 評估 `evaluate_validity.py`

目標:量化生成內容有多少比例真的有原文依據。

**做法(兩層):**

**第一層 — Citation validity(便宜、確定性高):**
檢查 `supporting_paper_ids` 裡的每個 id 是否真的出現在該次的 top-k context 裡。算出 `citation_validity_rate`(合法引用數 / 總引用數)。這一層不需要 API,純程式判斷,可以做為 hallucination 的第一道檢查。

**第二層 — Claim grounding(需要 LLM judge):**
對每個 `claim`,搭配它宣稱的支持文獻原文,問一個獨立的 LLM judge:

> 這段摘要內容是否**支持(entailed)**、**不支持(not entailed)**、還是**矛盾(contradicted)**這個聲稱?

- Judge 用**乾淨的 prompt**,不要透露這是誰生成的,也不要給它其他 context
- Judge 的 temperature 設 0,追求判斷穩定
- 每個 claim 判斷 **3 次**,取多數決,同時記錄 judge 自己的一致性(這本身也是一個有意思的數字)
- 輸出 `grounding_rate` = entailed claims / total claims

**保留人工標注介面:**輸出一份 `outputs/validity_for_human_review.csv`,欄位包含 `claim`, `supporting_abstract`, `llm_judgment`, `human_judgment`(留空)。我會手動標注 30~50 筆,之後計算 LLM judge 與人類判斷的 **Cohen's kappa**,用來驗證 LLM-as-judge 的可信度。這一步對委員會來說很重要,不要省略。

### 4.6 Reliability 評估 `evaluate_reliability.py`

目標:同一個 prompt 跑 N 次,結果差多少。

**三個層次的指標,都要算:**

1. **語意層 — Semantic consistency**
   - 把每次生成的所有 claim 串成一段文字,做 embedding
   - 計算 N 次結果兩兩之間的 cosine similarity,取平均值
   - 這是最直觀的「講的是不是同一件事」

2. **內容層 — Claim overlap**
   - 把不同次生成的 claim 兩兩配對,如果 embedding similarity > 閾值(預設 0.8)就視為「同一個 claim」
   - 計算 **Jaccard similarity**:N 次結果之間平均有多少比例的 claim 是共通的
   - 這比純語意相似度更嚴格,能抓到「大方向一樣但細節每次都不同」的情況

3. **數值層 — Numeric agreement**
   - 對 `overall_confidence` 這類連續分數,計算 N 次之間的 **ICC(2,1)**(intraclass correlation, two-way random effects, single measure)
   - 對 citation 的選擇(哪些 paper 被引用)這類類別型判斷,計算 **Krippendorff's alpha**(nominal level)

**統計實作要求:**
- ICC 和 Krippendorff's alpha 請寫在 `src/stats.py`,**不要直接呼叫黑箱套件就算了**,要在函式的 docstring 裡寫清楚:公式是什麼、用的是哪個變體(ICC 有六種)、參考文獻是誰(ICC 用 Shrout & Fleiss 1979;Krippendorff's alpha 用 Krippendorff 2004)
- 這些函式必須有單元測試(見 §8),因為之後我要在 CV 和面試裡解釋這部分,不能出錯

### 4.7 Actionability 評估 `evaluate_actionability.py`

**Rubric(1–5 分,寫在 config 裡方便調整):**

| 分數 | 定義 |
|---|---|
| 1 | 純描述性,只是重述論文在做什麼,無法據此採取任何行動 |
| 2 | 指出一個籠統的方向,但沒有具體到可以規劃 |
| 3 | 指出一個可辨識的研究缺口或設計方向,但仍需大量補充才能執行 |
| 4 | 具體到可以轉化成一個研究問題或設計決策,只需少量細化 |
| 5 | 具體到可以直接寫成研究設計、實驗方案或產品規格 |

- 用 LLM-as-judge 對每個 insight 打分,**要求它同時輸出理由**(理由本身之後可以放進報告當質性佐證)
- Judge temperature 設 0,每個 insight 評 3 次取中位數
- 一樣輸出 `outputs/actionability_for_human_review.csv` 給我手動標注,之後算 LLM 與人類評分的 **Spearman correlation**(順序型資料用 Spearman 比 Pearson 合適)

### 4.8 報告 `report.py`

**輸出 `outputs/results.csv`,每個 query 一列,欄位包含:**
`query_id`, `query_text`, `mean_sim`, `max_sim`, `sim_gap`, `citation_validity_rate`, `grounding_rate`, `semantic_consistency`, `claim_jaccard`, `confidence_sd`, `confidence_cv`, `krippendorff_alpha`, `actionability_mean`, `n_runs`, `n_parse_failures`

**實驗層級的 ICC:**
- 不能在單一 query 上計算 ICC(2,1),因為該情境下只有一個 item, between-item variance 為 0。
- 若要做跨-query 的一致性分析,應該建立矩陣 `rows = query_id`, `columns = run_index`,然後呼叫 `evaluate_confidence_icc()`。
- 這個 ICC 只用於整體實驗設計,不是用於單一 query 的風險報告。

**圖表(存進 `outputs/figures/`):**
1. 散佈圖:`mean_sim` vs `grounding_rate`,附上迴歸線與 Pearson r
2. 散佈圖:`mean_sim` vs `semantic_consistency`
3. 箱型圖:不同 temperature 下的 `semantic_consistency` 分布(如果有跑多個 temperature)
4. 長條圖:actionability 分數分布

**`report.md` 內容:**
- 方法摘要(資料來源、模型、參數、樣本數)
- 主要發現,每個發現都要附上具體數字與統計檢定結果(相關係數 + p 值 + 樣本數)
- **限制與威脅到效度的因素**:樣本數小、單一 LLM、單一領域、LLM-as-judge 本身的偏誤等。這段要誠實寫,不要美化——委員會反而會欣賞這點
- 後續可延伸的方向

---

## 5. Config 設計

`config.yaml` 要涵蓋所有可調參數,程式裡不要出現 magic number:

```yaml
data:
  arxiv_category: "cs.HC"
  n_papers: 500
  min_abstract_length: 100

embedding:
  model: "all-MiniLM-L6-v2"

retrieval:
  top_k: 5
  query_mode: "manual"        # manual | held_out
  manual_queries:
    - "How do users build and calibrate trust in AI-assisted decision making?"
    - "..."                    # 預填 10 個

generation:
  model: "claude-sonnet-4-6"
  temperatures: [0.7]
  n_runs: 5
  n_insights: 4
  max_tokens: 2000

evaluation:
  judge_model: "claude-sonnet-4-6"
  judge_temperature: 0.0
  judge_n_votes: 3
  claim_match_threshold: 0.8

budget:
  max_api_calls: 500           # 硬上限,超過就停止並警告
  
runtime:
  random_seed: 42
  cache_enabled: true
```

---

## 6. 成本控制(請務必實作)

這是我自己付費的專案,API 額度有限。請做到:

- `llm_client.py` 要有一個**全域呼叫計數器**,每次呼叫都累加,超過 `budget.max_api_calls` 就丟出例外中止,並印出目前用了多少
- 每次執行結束時印出:總呼叫次數、總 input/output tokens、依照公開定價估算的花費
- **快取是必須的**:用 `(model, prompt, temperature, run_index)` 的 hash 當 key,把回應存在 `data/cache/`。重跑 pipeline 時如果參數沒變就直接讀快取,不重複付費
- 注意 reliability 分析需要「同參數但不同結果」的多次呼叫,所以快取的 key 一定要包含 `run_index`,不能把 5 次重跑都快取成同一筆
- 在 README 裡估算完整跑一次大概要多少次呼叫、多少錢、多久

---

## 7. 錯誤處理

- API 呼叫用 exponential backoff 重試(最多 5 次),針對 rate limit 和暫時性錯誤
- JSON 解析失敗要記錄原始回應,標記 `parse_failure`,不中斷 pipeline
- 每個階段的中繼結果都要落地存檔,任何一步掛掉都能從上一步接著跑,不用整個重來
- Log 用 Python 的 `logging`,同時輸出到 console 和 `outputs/run.log`

---

## 8. 測試

`tests/test_stats.py` 至少要涵蓋:
- ICC:用一組已知答案的小資料(可以從 Shrout & Fleiss 論文或任何統計教科書的範例取),驗證算出來的值正確
- Krippendorff's alpha:用完全一致的資料應該得到 1.0,完全隨機的資料應該接近 0
- Jaccard similarity:手算幾個簡單案例驗證
- Cohen's kappa:同上

這些測試很重要,因為統計實作出錯的話整份報告的結論都不能用。

---

## 9. README 要寫什麼

- 一段話說明專案在回答什麼問題
- 安裝步驟(venv、requirements、.env)
- 分階段執行方式(每個 Phase 的指令)
- 預期耗時與 API 成本估算
- 結果檔案說明
- **方法論簡述**:每個評估指標是什麼、怎麼算的、為什麼選這個指標。這段之後我會直接改寫進申請文件,請寫得清楚一點

---

## 10. 開始之前請先跟我確認

1. 你打算怎麼設定 API key,我需要先做什麼?
2. Phase 1 的 500 篇、Phase 4 的 20 query × 5 runs 這個規模你覺得合理嗎?有沒有建議調整?
3. `src/stats.py` 裡的 ICC 和 Krippendorff's alpha,你打算自己實作還是用套件?(我傾向自己實作核心邏輯 + 用套件交叉驗證,這樣我能解釋清楚)

確認完就從 **Phase 0** 開始,做完停下來讓我檢查。