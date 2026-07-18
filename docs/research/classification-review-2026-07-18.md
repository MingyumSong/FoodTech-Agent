# 뉴스 LLM 분류 결과 검토 요청 (2026-07-18)

> **검토자**: 희정님 · **작성**: 민겸 (T-006)
> 매일 아침 크론이 뉴스를 수집하면서 LLM(gemini-2.5-flash)이 정부 푸드테크 10대 핵심분야로
> 자동 분류해 DB에 저장하기 시작했습니다. 첫 실데이터 78건의 분류가 적절한지 눈으로 확인 부탁드립니다.

## 검토 포인트 3가지

1. **오분류가 있나요?** — 각 분야 아래 기사들을 훑어보고 어색한 것에 표시해 주세요.
2. **"일반" 분류를 쪼갤까요?** — 10대 분야에 안 들어가는 푸드테크 기사를 "일반"으로 모으고 있는데
   12건이나 됩니다. 아래 목록을 보고 반복되는 주제(예: 스마트팜/애그테크, 정밀발효·대체단백,
   투자·정책 동향)가 보이면 별도 분야로 승격할지 의견 부탁드립니다.
3. **폐기가 적절했나요?** — 푸드테크와 무관 판정으로 버린 기사가 맨 아래 있습니다. 아깝게 버려진 게 있는지.

### 민겸 사전 관찰 ("일반" 12건에서 보이는 패턴)

- **투자·정책 클러스터**: 96조 푸드테크 신산업, 농협 펀드, 그래피 M&A — "투자·정책" 분야 승격 후보.
- **해외 동향 라운드업 클러스터**: DigitalFoodLab 주간 딜, FoodTech 500 시리즈 5건 — "글로벌 동향" 후보.
  (다만 이런 라운드업은 뉴스레터 코너 재료로는 좋아서, 분야 승격보다 그대로 둘 수도.)
- **⚠️ 노이즈 의심**: 캐시워크 돈버는퀴즈 정답 2건, 스타벅스 쿠폰 — "일반"이 아니라 폐기(해당없음)됐어야
  할 것으로 보임. 검토 결과에 따라 프롬프트에 "퀴즈 정답·쿠폰·프로모션 기사는 해당없음" 보정 예정.

## 분류 분포 (78건)

| 분야 | 건수 |
|---|---|
| 세포배양식품 | 5 |
| 식물기반식품 | 2 |
| 간편식 | 4 |
| 식품프린팅 | 8 |
| 스마트제조 | 11 |
| 스마트유통 | 2 |
| 커스터마이징 | 5 |
| 외식 푸드테크 | 9 |
| 업사이클링 | 11 |
| 친환경포장 | 9 |
| 일반 | 12 |

## 세포배양식품 (5건)

