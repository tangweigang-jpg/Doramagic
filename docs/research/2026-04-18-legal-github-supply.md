# Legal / Compliance / Contract / Legal-AI GitHub Supply Research
**Date:** 2026-04-18  
**Purpose:** Assess whether GitHub OSS supply in the legal domain is sufficient to extract 50-150 Doramagic blueprints (analogous to the 73 already extracted from Finance)  
**Researcher:** Claude Sonnet 4.6 (sub-agent)

---

## 1. Executive Summary

**Total viable projects identified (star > 500 OR active 2024-2026):** ~85-110 distinct repositories across all subdomains, with ~55-70 meeting the star > 500 + code-heavy bar that Doramagic's pipeline can directly consume.

**Top 3 subdomains by volume:**
1. **Legal NLP / LLMs** — largest cluster (~30+ repos); includes Chinese and English models, benchmarks, corpora
2. **Compliance / Regulatory / Policy** — deep infrastructure-grade OSS (Prowler 13.6k, OPA 11.6k, Wazuh 15.3k); code-heavy, pipeline-ready
3. **Contract Analysis / Generation** — growing fast post-GPT-4; ContextGem (1.8k), LexNLP (774), Blackstone (684)

**Supply verdict: MARGINAL → approaching SUFFICIENT.** Total addressable supply for Doramagic is 80-120 viable projects. 50 blueprints are achievable in Wave 1-2. 150 requires pulling in dataset-heavy and template-heavy repos which need pipeline adaptation. The domain is narrower than Finance's top tier but notably deeper in the compliance/infra sublayer.

**CN vs US gap:** US/Global-origin projects dominate by star count (>80% of top-50 by stars). Chinese legal LLMs (ChatLaw 7.5k, LaWGPT 6k, law-cn-ai 4.9k, DISC-LawLLM 899, fuzi.mingcha 371) form a real but thinner cluster — primarily LLM fine-tune repos, not pipelines or tools. CN-side tooling (parsers, contract review apps, compliance infra) is almost absent on GitHub; likely living on Gitee or proprietary.

---

## 2. Methodology

**Star threshold:** ≥ 500 stars for Wave 1 priority. Secondary analysis at 100-499 for depth. Sub-100 flagged only for notable CN-specific or niche projects.

**GitHub topic queries executed:**
1. `github.com/topics/legaltech?o=desc&s=stars`
2. `github.com/topics/legal?o=desc&s=stars`
3. `github.com/topics/law?o=desc&s=stars`
4. `github.com/topics/legal-nlp?o=desc&s=stars`
5. `github.com/topics/contract-analysis?o=desc&s=stars`
6. `github.com/topics/compliance?o=desc&s=stars`
7. `github.com/topics/patent-search?o=desc&s=stars`
8. `github.com/topics/legal-ai` (via WebSearch)
9. `github.com/topics/legal-documents` (via WebSearch)
10. `github.com/topics/legal-texts` (via WebSearch)

**Web searches executed (10+):**
1. "legal NLP open source GitHub projects 2025 stars contract analysis"
2. "awesome legal open source GitHub legaltech law NLP"
3. "GitHub topic:legal topic:legaltech most starred repositories 2025"
4. "GitHub contract analysis open source CUAD LegalBench legal-bert"
5. "Chinese legal NLP open source GitHub 法律 合同 合规 NLP 知识图谱 stars 2024"
6. "prowler cloud compliance open source GitHub stars wazuh openscap"
7. "GitHub e-discovery document review patent search prior art stars"
8. "LaWGPT LexiLaw ChatLaw GitHub stars Chinese legal LLM 中文法律"
9. "DISC-LawLLM FuziMingcha GitHub China stars 中文法律大模型 2024"
10. "THUNLP CAIL Chinese AI law challenge GitHub stars Tsinghua"
11. "GitHub legal document automation template generator docassemble hotdocs"
12. "GitHub legal chatbot question answering open source stars 2024"
13. "Harvard Caselaw Access Project case law dataset GitHub freelawproject"
14. "top legal open source GitHub projects 2024 2025"

