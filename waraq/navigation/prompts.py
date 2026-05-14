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
