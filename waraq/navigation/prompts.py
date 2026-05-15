# ── Stage 5: Navigation prompts ──────────────────────────────────────────────

def normalize_query_system() -> str:
    return (
        "أنت مساعد لغوي. مهمتك فقط تنظيف السؤال وتحسين صياغته اللغوية: "
        "إذا كان بالإنجليزية فترجمه إلى العربية الفصحى، "
        "وإذا كان بالعربية فأعد صياغته بأسلوب رسمي واضح. "
        "لا تضف معلومات جديدة ولا توجّه السؤال نحو موضوع بعينه. "
        "أعد السؤال المُعاد صياغته فقط دون أي شرح."
    )


def normalize_query_prompt(query: str, language: str) -> str:
    if language == "en":
        return f"ترجم هذا السؤال إلى العربية الفصحى دون تغيير معناه:\n\n{query}"
    return f"أعد صياغة هذا السؤال بأسلوب رسمي واضح دون تغيير معناه:\n\n{query}"


def check_intent_system() -> str:
    return (
        "أنت نظام تصنيف لنظام إجابة متخصص في معايير المحاسبة المصرية. "
        "صنّف نية المستخدم في إحدى الفئات الثلاث:\n"
        "- 'valid': سؤال عن معايير المحاسبة المصرية أو القوائم المالية أو الالتزامات المحاسبية أو تفسير المعايير\n"
        "- 'greeting': تحية أو رسالة ودية لا تحتوي على سؤال محاسبي\n"
        "- 'invalid': أي موضوع خارج نطاق معايير المحاسبة المصرية\n\n"
        "تنبيه صارم: ردك يجب أن يكون JSON صحيحاً تماماً وفق المخطط المحدد. "
        "لا تضف أي نص خارج بنية JSON."
    )


def check_intent_prompt(query: str) -> str:
    return f"السؤال: {query}"


def navigate_level_system() -> str:
    return (
        "أنت نظام تنقل في وثيقة معايير المحاسبة المصرية. "
        "مهمتك اختيار الأقسام الأنسب للإجابة على سؤال المستخدم. "
        "اختر الأقسام الأكثر صلة — القسم الجزئي الصلة مقبول إذا لم يكن هناك قسم مطابق تماماً. "
        "إذا لم يكن أي قسم ذا صلة على الإطلاق، أعد قائمة فارغة.\n\n"
        "تنبيه صارم: ردك يجب أن يكون JSON صحيحاً تماماً وفق المخطط المحدد. "
        "لا تضف أي نص خارج بنية JSON."
    )


def navigate_level_prompt(query: str, candidates: list[dict], multi_select: bool = False) -> str:
    sections = []
    for c in candidates:
        hook = c.get("hook")
        entry = f"- id: {c['id']}\n  العنوان: {c['title']}"
        if hook:
            entry += f"\n  الوصف: {hook}"
        sections.append(entry)
    sections_text = "\n\n".join(sections)

    if multi_select:
        instruction = (
            f"بناءً على السؤال: «{query}»\n"
            "أعد قائمة بـ id الأقسام الأكثر صلة. "
            "يمكنك اختيار قسم واحد أو أكثر إذا كانت عدة أقسام ذات صلة. "
            "إذا لم يكن أي قسم مناسباً على الإطلاق، أعد قائمة فارغة []."
        )
    else:
        instruction = (
            f"بناءً على السؤال: «{query}»\n"
            "أعد قائمة تحتوي على id القسم الواحد الأنسب للتعمق فيه. "
            "إذا لم يكن أي قسم مناسباً، أعد قائمة فارغة []."
        )

    return (
        f"السؤال: {query}\n\n"
        f"الأقسام المتاحة:\n\n{sections_text}\n\n"
        f"{instruction}\n\n"
        "تذكير: ردك يجب أن يكون JSON صحيحاً تماماً."
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


# ── Stage 6: Response generation prompts ─────────────────────────────────────

def answer_system() -> str:
    return (
        "أنت مساعد قانوني ومحاسبي متخصص في معايير المحاسبة المصرية. "
        "مهمتك الإجابة على أسئلة المستخدمين بدقة واحترافية بناءً حصراً على النص التنظيمي المقدم إليك. "
        "لا تضف أي معلومات خارج النص المقدم.\n\n"
        "تنبيه صارم: ردك يجب أن يكون JSON صحيحاً تماماً وفق المخطط المحدد. "
        "لا تضف أي نص خارج بنية JSON."
    )


def answer_prompt(query: str, leaf_metadata: list[dict], leaf_content: str) -> str:
    sources = "\n".join(
        f"- {m['title']} (صفحات {m['start_page']}–{m['end_page']})"
        for m in leaf_metadata
    )
    return (
        f"السؤال: {query}\n\n"
        f"المصادر: {sources}\n\n"
        f"النص التنظيمي:\n{leaf_content}\n\n"
        "بناءً على النص أعلاه فقط، أجب على السؤال بشكل كامل ومفصّل."
    )


def greeting_system() -> str:
    return (
        "أنت مساعد متخصص في معايير المحاسبة المصرية. "
        "عندما يُرسل إليك تحية أو رسالة ترحيبية، رد بأسلوب ودي ومهني باللغة ذاتها التي كتب بها المستخدم. "
        "عرّف بنفسك باختصار، واشرح ما يمكنك مساعدة المستخدم فيه من أسئلة تتعلق بمعايير المحاسبة المصرية."
    )


def greeting_prompt(query: str) -> str:
    return query


# ── Stage 4b: Section hook rebuild prompts ───────────────────────────────────
# Used by scripts/rebuild_section_hooks.py.
# Validated on sections 3–9 of the Egyptian Accounting Standards PDF (208 pages).
# When onboarding a new document: ensure all non-leaf section nodes in the
# target range have contents_page (single page int/str) and introduction_pages
# (list of int/str, may be empty) before running the script.

def rebuild_section_system() -> str:
    return (
        "أنت محلل محاسبي متخصص في معايير المحاسبة المصرية. "
        "مهمتك كتابة وصف موجز ومنظم لقسم رئيسي يتكون من ثلاث جمل بالترتيب التالي تماماً:\n"
        "يحتوي هذا القسم على: [ملخص فهرس المحتويات]\n"
        "يتناول هذا القسم: [ملخص المقدمة]\n"
        "يلخص هذا القسم: [ملخص الأقسام الفرعية]\n"
        "التزم بهذا الهيكل حرفياً. لا تضف أي نص خارجه."
    )


def rebuild_section_prompt(
    title: str,
    toc_content: str | None,
    intro_content: str | None,
    child_hooks: list[str],
) -> str:
    parts = [f"القسم: {title}"]
    if toc_content:
        parts.append(f"فهرس المحتويات:\n{toc_content}")
    if intro_content:
        parts.append(f"المقدمة:\n{intro_content}")
    hooks_text = "\n".join(f"- {h}" for h in child_hooks)
    parts.append(f"ملخصات الأقسام الفرعية:\n{hooks_text}")
    parts.append(
        "اكتب الوصف بالهيكل التالي تماماً:\n"
        "يحتوي هذا القسم على: [ملخص فهرس المحتويات في جملة واحدة]\n"
        "يتناول هذا القسم: [ملخص المقدمة في جملة واحدة]\n"
        "يلخص هذا القسم: [ملخص الأقسام الفرعية في جملة واحدة]"
    )
    return "\n\n".join(parts)