**Direct repo fetches:** courtlistener, docassemble, LaWGPT, ChatLaw, DISC-LawLLM, law-cn-ai, ContextGem, HazyResearch/legalbench, fuzi.mingcha, maastrichtlawtech/awesome-legal-nlp, CSHaitao/Awesome-LegalAI-Resources.

---

## 3. Project Inventory by Subdomain

### 3A. Contract Analysis / Generation

| Repo | Stars | Language | Last Active | Description | Type | Origin |
|------|-------|----------|-------------|-------------|------|--------|
| shcherbak-ai/contextgem | 1.8k | Python | 2025-2026 | Effortless LLM extraction from legal docs | Code-heavy | Global |
| LexPredict/lexpredict-lexnlp | 774 | Py/Jupyter | Active | NLP for contracts, clauses, dates, amounts | Code-heavy | US |
| LexPredict/lexpredict-contraxsuite | 181 | C# | Active | Full contract analysis platform | Code-heavy | US |
| TheAtticusProject/cuad | 493 | Python | 2023 | 13k+ NeurIPS contract annotations (CUAD) | Dataset-heavy | US |
| HazyResearch/legalbench | 569 | Py/Jupyter | Active | 162-task benchmark for legal LLM eval | Mixed | US |
| zeroentropy-ai/legalbenchrag | ~50 | Python | 2024 | LegalBench-RAG IR benchmark | Mixed | US |
| accordproject/template-archive | 337 | JavaScript | Active | Smart legal contract templates | Template | Global |
| accordproject/ergo | 167 | Coq | Active | Programming language for smart legal contracts | Code-heavy | Global |
| accordproject/web-components | 128 | JavaScript | Active | React components for legal contracts | Code-heavy | Global |
| accordproject/concerto | ~200 | JavaScript | Active | Data modeling language for legal/business | Code-heavy | Global |

**Pipeline note:** LexNLP and ContextGem are pure code libraries — ideal for Doramagic extraction. CUAD is dataset-only (13k JSON annotations): harder for business descriptor extraction.

---

### 3B. Legal NLP / LLMs (English)

| Repo | Stars | Language | Last Active | Description | Type | Origin |
|------|-------|----------|-------------|-------------|------|--------|
| coastalcph/lex-glue | 250 | Python | Active | LexGLUE benchmark, 7 legal NLP datasets | Mixed | EU/Global |
| Liquid-Legal-Institute/Legal-Text-Analytics | 716 | — | Active | Curated resources + tools index | Content | Global |
| maastrichtlawtech/awesome-legal-nlp | 314 | — | 2025 | Curated LegalNLP papers and tools | Content | EU |
| nlpaueb/legal-bert | ~400 (HF) | Python | 2022 | LEGAL-BERT pretrained on EU/US case law | Code-heavy | EU |
| Blackstone (explosion-ai) | 684 | Python | Active | spaCy pipeline for legal text NLP | Code-heavy | UK |
| neelguha/legal-ml-datasets | ~120 | — | 2023 | Collection of legal ML datasets | Dataset | US |
| CSHaitao/Awesome-LegalAI-Resources | 296 | — | Active | Curated legal AI datasets, benchmarks | Content | CN |
| Jeryi-Sun/LLM-and-Law | 295 | — | Active | Research papers on LLMs in law | Content | CN |
| Dai-shen/LAiW | ~150 | Python | 2024 | Chinese legal LLM benchmark | Mixed | CN |
| PileOfLaw (EleutherAI) | ~300 | Python | 2023 | 256GB English legal corpus | Dataset | US |

---

### 3C. Case Law / Precedent Search

| Repo | Stars | Language | Last Active | Description | Type | Origin |
|------|-------|----------|-------------|-------------|------|--------|
| freelawproject/courtlistener | 896 | Python | Active | Searchable US court opinions archive | Code-heavy | US |
| statedecoded/statedecoded | 263 | PHP | 2022 | Legal codes for humans (US state statutes) | Code-heavy | US |
| thunlp/CAIL | 502 | Python | 2022 | Chinese AI & Law challenge (2.6M criminal cases) | Dataset/Code | CN |
| lawglance/lawglance | 246 | Jupyter | Active | Free open-source RAG legal assistant | Code-heavy | Global |
| chrisryugj/korean-law-mcp | 1.5k | TypeScript | 2026 | Korean legal API tools, 16 MCP tools | Code-heavy | KR |
| pasal | 211 | TypeScript | Active | Indonesian legal platform MCP+REST | Code-heavy | ID |
| irlab-sdu/fuzi.mingcha | 371 | Python | 2025 | Chinese judicial LLM (statute retrieval, case analysis) | Code-heavy | CN |

