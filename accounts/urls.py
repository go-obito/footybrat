from django.urls import path

from .views import LoginView, MeView, RegisterView, TokenRefreshView

urlpatterns = [
    path("accounts/register/", RegisterView.as_view(), name="account-register"),
    path("accounts/login/", LoginView.as_view(), name="account-login"),
    path("accounts/token/refresh/", TokenRefreshView.as_view(), name="account-token-refresh"),
    path("accounts/me/", MeView.as_view(), name="account-me"),
    # Canonical auth aliases for frontend clients.
    path("auth/register/", RegisterView.as_view(), name="auth-register"),
    path("auth/login/", LoginView.as_view(), name="auth-login"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="auth-token-refresh"),
    path("auth/me/", MeView.as_view(), name="auth-me"),
]
