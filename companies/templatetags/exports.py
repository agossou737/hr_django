from django import template

register = template.Library()

LABELS = [("xlsx", "Excel"), ("pdf", "PDF"), ("csv", "CSV")]
CLS = ("btn border border-slate-300 font-medium text-slate-700 hover:bg-slate-150 "
       "dark:border-navy-450 dark:text-navy-100 dark:hover:bg-navy-500")


@register.simple_tag(takes_context=True)
def export_buttons(context):
    """Trois liens d'export (Excel, PDF, CSV) qui conservent les filtres de la page."""
    from django.utils.html import format_html, format_html_join

    params = context["request"].GET.copy()
    for key in ("export", "page"):
        params.pop(key, None)
    qs = params.urlencode()
    sep = "&" if qs else ""
    return format_html(
        '<div class="flex gap-1">{}</div>',
        format_html_join("", '<a class="{}" href="?{}{}export={}">{}</a>',
                         ((CLS, qs, sep, fmt, label) for fmt, label in LABELS)),
    )