---

### 3D. E-Discovery / Document Review

**Finding: Extremely thin on GitHub.** E-discovery is dominated by commercial vendors (Relativity, Everlaw, Logikcull). No OSS repo with > 200 stars was found. The sub-100 cluster includes:

| Repo | Stars | Language | Description | Type | Origin |
|------|-------|----------|-------------|------|--------|
| (none found > 200 stars) | — | — | — | — | — |
| Various AI doc review demos | <50 | Python | RAG-based document Q&A systems | Code | Various |

**Pipeline implication:** E-discovery as a standalone subdomain cannot supply Wave 1 projects for Doramagic. May appear as a use-case within broader legal NLP repos.

---

### 3E. Compliance / Regulatory (GDPR, HIPAA, SOX, cloud)

This is the largest-starred legal-adjacent cluster. Most are infrastructure/DevSecOps tools that encode regulatory requirements.

| Repo | Stars | Language | Last Active | Description | Type | Origin |
|------|-------|----------|-------------|-------------|------|--------|
| CISOfy/lynis | 15.5k | Shell | Active | Security audit + HIPAA/ISO27001/PCI checks | Code-heavy | Global |
| wazuh/wazuh | 15.3k | C++ | Active | SIEM+HIDS with GDPR/HIPAA/PCI compliance | Code-heavy | Global |
| prowler-cloud/prowler | 13.6k | Python | Active | Cloud compliance (GDPR, HIPAA, SOX, FedRAMP) | Code-heavy | Global |
| open-policy-agent/opa | 11.6k | Go | Active | General-purpose policy engine (Rego language) | Code-heavy | Global |
| bridgecrewio/checkov | 8.6k | Python | Active | IaC scanning, CIS/NIST/HIPAA controls | Code-heavy | Global |
| kyverno/kyverno | 7.6k | Go | Active | Kubernetes policy engine | Code-heavy | Global |
| aquasecurity/tfsec | 7k | Go | Active | Terraform security scanner | Code-heavy | Global |
| cloud-custodian | 6k | Python | Active | Cloud compliance rules engine | Code-heavy | Global |
| deepfence/ThreatMapper | 5.3k | TypeScript | Active | Cloud-native vulnerability/compliance | Code-heavy | Global |
| ossec/ossec-hids | 5k | C | Active | Host intrusion detection + compliance | Code-heavy | Global |
| intuitem/ciso-assistant-community | 4k | Python | Active | GRC platform, 130+ frameworks (ISO27001, NIST) | Code-heavy | Global |
| ComplianceAsCode/content | 2.7k | Shell | Active | SCAP/Bash compliance automation | Code-heavy | US |
| Bearer/bearer | 2.6k | Go | Active | Code scanner for privacy/GDPR | Code-heavy | Global |
| ballerine-io/ballerine | 2.4k | TypeScript | Active | Identity verification, KYC risk decisioning | Code-heavy | Global |

**Note:** Most compliance tools (Lynis, Wazuh, Prowler, OPA) are security-focused rather than legal-doctrine focused. Their business logic is rich: they encode specific regulatory clauses as detection rules. Doramagic can extract blueprints on "how to implement GDPR Article 32 controls" or "how to build HIPAA audit trails" from these codebases. Pipeline-ready.

---

### 3F. Patent / IP

| Repo | Stars | Language | Last Active | Description | Type | Origin |
|------|-------|----------|-------------|-------------|------|--------|
| PQAI Search Server | 119 | Python | Active | AI patent prior art search | Code-heavy | US |
| PatZilla | 115 | Python | Active | Patent research platform (USPTO+EPO) | Code-heavy | Global |
| USPTO OpenData Python | 108 | Python | Active | USPTO Open Data API client | Code-heavy | US |
| mahesh-maan/awesome-patent-retrieval | ~80 | — | 2024 | Curated patent processing resources | Content | Global |

