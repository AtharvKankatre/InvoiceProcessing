"""
URL configuration for sap_invoice project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
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
from django.urls import path, include
from user.models import User
from rest_framework import routers
from user.views import UserViewSet
from .views import LoginAPI

# from knox import views as knox_views
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

# Serializers define the API representation
# class UserSerializer(serializers.HyperlinkedModelSerializer):
#     class Meta:
#         model = User
#         fields = ['url', 'username', 'email', 'is_staff']


# ViewSets define the view behavior
# class UserViewSet(viewsets.ModelViewSet):
#     queryset = User.objects.all()
#     print("queryset", queryset)
#     serializer_class = UserSerializer


# Routers provide an easy way of automatically determining the URL conf.
router = routers.DefaultRouter()
router.register(r"users", UserViewSet)

urlpatterns = [
    path("", include(router.urls)),
    path("api/retail/", include("retail.urls")),
    path("api/sales/", include("sales.urls")),
    path("api/admin/", admin.site.urls),
    # rest framework auth api path
    # path('api-auth/', include('rest_framework.urls', namespace='rest_framework')),
    # path(r'api/auth/', include('knox.urls')),
    # from django.urls import path
    # from knox import views as knox_views
    # path("api/auth/login/", LoginAPI.as_view(), name="knox_login"),
    # path("api/auth/logout/", knox_views.LogoutView.as_view(), name="knox_logout"),
    # path(
    #     "api/auth/logoutall/",
    #     knox_views.LogoutAllView.as_view(),
    #     name="knox_logout_all",
    # ),
    path("api/auth/login/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
]
