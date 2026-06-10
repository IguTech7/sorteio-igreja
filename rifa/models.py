from django.db import models

class Participante(models.Model):
    numero = models.IntegerField(unique=True)
    nome = models.CharField(max_length=100)
    telefone = models.CharField(max_length=20, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['numero']

    def __str__(self):
        return f"#{self.numero} - {self.nome}"


class Configuracao(models.Model):
    nome_campanha = models.CharField(max_length=200, default="Rifa Beneficente")
    subtitulo = models.CharField(max_length=200, default="Campanha de Reforma do Templo")
    valor = models.DecimalField(max_digits=8, decimal_places=2, default=10.00)
    data_sorteio = models.DateField(null=True, blank=True)
    premio = models.CharField(max_length=200, default="Cesta Especial")
    causa = models.CharField(max_length=200, default="Reforma do Templo")
    pix_chave = models.CharField(max_length=200, default="contato@igrejaesperanca.com")
    pix_emv = models.TextField(blank=True)
    total_numeros = models.IntegerField(default=100)

    class Meta:
        verbose_name = "Configuração"

    def __str__(self):
        return self.nome_campanha

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class Sorteio(models.Model):
    numero_vencedor = models.IntegerField()
    nome_vencedor = models.CharField(max_length=100)
    realizado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Sorteio"
        ordering = ['-realizado_em']

    def __str__(self):
        return f"Sorteio: #{self.numero_vencedor} - {self.nome_vencedor}"

class RegistroComprovante(models.Model):
    nome_participante = models.CharField(max_length=100, blank=True)
    pagador = models.CharField(max_length=200, blank=True)
    data_hora_pix = models.CharField(max_length=50, blank=True)
    valor = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    texto_ocr = models.TextField(blank=True)
    imagem = models.ImageField(upload_to='comprovantes/', blank=True, null=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    numero = models.IntegerField(null=True, blank=True)

    class Meta:
        verbose_name = "Registro de Comprovante"
        verbose_name_plural = "Registros de Comprovantes"

    def __str__(self):
        return f"{self.pagador} — R${self.valor} — {self.data_hora_pix}"