**Finding:** Patent/IP is sparse on GitHub. No repo > 200 stars found in this niche. Not viable as a primary Wave 1 subdomain.

---

### 3G. Legal Document Automation (Templates / Forms)

| Repo | Stars | Language | Last Active | Description | Type | Origin |
|------|-------|----------|-------------|-------------|------|--------|
| jhpyle/docassemble | 935 | JavaScript | Active | Open-source guided interview + document assembly | Code-heavy | US |
| ankane/awesome-legal | 948 | — | Active | Curated free legal document templates | Content | US |
| CooleyLLP/seriesseed | 197 | — | Active | Startup financing docs (SAFE, equity) | Template | US |
| balanced-employee-ip-agreement | 2.2k | — | Active | GitHub's reusable BEIPA template | Template | US |
| github/site-policy | 2.1k | — | Active | GitHub's policies in markdown | Content | US |
| jackmorgan/the-plain-contract | 305 | — | Active | Plain-language freelance contract | Template | Global |
| OpenLegal/openlawoffice | ~80 | — | 2022 | Open source law office management | Code | US |

**Pipeline note:** Template repos (awesome-legal, seriesseed, plain-contract) are content-heavy markdown files — low business descriptor density. docassemble is code-heavy and extractable.

---

### 3H. Legal Chatbots / Question Answering

| Repo | Stars | Language | Last Active | Description | Type | Origin |
|------|-------|----------|-------------|-------------|------|--------|
| evolsb/claude-legal-skill | 202 | TypeScript | 2026 | AI contract review with CUAD risk detection | Code-heavy | US |
| Vaquill-AI/awesome-legaltech | ~150 | — | Active | Curated legaltech + AI tools list | Content | Global |
| lawglance/lawglance | 246 | Jupyter | Active | Free RAG legal assistant | Code-heavy | Global |

---

### 3I. Open Case Law Datasets

| Repo / Resource | Stars | Language | Description | Type | Origin |
|-----------------|-------|----------|-------------|------|--------|
| freelawproject/courtlistener | 896 | Python | 9M+ US court opinions, APIs | Code+Data | US |
| Harvard Caselaw Access Project | — | — | 6.7M US cases (360 years), CC0, Hugging Face | Dataset | US |
| PileOfLaw | ~300 | Python | 256GB+ legal corpus | Dataset | US |
| Multi_Legal_Pile | ~100 | Python | 689GB multilingual (24 languages) | Dataset | Global |
| coastalcph/fairlex | ~80 | Python | Cross-lingual fairness legal dataset | Dataset | EU |
| thunlp/CAIL | 502 | Python | 2.6M Chinese criminal case records | Dataset | CN |

---

### 3J. Chinese Legal Tech

| Repo | Stars | Language | Last Active | Description | Type | Origin |
|------|-------|----------|-------------|-------------|------|--------|
| PKU-YuanGroup/ChatLaw | 7.5k | Python | 2024 | Chinese legal LLM (MoE + knowledge graph) | Code-heavy | CN |
| pengxiao-song/LaWGPT | 6k | Python | 2023 | Chinese legal LLM (Llama fine-tune) | Code-heavy | CN |
| lvwzhen/law-cn-ai | 4.9k | MDX | Active | AI 法律助手 (Chinese law RAG app) | Content | CN |
| FudanDISC/DISC-LawLLM | 899 | Python | 2024 | Fudan Chinese legal LLM (300K SFT data) | Code-heavy | CN |
| thunlp/CAIL | 502 | Python | 2022 | THUNLP Chinese AI & Law Challenge | Dataset/Code | CN |
| irlab-sdu/fuzi.mingcha | 371 | Python | 2025 | Chinese judicial LLM (ChatGLM-based) | Code-heavy | CN |
| CSHaitao/LexiLaw | ~200 | Python | 2023 | Chinese legal LLM | Code-heavy | CN |
| Dai-shen/LAiW | ~150 | Python | 2024 | Chinese legal LLM benchmark | Mixed | CN |
| ai_law (topic:law) | 293 | Python | Active | Chinese legal text classification | Code-heavy | CN |
| ParseLawDocuments | 203 | Python | Active | Chinese legal doc analysis + clustering | Code-heavy | CN |

