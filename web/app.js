/**
 * Macau Tower Destination Agent — 前端演示逻辑
 * 含：远程 RAG Agent（后端）、本地规则兜底、埋点、中英切换
 */

(function () {
  "use strict";

  /** Q 版头像：对话气泡旁；完整立绘在 index.html 与 Agent 身份条 */
  const TOTA_CHIBI_SRC = "assets/tota-chibi.png";

  /** 后端 API（可在页面中设置 window.__AGENT_API__ 覆盖） */
  const API_BASE =
    (typeof window !== "undefined" && window.__AGENT_API__) || "https://hilda-totaweb.onrender.com";
  /** 设为 false 时仅用本地规则，不请求 LongCat */
  const USE_REMOTE_AGENT =
    typeof window === "undefined" || window.__USE_REMOTE_AGENT__ !== false;

  /** OpenAI 格式对话历史，供 /api/chat 使用 */
  let chatHistory = [];

  const I18N = {
    zh: {
      logo: "Macau Tower",
      navExplore: "Explore",
      heroEyebrow: "AI Destination Agent",
      heroTitle: "Meet Macau Tower — Your AI Destination Agent",
      heroSubtitle:
        "不是一座等待被浏览的地标，而是一位会与你互动、为你规划、陪你探索澳门的智能旅游管家。",
      ctaExplore: "开始探索",
      ctaChat: "和澳门塔聊聊",
      quickLabel: "试试这样问",
      heroPhotoCredit: "背景图：澳门塔实景（项目素材）",
      heroTotaAlt: "Tota — 澳门塔目的地 Agent 虚拟形象",
      agentName: "塔塔 Tota",
      agentTagline: "澳门塔 AI 旅游管家 · 虚拟形象",
      highlightsTitle: "澳门塔亮点",
      highlightsDesc: "观景、夜景、冒险与城市故事，一站掌握。",
      agentTitle: "与 Agent 对话",
      agentDesc: "快捷问题或自由输入，获取个性化玩法与路线建议。",
      inputPlaceholder: "描述你的时间、同行人与偏好…",
      send: "发送",
      agentHint: "票价与开放时段以官方渠道为准；此处为体验演示，不含实时票务数据。",
      guideTitle: "场景化导览",
      guideDesc: "黄昏、夜景与拍照点位，提前感受澳门塔氛围。",
      mementoTitle: "生成我的澳门塔时刻",
      mementoDesc: "基于你的对话偏好，生成可分享的纪念文案与卡片。",
      mementoBtn: "生成纪念卡",
      convertLabel: "转化入口",
      linkOfficial: "官网 / 门票",
      linkAgent: "继续问 Agent",
      mementoModalTitle: "你的澳门塔时刻",
      copyShare: "复制分享文案",
      regen: "重新生成",
      quickQuestions: [
        "我第一次来澳门，澳门塔值得去吗？",
        "我只有半天时间，怎么安排？",
        "我想和对象看夜景，什么时候来最好？",
        "带家人去，哪些体验更轻松？",
      ],
      highlights: [
        { icon: "🌆", title: "360° 观景", body: "俯瞰澳门半岛与氹仔天际线，城市画卷尽收眼底。" },
        { icon: "🌃", title: "夜景氛围", body: "黄昏至入夜的光线过渡，适合约会与摄影打卡。" },
        { icon: "🪂", title: "冒险体验", body: "笨猪跳、空中漫步等高空项目（依个人胆量选择）。" },
        { icon: "📖", title: "城市故事", body: "地标背后的澳门文旅叙事，从塔上读懂这座城。" },
      ],
      guideCards: [
        { emoji: "🌇", title: "黄昏时段", body: "日落前后光线柔和，适合观景与轻松拍照。" },
        { emoji: "✨", title: "夜景视角", body: "华灯初上时分的城市肌理，氛围感拉满。" },
        { emoji: "📸", title: "拍照点位", body: "观景层视野、玻璃栈道与塔身外观都是经典取景点。" },
        { emoji: "🍽️", title: "观景 + 餐饮", body: "可结合旋转餐厅或周边餐饮，安排半日松弛动线。" },
      ],
      followupLowConfidence:
        "想更精准地帮你规划：你更想了解玩法推荐、基础信息，还是夜景/拍照建议？回复其中一项即可。",
      faqTicket:
        "具体票价与套票以澳门塔官网或授权渠道为准，本演示不提供实时价格。需要的话，我可以根据你的停留时间和同行人推荐玩法节奏。",
      faqHours:
        "开放时间与最后入场规则会随季节与活动调整，出行前请在官网核对当日公告。若告诉我大致到达时段，我可以帮你排观景与动线顺序。",
      faqTransport:
        "澳门塔邻近西湾湖一带，可乘公交或酒店接驳前往；具体线路以你出发地为准。需要我按「半天行程」帮你串观景和周边吗？",
      faqFamily:
        "观光层适合家庭休闲漫步；刺激性项目请按身高、年龄及健康要求评估。若偏好轻松节奏，可选观景 + 餐饮组合，避开过于紧凑的时段。",
      faqRain:
        "雨天多数室内观景仍可进行，户外或高空项目可能受天气影响；请以现场安全指引为准。",
      defaultRecommend: "根据你的描述，下面是一套主推荐与备选方案，可左右滑动查看。",
      memorialFallback:
        "今晚从澳门塔看见的不只是夜景，也是这座城市慢慢亮起来的那一刻。把风、灯光和高空视角，一起留在这次旅程里。",
      faqGeneric:
        "我可以帮你梳理观景动线、夜景与拍照建议，或家庭轻松行程。你也可以直接说停留时长和同行人，我给出结构化路线卡。",
      localFallbackHint: "（线上模型暂不可用，已切换为本地演示回复）",
    },
    en: {
      logo: "Macau Tower",
      navExplore: "Explore",
      heroEyebrow: "AI Destination Agent",
      heroTitle: "Meet Macau Tower — Your AI Destination Agent",
      heroSubtitle:
        "More than a landmark to scroll past — an AI travel host that plans with you and explores Macau by your side.",
      ctaExplore: "Start exploring",
      ctaChat: "Chat with the Tower",
      quickLabel: "Try asking",
      heroPhotoCredit: "Background: Macau Tower photo (project asset)",
      heroTotaAlt: "Tota — Macau Tower Destination Agent virtual persona",
      agentName: "Tota",
      agentTagline: "Macau Tower AI host · virtual persona",
      highlightsTitle: "Highlights",
      highlightsDesc: "Views, night scenes, adventure, and city stories in one place.",
      agentTitle: "Talk to the Agent",
      agentDesc: "Use quick prompts or type freely for tailored ideas and route cards.",
      inputPlaceholder: "Tell us your time, companions, and preferences…",
      send: "Send",
      agentHint:
        "Tickets and hours are subject to official channels; this demo does not show live pricing.",
      guideTitle: "Scene guides",
      guideDesc: "Golden hour, night views, and photo spots — feel the vibe before you go.",
      mementoTitle: "My Macau Tower moment",
      mementoDesc: "Generate a shareable line and card based on your chat context.",
      mementoBtn: "Create memento",
      convertLabel: "Next steps",
      linkOfficial: "Official site / tickets",
      linkAgent: "Ask the Agent again",
      mementoModalTitle: "Your Macau Tower moment",
      copyShare: "Copy caption",
      regen: "Regenerate",
      quickQuestions: [
        "Is Macau Tower worth it for a first-time visitor?",
        "I only have half a day — how should I plan?",
        "Best time for a couple to enjoy the night view?",
        "Visiting with family — what feels relaxed and easy?",
      ],
      highlights: [
        { icon: "🌆", title: "360° views", body: "Panoramic skyline across the peninsula and Taipa." },
        { icon: "🌃", title: "Night glow", body: "Golden hour to city lights — great for dates and photos." },
        { icon: "🪂", title: "Adventure", body: "Bungee, skywalk, and more — pick what fits your comfort zone." },
        { icon: "📖", title: "City story", body: "Macau’s narrative from an icon above the city." },
      ],
      guideCards: [
        { emoji: "🌇", title: "Golden hour", body: "Soft light before sunset — easy viewing and photos." },
        { emoji: "✨", title: "Night perspective", body: "Watch the city switch on — strong atmosphere." },
        { emoji: "📸", title: "Photo spots", body: "Deck views, glass floors, and the tower facade are classics." },
        { emoji: "🍽️", title: "View + dining", body: "Pair observation with a meal for a relaxed half-day flow." },
      ],
      followupLowConfidence:
        "To tailor better: do you want play recommendations, basics (hours/transport), or night-view/photo tips? Reply with one.",
      faqTicket:
        "Pricing and bundles change — please check the official Macau Tower site. I can still suggest pacing for your hours and group.",
      faqHours:
        "Hours and last entry vary by season — verify on the official site before you go. Share your arrival window and I’ll suggest order of experiences.",
      faqTransport:
        "The tower is near Sai Van Lake; buses and hotel shuttles are common options depending on where you start. Want a half-day route?",
      faqFamily:
        "Observation decks suit relaxed family visits; thrill rides depend on height, age, and health rules. For an easy day, combine viewing with dining and avoid a rushed schedule.",
      faqRain:
        "Indoor viewing often remains available; outdoor or aerial activities may pause for weather — follow on-site safety guidance.",
      defaultRecommend: "Here is a primary plan and alternates — swipe the cards horizontally.",
      memorialFallback:
        "Tonight from Macau Tower you don’t just see the lights — you see the city turning on. Keep the wind, the glow, and the height in this trip.",
      faqGeneric:
        "I can help with viewing flow, night-view/photo timing, or a relaxed family plan. Tell me your duration and who you travel with, and I’ll return route cards.",
      localFallbackHint: "(Remote model unavailable — using local demo reply)",
    },
  };

  let lang = "zh";
  /** @type {{ intent: string, tags: string[], lastPlan?: object }} */
  let sessionContext = { intent: "", tags: [], lastPlan: null };

  const analytics = {
    events: [],
    track(name, payload = {}) {
      const row = { t: Date.now(), name, ...payload };
      this.events.push(row);
      if (typeof console !== "undefined" && console.debug) {
        console.debug("[analytics]", name, payload);
      }
    },
  };

  function t(key) {
    const bundle = I18N[lang] || I18N.zh;
    return bundle[key] !== undefined ? bundle[key] : key;
  }

  function applyI18n() {
    document.documentElement.lang = lang === "zh" ? "zh-CN" : "en";
    document.querySelectorAll("[data-i18n]").forEach((el) => {
      const k = el.getAttribute("data-i18n");
      if (k && I18N[lang][k] !== undefined) el.textContent = I18N[lang][k];
    });
    const totaHero = document.querySelector(".hero__tota-img");
    if (totaHero && t("heroTotaAlt")) totaHero.setAttribute("alt", t("heroTotaAlt"));
    const ph = document.getElementById("chat-input");
    if (ph && I18N[lang].inputPlaceholder) ph.placeholder = I18N[lang].inputPlaceholder;
    renderQuickChips();
    renderAgentQuick();
    renderHighlights();
    renderGuideCards();
  }

  function renderQuickChips() {
    const box = document.getElementById("hero-quick-chips");
    if (!box) return;
    box.innerHTML = "";
    I18N[lang].quickQuestions.forEach((q) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "chip";
      b.textContent = q;
      b.addEventListener("click", () => {
        analytics.track("quick_question_click", { source: "hero", text: q });
        void scrollToAgentChat().then(() => {
          focusChatInput();
          sendUserMessage(q);
        });
      });
      box.appendChild(b);
    });
  }

  function renderAgentQuick() {
    const box = document.getElementById("agent-quick");
    if (!box) return;
    box.innerHTML = "";
    I18N[lang].quickQuestions.forEach((q) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "chip";
      b.textContent = q;
      b.addEventListener("click", () => {
        analytics.track("quick_question_click", { source: "agent", text: q });
        sendUserMessage(q);
      });
      box.appendChild(b);
    });
  }

  function renderHighlights() {
    const grid = document.getElementById("highlight-cards");
    if (!grid) return;
    grid.innerHTML = "";
    I18N[lang].highlights.forEach((h) => {
      const div = document.createElement("article");
      div.className = "highlight-card";
      div.innerHTML = `<div class="highlight-card__icon">${h.icon}</div><h3>${h.title}</h3><p>${h.body}</p>`;
      grid.appendChild(div);
    });
  }

  function renderGuideCards() {
    const sc = document.getElementById("guide-cards");
    if (!sc) return;
    sc.innerHTML = "";
    I18N[lang].guideCards.forEach((g) => {
      const div = document.createElement("article");
      div.className = "guide-card";
      div.innerHTML = `<div class="guide-card__visual">${g.emoji}</div><div class="guide-card__body"><h3>${g.title}</h3><p>${g.body}</p></div>`;
      sc.appendChild(div);
    });
  }

  /** 轻量意图识别（关键词 + 置信度） */
  function detectIntent(text) {
    const s = text.toLowerCase();
    const isEn = lang === "en";
    let score = { seed: 0, faq: 0, recommend: 0, guide: 0, memento: 0 };
    const tags = [];

    const couple = /情侣|对象|约会|浪漫|二人|couple|date|romantic/i.test(s);
    const family = /家人|老人|孩子|家庭|带娃|family|kid|elder/i.test(s);
    const first = /第一次|首次|没来|first|first.time|never been/i.test(s);
    const night = /夜景|晚上|黄昏|日落|night|sunset|evening/i.test(s);
    const half = /半天|半日|几小时|half|few hours/i.test(s);
    const ticket = /门票|票价|多少钱|price|ticket|cost/i.test(s);
    const hours = /开放|时间|几点|关门|hours|open|close/i.test(s);
    const transport = /交通|怎么去|巴士|打车|bus|taxi|how to get/i.test(s);
    const rain = /下雨|雨天|rain/i.test(s);

    if (couple) tags.push("couple");
    if (family) tags.push("family");
    if (first) tags.push("first_time_visitor");
    if (night) tags.push("night_view");
    if (half) {
      tags.push("half_day");
      score.recommend += 2;
    }

    if (ticket) score.faq += 3;
    if (hours) score.faq += 3;
    if (transport) score.faq += 2;
    if (rain) score.faq += 2;
    if (family && /适合|轻松|安全|suitable|easy|safe/i.test(s)) score.faq += 2;

    if (/推荐|玩法|路线|安排|怎么玩|plan|recommend|itinerary/i.test(s)) score.recommend += 2;
    if (/值得|worth/i.test(s)) score.seed += 2;
    if (/澳门塔|macau tower/i.test(s)) score.seed += 1;
    if (half || night || couple || family) score.recommend += 1;
    if (/第一次|first/i.test(s)) score.seed += 2;
    if (/拍照|机位|打卡|photo|spot/i.test(s)) score.guide += 2;
    if (/纪念|分享|海报|文案|分享|memento|share|poster|caption/i.test(s)) score.memento += 3;

    const maxKey = Object.keys(score).reduce((a, b) => (score[a] >= score[b] ? a : b));
    const maxVal = score[maxKey];
    let intent = maxKey;
    if (maxVal === 0) {
      intent = "ambiguous";
    } else if (intent === "faq" && score.recommend > score.faq) {
      intent = "recommendation";
    }

    const confidence = Math.min(0.95, 0.35 + maxVal * 0.12 + (tags.length ? 0.08 : 0));
    const needFollowup = maxVal <= 1 || intent === "ambiguous";

    return {
      intent,
      confidence,
      user_tags: tags,
      need_followup: needFollowup,
      followup_question: needFollowup ? t("followupLowConfidence") : "",
    };
  }

  function buildPlans(userText, tags) {
    const isEn = lang === "en";
    const couple = tags.includes("couple") || /对象|情侣|约会|couple|date/i.test(userText);
    const family = tags.includes("family") || /家人|孩子|家庭|family|kid/i.test(userText);
    const night = tags.includes("night_view") || /夜景|晚上|night|evening/i.test(userText);
    const half = tags.includes("half_day") || /半天|半日|half/i.test(userText);

    /** @type {Array<{ plan_title: string, recommended_time: string, highlights: string[], reason: string, cta: string[] }>} */
    const plans = [];

    if (couple && night) {
      plans.push({
        plan_title: isEn ? "Couple night edition" : "情侣夜景版",
        recommended_time: isEn ? "17:30 – 20:00" : "17:30–20:00",
        highlights: isEn
          ? ["Golden hour to city lights", "Great for photos and slow pacing", "Relaxed rhythm"]
          : ["黄昏到夜景的过渡", "适合观景与拍照", "节奏相对轻松"],
        reason: isEn
          ? "Matches couples who want atmosphere and night views without a rushed schedule."
          : "适合希望氛围感与夜景、又不想行程过紧的情侣。",
        cta: isEn ? ["Details", "Memento", "Tickets"] : ["查看详情", "生成纪念卡", "查看门票"],
      });
    } else if (family) {
      plans.push({
        plan_title: isEn ? "Family easy edition" : "家庭轻松版",
        recommended_time: isEn ? "15:00 – 18:30" : "15:00–18:30",
        highlights: isEn
          ? ["Observation-focused flow", "Leave buffer for meals and rest", "Avoid back-to-back thrills"]
          : ["以观光动线为主", "预留用餐与休息", "刺激性项目视体力分开安排"],
        reason: isEn
          ? "Prioritizes comfort, clear pacing, and age-friendly experiences."
          : "侧重舒适动线、时段缓冲与人群适配。",
        cta: isEn ? ["Details", "Memento", "Tickets"] : ["查看详情", "生成纪念卡", "查看门票"],
      });
    } else if (half) {
      plans.push({
        plan_title: isEn ? "Half-day compact" : "半日精华版",
        recommended_time: isEn ? "16:00 – 19:30" : "16:00–19:30",
        highlights: isEn
          ? ["Deck loop first", "Catch sunset if timing allows", "Optional dining nearby"]
          : ["优先走完观景主圈", "时间允许可衔接黄昏", "可加周边轻餐饮"],
        reason: isEn
          ? "Compresses the must-see loop for travelers with limited time."
          : "在时间有限时压缩必看动线，减少折返。",
        cta: isEn ? ["Details", "Memento", "Tickets"] : ["查看详情", "生成纪念卡", "查看门票"],
      });
    } else {
      plans.push({
        plan_title: isEn ? "First-visit classic" : "首次到访经典版",
        recommended_time: isEn ? "17:00 – 20:30" : "17:00–20:30",
        highlights: isEn
          ? ["Iconic panorama", "Night lights if you can stay", "Story-rich lookout moments"]
          : ["地标级全景", "若可停留可衔接夜景", "适合建立对澳门的第一印象"],
        reason: isEn
          ? "A balanced first pass: strong memory point plus optional night glow."
          : "平衡「记忆点」与「可选夜景」，适合建立第一印象。",
        cta: isEn ? ["Details", "Memento", "Tickets"] : ["查看详情", "生成纪念卡", "查看门票"],
      });
    }

    if (plans.length < 2) {
      plans.push({
        plan_title: isEn ? "Alternate: daytime focus" : "备选：日间轻松",
        recommended_time: isEn ? "14:30 – 17:30" : "14:30–17:30",
        highlights: isEn
          ? ["Softer light for photos", "Shorter queues possible", "Add coffee or light meal"]
          : ["光线柔和适合拍照", "部分时段人流相对可控", "可加咖啡轻食"],
        reason: isEn ? "If you prefer daylight and a calmer pace." : "若你更偏好日光与轻松节奏。",
        cta: isEn ? ["Details", "Memento"] : ["查看详情", "生成纪念卡"],
      });
    }

    return plans;
  }

  function faqAnswer(text) {
    const s = text.toLowerCase();
    if (/门票|票价|多少钱|price|ticket|cost/i.test(s)) return { type: "text", html: escapeHtml(t("faqTicket")) };
    if (/开放|时间|几点|关门|hours|open|close/i.test(s)) return { type: "text", html: escapeHtml(t("faqHours")) };
    if (/交通|怎么去|巴士|打车|bus|taxi|how to get/i.test(s)) return { type: "text", html: escapeHtml(t("faqTransport")) };
    if (/家人|老人|孩子|家庭|带娃|family|kid|elder/i.test(s) && /适合|轻松|安全|suitable|easy/i.test(s))
      return { type: "text", html: escapeHtml(t("faqFamily")) };
    if (/下雨|雨天|rain/i.test(s)) return { type: "text", html: escapeHtml(t("faqRain")) };
    return null;
  }

  function escapeHtml(str) {
    const d = document.createElement("div");
    d.textContent = str;
    return d.innerHTML;
  }

  /** 模型返回的纯文本转气泡 HTML（保留换行） */
  function formatAssistantHtml(raw) {
    return escapeHtml(String(raw)).replace(/\n/g, "<br/>");
  }

  function seedingAnswer() {
    const isEn = lang === "en";
    const p = isEn
      ? "Macau Tower is one of the clearest skyline anchors in Macau — great for a strong first memory. Start with the deck loop; if you can stay for golden hour, the mood shifts completely. Want me to shape a half-day or night-focused plan?"
      : "澳门塔是澳门天际线里最「一眼即识」的地标之一，很适合作为你对这座城市的第一印象锚点。建议先走观景主圈；若能待到黄昏，氛围会完全不同。需要我按半天或夜景帮你排一版吗？";
    return { type: "text", html: escapeHtml(p) };
  }

  function routeCardsHtml(plans) {
    const cards = plans
      .map((p) => {
        const hl = p.highlights.map((x) => `<li>${escapeHtml(x)}</li>`).join("");
        const actions = p.cta
          .map((label) => {
            if (/门票|ticket/i.test(label))
              return `<a href="https://www.macautower.com.mo/" target="_blank" rel="noopener noreferrer" data-track="route_ticket">${escapeHtml(
                label
              )}</a>`;
            if (/纪念|memento/i.test(label))
              return `<button type="button" class="js-memento-from-card">${escapeHtml(label)}</button>`;
            return `<button type="button" class="js-detail">${escapeHtml(label)}</button>`;
          })
          .join("");
        return `<article class="route-card">
          <div class="route-card__title">${escapeHtml(p.plan_title)}</div>
          <div class="route-card__time">${escapeHtml(p.recommended_time)}</div>
          <ul>${hl}</ul>
          <p class="route-card__reason">${escapeHtml(p.reason)}</p>
          <div class="route-card__actions">${actions}</div>
        </article>`;
      })
      .join("");
    return `<div class="msg__bubble"><p style="margin:0 0 0.75rem">${escapeHtml(
      t("defaultRecommend")
    )}</p><div class="route-cards">${cards}</div></div>`;
  }

  /** 为 Agent 消息挂载虚拟塔形象头像 */
  function buildAgentAvatar() {
    const av = document.createElement("div");
    av.className = "msg__avatar";
    av.setAttribute("aria-hidden", "true");
    const img = document.createElement("img");
    img.src = TOTA_CHIBI_SRC;
    img.alt = "";
    img.width = 42;
    img.height = 42;
    av.appendChild(img);
    return av;
  }

  function wrapAgentRow(bubbleEl) {
    const row = document.createElement("div");
    row.className = "msg msg--agent";
    const col = document.createElement("div");
    col.className = "msg__column";
    col.appendChild(bubbleEl);
    row.appendChild(buildAgentAvatar());
    row.appendChild(col);
    return row;
  }

  function appendAgentMessage(htmlOrNode, isNode = false) {
    const chat = document.getElementById("chat");
    let bubble;
    if (isNode) {
      bubble = htmlOrNode;
    } else {
      bubble = document.createElement("div");
      bubble.className = "msg__bubble";
      bubble.innerHTML = htmlOrNode;
    }
    const wrap = wrapAgentRow(bubble);
    chat.appendChild(wrap);
    chat.scrollTop = chat.scrollHeight;
    bindCardActions(wrap);
  }

  function appendUserMessage(text) {
    const chat = document.getElementById("chat");
    const wrap = document.createElement("div");
    wrap.className = "msg msg--user";
    wrap.innerHTML = `<div class="msg__bubble">${escapeHtml(text)}</div>`;
    chat.appendChild(wrap);
    chat.scrollTop = chat.scrollHeight;
  }

  function showTyping() {
    const chat = document.getElementById("chat");
    const id = "typing-" + Date.now();
    const bubble = document.createElement("div");
    bubble.className = "msg__bubble typing";
    bubble.innerHTML = "<span></span><span></span><span></span>";
    const wrap = wrapAgentRow(bubble);
    wrap.id = id;
    chat.appendChild(wrap);
    chat.scrollTop = chat.scrollHeight;
    return id;
  }

  function removeTyping(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
  }

  function bindCardActions(container) {
    container.querySelectorAll(".js-memento-from-card").forEach((btn) => {
      btn.addEventListener("click", () => {
        analytics.track("memento_click", { from: "route_card" });
        openMemento();
      });
    });
    container.querySelectorAll(".js-detail").forEach((btn) => {
      btn.addEventListener("click", () => {
        analytics.track("detail_click", {});
        void scrollToSnapSection("guide");
      });
    });
    container.querySelectorAll("a[data-track]").forEach((a) => {
      a.addEventListener("click", () => analytics.track("conversion_click", { href: a.getAttribute("href") }));
    });
  }

  function processReply(userText) {
    const det = detectIntent(userText);
    sessionContext.intent = det.intent;
    sessionContext.tags = det.user_tags;

    analytics.track("intent_detected", {
      intent: det.intent,
      confidence: det.confidence,
      tags: det.user_tags,
    });

    const faq = faqAnswer(userText);
    if (faq) return faq;

    if (det.need_followup && det.followup_question) {
      return { type: "text", html: escapeHtml(det.followup_question) };
    }

    if (det.intent === "faq") {
      return { type: "text", html: escapeHtml(t("faqGeneric")) };
    }

    // 种草：意图为 seed（如「值得去吗」）或首次到访问句
    if (det.intent === "seed") {
      return seedingAnswer();
    }

    if (
      /值得|worth|第一次|first/i.test(userText) &&
      (/吗|？|\?/i.test(userText) || /值得去|worth it/i.test(userText))
    ) {
      return seedingAnswer();
    }

    if (det.intent === "memento") {
      sessionContext.lastPlan = buildPlans(userText, det.user_tags)[0];
      return { type: "text", html: escapeHtml(generateMemorialText()) };
    }

    const plans = buildPlans(userText, det.user_tags);
    sessionContext.lastPlan = plans[0];
    return { type: "route", plans };
  }

  /** 纯本地规则回复（无远程 Agent），不写「线上不可用」提示 */
  function appendPureLocalReply(reply) {
    if (reply.type === "route") {
      const div = document.createElement("div");
      div.innerHTML = routeCardsHtml(reply.plans);
      const inner = div.firstElementChild;
      appendAgentMessage(inner, true);
      analytics.track("recommendation_shown", { count: reply.plans.length });
      chatHistory.push({
        role: "assistant",
        content: reply.plans.map((p) => p.plan_title).join("；"),
      });
    } else {
      appendAgentMessage(reply.html);
      const tmp = document.createElement("div");
      tmp.innerHTML = reply.html;
      chatHistory.push({ role: "assistant", content: tmp.textContent.trim() });
    }
  }

  async function sendUserMessage(text) {
    const trimmed = (text || "").trim();
    if (!trimmed) return;
    appendUserMessage(trimmed);
    chatHistory.push({ role: "user", content: trimmed });

    const tid = showTyping();

    if (!USE_REMOTE_AGENT) {
      window.setTimeout(() => {
        removeTyping(tid);
        const reply = processReply(trimmed);
        appendPureLocalReply(reply);
        analytics.track("message_round", {});
      }, 350);
      return;
    }

    try {
      const res = await fetch(`${API_BASE}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          messages: chatHistory.slice(-20),
          max_tokens: 1000,
          temperature: 0.7,
        }),
      });
      removeTyping(tid);
      if (!res.ok) {
        const errText = await res.text();
        throw new Error(errText || String(res.status));
      }
      const data = await res.json();
      const content = data.message && data.message.content;
      if (content == null || content === "") {
        throw new Error("empty assistant content");
      }
      chatHistory.push({ role: "assistant", content });
      appendAgentMessage(formatAssistantHtml(content));
      analytics.track("agent_api_success", {});
    } catch (err) {
      removeTyping(tid);
      analytics.track("agent_api_error", { message: String(err && err.message) });
      appendAgentMessage(escapeHtml(t("localFallbackHint")));
      const reply = processReply(trimmed);
      let assistantAcc = t("localFallbackHint");
      if (reply.type === "route") {
        const div = document.createElement("div");
        div.innerHTML = routeCardsHtml(reply.plans);
        const inner = div.firstElementChild;
        appendAgentMessage(inner, true);
        analytics.track("recommendation_shown", { count: reply.plans.length });
        assistantAcc += "\n" + reply.plans.map((p) => p.plan_title).join("；");
      } else {
        appendAgentMessage(reply.html);
        const tmp = document.createElement("div");
        tmp.innerHTML = reply.html;
        assistantAcc += "\n" + tmp.textContent.trim();
      }
      chatHistory.push({ role: "assistant", content: assistantAcc });
    }

    analytics.track("message_round", {});
  }

  function generateMemorialText() {
    const isEn = lang === "en";
    const tags = sessionContext.tags || [];
    const plan = sessionContext.lastPlan;
    if (plan) {
      const theme = plan.plan_title;
      if (tags.includes("couple") || /情侣|夜景/i.test(theme)) {
        return isEn
          ? "From Macau Tower tonight: the city lights don’t rush — they gather. Share this height, this breeze, and this slow glow with someone who matters."
          : "在澳门塔的这一晚，城市的灯不急不躁，一层层亮起来。把这份高度、风和慢下来的光，留给重要的人。";
      }
      if (tags.includes("family")) {
        return isEn
          ? "A gentle loop above Macau — easy pacing, wide views, and a memory the whole family can share."
          : "在澳门塔上慢慢走、远远看，把轻松和风景都留给家人，这一趟就值得。";
      }
    }
    return t("memorialFallback");
  }

  function openMemento() {
    const text = generateMemorialText();
    document.getElementById("memento-text").textContent = text;
    const meta =
      lang === "en"
        ? `Tags: ${sessionContext.tags.join(", ") || "—"} · Demo caption`
        : `标签：${sessionContext.tags.join("、") || "—"} · 演示文案`;
    document.getElementById("memento-meta").textContent = meta;
    const modal = document.getElementById("modal-memento");
    modal.hidden = false;
    analytics.track("memento_open", {});
  }

  function closeModal() {
    document.getElementById("modal-memento").hidden = true;
  }

  function initParticles() {
    const canvas = document.getElementById("particle-canvas");
    const hero = document.getElementById("hero");
    if (!canvas || !canvas.getContext || !hero) return;
    const ctx = canvas.getContext("2d");
    let w = 0;
    let h = 0;
    const particles = [];
    const N = 48;

    function resize() {
      w = canvas.width = hero.offsetWidth;
      h = canvas.height = hero.offsetHeight;
    }

    for (let i = 0; i < N; i++) {
      particles.push({
        x: Math.random(),
        y: Math.random(),
        r: Math.random() * 1.2 + 0.3,
        vx: (Math.random() - 0.5) * 0.00025,
        vy: (Math.random() - 0.5) * 0.0002,
        a: Math.random() * 0.35 + 0.1,
      });
    }

    function tick() {
      if (w > 0 && h > 0) {
        ctx.clearRect(0, 0, w, h);
        particles.forEach((p) => {
          p.x += p.vx;
          p.y += p.vy;
          if (p.x < 0 || p.x > 1) p.vx *= -1;
          if (p.y < 0 || p.y > 1) p.vy *= -1;
          ctx.beginPath();
          ctx.fillStyle = `rgba(140, 170, 255, ${p.a})`;
          ctx.arc(p.x * w, p.y * h, p.r, 0, Math.PI * 2);
          ctx.fill();
        });
      }
      requestAnimationFrame(tick);
    }

    resize();
    window.addEventListener("resize", resize);
    if (typeof ResizeObserver !== "undefined") {
      const ro = new ResizeObserver(() => resize());
      ro.observe(hero);
    }
    window.requestAnimationFrame(() => resize());
    tick();
  }

  /** 顶栏本身高度（px），不含额外呼吸间距 */
  function getHeaderBarHeight() {
    const header = document.querySelector(".site-header");
    if (!header) return 80;
    return Math.ceil(header.getBoundingClientRect().height);
  }

  /** 固定顶栏 + 呼吸间距（px），整页滚动只在此处减一次，避免 scroll-padding 与 scroll-margin 叠加 */
  function getFixedHeaderGap() {
    return getHeaderBarHeight() + 12;
  }

  /** 写入 html 的 scroll-padding-top，与 scroll-snap、scrollIntoView 共用同一顶栏留白 */
  function syncHeaderAnchorOffset() {
    document.documentElement.style.setProperty("--header-anchor-offset", `${getFixedHeaderGap()}px`);
  }

  /**
   * 程序化滚到指定 id 区块顶边（对齐固定顶栏）。
   * html 上 mandatory 纵向 scroll-snap 与 scrollIntoView(smooth) 会抢滚动，易卡在相邻屏之间；
   * 故短暂关闭 snap，用 window.scrollTo 像素定位，结束后再恢复。
   * @param {string} sectionId
   * @param {{ smooth?: boolean }} [opts]
   */
  function scrollToSectionPixel(sectionId, opts) {
    syncHeaderAnchorOffset();
    const el = document.getElementById(sectionId);
    if (!el) return Promise.resolve();

    const o = opts || {};
    const allowSmooth = o.smooth !== false;
    const html = document.documentElement;

    return new Promise((resolve) => {
      const prevSnap = html.style.scrollSnapType;
      html.style.scrollSnapType = "none";

      const cleanup = () => {
        if (!prevSnap) html.style.removeProperty("scroll-snap-type");
        else html.style.scrollSnapType = prevSnap;
      };

      const run = () => {
        const pad = getFixedHeaderGap();
        const targetY = Math.max(0, el.getBoundingClientRect().top + window.pageYOffset - pad);
        const cur = window.pageYOffset;
        const useSmooth = allowSmooth && Math.abs(targetY - cur) > 12;

        let settled = false;
        const finish = () => {
          if (settled) return;
          settled = true;
          cleanup();
          html.removeEventListener("scrollend", onEnd);
          window.clearTimeout(tid);
          resolve();
        };
        const onEnd = () => finish();
        html.addEventListener("scrollend", onEnd, { passive: true });
        const tid = window.setTimeout(finish, useSmooth ? 950 : 80);
        window.scrollTo({ top: targetY, behavior: useSmooth ? "smooth" : "auto" });
      };

      window.requestAnimationFrame(run);
    });
  }

  /** 路线卡「查看详情」等 */
  function scrollToSnapSection(sectionId, smooth) {
    return scrollToSectionPixel(sectionId, { smooth: smooth !== false });
  }

  function scrollToHighlights() {
    return scrollToSectionPixel("highlights");
  }

  function scrollToAgentChat() {
    return scrollToSectionPixel("agent");
  }

  function focusChatInput() {
    const input = document.getElementById("chat-input");
    if (input) input.focus({ preventScroll: true });
  }

  function init() {
    analytics.track("page_view", { path: "/" });
    applyI18n();
    syncHeaderAnchorOffset();
    window.addEventListener("resize", () => syncHeaderAnchorOffset());

    document.getElementById("lang-toggle").addEventListener("click", () => {
      lang = lang === "zh" ? "en" : "zh";
      chatHistory = [];
      analytics.track("lang_toggle", { lang });
      applyI18n();
      requestAnimationFrame(() => syncHeaderAnchorOffset());
    });

    document.getElementById("cta-explore").addEventListener("click", () => {
      analytics.track("cta_click", { id: "explore" });
      void scrollToHighlights();
    });

    document.querySelectorAll('a[href="#highlights"]').forEach((a) => {
      a.addEventListener("click", (e) => {
        e.preventDefault();
        void scrollToHighlights();
      });
    });

    document.getElementById("cta-chat").addEventListener("click", () => {
      analytics.track("cta_click", { id: "chat" });
      void scrollToAgentChat().then(() => focusChatInput());
    });

    document.querySelectorAll("a.js-scroll-agent").forEach((a) => {
      a.addEventListener("click", (e) => {
        e.preventDefault();
        void scrollToAgentChat().then(() => focusChatInput());
      });
    });

    document.getElementById("chat-form").addEventListener("submit", (e) => {
      e.preventDefault();
      const input = document.getElementById("chat-input");
      sendUserMessage(input.value);
      input.value = "";
      analytics.track("chat_submit", {});
    });

    document.getElementById("btn-memento").addEventListener("click", () => {
      openMemento();
    });

    document.getElementById("copy-memento").addEventListener("click", async () => {
      const text = document.getElementById("memento-text").textContent;
      try {
        await navigator.clipboard.writeText(text);
        analytics.track("memento_copy", {});
      } catch {
        analytics.track("memento_copy_fail", {});
      }
    });

    document.getElementById("regen-memento").addEventListener("click", () => {
      const el = document.getElementById("memento-text");
      el.textContent = generateMemorialText();
      analytics.track("memento_regen", {});
    });

    document.querySelectorAll("[data-close-modal]").forEach((el) => {
      el.addEventListener("click", closeModal);
    });

    initParticles();

    // 首屏停留时长（简单示例）
    const t0 = Date.now();
    window.addEventListener("beforeunload", () => {
      analytics.track("time_on_page_ms", { ms: Date.now() - t0 });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
