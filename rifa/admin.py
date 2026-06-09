from django.contrib import admin
from .models import Participante, Configuracao, Sorteio, RegistroComprovante


@admin.register(Configuracao)
class ConfiguracaoAdmin(admin.ModelAdmin):
    list_display = ['nome_campanha', 'valor', 'data_sorteio', 'premio']


@admin.register(Participante)
class ParticipanteAdmin(admin.ModelAdmin):
    list_display = ['numero', 'nome', 'telefone', 'criado_em']
    search_fields = ['nome', 'telefone']
    ordering = ['numero']


@admin.register(Sorteio)
class SorteioAdmin(admin.ModelAdmin):
    list_display = ['numero_vencedor', 'nome_vencedor', 'realizado_em']
    ordering = ['-realizado_em']


@admin.register(RegistroComprovante)
class RegistroComprovanteAdmin(admin.ModelAdmin):
    list_display = ('pagador', 'data_hora_pix', 'valor', 'nome_participante', 'criado_em')
    list_filter = ('criado_em',)
    search_fields = ('pagador', 'nome_participante')
    ordering = ('-criado_em',)