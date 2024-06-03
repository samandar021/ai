from modeltranslation.translator import TranslationOptions, register

from .models import Title


@register(Title)
class TitletTranslation(TranslationOptions):
    fields = ('title', 'body')