- [ ] 🌏 [What does cultivated meat really taste like - 15 consumers share their experience](https://therottenapple.substack.com/p/what-does-cultivated-meat-really)
- [ ] 🌏 [The Netherlands Builds the World’s First Cultivated Meat Farm: Real Beef, Grown in a Bioreactor](https://quasa.io/media/the-netherlands-builds-the-world-s-first-cultivated-meat-farm-real-beef-grown-in-a-bioreactor)
- [ ] 🌏 [From farm to table or lab to table: Cell-cultivated meat sparks local attention](https://www.wgem.com/2026/07/09/farm-table-or-lab-table-cell-cultivated-meat-sparks-local-attention/)
- [ ] 🌏 [What Cultivated Meat Teaches About Building New Industries - Cultivated Meat News](https://cultivated-meat.maubon.com/2026/07/07/what-cultivated-meat-teaches-about-building-new-industries/)
- [ ] 🌏 [Federal approval for lab-grown meat sparks Louisiana debate](https://www.ktalnews.com/news/consumer-alerts/lab-grown-meat-louisiana-concerns/)

## 식물기반식품 (2건)

- [ ] 🌏 [A Dietitian Shares the Best Meatless Protein Sources for a Healthy Plant-Based Diet](https://www.prevention.com/food-nutrition/healthy-eating/a72092660/best-plant-based-protein-sources/)
- [ ] 🌏 [Global Plant-Based Foods Market Strategic Research Report | Market Research Reports® Inc.](https://www.marketresearchreports.com/reports/global-plant-based-foods-market-strategic-research-report)

## 간편식 (4건)

- [ ] 🌏 [Bento Express | Commissary Sushi for Retail and Foodservice](https://www.bentosushi.com/signature-lines/commissary-partnership/bento-express/)
- [ ] 🌏 [The Best Meal Delivery Services of 2026, Tested by Taste of Home Editors](https://www.tasteofhome.com/collection/best-meal-delivery-service/)
- [ ] 🌏 [Small manufacturer frozen ready meal process steps - IFSQN](https://www.ifsqn.com/forum/index.php/topic/47355-small-manufacturer-frozen-ready-meal-process-steps/)
- [ ] 🌏 [Meal, Ready-to-Eat - Wikipedia](https://en.wikipedia.org/wiki/Meal,_Ready-to-Eat)

## 식품프린팅 (8건)

- [ ] [동물실험 없이 신약 심사받는다…K-바이오, '대체시험' 기술 확보](https://www.kpinews.kr/newsView/1065577812267833)
- [ ] [[임신·출산뉴스] 구로구, 임산부 친환경농산물 지원사업 추진…연 24만...](https://www.ibabynews.com/news/articleView.html?idxno=152894)
- [ ] 🌏 [Optimization of Formulation and Processing Parameters for High-Fidelity 3D Printing of a Surimi–Flour Composite Batter](https://www.mdpi.com/2304-8158/15/14/2502)
- [ ] 🌏 [3D Food Printing Market to Reach USD 17.97 Billion by 2035, Driven by Personalized Nutrition and Food Technology Innovation](https://www.openpr.com/news/4576742/3d-food-printing-market-to-reach-usd-17-97-billion-by-2035-driven)
- [ ] 🌏 [The Revolutionary Effects of 3D Food Printing: Transforming the Culinary World - HomeDiningKitchen](https://homediningkitchen.com/what-are-the-effects-of-3d-food-printing/)
- [ ] 🌏 [3D printing - Wikipedia](https://en.wikipedia.org/wiki/3D_printing)
- [ ] 🌏 [Non-destructive testing technologies for quality control in food 3D printing: A systematic review - ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S2212429226012393)
- [ ] 🌏 [Beyond 3D: How 4D Food Printing Could Transform Personalized Nutrition | Research Communities by Springer Nature](https://communities.springernature.com/posts/beyond-3d-how-4d-food-printing-could-transform-personalized-nutrition)

## 스마트제조 (11건)

- [ ] [오뚜기-농심-삼양식품, K라면 '수출기지 확장'](http://www.sportsq.co.kr/news/articleView.html?idxno=496506)
- [ ] [[주간유통잇슈] 홈플러스 '회생 불씨', 쿠팡 총수 지정 '일단 정지'](https://www.shinailbo.co.kr/news/articleView.html?idxno=5041526)
- [ ] [농심 이어 오뚜기도 품었다…‘신선한 라면’ 맛볼 수 있는 이곳](https://www.joongang.co.kr/article/25446049)
- [ ] [최우식 딥노이드 대표 "의료AI 파운데이션 모델, 구글 메드젬마 앞섰다...](https://www.edaily.co.kr/news/newspath.asp?newsid=02860166645515176)
- [ ] [인천푸드테크협회, 창립 2주년 맞아 미래비전 선포…7월 22일 기념행사 ...](https://www.ppss.kr/news/articleView.html?idxno=302292)
- [ ] [현장을 이해하는 AI, 자율제조 경쟁력 높인다](http://www.engjournal.co.kr/news/articleView.html?idxno=3872)
- [ ] [[Invest]현대차 '미래전략 핵심' 현대오토에버도 노조 출범…로봇·SDV 전...](https://www.investchosun.com/site/data/html_dir/2026/07/15/2026071580030.html)
- [ ] [‘사각지대’ 액상 공정, AI가 실시간으로 읽는다](https://www.donga.com/news/Economy/article/all/20260714/134291059/2)
- [ ] 🌏 [AI in food manufacturing: Use cases | KAIZEN™ Article](https://kaizen.com/insights/ai-food-manufacturing/)
- [ ] 🌏 [Automation and Robotics in the Food Industry: Cyber-Physical Systems, Digital Twins, and AI-Driven Quality Control in the Era of Industry 5.0 | Food Engineering Reviews | Springer Nature Link](https://link.springer.com/article/10.1007/s12393-026-09453-w)
- [ ] 🌏 [AI in Food Processing Market Insights - Shaping Smart Food Manufacturing](https://www.globemarketresearch.com/press-release/ai-in-food-processing-market-news)

## 스마트유통 (2건)

- [ ] [농협, 생산·유통·판매 전방위 혁신](http://www.bokuennews.com/news/article.html?no=281365)
- [ ] 🌏 [Food Cold Chain Market Size, Share, Trends, Industry Analysis, and Forecast 2025-2035](https://www.openpr.com/news/4575734/food-cold-chain-market-size-share-trends-industry-analysis)

## 커스터마이징 (5건)

- [ ] 🌏 [Beyond BMI: Personalized Nutrition in Obesity, Normal-Weight Obesity, Metabolic Syndrome, and MASLD](https://www.mdpi.com/2072-6643/18/14/2345)
- [ ] 🌏 [Fuel for active nutrition: AI and tech power personalized product innovations](https://www.nutritioninsight.com/news/ai-active-nutrition-personalization.html)
- [ ] 🌏 [Best Nutrition Apps (2026): Nutritionist Approved | Fortune](https://fortune.com/article/best-nutrition-apps/)
- [ ] 🌏 [Orthomolecular Nutrition Explained: Personalized Holistic Health Guide](https://edisoninst.com/orthomolecular-nutrition-personalized-holistic-health-guide/)
- [ ] 🌏 [Why AI Google Cloud Is the Future of Personalized Nutrition in America](https://techversions.com/ai-machine-learning/why-ai-google-cloud-is-the-future-of-personalized-nutrition-in-america/)

## 외식 푸드테크 (9건)

- [ ] [광화문 최고의 전망을 품은 스테이크하우스…이제 맛으로 증명할 차례 ...](https://www.joongang.co.kr/article/25446076)
- [ ] ["축제 주인은 시민"...밀양시, 여름축제 "내빈 의전·바가지 없앴다"](https://www.pointe.co.kr/news/articleView.html?idxno=81918)
- [ ] [중국 RX, 실생활 어떻게 달라졌나](https://www.mk.co.kr/article/12095244)
- [ ] [재벌집 막내아들 홀로서기 시작…의좋은 한화 삼형제의 미래](https://www.joongang.co.kr/article/25446046)
- [ ] 🌏 [Richtech Robotics Inc. (RR) Stock Price, News, Quote & History - Yahoo Finance](https://finance.yahoo.com/quote/RR/)
- [ ] 🌏 [Robotic Waiter - Robotic Restaurant](https://kioskindustry.org/robotic-waiter-robotic-restaurant/)
- [ ] 🌏 [A restaurant run by robots | Hub](https://hub.jhu.edu/magazine/2026/summer/a-restaurant-run-by-robots/)
- [ ] 🌏 [Hotel Robots: Integrating Automation in Hospitality](https://insights.ehl.edu/hotel-robots)
- [ ] 🌏 [Hospitality Robots — Delivery & Concierge | RoboMercato](https://www.robomercato.com/use-cases/hospitality-customer-service)

## 업사이클링 (11건)

- [ ] [김천시, 지역상생 사회공헌 5자 공동업무협약 체결](https://www.sentv.co.kr/article/view/sentv202607160162)
- [ ] [김천시, 지역상생 ESG 시동](https://view.asiae.co.kr/article/2026071618360161524)
- [ ] [휴밀, AFPRO 2026서 '온리튼튼' 알려..."아기상어 캐릭터로 만든 초코맛...](https://kr.aving.net/news/articleView.html?idxno=1812484)
- [ ] [로브콜, AFPRO 2026서 '매실매실과 OMG' 알려..."설탕이 없는 매실과 오미...](https://kr.aving.net/news/articleView.html?idxno=1812472)
- [ ] [라이스밸류, AFPRO 2026서 독자적 ISOT 기술 적용한 친환경 '쌀 및 미강 ...](https://kr.aving.net/news/articleView.html?idxno=1812469)
- [ ] [도로공사, 김천 샤인머스캣 농가에 ' 푸드 업사이클링 ' 상생모델 제시](https://www.g-enews.com/view.php?ud=202607161204225340a9fc143920_1)
- [ ] [[ESG트렌드] ESG 문화 유튜브 '대담해', 지속가능한 국내외 여행지와 ESG...](https://www.ibabynews.com/news/articleView.html?idxno=152974)
- [ ] [‘컵과일’샤인머스캣으로… ‘달콤한 나눔’ 출격](https://www.munhwa.com/article/11603156?ref=naver)
- [ ] [김천 샤인머스캣, 취약계층 아동 돕는 ‘가치소비’로](https://www.kbsm.net/news/view.php?idx=526987)
- [ ] 🌏 [What Is Upcycled Food? The 2026 Trend Already on Your Plate — CHOMP](https://www.chomphk.com/blog/what-is-upcycled-food)
- [ ] 🌏 [These Snacks Aren't Just Tasty — They're Saving the Planet | Clean Plates](https://cleanplates.com/product-roundup/upcycled-foods/)

## 친환경포장 (9건)

- [ ] [농 식품 부 2026년 하반기 달라지는 주요 제도](https://www.newsam.co.kr/news/article.html?no=43525)
- [ ] [[산청 24시] 유명현 군수, 딸기농가서 민선 9기 첫 현장간담회](https://www.sisajournal.com/news/articleView.html?idxno=380179)
- [ ] [에코넥트, AFPRO 2026서 'OriginK' 알려..."K-FOOD 미주 수출 플랫폼!"](https://kr.aving.net/news/articleView.html?idxno=1812446)
- [ ] [KCL,유럽 PPWR< 포장 및 포장 폐기물 규정> 대응 네트워크 구축](https://www.naeil.com/news/read/595621?ref=naver)
- [ ] [7월 3주차 해외 ESG 핫클립](http://www.impacton.net/news/articleView.html?idxno=19623)
- [ ] [중앙디자인 포장 , 손잡이 보냉백 출시](https://www.ksilbo.co.kr/news/articleView.html?idxno=1062318)
- [ ] [KCL, 독일·이탈리아 현지에 유럽 PPWR 대응 네트워크 구축](https://www.electimes.com/news/articleView.html?idxno=370356)
- [ ] 🌏 [Sustainable Food Packaging: Recent Advances In Biodegradable And Smart Packaging Technologies » Article](https://journals.stmjournals.com/article/article=2026/view=249885/)
- [ ] 🌏 [Frontiers | Frozen food packaging: recent technological advances and future perspectives](https://www.frontiersin.org/journals/sustainable-food-systems/articles/10.3389/fsufs.2026.1891260/full)

## 일반 (12건)

- [ ] [노프랍 아줄렌…캐시워크 돈버는퀴즈 정답 공개](https://www.gametoc.co.kr/news/articleView.html?idxno=110042)
- [ ] [[단독] 캐시워크 돈버는퀴즈 정답 7월 18일](https://www.bntnews.co.kr/article/view/bnt202607180005)
- [ ] ['프리퀀시' 없는 여름 맞은 스타벅스...무료 쿠폰으로 고객 잡기](https://www.ntoday.co.kr/news/articleView.html?idxno=128231)
- [ ] [96조 돌파한 푸드테크 신산업…기업별 맞춤형 지원 시급](https://www.nocutnews.co.kr/news/6549351?utm_source=naver&utm_medium=article&utm_campaign=20260718050108)
- [ ] ["돈 버는 농협에서 농민 돕는 농협으로"…생산부터 판매까지 싹 바꾼다](https://www.mt.co.kr/economy/2026/07/16/2026071609142543145)
- [ ] [강태영 농협은행장 "농 식품 펀드, 2030년까지 8000억 키운다"](https://www.mt.co.kr/finance/2026/07/16/2026071512302096590)
- [ ] 🌏 [20 FoodTech insights and deals to know this week (2026 – week #29) - DigitalFoodLab](https://digitalfoodlab.com/20-foodtech-insights-and-deals-to-know-this-week-2026-week-29/)
- [ ] 🌏 [European Powerhouses in the 2025 FoodTech 500 Rankings | Forward Fooding](https://forwardfooding.com/blog/the-foodtech-500/european-foodtech-500-2025/)
- [ ] 🌏 [The FoodTech 500 Alumni News Round-up (July Edition) | Forward Fooding](https://forwardfooding.com/blog/foodtech-500-alumni-news/round-up-july-2026-edition/)
- [ ] 🌏 [10 FoodTech Startups Transforming the Global Food Industry](https://circleofnews.in/top-10-foodtech-startups-2026/)
- [ ] 🌏 [17 FoodTech insights and deals to know this week (2026 – week #28) - DigitalFoodLab](https://digitalfoodlab.com/17-foodtech-insights-and-deals-to-know-this-week-2026-week-28/)
- [ ] [그래피, M&A 위해 600억대 실탄 마련…사업확대 '잰걸음'](https://www.mt.co.kr/stock/2026/07/16/2026071614592211907)

## 폐기(해당없음) — 저장 안 한 기사

- [ ] [[유통소식]신세계百, 부산 센텀시티서 'K-HERITAGE' 문화행사](http://www.4th.kr/news/articleView.html?idxno=2114814)
- [ ] [[부산ㆍ경남 대학 브리핑 모음(7월15일)] 인제대 AI 교육 받은 김해여고...](https://www.dnews.co.kr/uhtml/view.jsp?idxno=202607141308354880100)

---
체크 방법: 문제 있는 기사만 체크박스에 표시하고 옆에 한 줄 코멘트 부탁드립니다.
결과에 따라 ① 프롬프트 보정 ② "일반" 세분화 ③ 재분류를 진행합니다. (분류 체계 근거: 결정 2)
