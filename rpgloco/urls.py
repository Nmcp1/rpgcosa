# rpgloco/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views

from accounts.views import start_menu, logout_view

urlpatterns = [
    path("admin/", admin.site.urls),

    # Menú de inicio
    path("", start_menu, name="start_menu"),

    # API de cuentas (registro con invitación por JSON)
    path("api/accounts/", include("accounts.urls")),
    path("logout/", logout_view, name="logout"),

    # API del juego + vistas HTML del juego (world, shop, etc.)
    path("api/game/", include("game.urls")),

    # Logout sencillo que vuelve al menú
    path(
        "logout/",
        auth_views.LogoutView.as_view(next_page="start_menu"),
        name="logout",
    ),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