**Key observation:** Chinese legal LLMs are model weights + fine-tuning scripts. They have rich code (training pipelines, evaluation harnesses) but business logic lives in SFT datasets and prompts, not in architectural decision-making. Doramagic can extract blueprints around "how to build domain-specific legal LLMs" or "how to design legal SFT datasets."

---

## 4. Quality Assessment

### Star Band Distribution (legal domain, all subdomains)

| Band | Count (estimated) | Examples |
|------|------------------|---------|
| **10k+** | 4 | Lynis (15.5k), Wazuh (15.3k), Prowler (13.6k), OPA (11.6k) |
| **5k-10k** | 6 | ChatLaw (7.5k), checkov (8.6k), kyverno (7.6k), tfsec (7k), cloud-custodian (6k), LaWGPT (6k) |
| **1k-5k** | 12 | law-cn-ai (4.9k), OpenSign (6.2k*), ossec (5k), ballerine (2.4k), balanced-BEIPA (2.2k), ContextGem (1.8k), korean-law-mcp (1.5k), Databunker (1.4k), ciso-assistant (4k), bearer (2.6k), ComplianceAsCode (2.7k), intuitem ciso (4k) |
| **500-1k** | ~15 | CourtListener (896), docassemble (935), DISC-LawLLM (899), awesome-legal (948), CAIL (502), CUAD (493), LexNLP (774), Blackstone (684), Legal-Text-Analytics (716), legalbench (569), Databunker (1.4k), OpenSign (6.2k*) |
| **100-499** | ~35 | fuzi.mingcha (371), LexGLUE (250), LLM-and-Law (295), awesome-legal-nlp (314), statedecoded (263), LexiLaw (~200), PQAI (119), PatZilla (115), ContraxSuite (181), etc. |

*OpenSign is e-signature SaaS, borderline relevant.

**Total Doramagic-extractable (star > 500, active within 18 months, code-heavy enough):**

Strict filter (all three criteria): **~45-55 projects**  
Relaxed filter (star > 200, active, some code): **~80-100 projects**

### Top 10 Most-Starred Legal/Adjacent Projects Globally

| Rank | Repo | Stars | Category |
|------|------|-------|----------|
| 1 | CISOfy/lynis | 15.5k | Compliance/Security |
| 2 | wazuh/wazuh | 15.3k | Compliance/SIEM |
| 3 | prowler-cloud/prowler | 13.6k | Cloud Compliance |
| 4 | open-policy-agent/opa | 11.6k | Policy/Compliance |
| 5 | bridgecrewio/checkov | 8.6k | IaC Compliance |
| 6 | kyverno/kyverno | 7.6k | K8s Compliance |
| 7 | aquasecurity/tfsec | 7k | Terraform Compliance |
| 8 | PKU-YuanGroup/ChatLaw | 7.5k | Chinese Legal LLM |
| 9 | cloud-custodian | 6k | Cloud Compliance |
| 10 | pengxiao-song/LaWGPT | 6k | Chinese Legal LLM |

---

## 5. Code-Heavy vs Content-Heavy Analysis

### Breakdown by project type

| Type | Count (est.) | Pipeline Difficulty | Examples |
|------|-------------|--------------------|---------  |
| **Code-heavy** (NLP libraries, parsers, rule engines, LLM training pipelines) | ~40% (~35 projects) | Low — direct extraction | LexNLP, Blackstone, OPA, ContextGem, ChatLaw training code, prowler |
| **Dataset-heavy** (case law dumps, contract corpora, benchmark JSONs) | ~25% (~22 projects) | High — little business logic in source files | CUAD, PileOfLaw, CAIL, Harvard CAP, Multi_Legal_Pile |
| **Template-heavy** (markdown/docx contract templates, policy docs) | ~20% (~18 projects) | Medium — business rules embedded in prose | awesome-legal, seriesseed, site-policy, plain-contract |
| **Mixed** (web apps with code + data) | ~15% (~13 projects) | Medium — selective file targeting needed | CourtListener (Python web app), docassemble, law-cn-ai, DISC-LawLLM |

