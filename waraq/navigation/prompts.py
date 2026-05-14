# ── Stage 5: Navigation prompts ──────────────────────────────────────────────

def normalize_query_system() -> str:
    return (
        "أنت متخصص في معايير المحاسبة المصرية. "
        "إذا كان السؤال بالإنجليزية، ترجمه أولاً إلى العربية. "
        "ثم أعد صياغته بأسلوب رسمي ودقيق يناسب البحث في وثيقة تنظيمية. "
        "أعد السؤال المُعاد صياغته فقط دون أي شرح."
    )


def normalize_query_prompt(query: str, language: str) -> str:
    if language == "en":
        return f"ترجم هذا السؤال إلى العربية الفصحى وأعد صياغته بشكل رسمي:\n\n{query}"
    return f"أعد صياغة هذا السؤال بأسلوب رسمي ودقيق:\n\n{query}"


def check_intent_system() -> str:
    return (
        "أنت نظام تصنيف لنظام إجابة متخصص في معايير المحاسبة المصرية. "
        "صنّف نية المستخدم في إحدى الفئات الثلاث:\n"
        "- 'valid': سؤال عن معايير المحاسبة المصرية أو القوائم المالية أو الالتزامات المحاسبية أو تفسير المعايير\n"
        "- 'greeting': تحية أو رسالة ودية لا تحتوي على سؤال محاسبي\n"
        "- 'invalid': أي موضوع خارج نطاق معايير المحاسبة المصرية"
    )


def check_intent_prompt(query: str) -> str:
    return f"السؤال: {query}"


def navigate_level_system() -> str:
    return (
        "أنت نظام تنقل في وثيقة معايير المحاسبة المصرية. "
        "اختر القسم الأنسب للإجابة على سؤال المستخدم من بين الأقسام المتاحة. "
        "إذا لم يكن أي قسم ذا صلة بالسؤال، أعد null."
    )


def navigate_level_prompt(query: str, candidates: list[dict]) -> str:
    sections = []
    for c in candidates:
        hook = c.get("hook")
        entry = f"- id: {c['id']}\n  العنوان: {c['title']}"
        if hook:
            entry += f"\n  الوصف: {hook}"
        sections.append(entry)
    sections_text = "\n\n".join(sections)
    return (
        f"السؤال: {query}\n\n"
        f"الأقسام المتاحة:\n\n{sections_text}\n\n"
        "أعد id القسم الأكثر صلة بالسؤال، أو null إذا لم يكن أي قسم مناسباً."
    )


# ── Stage 4: Summary prompts ──────────────────────────────────────────────────

def _location_line(breadcrumb: list[str]) -> str:
    if not breadcrumb:
        return ""
    return f"الموقع في الوثيقة: {' > '.join(breadcrumb)}\n"


def summarize_leaf_prompt(title: str, content: str, breadcrumb: list[str] | None = None) -> str:
    location = _location_line(breadcrumb or [])
    return (
        f"{location}"
        f"القسم: {title}\n\n"
        f"النص:\n{content}\n\n"
        "بناءً على النص أعلاه، اكتب فقرة واحدة موجزة باللغة العربية تصف: "
        "ما هي الأسئلة المحاسبية أو التنظيمية التي يجيب عليها هذا القسم؟ "
        "وما هي المعايير أو المفاهيم أو الالتزامات التي يغطيها؟ "
        "اكتب الفقرة بأسلوب يساعد على الاسترجاع — أي أن شخصاً يبحث عن موضوع معين يستطيع من خلالها معرفة ما إذا كان هذا القسم يجيب على سؤاله."
    )


def summarize_leaf_system() -> str:
    return (
        "أنت محلل محاسبي متخصص في معايير المحاسبة المصرية. "
        "مهمتك كتابة ملخصات موجزة ودقيقة للأقسام التنظيمية تساعد على استرجاعها لاحقاً."
    )


def rollup_prompt(title: str, child_hooks: list[str], breadcrumb: list[str] | None = None) -> str:
    location = _location_line(breadcrumb or [])
    hooks_text = "\n".join(f"- {h}" for h in child_hooks)
    return (
        f"{location}"
        f"القسم الرئيسي: {title}\n\n"
        f"ملخصات الأقسام الفرعية:\n{hooks_text}\n\n"
        "بناءً على ملخصات الأقسام الفرعية أعلاه، اكتب فقرة واحدة موجزة باللغة العربية "
        "تصف النطاق الكامل لهذا القسم الرئيسي: ما هي المواضيع التي يغطيها مجتمعةً؟ "
        "اكتب الفقرة بأسلوب يساعد على الاسترجاع."
    )


def rollup_system() -> str:
    return (
        "أنت محلل محاسبي متخصص في معايير المحاسبة المصرية. "
        "مهمتك تجميع ملخصات الأقسام الفرعية في ملخص موحد للقسم الرئيسي."
    )
