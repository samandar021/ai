from django.urls import path, include, re_path
# import routers
from rest_framework import routers
from rest_framework.authtoken import views as auth_views
from .views import *

# define the router
router = routers.DefaultRouter()

# define the router path and viewset to be used

app_name = 'title'

urlpatterns = [
    path('', include(router.urls)),
    path('auth/', include('rest_framework.urls')),
    re_path(r"^title/$", TitleView.as_view(), name='title view'),
    path("title/<pk>", TitleUpdateView.as_view(), name='update title view'),
    re_path(r"^iosfiles/$", IOSFileView.as_view(), name='iosfile view'),
    path("iosfiles/<pk>", IOSFileUpdateView.as_view(), name='update iosfiles view'),

]