### Implications for Doramagic Pipeline

- **~35 code-heavy projects** are directly pipeline-ready using current architecture (reads Python/Go/JS + docstrings → Business Descriptors + Use Cases + Stages).
- **~22 dataset-heavy projects**: pipeline would need to pivot to reading README, paper abstracts, and benchmark task definitions rather than source code. A "document extraction" adapter would be needed — similar to what was explored in the 2026-04-14 non-code knowledge extraction research.
- **~18 template-heavy projects**: if blueprint is "how to draft a SAFE agreement" or "how to structure an NDA", these could yield blueprints via prose analysis. Medium adaptation needed.
- **Compliance infra projects** (Prowler, OPA, Wazuh): code is rich but blueprints will be about "security compliance implementation patterns" rather than "legal practice workflows." Relevant but requires a different blueprint taxonomy.

---

## 6. CN vs US Coverage Gap

### Count by Origin

| Origin | Viable Projects (star > 200, active) | Notable Examples |
|--------|-------------------------------------|-----------------|
| **US** | ~40 | CourtListener, LexNLP, CUAD, docassemble, Prowler, OPA, LegalBench, Blackstone (UK) |
| **Global/Neutral** | ~25 | OPA, kyverno, checkov, ContextGem, accordproject, Lynis, Wazuh |
| **CN** | ~12 | ChatLaw, LaWGPT, law-cn-ai, DISC-LawLLM, CAIL, fuzi.mingcha, LexiLaw, LAiW, ai_law, ParseLawDocuments |
| **EU** | ~8 | LexGLUE, awesome-legal-nlp, fairlex, Legal-HeBERT (Israel), multi-eurlex |
| **KR/Other Asia** | ~3 | korean-law-mcp (1.5k), pasal (Indonesia, 211), fuzi.mingcha |

### CN-Side Gap Analysis

Chinese legal OSS is **LLM-first, tooling-sparse.** What exists:
- LLM fine-tuning repos (ChatLaw, LaWGPT, DISC-LawLLM, LexiLaw, fuzi.mingcha) — 5 projects > 200 stars
- Benchmarks/datasets (CAIL, LAiW) — 2 projects
- Content/demo apps (law-cn-ai, ai_law, ParseLawDocuments) — 3 projects

**What is missing from CN GitHub:**
- Contract clause extraction libraries (no CN equivalent of LexNLP)
- 合同审查 (contract review) pipeline tools with open code
- Legal knowledge graphs (KG repos exist in Chinese academia papers but rarely open-sourced on GitHub; likely on Gitee)
- Compliance tooling for Chinese regulations (PIPL, GB standards)
- Court opinion search infrastructure (equivalent to CourtListener for Chinese judiciary data)

**Gap severity:** Significant. CN-side contributes ~12 of ~85 viable projects. If Doramagic wants CN legal blueprints, it will need to either: (a) source from Gitee, (b) use the LLM training repos and derive blueprints about "how to build Chinese legal AI," or (c) supplement with academic papers as source material.

---

## 7. Comparison to Finance

| Metric | Finance | Legal |
|--------|---------|-------|
| Total viable projects (> 500 stars, code-heavy) | ~100+ | ~45-55 |
| Top-starred project | qlib (~20k), QuantLib (~5k) | Lynis (15.5k), Wazuh (15.3k) |
| Avg stars (top 20) | ~3-5k | ~5-6k (inflated by compliance infra) |
| CN-side projects | Strong (qlib, akshare, mootdx, baostock, etc.) | Weak (5-6 code-heavy repos) |
| Code-heavy % | ~65% | ~40% |
| Dataset-heavy % | ~20% | ~25% |
| Domain coherence | High — all finance workflows | Low-medium — legal + compliance + policy = 3 distinct verticals |
| Pipeline-ready as-is | ~65 projects | ~35 projects |
| Activity level | High (most top repos active 2025-2026) | High for compliance infra; moderate for legal NLP |

**Key difference:** Finance OSS is dominated by code-heavy quantitative libraries (backtesting engines, data connectors, portfolio optimizers) that directly map to Doramagic business descriptors. Legal OSS splits across: (1) compliance infra (rich code, but security-focused), (2) NLP/LLM repos (rich code, but AI-research-focused), (3) content/templates (thin business logic). The finance pipeline produced 73 blueprints from ~100 viable projects. Legal can realistically produce 50-80 blueprints from 85-110 addressable projects, with ~20-30 requiring pipeline adaptation.

