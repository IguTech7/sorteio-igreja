import random
import io
import qrcode
from django.db import IntegrityError, transaction
from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_exempt
import json

from .models import Participante, Configuracao, Sorteio, RegistroComprovante
from django.utils import timezone


def index(request):
    config = Configuracao.get()
    return render(request, 'rifa/index.html', {'config': config})


@require_GET
def api_status(request):
    config = Configuracao.get()
    participantes = Participante.objects.all()
    ocupados = {p.numero: p.nome for p in participantes}
    vendidos = participantes.count()
    return JsonResponse({
        'ocupados': ocupados,
        'vendidos': vendidos,
        'disponiveis': config.total_numeros - vendidos,
        'arrecadado': float(config.valor * vendidos),
        'valor': float(config.valor),
        'total_numeros': config.total_numeros,
    })


@csrf_exempt
@require_POST
def api_participar(request):
    try:
        data = json.loads(request.body)
        numeros = data.get('numeros', [])
        nome = data.get('nome', '').strip()
        telefone = data.get('telefone', '').strip()
    except:
        return JsonResponse({'ok': False, 'erro': 'Dados inválidos.'}, status=400)

    config = Configuracao.get()

    if not nome:
        return JsonResponse({'ok': False, 'erro': 'Nome é obrigatório.'}, status=400)

    if not numeros:
        return JsonResponse({'ok': False, 'erro': 'Selecione ao menos um número.'}, status=400)

    try:
        with transaction.atomic():
            for numero in numeros:
                numero = int(numero)
                if numero < 1 or numero > config.total_numeros:
                    return JsonResponse({'ok': False, 'erro': f'Número {numero} inválido.'}, status=400)
                if Participante.objects.filter(numero=numero).exists():
                    return JsonResponse({'ok': False, 'erro': f'O número {numero} já está ocupado.'}, status=409)

            for numero in numeros:
                Participante.objects.create(numero=numero, nome=nome, telefone=telefone)

    except IntegrityError:
        return JsonResponse({'ok': False, 'erro': 'Um ou mais números já foram reservados.'}, status=409)

    return JsonResponse({'ok': True, 'mensagem': f'{len(numeros)} número(s) confirmado(s) para {nome}!'})


@require_GET
def api_vendidos(request):
    participantes = Participante.objects.all()
    data = [{'numero': p.numero, 'nome': p.nome} for p in participantes]
    return JsonResponse({'vendidos': data})


@csrf_exempt
@require_POST
def api_sortear(request):
    if not request.user.is_authenticated:
        return JsonResponse({'ok': False, 'erro': 'Não autorizado.'}, status=401)
    participantes = list(Participante.objects.all())
    if not participantes:
        return JsonResponse({'ok': False, 'erro': 'Nenhum número vendido para sortear.'}, status=400)
    vencedor = random.choice(participantes)
    Sorteio.objects.create(numero_vencedor=vencedor.numero, nome_vencedor=vencedor.nome)
    return JsonResponse({'ok': True, 'numero': vencedor.numero, 'nome': vencedor.nome})


@csrf_exempt
@require_POST
def api_resetar(request):
    if not request.user.is_authenticated:
        return JsonResponse({'ok': False, 'erro': 'Não autorizado.'}, status=401)
    Participante.objects.all().delete()
    Sorteio.objects.all().delete()
    return JsonResponse({'ok': True, 'mensagem': 'Rifa resetada com sucesso.'})


@require_GET
def qrcode_pix(request):
    config = Configuracao.get()
    dado = config.pix_emv.strip() if config.pix_emv.strip() else config.pix_chave
    img = qrcode.make(dado)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return HttpResponse(buf, content_type='image/png')


@csrf_exempt
@require_POST
def api_excluir(request):
    if not request.user.is_authenticated:
        return JsonResponse({'ok': False, 'erro': 'Não autorizado.'}, status=401)
    try:
        data = json.loads(request.body)
        numero = int(data.get('numero', 0))
    except (ValueError, KeyError):
        return JsonResponse({'ok': False, 'erro': 'Dados inválidos.'}, status=400)

    try:
        p = Participante.objects.get(numero=numero)
        nome = p.nome
        p.delete()
        return JsonResponse({'ok': True, 'mensagem': f'Número {numero} de {nome} removido.'})
    except Participante.DoesNotExist:
        return JsonResponse({'ok': False, 'erro': 'Número não encontrado.'}, status=404)


