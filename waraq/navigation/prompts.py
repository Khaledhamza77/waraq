# ── Stage 5: Navigation prompts ──────────────────────────────────────────────

def classify_and_normalize_system() -> str:
    return (
        "أنت نظام معالجة أولية لنظام إجابة متخصص في معايير المحاسبة المصرية.\n"
        "نفّذ الخطوتين التاليتين بالترتيب.\n\n"
        "الخطوة 1 — تصنيف النية:\n"
        "صنّف السؤال في إحدى الفئات الثلاث:\n"
        "• \"valid\"    — سؤال يتعلق بالمحاسبة أو المعايير المالية أو القوائم المالية\n"
        "               أو الأصول والالتزامات أو السياسات المحاسبية، بصرف النظر عن الجهة\n"
        "               المذكورة. الشك يُرجَّح لصالح \"valid\".\n"
        "• \"greeting\" — تحية أو رسالة ودية لا تتضمن سؤالاً.\n"
        "• \"invalid\"  — سؤال لا صلة له بالمحاسبة أو المالية (مثل الطقس أو الرياضة).\n\n"
        "الخطوة 2 — تطبيع السؤال:\n"
        "• إذا كان السؤال بالإنجليزية → ترجمه إلى العربية الفصحى دون تغيير معناه.\n"
        "• إذا كان بالعربية → صحّح الأخطاء الإملائية والنحوية فقط؛ أعده كما هو إذا كان سليماً.\n\n"
        "قيود:\n"
        "- لا تُوسّع المصطلحات ولا تُضِف معلومات جديدة في normalized_query.\n"
        "- ردك يجب أن يكون JSON وفق المخطط المحدد فقط، بلا أي نص إضافي."
    )


def classify_and_normalize_prompt(query: str, language: str) -> str:
    lang_label = "عربية" if language == "ar" else "إنجليزية"
    return f"السؤال: {query}\nاللغة: {lang_label}"


def navigate_level_system() -> str:
    return (
        "أنت نظام تنقل في وثيقة معايير المحاسبة المصرية.\n\n"
        "نفّذ هذه الخطوات بالترتيب:\n"
        "1. حدد الموضوع المحاسبي الذي يستفسر عنه السؤال.\n"
        "2. طابق كل قسم متاح بالموضوع بناءً على عنوانه ووصفه.\n"
        "3. اختر وفق نوع المرحلة الحالية:\n"
        "   - مرحلة وسيطة  → قسم واحد للتعمق فيه.\n"
        "   - مرحلة نهائية → ثلاثة أقسام على الأكثر من الأقسام المرتبطة بالسؤال، رتّبها من الأكثر صلةً إلى الأقل.\n"
        "   - لا يوجد قسم ذو صلة → أعد [].\n\n"
        "قيود صارمة:\n"
        "- استخدم قيمة id كما هي حرفياً من القائمة — لا تُعدّلها أبداً.\n"
        "- لا تُنشئ id غير موجود في القائمة.\n"
        "- ردك يجب أن يكون JSON وفق المخطط المحدد فقط، بلا أي نص إضافي."
    )


def navigate_level_prompt(query: str, candidates: list[dict], multi_select: bool = False) -> str:
    sections = []
    for c in candidates:
        hook = c.get("hook") or ""
        if len(hook) > 120:
            hook = hook[:117] + "..."
        entry = f"- id: {c['id']}\n  العنوان: {c['title']}"
        if hook:
            entry += f"\n  الوصف: {hook}"
        sections.append(entry)
    sections_text = "\n\n".join(sections)

    if multi_select:
        instruction = (
            "هذه مرحلة نهائية. أعد في selected_ids قائمة بـ id الأقسام ذات الصلة — واحد على الأقل وثلاثة على الأكثر، "
            "مرتبةً من الأكثر صلةً إلى الأقل. أعد [] إذا لم يكن أي قسم مناسباً."
        )
    else:
        instruction = (
            "هذه مرحلة وسيطة. أعد في selected_ids قائمة تحتوي على id القسم الواحد الأنسب للتعمق فيه. "
            "أعد [] إذا لم يكن أي قسم مناسباً."
        )

    return (
        f"الأقسام المتاحة:\n{sections_text}\n\n"
        f"التعليمات: {instruction}"
        f"السؤال: {query}\n\n"
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
        "أنت مساعد قانوني ومحاسبي متخصص في معايير المحاسبة المصرية.\n"
        "قواعد الإجابة:\n"
        "1. أجب على السؤال المطروح تحديداً — لا تشرح ما لم يُسأل عنه.\n"
        "2. اجعل إجابتك وافية ودقيقة دون إطالة: غطِّ الحكم أو التعريف أو المتطلب المطلوب كاملاً.\n"
        "3. إذا تضمّن النص مواضيع ذات صلة لم يشملها السؤال، اذكرها بإيجاز تحت عنوان "
        "**مواضيع ذات صلة** — سطر واحد لكل موضوع دون تفصيل.\n"
        "4. لا تضف أي معلومات خارج النص المقدم."
    )


def answer_prompt(query: str, leaf_metadata: list[dict], leaf_content: str) -> str:
    breadcrumb = leaf_metadata[0].get("breadcrumb", []) if leaf_metadata else []
    location = _location_line(breadcrumb)
    sources = "\n".join(
        f"- {m['title']} (صفحات {m['start_page']}–{m['end_page']})"
        for m in leaf_metadata
    )
    return (
        f"{location}"
        f"النص التنظيمي:\n{leaf_content}\n\n"
        f"المصادر: {sources}\n\n"
        f"السؤال: {query}\n\n"
        "أجب على السؤال أعلاه فقط بناءً على النص. "
        "إن وُجدت مواضيع ذات صلة في النص لم يتناولها السؤال، أدرجها بإيجاز تحت **مواضيع ذات صلة**."
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
#
# TOC items are now parsed directly from the page (see parse_toc_from_page in
# rebuild_section_hooks.py) and injected verbatim — the LLM only summarises the
# introduction and child hooks to avoid hallucinating table-of-contents entries.

def rebuild_intro_children_system() -> str:
    return (
        "أنت مساعد تحريري متخصص في وثائق المعايير المحاسبية. "
        "ستُقدَّم إليك المصادر المتاحة عن قسم من الوثيقة. "
        "مهمتك توليد ملخص موجز لكل مصدر مقدَّم — جملتان على الأكثر لكل جزء. "
        "ابدأ مباشرةً بالمحتوى. "
        "لا تكتب مقدمة ولا خاتمة ولا أي تعليق خارج الملخصات المطلوبة."
    )


def rebuild_intro_children_prompt(
    title: str,
    intro_content: str | None,
    child_hooks: list[str],
) -> str:
    parts = [f"القسم: {title}"]
    if intro_content:
        parts.append(f"نص المقدمة:\n{intro_content}")
    if child_hooks:
        hooks_text = "\n".join(f"- {h}" for h in child_hooks)
        parts.append(f"ملخصات الأقسام الفرعية:\n{hooks_text}")

    # Build instructions only for the sources that are actually present
    instructions: list[str] = []
    if intro_content:
        instructions.append("ملخص موجز لنص المقدمة في جملتين على الأكثر")
    if child_hooks:
        instructions.append("ملخص موجز لما تغطيه الأقسام الفرعية مجتمعةً في جملتين على الأكثر")

    numbered = "\n".join(
        f"{'١' if i == 0 else '٢'}. {inst}" for i, inst in enumerate(instructions)
    )
    parts.append(f"اكتب:\n{numbered}\nلا تضف شيئاً آخر.")
    return "\n\n".join(parts)