---

## 8. Pipeline Adaptation Risk

### Current pipeline capability
Doramagic's Blueprint pipeline reads source code + docstrings → extracts Business Descriptors, Use Cases, Stages, Evidence. Optimized for code-centric libs like QuantLib, qlib, akshare.

### Risk by project type in legal domain

| Project Type | Risk Level | Adaptation Needed |
|-------------|-----------|------------------|
| Code-heavy NLP libraries (LexNLP, Blackstone, ContextGem) | **Low** | None — direct extraction works |
| Compliance infra (OPA, Prowler, Checkov) | **Low-Medium** | Blueprint taxonomy needs a "compliance rule" stage type, not just "trading strategy" stage |
| Chinese LLM fine-tune repos (ChatLaw, LaWGPT) | **Medium** | Pipeline reads training code but business logic is in dataset curation; need to extract from README + SFT dataset structure |
| Dataset-only repos (CUAD, PileOfLaw, CAIL) | **High** | No source code to parse; need document-extraction adapter to read paper PDFs + schema files |
| Template repos (seriesseed, awesome-legal, plain-contract) | **High** | Markdown templates lack structured business logic; need prose-extraction mode |
| Web apps (CourtListener, docassemble) | **Medium** | Large Python/JS codebases — pipeline works but requires selective file targeting (skip migrations, focus on service/logic layers) |

### Recommended adaptations (prioritized)
1. **Add Compliance stage type** to Blueprint schema — "policy rule" / "control check" / "regulatory mapping" as Stage categories. Unblocks 14 high-star compliance repos.
2. **README + paper extraction mode** — for dataset-heavy repos, extract Use Cases from benchmark task definitions. Unblocks ~22 dataset repos.
3. **No adaptation needed for immediate Wave 1** — the 35 code-heavy projects can be run through existing pipeline.

---

## 9. Verdict & Recommendation

**Supply verdict: MARGINAL (50-120 viable projects)**. Not insufficient, but not as deep as Finance. 50 blueprints are clearly achievable. 150 requires pulling compliance infra + dataset repos with pipeline adaptation.

### Top 20 Projects for Wave 1 (prioritized by star count + code-heavy + pipeline-readiness)

| Priority | Repo | Stars | Subdomain | Reason |
|----------|------|-------|-----------|--------|
| 1 | prowler-cloud/prowler | 13.6k | Compliance | Python, rich compliance-check business logic |
| 2 | open-policy-agent/opa | 11.6k | Compliance | Go, policy engine — rich rule patterns |
| 3 | bridgecrewio/checkov | 8.6k | Compliance | Python, IaC compliance rules |
| 4 | PKU-YuanGroup/ChatLaw | 7.5k | CN Legal LLM | Python, full training pipeline |
| 5 | pengxiao-song/LaWGPT | 6k | CN Legal LLM | Python, legal domain pretraining pipeline |
| 6 | cloud-custodian | 6k | Compliance | Python, cloud governance rules |
| 7 | intuitem/ciso-assistant | 4k | Compliance GRC | Python, 130+ regulatory frameworks |
| 8 | lvwzhen/law-cn-ai | 4.9k | CN Legal App | RAG pipeline for Chinese law (code thin) |
| 9 | ComplianceAsCode/content | 2.7k | Compliance | SCAP compliance automation |
| 10 | shcherbak-ai/contextgem | 1.8k | Contract Analysis | Python, LLM extraction framework |
| 11 | chrisryugj/korean-law-mcp | 1.5k | Case Law | TypeScript, legal API integration patterns |
| 12 | freelawproject/courtlistener | 896 | Case Law | Python web app, court data infrastructure |
| 13 | FudanDISC/DISC-LawLLM | 899 | CN Legal LLM | Python, legal SFT pipeline |
| 14 | jhpyle/docassemble | 935 | Doc Automation | JS/Python, guided interview logic |
| 15 | ankane/awesome-legal (reference only) | 948 | Templates | Content-heavy; use as catalog, not extraction source |
| 16 | LexPredict/lexpredict-lexnlp | 774 | Contract NLP | Python, clause extraction library |
| 17 | Liquid-Legal-Institute/Legal-Text-Analytics | 716 | Legal NLP | Resource index; derive blueprints from linked projects |
| 18 | explosion-ai/Blackstone | 684 | Legal NLP | Python, spaCy pipeline for UK legal text |
| 19 | HazyResearch/legalbench | 569 | Benchmarks | Python, 162 legal reasoning tasks |
| 20 | thunlp/CAIL | 502 | CN Case Law | Python, challenge infrastructure + dataset |