@csrf_exempt
@require_POST
def api_registrar_comprovante(request):
    try:
        nome_participante = request.POST.get('nome_participante', '').strip()
        pagador = request.POST.get('pagador', '').strip()
        data_hora_pix = request.POST.get('data_hora_pix', '').strip()
        valor = request.POST.get('valor', 0)
        texto_ocr = request.POST.get('texto_ocr', '').strip()
        imagem = request.FILES.get('imagem')

        RegistroComprovante.objects.create(
            nome_participante=nome_participante,
            pagador=pagador,
            data_hora_pix=data_hora_pix,
            valor=valor,
            texto_ocr=texto_ocr,
            imagem=imagem
        )
        return JsonResponse({'ok': True})
    except Exception as e:
        return JsonResponse({'ok': False, 'erro': str(e)}, status=400)

@require_GET
def api_comprovantes(request):
    if not request.user.is_authenticated:
        return JsonResponse({'ok': False, 'erro': 'Não autorizado.'}, status=401)
    registros = RegistroComprovante.objects.all().order_by('-criado_em')
    data = [{
        'id': r.id,
        'pagador': r.pagador,
        'data_hora_pix': r.data_hora_pix,
        'valor': float(r.valor),
        'nome_participante': r.nome_participante,
        'criado_em': r.criado_em.astimezone().strftime('%d/%m/%Y %H:%M'),
        'imagem_url': r.imagem.url if r.imagem else None,
    } for r in registros]
    return JsonResponse({'comprovantes': data})


@csrf_exempt
@require_POST
def api_excluir_comprovante(request):
    if not request.user.is_authenticated:
        return JsonResponse({'ok': False, 'erro': 'Não autorizado.'}, status=401)
    try:
        data = json.loads(request.body)
        reg_id = int(data.get('id', 0))
    except:
        return JsonResponse({'ok': False, 'erro': 'Dados inválidos.'}, status=400)
    try:
        r = RegistroComprovante.objects.get(id=reg_id)
        r.delete()
        return JsonResponse({'ok': True})
    except RegistroComprovante.DoesNotExist:
        return JsonResponse({'ok': False, 'erro': 'Registro não encontrado.'}, status=404)


@csrf_exempt
@require_POST
def api_registrar_comprovante(request):
    try:
        nome_participante = request.POST.get('nome_participante', '').strip()
        pagador = request.POST.get('pagador', '').strip()
        data_hora_pix = request.POST.get('data_hora_pix', '').strip()
        valor = request.POST.get('valor', 0)
        texto_ocr = request.POST.get('texto_ocr', '').strip()
        imagem = request.FILES.get('imagem')

        RegistroComprovante.objects.create(
            nome_participante=nome_participante,
            pagador=pagador,
            data_hora_pix=data_hora_pix,
            valor=valor,
            texto_ocr=texto_ocr,
            imagem=imagem
        )
        return JsonResponse({'ok': True})
    except Exception as e:
        return JsonResponse({'ok': False, 'erro': str(e)}, status=400)


@require_GET
def api_comprovantes(request):
    if not request.user.is_authenticated:
        return JsonResponse({'ok': False, 'erro': 'Não autorizado.'}, status=401)
    registros = RegistroComprovante.objects.all().order_by('-criado_em')
    data = [{
        'id': r.id,
        'pagador': r.pagador,
        'data_hora_pix': r.data_hora_pix,
        'valor': float(r.valor),
        'nome_participante': r.nome_participante,
        'criado_em': r.criado_em.strftime('%d/%m/%Y %H:%M'),
        'imagem_url': r.imagem.url if r.imagem else None,
    } for r in registros]
    return JsonResponse({'comprovantes': data})