"""mySearch URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, re_path, include
from search.views import IndexView, favicon_view, SearchSuggest, SearchView
from django.views.static import serve
from mySearch.settings import MEDIA_ROOT

urlpatterns = [

    path('admin/', admin.site.urls),
    path('', IndexView.as_view(), name='index'),
    path('suggest/', SearchSuggest.as_view(), name="suggest"),
    path('search/', SearchView.as_view(), name="search"),
    path('favicon.ico', favicon_view),

    re_path('^media/(?P<path>.*)', serve, {'document_root': MEDIA_ROOT})

]