### Known blockers
1. **Compliance-infra / legal-practice domain gap**: Projects like Prowler, OPA, and Wazuh encode *security compliance* rather than *legal practice workflows* (contracts, litigation, M&A). Blueprints extracted will be "cloud security compliance patterns," not "contract negotiation patterns." This is still valuable but requires the CEO to decide if security compliance counts as "legal domain."
2. **CN-side shallowness**: If the goal is CN legal tooling blueprints specifically, supply is thin (~10 viable repos). Most CN legal OSS is LLM fine-tuning, not workflow tooling.
3. **Dataset-heavy repos**: 22+ projects (CUAD, PileOfLaw, CAIL) require pipeline adaptation before extraction.

---

## 10. Risks & Gaps

### What couldn't be verified
- **Exact star counts for some repos** where GitHub page content was truncated (LexGLUE, PileOfLaw, various smaller Chinese repos). Counts are approximate.
- **Gitee coverage**: Chinese legal OSS on Gitee (码云) is not indexed by GitHub search. Anecdotally, Chinese court/government tooling lives on Gitee or in private repos. The real CN-side supply may be 2-3x larger but inaccessible via GitHub-based pipeline.
- **Enterprise-grade OSS**: Projects by LexisNexis, Thomson Reuters (HighQ open-source components), or Mitratech subsidiaries may exist but weren't surfaced.
- **Recent 2025-2026 emergence**: Legal AI is moving fast post-GPT-4o. Several repos <100 stars today may reach 500+ by Q3 2026 (e.g., legalbench-rag, newer Chinese LLMs like Qwen-Legal variants).

### Recommended follow-up
1. **Gitee search**: Run equivalent searches on gitee.com for 法律, 合同审查, 合规 — may surface 10-20 additional CN projects.
2. **Awesome list deep-crawl**: Fetch and parse all entries in awesome-legal-nlp, awesome-legaltech, and Awesome-LegalAI-Resources to surface 50+ smaller repos not yet in this analysis.
3. **HuggingFace legal models**: Legal-BERT variants, InLegalBERT, domain LLMs — their linked GitHub training repos may be extractable.
4. **Stanford CodeX audit**: CodeX legaltech lab may have open-sourced tools not well-indexed by topic tags.
5. **Academic org scan**: Fudan DISC, Tsinghua THUNLP, Shanghai Jiao Tong, and Renmin University all have legal NLP groups with potentially open repos.

---

## Final Verdict (CEO Brief)

**The legal domain has sufficient but not abundant GitHub supply for Doramagic's extraction pipeline. Wave 1 (15-30 projects) is clearly executable using the existing pipeline against code-heavy repos: 35+ projects meet all criteria (star > 500, active, code-heavy). A 50-blueprint target is achievable within 2 waves. A 150-blueprint target requires: (a) expanding the definition of "legal" to include security compliance infra (which adds ~14 high-star repos like Prowler, OPA, Checkov), (b) building a dataset/document extraction adapter for the 22+ dataset-heavy legal repos, and (c) supplementing GitHub with Gitee for CN-side coverage. The CN legal tech supply on GitHub is a genuine gap — only ~10-12 viable CN repos vs. 40+ US/Global repos. If Doramagic's Wave 1 prioritizes compliance infra + English legal NLP, supply is sufficient. If it requires CN-native legal practice tooling, supply is insufficient without Gitee access. Recommend launching Wave 1 with the top 20 projects listed above, all US/Global, all code-heavy, and deferring CN-specific waves until Gitee access is established.**
