from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('api/status/', views.api_status, name='api_status'),
    path('api/participar/', views.api_participar, name='api_participar'),
    path('api/vendidos/', views.api_vendidos, name='api_vendidos'),
    path('api/sortear/', views.api_sortear, name='api_sortear'),
    path('api/resetar/', views.api_resetar, name='api_resetar'),
    path('api/qrcode/', views.qrcode_pix, name='qrcode_pix'),
    path('login/', auth_views.LoginView.as_view(template_name='rifa/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='/'), name='logout'),
    path('api/excluir/', views.api_excluir, name='api_excluir'),
    path('api/registrar-comprovante/', views.api_registrar_comprovante, name='api_registrar_comprovante'),
    path('api/comprovantes/', views.api_comprovantes, name='api_comprovantes'),
    path('api/excluir-comprovante/', views.api_excluir_comprovante, name='api_excluir_comprovante'),
    path('api/editar-comprovante/', views.api_editar_comprovante, name='api_editar_comprovante'),
    path('api/verificar-comprovante/', views.api_verificar_comprovante),
    path('api/registrar-tentativa/', views.api_registrar_tentativa, name='api_registrar_tentativa'),
    path('api/tentativas/', views.api_tentativas, name='api_tentativas'),
    path('api/excluir-tentativa/', views.api_excluir_tentativa, name='api_excluir_tentativa'),
    path('api/participar-admin/', views.api_participar_admin, name='api_participar_admin'),
    path('api/criar-pagamento/', views.api_criar_pagamento, name='api_criar_pagamento'),
    path('api/webhook-mp/', views.api_webhook_mp, name='api_webhook_mp'),
    path('api/buscar-participante/', views.api_buscar_participante, name='api_buscar_participante'),
]