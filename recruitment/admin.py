from django.contrib import admin

from .models import Application, JobOffer

admin.site.register(JobOffer)
admin.site.register(Application)
