from django.contrib import admin

# Register your models here.

from .models import Title, IOSFiles

admin.site.register(Title)
admin.site.register(IOSFiles)